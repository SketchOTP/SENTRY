import tempfile
import threading
import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np

from perception.always_on_voice import AlwaysOnVoiceConfig, AlwaysOnVoiceLoop, VoiceDiagnostics, VoiceState
from perception.speaker_context import WakeIdentityCoordinator
from perception.vosk_kws import CommandStreamProgress


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


class CommandRecognizer:
    endpointer_mode = "test_host_boundary"

    def __init__(self, updates=()):
        self.updates = iter(updates)
        self.calls = 0
        self.resets = 0
        self.audio = []
        self.segment_count = 0

    def feed(self, audio):
        self.calls += 1
        self.audio.append(np.asarray(audio, dtype=np.int16).copy())
        value = next(self.updates, False)
        if value == "error":
            raise RuntimeError("command recognizer failed")
        if value == "final":
            self.segment_count += 1
        progressed = bool(value)
        return CommandStreamProgress(
            result_class=("segment_final" if value == "final" else ("partial" if progressed else "partial_empty")),
            progressed=progressed,
            finalized_segment_count=self.segment_count,
            partial_word_count=(1 if progressed and value != "final" else 0),
            observed_word_count=self.calls if progressed else 0,
            processing_ms=1.0,
        )

    def reset(self):
        self.resets += 1


class Transcriber:
    def __init__(self, transcripts):
        self.transcripts = iter(transcripts)
        self.calls = 0
        self.audio_lengths = []
        self.audio = []

    def transcribe(self, audio, sample_rate):
        self.calls += 1
        self.audio_lengths.append(audio.size)
        self.audio.append(np.asarray(audio, dtype=np.float32).copy())
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
    def make_loop(
        self, probabilities, transcripts=(), *, detections=(), command_updates=(),
        clock=None, gate=None, ask=None, config=None, fast_streaming_timing=True,
        presentation_completed=None, presentation_failed=None, response_expired=None,
        identity_coordinator=None, wake_chime=None,
    ):
        clock = clock or Clock()
        config = config or AlwaysOnVoiceConfig(minimum_speech_ms=32, end_silence_ms=64, followup_window_seconds=1.0)
        if fast_streaming_timing:
            config = replace(
                config,
                command_continuation_idle_ms=32,
                command_stability_recheck_ms=32,
                command_trailing_tail_ms=0,
            )
        probabilities = list(probabilities) + [0.0, 0.0]
        self.transcriber = Transcriber(transcripts)
        self.speaker = Speaker()
        self.wake_detector = WakeDetector(detections)
        self.command_recognizer = CommandRecognizer(command_updates)
        self.ask_calls = []

        def ask_fn(command, **kwargs):
            self.ask_calls.append((command, kwargs))
            return {"answer": "Grounded answer.", "grounding": "supported", "luna_invocations": 1}

        return AlwaysOnVoiceLoop(
            config,
            stream=Stream([CHUNK] * len(probabilities), clock),
            vad=Vad(probabilities),
            wake_detector=self.wake_detector,
            command_recognizer=self.command_recognizer,
            transcriber=self.transcriber,
            speaker=self.speaker,
            ask_fn=ask or ask_fn,
            action_presentation_completed_fn=presentation_completed,
            action_presentation_failed_fn=presentation_failed,
            action_response_expired_fn=response_expired,
            diagnostics=VoiceDiagnostics(Path(tempfile.mkdtemp()) / "voice.json"),
            speech_activity=gate or Gate(),
            identity_coordinator=identity_coordinator,
            wake_chime_fn=wake_chime,
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

    def test_non_wake_speech_never_starts_identity_camera(self):
        inspections = []
        coordinator = WakeIdentityCoordinator(lambda duration: inspections.append(duration) or {"people": []})
        loop, _ = self.make_loop(
            [0.9, 0.0, 0.0], identity_coordinator=coordinator,
        )
        self.assertEqual(self.run_loop(loop), 0)
        self.assertEqual(inspections, [])

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

    def test_accepted_vosk_wake_requests_preloaded_chime_exactly_once(self):
        chime_calls = []
        loop, _ = self.make_loop(
            [0.9, 0.0, 0.0],
            ["Sentry, status"],
            detections=[True, True, False],
            wake_chime=lambda: chime_calls.append("play") or True,
        )
        self.assertEqual(self.run_loop(loop), 0)
        self.assertEqual(chime_calls, ["play"])
        self.assertTrue(loop.diagnostics.payload["wake_chime_requested"])
        self.assertEqual(loop.diagnostics.payload["wake_chime_request_latency_ms"], 0.0)

    def test_first_wake_starts_identity_preflight_and_attaches_current_envelope(self):
        clock = Clock()
        inspections = []
        coordinator = WakeIdentityCoordinator(
            lambda duration: inspections.append(duration) or {
                "observed_at": "2026-09-02T22:14:00+00:00",
                "people": [{
                    "visible": True, "identity_state": "recognized",
                    "person_id": "primary_user", "display_name": "Sketch",
                    "identity_confidence": 0.91,
                }],
            },
            clock=clock,
        )
        loop, _ = self.make_loop(
            [0.9, 0.0, 0.0], ["Sentry, who are you talking to?"],
            detections=[True, False, False], clock=clock,
            identity_coordinator=coordinator,
        )
        self.assertEqual(self.run_loop(loop), 0)
        self.assertEqual(inspections, [3.0])
        envelope = self.ask_calls[0][1]["speaker_context"]
        self.assertEqual(envelope["status"], "recognized")
        self.assertEqual(envelope["display_name"], "Sketch")
        self.assertFalse(envelope["exact_arrival_known"])
        self.assertFalse(envelope["frames_persisted"])
        self.assertFalse(envelope["image_shared_with_codex"])

    def test_followup_and_pending_response_reuse_identity_without_camera(self):
        clock = Clock()
        inspections = []
        coordinator = WakeIdentityCoordinator(
            lambda duration: inspections.append(duration) or {
                "observed_at": "2026-09-02T22:14:00+00:00", "people": [],
            },
            clock=clock,
        )
        loop, _ = self.make_loop([0.0], clock=clock, identity_coordinator=coordinator)
        loop._begin_wake_conversation()
        first = coordinator.current_envelope(wait_for_preflight=True)
        loop._focus_id = "focus"
        loop._focus_deadline = 8.0
        loop._dispatch_command("followup", is_followup=True)
        loop._action_response_authorization_id = "auth-1"
        loop._action_response_deadline = 120.0
        loop._dispatch_command("cancel", is_followup=False, is_action_response=True)
        self.assertEqual(inspections, [3.0])
        self.assertEqual(self.ask_calls[0][1]["speaker_context"]["context_id"], first["context_id"])
        self.assertEqual(self.ask_calls[1][1]["speaker_context"]["context_id"], first["context_id"])

    def test_thread_rotation_response_keeps_still_valid_speaker_context(self):
        clock = Clock()
        coordinator = WakeIdentityCoordinator(
            lambda _duration: {
                "observed_at": "2026-09-02T22:14:00+00:00",
                "people": [{
                    "visible": True,
                    "identity_state": "recognized",
                    "person_id": "primary_user",
                    "display_name": "Sketch",
                }],
            },
            clock=clock,
        )
        loop, _ = self.make_loop(
            [0.0], clock=clock, identity_coordinator=coordinator,
            ask=lambda _command, **_kwargs: {
                "answer": "Conversation rotated.", "luna_invocations": 0,
                "security_handler": "conversation_rotated",
            },
        )
        loop._begin_wake_conversation()
        first = coordinator.current_envelope(wait_for_preflight=True)
        loop._dispatch_command("rotate conversation", is_followup=False)
        current = coordinator.current_envelope()
        self.assertEqual(current["status"], "recognized")
        self.assertEqual(current["display_name"], "Sketch")
        self.assertEqual(current["context_id"], first["context_id"])

    def test_vosk_authority_allows_one_full_whisper_pass_when_wake_is_omitted(self):
        class Detection:
            samples_after_token = 512

        loop, _ = self.make_loop(
            [0.9, 0.0, 0.0],
            ["Do I have an office reminder?"],
            detections=[Detection(), False, False],
        )
        self.assertEqual(self.run_loop(loop), 0)
        self.assertEqual(self.ask_calls[0][0], "Do I have an office reminder?")
        self.assertEqual(self.transcriber.calls, 1)
        self.assertEqual(loop.diagnostics.payload["transcription_view"], "full_utterance")
        self.assertEqual(
            loop.diagnostics.payload["command_extraction_mode"],
            "vosk_authorized_full_transcript",
        )

    def test_early_vosk_wake_waits_for_same_long_utterance_endpoint(self):
        class Detection:
            samples_after_token = 256

        loop, _ = self.make_loop(
            [0.9, 0.9, 0.9, 0.9, 0.0, 0.0],
            ["Create a detailed multi-step execution plan and inspect the workspace"],
            detections=[Detection(), False, False, False, False, False],
        )

        self.assertEqual(self.run_loop(loop), 0)
        self.assertEqual(
            [call[0] for call in self.ask_calls],
            ["Create a detailed multi-step execution plan and inspect the workspace"],
        )
        self.assertEqual(self.transcriber.calls, 1)
        self.assertGreater(self.transcriber.audio_lengths[0], 3 * CHUNK.size)

    def test_early_wake_without_command_waits_before_entering_armed(self):
        class Detection:
            samples_after_token = 0

        clock = Clock()
        loop, clock = self.make_loop(
            [0.0, 0.0, 0.0],
            ["Sentry"],
            detections=[Detection(), False, False],
            clock=clock,
            config=AlwaysOnVoiceConfig(
                minimum_speech_ms=32,
                end_silence_ms=64,
                followup_window_seconds=1.0,
            ),
        )
        self.assertEqual(self.run_loop(loop), 0)
        self.assertEqual(self.transcriber.calls, 1)
        self.assertEqual(self.ask_calls, [])

    def test_streaming_idle_candidate_requires_stability_recheck(self):
        loop, _ = self.make_loop(
            [0.9, 0.0, 0.0],
            ["Sentry, move the file"],
            detections=[object(), False, False],
        )

        self.assertEqual(self.run_loop(loop), 0)
        self.assertEqual(self.transcriber.calls, 1)
        self.assertEqual(len(self.ask_calls), 1)
        self.assertEqual(loop.diagnostics.payload["command_close_candidates"], 1)
        self.assertEqual(loop.diagnostics.payload["endpoint_reason"], "streaming_command_idle")

    def test_stream_progress_keeps_same_capture_across_pause(self):
        loop, _ = self.make_loop(
            [0.9, 0.0, 0.9, 0.0, 0.0],
            ["Sentry, finish the whole request"],
            detections=[object(), False, False, False, False],
            command_updates=[True, False, True, False, False],
        )

        self.assertEqual(self.run_loop(loop), 0)
        self.assertEqual(len(self.ask_calls), 1)
        self.assertGreaterEqual(self.command_recognizer.calls, 5)
        self.assertEqual(loop.diagnostics.payload["capture_gap_count"], 0)
        self.assertGreaterEqual(self.transcriber.audio_lengths[0], 3 * CHUNK.size)

    def test_renewed_speech_cancels_pending_idle_candidate(self):
        config = AlwaysOnVoiceConfig(
            minimum_speech_ms=32,
            end_silence_ms=64,
            followup_window_seconds=1.0,
            command_continuation_idle_ms=64,
            command_stability_recheck_ms=32,
            command_trailing_tail_ms=0,
        )
        loop, _ = self.make_loop(
            [0.9, 0.0, 0.0, 0.9, 0.0, 0.0],
            ["Sentry, finish after resuming"],
            detections=[object(), False, False, False, False, False],
            config=config,
            fast_streaming_timing=False,
        )

        self.assertEqual(self.run_loop(loop), 0)
        self.assertEqual(len(self.ask_calls), 1)
        self.assertEqual(loop.diagnostics.payload["command_close_candidate_cancellations"], 1)
        self.assertEqual(loop.diagnostics.payload["command_close_cancel_reason"], "speech_resumed")

    def test_multiple_vosk_segment_finals_do_not_close_or_duplicate_dispatch(self):
        loop, _ = self.make_loop(
            [0.9, 0.9, 0.0, 0.9, 0.0, 0.0],
            ["Sentry, answer this once"],
            detections=[object(), False, False, False, False, False],
            command_updates=["final", "final", "final", False, False, False],
        )

        self.assertEqual(self.run_loop(loop), 0)
        self.assertEqual(self.transcriber.calls, 1)
        self.assertEqual(len(self.ask_calls), 1)
        self.assertGreaterEqual(loop.diagnostics.payload["command_stream_finalized_segment_count"], 3)
        self.assertEqual(loop.diagnostics.payload["endpoint_reason"], "streaming_command_idle")

    def test_command_recognizer_error_fails_before_whisper_or_dispatch(self):
        loop, clock = self.make_loop(
            [0.9],
            ["must not be used"],
            detections=[object()],
            command_updates=["error"],
        )

        self.assertEqual(self.run_loop(loop), 1)
        self.assertEqual(self.transcriber.calls, 0)
        self.assertEqual(self.ask_calls, [])
        self.assertIn("RuntimeError", loop.diagnostics.payload["last_error"])

    def test_nonwake_segment_never_starts_command_recognizer_or_whisper(self):
        loop, _ = self.make_loop([0.9, 0.0, 0.0], detections=[False, False, False])

        self.assertEqual(self.run_loop(loop), 0)
        self.assertEqual(self.command_recognizer.calls, 0)
        self.assertEqual(self.transcriber.calls, 0)
        self.assertEqual(self.ask_calls, [])

    def test_new_wake_after_completed_nonwake_segment_uses_only_current_timeline(self):
        class Detection:
            samples_after_token = 0

        loop, _ = self.make_loop(
            [0.9, 0.0, 0.0, 0.9, 0.9, 0.0, 0.0],
            ["Sentry move the controlled file to Downloads after confirmation"],
            detections=[False, False, False, Detection(), False, False, False],
        )

        self.assertEqual(self.run_loop(loop), 0)
        self.assertEqual(
            [call[0] for call in self.ask_calls],
            ["move the controlled file to Downloads after confirmation"],
        )
        self.assertEqual(self.transcriber.calls, 1)

    def test_vad_hysteresis_keeps_low_energy_authorized_speech_in_one_segment(self):
        class Detection:
            samples_after_token = 256

        config = AlwaysOnVoiceConfig(
            minimum_speech_ms=32,
            end_silence_ms=64,
            followup_window_seconds=1.0,
            vad_threshold=0.35,
            vad_continuation_threshold=0.20,
        )
        loop, _ = self.make_loop(
            [0.40, 0.25, 0.22, 0.24, 0.0, 0.0],
            [
                "Carry out this longer natural command without clipping it",
                "Carry out this longer natural command without clipping it",
            ],
            detections=[Detection(), False, False, False, False, False],
            config=config,
        )

        self.assertEqual(self.run_loop(loop), 0)
        self.assertEqual(len(self.ask_calls), 1)
        self.assertGreater(self.transcriber.audio_lengths[0], 3 * CHUNK.size)

    def test_active_long_capture_uses_vosk_post_token_boundary_for_whisper(self):
        class Detection:
            samples_after_token = 128

        loop, _ = self.make_loop(
            [0.9, 0.9, 0.0, 0.0],
            ["Sentry move the controlled file to Downloads as cancelled voice proof"],
            detections=[False, Detection(), False, False],
        )

        self.assertEqual(self.run_loop(loop), 0)
        self.assertEqual(
            self.ask_calls[0][0],
            "move the controlled file to Downloads as cancelled voice proof",
        )
        self.assertGreaterEqual(self.transcriber.audio_lengths[0], 2 * CHUNK.size)

    def test_late_final_wake_uses_exact_tail_distance_beyond_ring_buffer(self):
        class Detection:
            samples_after_token = 8 * CHUNK.size

        loop, _ = self.make_loop(
            [0.9] * 10 + [0.0, 0.0],
            ["Sentry execute the complete long command after the wake token"],
            detections=[False] * 9 + [Detection(), False, False],
        )

        self.assertEqual(self.run_loop(loop), 0)
        self.assertEqual(len(self.ask_calls), 1)
        self.assertGreaterEqual(self.transcriber.audio_lengths[0], 10 * CHUNK.size)

    def test_vosk_authorized_long_command_survives_whisper_omitting_wake_token(self):
        class Detection:
            samples_after_token = 3 * CHUNK.size

        config = AlwaysOnVoiceConfig(
            minimum_speech_ms=32,
            end_silence_ms=64,
            followup_window_seconds=1.0,
        )
        loop, _ = self.make_loop(
            [0.9] * 50 + [0.0, 0.0],
            [
                "Move the controlled proof file to Downloads but wait for confirmation",
                "Move the controlled proof file to Downloads but wait for confirmation",
            ],
            detections=[False] * 49 + [Detection(), False, False],
            config=config,
        )

        self.assertEqual(self.run_loop(loop), 0)
        self.assertEqual(
            [call[0] for call in self.ask_calls],
            ["Move the controlled proof file to Downloads but wait for confirmation"],
        )
        self.assertEqual(
            loop.diagnostics.payload["command_extraction_mode"],
            "vosk_authorized_full_transcript",
        )

    def test_short_wake_only_misrecognition_does_not_become_a_command(self):
        loop, _ = self.make_loop(
            [0.9, 0.0, 0.0],
            ["Century"],
            detections=[False, True, False],
        )

        self.assertEqual(self.run_loop(loop), 0)
        self.assertEqual(self.ask_calls, [])

    def test_bare_wake_recovered_from_timed_tail_arms_without_dispatch(self):
        class Detection:
            samples_after_token = 512

        loop, _ = self.make_loop([0.0], ["Sentry"], detections=[Detection()])
        self.assertEqual(self.run_loop(loop), 0)
        self.assertEqual(self.ask_calls, [])

    def test_wake_only_arms_then_followup_dispatches_without_second_wake(self):
        loop, _ = self.make_loop(
            [0.9, 0.0, 0.0, 0.0, 0.9, 0.0, 0.0],
            ["Sentry", "What is the weather"],
            detections=[False, True, False, False, False, False, False],
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
        self.assertFalse(AlwaysOnVoiceConfig.from_mapping({}).sleep_enabled)
        self.assertEqual(AlwaysOnVoiceConfig.from_mapping({}).wake_token, "sentry")
        with self.assertRaises(ValueError):
            AlwaysOnVoiceConfig.from_mapping({"always_on_enabled": True})

    def test_sleep_enabled_opens_no_microphone_and_accepts_no_wake(self):
        chime_calls = []
        loop, _ = self.make_loop(
            [0.9],
            detections=[True],
            config=AlwaysOnVoiceConfig(
                sleep_enabled=True,
                minimum_speech_ms=32,
                end_silence_ms=64,
            ),
            wake_chime=lambda: chime_calls.append("play") or True,
        )

        class ForbiddenStream:
            def iter_chunks(self, _stop_event):
                raise AssertionError("sleep mode must not open the microphone")

        loop.stream = ForbiddenStream()
        self.assertEqual(self.run_loop(loop), 0)
        self.assertEqual(loop.state, VoiceState.SLEEPING)
        self.assertEqual(loop.wake_detector.calls, 0)
        self.assertEqual(self.transcriber.calls, 0)
        self.assertEqual(self.ask_calls, [])
        self.assertEqual(chime_calls, [])
        self.assertFalse(loop.diagnostics.payload["wake_enabled"])

    def test_config_accepts_supported_english_kokoro_voices(self):
        config = AlwaysOnVoiceConfig.from_mapping({"kokoro_voice": "bm_george", "kokoro_speed": 0.9})
        self.assertEqual(config.kokoro_voice, "bm_george")
        self.assertEqual(
            AlwaysOnVoiceConfig.from_mapping({"kokoro_voice": "am_michael"}).kokoro_voice,
            "am_michael",
        )
        with self.assertRaises(ValueError):
            AlwaysOnVoiceConfig.from_mapping({"kokoro_voice": "unknown_voice"})
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

    def test_host_security_response_does_not_erase_known_codex_thread_status(self):
        def host_response(_command, **_kwargs):
            return {
                "answer": "The exact pending action was completed.",
                "luna_invocations": 0,
                "security_handler": "authorization_completed",
            }

        loop, _ = self.make_loop([0.0], ask=host_response)
        loop.diagnostics.update(codex_thread_active=True, codex_session_resumed=True)
        loop._dispatch_command("confirm", is_followup=False)

        self.assertTrue(loop.diagnostics.payload["codex_thread_active"])
        self.assertTrue(loop.diagnostics.payload["codex_session_resumed"])

    def test_pending_action_opens_distinct_wake_free_response_window_after_tts(self):
        completed = []

        def ask_with_pending(_command, **_kwargs):
            return {
                "answer": "I'm ready to move the controlled file. Shall I do that?",
                "luna_invocations": 1,
                "action_dialogue": {
                    "pending": True,
                    "authorization_id": "auth-1",
                    "target_summary": "move controlled file",
                },
            }

        def complete(authorization_id, **kwargs):
            completed.append((authorization_id, kwargs))
            return {"authorization_id": authorization_id, "target_summary": "move controlled file"}

        config = AlwaysOnVoiceConfig(
            minimum_speech_ms=32, end_silence_ms=64, post_speech_rearm_ms=0,
            action_response_window_seconds=120,
        )
        loop, _ = self.make_loop([0.0], ask=ask_with_pending, config=config, presentation_completed=complete)
        loop._dispatch_command("move it after confirmation", is_followup=False)
        self.assertEqual(loop.state, VoiceState.SPEAKING)
        loop.process_chunk(CHUNK)
        self.assertEqual(loop.state, VoiceState.AWAITING_OPERATOR_RESPONSE)
        self.assertTrue(loop.diagnostics.payload["action_response_active"])
        self.assertEqual(completed[0][0], "auth-1")
        self.assertEqual(completed[0][1]["response_window_seconds"], 120)

    def test_natural_pending_response_is_captured_without_second_wake(self):
        responses = iter([
            {
                "answer": "Shall I move the file?", "luna_invocations": 1,
                "action_dialogue": {"pending": True, "authorization_id": "auth-1", "target_summary": "move file"},
            },
            {"answer": "Done.", "luna_invocations": 0, "security_handler": "action_approved"},
        ])
        ask_calls = []

        def ask(command, **kwargs):
            ask_calls.append((command, kwargs))
            return next(responses)

        config = AlwaysOnVoiceConfig(
            minimum_speech_ms=32, end_silence_ms=64, post_speech_rearm_ms=0,
            action_response_window_seconds=120,
        )
        loop, clock = self.make_loop(
            [0.0, 0.9, 0.0, 0.0], ["Confirmed."], ask=ask, config=config,
            presentation_completed=lambda authorization_id, **_kwargs: {
                "authorization_id": authorization_id, "target_summary": "move file",
            },
        )
        loop._conversation_id = "action-context"
        loop._dispatch_command("move it after confirmation", is_followup=False)
        for _ in range(4):
            loop.process_chunk(CHUNK)
            clock.value += 0.032
        self.assertEqual([item[0] for item in ask_calls], ["move it after confirmation", "Confirmed."])
        self.assertEqual(self.wake_detector.calls, 4)
        self.assertFalse(loop._action_response_active())
        self.assertEqual(self.speaker.messages[-1], "Done.")
        self.assertEqual(loop.diagnostics.payload["action_response_close_reason"], "resolved")

    def test_pending_action_timeout_expires_without_whisper_or_agent_dispatch(self):
        expired = []
        config = AlwaysOnVoiceConfig(
            minimum_speech_ms=32, end_silence_ms=64,
            action_response_window_seconds=120,
        )
        loop, clock = self.make_loop(
            [0.0], config=config,
            response_expired=lambda authorization_id, **_kwargs: expired.append(authorization_id) or {"status": "EXPIRED"},
        )
        loop._action_response_authorization_id = "auth-1"
        loop._action_response_deadline = 120.0
        loop._set_state(VoiceState.AWAITING_OPERATOR_RESPONSE)
        clock.value = 121.0
        loop.process_chunk(CHUNK)
        self.assertEqual(expired, ["auth-1"])
        self.assertEqual(self.transcriber.calls, 0)
        self.assertEqual(self.ask_calls, [])
        self.assertEqual(loop.state, VoiceState.LISTENING)

    def test_failed_action_prompt_delivery_never_opens_response_window(self):
        failed = []

        def pending(_command, **_kwargs):
            return {
                "answer": "Shall I do that?", "luna_invocations": 0,
                "action_dialogue": {"pending": True, "authorization_id": "auth-1", "target_summary": "move file"},
            }

        loop, _ = self.make_loop(
            [0.0], ask=pending,
            presentation_completed=lambda *_args, **_kwargs: self.fail("must not become actionable"),
            presentation_failed=lambda authorization_id, **_kwargs: failed.append(authorization_id) or {"status": "FAILED"},
        )
        loop.speaker = Speaker(result=False)
        loop._dispatch_command("move it later", is_followup=False)
        self.assertEqual(failed, ["auth-1"])
        self.assertFalse(loop._action_response_active())
        self.assertEqual(loop.state, VoiceState.LISTENING)

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
            AlwaysOnVoiceConfig.from_mapping({"action_response_window_seconds": 0})
        with self.assertRaises(ValueError):
            AlwaysOnVoiceConfig.from_mapping({"conversation_followup_max_turns": -1})
        with self.assertRaises(ValueError):
            AlwaysOnVoiceConfig.from_mapping({"vad_threshold": 0.35, "vad_continuation_threshold": 0.4})
        with self.assertRaises(ValueError):
            AlwaysOnVoiceConfig.from_mapping({"wake_identity_refresh_idle_seconds": 0})
        with self.assertRaises(ValueError):
            AlwaysOnVoiceConfig.from_mapping({
                "wake_identity_camera_duration_seconds": 6,
                "wake_identity_join_timeout_seconds": 5,
            })

    def test_twelve_second_fragmented_command_freezes_exact_pcm_once(self):
        command_chunks = 375
        trailing_silence = 170
        total = 2 + command_chunks + trailing_silence
        chunks = [np.full(512, index / 1000, dtype=np.float32) for index in range(total)]
        probabilities = [0.0, 0.0] + [0.9] * command_chunks + [0.0] * trailing_silence
        for start, length in ((80, 10), (170, 56), (260, 10), (330, 10)):
            for index in range(start, start + length):
                probabilities[2 + index] = 0.0
        detections = [False] * total
        detections[5] = object()
        config = AlwaysOnVoiceConfig(
            minimum_speech_ms=32,
            pre_speech_ms=64,
            end_silence_ms=1500,
            maximum_utterance_seconds=45,
            command_continuation_idle_ms=5000,
            command_stability_recheck_ms=400,
            command_trailing_tail_ms=500,
        )
        loop, clock = self.make_loop(
            probabilities,
            ["Sentry, move the controlled file after exact confirmation"],
            detections=detections,
            config=config,
            fast_streaming_timing=False,
        )
        loop.stream = Stream(chunks, clock)

        self.assertEqual(self.run_loop(loop), 0)
        self.assertEqual(self.transcriber.calls, 1)
        # The source remains open through five seconds of final idle, while
        # batch Whisper receives only a deterministic 500 ms trailing tail.
        np.testing.assert_array_equal(
            self.transcriber.audio[0],
            np.concatenate(chunks)[: (2 + command_chunks) * 512 + 8_000],
        )
        self.assertEqual(len(self.ask_calls), 1)
        self.assertGreater(self.transcriber.audio_lengths[0] / 16_000, 12.0)
        self.assertGreaterEqual(loop.diagnostics.payload["capture_source_duration_ms"], 17_000)
        self.assertGreater(loop.diagnostics.payload["trailing_idle_trimmed_ms"], 4_000)
        self.assertEqual(loop.diagnostics.payload["capture_gap_count"], 0)
        self.assertEqual(loop.diagnostics.payload["transcription_attempt_count"], 1)

    def test_late_wake_promotes_complete_speech_epoch_not_recent_tail(self):
        speech_chunks = 160
        chunks = [np.full(512, index / 1000, dtype=np.float32) for index in range(speech_chunks + 2)]
        detections = [False] * (speech_chunks + 2)
        detections[120] = object()
        loop, clock = self.make_loop(
            [0.9] * speech_chunks + [0.0, 0.0],
            ["Sentry, keep the entire command from the beginning"],
            detections=detections,
            config=AlwaysOnVoiceConfig(
                minimum_speech_ms=32,
                pre_speech_ms=0,
                end_silence_ms=64,
            ),
        )
        loop.stream = Stream(chunks, clock)

        self.assertEqual(self.run_loop(loop), 0)
        np.testing.assert_array_equal(self.transcriber.audio[0], np.concatenate(chunks[:speech_chunks]))
        self.assertGreater(self.transcriber.audio_lengths[0], 3 * 16_000)

    def test_early_partial_wake_and_later_duplicate_keep_one_capture_and_dispatch(self):
        detections = [False, object()] + [False] * 20 + [object()] + [False, False]
        probabilities = [0.9] * (len(detections) - 2) + [0.0, 0.0]
        loop, _ = self.make_loop(
            probabilities,
            ["Sentry, execute this one request exactly once"],
            detections=detections,
        )

        self.assertEqual(self.run_loop(loop), 0)
        self.assertEqual(len(self.ask_calls), 1)
        self.assertEqual(loop.diagnostics.payload["wake_detections"], 1)
        self.assertGreaterEqual(loop.diagnostics.payload["wake_debounce_suppressions"], 1)

    def test_audio_gap_inside_authorized_capture_fails_before_stt_or_dispatch(self):
        loop, _ = self.make_loop([0.9, 0.9], detections=[object(), False])
        loop._set_state(VoiceState.LISTENING)
        loop.process_chunk(CHUNK, sequence_number=0, start_sample=0)
        loop.process_chunk(CHUNK, sequence_number=2, start_sample=1024)

        self.assertEqual(self.transcriber.calls, 0)
        self.assertEqual(self.ask_calls, [])
        self.assertEqual(loop.diagnostics.payload["last_segment_outcome"], "audio_gap")
        self.assertGreaterEqual(loop.diagnostics.payload["capture_gap_count"], 1)

    def test_maximum_duration_never_transcribes_or_proposes_partial_command(self):
        config = AlwaysOnVoiceConfig(
            minimum_speech_ms=32,
            pre_speech_ms=0,
            end_silence_ms=64,
            maximum_utterance_seconds=0.096,
            timeline_capacity_seconds=1.0,
        )
        loop, _ = self.make_loop(
            [0.9, 0.9, 0.9, 0.9],
            detections=[object(), False, False, False],
            config=config,
        )

        self.assertEqual(self.run_loop(loop), 0)
        self.assertEqual(self.transcriber.calls, 0)
        self.assertEqual(self.ask_calls, [])
        self.assertIn("too long", self.speaker.messages[0].lower())
        self.assertEqual(loop.diagnostics.payload["last_command_transcription_status"], "truncated")

    def test_empty_post_wake_view_enters_armed_without_guessing_command(self):
        class Detection:
            samples_after_token = 0

        loop, _ = self.make_loop(
            [0.9, 0.0, 0.0],
            ["Move"],
            detections=[Detection(), False, False],
        )

        self.assertEqual(self.run_loop(loop), 0)
        self.assertEqual(self.ask_calls, [])
        self.assertEqual(self.transcriber.calls, 1)


if __name__ == "__main__":
    unittest.main()
