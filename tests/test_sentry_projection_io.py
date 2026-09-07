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

    def test_hdmi_playback_converts_voice_format_before_aplay(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = self.make_state(Path(tmp))
            state._write_settings("hdmi")
            with patch("tools.sentry_projection_io.validate_wav_payload") as validate, patch(
                "tools.sentry_projection_io.subprocess.run"
            ) as run:
                validate.return_value = (b"pcm", 24_000, 1)
                state.play_wav(b"wav")
            validate.assert_called_once_with(b"wav")
            self.assertEqual(run.call_count, 2)
            run.assert_any_call(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-f",
                    "s16le",
                    "-ar",
                    "24000",
                    "-ac",
                    "1",
                    "-i",
                    "pipe:0",
                    "-f",
                    "s16le",
                    "-ar",
                    "48000",
                    "-ac",
                    "2",
                    "pipe:1",
                ],
                input=b"pcm",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=125,
                check=True,
            )
            run.assert_any_call(
                [
                    "aplay",
                    "-q",
                    "-D",
                    HDMI_ALSA_DEVICE,
                    "-t",
                    "raw",
                    "-f",
                    "S16_LE",
                    "-c",
                    "2",
                    "-r",
                    "48000",
                    "-",
                ],
                input=run.return_value.stdout,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=125,
                check=True,
            )


if __name__ == "__main__":
    unittest.main()
