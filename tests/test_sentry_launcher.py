import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.sentry_launch import (
    CORE_UNITS,
    UI_APPLICATION_ID,
    audio_sink_for_target,
    configured_launch_units,
    display_for_target,
    effective_display_target,
    launch,
)


def _result(
    returncode: int = 0,
    stderr: str = "",
    stdout: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


class SentryLauncherTests(unittest.TestCase):
    def test_identity_wrapper_uses_its_own_directory_and_preserves_arguments(self):
        source = (
            Path(__file__).resolve().parents[1] / "tools/sentry_open_identity_ui.sh"
        ).read_text(encoding="utf-8")
        interpreter = "/home/sketch/.venvs/sentry-ubuntu/bin/python"
        self.assertIn(f"exec {interpreter}", source)
        self.assertNotIn("/srv/ATLAS", source)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tools = root / "relocated checkout" / "tools"
            tools.mkdir(parents=True)
            wrapper = tools / "sentry_open_identity_ui.sh"
            # Use a synthetic sibling launcher, never real services or config.
            wrapper.write_text(
                source.replace(interpreter, json.dumps(sys.executable)),
                encoding="utf-8",
            )
            (tools / "sentry_launch.py").write_text(
                "import json, sys; print(json.dumps(sys.argv))\n", encoding="utf-8"
            )
            result = subprocess.run(
                ["/bin/bash", str(wrapper), "--display-target", "rtx", "two words"],
                cwd=root,
                env={"PATH": "/usr/bin:/bin"},
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
            self.assertEqual(
                json.loads(result.stdout),
                [
                    str(tools / "sentry_launch.py"),
                    "--config",
                    "/home/sketch/.config/sentry/config.json",
                    "--display-target",
                    "rtx",
                    "two words",
                ],
            )

    def test_named_display_targets_resolve_to_independent_x_screens(self):
        self.assertEqual(display_for_target("main", ":1"), ":1.0")
        self.assertEqual(display_for_target("rtx", ":1.0"), ":1.1")
        self.assertEqual(display_for_target("main", ":1.1"), ":1.0")

    def test_audio_target_selects_hdmi_for_rtx_and_analog_for_main(self):
        sinks = (
            "56\talsa_output.pci-0000_0a_00.4.analog-stereo\tPipeWire\n"
            "67\talsa_output.pci-0000_08_00.1.hdmi-stereo\tPipeWire\n"
        )
        self.assertEqual(
            audio_sink_for_target("main", sinks),
            "alsa_output.pci-0000_0a_00.4.analog-stereo",
        )
        self.assertEqual(
            audio_sink_for_target("rtx", sinks),
            "alsa_output.pci-0000_08_00.1.hdmi-stereo",
        )

    def test_gnome_discrete_gpu_launch_context_targets_rtx_screen(self):
        self.assertEqual(
            effective_display_target(None, {"__NV_PRIME_RENDER_OFFLOAD": "1"}),
            "rtx",
        )
        self.assertEqual(effective_display_target(None, {}), None)
        self.assertEqual(
            effective_display_target("main", {"__NV_PRIME_RENDER_OFFLOAD": "1"}),
            "main",
        )

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

    def test_sleep_setting_does_not_remove_voice_from_launch_units(self):
        with tempfile.TemporaryDirectory() as directory:
            config = self._config(Path(directory), voice={"sleep_enabled": True})
            units = configured_launch_units(config)
            self.assertIn("sentry-ui.service", units)
            self.assertIn("sentry-state-api.service", units)
            self.assertIn("sentry-voice.service", units)

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

    def test_rtx_action_restarts_only_ui_on_secondary_screen_and_switches_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self._config(root)
            display_environment = root / "ui-display.env"
            calls = []
            sinks = (
                "56\talsa_output.pci-0000_0a_00.4.analog-stereo\tPipeWire\n"
                "67\talsa_output.pci-0000_08_00.1.hdmi-stereo\tPipeWire\n"
            )

            def run(command, **kwargs):
                calls.append((command, kwargs))
                if command[:4] == ["pactl", "list", "short", "sinks"]:
                    return _result(stdout=sinks)
                return _result()

            with patch("tools.sentry_launch.shutil.which", return_value="/usr/bin/gapplication"):
                units = launch(
                    config,
                    display_target="rtx",
                    run=run,
                    sleep=lambda _seconds: None,
                    environment={
                        "DISPLAY": ":1",
                        "XAUTHORITY": "/run/user/1000/gdm/Xauthority",
                    },
                    display_environment_path=display_environment,
                )

            self.assertIn("sentry-ui.service", units)
            self.assertEqual(
                display_environment.read_text(encoding="utf-8"),
                "DISPLAY=:1.1\nXAUTHORITY=/run/user/1000/gdm/Xauthority\n",
            )
            self.assertEqual(display_environment.stat().st_mode & 0o777, 0o600)
            commands = [command for command, _kwargs in calls]
            self.assertIn(["xdpyinfo", "-display", ":1.1"], commands)
            self.assertIn(
                ["pactl", "set-default-sink", "alsa_output.pci-0000_08_00.1.hdmi-stereo"],
                commands,
            )
            self.assertIn(["systemctl", "--user", "restart", "sentry-ui.service"], commands)
            self.assertFalse(any(command[:2] == ["pactl", "set-default-source"] for command in commands))


if __name__ == "__main__":
    unittest.main()
