"""Deterministic sample-continuity tests for resident voice PCM ownership."""

from __future__ import annotations

import unittest

import numpy as np

from perception.audio_timeline import (
    ActiveUtteranceCapture,
    AudioChunk,
    AudioTimelineError,
    AudioTimelineGap,
    PcmTimeline,
)


def _pcm(start: int, size: int = 8) -> np.ndarray:
    return np.arange(start, start + size, dtype=np.float32)


class AudioTimelineTests(unittest.TestCase):
    def test_publish_assigns_monotonic_sequence_and_sample_offsets(self) -> None:
        timeline = PcmTimeline(capacity_samples=64)
        first = timeline.publish(_pcm(0), monotonic_timestamp=1.0, vad_probability=0.1)
        second = timeline.publish(_pcm(8), monotonic_timestamp=2.0, vad_probability=0.9)

        self.assertEqual((first.sequence_number, first.start_sample, first.end_sample), (0, 0, 8))
        self.assertEqual((second.sequence_number, second.start_sample, second.end_sample), (1, 8, 16))
        self.assertEqual(timeline.stream_sequence, 2)
        self.assertEqual(timeline.stream_end_sample, 16)
        self.assertFalse(first.pcm.flags.writeable)

    def test_duplicate_or_missing_coordinates_fail_closed(self) -> None:
        timeline = PcmTimeline(capacity_samples=64)
        timeline.publish(_pcm(0), monotonic_timestamp=1.0, vad_probability=0.1)
        with self.assertRaises(AudioTimelineGap):
            timeline.publish(
                _pcm(8),
                monotonic_timestamp=2.0,
                vad_probability=0.1,
                sequence_number=0,
                start_sample=8,
            )
        with self.assertRaises(AudioTimelineGap):
            timeline.publish(
                _pcm(16),
                monotonic_timestamp=3.0,
                vad_probability=0.1,
                sequence_number=2,
                start_sample=16,
            )

    def test_exact_range_read_is_sample_for_sample(self) -> None:
        timeline = PcmTimeline(capacity_samples=64)
        for index in range(4):
            timeline.publish(_pcm(index * 8), monotonic_timestamp=float(index), vad_probability=0.5)
        result = timeline.read_range(4, 28)
        np.testing.assert_array_equal(result, np.arange(4, 28, dtype=np.float32))
        self.assertFalse(result.flags.writeable)

    def test_active_capture_is_append_only_and_freezes_exact_sequence(self) -> None:
        timeline = PcmTimeline(capacity_samples=64)
        first = timeline.publish(_pcm(0), monotonic_timestamp=0.0, vad_probability=0.9)
        capture = ActiveUtteranceCapture.promote(
            timeline,
            capture_id="capture",
            wake_event_id="wake",
            capture_mode="wake_inline",
            capture_start_sample=0,
            capture_end_sample=first.end_sample,
            wake_detected_sample=first.end_sample,
            wake_token_end_sample=4,
            speech_epoch_start_sample=0,
            last_voice_sample=first.end_sample,
        )
        for index in range(1, 4):
            chunk = timeline.publish(
                _pcm(index * 8), monotonic_timestamp=float(index), vad_probability=0.9
            )
            capture.append(chunk, speaking=True)
        live_view = capture.view(last_samples=12)
        np.testing.assert_array_equal(live_view, np.arange(20, 32, dtype=np.float32))
        self.assertFalse(live_view.flags.writeable)
        frozen = capture.freeze("silence")

        np.testing.assert_array_equal(frozen.pcm, np.arange(32, dtype=np.float32))
        self.assertEqual(frozen.sample_count, 32)
        self.assertEqual(frozen.chunk_count, 4)
        self.assertEqual(frozen.gap_count, 0)
        self.assertFalse(frozen.pcm.flags.writeable)
        with self.assertRaises(AudioTimelineError):
            capture.freeze("duplicate")

    def test_gap_inside_active_capture_is_detected(self) -> None:
        timeline = PcmTimeline(capacity_samples=64)
        first = timeline.publish(_pcm(0), monotonic_timestamp=0.0, vad_probability=0.9)
        capture = ActiveUtteranceCapture.promote(
            timeline,
            capture_id="capture",
            wake_event_id="wake",
            capture_mode="wake_inline",
            capture_start_sample=0,
            capture_end_sample=first.end_sample,
            wake_detected_sample=first.end_sample,
            wake_token_end_sample=4,
            speech_epoch_start_sample=0,
            last_voice_sample=first.end_sample,
        )
        missing_middle = AudioChunk(
            sequence_number=2,
            start_sample=16,
            end_sample=24,
            monotonic_timestamp=2.0,
            pcm=_pcm(16),
            vad_probability=0.9,
        )
        with self.assertRaises(AudioTimelineGap):
            capture.append(missing_middle, speaking=True)
        self.assertEqual(capture.gap_count, 1)

    def test_ring_wrap_does_not_truncate_promoted_active_capture(self) -> None:
        timeline = PcmTimeline(capacity_samples=24)
        first = timeline.publish(_pcm(0), monotonic_timestamp=0.0, vad_probability=0.9)
        capture = ActiveUtteranceCapture.promote(
            timeline,
            capture_id="capture",
            wake_event_id="wake",
            capture_mode="wake_inline",
            capture_start_sample=0,
            capture_end_sample=first.end_sample,
            wake_detected_sample=first.end_sample,
            wake_token_end_sample=4,
            speech_epoch_start_sample=0,
            last_voice_sample=first.end_sample,
        )
        for index in range(1, 10):
            chunk = timeline.publish(
                _pcm(index * 8), monotonic_timestamp=float(index), vad_probability=0.9
            )
            capture.append(chunk, speaking=True)
        self.assertGreater(timeline.earliest_sample, capture.capture_start_sample)
        frozen = capture.freeze("silence")
        np.testing.assert_array_equal(frozen.pcm, np.arange(80, dtype=np.float32))

    def test_clearing_audio_preserves_stream_identity(self) -> None:
        timeline = PcmTimeline(capacity_samples=64)
        timeline.publish(_pcm(0), monotonic_timestamp=0.0, vad_probability=None)
        timeline.clear_audio()
        second = timeline.publish(_pcm(8), monotonic_timestamp=1.0, vad_probability=None)
        self.assertEqual((second.sequence_number, second.start_sample), (1, 8))
        self.assertEqual(timeline.earliest_sample, 8)

    def test_freeze_trims_only_requested_trailing_idle(self) -> None:
        timeline = PcmTimeline(capacity_samples=64)
        first = timeline.publish(_pcm(0), monotonic_timestamp=0.0, vad_probability=0.9)
        capture = ActiveUtteranceCapture.promote(
            timeline,
            capture_id="trim",
            wake_event_id="wake",
            capture_mode="wake_inline",
            capture_start_sample=0,
            capture_end_sample=first.end_sample,
            wake_detected_sample=first.end_sample,
            wake_token_end_sample=4,
            speech_epoch_start_sample=0,
            last_voice_sample=first.end_sample,
        )
        for index in range(1, 4):
            chunk = timeline.publish(
                _pcm(index * 8), monotonic_timestamp=float(index), vad_probability=0.0
            )
            capture.append(chunk, speaking=False)

        frozen = capture.freeze("streaming_command_idle", end_sample=16)
        np.testing.assert_array_equal(frozen.pcm, np.arange(16, dtype=np.float32))
        self.assertEqual(frozen.capture_end_sample, 16)
        self.assertEqual(frozen.source_end_sample, 32)
        self.assertEqual(frozen.trailing_samples_trimmed, 16)


if __name__ == "__main__":
    unittest.main()
