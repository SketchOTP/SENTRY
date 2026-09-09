"""Authenticated status read endpoint for a remote SENTRY projection."""

from __future__ import annotations

import argparse
import json
import signal
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from perception.remote_voice import constant_time_token_match, read_private_token


STATUS_KEYS = {
    "state", "status", "reason", "updated_at", "sleep_enabled", "wake_enabled",
    "vad_healthy", "microphone_audio_level", "output_audio_level", "last_wake_at",
    "speaker_context_active", "speaker_context_state", "speaker_context_display_name",
    "speaker_context_preflight_active", "last_segment_outcome", "anima_event_status",
    "anima_event_gate",
    "active_instance_id", "voice_id", "speech_speed",
}


def bounded_status(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"state": "UNAVAILABLE", "reason": "Voice listener has not published status."}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {"state": "UNAVAILABLE", "reason": "Voice status is unavailable."}
    if not isinstance(value, dict):
        return {"state": "UNAVAILABLE", "reason": "Voice status is invalid."}
    result = {key: value[key] for key in STATUS_KEYS if key in value}
    return result if result else {"state": "UNAVAILABLE", "reason": "Voice status is empty."}


class StatusHandler(BaseHTTPRequestHandler):
    server_version = "SENTRYProjectionStatus/1"

    def _send(self, status: int, payload: object) -> None:
        data = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        state = self.server.state  # type: ignore[attr-defined]
        header = self.headers.get("Authorization", "")
        try:
            expected = read_private_token(state.token_file)
        except (OSError, ValueError):
            expected = ""
        if not header.startswith("Bearer ") or not expected or not constant_time_token_match(header[7:], expected):
            self._send(401, {"ok": False, "error": "authentication_required"})
            return
        if self.path == "/health":
            self._send(200, {"ok": True, "service": "sentry-projection-status"})
        elif self.path == "/v1/status":
            self._send(200, bounded_status(state.status_path))
        else:
            self._send(404, {"ok": False, "error": "not_found"})

    def log_message(self, _format: str, *_args: object) -> None:
        return


class StatusState:
    def __init__(self, token_file: Path, status_path: Path) -> None:
        self.token_file = token_file.expanduser()
        self.status_path = status_path.expanduser()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=48220)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--status-path", type=Path, default=Path("/run/user/1000/sentry/voice.json"))
    args = parser.parse_args(argv)
    server = ThreadingHTTPServer((args.host, args.port), StatusHandler)
    server.state = StatusState(args.token_file, args.status_path)  # type: ignore[attr-defined]
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
