import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from perception.alarms import AlarmDispatcher
from perception.presence_store import PresenceStore
from tools.sentry_conversation_tools import ConversationToolHost
from tools.sentry_alarms import _LazyKokoroSpeaker
from tools.sentry_state_api import _Handler


BASE = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


class Speaker:
    def __init__(self, delivered=True):
        self.delivered = delivered
        self.messages = []

    def speak(self, text):
        self.messages.append(text)
        return self.delivered


class AlarmTests(unittest.TestCase):
    def test_idle_alarm_speaker_is_lazy(self):
        speaker = _LazyKokoroSpeaker(python_executable=None, voice="bm_george", speed=0.9)
        self.assertIsNone(speaker._speaker)

    def test_schema9_create_list_idempotence_cancel_and_validation(self):
        with tempfile.TemporaryDirectory() as directory, PresenceStore(Path(directory) / "sentry.db") as store:
            self.assertEqual(store.health()["schema_version"], 9)
            alarm = store.create_alarm(
                scheduled_for=BASE + timedelta(hours=1), display_timezone="America/New_York",
                label="Morning alarm", source_surface="test", source_request_id="a1", created_at=BASE,
            )
            duplicate = store.create_alarm(
                scheduled_for=BASE + timedelta(hours=2), display_timezone="America/New_York",
                label="Different label", source_surface="test", source_request_id="a1", created_at=BASE,
            )
            self.assertEqual(duplicate["alarm_id"], alarm["alarm_id"])
            self.assertEqual(store.alarms(status="pending")[0]["label"], "Morning alarm")
            cancelled = store.cancel_alarm(alarm["alarm_id"], source_surface="test", source_request_id="cancel-a1", cancelled_at=BASE)
            self.assertEqual(cancelled["status"], "cancelled")
            with self.assertRaises(ValueError):
                store.create_alarm(
                    scheduled_for=BASE, display_timezone="America/New_York", label="past",
                    source_surface="test", source_request_id="past", created_at=BASE,
                )
            with self.assertRaises(ValueError):
                store.create_alarm(
                    scheduled_for=BASE + timedelta(hours=1), display_timezone="not/a-zone", label="bad zone",
                    source_surface="test", source_request_id="zone", created_at=BASE,
                )

    def test_due_alarm_is_claimed_before_speech_and_finalized_once(self):
        with tempfile.TemporaryDirectory() as directory, PresenceStore(Path(directory) / "sentry.db") as store:
            alarm = store.create_alarm(
                scheduled_for=BASE + timedelta(minutes=1), display_timezone="America/New_York",
                label="Start the day", source_surface="test", source_request_id="a1", created_at=BASE,
            )
            speaker = Speaker()
            dispatcher = AlarmDispatcher(store, speaker=speaker)
            self.assertEqual(dispatcher.process_due(now=BASE + timedelta(seconds=59)), [])
            outcomes = dispatcher.process_due(now=BASE + timedelta(minutes=1))
            self.assertEqual([item.status for item in outcomes], ["delivered"])
            self.assertEqual(speaker.messages, ["Alarm. Start the day."])
            self.assertEqual(store.alarm(alarm["alarm_id"])["status"], "delivered")
            self.assertEqual(dispatcher.process_due(now=BASE + timedelta(minutes=2)), [])

    def test_delivery_failure_and_uncertain_restart_never_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sentry.db"
            with PresenceStore(path) as store:
                failed = store.create_alarm(
                    scheduled_for=BASE + timedelta(minutes=1), display_timezone="America/New_York",
                    label="Fail", source_surface="test", source_request_id="fail", created_at=BASE,
                )
                AlarmDispatcher(store, speaker=Speaker(False)).process_due(now=BASE + timedelta(minutes=1))
                self.assertEqual(store.alarm(failed["alarm_id"])["status"], "failed")
                claimed = store.create_alarm(
                    scheduled_for=BASE + timedelta(minutes=2), display_timezone="America/New_York",
                    label="Crash", source_surface="test", source_request_id="crash", created_at=BASE,
                )
                self.assertEqual(len(store.claim_due_alarms(now=BASE + timedelta(minutes=2))), 1)
            with PresenceStore(path) as reopened:
                record = reopened.alarm(claimed["alarm_id"])
                self.assertEqual(record["status"], "failed")
                self.assertEqual(record["failure_reason"], "unknown_delivery_after_restart")
                self.assertEqual(AlarmDispatcher(reopened, speaker=Speaker()).process_due(now=BASE + timedelta(minutes=3)), [])

    def test_api_and_conversation_tools_create_query_cancel(self):
        with tempfile.TemporaryDirectory() as directory, PresenceStore(Path(directory) / "sentry.db") as store:
            server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
            server.store = store
            server.display_timezone = "America/New_York"
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host = ConversationToolHost(
                    base_url=f"http://127.0.0.1:{server.server_port}", source_surface="test", source_request_id="alarm-tool",
                )
                created = host.execute("create_one_shot_alarm", {
                    "scheduled_for": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                    "display_timezone": "America/New_York", "label": "Wake up",
                })
                self.assertEqual(created["status"], "succeeded")
                self.assertIn("at", created["result"]["scheduled_for_local_display"])
                listed = host.execute("get_alarms", {"status": "pending"})
                self.assertEqual(listed["facts"][0]["data"]["alarms"][0]["label"], "Wake up")
                self.assertIn("scheduled_for_local_display", listed["facts"][0]["data"]["alarms"][0])
                alarm_id = created["result"]["alarm_id"]
                cancelled = host.execute("cancel_alarm", {"alarm_id": alarm_id})
                self.assertEqual(cancelled["status"], "succeeded")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_atlas_restore_preserves_alarm_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local, atlas = root / "local" / "sentry.db", root / "atlas" / "sentry.db"
            with PresenceStore(local, atlas_mirror_path=atlas) as store:
                alarm = store.create_alarm(
                    scheduled_for=BASE + timedelta(days=1), display_timezone="America/New_York",
                    label="Restore", source_surface="test", source_request_id="restore", created_at=BASE,
                )
            local.unlink()
            with PresenceStore(local, atlas_mirror_path=atlas) as restored:
                self.assertEqual(restored.alarm(alarm["alarm_id"])["status"], "pending")


if __name__ == "__main__":
    unittest.main()
