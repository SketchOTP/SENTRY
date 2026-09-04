import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.sentry_launch import CORE_UNITS, UI_APPLICATION_ID, configured_launch_units, launch


def _result(returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], returncode, "", stderr)


class SentryLauncherTests(unittest.TestCase):
    def _config(self, root: Path, **updates) -> Path:
        payload = {
            "voice": {"always_on_enabled": True, "sleep_enabled": False},
            "resident": {
                "continuous_perception_enabled": False,
                "continuous_proactivity_enabled": False,
            },
            "proactivity": {"enabled": True},
            "weather": {"enabled": True, "latitude": 1.0, "longitude": 2.0},
            "alarms": {"enabled": True},
        }
        for section, values in updates.items():
            payload[section].update(values)
        path = root / "config.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_launch_starts_configured_stack_once_and_activates_existing_ui(self):
        with tempfile.TemporaryDirectory() as directory:
            config = self._config(Path(directory))
            calls = []

            def run(command, **kwargs):
                calls.append((command, kwargs))
                return _result()

            with patch("tools.sentry_launch.shutil.which", return_value="/usr/bin/gapplication"):
                units = launch(config, run=run, sleep=lambda _seconds: None)
            self.assertEqual(
                units,
                (*CORE_UNITS, "sentry-alarms.timer", "sentry-weather.timer", "sentry-voice.service"),
            )
            self.assertEqual(calls[0][0], ["systemctl", "--user", "start", *units])
            self.assertEqual(calls[1][0], ["gapplication", "launch", UI_APPLICATION_ID])

    def test_sleep_preserves_ui_and_support_services_but_does_not_start_voice(self):
        with tempfile.TemporaryDirectory() as directory:
            config = self._config(Path(directory), voice={"sleep_enabled": True})
            units = configured_launch_units(config)
            self.assertIn("sentry-ui.service", units)
            self.assertIn("sentry-state-api.service", units)
            self.assertNotIn("sentry-voice.service", units)

    def test_disabled_optional_services_remain_stopped(self):
        with tempfile.TemporaryDirectory() as directory:
            config = self._config(
                Path(directory),
                voice={"always_on_enabled": False},
                resident={
                    "continuous_perception_enabled": False,
                    "continuous_proactivity_enabled": False,
                },
                weather={"enabled": False},
                alarms={"enabled": False},
            )
            self.assertEqual(configured_launch_units(config), CORE_UNITS)

    def test_explicit_continuous_opt_ins_are_respected(self):
        with tempfile.TemporaryDirectory() as directory:
            config = self._config(
                Path(directory),
                resident={
                    "continuous_perception_enabled": True,
                    "continuous_proactivity_enabled": True,
                },
            )
            units = configured_launch_units(config)
            self.assertIn("sentry-perception.service", units)
            self.assertIn("sentry-proactive.service", units)

    def test_ui_activation_retries_until_application_is_registered(self):
        with tempfile.TemporaryDirectory() as directory:
            config = self._config(Path(directory))
            attempts = 0

            def run(command, **kwargs):
                nonlocal attempts
                if command[0] == "gapplication":
                    attempts += 1
                    return _result(1 if attempts < 3 else 0, "not ready")
                return _result()

            with patch("tools.sentry_launch.shutil.which", return_value="/usr/bin/gapplication"):
                launch(config, run=run, sleep=lambda _seconds: None)
            self.assertEqual(attempts, 3)


if __name__ == "__main__":
    unittest.main()
