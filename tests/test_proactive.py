import json
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from perception.presence_store import PresenceStore
from perception.proactive import (
    ProactivePolicyConfig,
    ProactiveProcessor,
    SpeechDispatcher,
    validate_proactive_judgment,
)
from tools.sentry_grounding import build_proactive_fact_packet


BASE = datetime(2026, 8, 29, 20, 0, tzinfo=timezone.utc)


def observed(store: PresenceStore, state: str, timestamp: datetime, transition: str | None = None, *, person: bool = False) -> None:
    people = []
    if person:
        people = [{
            "track_id": 4,
            "visible": True,
            "person_id": "primary_user",
            "identity_state": "recognized",
            "identity_confidence": 0.91,
        }]
    store.record_observation({
        "room_state": state,
        "captured_at": timestamp.isoformat(),
        "camera_state": "online" if state in {"empty", "occupied"} else state,
        "room_state_transition": transition,
        "frame_sequence": int(timestamp.timestamp()),
        "people": people,
        "detector_evidence": person,
        "max_person_confidence": 0.91 if person else None,
    })


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


def judge_response(packet, **kwargs):
    return {
        "ok": True,
        "model": "gpt-5.6-luna",
        "reasoning_effort": kwargs["effort"],
        "usage": {},
        "result": {
            "decision": "speak",
            "message": "Welcome back, Sketch.",
            "fact_ids": ["proactive-candidate", "current-room-state"],
            "reason_code": "useful_return_acknowledgement",
        },
    }


def make_store(path: Path) -> tuple[PresenceStore, dict]:
    store = PresenceStore(path)
    observed(store, "empty", BASE)
    observed(store, "occupied", BASE + timedelta(seconds=2), "empty->occupied", person=True)
    event = next(item for item in store.events() if item["event_type"] == "person.identified")
    return store, event


class ProactivePolicyTests(unittest.TestCase):
    def config(self, **overrides):
        values = {
            "enabled": True,
            "event_ttl_seconds": 30,
            "same_session_max_actions": 1,
            "person_cooldown_minutes": 30,
            "global_max_spoken_actions_per_hour": 2,
            "startup_suppression_seconds": 0,
        }
        values.update(overrides)
        return ProactivePolicyConfig.from_mapping(values)

    def test_schema_four_migrates_and_action_log_is_metadata_only(self):
        with tempfile.TemporaryDirectory() as directory:
            with PresenceStore(Path(directory) / "sentry.db") as store:
                self.assertEqual(store.health()["schema_version"], 4)
                columns = {row[1] for row in store._connection.execute("PRAGMA table_info(proactive_actions)")}
                self.assertIn("suppression_reason", columns)

    def test_deterministic_suppressions_use_zero_luna_calls(self):
        cases = (
            ("disabled", {"enabled": False}),
            ("unsupported_event", {"event_type": "room.became_occupied"}),
            ("non_primary", {"person_id": "unknown"}),
            ("stale", {"occurred_at": BASE - timedelta(minutes=2)}),
            ("room_not_occupied", {"state": "empty"}),
            ("restart_reconciled", {"restart_reconciled": True}),
        )
        for reason, changes in cases:
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as directory:
                store, event = make_store(Path(directory) / "sentry.db")
                try:
                    if changes.get("state") == "empty":
                        observed(store, "empty", BASE + timedelta(seconds=3), "occupied->empty")
                    event = dict(event)
                    event["event_type"] = changes.get("event_type", event["event_type"])
                    event["occurred_at"] = changes.get("occurred_at", event["occurred_at"]).isoformat() if isinstance(changes.get("occurred_at"), datetime) else event["occurred_at"]
                    event["payload"] = dict(event["payload"])
                    event["payload"]["person_id"] = changes.get("person_id", event["payload"].get("person_id"))
                    if changes.get("restart_reconciled"):
                        event["payload"]["recovered_after_restart"] = True
                    speech = FakeSpeech()
                    calls = []
                    processor = ProactiveProcessor(store, self.config(**changes), judge=lambda *a, **k: calls.append(1), speech=speech, started_at=BASE)
                    result = processor.process_event(event, now=BASE + timedelta(seconds=3))
                    self.assertEqual(result.suppression_reason, reason)
                    self.assertEqual(calls, [])
                    self.assertEqual(speech.calls, [])
                finally:
                    store.close()

    def test_eligible_candidate_invokes_one_luna_turn_and_delivers_once(self):
        with tempfile.TemporaryDirectory() as directory:
            store, event = make_store(Path(directory) / "sentry.db")
            speech = FakeSpeech()
            calls = []
            processor = ProactiveProcessor(store, self.config(), judge=lambda *a, **k: (calls.append(1) or judge_response(*a, **k)), speech=speech, started_at=BASE)
            result = processor.process_event(event, now=BASE + timedelta(seconds=3))
            duplicate = processor.process_event(event, now=BASE + timedelta(seconds=4))
            self.assertEqual(len(calls), 1)
            self.assertEqual(speech.calls, ["Welcome back, Sketch."])
            self.assertEqual(result.delivery_status, "delivered")
            self.assertEqual(duplicate.suppression_reason, "duplicate")
            self.assertEqual(store.proactive_actions()[0]["delivery_status"], "delivered")
            store.close()

    def test_same_session_reacquisition_suppressed_without_luna(self):
        with tempfile.TemporaryDirectory() as directory:
            store, first = make_store(Path(directory) / "sentry.db")
            second = dict(first, event_id="second-event")
            speech = FakeSpeech()
            calls = []
            processor = ProactiveProcessor(store, self.config(), judge=lambda *a, **k: (calls.append(1) or judge_response(*a, **k)), speech=speech, started_at=BASE)
            processor.process_event(first, now=BASE + timedelta(seconds=3))
            result = processor.process_event(second, now=BASE + timedelta(seconds=4))
            self.assertEqual(result.suppression_reason, "already_handled_session")
            self.assertEqual(len(calls), 1)
            self.assertEqual(len(speech.calls), 1)
            store.close()

    def test_cooldown_and_hourly_budget_are_persisted_suppressions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sentry.db"
            store, first = make_store(path)
            speech = FakeSpeech()
            processor = ProactiveProcessor(store, self.config(), judge=lambda *a, **k: judge_response(*a, **k), speech=speech, started_at=BASE)
            processor.process_event(first, now=BASE + timedelta(seconds=3))
            observed(store, "empty", BASE + timedelta(seconds=5), "occupied->empty")
            observed(store, "occupied", BASE + timedelta(seconds=10), "empty->occupied", person=True)
            second = next(item for item in store.events() if item["event_type"] == "person.identified" and item["event_id"] != first["event_id"])
            self.assertEqual(processor.process_event(second, now=BASE + timedelta(seconds=11)).suppression_reason, "cooldown")
            store.close()

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sentry.db"
            store, first = make_store(path)
            speech = FakeSpeech()
            processor = ProactiveProcessor(
                store,
                self.config(person_cooldown_minutes=0, global_max_spoken_actions_per_hour=1),
                judge=judge_response,
                speech=speech,
                started_at=BASE,
            )
            processor.process_event(first, now=BASE + timedelta(seconds=3))
            observed(store, "empty", BASE + timedelta(seconds=5), "occupied->empty")
            observed(store, "occupied", BASE + timedelta(seconds=10), "empty->occupied", person=True)
            second = next(item for item in store.events() if item["event_type"] == "person.identified" and item["event_id"] != first["event_id"])
            self.assertEqual(processor.process_event(second, now=BASE + timedelta(seconds=11)).suppression_reason, "hourly_budget")
            store.close()

    def test_speech_busy_suppresses_without_invoking_luna(self):
        with tempfile.TemporaryDirectory() as directory:
            store, event = make_store(Path(directory) / "sentry.db")
            speech = FakeSpeech()
            speech.busy = True
            calls = []
            result = ProactiveProcessor(store, self.config(), judge=lambda *a, **k: calls.append(1), speech=speech, started_at=BASE).process_event(event, now=BASE + timedelta(seconds=3))
            self.assertEqual(result.suppression_reason, "speech_busy")
            self.assertEqual(calls, [])
            self.assertEqual(speech.calls, [])
            store.close()

    def test_judge_silent_and_invalid_fail_closed_without_speech(self):
        with tempfile.TemporaryDirectory() as directory:
            store, event = make_store(Path(directory) / "sentry.db")
            speech = FakeSpeech()
            silent = lambda packet, **kwargs: {"ok": True, "result": {"decision": "silent", "message": None, "fact_ids": ["proactive-candidate"], "reason_code": "nothing_useful_to_add"}}
            result = ProactiveProcessor(store, self.config(), judge=silent, speech=speech, started_at=BASE).process_event(event, now=BASE + timedelta(seconds=3))
            self.assertEqual(result.suppression_reason, "judge_silent")
            self.assertEqual(speech.calls, [])
            store.close()

        with tempfile.TemporaryDirectory() as directory:
            store, event = make_store(Path(directory) / "sentry.db")
            speech = FakeSpeech()
            invalid = lambda packet, **kwargs: {"ok": True, "result": {"decision": "speak", "message": "unsupported", "fact_ids": ["not-a-fact"], "reason_code": "bad"}}
            result = ProactiveProcessor(store, self.config(), judge=invalid, speech=speech, started_at=BASE).process_event(event, now=BASE + timedelta(seconds=3))
            self.assertEqual(result.suppression_reason, "judge_invalid")
            self.assertEqual(speech.calls, [])
            store.close()

    def test_restart_does_not_redeliver_and_fact_packet_excludes_biometrics(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sentry.db"
            store, event = make_store(path)
            processor = ProactiveProcessor(store, self.config(), judge=judge_response, speech=FakeSpeech(), started_at=BASE)
            processor.process_event(event, now=BASE + timedelta(seconds=3))
            packet = build_proactive_fact_packet(store, event, {"candidate_key": "primary_user:session:1", "hourly_spoken_count": 1, "hourly_spoken_limit": 2, "same_session_action_count": 1, "same_session_action_limit": 1}, as_of=(BASE + timedelta(seconds=3)).isoformat())
            encoded = json.dumps(packet)
            self.assertNotIn("prototype", encoded)
            self.assertNotIn("embedding", encoded)
            store.close()
            reopened = PresenceStore(path)
            speech = FakeSpeech()
            result = ProactiveProcessor(reopened, self.config(), judge=lambda *a, **k: self.fail("restart must not call Luna"), speech=speech, started_at=BASE).process_event(event, now=BASE + timedelta(seconds=4))
            self.assertEqual(result.suppression_reason, "duplicate")
            self.assertEqual(speech.calls, [])
            reopened.close()

    def test_action_log_survives_atlas_snapshot_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local = root / "local" / "sentry.db"
            atlas = root / "atlas" / "sentry.db"
            with PresenceStore(local, atlas_mirror_path=atlas) as store:
                observed(store, "empty", BASE)
                observed(store, "occupied", BASE + timedelta(seconds=2), "empty->occupied", person=True)
                event = next(item for item in store.events() if item["event_type"] == "person.identified")
                processor = ProactiveProcessor(store, self.config(), judge=lambda *a, **k: {"ok": True, "result": {"decision": "silent", "message": None, "fact_ids": ["proactive-candidate"], "reason_code": "nothing_useful_to_add"}}, speech=FakeSpeech(), started_at=BASE)
                processor.process_event(event, now=BASE + timedelta(seconds=3))
            local.unlink()
            with PresenceStore(local, atlas_mirror_path=atlas) as restored:
                self.assertTrue(restored.recovery_info["recovered"])
                self.assertEqual(len(restored.proactive_actions()), 1)
                self.assertEqual(restored.proactive_actions()[0]["suppression_reason"], "judge_silent")

    def test_delivery_failure_is_persisted_and_does_not_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            store, event = make_store(Path(directory) / "sentry.db")
            speech = FakeSpeech(result=False)
            processor = ProactiveProcessor(store, self.config(), judge=judge_response, speech=speech, started_at=BASE)
            result = processor.process_event(event, now=BASE + timedelta(seconds=3))
            self.assertEqual(result.suppression_reason, "delivery_failed")
            self.assertEqual(store.proactive_actions()[0]["delivery_status"], "failed")
            self.assertEqual(processor.process_event(event, now=BASE + timedelta(seconds=4)).suppression_reason, "duplicate")
            self.assertEqual(len(speech.calls), 1)
            store.close()

    def test_response_validation_enforces_short_grounded_output(self):
        self.assertIsNone(validate_proactive_judgment({"decision": "speak", "message": "Hello.", "fact_ids": ["f1"], "reason_code": "ok"}, {"f1"}))
        self.assertIsNotNone(validate_proactive_judgment({"decision": "silent", "message": "No", "fact_ids": ["f1"], "reason_code": "ok"}, {"f1"}))
        self.assertIsNotNone(validate_proactive_judgment({"decision": "speak", "message": "I detected you.", "fact_ids": ["f1"], "reason_code": "ok"}, {"f1"}))

    def test_speech_dispatcher_cancel_uses_bounded_local_backend(self):
        fake_process = type("Process", (), {"poll": lambda self: None, "wait": lambda self: 0, "terminate": lambda self: None})()
        with patch("perception.proactive.subprocess.Popen", return_value=fake_process) as popen, patch("perception.proactive.subprocess.run") as run:
            dispatcher = SpeechDispatcher("/usr/bin/spd-say")
            thread = threading.Thread(target=lambda: dispatcher.speak("short test"))
            thread.start()
            for _ in range(50):
                if dispatcher.is_speaking:
                    break
                time.sleep(0.001)
            self.assertTrue(dispatcher.cancel())
            thread.join(timeout=1)
            self.assertTrue(run.called)
            self.assertEqual(popen.call_args.args[0][0], "/usr/bin/spd-say")


if __name__ == "__main__":
    unittest.main()
