import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.sentry_projection_io import HDMI_ALSA_DEVICE, ProjectionState


class ProjectionAudioTests(unittest.TestCase):
    def make_state(self, root: Path) -> ProjectionState:
        token = root / "projection.token"
        token.write_text("test-token\n", encoding="utf-8")
        return ProjectionState(token_file=token, settings_file=root / "projection.json")

    def test_hdmi_selection_uses_fixed_probe_and_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = self.make_state(Path(tmp))
            with patch.object(state, "hdmi_available", return_value=True):
                result = state.set_output("hdmi")
            self.assertEqual(result["audio_output"], "hdmi")
            self.assertEqual(result["sink"], {"id": "rpi5-hdmi", "name": "Roku TV HDMI"})
            self.assertEqual(json.loads(state.settings_file.read_text())["audio_output"], "hdmi")

    def test_hdmi_selection_fails_without_fixed_device(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = self.make_state(Path(tmp))
            with patch.object(state, "hdmi_available", return_value=False), self.assertRaisesRegex(
                RuntimeError, "HDMI ALSA playback"
            ):
                state.set_output("hdmi")
            self.assertEqual(state.selected_output(), "usb")

    def test_hdmi_playback_uses_aplay_and_validates_wav(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = self.make_state(Path(tmp))
            state._write_settings("hdmi")
            with patch("tools.sentry_projection_io.validate_wav_payload") as validate, patch(
                "tools.sentry_projection_io.subprocess.run"
            ) as run:
                state.play_wav(b"wav")
            validate.assert_called_once_with(b"wav")
            run.assert_called_once_with(
                ["aplay", "-q", "-D", HDMI_ALSA_DEVICE, "-"],
                input=b"wav",
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=125,
                check=True,
            )


if __name__ == "__main__":
    unittest.main()
