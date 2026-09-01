import json
import unittest
from unittest.mock import patch

from tools.sentry_ask import ask
from tools.sentry_grounding import build_fact_packet
from tools.sentry_routine_intent import RoutineIntent, select_routine_intent


def api_responses(state="empty"):
    return {
        "health": {
            "ok": True, "db_available": True, "schema_version": 5, "atlas_mirror": {"status": "ok"},
            "display_timezone": "America/New_York",
            "perception": {
                "status": "fresh", "heartbeat_updated_at": "2026-08-30T16:00:00+00:00",
                "age_seconds": 0.0, "process_alive": True, "camera_state": "online",
                "room_state": state, "current_physical_available": True, "reason": None,
            },
        },
        "state": {"room_id": "office", "state": state, "camera_state": "online", "updated_at": "2026-08-30T16:00:00+00:00", "person_count": 0, "people": []},
        "sessions": {"sessions": []},
        "persons": {"persons": []},
        "events": {"events": []},
    }


def snapshot(routine_type="office_session_start_time", scope="all_days", maturity="stable", samples=12, dates=10):
    statistics = (
        {"circular_center_local_time": "08:55:00", "mean_resultant_length": 0.92, "circular_dispersion": 0.08}
        if routine_type.endswith("time")
        else {"median": 7200.0, "mad": 600.0, "p25": 6000.0, "p75": 8400.0, "minimum": 5400.0, "maximum": 10800.0, "relative_mad": 0.0833}
    )
    return {
        "routine_key": f"{routine_type}:{scope}",
        "routine_type": routine_type,
        "scope": scope,
        "timezone": "America/New_York",
        "algorithm_version": "routine-statistics-v1",
        "window_start": "2026-07-01T00:00:00+00:00",
        "window_end": "2026-08-30T16:00:00+00:00",
        "source_as_of": "2026-08-30T15:00:00+00:00",
        "generated_at": "2026-08-30T16:00:00+00:00",
        "sample_count": samples,
        "distinct_date_count": dates,
        "maturity_status": maturity,
        "statistics": statistics,
        "exclusions": {"uncertain_end": 0, "camera_interruption": 0},
        "secret": "must not pass",
    }


class RoutineConversationTests(unittest.TestCase):
    def test_intent_routing_is_conservative_and_selects_scopes(self):
        self.assertIsNone(select_routine_intent("When did I come in today?"))
        self.assertEqual(
            select_routine_intent("When do I usually come into the office on weekdays?"),
            RoutineIntent(("office_session_start_time",), "weekday"),
        )
        self.assertEqual(
            select_routine_intent("How long are office sessions typically?"),
            RoutineIntent(("office_session_duration",), "all_days"),
        )
        self.assertEqual(
            select_routine_intent("What time do you usually first recognize me?"),
            RoutineIntent(("primary_user_session_first_confirmed_time",), "all_days"),
        )
        self.assertEqual(
            select_routine_intent("How long am I usually gone between sessions?"),
            RoutineIntent(("office_absence_between_sessions",), "all_days"),
        )
        self.assertEqual(
            select_routine_intent("What is my Monday pattern?"),
            RoutineIntent((
                "office_session_start_time", "office_session_duration",
                "office_absence_between_sessions", "primary_user_session_first_confirmed_time",
            ), "monday"),
        )

    def test_unsupported_habitual_activity_has_no_supported_routine_type(self):
        intent = select_routine_intent("What am I usually doing in here?")
        self.assertIsNotNone(intent)
        self.assertTrue(intent.unsupported)

    def test_unsupported_habitual_cause_and_premise_have_no_supported_routine_type(self):
        for question in ("Why do I usually leave early?", "You know I always leave around 5, right?"):
            with self.subTest(question=question):
                intent = select_routine_intent(question)
                self.assertIsNotNone(intent)
                self.assertTrue(intent.unsupported)

    @patch("tools.sentry_grounding._get_json")
    def test_insufficient_routine_remains_a_bounded_fact_not_a_habit_claim(self, get_json):
        responses = api_responses()
        responses["routines"] = {"routines": [snapshot(maturity="insufficient", samples=3, dates=3)]}
        get_json.side_effect = [responses["health"], responses["state"], responses["sessions"], responses["persons"], responses["events"], responses["routines"]]
        packet = build_fact_packet(responses, routine_keys_to_include={"office_session_start_time:all_days"})
        routine = next(fact for fact in packet["facts"] if fact["kind"] == "derived_routine")
        self.assertEqual(routine["fact_id"], "routine:office_session_start_time:all_days")
        self.assertEqual(routine["data"]["maturity_status"], "insufficient")
        self.assertEqual(routine["data"]["sample_count"], 3)

    def test_observed_routine_packet_is_bounded_and_tentative(self):
        responses = api_responses()
        responses["routines"] = {"routines": [snapshot(maturity="observed", samples=6, dates=6)]}
        packet = build_fact_packet(responses, routine_keys_to_include={"office_session_start_time:all_days"})
        routine_fact = next(fact for fact in packet["facts"] if fact["kind"] == "derived_routine")
        self.assertEqual(routine_fact["data"]["maturity_status"], "observed")
        self.assertNotIn("secret", json.dumps(packet))

    def test_stable_routine_packet_keeps_current_physical_state_authoritative(self):
        responses = api_responses("empty")
        responses["routines"] = {"routines": [snapshot(maturity="stable")]}
        packet = build_fact_packet(responses, routine_keys_to_include={"office_session_start_time:all_days"})
        current_state = next(fact for fact in packet["facts"] if fact["fact_id"] == "current-room-state")
        routine = next(fact for fact in packet["facts"] if fact["kind"] == "derived_routine")
        self.assertEqual(current_state["data"]["state"], "empty")
        self.assertEqual(routine["data"]["maturity_status"], "stable")

    def test_physical_packet_does_not_depend_on_routine_endpoint(self):
        responses = api_responses("occupied")
        packet = build_fact_packet(responses)
        self.assertIn("current-room-state", {fact["fact_id"] for fact in packet["facts"]})

    def test_routine_source_failure_is_representable_as_unavailable_tool_result(self):
        from tools.sentry_conversation_tools import ConversationToolHost
        self.assertEqual(ConversationToolHost.validate_call("get_routines", {"routine_type": "unknown"}), "routine type is not supported")

    def test_fact_packet_filters_routine_to_requested_key_and_drops_sensitive_fields(self):
        responses = api_responses()
        responses["routines"] = {"routines": [snapshot(), snapshot("office_session_duration"), {**snapshot(), "routine_type": "unknown"}, {"routine_key": "bad"}]}
        packet = build_fact_packet(responses, as_of="2026-08-30T16:00:00+00:00", routine_keys_to_include={"office_session_start_time:all_days"})
        routines = [fact for fact in packet["facts"] if fact["kind"] == "derived_routine"]
        self.assertEqual([fact["fact_id"] for fact in routines], ["routine:office_session_start_time:all_days"])
        self.assertNotIn("secret", json.dumps(packet))


if __name__ == "__main__":
    unittest.main()
