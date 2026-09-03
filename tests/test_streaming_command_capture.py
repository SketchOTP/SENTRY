"""Deterministic gates for the dual-Vosk long-command boundary."""

from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path

import numpy as np

from perception.always_on_voice import (
    AlwaysOnVoiceConfig,
    AlwaysOnVoiceLoop,
    VoiceDiagnostics,
    VoiceState,
)
from perception.vosk_kws import CommandStreamProgress


CHUNK_SAMPLES = 512
CHUNK_SECONDS = CHUNK_SAMPLES / 16_000


class Clock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value


class Vad:
    def __init__(self, values: list[float]) -> None:
        self.values = iter(values)

    def probability(self, _samples: np.ndarray) -> float:
        return next(self.values)

    def reset(self) -> None:
        return None


class Wake:
    last_result_class = "empty"

    def __init__(self, detection_index: int | None = 0) -> None:
        self.detection_index = detection_index
        self.calls = 0
        self.resets = 0

    def feed(self, _pcm: np.ndarray) -> list[object]:
        detected = self.calls == self.detection_index
        self.calls += 1
        self.last_result_class = "wake" if detected else "nonwake"
        return [object()] if detected else []

    def reset(self) -> None:
        self.resets += 1


class StreamingCommand:
    endpointer_mode = "test_host_boundary"
    last_result_class = "none"

    def __init__(self, *, progress_calls: set[int] | None = None, final_calls: set[int] | None = None) -> None:
        self.progress_calls = progress_calls or set()
        self.final_calls = final_calls or set()
        self.call_index = 0
        self.reset_count = 0
        self.current_audio: list[np.ndarray] = []
        self.completed_audio: list[np.ndarray] = []
        self.segment_count = 0

    def feed(self, pcm: np.ndarray) -> CommandStreamProgress:
        self.current_audio.append(np.asarray(pcm, dtype=np.int16).copy())
        progressed = self.call_index in self.progress_calls or self.call_index in self.final_calls
        finalized = self.call_index in self.final_calls
        if finalized:
            self.segment_count += 1
        self.call_index += 1
        self.last_result_class = "segment_final" if finalized else ("partial" if progressed else "partial_empty")
        return CommandStreamProgress(
            result_class=self.last_result_class,
            progressed=progressed,
            finalized_segment_count=self.segment_count,
            partial_word_count=(1 if progressed and not finalized else 0),
            observed_word_count=self.call_index if progressed else 0,
            processing_ms=0.25,
        )

    def reset(self) -> None:
        if self.current_audio:
            self.completed_audio.append(np.concatenate(self.current_audio))
        self.current_audio = []
        self.call_index = 0
        self.segment_count = 0
        self.reset_count += 1


class Transcriber:
    def __init__(self, text: str = "Sentry, move the controlled source to the controlled target") -> None:
        self.text = text
        self.calls = 0
        self.audio: list[np.ndarray] = []

    def transcribe(self, audio: np.ndarray, _sample_rate: int) -> str:
        self.calls += 1
        self.audio.append(np.asarray(audio, dtype=np.float32).copy())
        return self.text


class Speaker:
    def speak(self, _text: str) -> bool:
        return True


class Gate:
    def is_active(self) -> bool:
        return False


class StreamingCommandCaptureTests(unittest.TestCase):
    def _build(
        self,
        probabilities: list[float],
        *,
        detection_index: int | None = 0,
        progress_calls: set[int] | None = None,
        final_calls: set[int] | None = None,
        command_idle_ms: int = 5000,
        stability_ms: int = 400,
    ) -> tuple[AlwaysOnVoiceLoop, Clock, StreamingCommand, Transcriber, list[str]]:
        clock = Clock()
        command = StreamingCommand(progress_calls=progress_calls, final_calls=final_calls)
        transcriber = Transcriber()
        dispatched: list[str] = []

        def ask(text: str, **_kwargs: object) -> dict[str, object]:
            dispatched.append(text)
            return {"answer": "Controlled answer.", "luna_invocations": 0}

        loop = AlwaysOnVoiceLoop(
            AlwaysOnVoiceConfig(
                minimum_speech_ms=32,
                pre_speech_ms=64,
                end_silence_ms=1500,
                command_continuation_idle_ms=command_idle_ms,
                command_stability_recheck_ms=stability_ms,
                command_trailing_tail_ms=500,
                maximum_utterance_seconds=45,
            ),
            stream=None,
            vad=Vad(probabilities),
            wake_detector=Wake(detection_index),
            command_recognizer=command,
            transcriber=transcriber,
            speaker=Speaker(),
            ask_fn=ask,
            diagnostics=VoiceDiagnostics(Path(tempfile.mkdtemp()) / "voice.json"),
            speech_activity=Gate(),
            clock=clock,
        )
        loop._set_state(VoiceState.LISTENING)
        return loop, clock, command, transcriber, dispatched

    @staticmethod
    def _chunks(count: int) -> list[np.ndarray]:
        return [np.full(CHUNK_SAMPLES, (index % 100) / 1000.0, dtype=np.float32) for index in range(count)]

    @staticmethod
    def _advance(loop: AlwaysOnVoiceLoop, clock: Clock, chunks: list[np.ndarray]) -> None:
        for chunk in chunks:
            clock.value += CHUNK_SECONDS
            loop.process_chunk(chunk)

    def test_pauses_through_four_and_a_half_seconds_remain_one_command(self) -> None:
        for pause_seconds in (1.5, 2.5, 3.5, 4.5):
            with self.subTest(pause_seconds=pause_seconds):
                first = math.ceil(1.0 / CHUNK_SECONDS)
                pause = math.ceil(pause_seconds / CHUNK_SECONDS)
                resumed = math.ceil(1.0 / CHUNK_SECONDS)
                final_idle = math.ceil(5.5 / CHUNK_SECONDS)
                probabilities = [0.9] * first + [0.0] * pause + [0.9] * resumed + [0.0] * final_idle
                loop, clock, _, transcriber, dispatched = self._build(probabilities)
                chunks = self._chunks(len(probabilities))

                before_final = first + pause + resumed + math.floor(4.9 / CHUNK_SECONDS)
                self._advance(loop, clock, chunks[:before_final])
                self.assertEqual(transcriber.calls, 0)
                self.assertEqual(dispatched, [])
                self._advance(loop, clock, chunks[before_final:])

                self.assertEqual(transcriber.calls, 1)
                self.assertEqual(len(dispatched), 1)
                self.assertEqual(loop.diagnostics.payload["capture_gap_count"], 0)
                self.assertEqual(loop.diagnostics.payload["endpoint_reason"], "streaming_command_idle")

    def test_streaming_progress_extends_turn_when_silero_under_reports(self) -> None:
        speech = math.ceil(0.5 / CHUNK_SECONDS)
        silence = math.ceil(10.5 / CHUNK_SECONDS)
        probabilities = [0.9] * speech + [0.0] * silence
        progress_at = speech + math.ceil(4.0 / CHUNK_SECONDS)
        loop, clock, _, transcriber, dispatched = self._build(
            probabilities,
            progress_calls={progress_at},
        )
        chunks = self._chunks(len(probabilities))

        early_end = speech + math.floor(8.8 / CHUNK_SECONDS)
        self._advance(loop, clock, chunks[:early_end])
        self.assertEqual(transcriber.calls, 0)
        self._advance(loop, clock, chunks[early_end:])
        self.assertEqual(transcriber.calls, 1)
        self.assertEqual(len(dispatched), 1)

    def test_three_vosk_segment_finals_remain_one_command(self) -> None:
        speech = math.ceil(3.0 / CHUNK_SECONDS)
        final_idle = math.ceil(5.5 / CHUNK_SECONDS)
        probabilities = [0.9] * speech + [0.0] * final_idle
        loop, clock, _, transcriber, dispatched = self._build(
            probabilities,
            final_calls={10, 35, 70},
        )
        chunks = self._chunks(len(probabilities))
        self._advance(loop, clock, chunks[: speech + math.floor(4.9 / CHUNK_SECONDS)])
        self.assertEqual(transcriber.calls, 0)
        self._advance(loop, clock, chunks[speech + math.floor(4.9 / CHUNK_SECONDS) :])

        self.assertEqual(transcriber.calls, 1)
        self.assertEqual(len(dispatched), 1)
        self.assertEqual(loop.diagnostics.payload["command_stream_finalized_segment_count"], 3)

    def test_late_wake_backfill_has_no_duplicate_or_missing_samples(self) -> None:
        speech = math.ceil(4.0 / CHUNK_SECONDS)
        final_idle = math.ceil(5.5 / CHUNK_SECONDS)
        probabilities = [0.9] * speech + [0.0] * final_idle
        wake_index = math.ceil(3.0 / CHUNK_SECONDS)
        loop, clock, command, transcriber, dispatched = self._build(
            probabilities,
            detection_index=wake_index,
        )
        chunks = self._chunks(len(probabilities))
        self._advance(loop, clock, chunks)

        self.assertEqual(transcriber.calls, 1)
        self.assertEqual(len(dispatched), 1)
        self.assertTrue(command.completed_audio)
        source_samples = int(loop.diagnostics.payload["capture_source_end_sample"])
        expected_stream = AlwaysOnVoiceLoop._to_int16(np.concatenate(chunks)[:source_samples])
        np.testing.assert_array_equal(command.completed_audio[0], expected_stream)
        self.assertEqual(loop.diagnostics.payload["capture_gap_count"], 0)

    def test_nonwake_never_starts_streaming_command_session(self) -> None:
        probabilities = [0.9] * 32 + [0.0] * 48
        loop, clock, command, transcriber, dispatched = self._build(
            probabilities,
            detection_index=None,
        )
        self._advance(loop, clock, self._chunks(len(probabilities)))
        self.assertEqual(command.current_audio, [])
        self.assertEqual(command.completed_audio, [])
        self.assertEqual(transcriber.calls, 0)
        self.assertEqual(dispatched, [])


if __name__ == "__main__":
    unittest.main()
