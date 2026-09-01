"""Small cross-process speech-activity coordination for local SENTRY audio.

The lock is held only while SENTRY is synthesizing or playing speech.  It is
not an event bus and carries no utterance, transcript, or audio content.
"""

from __future__ import annotations

import fcntl
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def _runtime_path() -> Path:
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime:
        return Path(runtime) / "sentry" / "speech.lock"
    return Path("/run/user") / str(os.getuid()) / "sentry" / "speech.lock"


class SpeechActivityGate:
    """Advisory user-runtime lock shared by every SENTRY speech path."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else _runtime_path()

    def _open(self) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            self.path.parent.chmod(0o700)
        except OSError:
            pass
        return os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)

    def is_active(self) -> bool:
        """Return true when another SENTRY speech path currently holds the gate."""
        try:
            descriptor = self._open()
        except OSError:
            # A permission/runtime failure should make listeners conservative.
            return True
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            return False
        finally:
            os.close(descriptor)

    @contextmanager
    def acquire(self) -> Iterator[bool]:
        """Acquire exclusively without waiting; yield false when speech is busy."""
        try:
            descriptor = self._open()
        except OSError:
            yield False
            return
        locked = False
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
            except BlockingIOError:
                yield False
                return
            yield True
        finally:
            if locked:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                except OSError:
                    pass
            os.close(descriptor)
