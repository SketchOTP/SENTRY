import unittest
import base64
import io
import json
from pathlib import Path
from unittest.mock import Mock, patch
from types import SimpleNamespace
import wave

import numpy as np

from perception.voice import (
    KokoroSpeaker,
    PulseCachedWakeChime,
    ReactiveVoiceConfig,
    ReactiveVoiceLoop,
    normalized_audio_level,
)


class VoiceTests(unittest.TestCase):
    def setUp(self):
        self.recorder = Mock()
        self.recorder.record.return_value = np.zeros(16000, dtype=np.float32)
        self.transcriber = Mock()
        self.speaker = Mock()
        self.speaker.speak.return_value = True

    def loop(self, ask_fn):
        return ReactiveVoiceLoop(
            ReactiveVoiceConfig(recording_seconds=1.0),
            recorder=self.recorder,
            transcriber=self.transcriber,
            speaker=self.speaker,
            ask_fn=ask_fn,
        )

    def test_transient_audio_is_transcribed_then_discarded_after_one_grounded_answer(self):
        self.transcriber.transcribe.return_value = "Is anyone in the office?"
        ask = Mock(return_value={"answer": "The office is occupied.", "grounding": "supported", "luna_invocations": 1})
        result = self.loop(ask).run_once()
        self.assertEqual(result.status, "answered")
        self.assertEqual(result.delivery, "delivered")
        ask.assert_called_once()
        self.assertEqual(ask.call_args.args, ("Is anyone in the office?",))
        self.assertEqual(ask.call_args.kwargs["base_url"], "http://127.0.0.1:48174")
        self.assertEqual(ask.call_args.kwargs["room_id"], "office")
        self.assertEqual(ask.call_args.kwargs["effort"], "low")
        self.assertEqual(ask.call_args.kwargs["timeout_seconds"], 120)
        self.assertTrue(ask.call_args.kwargs["conversation_id"].startswith("reactive-"))
        self.speaker.speak.assert_called_once_with("The office is occupied.")
        self.recorder.record.assert_called_once_with(1.0)
        self.transcriber.transcribe.assert_called_once()

    def test_no_speech_does_not_call_m4_or_speaker(self):
        self.transcriber.transcribe.return_value = ""
        ask = Mock()
        result = self.loop(ask).run_once()
        self.assertEqual(result.status, "no_speech")
        ask.assert_not_called()
        self.speaker.speak.assert_not_called()

    def test_m4_unavailable_answer_is_still_delivered_truthfully(self):
        self.transcriber.transcribe.return_value = "Who is in the office?"
        ask = Mock(return_value={
            "answer": "SENTRY state is currently unavailable, so I can't answer that reliably.",
            "grounding": "unavailable",
            "luna_invocations": 0,
        })
        result = self.loop(ask).run_once()
        self.assertEqual(result.status, "answered")
        self.assertEqual(result.grounding, "unavailable")
        self.assertEqual(result.luna_invocations, 0)
        self.speaker.speak.assert_called_once()

    def test_recording_or_transcription_failure_does_not_call_m4(self):
        self.recorder.record.side_effect = RuntimeError("microphone unavailable")
        ask = Mock()
        result = self.loop(ask).run_once()
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.luna_invocations, 0)
        ask.assert_not_called()
        self.speaker.speak.assert_not_called()

    def test_kokoro_uses_local_worker_and_pipewire_not_remote_service(self):
        output = io.BytesIO()
        with wave.open(output, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(24_000)
            wav.writeframes(b"\x00\x00" * 8)
        audio_b64 = base64.b64encode(output.getvalue()).decode("ascii")
        synth = Mock(return_value=SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"audioBase64": audio_b64}).encode(),
            stderr=b"",
        ))
        player = Mock()
        player.returncode = 0
        with patch("perception.voice.subprocess.run", synth), patch(
            "perception.voice.subprocess.Popen", return_value=player
        ) as popen:
            speaker = KokoroSpeaker(
                python_executable="/usr/bin/python3",
                worker_script=Path(__file__).resolve().parents[1] / "tools" / "sentry_kokoro_worker.py",
                player="/usr/bin/pw-play",
            )
            self.assertTrue(speaker.speak("Welcome home."))
        self.assertEqual(synth.call_args.args[0][0], "/usr/bin/python3")
        self.assertEqual(player.communicate.call_args.args[0], b"\x00\x00" * 8)
        self.assertEqual(player.communicate.call_args.kwargs, {"timeout": 300})
        self.assertIn("--rate", popen.call_args.args[0])
        self.assertIn("24000", popen.call_args.args[0])

    def test_wake_chime_is_preloaded_then_played_from_the_audio_server_cache(self):
        upload = SimpleNamespace(returncode=0)
        with patch("perception.voice.subprocess.run", return_value=upload) as run, patch(
            "perception.voice.subprocess.Popen", return_value=SimpleNamespace()
        ) as popen:
            chime = PulseCachedWakeChime(
                pactl="/usr/bin/pactl",
                sound_path=__file__,
                sample_name="sentry-wake-test",
            )
            self.assertTrue(chime.prepare())
            self.assertTrue(chime.play())
            chime.close()

        self.assertEqual(
            run.call_args_list[0].args[0],
            ["/usr/bin/pactl", "upload-sample", __file__, "sentry-wake-test"],
        )
        self.assertEqual(
            popen.call_args.args[0],
            ["/usr/bin/pactl", "play-sample", "sentry-wake-test"],
        )
        self.assertEqual(
            run.call_args_list[-1].args[0],
            ["/usr/bin/pactl", "remove-sample", "sentry-wake-test"],
        )

    def test_default_wake_cue_uses_the_bubble_pop_not_volume_change_sound(self):
        names = [path.name for path in PulseCachedWakeChime.DEFAULT_SOUND_PATHS]
        self.assertEqual(names[0], "message.oga")
        self.assertNotIn("audio-volume-change.oga", names)

    def test_audio_level_is_bounded_and_tracks_pcm_energy(self):
        silence = normalized_audio_level(np.zeros(512, dtype=np.float32))
        quiet = normalized_audio_level(np.full(512, 0.002, dtype=np.float32))
        loud = normalized_audio_level(np.full(512, 0.5, dtype=np.float32))
        self.assertEqual(silence, 0.0)
        self.assertGreater(quiet, silence)
        self.assertGreater(loud, quiet)
        self.assertLessEqual(loud, 1.0)

    def test_kokoro_reports_actual_output_pcm_level_then_resets(self):
        output = io.BytesIO()
        with wave.open(output, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(24_000)
            wav.writeframes((8192).to_bytes(2, "little", signed=True) * 480)
        audio_b64 = base64.b64encode(output.getvalue()).decode("ascii")
        synth = Mock(return_value=SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"audioBase64": audio_b64}).encode(),
            stderr=b"",
        ))
        player = Mock()
        player.returncode = 0
        player.poll.return_value = None
        levels: list[float] = []
        with patch("perception.voice.subprocess.run", synth), patch(
            "perception.voice.subprocess.Popen", return_value=player,
        ):
            speaker = KokoroSpeaker(
                python_executable="/usr/bin/python3",
                worker_script=Path(__file__).resolve().parents[1] / "tools" / "sentry_kokoro_worker.py",
                player="/usr/bin/pw-play",
                level_callback=levels.append,
            )
            self.assertTrue(speaker.speak("Audio-reactive orb proof."))
        self.assertGreater(max(levels), 0.0)
        self.assertEqual(levels[-1], 0.0)


if __name__ == "__main__":
    unittest.main()
