"""Bounded, sample-indexed, memory-only PCM ownership for resident voice."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque

import numpy as np


class AudioTimelineError(RuntimeError):
    """Base class for fail-closed audio chronology errors."""


class AudioTimelineGap(AudioTimelineError):
    """Raised when a chunk or requested range is not chronologically complete."""


@dataclass(frozen=True)
class AudioChunk:
    """One immutable PCM chunk with monotonic stream coordinates."""

    sequence_number: int
    start_sample: int
    end_sample: int
    monotonic_timestamp: float
    pcm: np.ndarray
    vad_probability: float | None = None

    def __post_init__(self) -> None:
        values = np.ascontiguousarray(self.pcm, dtype=np.float32).copy()
        if values.ndim != 1 or values.size <= 0:
            raise ValueError("audio chunks must contain one-dimensional PCM")
        if self.sequence_number < 0 or self.start_sample < 0:
            raise ValueError("audio chunk coordinates must be non-negative")
        if self.end_sample != self.start_sample + values.size:
            raise ValueError("audio chunk sample range does not match its PCM")
        values.setflags(write=False)
        object.__setattr__(self, "pcm", values)


class PcmTimeline:
    """One bounded chronology shared by wake, VAD, and active capture."""

    def __init__(self, *, capacity_samples: int) -> None:
        if capacity_samples <= 0:
            raise ValueError("timeline capacity must be positive")
        self.capacity_samples = int(capacity_samples)
        self._chunks: Deque[AudioChunk] = deque()
        self._next_sequence = 0
        self._stream_end_sample = 0

    @property
    def stream_sequence(self) -> int:
        return self._next_sequence

    @property
    def stream_end_sample(self) -> int:
        return self._stream_end_sample

    @property
    def earliest_sample(self) -> int:
        return self._chunks[0].start_sample if self._chunks else self._stream_end_sample

    @property
    def retained_samples(self) -> int:
        return self._stream_end_sample - self.earliest_sample

    def publish(
        self,
        pcm: np.ndarray,
        *,
        monotonic_timestamp: float,
        vad_probability: float | None,
        sequence_number: int | None = None,
        start_sample: int | None = None,
    ) -> AudioChunk:
        """Accept one chunk exactly once and assign/validate stream coordinates."""
        expected_sequence = self._next_sequence
        expected_start = self._stream_end_sample
        actual_sequence = expected_sequence if sequence_number is None else int(sequence_number)
        actual_start = expected_start if start_sample is None else int(start_sample)
        if actual_sequence != expected_sequence or actual_start != expected_start:
            raise AudioTimelineGap(
                "audio chronology discontinuity: "
                f"expected sequence/sample {expected_sequence}/{expected_start}, "
                f"received {actual_sequence}/{actual_start}"
            )
        values = np.asarray(pcm, dtype=np.float32)
        chunk = AudioChunk(
            sequence_number=actual_sequence,
            start_sample=actual_start,
            end_sample=actual_start + values.size,
            monotonic_timestamp=float(monotonic_timestamp),
            pcm=values,
            vad_probability=(None if vad_probability is None else float(vad_probability)),
        )
        self._chunks.append(chunk)
        self._next_sequence += 1
        self._stream_end_sample = chunk.end_sample
        retention_floor = max(0, self._stream_end_sample - self.capacity_samples)
        while self._chunks and self._chunks[0].end_sample <= retention_floor:
            self._chunks.popleft()
        return chunk

    def read_range(self, start_sample: int, end_sample: int) -> np.ndarray:
        """Return one immutable exact sample range or fail on missing chronology."""
        start = int(start_sample)
        end = int(end_sample)
        if start < 0 or end < start:
            raise ValueError("invalid audio sample range")
        if start < self.earliest_sample or end > self._stream_end_sample:
            raise AudioTimelineGap(
                f"audio range {start}:{end} is outside retained chronology "
                f"{self.earliest_sample}:{self._stream_end_sample}"
            )
        if start == end:
            empty = np.zeros(0, dtype=np.float32)
            empty.setflags(write=False)
            return empty
        pieces: list[np.ndarray] = []
        expected = start
        for chunk in self._chunks:
            if chunk.end_sample <= start:
                continue
            if chunk.start_sample >= end:
                break
            overlap_start = max(start, chunk.start_sample)
            overlap_end = min(end, chunk.end_sample)
            if overlap_start != expected:
                raise AudioTimelineGap(
                    f"audio gap before sample {overlap_start}; expected {expected}"
                )
            left = overlap_start - chunk.start_sample
            right = overlap_end - chunk.start_sample
            pieces.append(chunk.pcm[left:right])
            expected = overlap_end
        if expected != end:
            raise AudioTimelineGap(f"audio range ended at {expected}; expected {end}")
        result = np.ascontiguousarray(np.concatenate(pieces), dtype=np.float32)
        result.setflags(write=False)
        return result

    def chunk_count_for_range(self, start_sample: int, end_sample: int) -> int:
        return sum(
            1
            for chunk in self._chunks
            if chunk.end_sample > start_sample and chunk.start_sample < end_sample
        )

    def clear_audio(self) -> None:
        """Release retained PCM while preserving monotonic stream coordinates."""
        self._chunks.clear()


@dataclass(frozen=True)
class FrozenUtterance:
    """One immutable, continuity-verified PCM result for STT."""

    capture_id: str
    wake_event_id: str | None
    capture_mode: str
    capture_start_sample: int
    wake_detected_sample: int | None
    wake_token_end_sample: int | None
    capture_end_sample: int
    source_end_sample: int
    speech_epoch_start_sample: int | None
    last_voice_sample: int | None
    command_speech_seen: bool
    chunk_count: int
    sample_count: int
    trailing_samples_trimmed: int
    gap_count: int
    endpoint_reason: str
    pcm: np.ndarray

    def view(self, start_sample: int, end_sample: int | None = None) -> np.ndarray:
        end = self.capture_end_sample if end_sample is None else int(end_sample)
        start = max(self.capture_start_sample, int(start_sample))
        if end < start or end > self.capture_end_sample:
            raise ValueError("invalid frozen utterance view")
        left = start - self.capture_start_sample
        right = end - self.capture_start_sample
        result = np.ascontiguousarray(self.pcm[left:right], dtype=np.float32)
        result.setflags(write=False)
        return result


class ActiveUtteranceCapture:
    """Append-only command capture promoted from one shared PCM timeline."""

    def __init__(
        self,
        *,
        capture_id: str,
        wake_event_id: str | None,
        capture_mode: str,
        capture_start_sample: int,
        wake_detected_sample: int | None,
        wake_token_end_sample: int | None,
        speech_epoch_start_sample: int | None,
        last_voice_sample: int | None,
        initial_pcm: np.ndarray,
        initial_end_sample: int,
        initial_chunk_count: int,
        command_speech_seen: bool = False,
    ) -> None:
        initial = np.ascontiguousarray(initial_pcm, dtype=np.float32).copy()
        if initial_end_sample != capture_start_sample + initial.size:
            raise AudioTimelineGap("promoted capture range does not match initial PCM")
        self.capture_id = capture_id
        self.wake_event_id = wake_event_id
        self.capture_mode = capture_mode
        self.capture_start_sample = int(capture_start_sample)
        self.wake_detected_sample = wake_detected_sample
        self.wake_token_end_sample = wake_token_end_sample
        self.current_end_sample = int(initial_end_sample)
        self.speech_epoch_start_sample = speech_epoch_start_sample
        self.last_voice_sample = last_voice_sample
        self.command_speech_seen = bool(command_speech_seen)
        self.chunk_count = int(initial_chunk_count)
        self.sample_count = int(initial.size)
        self.gap_count = 0
        self.endpoint_reason: str | None = None
        self._pieces: list[np.ndarray] = [initial] if initial.size else []
        self._frozen = False

    @classmethod
    def promote(
        cls,
        timeline: PcmTimeline,
        *,
        capture_id: str,
        wake_event_id: str | None,
        capture_mode: str,
        capture_start_sample: int,
        capture_end_sample: int,
        wake_detected_sample: int | None,
        wake_token_end_sample: int | None,
        speech_epoch_start_sample: int | None,
        last_voice_sample: int | None,
        command_speech_seen: bool = False,
    ) -> "ActiveUtteranceCapture":
        return cls(
            capture_id=capture_id,
            wake_event_id=wake_event_id,
            capture_mode=capture_mode,
            capture_start_sample=capture_start_sample,
            wake_detected_sample=wake_detected_sample,
            wake_token_end_sample=wake_token_end_sample,
            speech_epoch_start_sample=speech_epoch_start_sample,
            last_voice_sample=last_voice_sample,
            initial_pcm=timeline.read_range(capture_start_sample, capture_end_sample),
            initial_end_sample=capture_end_sample,
            initial_chunk_count=timeline.chunk_count_for_range(capture_start_sample, capture_end_sample),
            command_speech_seen=command_speech_seen,
        )

    def append(self, chunk: AudioChunk, *, speaking: bool) -> None:
        if self._frozen:
            raise AudioTimelineError("cannot append to a frozen utterance")
        if chunk.start_sample != self.current_end_sample:
            self.gap_count += 1
            raise AudioTimelineGap(
                f"active capture expected sample {self.current_end_sample}, "
                f"received {chunk.start_sample}"
            )
        self._pieces.append(chunk.pcm)
        self.current_end_sample = chunk.end_sample
        self.chunk_count += 1
        self.sample_count += chunk.pcm.size
        if speaking:
            self.last_voice_sample = chunk.end_sample
            if self.wake_detected_sample is None or chunk.end_sample > self.wake_detected_sample:
                self.command_speech_seen = True

    def view(self, *, last_samples: int | None = None) -> np.ndarray:
        """Return an immutable copy without freezing or changing capture ownership."""
        if self._frozen:
            raise AudioTimelineError("cannot view a frozen utterance")
        pcm = (
            np.ascontiguousarray(np.concatenate(self._pieces), dtype=np.float32)
            if self._pieces
            else np.zeros(0, dtype=np.float32)
        )
        expected = self.current_end_sample - self.capture_start_sample
        if pcm.size != expected:
            self.gap_count += 1
            raise AudioTimelineGap(
                f"active capture contains {pcm.size} samples; expected {expected}"
            )
        if last_samples is not None:
            if last_samples <= 0:
                raise ValueError("last_samples must be positive")
            pcm = pcm[-int(last_samples) :]
        result = np.ascontiguousarray(pcm, dtype=np.float32)
        result.setflags(write=False)
        return result

    def freeze(
        self,
        endpoint_reason: str,
        *,
        end_sample: int | None = None,
    ) -> FrozenUtterance:
        if self._frozen:
            raise AudioTimelineError("utterance was already frozen")
        self._frozen = True
        self.endpoint_reason = endpoint_reason
        pcm = (
            np.ascontiguousarray(np.concatenate(self._pieces), dtype=np.float32)
            if self._pieces
            else np.zeros(0, dtype=np.float32)
        )
        expected = self.current_end_sample - self.capture_start_sample
        if pcm.size != expected:
            self.gap_count += 1
            raise AudioTimelineGap(
                f"frozen capture contains {pcm.size} samples; expected {expected}"
            )
        frozen_end = self.current_end_sample if end_sample is None else int(end_sample)
        if frozen_end < self.capture_start_sample or frozen_end > self.current_end_sample:
            raise ValueError("frozen utterance end is outside the active capture")
        frozen_size = frozen_end - self.capture_start_sample
        trailing_samples_trimmed = pcm.size - frozen_size
        pcm = np.ascontiguousarray(pcm[:frozen_size], dtype=np.float32)
        pcm.setflags(write=False)
        return FrozenUtterance(
            capture_id=self.capture_id,
            wake_event_id=self.wake_event_id,
            capture_mode=self.capture_mode,
            capture_start_sample=self.capture_start_sample,
            wake_detected_sample=self.wake_detected_sample,
            wake_token_end_sample=self.wake_token_end_sample,
            capture_end_sample=frozen_end,
            source_end_sample=self.current_end_sample,
            speech_epoch_start_sample=self.speech_epoch_start_sample,
            last_voice_sample=self.last_voice_sample,
            command_speech_seen=self.command_speech_seen,
            chunk_count=self.chunk_count,
            sample_count=pcm.size,
            trailing_samples_trimmed=trailing_samples_trimmed,
            gap_count=self.gap_count,
            endpoint_reason=endpoint_reason,
            pcm=pcm,
        )
