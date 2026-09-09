"""Authenticated, bounded media transport for a SENTRY projection endpoint.

The projection host is an I/O surface only.  This module carries ephemeral
mono PCM from the projection microphone to the processing host and generated
WAV bytes in the other direction.  It intentionally contains no household,
model, database, or provider operations.
"""

from __future__ import annotations

import hmac
import io
import json
import shutil
import subprocess
import threading
import urllib.error
import urllib.request
import wave
from pathlib import Path
from typing import Iterator

import numpy as np


MAX_TOKEN_BYTES = 4096
MAX_WAV_BYTES = 16 * 1024 * 1024


def read_private_token(path: str | Path) -> str:
    """Read one mode-0600 token without ever printing it."""

    target = Path(path).expanduser()
    if target.is_symlink() or not target.is_file():
        raise ValueError("projection token file must be a regular file")
    mode = target.stat().st_mode & 0o777
    if mode != 0o600:
        raise ValueError("projection token file must be mode 0600")
    value = target.read_text(encoding="utf-8").strip()
    if not value or len(value.encode("utf-8")) > MAX_TOKEN_BYTES:
        raise ValueError("projection token is invalid")
    return value


def authorization_header(token: str) -> str:
    if not token or "\r" in token or "\n" in token:
        raise ValueError("projection token is invalid")
    return f"Bearer {token}"


class RemotePcmStream:
    """Stream fixed-size 16 kHz mono PCM chunks from the projection host."""

    def __init__(
        self,
        *,
        url: str,
        token_file: str | Path,
        sample_rate: int = 16_000,
        chunk_samples: int = 512,
        timeout_seconds: float = 10.0,
    ) -> None:
        if not url.startswith("http://"):
            raise ValueError("projection microphone URL must use HTTP on the private LAN")
        if sample_rate != 16_000 or chunk_samples <= 0:
            raise ValueError("projection microphone format is unsupported")
        self.url = url
        self.token_file = Path(token_file).expanduser()
        self.sample_rate = sample_rate
        self.chunk_samples = chunk_samples
        self.timeout_seconds = timeout_seconds

    def iter_chunks(self, stop_event: threading.Event) -> Iterator[np.ndarray]:
        token = read_private_token(self.token_file)
        request = urllib.request.Request(
            self.url,
            headers={
                "Authorization": authorization_header(token),
                "Accept": "application/octet-stream",
            },
            method="GET",
        )
        chunk_bytes = self.chunk_samples * 2
        pending = bytearray()
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            while not stop_event.is_set():
                data = response.read(chunk_bytes - len(pending))
                if not data:
                    if pending:
                        raise RuntimeError("projection microphone ended with an incomplete PCM chunk")
                    raise RuntimeError("projection microphone stream ended")
                pending.extend(data)
                if len(pending) < chunk_bytes:
                    continue
                yield np.frombuffer(bytes(pending), dtype=np.int16).astype(np.float32) / 32768.0
                pending.clear()


class RemoteWavPlayback:
    """Deliver one generated WAV to the projection host without disk storage."""

    def __init__(
        self,
        *,
        url: str,
        token_file: str | Path,
        timeout_seconds: float = 15.0,
    ) -> None:
        if not url.startswith("http://"):
            raise ValueError("projection playback URL must use HTTP on the private LAN")
        self.url = url
        self.token_file = Path(token_file).expanduser()
        self.timeout_seconds = timeout_seconds

    def send(self, wav_bytes: bytes) -> bool:
        return self.send_with_timing(wav_bytes)["delivered"]

    def send_with_timing(self, wav_bytes: bytes) -> dict[str, str | bool | None]:
        """Return the projection-owned playback-start timestamp when available."""
        if not isinstance(wav_bytes, bytes) or not 0 < len(wav_bytes) <= MAX_WAV_BYTES:
            return {"delivered": False, "tts_start_at": None, "timing_source": None}
        token = read_private_token(self.token_file)
        request = urllib.request.Request(
            self.url,
            data=wav_bytes,
            headers={
                "Authorization": authorization_header(token),
                "Content-Type": "audio/wav",
                "Content-Length": str(len(wav_bytes)),
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read(4097))
                start = payload.get("tts_start_at") if isinstance(payload, dict) else None
                valid_start = isinstance(start, str) and bool(start.strip())
                return {
                    "delivered": 200 <= response.status < 300 and payload.get("played") is True,
                    "tts_start_at": start if valid_start else None,
                    "timing_source": "PROJECTION_PLAYBACK_PROCESS" if valid_start else None,
                }
        except (
            OSError,
            ValueError,
            json.JSONDecodeError,
            urllib.error.HTTPError,
            urllib.error.URLError,
        ):
            return {"delivered": False, "tts_start_at": None, "timing_source": None}


def validate_wav_payload(wav_bytes: bytes) -> tuple[bytes, int, int]:
    """Validate and decode a bounded generated WAV before playback."""

    if not isinstance(wav_bytes, bytes) or not 0 < len(wav_bytes) <= MAX_WAV_BYTES:
        raise ValueError("WAV payload is outside the bounded size")
    with wave.open(io.BytesIO(wav_bytes)) as wav:
        if wav.getcomptype() != "NONE" or wav.getsampwidth() != 2:
            raise ValueError("projection audio must be uncompressed 16-bit PCM")
        sample_rate = wav.getframerate()
        channels = wav.getnchannels()
        frames = wav.getnframes()
        if not 8_000 <= sample_rate <= 48_000 or channels not in {1, 2}:
            raise ValueError("projection audio format is unsupported")
        if frames <= 0 or frames > sample_rate * 120:
            raise ValueError("projection audio duration is outside the bounded limit")
        return wav.readframes(frames), sample_rate, channels


def play_wav_with_pipewire(wav_bytes: bytes, *, player: str | None = None) -> None:
    """Play validated ephemeral audio through the projection host's default sink."""

    pcm, sample_rate, channels = validate_wav_payload(wav_bytes)
    executable = player or shutil.which("pw-play")
    if not executable:
        raise RuntimeError("pw-play was not found")
    subprocess.run(
        [
            executable,
            "--rate", str(sample_rate),
            "--channels", str(channels),
            "--format", "s16",
            "--media-role", "Communication",
            "-",
        ],
        input=pcm,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        timeout=125,
        check=True,
    )


def constant_time_token_match(presented: str, expected: str) -> bool:
    return hmac.compare_digest(presented.encode("utf-8"), expected.encode("utf-8"))
