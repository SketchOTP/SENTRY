import unittest
import json
import tempfile
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from unittest.mock import patch

from tools.sentry_ask import ask
from tools.sentry_grounding import build_fact_packet, validate_grounded_response
from tools.sentry_state_api import _Handler
from perception.presence_store import PresenceStore


def api_responses(state="occupied"):
    return {
        "health": {
            "ok": True,
            "db_available": True,
            "schema_version": 3,
            "atlas_mirror": {"status": "ok"},
            "display_timezone": "America/New_York",
            "perception": {
                "status": "fresh",
                "heartbeat_updated_at": "2026-08-29T16:00:00+00:00",
                "age_seconds": 0.0,
                "process_alive": True,
                "camera_state": "online",
                "room_state": state,
                "current_physical_available": True,
                "reason": None,
            },
        },
        "state": {
            "room_id": "office",
            "state": state,
            "camera_state": "online",
            "updated_at": "2026-08-29T16:00:00+00:00",
            "person_count": 1 if state == "occupied" else 0,
            "people": [
                {
                    "track_id": 7,
                    "person_id": "primary_user",
                    "identity_state": "recognized",
                    "identity_confidence": 0.91,
                    "bbox": [1, 2, 3, 4],
                }
            ] if state == "occupied" else [],
        },
        "persons": {
            "persons": [{
                "person_id": "primary_user",
                "display_name": "Sketch",
                "enrollment_status": "active",
                "created_at": "2026-08-29T10:00:00+00:00",
                "updated_at": "2026-08-29T10:00:00+00:00",
            }]
        },
        "sessions": {
            "sessions": [{
                "session_id": 4,
                "room_id": "office",
                "started_at": "2026-08-29T15:00:00+00:00",
                "ended_at": None,
                "status": "open",
                "start_reason": "observed",
                "end_reason": None,
                "recovered_after_restart": 0,
                "end_time_uncertain": 0,
                "secret": "must not pass",
            }]
        },
        "events": {
            "events": [
                {
                    "event_id": "e2",
                    "event_type": "person.identified",
                    "occurred_at": "2026-08-29T15:04:00+00:00",
                    "room_id": "office",
                    "session_id": 4,
                    "source": "sentry_perception",
                    "confidence": 0.91,
                    "schema_version": 3,
                    "payload": {
                        "person_id": "primary_user",
                        "track_id": 7,
                        "identity_state": "recognized",
                        "identity_confidence": 0.91,
                        "prototype": "must not pass",
                    },
                },
                {
                    "event_id": "e1",
                    "event_type": "room.became_empty",
                    "occurred_at": "2026-08-29T14:00:00+00:00",
                    "room_id": "office",
                    "session_id": 3,
                    "source": "sentry_perception",
                    "confidence": None,
                    "schema_version": 3,
                    "payload": {"end_time_uncertain": True, "raw_frame": "must not pass"},
                },
            ]
        },
    }


class GroundingTests(unittest.TestCase):
    def test_seeded_api_fixtures_cover_authoritative_states_and_identity_variants(self):
        fixtures = (
            ("empty", "empty", [], "supported"),
            ("recognized", "occupied", [{"track_id": 1, "person_id": "primary_user", "identity_state": "recognized"}], "supported"),
            ("unknown", "occupied", [{"track_id": 2, "person_id": None, "identity_state": "unknown"}], "supported"),
            ("unresolved", "occupied", [{"track_id": 3, "person_id": None, "identity_state": "unresolved"}], "supported"),
            ("degraded", "degraded", [], "supported"),
            ("offline", "offline", [], "supported"),
        )
        for name, state, people, expected_grounding in fixtures:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "sentry.db"
                with PresenceStore(path) as store:
                    if state == "occupied":
                        store.record_observation({"room_state": "empty", "captured_at": "2026-08-29T10:00:00+00:00", "camera_state": "online", "people": []})
                        store.record_observation({
                            "room_state": state, "captured_at": "2026-08-29T10:00:02+00:00", "camera_state": "online",
                            "people": people, "room_state_transition": "empty->occupied", "detector_evidence": True,
                        })
                    else:
                        store.record_observation({
                            "room_state": state, "captured_at": "2026-08-29T10:00:00+00:00",
                            "camera_state": "offline" if state == "offline" else state,
                            "people": people,
                        })
                    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
                    server.store = store
                    heartbeat = Path(directory) / "perception.json"
                    heartbeat.write_text(json.dumps({
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                        "process_alive": True,
                        "summary": {"camera_state": "offline" if state == "offline" else state if state == "degraded" else "online", "room_state": state},
                    }), encoding="utf-8")
                    server.perception_heartbeat = heartbeat
                    server.perception_freshness_seconds = 75.0
                    server.display_timezone = "America/New_York"
                    thread = Thread(target=server.serve_forever, daemon=True)
                    thread.start()
                    try:
                        from tools.sentry_grounding import retrieve_fact_packet
                        retrieval = retrieve_fact_packet(f"http://127.0.0.1:{server.server_port}")
                        self.assertTrue(retrieval.available)
                        ids = {fact["fact_id"] for fact in retrieval.packet["facts"]}
                        if state in {"degraded", "offline"}:
                            self.assertNotIn("current-room-state", ids)
                            self.assertNotIn("current-room-people", ids)
                            response = {"answer": "Current occupancy is unavailable.", "grounding": "unavailable", "fact_ids": [], "limitations": ["camera is unavailable"]}
                        else:
                            self.assertIn("current-room-state", ids)
                            self.assertIn("current-room-people", ids)
                            current = next(fact for fact in retrieval.packet["facts"] if fact["fact_id"] == "current-room-state")
                            self.assertEqual(current["data"]["state"], state)
                            response = {"answer": f"Fixture {name} is {state}.", "grounding": expected_grounding, "fact_ids": ["current-room-state"], "limitations": []}
                        self.assertIsNone(validate_grounded_response(response, ids))
                    finally:
                        server.shutdown()
                        server.server_close()
                        thread.join(timeout=5)

    def test_seeded_completed_and_restart_uncertain_sessions_are_whitelisted(self):
        responses = api_responses("empty")
        responses["sessions"] = {"sessions": [
            {"session_id": 9, "room_id": "office", "started_at": "2026-08-29T09:00:00+00:00", "ended_at": "2026-08-29T09:30:00+00:00", "status": "completed", "start_reason": "observed", "end_reason": "restart_reconciled", "recovered_after_restart": 1, "end_time_uncertain": 1, "prototype": "drop"}
        ]}
        responses["events"] = {"events": [{
            "event_id": "r1", "event_type": "presence.session_ended", "occurred_at": "2026-08-29T09:30:00+00:00", "room_id": "office", "session_id": 9, "source": "sentry_perception", "confidence": None, "schema_version": 3,
            "payload": {"recovered_after_restart": True, "end_time_uncertain": True, "raw_frame": "drop"},
        }]}
        packet = build_fact_packet(responses, as_of="2026-08-29T16:00:00+00:00")
        encoded = json.dumps(packet)
        self.assertIn("restart_reconciled", encoded)
        self.assertIn("end_time_uncertain", encoded)
        self.assertNotIn("prototype", encoded)
        self.assertNotIn("raw_frame", encoded)

    def test_fact_packet_is_allow_listed_and_derives_identity_without_conflating_arrival(self):
        packet = build_fact_packet(api_responses(), as_of="2026-08-29T16:00:00+00:00")
        facts = {fact["fact_id"]: fact for fact in packet["facts"]}
        self.assertEqual(facts["current-room-state"]["data"]["state"], "occupied")
        self.assertEqual(facts["current-room-people"]["data"]["people"][0]["display_name"], "Sketch")
        self.assertNotIn("bbox", facts["current-room-people"]["data"]["people"][0])
        self.assertNotIn("prototype", jsonish(packet))
        self.assertEqual(facts["current-open-session"]["data"]["session_id"], 4)
        self.assertEqual(facts["primary-user-identification"]["data"]["first_identified_at"], "2026-08-29T15:04:00+00:00")

    def test_current_day_confirmation_is_not_presented_as_exact_arrival(self):
        responses = api_responses()
        responses["sessions"] = {"sessions": [{
            **responses["sessions"]["sessions"][0],
            "started_at": "2026-08-31T20:51:08+00:00",
            "continuity_uncertain": 1,
        }]}
        responses["primary_user_events"] = {"events": [{
            **responses["events"]["events"][0],
            "occurred_at": "2026-09-01T10:05:00+00:00",
        }]}
        packet = build_fact_packet(responses, as_of="2026-09-01T16:00:00+00:00")
        facts = {fact["fact_id"]: fact for fact in packet["facts"]}
        confirmation = facts["primary-user-presence-confirmation"]["data"]
        self.assertEqual(confirmation["local_date"], "2026-09-01")
        self.assertEqual(confirmation["first_confirmed_at_local_display"], "September 1, 2026 at 6:05 AM EDT")
        self.assertFalse(confirmation["exact_arrival_known"])
        self.assertEqual(facts["current-open-session"]["data"]["started_at_local_display"], "August 31, 2026 at 4:51 PM EDT")
        self.assertTrue(facts["current-open-session"]["data"]["continuity_uncertain"])

    def test_empty_current_day_confirmation_remains_explicit(self):
        responses = api_responses()
        responses["primary_user_events"] = {"events": []}
        packet = build_fact_packet(responses, as_of="2026-09-01T16:00:00+00:00")
        facts = {fact["fact_id"]: fact for fact in packet["facts"]}
        confirmation = facts["primary-user-presence-confirmation"]["data"]
        self.assertEqual(confirmation["local_date"], "2026-09-01")
        self.assertEqual(confirmation["confirmation_count"], 0)
        self.assertIsNone(confirmation["first_confirmed_at"])
        self.assertFalse(confirmation["exact_arrival_known"])

    def test_empty_packet_has_history_fact_but_no_open_session_or_identity_derivation(self):
        responses = api_responses("empty")
        responses["sessions"] = {"sessions": []}
        responses["events"] = {"events": []}
        packet = build_fact_packet(responses, as_of="2026-08-29T16:00:00+00:00")
        ids = {fact["fact_id"] for fact in packet["facts"]}
        self.assertIn("room-sessions", ids)
        self.assertNotIn("current-open-session", ids)
        self.assertNotIn("primary-user-identification", ids)

    def test_response_validation_rejects_unknown_fact_and_missing_citation(self):
        valid = {"answer": "The office is occupied.", "grounding": "supported", "fact_ids": ["current-room-state"], "limitations": []}
        self.assertIsNone(validate_grounded_response(valid, {"current-room-state"}))
        invalid_id = {**valid, "fact_ids": ["not-supplied"]}
        self.assertIsNotNone(validate_grounded_response(invalid_id, {"current-room-state"}))
        no_facts = {**valid, "fact_ids": []}
        self.assertIsNotNone(validate_grounded_response(no_facts, {"current-room-state"}))

    def test_response_validation_rejects_extra_fields_and_bad_grounding(self):
        base = {"answer": "No.", "grounding": "supported", "fact_ids": ["current-room-state"], "limitations": []}
        self.assertIsNotNone(validate_grounded_response({**base, "extra": True}, {"current-room-state"}))
        self.assertIsNotNone(validate_grounded_response({**base, "grounding": "guess"}, {"current-room-state"}))

    @patch("tools.sentry_grounding._get_json")
    def test_retrieval_health_failure_is_explicit_before_any_conversation(self, get_json):
        get_json.return_value = {"ok": False, "db_available": False}
        from tools.sentry_grounding import retrieve_fact_packet
        retrieval = retrieve_fact_packet("http://127.0.0.1:48174")
        self.assertFalse(retrieval.available)
        self.assertIn("unavailable", retrieval.error)

    @patch("tools.sentry_grounding._get_json")
    def test_retrieved_fact_packet_supports_later_bounded_orchestration(self, get_json):
        responses = api_responses()
        get_json.side_effect = [
            responses["health"], responses["state"], responses["sessions"], responses["persons"],
            responses["events"], {"events": [responses["events"]["events"][0]]},
        ]
        from tools.sentry_grounding import retrieve_fact_packet
        retrieval = retrieve_fact_packet("http://127.0.0.1:48174")
        self.assertTrue(retrieval.available)
        assert retrieval.packet is not None
        ids = {fact["fact_id"] for fact in retrieval.packet["facts"]}
        self.assertIn("current-room-state", ids)
        self.assertIn("primary-user-presence-confirmation", ids)
        self.assertIsNone(validate_grounded_response({
            "answer": "The office is occupied.", "grounding": "supported",
            "fact_ids": ["current-room-state"], "limitations": [],
        }, ids))


def jsonish(value):
    import json
    return json.dumps(value, sort_keys=True)


if __name__ == "__main__":
    unittest.main()
