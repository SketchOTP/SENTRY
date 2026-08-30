import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from unittest.mock import patch

from perception.presence_store import PresenceStore
from perception.proactive import ProactivePolicyConfig, ProactiveProcessor, WeatherContextPolicy
from tools.sentry_ask import ask
from tools.sentry_reminder_intent import ReminderIntent, select_reminder_intent
from tools.sentry_state_api import _Handler


BASE = datetime(2026, 8, 30, 15, 0, tzinfo=timezone.utc)


class FakeSpeech:
    def __init__(self, result: bool = True):
        self.result = result
        self.calls: list[str] = []
        self.busy = False

    @property
    def is_speaking(self):
        return self.busy

    def speak(self, text: str) -> bool:
        self.calls.append(text)
        return self.result


def observe(store: PresenceStore, state: str, timestamp: datetime, *, person: str | None = None,
            transition: str | None = None, camera_state: str | None = None) -> None:
    people = []
    if person:
        people = [{"track_id": 4, "visible": True, "person_id": person, "identity_state": "recognized" if person == "primary_user" else "unknown"}]
    store.record_observation({
        "room_state": state, "captured_at": timestamp.isoformat(),
        "camera_state": camera_state or ("online" if state in {"empty", "occupied"} else state),
        "room_state_transition": transition, "frame_sequence": int(timestamp.timestamp()),
        "people": people, "detector_evidence": bool(person),
        "max_person_confidence": 0.9 if person else None,
    })


def event_for(store: PresenceStore, *, newest: bool = True) -> dict:
    events = [item for item in store.events() if item["event_type"] == "person.identified"]
    return events[0] if newest else events[-1]


def make_session(store: PresenceStore, start: datetime) -> dict:
    observe(store, "empty", start)
    observe(store, "occupied", start + timedelta(seconds=2), person="primary_user", transition="empty->occupied")
    return event_for(store)


def proactive_config(**overrides):
    values = {"enabled": True, "startup_suppression_seconds": 0}
    values.update(overrides)
    return ProactivePolicyConfig.from_mapping(values)


def relevant_weather(store: PresenceStore, at: datetime) -> None:
    store.persist_weather_snapshot({
        "provider": "nws", "location_label": "fixture", "latitude": 38.9, "longitude": -77.0,
        "timezone": "America/New_York", "fetched_at": at.isoformat(),
        "fresh_until": (at + timedelta(minutes=30)).isoformat(), "source_fingerprint": "fixture-weather",
        "current": {}, "hourly": [{"start": at.isoformat(), "end": (at + timedelta(hours=1)).isoformat(),
                                      "precipitation_probability": 80, "short_forecast": "Rain likely"}],
        "alerts": [{"id": "alert-ignored", "event": "Advisory"}],
        "source_metadata": {"provider": "nws", "component_errors": []},
    })


class EventReminderTests(unittest.TestCase):
    def test_schema_eight_migration_and_empty_reminder_state(self):
        with tempfile.TemporaryDirectory() as directory:
            with PresenceStore(Path(directory) / "sentry.db") as store:
                self.assertEqual(store.health()["schema_version"], 8)
                columns = {row[1] for row in store._connection.execute("PRAGMA table_info(event_reminders)")}
                self.assertTrue({"reminder_id", "created_session_id", "delivery_action_id", "failure_reason"} <= columns)
                self.assertEqual(store.event_reminders(), [])

    def test_intent_router_supports_create_query_cancel_and_rejects_scheduler_shapes(self):
        self.assertEqual(select_reminder_intent("Remind me next time I come into the office to call Mom."), ReminderIntent("create", "call Mom"))
        self.assertEqual(select_reminder_intent("Next time I'm in the office, remind me to take the laundry out."), ReminderIntent("create", "take the laundry out"))
        self.assertEqual(select_reminder_intent("Do I have an office reminder?"), ReminderIntent("query"))
        self.assertEqual(select_reminder_intent("Cancel my office reminder."), ReminderIntent("cancel"))
        self.assertEqual(select_reminder_intent("Remind me tomorrow."), ReminderIntent("unsupported"))
        self.assertEqual(select_reminder_intent("Remind me when it rains."), ReminderIntent("unsupported"))
        self.assertIsNone(select_reminder_intent("When did I come in today?"))

    def test_create_during_active_session_records_session_and_rejects_second_pending(self):
        with tempfile.TemporaryDirectory() as directory:
            with PresenceStore(Path(directory) / "sentry.db") as store:
                event = make_session(store, BASE)
                first = store.create_event_reminder(message="call Mom", source_surface="test", source_request_id="r1", created_at=BASE + timedelta(seconds=3))
                repeated = store.create_event_reminder(message="changed text", source_surface="test", source_request_id="r1", created_at=BASE + timedelta(seconds=4))
                self.assertEqual(first["reminder_id"], repeated["reminder_id"])
                self.assertEqual(first["created_session_id"], event["session_id"])
                with self.assertRaises(ValueError):
                    store.create_event_reminder(message="another", source_surface="test", source_request_id="r2", created_at=BASE + timedelta(seconds=5))

    def test_create_empty_room_has_no_created_session_and_cancel_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            with PresenceStore(Path(directory) / "sentry.db") as store:
                observe(store, "empty", BASE)
                reminder = store.create_event_reminder(message="check printer", source_surface="test", source_request_id="r1", created_at=BASE + timedelta(seconds=1))
                self.assertIsNone(reminder["created_session_id"])
                cancelled = store.cancel_event_reminder(reminder["reminder_id"], source_surface="test", source_request_id="c1")
                repeated = store.cancel_event_reminder(reminder["reminder_id"], source_surface="test", source_request_id="c1")
                self.assertEqual(cancelled["status"], "cancelled")
                self.assertEqual(cancelled["reminder_id"], repeated["reminder_id"])

    def test_message_bounds_and_supported_enums_are_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            with PresenceStore(Path(directory) / "sentry.db") as store:
                with self.assertRaises(ValueError):
                    store.create_event_reminder(message="line one\nline two", source_surface="test", source_request_id="r1")
                with self.assertRaises(ValueError):
                    store.create_event_reminder(message="x" * 121, source_surface="test", source_request_id="r2")
                with self.assertRaises(ValueError):
                    store.create_event_reminder(message="x", trigger_kind="tomorrow", source_surface="test", source_request_id="r3")

    def test_same_session_identity_does_not_trigger_and_future_session_delivers_without_luna(self):
        with tempfile.TemporaryDirectory() as directory:
            with PresenceStore(Path(directory) / "sentry.db") as store:
                first = make_session(store, BASE)
                reminder = store.create_event_reminder(message="call Mom", source_surface="test", source_request_id="r1", created_at=BASE + timedelta(seconds=3))
                same_session = dict(first, event_id="reacquired-a", occurred_at=(BASE + timedelta(seconds=4)).isoformat())
                store.record_preference(operation="set", value="suppress", source_surface="test", source_request_id="p1")
                speech = FakeSpeech()
                calls = []
                processor = ProactiveProcessor(store, proactive_config(), judge=lambda *a, **k: calls.append(1), speech=speech, started_at=BASE)
                self.assertEqual(processor.process_event(same_session, now=BASE + timedelta(seconds=5)).suppression_reason, "user_preference")
                self.assertEqual(speech.calls, [])
                observe(store, "empty", BASE + timedelta(seconds=10), transition="occupied->empty")
                second = make_session(store, BASE + timedelta(seconds=20))
                result = processor.process_event(second, now=BASE + timedelta(seconds=23))
                self.assertEqual(result.delivery_status, "delivered")
                self.assertEqual(speech.calls, ["Reminder: call Mom."])
                self.assertEqual(calls, [])
                self.assertEqual(store.event_reminder(reminder["reminder_id"])["status"], "delivered")

    def test_non_primary_stale_restart_and_invalid_events_do_not_deliver(self):
        for change, reason in (("non_primary", "non_primary"), ("stale", "stale"), ("restart", "restart_reconciled")):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                with PresenceStore(Path(directory) / "sentry.db") as store:
                    event = make_session(store, BASE)
                    store.create_event_reminder(message="check printer", source_surface="test", source_request_id="r1", created_at=BASE - timedelta(seconds=1))
                    candidate = dict(event, event_id=f"{change}-event")
                    candidate["payload"] = dict(event["payload"])
                    if change == "non_primary":
                        candidate["payload"]["person_id"] = "unknown"
                    elif change == "stale":
                        candidate["occurred_at"] = (BASE - timedelta(minutes=2)).isoformat()
                    else:
                        candidate["payload"]["recovered_after_restart"] = True
                    speech = FakeSpeech()
                    result = ProactiveProcessor(store, proactive_config(), judge=lambda *a, **k: self.fail("invalid event reached Luna"), speech=speech, started_at=BASE).process_event(candidate, now=BASE + timedelta(seconds=3))
                    self.assertEqual(result.suppression_reason, reason)
                    self.assertEqual(speech.calls, [])
                    self.assertEqual(store.event_reminders()[0]["status"], "pending")

    def test_reminder_out_ranks_preference_cooldown_budget_and_weather(self):
        with tempfile.TemporaryDirectory() as directory:
            with PresenceStore(Path(directory) / "sentry.db") as store:
                observe(store, "empty", BASE)
                reminder = store.create_event_reminder(message="check printer", source_surface="test", source_request_id="r1", created_at=BASE)
                event = make_session(store, BASE + timedelta(minutes=1))
                relevant_weather(store, BASE + timedelta(minutes=1, seconds=2))
                store.record_preference(operation="set", value="suppress", source_surface="test", source_request_id="p1")
                speech = FakeSpeech()
                calls = []
                processor = ProactiveProcessor(store, proactive_config(global_max_spoken_actions_per_hour=0), judge=lambda *a, **k: calls.append(1), speech=speech, started_at=BASE, weather_policy=WeatherContextPolicy(configured=True, location_label="fixture"))
                result = processor.process_event(event, now=BASE + timedelta(minutes=1, seconds=3))
                self.assertEqual(result.delivery_status, "delivered")
                self.assertEqual(speech.calls, ["Reminder: check printer."])
                self.assertEqual(calls, [])
                action = store.proactive_action_for_event(event["event_id"])
                self.assertEqual(action["candidate_key"], f"reminder:{reminder['reminder_id']}:session:{event['session_id']}")

    def test_delivery_failure_is_durable_and_claimed_crash_is_not_replayed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sentry.db"
            with PresenceStore(path) as store:
                observe(store, "empty", BASE)
                reminder = store.create_event_reminder(message="call Mom", source_surface="test", source_request_id="r1", created_at=BASE - timedelta(seconds=1))
                event = make_session(store, BASE + timedelta(seconds=2))
                failed = ProactiveProcessor(store, proactive_config(), speech=FakeSpeech(False), started_at=BASE).process_event(event, now=BASE + timedelta(seconds=7))
                self.assertEqual(failed.delivery_status, "failed")
                self.assertEqual(store.event_reminder(reminder["reminder_id"])["status"], "failed")
            with PresenceStore(path) as store:
                observe(store, "empty", BASE + timedelta(minutes=10), transition="occupied->empty")
                reminder = store.create_event_reminder(message="take laundry out", source_surface="test", source_request_id="r2", created_at=BASE + timedelta(minutes=10, seconds=1))
                observe(store, "occupied", BASE + timedelta(minutes=10, seconds=2), person="primary_user", transition="empty->occupied")
                event = event_for(store)
                claimed = store.claim_event_reminder(reminder_id=reminder["reminder_id"], action_id="claim-action", source_event_id=event["event_id"], session_id=event["session_id"], event_timestamp=event["occurred_at"], evaluated_at=(BASE + timedelta(minutes=10, seconds=3)).isoformat())
                self.assertIsNotNone(claimed)
            with PresenceStore(path) as reopened:
                self.assertEqual(reopened.event_reminder(reminder["reminder_id"])["status"], "failed")
                self.assertEqual(reopened.event_reminder(reminder["reminder_id"])["failure_reason"], "unknown_delivery_after_restart")
                self.assertEqual(reopened.proactive_action_for_event(event["event_id"])["delivery_status"], "failed")

    def test_replay_and_restart_cannot_duplicate_delivery(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sentry.db"
            with PresenceStore(path) as store:
                observe(store, "empty", BASE)
                store.create_event_reminder(message="check printer", source_surface="test", source_request_id="r1", created_at=BASE - timedelta(seconds=1))
                event = make_session(store, BASE + timedelta(seconds=2))
                speech = FakeSpeech()
                processor = ProactiveProcessor(store, proactive_config(), speech=speech, started_at=BASE)
                processor.process_event(event, now=BASE + timedelta(seconds=7))
                processor.process_event(event, now=BASE + timedelta(seconds=8))
                self.assertEqual(speech.calls, ["Reminder: check printer."])
            with PresenceStore(path) as reopened:
                speech = FakeSpeech()
                result = ProactiveProcessor(reopened, proactive_config(), speech=speech, started_at=BASE).process_event(event, now=BASE + timedelta(seconds=5))
                self.assertEqual(result.suppression_reason, "duplicate")
                self.assertEqual(speech.calls, [])

    def test_atlas_restore_preserves_pending_and_delivered_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local, atlas = root / "local" / "sentry.db", root / "atlas" / "sentry.db"
            with PresenceStore(local, atlas_mirror_path=atlas) as store:
                pending = store.create_event_reminder(message="call Mom", source_surface="test", source_request_id="r1", created_at=BASE - timedelta(seconds=1))
            local.unlink()
            with PresenceStore(local, atlas_mirror_path=atlas) as restored:
                self.assertEqual(restored.event_reminder(pending["reminder_id"])["status"], "pending")
                event = make_session(restored, BASE)
                result = ProactiveProcessor(restored, proactive_config(), speech=FakeSpeech(), started_at=BASE).process_event(event, now=BASE + timedelta(seconds=3))
                self.assertEqual(result.delivery_status, "delivered")
            local.unlink()
            with PresenceStore(local, atlas_mirror_path=atlas) as restored:
                self.assertEqual(restored.event_reminder(pending["reminder_id"])["status"], "delivered")

    def test_api_and_ask_create_query_cancel_without_luna(self):
        with tempfile.TemporaryDirectory() as directory, PresenceStore(Path(directory) / "sentry.db") as store:
            server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
            server.store = store
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_port}"
                created = ask("Remind me next time I come into the office to call Mom.", base_url=base_url)
                self.assertEqual(created["luna_invocations"], 0)
                self.assertEqual(store.event_reminders()[0]["message"], "call Mom")
                queried = ask("Do I have an office reminder?", base_url=base_url)
                self.assertEqual(queried["luna_invocations"], 0)
                self.assertIn("call Mom", queried["answer"])
                cancelled = ask("Cancel my office reminder.", base_url=base_url)
                self.assertEqual(cancelled["luna_invocations"], 0)
                self.assertEqual(store.event_reminders()[0]["status"], "cancelled")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_unsupported_reminder_shapes_are_deterministic_and_do_not_call_luna(self):
        with patch("tools.sentry_ask.invoke_grounded_query") as invoke:
            for question in ("Remind me at 5 PM.", "Remind me every Monday.", "Remind me when it rains.", "Remind me when I leave the house."):
                result = ask(question)
                self.assertEqual(result["luna_invocations"], 0)
                self.assertIn("next distinct office session", result["answer"])
        invoke.assert_not_called()

    def test_no_reminder_preserves_contextual_weather_path_and_no_routines(self):
        with tempfile.TemporaryDirectory() as directory:
            with PresenceStore(Path(directory) / "sentry.db") as store:
                event = make_session(store, BASE)
                relevant_weather(store, BASE + timedelta(seconds=2))
                calls = []
                speech = FakeSpeech()
                def judge(packet, **kwargs):
                    calls.append(packet)
                    return {"ok": True, "result": {"decision": "silent", "message": None, "fact_ids": ["weather-context-health", "weather-near-term-precipitation"], "reason_code": "nothing_useful_to_add"}}
                result = ProactiveProcessor(store, proactive_config(), judge=judge, speech=speech, started_at=BASE, weather_policy=WeatherContextPolicy(configured=True, location_label="fixture")).process_event(event, now=BASE + timedelta(seconds=3))
                self.assertEqual(result.judge_decision, "silent")
                self.assertEqual(len(calls), 1)
                packet_text = json.dumps(calls[0])
                self.assertNotIn("routine", packet_text)
                self.assertNotIn("alert-ignored", packet_text)


if __name__ == "__main__":
    unittest.main()
