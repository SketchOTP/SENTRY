import tempfile
import threading
import unittest
from pathlib import Path

import numpy as np

from perception.always_on_voice import AlwaysOnVoiceConfig, AlwaysOnVoiceLoop, VoiceDiagnostics, VoiceState


CHUNK = np.ones(512, dtype=np.float32)


class Clock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value


class Stream:
    def __init__(self, chunks, clock, step=0.032):
        self.chunks = chunks
        self.clock = clock
        self.step = step

    def iter_chunks(self, stop_event):
        for chunk in self.chunks:
            self.clock.value += self.step
            yield chunk


class Vad:
    def __init__(self, probabilities):
        self.probabilities = iter(probabilities)
        self.resets = 0

    def probability(self, samples):
        return next(self.probabilities)

    def reset(self):
        self.resets += 1


class WakeDetector:
    def __init__(self, detections=()):
        self.detections = iter(detections)
        self.calls = 0
        self.resets = 0
        self.last_result_class = "empty"

    def feed(self, pcm):
        self.calls += 1
        detected = next(self.detections, False)
        self.last_result_class = "wake" if detected else "nonwake"
        return [(object() if detected is True else detected)] if detected else []

    def reset(self):
        self.resets += 1
        self.last_result_class = "reset"


class Transcriber:
    def __init__(self, transcripts):
        self.transcripts = iter(transcripts)
        self.calls = 0
        self.audio_lengths = []

    def transcribe(self, audio, sample_rate):
        self.calls += 1
        self.audio_lengths.append(audio.size)
        return next(self.transcripts)


class Speaker:
    def __init__(self, result=True):
        self.messages = []
        self.result = result

    def speak(self, text):
        self.messages.append(text)
        return self.result


class Gate:
    def __init__(self, active=False):
        self.active = active

    def is_active(self):
        return self.active


class AlwaysOnVoiceTests(unittest.TestCase):
    def make_loop(self, probabilities, transcripts=(), *, detections=(), clock=None, gate=None, ask=None, config=None):
        clock = clock or Clock()
        config = config or AlwaysOnVoiceConfig(minimum_speech_ms=32, end_silence_ms=64, followup_window_seconds=1.0)
        self.transcriber = Transcriber(transcripts)
        self.speaker = Speaker()
        self.wake_detector = WakeDetector(detections)
        self.ask_calls = []

        def ask_fn(command, **kwargs):
            self.ask_calls.append((command, kwargs))
            return {"answer": "Grounded answer.", "grounding": "supported", "luna_invocations": 1}

        return AlwaysOnVoiceLoop(
            config,
            stream=Stream([CHUNK] * len(probabilities), clock),
            vad=Vad(probabilities),
            wake_detector=self.wake_detector,
            transcriber=self.transcriber,
            speaker=self.speaker,
            ask_fn=ask or ask_fn,
            diagnostics=VoiceDiagnostics(Path(tempfile.mkdtemp()) / "voice.json"),
            speech_activity=gate or Gate(),
            clock=clock,
        ), clock

    def run_loop(self, loop):
        return loop.run(threading.Event())

    @staticmethod
    def open_focus(loop, clock, *, conversation_id="focus-test"):
        """Install a bounded, RAM-only focus fixture without simulating TTS."""
        loop._conversation_id = conversation_id
        loop._focus_id = "focus-test"
        loop._focus_deadline = clock.value + 8.0
        loop._set_state(VoiceState.FOLLOWUP_LISTENING)

    def test_silence_never_reaches_whisper_or_luna(self):
        loop, _ = self.make_loop([0.0] * 8)
        self.assertEqual(self.run_loop(loop), 0)
        self.assertEqual(self.transcriber.calls, 0)
        self.assertEqual(self.ask_calls, [])

    def test_non_wake_speech_is_discarded_without_whisper_or_command(self):
        loop, _ = self.make_loop([0.9, 0.0, 0.0])
        self.assertEqual(self.run_loop(loop), 0)
        self.assertEqual(self.transcriber.calls, 0)
        self.assertEqual(self.ask_calls, [])
        self.assertEqual(self.speaker.messages, [])

    def test_vosk_wake_then_inline_command_uses_only_text_after_sentry(self):
        loop, _ = self.make_loop(
            [0.9, 0.0, 0.0],
            ["earlier speech Sentry, Is anyone in the office?"],
            detections=[False, True, False],
        )
        self.assertEqual(self.run_loop(loop), 0)
        self.assertEqual(self.ask_calls[0][0], "Is anyone in the office?")
        self.assertEqual(self.speaker.messages, ["Grounded answer."])
        self.assertGreater(loop.diagnostics.payload["last_command_dispatch_latency_ms"], 0)
        self.assertNotIn("transcript", loop.diagnostics.payload)

    def test_vosk_timed_tail_reaches_whisper_without_prewake_audio(self):
        class Detection:
            queued_after_token = np.ones(1_024, dtype=np.int16)

        loop, _ = self.make_loop(
            [0.0],
            ["Do I have an office reminder?"],
            detections=[Detection()],
        )
        self.assertEqual(self.run_loop(loop), 0)
        self.assertEqual(self.ask_calls[0][0], "Do I have an office reminder?")

    def test_bare_wake_recovered_from_timed_tail_arms_without_dispatch(self):
        class Detection:
            queued_after_token = np.ones(512, dtype=np.int16)

        loop, _ = self.make_loop([0.0], ["Sentry"], detections=[Detection()])
        self.assertEqual(self.run_loop(loop), 0)
        self.assertEqual(self.ask_calls, [])

    def test_wake_only_arms_then_followup_dispatches_without_second_wake(self):
        loop, _ = self.make_loop(
            [0.9, 0.0, 0.0, 0.9, 0.0, 0.0],
            ["Sentry", "What is the weather"],
            detections=[False, True, False, False, False, False],
        )
        self.assertEqual(self.run_loop(loop), 0)
        self.assertEqual(self.ask_calls[0][0], "What is the weather")

    def test_armed_timeout_makes_no_command(self):
        clock = Clock()
        loop, clock = self.make_loop([0.9, 0.0, 0.0, 0.0], ["Sentry"], detections=[False, True, False, False], clock=clock)
        loop.stream.step = 1.0
        self.assertEqual(self.run_loop(loop), 0)
        self.assertEqual(self.ask_calls, [])

    def test_multiple_vosk_frames_produce_one_command(self):
        loop, _ = self.make_loop(
            [0.9, 0.0, 0.0],
            ["Sentry, status"],
            detections=[False, True, True],
        )
        self.assertEqual(self.run_loop(loop), 0)
        self.assertEqual([call[0] for call in self.ask_calls], ["status"])
        self.assertEqual(loop.diagnostics.payload["wake_detections"], 1)

    def test_speech_activity_suppresses_wake_vad_and_transcription(self):
        loop, _ = self.make_loop([0.9, 0.9, 0.9], ["Sentry, test"], detections=[True, True, True], gate=Gate(active=True))
        self.assertEqual(self.run_loop(loop), 0)
        self.assertEqual(self.wake_detector.calls, 0)
        self.assertEqual(self.transcriber.calls, 0)
        self.assertEqual(self.ask_calls, [])

    def test_whisper_failure_after_wake_enters_armed_without_command(self):
        class BrokenTranscriber:
            def transcribe(self, audio, sample_rate):
                raise RuntimeError("failed")

        loop, _ = self.make_loop([0.9, 0.0, 0.0], detections=[False, True, False])
        loop.transcriber = BrokenTranscriber()
        self.assertEqual(self.run_loop(loop), 0)
        self.assertEqual(self.ask_calls, [])

    def test_diagnostics_never_include_ambient_transcript(self):
        with tempfile.TemporaryDirectory() as directory:
            diagnostics = VoiceDiagnostics(Path(directory) / "voice.json")
            diagnostics.update(state="LISTENING", last_segment_outcome="non_wake")
            contents = diagnostics.path.read_text(encoding="utf-8")
            self.assertNotIn("transcript", contents)
            self.assertNotIn("ordinary office conversation", contents)

    def test_config_is_opt_in_and_requires_vosk_model_when_enabled(self):
        self.assertFalse(AlwaysOnVoiceConfig.from_mapping({}).always_on_enabled)
        self.assertEqual(AlwaysOnVoiceConfig.from_mapping({}).wake_token, "sentry")
        with self.assertRaises(ValueError):
            AlwaysOnVoiceConfig.from_mapping({"always_on_enabled": True})
        with self.assertRaises(ValueError):
            AlwaysOnVoiceConfig.from_mapping({"base_url": "https://example.com"})

    def test_delivery_failure_returns_listener_to_safe_state(self):
        loop, _ = self.make_loop([0.9, 0.0, 0.0], ["Sentry, status"], detections=[False, True, False])
        loop.speaker = Speaker(result=False)
        self.assertEqual(self.run_loop(loop), 0)
        self.assertEqual(loop.state, VoiceState.DISABLED)
        self.assertEqual(self.ask_calls[0][0], "status")
        self.assertFalse(loop.diagnostics.payload["last_speech_delivery_success"])

    def test_successful_answer_opens_distinct_followup_state_after_rearm(self):
        config = AlwaysOnVoiceConfig(
            minimum_speech_ms=32,
            end_silence_ms=64,
            followup_window_seconds=1.0,
            post_speech_rearm_ms=0,
            conversation_followup_window_seconds=8.0,
            conversation_followup_max_turns=2,
        )
        loop, clock = self.make_loop([0.0], config=config)
        loop._conversation_id = "initial-focus"
        loop._dispatch_command("What is the weather today?", is_followup=False)
        self.assertEqual(loop.state, VoiceState.SPEAKING)
        loop.process_chunk(CHUNK)
        self.assertEqual(loop.state, VoiceState.FOLLOWUP_LISTENING)
        self.assertTrue(loop.diagnostics.payload["conversation_focus_active"])
        self.assertEqual(loop.diagnostics.payload["followup_turn_index"], 0)
        self.assertEqual(self.ask_calls[0][1]["conversation_id"], "initial-focus")

    def test_focus_followup_dispatches_without_wake_and_reuses_conversation_id(self):
        loop, clock = self.make_loop([0.9, 0.0, 0.0], ["What about tomorrow?"])
        self.open_focus(loop, clock, conversation_id="weather-focus")
        for _ in range(3):
            loop.process_chunk(CHUNK)
            clock.value += 0.032
        self.assertEqual(self.ask_calls[0][0], "What about tomorrow?")
        self.assertEqual(self.ask_calls[0][1]["conversation_id"], "weather-focus")
        self.assertEqual(loop._followup_turn_count, 1)
        self.assertTrue(loop._focus_pending)

    def test_optional_sentry_inside_focus_is_one_stripped_followup(self):
        loop, clock = self.make_loop([0.9, 0.0, 0.0], ["Sentry, what about tomorrow?"])
        self.open_focus(loop, clock)
        for _ in range(3):
            loop.process_chunk(CHUNK)
            clock.value += 0.032
        self.assertEqual([call[0] for call in self.ask_calls], ["what about tomorrow?"])
        self.assertEqual(loop.diagnostics.payload["command_dispatches"], 1)

    def test_second_followup_closes_focus_and_requires_wake_again(self):
        config = AlwaysOnVoiceConfig(minimum_speech_ms=32, end_silence_ms=64, followup_window_seconds=1.0, post_speech_rearm_ms=0)
        loop, clock = self.make_loop([0.0, 0.0], config=config)
        self.open_focus(loop, clock)
        loop._dispatch_command("first followup", is_followup=True)
        loop.process_chunk(CHUNK)
        self.assertEqual(loop.state, VoiceState.FOLLOWUP_LISTENING)
        loop._dispatch_command("second followup", is_followup=True)
        self.assertEqual(loop.state, VoiceState.LISTENING)
        self.assertFalse(loop._focus_active())
        self.assertEqual(loop.diagnostics.payload["followup_close_reason"], "turn_limit")
        self.assertEqual(loop._followup_turn_count, 2)

    def test_focus_timeout_closes_without_whisper_luna_or_dispatch(self):
        loop, clock = self.make_loop([0.0])
        self.open_focus(loop, clock)
        clock.value = 9.0
        loop.process_chunk(CHUNK)
        self.assertEqual(loop.state, VoiceState.LISTENING)
        self.assertEqual(self.transcriber.calls, 0)
        self.assertEqual(self.ask_calls, [])
        self.assertEqual(loop.diagnostics.payload["followup_close_reason"], "timeout")

    def test_speech_activity_closes_focus_and_cannot_dispatch_followup(self):
        gate = Gate(active=True)
        loop, clock = self.make_loop([0.9], ["should not dispatch"], gate=gate)
        self.open_focus(loop, clock)
        loop.process_chunk(CHUNK)
        self.assertEqual(loop.state, VoiceState.SPEAKING)
        self.assertFalse(loop._focus_active())
        self.assertEqual(self.transcriber.calls, 0)
        self.assertEqual(self.ask_calls, [])

    def test_shutdown_clears_ram_only_focus_state(self):
        loop, clock = self.make_loop([])
        self.open_focus(loop, clock)
        self.assertEqual(self.run_loop(loop), 0)
        self.assertFalse(loop._focus_active())
        self.assertEqual(loop.diagnostics.payload["followup_close_reason"], "shutdown")

    def test_followup_config_rejects_invalid_bounds(self):
        with self.assertRaises(ValueError):
            AlwaysOnVoiceConfig.from_mapping({"conversation_followup_window_seconds": 0})
        with self.assertRaises(ValueError):
            AlwaysOnVoiceConfig.from_mapping({"conversation_followup_max_turns": -1})


if __name__ == "__main__":
    unittest.main()
