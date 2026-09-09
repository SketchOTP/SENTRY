import json
import unittest
from unittest.mock import patch

from tools.sentry_voice_supervisor import _desired_signature, _runtime_signature, reconcile_once


class VoiceSupervisorTests(unittest.TestCase):
    @patch("tools.sentry_voice_supervisor.AnimaConfig.load")
    @patch("tools.sentry_voice_supervisor.reconcile_visible_face", return_value="face_ready")
    @patch("tools.sentry_voice_supervisor._systemctl")
    def test_sleep_restarts_active_voice_so_it_publishes_sleeping(self, systemctl, face, load):
        load.return_value = _Config(_settings(sleep_enabled=True))
        systemctl.return_value.returncode = 0
        with patch("tools.sentry_voice_supervisor.voice_is_active", return_value=True):
            self.assertEqual(reconcile_once(), "sleeping")
        self.assertEqual(systemctl.call_args.args, ("restart", "sentry-voice.service"))

    @patch("tools.sentry_voice_supervisor.AnimaConfig.load")
    @patch("tools.sentry_voice_supervisor.reconcile_visible_face", return_value="face_ready")
    @patch("tools.sentry_voice_supervisor._systemctl")
    def test_standby_starts_failed_voice_and_never_reads_local_sleep(self, systemctl, face, load):
        load.return_value = _Config(_settings())
        systemctl.return_value.returncode = 0
        with patch("tools.sentry_voice_supervisor.voice_is_active", return_value=False):
            self.assertEqual(reconcile_once(), "starting")
        self.assertEqual(
            [call.args for call in systemctl.call_args_list],
            [("reset-failed", "sentry-voice.service"), ("start", "sentry-voice.service")],
        )

    @patch(
        "tools.sentry_voice_supervisor._runtime_signature",
        return_value=("living_room", "bm_george", 0.9),
    )
    @patch("tools.sentry_voice_supervisor.AnimaConfig.load")
    @patch("tools.sentry_voice_supervisor.reconcile_visible_face", return_value="office_ui_started")
    @patch("tools.sentry_voice_supervisor._systemctl")
    def test_active_instance_change_restarts_only_voice_edge(
        self, systemctl, face, load, runtime
    ):
        load.return_value = _Config(_settings(active_instance_id="office"))
        systemctl.return_value.returncode = 0
        with patch("tools.sentry_voice_supervisor.voice_is_active", return_value=True):
            self.assertEqual(reconcile_once(), "switching_instance")
        self.assertEqual(systemctl.call_args.args, ("restart", "sentry-voice.service"))

    def test_voice_signature_is_bounded_and_reads_ephemeral_status(self):
        self.assertEqual(_desired_signature(_settings()), ("living_room", "bm_george", 0.9))
        with patch("tools.sentry_voice_supervisor._voice_status_path") as path:
            path.return_value.read_text.return_value = json.dumps(
                {
                    "active_instance_id": "office",
                    "voice_id": "bm_lewis",
                    "speech_speed": 1.0,
                }
            )
            self.assertEqual(_runtime_signature(), ("office", "bm_lewis", 1.0))

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


def _settings(**changes):
    value = {
        "sleep_enabled": False,
        "active_instance_id": "living_room",
        "voice_id": "bm_george",
        "speech_speed": 0.9,
    }
    value.update(changes)
    return value
