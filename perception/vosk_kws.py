"""Local Vosk restricted-vocabulary wake detection for the resident listener.

The adapter consumes only incremental in-memory PCM.  It decides whether the
single ``sentry`` token occurred and never transcribes or persists ambient
speech.  Whisper remains downstream command STT after this adapter wakes.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Callable

import numpy as np

SAMPLE_RATE = 16_000


@dataclass(frozen=True)
class WakeDetection:
    """A local Vosk wake event plus bounded RAM-only PCM around it."""

    detected_sample: int
    score: float
    queued_before: np.ndarray
    queued_after_token: np.ndarray | None = None
    token_start_seconds: float | None = None
    token_end_seconds: float | None = None


class VoskKwsEvaluator:
    """Recognize exactly one wake token with a non-forcing Vosk grammar."""

    def __init__(
        self,
        model_path: Path,
        *,
        detect_partial: bool = True,
        queue_seconds: float = 3.0,
        debounce_seconds: float = 3.0,
        model_factory: Callable[[str], Any] | None = None,
        recognizer_factory: Callable[..., Any] | None = None,
    ) -> None:
        if queue_seconds <= 0 or debounce_seconds < 0:
            raise ValueError("queue/debounce durations are invalid")
        self.model_path = model_path.expanduser().resolve()
        if not self.model_path.is_dir():
            raise RuntimeError(f"Vosk model is unavailable: {self.model_path}")
        if model_factory is None or recognizer_factory is None:
            try:
                import vosk
            except ImportError as exc:  # pragma: no cover - evaluator environment only
                raise RuntimeError("Vosk runtime is unavailable") from exc
            vosk.SetLogLevel(-1)
            model_factory = vosk.Model
            recognizer_factory = vosk.KaldiRecognizer
        grammar = json.dumps(["sentry", "[unk]"])
        self._model = model_factory(str(self.model_path))
        self._recognizer = recognizer_factory(self._model, SAMPLE_RATE, grammar)
        set_words = getattr(self._recognizer, "SetWords", None)
        if callable(set_words):
            set_words(True)
        self.detect_partial = bool(detect_partial)
        self._queue = deque(maxlen=int(queue_seconds * SAMPLE_RATE))
        self._sample_count = 0
        self._recognizer_start_sample = 0
        self._last_detection_sample: int | None = None
        self._debounce_samples = int(debounce_seconds * SAMPLE_RATE)
        self.last_result_class = "none"

    @staticmethod
    def _word_timing(payload: dict[str, Any]) -> tuple[float | None, float | None]:
        words = payload.get("result")
        if not isinstance(words, list):
            return None, None
        for word in words:
            if isinstance(word, dict) and str(word.get("word", "")).casefold() == "sentry":
                start = word.get("start")
                end = word.get("end")
                return (float(start) if isinstance(start, (int, float)) else None, float(end) if isinstance(end, (int, float)) else None)
        return None, None

    def feed(self, pcm: np.ndarray) -> list[WakeDetection]:
        """Process incremental PCM; only an exact one-token wake can fire."""
        values = np.asarray(pcm)
        if values.dtype != np.int16 or values.ndim != 1:
            raise ValueError("Vosk evaluator requires mono signed 16-bit PCM")
        if not values.size:
            return []
        contiguous = np.ascontiguousarray(values)
        self._queue.extend(contiguous.tolist())
        self._sample_count += contiguous.size
        final_available = bool(self._recognizer.AcceptWaveform(contiguous.tobytes()))
        payload = self._recognizer.Result() if final_available else self._recognizer.PartialResult()
        try:
            decoded_payload = json.loads(payload)
            if not isinstance(decoded_payload, dict):
                raise TypeError("Vosk payload is not an object")
            decoded = str(decoded_payload.get("text" if final_available else "partial", "")).casefold().strip()
        except (TypeError, json.JSONDecodeError):
            self.last_result_class = "malformed"
            return []
        if not self.detect_partial and not final_available:
            self.last_result_class = "partial"
            return []
        is_debounced = (
            self._last_detection_sample is not None
            and self._sample_count - self._last_detection_sample < self._debounce_samples
        )
        if decoded != "sentry":
            self.last_result_class = "nonwake" if decoded else "empty"
            return []
        if is_debounced:
            self.last_result_class = "debounced"
            return []
        self.last_result_class = "wake"
        self._last_detection_sample = self._sample_count
        token_start, token_end = self._word_timing(decoded_payload) if final_available else (None, None)
        queued = np.asarray(self._queue, dtype=np.int16)
        queued_after_token: np.ndarray | None = None
        if token_end is not None:
            token_end_sample = self._recognizer_start_sample + int(token_end * SAMPLE_RATE)
            tail_samples = max(0, self._sample_count - token_end_sample)
            queued_after_token = queued[-min(queued.size, tail_samples):].copy() if tail_samples else np.zeros(0, dtype=np.int16)
        return [
            WakeDetection(
                detected_sample=self._sample_count,
                score=1.0,
                queued_before=queued,
                queued_after_token=queued_after_token,
                token_start_seconds=token_start,
                token_end_seconds=token_end,
            )
        ]

    def reset(self) -> None:
        """Forget decoder context after a wake, timeout, or speech period."""
        reset = getattr(self._recognizer, "Reset", None)
        if callable(reset):
            reset()
        self._recognizer_start_sample = self._sample_count
        self._last_detection_sample = None
        self.last_result_class = "reset"

    def close(self) -> None:
        """Release the isolated recognizer reference without writing audio."""
        self._recognizer = None
        self._model = None

    def __enter__(self) -> "VoskKwsEvaluator":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
