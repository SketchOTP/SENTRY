import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from unittest.mock import patch

from perception.presence_store import PREFERENCE_KEY, PresenceStore
from perception.proactive import ProactivePolicyConfig, ProactiveProcessor
from tools.sentry_ask import ask
from tools.sentry_preference_intent import PreferenceIntent, select_preference_intent
from tools.sentry_state_api import _Handler


BASE = datetime(2026, 8, 30, 15, 0, tzinfo=timezone.utc)


def make_action(store: PresenceStore, *, action_id: str = "action-1", event_id: str = "event-1", delivered: bool = True) -> None:
    store.claim_proactive_action(
        action_id=action_id, source_event_id=event_id, candidate_key="primary_user:session:1",
        event_type="person.identified", person_id="primary_user", session_id=None,
        event_timestamp=BASE.isoformat(), evaluated_at=BASE.isoformat(),
        eligibility_result="eligible", suppression_reason=None,
    )
    if delivered:
        store.update_proactive_action(action_id, judge_invoked=True, judge_model="gpt-5.6-luna", judge_effort="low",
                                      judge_decision="speak", cited_fact_ids=["current-room-state"],
                                      utterance="Welcome.", delivery_status="delivered", delivered_at=(BASE + timedelta(seconds=1)).isoformat())


class PreferenceMemoryTests(unittest.TestCase):
    def test_schema_six_migration_and_default_value(self):
        with tempfile.TemporaryDirectory() as directory:
            with PresenceStore(Path(directory) / "sentry.db") as store:
                self.assertEqual(store.health()["schema_version"], 7)
                self.assertEqual(store.preference_value(), "default")
                self.assertEqual({row[1] for row in store._connection.execute("PRAGMA table_info(preference_events)")} >= {
                    "preference_event_id", "preference_key", "operation", "value_json", "source_request_id"
                }, True)

    def test_set_clear_allow_and_idempotence_are_auditable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sentry.db"
            with PresenceStore(path) as store:
                suppressed = store.record_preference(operation="set", value="suppress", source_surface="test", source_request_id="r1", created_at=BASE)
                repeated = store.record_preference(operation="set", value="suppress", source_surface="test", source_request_id="r1", created_at=BASE + timedelta(seconds=1))
                self.assertEqual(suppressed["preference_event_id"], repeated["preference_event_id"])
                self.assertEqual(store.preference_value(), "suppress")
                allowed = store.record_preference(operation="set", value="allow", source_surface="test", source_request_id="r2", created_at=BASE + timedelta(seconds=2))
                self.assertEqual(store.preference_value(), "allow")
                cleared = store.record_preference(operation="clear", source_surface="test", source_request_id="r3", created_at=BASE + timedelta(seconds=3))
                self.assertEqual(store.preference_value(), "default")
                self.assertEqual(len(store.preference_events()), 3)
                self.assertEqual(cleared["supersedes_event_id"], allowed["preference_event_id"])
            with PresenceStore(path) as reopened:
                self.assertEqual(reopened.preference_value(), "default")
                self.assertEqual(len(reopened.preference_events()), 3)

    def test_feedback_matrix_and_do_not_repeat_creates_only_supported_preference(self):
        with tempfile.TemporaryDirectory() as directory:
            with PresenceStore(Path(directory) / "sentry.db") as store:
                make_action(store)
                helpful = store.record_proactive_feedback(action_id="action-1", feedback_type="helpful", source_surface="test", source_request_id="f1")
                not_helpful = store.record_proactive_feedback(action_id="action-1", feedback_type="not_helpful", source_surface="test", source_request_id="f2")
                too_frequent = store.record_proactive_feedback(action_id="action-1", feedback_type="too_frequent", source_surface="test", source_request_id="f3")
                self.assertIsNone(helpful["resulting_preference_event_id"])
                self.assertIsNone(not_helpful["resulting_preference_event_id"])
                self.assertIsNone(too_frequent["resulting_preference_event_id"])
                self.assertEqual(store.preference_value(), "default")
                repeat = store.record_proactive_feedback(action_id="action-1", feedback_type="do_not_repeat", source_surface="test", source_request_id="f4")
                duplicate = store.record_proactive_feedback(action_id="action-1", feedback_type="do_not_repeat", source_surface="test", source_request_id="f4")
                self.assertEqual(repeat["feedback_id"], duplicate["feedback_id"])
                self.assertEqual(store.preference_value(), "suppress")
                self.assertEqual(len(store.proactive_feedback()), 4)
                with self.assertRaises(ValueError):
                    store.record_proactive_feedback(action_id="missing", feedback_type="helpful", source_surface="test", source_request_id="bad")

    def test_recent_action_requires_one_unambiguous_delivered_action(self):
        with tempfile.TemporaryDirectory() as directory:
            with PresenceStore(Path(directory) / "sentry.db") as store:
                make_action(store)
                self.assertIsNotNone(store.recent_delivered_proactive_action(now=BASE + timedelta(seconds=10)))
                make_action(store, action_id="action-2", event_id="event-2")
                self.assertIsNone(store.recent_delivered_proactive_action(now=BASE + timedelta(seconds=10)))
                self.assertIsNone(store.recent_delivered_proactive_action(now=BASE + timedelta(minutes=11)))

    def test_atlas_restore_preserves_preference_and_feedback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local, atlas = root / "local" / "sentry.db", root / "atlas" / "sentry.db"
            with PresenceStore(local, atlas_mirror_path=atlas) as store:
                make_action(store)
                store.record_preference(operation="set", value="suppress", source_surface="test", source_request_id="p1")
                store.record_proactive_feedback(action_id="action-1", feedback_type="do_not_repeat", source_surface="test", source_request_id="f1")
            local.unlink()
            with PresenceStore(local, atlas_mirror_path=atlas) as restored:
                self.assertEqual(restored.health()["schema_version"], 7)
                self.assertEqual(restored.preference_value(), "suppress")
                self.assertEqual(len(restored.proactive_feedback()), 1)

    def test_preference_suppression_happens_before_luna(self):
        with tempfile.TemporaryDirectory() as directory:
            with PresenceStore(Path(directory) / "sentry.db") as store:
                store.record_observation({"room_state": "empty", "captured_at": BASE.isoformat(), "camera_state": "online", "people": []})
                store.record_observation({"room_state": "occupied", "captured_at": (BASE + timedelta(seconds=2)).isoformat(), "camera_state": "online", "people": [{"track_id": 1, "person_id": "primary_user", "identity_state": "recognized", "visible": True}], "room_state_transition": "empty->occupied", "detector_evidence": True, "max_person_confidence": 0.9})
                event = next(item for item in store.events() if item["event_type"] == "person.identified")
                store.record_preference(operation="set", value="suppress", source_surface="test", source_request_id="p1")
                calls = []
                processor = ProactiveProcessor(
                    store,
                    ProactivePolicyConfig.from_mapping({"enabled": True, "startup_suppression_seconds": 0}),
                    judge=lambda *a, **k: calls.append(1),
                    started_at=BASE,
                )
                result = processor.process_event(event, now=BASE + timedelta(seconds=3))
                self.assertEqual(result.suppression_reason, "user_preference")
                self.assertEqual(calls, [])
                action = store.proactive_action_for_event(event["event_id"])
                self.assertEqual(action["suppression_reason"], "user_preference")
                self.assertFalse(action["judge_invoked"])

    def test_intents_cover_supported_commands_feedback_and_refuse_general_memory(self):
        self.assertEqual(select_preference_intent("Don't greet me when I come in."), PreferenceIntent("write", "set", "suppress"))
        self.assertEqual(select_preference_intent("You can greet me when I come in again."), PreferenceIntent("write", "set", "allow"))
        self.assertEqual(select_preference_intent("Forget my greeting preference."), PreferenceIntent("write", "clear"))
        self.assertEqual(select_preference_intent("That was helpful."), PreferenceIntent("feedback", feedback_type="helpful"))
        self.assertEqual(select_preference_intent("Don't do that again."), PreferenceIntent("feedback", feedback_type="do_not_repeat"))
        self.assertEqual(select_preference_intent("Remember that I like blue."), PreferenceIntent("unsupported_memory"))

    def test_ask_refuses_arbitrary_memory_without_luna_or_api_write(self):
        with patch("tools.sentry_ask.invoke_grounded_query") as invoke:
            result = ask("Remember that I like blue.")
        invoke.assert_not_called()
        self.assertEqual(result["luna_invocations"], 0)
        self.assertIn("don't support", result["answer"])

    def test_ask_preference_write_and_recall_are_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            with PresenceStore(Path(directory) / "sentry.db") as store:
                server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
                server.store = store
                thread = Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    base_url = f"http://127.0.0.1:{server.server_port}"
                    saved = ask("Don't greet me when I come in.", base_url=base_url)
                    self.assertEqual(saved["grounding"], "supported")
                    self.assertEqual(saved["luna_invocations"], 0)
                    self.assertEqual(store.preference_value(), "suppress")
                    recalled = ask("Do I have arrival greetings disabled?", base_url=base_url)
                    self.assertEqual(recalled["grounding"], "supported")
                    self.assertEqual(recalled["luna_invocations"], 0)
                    self.assertIn("disabled", recalled["answer"])
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=3)

    def test_preference_api_is_local_metadata_only_and_validates_enums(self):
        with tempfile.TemporaryDirectory() as directory:
            with PresenceStore(Path(directory) / "sentry.db") as store:
                server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
                server.store = store
                thread = Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
                    body = json.dumps({"operation": "set", "value": "suppress", "source_surface": "test", "source_request_id": "api-1"})
                    connection.request("POST", "/v1/preferences", body, {"Content-Type": "application/json"})
                    response = connection.getresponse()
                    payload = json.loads(response.read())
                    self.assertEqual(response.status, 200)
                    self.assertEqual(payload["current_value"], "suppress")
                    self.assertNotIn("prototype", json.dumps(payload))
                    connection.request("GET", "/v1/preferences?history=1")
                    response = connection.getresponse()
                    self.assertEqual(json.loads(response.read())["current_value"], "suppress")
                    bad = json.dumps({"operation": "set", "value": "anything", "source_request_id": "bad"})
                    connection.request("POST", "/v1/preferences", bad, {"Content-Type": "application/json"})
                    self.assertEqual(connection.getresponse().status, 400)
                    connection.close()
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
