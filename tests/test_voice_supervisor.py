import unittest
from unittest.mock import patch

from tools.sentry_voice_supervisor import reconcile_once


class VoiceSupervisorTests(unittest.TestCase):
    @patch("tools.sentry_voice_supervisor.AnimaConfig.load")
    @patch("tools.sentry_voice_supervisor._systemctl")
    def test_sleep_restarts_active_voice_so_it_publishes_sleeping(self, systemctl, load):
        load.return_value = _Config({"sleep_enabled": True})
        systemctl.return_value.returncode = 0
        with patch("tools.sentry_voice_supervisor.voice_is_active", return_value=True):
            self.assertEqual(reconcile_once(), "sleeping")
        self.assertEqual(systemctl.call_args.args, ("restart", "sentry-voice.service"))

    @patch("tools.sentry_voice_supervisor.AnimaConfig.load")
    @patch("tools.sentry_voice_supervisor._systemctl")
    def test_standby_starts_failed_voice_and_never_reads_local_sleep(self, systemctl, load):
        load.return_value = _Config({"sleep_enabled": False})
        systemctl.return_value.returncode = 0
        with patch("tools.sentry_voice_supervisor.voice_is_active", return_value=False):
            self.assertEqual(reconcile_once(), "starting")
        self.assertEqual(
            [call.args for call in systemctl.call_args_list],
            [("reset-failed", "sentry-voice.service"), ("start", "sentry-voice.service")],
        )

    @patch("tools.sentry_voice_supervisor.AnimaConfig.load", return_value=None)
    @patch("tools.sentry_voice_supervisor._systemctl")
    def test_unavailable_anima_stops_voice_instead_of_guessing_wake_state(self, systemctl, load):
        systemctl.return_value.returncode = 0
        with patch("tools.sentry_voice_supervisor.voice_is_active", return_value=True):
            self.assertEqual(reconcile_once(), "anima_unavailable_stopped")
        self.assertEqual(systemctl.call_args.args, ("stop", "sentry-voice.service"))


class _Config:
    def __init__(self, settings):
        self.settings = settings

    def client(self):
        return _Client(self.settings)


class _Client:
    def __init__(self, settings):
        self.settings = settings

    def voice_settings(self):
        return self.settings
