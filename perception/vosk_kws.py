"""Local Vosk restricted-vocabulary wake detection for the resident listener.

The adapter consumes only incremental in-memory PCM.  It decides whether the
single ``sentry`` token occurred and never transcribes or persists ambient
speech.  Whisper remains downstream command STT after this adapter wakes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import time
from typing import Any, Callable
import uuid

import numpy as np

SAMPLE_RATE = 16_000


class VoskRuntimeUnavailable(RuntimeError):
    """Raised when the required local Vosk runtime/model cannot initialize."""


class VoskSharedModel:
    """Load one local acoustic model for independent wake and command decoders."""

    def __init__(
        self,
        model_path: Path,
        *,
        model_factory: Callable[[str], Any] | None = None,
        recognizer_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.model_path = model_path.expanduser().resolve()
        if not self.model_path.is_dir():
            raise VoskRuntimeUnavailable(f"Vosk model is unavailable: {self.model_path}")
        if model_factory is None or recognizer_factory is None:
            try:
                import vosk
            except ImportError as exc:  # pragma: no cover - deployment dependent
                raise VoskRuntimeUnavailable("Vosk runtime is unavailable") from exc
            vosk.SetLogLevel(-1)
            model_factory = vosk.Model
            recognizer_factory = vosk.KaldiRecognizer
        try:
            self.model = model_factory(str(self.model_path))
        except Exception as exc:  # noqa: BLE001 - normalize deployment failures
            raise VoskRuntimeUnavailable(
                f"Vosk model initialization failed: {type(exc).__name__}"
            ) from exc
        self.recognizer_factory = recognizer_factory
        try:
            self.runtime_version = version("vosk")
        except PackageNotFoundError:  # pragma: no cover - injected test runtime
            self.runtime_version = "unknown"


@dataclass(frozen=True)
class CommandStreamProgress:
    """Content-free evidence from one full-vocabulary streaming decode step."""

    result_class: str
    progressed: bool
    finalized_segment_count: int
    partial_word_count: int
    observed_word_count: int
    processing_ms: float


class VoskStreamingCommandRecognizer:
    """Observe post-wake linguistic progress without authorizing command text."""

    def __init__(
        self,
        shared_model: VoskSharedModel,
        *,
        sample_rate: int = SAMPLE_RATE,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        if sample_rate != SAMPLE_RATE:
            raise ValueError("Vosk command recognition requires 16 kHz PCM")
        self.shared_model = shared_model
        self.sample_rate = int(sample_rate)
        self._clock = clock
        self._recognizer = self._new_recognizer()
        self._partial_text = ""
        self._finalized_segments: list[str] = []
        self._observed_word_count = 0
        self.last_result_class = "none"
        # Vosk 0.3.45's Python binding does not expose endpointer-mode controls.
        # Host-side continuation idle is therefore the command boundary.
        self.endpointer_mode = "binding_default_host_boundary"

    def _new_recognizer(self) -> Any:
        try:
            recognizer = self.shared_model.recognizer_factory(
                self.shared_model.model, self.sample_rate
            )
            set_words = getattr(recognizer, "SetWords", None)
            if callable(set_words):
                set_words(True)
            set_partial_words = getattr(recognizer, "SetPartialWords", None)
            if callable(set_partial_words):
                set_partial_words(True)
            return recognizer
        except Exception as exc:  # noqa: BLE001
            raise VoskRuntimeUnavailable(
                f"Vosk command recognizer initialization failed: {type(exc).__name__}"
            ) from exc

    @staticmethod
    def _decode(payload: str, key: str) -> tuple[str, int]:
        try:
            value = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise VoskRuntimeUnavailable("Vosk command result was malformed") from exc
        if not isinstance(value, dict):
            raise VoskRuntimeUnavailable("Vosk command result was not an object")
        text = " ".join(str(value.get(key, "")).casefold().split())
        words_key = "result" if key == "text" else "partial_result"
        words = value.get(words_key)
        word_count = len(words) if isinstance(words, list) else len(text.split())
        return text, word_count

    def feed(self, pcm: np.ndarray) -> CommandStreamProgress:
        """Consume one chronological PCM increment and report metadata only."""
        values = np.asarray(pcm)
        if values.dtype != np.int16 or values.ndim != 1:
            raise ValueError("Vosk command recognizer requires mono signed 16-bit PCM")
        if not values.size:
            return CommandStreamProgress(
                result_class="empty",
                progressed=False,
                finalized_segment_count=len(self._finalized_segments),
                partial_word_count=len(self._partial_text.split()),
                observed_word_count=self._observed_word_count,
                processing_ms=0.0,
            )
        started = self._clock()
        try:
            finalized = bool(
                self._recognizer.AcceptWaveform(np.ascontiguousarray(values).tobytes())
            )
            raw = self._recognizer.Result() if finalized else self._recognizer.PartialResult()
            text, word_count = self._decode(raw, "text" if finalized else "partial")
        except VoskRuntimeUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 - active command must fail closed
            raise VoskRuntimeUnavailable(
                f"Vosk command recognition failed: {type(exc).__name__}"
            ) from exc

        progressed = False
        if finalized:
            if text:
                self._finalized_segments.append(text)
                self._observed_word_count += max(1, word_count)
                progressed = True
            self._partial_text = ""
            result_class = "segment_final" if text else "segment_empty"
        else:
            progressed = bool(text and text != self._partial_text)
            self._partial_text = text
            self._observed_word_count = max(
                self._observed_word_count,
                sum(len(item.split()) for item in self._finalized_segments) + word_count,
            )
            result_class = "partial" if text else "partial_empty"
        self.last_result_class = result_class
        return CommandStreamProgress(
            result_class=result_class,
            progressed=progressed,
            finalized_segment_count=len(self._finalized_segments),
            partial_word_count=(0 if finalized else word_count),
            observed_word_count=self._observed_word_count,
            processing_ms=(self._clock() - started) * 1000.0,
        )

    def reset(self) -> None:
        """Clear all ephemeral transcript context for the next command session."""
        reset = getattr(self._recognizer, "Reset", None)
        if callable(reset):
            reset()
        else:  # pragma: no cover - current Vosk binding exposes Reset
            self._recognizer = self._new_recognizer()
        self._partial_text = ""
        self._finalized_segments.clear()
        self._observed_word_count = 0
        self.last_result_class = "reset"

    def close(self) -> None:
        self._recognizer = None
        self._partial_text = ""
        self._finalized_segments.clear()


@dataclass(frozen=True)
class WakeDetection:
    """A metadata-only local Vosk event mapped onto the shared PCM stream."""

    detected_sample: int
    detected_at_monotonic: float
    score: float
    wake_event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    wake_token: str = "sentry"
    detection_source: str = "partial"
    samples_after_token: int | None = None
    token_end_sample: int | None = None
    token_start_seconds: float | None = None
    token_end_seconds: float | None = None


class VoskKwsEvaluator:
    """Recognize exactly one wake token with a non-forcing Vosk grammar."""

    def __init__(
        self,
        model_path: Path,
        *,
        detect_partial: bool = True,
        partial_confirmation_frames: int = 1,
        debounce_seconds: float = 3.0,
        model_factory: Callable[[str], Any] | None = None,
        recognizer_factory: Callable[..., Any] | None = None,
        shared_model: VoskSharedModel | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if debounce_seconds < 0 or partial_confirmation_frames <= 0:
            raise ValueError("debounce/confirmation values are invalid")
        self.model_path = model_path.expanduser().resolve()
        if not self.model_path.is_dir():
            raise RuntimeError(f"Vosk model is unavailable: {self.model_path}")
        if shared_model is not None:
            self._model = shared_model.model
            recognizer_factory = shared_model.recognizer_factory
            self._owns_model = False
        elif model_factory is None or recognizer_factory is None:
            try:
                import vosk
            except ImportError as exc:  # pragma: no cover - evaluator environment only
                raise RuntimeError("Vosk runtime is unavailable") from exc
            vosk.SetLogLevel(-1)
            model_factory = vosk.Model
            recognizer_factory = vosk.KaldiRecognizer
            self._model = model_factory(str(self.model_path))
            self._owns_model = True
        else:
            self._model = model_factory(str(self.model_path))
            self._owns_model = True
        grammar = json.dumps(["sentry", "[unk]"])
        self._recognizer = recognizer_factory(self._model, SAMPLE_RATE, grammar)
        set_words = getattr(self._recognizer, "SetWords", None)
        if callable(set_words):
            set_words(True)
        self.detect_partial = bool(detect_partial)
        self._clock = clock
        self._partial_confirmation_frames = int(partial_confirmation_frames)
        self._partial_wake_hits = 0
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
        if not final_available and decoded == "sentry":
            self._partial_wake_hits += 1
            if self._partial_wake_hits < self._partial_confirmation_frames:
                self.last_result_class = "partial_candidate"
                return []
        else:
            self._partial_wake_hits = 0
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
        self._partial_wake_hits = 0
        self._last_detection_sample = self._sample_count
        token_start, token_end = self._word_timing(decoded_payload) if final_available else (None, None)
        samples_after_token: int | None = None
        token_end_sample: int | None = None
        if token_end is not None:
            token_end_sample = self._recognizer_start_sample + int(token_end * SAMPLE_RATE)
            samples_after_token = max(0, self._sample_count - token_end_sample)
        return [
            WakeDetection(
                wake_event_id=str(uuid.uuid4()),
                wake_token="sentry",
                detection_source="final" if final_available else "partial",
                detected_sample=self._sample_count,
                detected_at_monotonic=self._clock(),
                score=1.0,
                samples_after_token=samples_after_token,
                token_end_sample=token_end_sample,
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
        self._partial_wake_hits = 0
        self.last_result_class = "reset"

    def close(self) -> None:
        """Release the isolated recognizer reference without writing audio."""
        self._recognizer = None
        if self._owns_model:
            self._model = None

    def __enter__(self) -> "VoskKwsEvaluator":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
