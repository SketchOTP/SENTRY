"""Small authenticated I/O endpoint for a remote SENTRY projection host.

This process is intended to run on the RPi5.  It owns only PipeWire capture,
PipeWire playback, and the logical audio-output selector.  It has no ANIMA,
Home Assistant, database, model, or filesystem-authority interface.
"""

from __future__ import annotations

import argparse
import json
import re
import signal
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from perception.remote_voice import (
    MAX_WAV_BYTES,
    constant_time_token_match,
    play_wav_with_pipewire,
    read_private_token,
)


OUTPUT_VALUES = {"usb", "hdmi"}
SINK_LINE = re.compile(r"^\s*[│ ]*[* ]*([0-9]+)\.\s+(.+?)\s+\[vol:")


def _read_json(body: bytes) -> dict[str, Any]:
    value = json.loads(body.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("request must be a JSON object")
    return value


class ProjectionState:
    def __init__(self, *, token_file: Path, settings_file: Path) -> None:
        self.token_file = token_file.expanduser()
        self.settings_file = settings_file.expanduser()
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.settings_file.exists():
            self._write_settings("usb")
        self._lock = threading.RLock()

    def authorized(self, header: str | None) -> bool:
        if not isinstance(header, str) or not header.startswith("Bearer "):
            return False
        try:
            expected = read_private_token(self.token_file)
        except (OSError, ValueError):
            return False
        return constant_time_token_match(header[7:], expected)

    def _write_settings(self, output: str) -> None:
        temporary = self.settings_file.with_suffix(".tmp")
        temporary.write_text(json.dumps({"audio_output": output}) + "\n", encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(self.settings_file)
        self.settings_file.chmod(0o600)

    def selected_output(self) -> str:
        try:
            value = json.loads(self.settings_file.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return "usb"
        output = value.get("audio_output") if isinstance(value, dict) else None
        return output if output in OUTPUT_VALUES else "usb"

    def camera_snapshot(self) -> bytes:
        """Capture one bounded JPEG from the projection webcam."""
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError("projection camera support is unavailable") from exc
        capture = cv2.VideoCapture("/dev/video0", cv2.CAP_V4L2)
        if not capture.isOpened():
            capture.release()
            raise RuntimeError("projection camera is unavailable or busy")
        try:
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            ok, frame = capture.read()
            if not ok or frame is None:
                raise RuntimeError("projection camera returned no frame")
            encoded, jpeg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
            if not encoded:
                raise RuntimeError("projection camera JPEG encoding failed")
            payload = jpeg.tobytes()
            if len(payload) > 2_000_000:
                raise RuntimeError("projection camera frame exceeds the bounded size")
            return payload
        finally:
            capture.release()

    def sinks(self) -> list[dict[str, str]]:
        result = subprocess.run(
            ["wpctl", "status"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        sinks: list[dict[str, str]] = []
        in_sinks = False
        for line in result.stdout.splitlines():
            if "├─ Sinks:" in line or "└─ Sinks:" in line:
                in_sinks = True
                continue
            if in_sinks and ("├─ " in line or "└─ " in line) and "Sinks:" not in line:
                break
            if not in_sinks:
                continue
            match = SINK_LINE.match(line)
            if match:
                sinks.append({"id": match.group(1), "name": match.group(2).strip()})
        return sinks

    def set_output(self, output: str) -> dict[str, Any]:
        if output not in OUTPUT_VALUES:
            raise ValueError("audio_output must be usb or hdmi")
        candidates = self.sinks()
        matching = [
            sink for sink in candidates
            if ("hdmi" in sink["name"].lower()) == (output == "hdmi")
        ]
        if not matching:
            raise RuntimeError(f"no {output} PipeWire sink is currently available")
        if len(matching) > 1:
            raise RuntimeError(f"multiple {output} PipeWire sinks are available")
        subprocess.run(["wpctl", "set-default", matching[0]["id"]], check=True, timeout=5)
        with self._lock:
            self._write_settings(output)
        return {"audio_output": output, "sink": matching[0]}


class ProjectionHandler(BaseHTTPRequestHandler):
    server_version = "SENTRYProjectionIO/1"

    @property
    def state(self) -> ProjectionState:
        return self.server.state  # type: ignore[attr-defined]

    def _send(self, status: int, payload: object) -> None:
        data = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_bytes(self, status: int, content_type: str, payload: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _authorized(self) -> bool:
        if self.state.authorized(self.headers.get("Authorization")):
            return True
        self._send(401, {"ok": False, "error": "authentication_required"})
        return False

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        if not self._authorized():
            return
        if self.path == "/health":
            self._send(200, {"ok": True, "service": "sentry-projection-io", "audio_output": self.state.selected_output()})
            return
        if self.path == "/v1/output":
            self._send(200, {"ok": True, "audio_output": self.state.selected_output(), "sinks": self.state.sinks()})
            return
        if self.path == "/v1/camera/snapshot":
            try:
                self._send_bytes(200, "image/jpeg", self.state.camera_snapshot())
            except (OSError, RuntimeError, ValueError) as exc:
                self._send(503, {"ok": False, "error": str(exc)})
            return
        if self.path != "/v1/microphone":
            self._send(404, {"ok": False, "error": "not_found"})
            return
        process = subprocess.Popen(
            ["pw-record", "--rate", "16000", "--channels", "1", "--format", "s16", "-"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            if process.stdout is None:
                raise RuntimeError("pw-record did not expose PCM output")
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("X-SENTRY-Sample-Rate", "16000")
            self.send_header("X-SENTRY-Channels", "1")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            while True:
                data = process.stdout.read(1024)
                if not data:
                    break
                self.wfile.write(data)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        if not self._authorized():
            return
        if self.path == "/v1/output":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 1024:
                    raise ValueError("invalid request size")
                payload = _read_json(self.rfile.read(length))
                result = self.state.set_output(str(payload.get("audio_output", "")))
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
                self._send(409, {"ok": False, "error": str(exc)})
                return
            self._send(200, {"ok": True, **result})
            return
        if self.path != "/v1/tts":
            self._send(404, {"ok": False, "error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_WAV_BYTES:
                raise ValueError("WAV payload is outside the bounded size")
            payload = self.rfile.read(length)
            if len(payload) != length:
                raise ValueError("incomplete WAV payload")
            play_wav_with_pipewire(payload)
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            self._send(422, {"ok": False, "error": str(exc)})
            return
        self._send(200, {"ok": True, "played": True})

    def log_message(self, _format: str, *_args: object) -> None:
        return


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=48221)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--settings-file", type=Path, default=Path("~/.config/sentry/projection.json"))
    args = parser.parse_args(argv)
    state = ProjectionState(token_file=args.token_file, settings_file=args.settings_file)
    server = ThreadingHTTPServer((args.host, args.port), ProjectionHandler)
    server.state = state  # type: ignore[attr-defined]
    stop_event = threading.Event()
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda *_: stop_event.set())
    while not stop_event.is_set():
        server.timeout = 1.0
        server.handle_request()
    server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
