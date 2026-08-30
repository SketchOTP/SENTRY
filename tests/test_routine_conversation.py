import json
import unittest
from unittest.mock import patch

from tools.sentry_ask import ask
from tools.sentry_grounding import build_fact_packet
from tools.sentry_routine_intent import RoutineIntent, select_routine_intent


def api_responses(state="empty"):
    return {
        "health": {"ok": True, "db_available": True, "schema_version": 5, "atlas_mirror": {"status": "ok"}},
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

    def test_unsupported_habitual_activity_question_is_rejected_without_luna(self):
        with patch("tools.sentry_ask.invoke_grounded_query") as invoke:
            result = ask("What am I usually doing in here?")
        invoke.assert_not_called()
        self.assertEqual(result["grounding"], "unavailable")
        self.assertEqual(result["luna_invocations"], 0)
        self.assertIn("activity", result["limitations"][0])

    def test_unsupported_habitual_cause_and_premise_are_rejected_without_luna(self):
        for question in ("Why do I usually leave early?", "You know I always leave around 5, right?"):
            with self.subTest(question=question), patch("tools.sentry_ask.invoke_grounded_query") as invoke:
                result = ask(question)
            invoke.assert_not_called()
            self.assertEqual(result["grounding"], "unavailable")
            self.assertEqual(result["luna_invocations"], 0)
            self.assertIn("causal", result["limitations"][0])

    @patch("tools.sentry_ask.invoke_grounded_query")
    @patch("tools.sentry_grounding._get_json")
    def test_insufficient_routine_is_deterministic_and_cites_routine_fact(self, get_json, invoke):
        responses = api_responses()
        responses["routines"] = {"routines": [snapshot(maturity="insufficient", samples=3, dates=3)]}
        get_json.side_effect = [responses["health"], responses["state"], responses["sessions"], responses["persons"], responses["events"], responses["routines"]]
        result = ask("When do I usually come into the office?")
        invoke.assert_not_called()
        self.assertEqual(result["grounding"], "unavailable")
        self.assertEqual(result["luna_invocations"], 0)
        self.assertEqual(result["fact_ids"], ["routine:office_session_start_time:all_days"])
        self.assertIn("3 qualifying observations across 3 dates", result["answer"])
        self.assertIn("sparse-history", result["limitations"][0])

    @patch("tools.sentry_ask.invoke_grounded_query")
    @patch("tools.sentry_grounding._get_json")
    def test_observed_routine_reaches_one_luna_turn_with_bounded_fact(self, get_json, invoke):
        responses = api_responses()
        responses["routines"] = {"routines": [snapshot(maturity="observed", samples=6, dates=6)]}
        get_json.side_effect = [responses["health"], responses["state"], responses["sessions"], responses["persons"], responses["events"], responses["routines"]]
        invoke.return_value = {
            "ok": True, "model": "gpt-5.6-luna", "reasoning_effort": "low", "usage": {},
            "result": {
                "answer": "So far, the office has tended to become occupied around 8:55 AM, but the pattern is tentative.",
                "grounding": "partial", "fact_ids": ["routine:office_session_start_time:all_days"],
                "limitations": ["The pattern is observed rather than stable."],
            },
        }
        result = ask("What time is the office normally occupied?")
        invoke.assert_called_once()
        packet = invoke.call_args.args[1]
        routine_fact = next(fact for fact in packet["facts"] if fact["kind"] == "derived_routine")
        self.assertEqual(routine_fact["data"]["maturity_status"], "observed")
        self.assertNotIn("secret", json.dumps(packet))
        self.assertEqual(result["luna_invocations"], 1)

    @patch("tools.sentry_ask.invoke_grounded_query")
    @patch("tools.sentry_grounding._get_json")
    def test_stable_routine_packet_keeps_current_physical_state_authoritative(self, get_json, invoke):
        responses = api_responses("empty")
        responses["routines"] = {"routines": [snapshot(maturity="stable")]}
        get_json.side_effect = [responses["health"], responses["state"], responses["sessions"], responses["persons"], responses["events"], responses["routines"]]
        invoke.return_value = {
            "ok": True, "model": "gpt-5.6-luna", "reasoning_effort": "low", "usage": {},
            "result": {
                "answer": "That is your usual pattern, but the office is currently empty.",
                "grounding": "supported", "fact_ids": ["routine:office_session_start_time:all_days", "current-room-state"],
                "limitations": [],
            },
        }
        result = ask("I'm usually here by now, right?")
        packet = invoke.call_args.args[1]
        current_state = next(fact for fact in packet["facts"] if fact["fact_id"] == "current-room-state")
        routine = next(fact for fact in packet["facts"] if fact["kind"] == "derived_routine")
        self.assertEqual(current_state["data"]["state"], "empty")
        self.assertEqual(routine["data"]["maturity_status"], "stable")
        self.assertEqual(result["grounding"], "supported")

    @patch("tools.sentry_ask.invoke_grounded_query")
    @patch("tools.sentry_grounding._get_json")
    def test_physical_query_does_not_depend_on_routine_endpoint(self, get_json, invoke):
        responses = api_responses("occupied")
        get_json.side_effect = [responses["health"], responses["state"], responses["sessions"], responses["persons"], responses["events"]]
        invoke.return_value = {
            "ok": True, "model": "gpt-5.6-luna", "reasoning_effort": "low", "usage": {},
            "result": {"answer": "The office is occupied.", "grounding": "supported", "fact_ids": ["current-room-state"], "limitations": []},
        }
        result = ask("Is anyone in the office?")
        self.assertEqual(result["grounding"], "supported")
        self.assertEqual(get_json.call_count, 5)
        invoke.assert_called_once()

    @patch("tools.sentry_grounding._get_json")
    def test_routine_endpoint_failure_is_unavailable_without_luna(self, get_json):
        responses = api_responses()
        get_json.side_effect = [responses["health"], responses["state"], responses["sessions"], responses["persons"], responses["events"], ValueError("routine endpoint down")]
        with patch("tools.sentry_ask.invoke_grounded_query") as invoke:
            result = ask("How long are office sessions usually?")
        invoke.assert_not_called()
        self.assertEqual(result["grounding"], "unavailable")
        self.assertEqual(result["luna_invocations"], 0)
        self.assertIn("routine history", result["answer"])

    def test_fact_packet_filters_routine_to_requested_key_and_drops_sensitive_fields(self):
        responses = api_responses()
        responses["routines"] = {"routines": [snapshot(), snapshot("office_session_duration"), {**snapshot(), "routine_type": "unknown"}, {"routine_key": "bad"}]}
        packet = build_fact_packet(responses, as_of="2026-08-30T16:00:00+00:00", routine_keys_to_include={"office_session_start_time:all_days"})
        routines = [fact for fact in packet["facts"] if fact["kind"] == "derived_routine"]
        self.assertEqual([fact["fact_id"] for fact in routines], ["routine:office_session_start_time:all_days"])
        self.assertNotIn("secret", json.dumps(packet))


if __name__ == "__main__":
    unittest.main()
