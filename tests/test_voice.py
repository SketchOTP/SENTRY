import unittest
import json
from pathlib import Path
from unittest.mock import Mock, patch
from types import SimpleNamespace

import numpy as np

from perception.voice import KokoroSpeaker, ReactiveVoiceConfig, ReactiveVoiceLoop


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
        ask.assert_called_once_with(
            "Is anyone in the office?",
            base_url="http://127.0.0.1:48174",
            room_id="office",
            effort="low",
            timeout_seconds=120,
        )
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
        audio_b64 = "UklGRg=="
        synth = Mock(return_value=SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"audioBase64": audio_b64}).encode(),
            stderr=b"",
        ))
        player = Mock()
        player.returncode = 0
        with patch("perception.voice.subprocess.run", synth), patch(
            "perception.voice.subprocess.Popen", return_value=player
        ):
            speaker = KokoroSpeaker(
                python_executable="/usr/bin/python3",
                worker_script=Path(__file__).resolve().parents[1] / "tools" / "sentry_kokoro_worker.py",
                player="/usr/bin/pw-play",
            )
            self.assertTrue(speaker.speak("Welcome home."))
        self.assertEqual(synth.call_args.args[0][0], "/usr/bin/python3")
        self.assertEqual(player.communicate.call_args.args[0], b"RIFF")
        self.assertEqual(player.communicate.call_args.kwargs, {"timeout": 300})


if __name__ == "__main__":
    unittest.main()
