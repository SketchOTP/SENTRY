"""Bounded local reactive voice loop for SENTRY.

Audio is captured from PipeWire into memory, transcribed locally with Whisper,
passed to the existing grounded M4 query function, and optionally delivered
through a local Kokoro runtime and PipeWire playback. No audio is written to
disk and this module never calls Codex/Luna directly.
"""

from __future__ import annotations

import base64
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

import numpy as np

from .speech_activity import SpeechActivityGate


class AudioRecorder(Protocol):
    def record(self, duration_seconds: float) -> np.ndarray: ...


class Transcriber(Protocol):
    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str: ...


class Speaker(Protocol):
    def speak(self, text: str) -> bool: ...


class PipeWireRecorder:
    """Capture mono 16-bit PCM from the default PipeWire source in memory."""

    def __init__(
        self,
        *,
        executable: str | None = None,
        source: str | None = None,
        sample_rate: int = 16_000,
        channels: int = 1,
    ) -> None:
        self.executable = executable or shutil.which("pw-record")
        self.source = source
        self.sample_rate = sample_rate
        self.channels = channels
        if self.sample_rate <= 0 or self.channels <= 0:
            raise ValueError("audio sample rate and channels must be positive")

    @property
    def available(self) -> bool:
        return bool(self.executable)

    def record(self, duration_seconds: float) -> np.ndarray:
        if duration_seconds <= 0:
            raise ValueError("recording duration must be positive")
        if not self.executable:
            raise RuntimeError("pw-record was not found")
        command = [
            self.executable,
            "--rate",
            str(self.sample_rate),
            "--channels",
            str(self.channels),
            "--format",
            "s16",
        ]
        if self.source:
            command.extend(["--target", self.source])
        command.append("-")
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        stdout_chunks: list[bytes] = []
        stderr_chunks: list[bytes] = []
        stdout_thread = threading.Thread(
            target=_drain_pipe, args=(process.stdout, stdout_chunks), daemon=True
        )
        stderr_thread = threading.Thread(
            target=_drain_pipe, args=(process.stderr, stderr_chunks), daemon=True
        )
        stdout_thread.start()
        stderr_thread.start()
        try:
            deadline = time.monotonic() + duration_seconds
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                time.sleep(min(remaining, 0.05))
            _terminate_capture_process(process)
            process.wait(timeout=5)
        except BaseException:
            _terminate_capture_process(process)
            try:
                process.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                pass
            raise
        stdout_thread.join(timeout=5)
        stderr_thread.join(timeout=5)
        stdout = b"".join(stdout_chunks)
        stderr = b"".join(stderr_chunks)
        # pw-record exits with status 1 when intentionally stopped by SIGINT or
        # SIGTERM after producing a valid stdout stream.  A launch/read failure
        # still has no samples and is rejected below.
        if process.returncode not in (0, 1, -signal.SIGINT, -signal.SIGTERM):
            detail = " ".join(stderr.decode("utf-8", errors="replace").split())
            raise RuntimeError(f"pw-record failed with status {process.returncode}: {detail[-500:]}")
        if not stdout:
            raise RuntimeError("pw-record returned no audio samples")
        samples = np.frombuffer(stdout, dtype=np.int16).astype(np.float32) / 32768.0
        if self.channels > 1:
            samples = samples.reshape(-1, self.channels).mean(axis=1)
        return np.ascontiguousarray(samples)


def _drain_pipe(stream: Any, chunks: list[bytes]) -> None:
    if stream is None:
        return
    try:
        chunks.append(stream.read())
    except (OSError, ValueError):
        return


def _terminate_capture_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            process.kill()
        process.wait(timeout=2)


class WhisperTranscriber:
    """CPU-local OpenAI Whisper adapter with an in-memory audio boundary."""

    def __init__(
        self,
        *,
        model_name: str = "tiny.en",
        download_root: str | Path | None = None,
    ) -> None:
        try:
            import whisper
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError("openai-whisper is required for local STT") from exc
        cache_root = Path(download_root).expanduser() if download_root else Path.home() / ".cache" / "whisper"
        cache_root.mkdir(parents=True, exist_ok=True)
        self.model_name = model_name
        self.model = whisper.load_model(model_name, device="cpu", download_root=str(cache_root))

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        if sample_rate != 16_000:
            raise ValueError("WhisperTranscriber requires 16 kHz audio")
        if audio.size == 0:
            return ""
        result = self.model.transcribe(
            np.asarray(audio, dtype=np.float32),
            language="en",
            fp16=False,
            temperature=0,
            condition_on_previous_text=False,
            verbose=False,
        )
        return " ".join(str(result.get("text", "")).split())


class NullSpeaker:
    """Test/dry-run speaker that intentionally performs no delivery."""

    def speak(self, text: str) -> bool:
        return False


class LocalVoiceIndicator:
    """Show a temporary local Zenity window for operator speech timing."""

    def __init__(self, *, executable: str | None = None) -> None:
        self.executable = executable or shutil.which("zenity")
        self.process: subprocess.Popen[str] | None = None

    @property
    def available(self) -> bool:
        return bool(self.executable and (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")))

    def open(self) -> bool:
        if not self.available:
            return False
        try:
            self.process = subprocess.Popen(
                [
                    self.executable,
                    "--progress",
                    "--title=SENTRY Reactive Voice",
                    "--text=GET READY",
                    "--percentage=0",
                    "--no-cancel",
                    "--auto-close",
                    "--width=560",
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            return True
        except OSError:
            self.process = None
            return False

    def update(self, message: str, percentage: int | None = None) -> None:
        process = self.process
        if process is None or process.stdin is None or process.poll() is not None:
            return
        try:
            process.stdin.write(f"# {message}\n")
            if percentage is not None:
                process.stdin.write(f"{max(0, min(100, percentage))}\n")
            process.stdin.flush()
        except (BrokenPipeError, OSError, ValueError):
            self.close()

    def finish(self) -> None:
        process = self.process
        if process is None:
            return
        self.update("DONE", 100)
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.terminate()
        finally:
            self.process = None

    def close(self) -> None:
        process = self.process
        self.process = None
        if process is None:
            return
        try:
            process.terminate()
            process.wait(timeout=1)
        except (OSError, subprocess.TimeoutExpired):
            try:
                process.kill()
            except OSError:
                pass


class KokoroSpeaker:
    """Use an installed local Kokoro runtime and PipeWire playback in memory."""

    def __init__(
        self,
        *,
        python_executable: str | None = None,
        worker_script: str | Path | None = None,
        voice: str = "am_michael",
        speed: float = 0.9,
        player: str | None = None,
        timeout_seconds: int = 300,
        speech_activity: SpeechActivityGate | None = None,
    ) -> None:
        self.python_executable = python_executable or _discover_kokoro_python()
        self.worker_script = Path(worker_script) if worker_script else Path(__file__).resolve().parents[1] / "tools" / "sentry_kokoro_worker.py"
        self.voice = voice
        self.speed = min(1.3, max(0.75, float(speed)))
        self.player = player or shutil.which("pw-play")
        self.timeout_seconds = timeout_seconds
        self.speech_activity = speech_activity or SpeechActivityGate()
        self._lock = threading.RLock()
        self._process: subprocess.Popen[bytes] | None = None

    @property
    def available(self) -> bool:
        return bool(self.player and self.python_executable and Path(self.worker_script).is_file())

    @property
    def is_speaking(self) -> bool:
        with self._lock:
            return self._process is not None and self._process.poll() is None

    def speak(self, text: str) -> bool:
        if not self.available or not isinstance(text, str) or not text.strip():
            return False
        try:
            with self.speech_activity.acquire() as acquired:
                if not acquired:
                    return False
                synth = subprocess.run(
                    [self.python_executable, str(self.worker_script)],
                    input=(json.dumps({"text": text, "voice": self.voice, "speed": self.speed}) + "\n").encode("utf-8"),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=self.timeout_seconds,
                    check=False,
                )
                if synth.returncode != 0:
                    return False
                response = json.loads(synth.stdout.decode("utf-8"))
                audio = base64.b64decode(response["audioBase64"], validate=True)
                if not audio:
                    return False
                pcm, sample_rate, channels = _decode_wav(audio)
                process = subprocess.Popen(
                    [
                        self.player,
                        "--rate",
                        str(sample_rate),
                        "--channels",
                        str(channels),
                        "--format",
                        "s16",
                        "--media-role",
                        "Communication",
                        "-",
                    ],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                )
                with self._lock:
                    self._process = process
                process.communicate(pcm, timeout=self.timeout_seconds)
                with self._lock:
                    if self._process is process:
                        self._process = None
                return process.returncode == 0
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired):
            self.cancel()
            return False

    def cancel(self) -> bool:
        with self._lock:
            process = self._process
        if process is None or process.poll() is not None:
            return False
        try:
            process.terminate()
            process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            try:
                process.kill()
            except OSError:
                return False
        finally:
            with self._lock:
                if self._process is process:
                    self._process = None
        return True


def _decode_wav(audio: bytes) -> tuple[bytes, int, int]:
    """Extract PCM and its format so PipeWire stdin cannot guess incorrectly."""
    with wave.open(io.BytesIO(audio), "rb") as wav:
        if wav.getcomptype() != "NONE" or wav.getsampwidth() != 2:
            raise ValueError("Kokoro output must be uncompressed 16-bit PCM WAV")
        return wav.readframes(wav.getnframes()), wav.getframerate(), wav.getnchannels()


def _discover_kokoro_python() -> str | None:
    """Find an existing local Python environment that provides Kokoro."""
    candidates: list[Path] = []
    configured = os.environ.get("SENTRY_KOKORO_PYTHON")
    if configured:
        candidates.append(Path(configured).expanduser())
    candidates.append(Path(sys.executable))
    for root in (Path.home() / ".venvs", Path.home() / "Projects"):
        if root.is_dir():
            candidates.extend(root.glob("*/bin/python"))
            candidates.extend(root.glob("*/.venv/bin/python"))
            candidates.extend(root.glob("*/*/.venv/bin/python"))
    seen: set[str] = set()
    for candidate in candidates:
        path = str(candidate)
        if path in seen or not candidate.is_file():
            continue
        seen.add(path)
        try:
            probe = subprocess.run(
                [path, "-c", "import kokoro, soundfile"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if probe.returncode == 0:
            return path
    return None


@dataclass(frozen=True)
class ReactiveVoiceConfig:
    base_url: str = "http://127.0.0.1:48174"
    room_id: str = "office"
    effort: str = "low"
    timeout_seconds: int = 120
    sample_rate: int = 16_000
    recording_seconds: float = 5.0


@dataclass(frozen=True)
class ReactiveVoiceResult:
    request_id: str
    status: str
    transcript: str | None
    answer: str | None
    grounding: str | None
    luna_invocations: int
    delivery: str
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "status": self.status,
            "transcript": self.transcript,
            "answer": self.answer,
            "grounding": self.grounding,
            "luna_invocations": self.luna_invocations,
            "delivery": self.delivery,
            "error": self.error,
        }


class ReactiveVoiceLoop:
    """Run one explicit request through local STT, M4 grounding, and speech."""

    def __init__(
        self,
        config: ReactiveVoiceConfig | None = None,
        *,
        recorder: AudioRecorder,
        transcriber: Transcriber,
        speaker: Speaker,
        ask_fn: Callable[..., dict[str, Any]],
    ) -> None:
        self.config = config or ReactiveVoiceConfig()
        self.recorder = recorder
        self.transcriber = transcriber
        self.speaker = speaker
        self.ask_fn = ask_fn
        # RAM-only conversation identity lets repeated explicit requests from
        # this loop resolve bounded follow-ups without creating durable memory.
        self.conversation_id = f"reactive-{uuid.uuid4()}"

    def run_once(self) -> ReactiveVoiceResult:
        request_id = str(uuid.uuid4())
        try:
            audio = self.recorder.record(self.config.recording_seconds)
            transcript = self.transcriber.transcribe(audio, self.config.sample_rate)
        except Exception as exc:  # noqa: BLE001 - voice failures are explicit
            return ReactiveVoiceResult(request_id, "failed", None, None, None, 0, "not_attempted", str(exc))
        if not transcript:
            return ReactiveVoiceResult(request_id, "no_speech", "", None, None, 0, "not_attempted")

        try:
            response = self.ask_fn(
                transcript,
                base_url=self.config.base_url,
                room_id=self.config.room_id,
                effort=self.config.effort,
                timeout_seconds=self.config.timeout_seconds,
                conversation_id=self.conversation_id,
            )
        except Exception as exc:  # noqa: BLE001 - preserve explicit bridge failure
            return ReactiveVoiceResult(request_id, "failed", transcript, None, None, 0, "not_attempted", str(exc))

        answer = response.get("answer") if isinstance(response, dict) else None
        grounding = response.get("grounding") if isinstance(response, dict) else None
        luna_invocations = int(response.get("luna_invocations", 0)) if isinstance(response, dict) else 0
        if not isinstance(answer, str) or not answer.strip():
            return ReactiveVoiceResult(request_id, "failed", transcript, None, grounding, luna_invocations, "not_attempted", "M4 returned no answer")
        delivered = bool(self.speaker.speak(answer))
        return ReactiveVoiceResult(
            request_id,
            "answered",
            transcript,
            answer,
            grounding,
            luna_invocations,
            "delivered" if delivered else "failed",
            None if delivered else "local speech delivery failed",
        )
