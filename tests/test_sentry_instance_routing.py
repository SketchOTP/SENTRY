import unittest

from tools.sentry_always_on_voice import effective_voice_mapping
from tools.sentry_identity_enrollment import IdentityEnrollmentManager
from tools.sentry_ui import projection_instance_payload


class SentryInstanceRoutingTests(unittest.TestCase):
    def setUp(self):
        self.projection = {
            "projection_microphone_url": "http://pi/microphone",
            "projection_playback_url": "http://pi/tts",
            "projection_camera_url": "http://pi/camera",
            "projection_token_file": "/private/token",
            "microphone_source": "office-mic",
        }

    def test_living_room_selects_complete_remote_edge(self):
        value, active = effective_voice_mapping(
            self.projection,
            {"active_instance_id": "living_room", "sleep_enabled": False},
        )
        self.assertEqual(active, "living_room")
        self.assertEqual(value["projection_microphone_url"], "http://pi/microphone")
        self.assertEqual(value["projection_playback_url"], "http://pi/tts")
        self.assertEqual(value["projection_camera_url"], "http://pi/camera")

    def test_office_selects_local_camera_microphone_and_speaker_as_one_edge(self):
        value, active = effective_voice_mapping(
            self.projection,
            {"active_instance_id": "office", "sleep_enabled": False},
        )
        self.assertEqual(active, "office")
        self.assertEqual(value["microphone_source"], "office-mic")
        self.assertFalse(any(key.startswith("projection_") for key in value))

    def test_incomplete_living_room_edge_fails_closed(self):
        incomplete = dict(self.projection)
        incomplete.pop("projection_camera_url")
        with self.assertRaisesRegex(ValueError, "transport is incomplete"):
            effective_voice_mapping(incomplete, {"active_instance_id": "living_room"})

    def test_inactive_pi_projection_does_not_mirror_office_activity(self):
        payload = projection_instance_payload(
            {"state": "SPEAKING", "active_instance_id": "office"}
        )
        self.assertEqual(payload["state"], "INACTIVE")
        self.assertFalse(payload["wake_enabled"])
        self.assertIn("office", payload["reason"])

    def test_face_enrollment_uses_the_current_anima_selected_camera(self):
        manager = IdentityEnrollmentManager.__new__(IdentityEnrollmentManager)
        remote = object()
        manager.remote_camera = remote
        manager.active_instance_provider = lambda: "living_room"
        self.assertIs(manager._remote_camera_for_capture(), remote)
        manager.active_instance_provider = lambda: "office"
        self.assertIsNone(manager._remote_camera_for_capture())


if __name__ == "__main__":
    unittest.main()
