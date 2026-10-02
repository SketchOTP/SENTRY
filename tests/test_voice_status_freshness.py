import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from perception.voice_status import fresh_status, read_runtime_voice
from tools.sentry_projection_status import bounded_status
from tools.sentry_voice_supervisor import publish_desired_status


class VoiceStatusFreshnessTests(unittest.TestCase):
    def test_stale_missing_naive_future_and_invalid_metadata_fail_closed(self):
        now = datetime.now(timezone.utc)
        for stamp in (None, "bad", now.replace(tzinfo=None).isoformat(),
                      (now - timedelta(seconds=61)).isoformat(),
                      (now + timedelta(seconds=20)).isoformat()):
            payload = fresh_status({"state": "SLEEPING", "sleep_enabled": True,
                                    "speaker_context_display_name": "old", "updated_at": stamp}, now=now)
            self.assertEqual(payload["state"], "UNAVAILABLE")
            self.assertNotIn("sleep_enabled", payload)
            self.assertNotIn("speaker_context_display_name", payload)
        self.assertEqual(fresh_status([])["state"], "UNAVAILABLE")

    def test_fresh_observation_preserved_and_intent_separate(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "voice.json"
            path.write_text(json.dumps({"state": "SLEEPING", "sleep_enabled": True,
                                       "updated_at": "2020-01-01T00:00:00+00:00"}))
            publish_desired_status({"status": "CURRENT", "desired_sleep_enabled": False,
                                    "desired_instance_id": "office"}, path.with_name("voice-supervisor.json"))
            payload = read_runtime_voice(path)
            self.assertEqual(payload["state"], "UNAVAILABLE")
            self.assertFalse(payload["desired_sleep_enabled"])
            self.assertEqual(payload["desired_instance_id"], "office")
            self.assertEqual(bounded_status(path), payload)
            path.write_text(json.dumps({"state": "LISTENING", "private": "omit",
                                       "updated_at": datetime.now(timezone.utc).isoformat()}))
            self.assertEqual(read_runtime_voice(path)["state"], "LISTENING")
            self.assertNotIn("private", bounded_status(path))
