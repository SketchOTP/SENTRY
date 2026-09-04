import tempfile
import unittest
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from perception.presence_store import PresenceStore
from tools.sentry_conversation_orchestrator import ConversationOrchestrator, RecentConversationContext
from tools.sentry_conversation_tools import ConversationToolHost
from tools.sentry_state_api import _Handler


class _Host:
    def __init__(self, **_kwargs):
        self.calls = []

    def execute(self, name, arguments):
        self.calls.append((name, arguments))
        fact_id = {
            "get_current_office_state": "current-room-state",
            "get_office_history": "room-events",
            "get_office_reminders": "office-reminders",
            "get_acknowledgement_preference": "preference:proactivity.primary_user_session_acknowledgement",
            "get_recent_proactive_action": "recent-proactive-action",
            "get_routines": "routine:office_session_start_time:all_days",
            "get_weather": "weather:forecast:near-term",
            "use_native_web_search": "web:native-search-authorized",
        }.get(name)
        if name in {"create_next_office_reminder", "cancel_pending_office_reminder", "set_acknowledgement_preference", "clear_acknowledgement_preference", "record_proactive_feedback"}:
            return {"tool": name, "status": "succeeded", "result": {"ok": True}, "fact_ids": [], "limitations": []}
        return {"tool": name, "status": "supported", "as_of": "2026-08-31T12:00:00+00:00", "facts": [{"fact_id": fact_id, "kind": "fixture", "as_of": "2026-08-31T12:00:00+00:00", "data": {}}], "limitations": []}


class ConversationOrchestrationTests(unittest.TestCase):
    def make_orchestrator(self, plan):
        self.host = _Host()
        self.planner_inputs = []
        self.synthesis_inputs = []

        def planner(question, catalog, context, **_kwargs):
            self.planner_inputs.append((question, catalog, context))
            return {"ok": True, "model": "gpt-5.6-luna", "usage": {}, "result": {"tool_calls": plan, "needs_final_synthesis": True}}

        def synthesis(question, results, context, **_kwargs):
            self.synthesis_inputs.append((question, results, context))
            ids = [fact["fact_id"] for result in results for fact in result.get("facts", [])]
            return {"ok": True, "model": "gpt-5.6-luna", "usage": {}, "result": {"answer": "Grounded fixture answer.", "grounding": "supported", "fact_ids": ids, "limitations": []}}

        return ConversationOrchestrator(planner=planner, synthesizer=synthesis, host_factory=lambda **kwargs: self.host)

    def test_natural_text_matrix_reaches_semantically_selected_tool_without_m4_fallback(self):
        matrix = {
            "Do I have anything waiting for me next time?": "get_office_reminders",
            "What did you mean to tell me when I came in?": "get_office_reminders",
            "How are greetings configured for me?": "get_acknowledgement_preference",
            "Why did you stay quiet after seeing me?": "get_recent_proactive_action",
            "What is the office doing right now?": "get_current_office_state",
            "When did you first see me today?": "get_office_history",
            "What pattern have you seen on Mondays?": "get_routines",
            "Will rain be likely later?": "get_weather",
            "Are there any weather warnings?": "get_weather",
            "Tell me about my next office reminder": "get_office_reminders",
            "What do you remember about greeting me?": "get_acknowledgement_preference",
            "When was the room last empty?": "get_office_history",
            "Do you see anyone now?": "get_current_office_state",
            "How long are office sessions normally?": "get_routines",
            "What is it like outside?": "get_weather",
            "What was the last thing you proactively said?": "get_recent_proactive_action",
            "Look up the current weather in Boston tomorrow.": "use_native_web_search",
            "Search the web for the latest OpenAI news.": "use_native_web_search",
        }
        for question, tool in matrix.items():
            with self.subTest(question=question):
                arguments = {"topic": "forecast"} if tool == "get_weather" else {}
                orchestrator = self.make_orchestrator([{"name": tool, "arguments": arguments}])
                # A narrow fixture supplies valid argument alternatives only.
                if tool == "get_routines":
                    orchestrator = self.make_orchestrator([{"name": tool, "arguments": {"routine_type": "office_session_duration", "scope": "monday"}}])
                result = orchestrator.ask(question)
                self.assertEqual(result["tool_calls"][0]["name"], tool)
                self.assertEqual(result["luna_invocations"], 2)

    def test_tool_budget_mutation_budget_and_invalid_argument_are_fail_closed(self):
        cases = (
            ([{"name": "get_office_history", "arguments": {}}, {"name": "get_weather", "arguments": {"topic": "current"}}, {"name": "get_office_reminders", "arguments": {}}, {"name": "get_current_office_state", "arguments": {}}], "tool-call"),
            ([{"name": "set_acknowledgement_preference", "arguments": {"value": "allow"}}, {"name": "clear_acknowledgement_preference", "arguments": {}}], "mutation"),
            ([{"name": "get_weather", "arguments": {"topic": "network"}}], "invalid"),
            ([{"name": "shell", "arguments": {"command": "id"}}], "invalid"),
        )
        for calls, label in cases:
            with self.subTest(label=label):
                orchestrator = self.make_orchestrator(calls)
                result = orchestrator.ask("fixture")
                self.assertEqual(result["grounding"], "unavailable")
                self.assertEqual(result["luna_invocations"], 1)
                self.assertEqual(self.host.calls, [])

    def test_ambiguous_mutation_has_zero_writes_and_direct_mutation_has_one(self):
        ambiguous = self.make_orchestrator([{"name": "get_acknowledgement_preference", "arguments": {}}])
        result = ambiguous.ask("Could you maybe change how you greet me sometime?")
        self.assertEqual(result["tool_calls"][0]["name"], "get_acknowledgement_preference")
        self.assertNotIn("set_acknowledgement_preference", [name for name, _ in self.host.calls])

        direct = self.make_orchestrator([{"name": "set_acknowledgement_preference", "arguments": {"value": "suppress"}}])
        result = direct.ask("Do not greet me when you first recognize me.")
        self.assertEqual(result["tool_calls"][0]["name"], "set_acknowledgement_preference")
        self.assertEqual(len(self.host.calls), 1)

    def test_multi_domain_result_and_fact_ids_are_validated(self):
        orchestrator = self.make_orchestrator([
            {"name": "get_office_reminders", "arguments": {}},
            {"name": "get_current_office_state", "arguments": {}},
        ])
        result = orchestrator.ask("Do I have a reminder, and is the office occupied?")
        self.assertEqual([item["name"] for item in result["tool_calls"]], ["get_office_reminders", "get_current_office_state"])
        self.assertEqual(result["fact_ids"], ["office-reminders", "current-room-state"])

    def test_unknown_synthesis_fact_id_is_rejected(self):
        def planner(*_args, **_kwargs):
            return {"ok": True, "result": {"tool_calls": [{"name": "get_office_reminders", "arguments": {}}], "needs_final_synthesis": True}, "usage": {}}

        def synthesis(*_args, **_kwargs):
            return {"ok": True, "result": {"answer": "Not grounded.", "grounding": "supported", "fact_ids": ["not-a-real-fact"], "limitations": []}, "usage": {}}

        orchestrator = ConversationOrchestrator(planner=planner, synthesizer=synthesis, host_factory=lambda **kwargs: _Host())
        result = orchestrator.ask("Do I have a reminder?")
        self.assertEqual(result["grounding"], "unavailable")
        self.assertIn("validation", result["limitations"][0])

    def test_native_web_authorization_is_passed_as_a_typed_fact(self):
        orchestrator = self.make_orchestrator([{"name": "use_native_web_search", "arguments": {}}])
        result = orchestrator.ask("Look up the current weather in Boston tomorrow.")
        self.assertEqual(result["tool_calls"], [{"name": "use_native_web_search", "arguments": {}}])
        self.assertEqual(result["fact_ids"], ["web:native-search-authorized"])

    def test_recent_turn_context_is_bounded_ram_only_and_expires(self):
        context = RecentConversationContext(max_turns=2, ttl_seconds=600)
        context.add("voice", "First question", "First answer")
        context.add("voice", "What about tomorrow?", "Second answer")
        context.add("voice", "Why?", "Third answer")
        self.assertEqual([turn["user"] for turn in context.prior("voice")], ["What about tomorrow?", "Why?"])
        context.reset("voice")
        self.assertEqual(context.prior("voice"), [])

    def test_followup_sequences_reuse_ram_context_without_a_voice_intent_router(self):
        """The orchestrator receives ordinary natural turns under one focus id."""
        plans = {
            "What is the weather today?": {"name": "get_weather", "arguments": {"topic": "current"}},
            "What about tomorrow?": {"name": "get_weather", "arguments": {"topic": "forecast"}},
            "When was I first confirmed today?": {"name": "get_office_history", "arguments": {}},
            "Was that my exact arrival?": {"name": "get_office_history", "arguments": {}},
            "Do I have a reminder?": {"name": "get_office_reminders", "arguments": {}},
            "What was it again?": {"name": "get_office_reminders", "arguments": {}},
            "Cancel it.": {"name": "cancel_pending_office_reminder", "arguments": {}},
        }
        host = _Host()
        planner_inputs = []

        def planner(question, _catalog, prior, **_kwargs):
            planner_inputs.append((question, prior))
            return {"ok": True, "usage": {}, "result": {"tool_calls": [plans[question]], "needs_final_synthesis": True}}

        def synthesis(_question, results, _prior, **_kwargs):
            ids = [fact["fact_id"] for result in results for fact in result.get("facts", [])]
            return {"ok": True, "usage": {}, "result": {"answer": "Grounded fixture answer.", "grounding": "supported", "fact_ids": ids, "limitations": []}}

        orchestrator = ConversationOrchestrator(planner=planner, synthesizer=synthesis, host_factory=lambda **_kwargs: host)
        sequences = (
            ("weather-focus", "What is the weather today?", "What about tomorrow?", "get_weather"),
            ("history-focus", "When was I first confirmed today?", "Was that my exact arrival?", "get_office_history"),
            ("reminder-focus", "Do I have a reminder?", "What was it again?", "get_office_reminders"),
        )
        for conversation_id, initial, followup, expected_tool in sequences:
            with self.subTest(conversation_id=conversation_id):
                first = orchestrator.ask(initial, conversation_id=conversation_id)
                second = orchestrator.ask(followup, conversation_id=conversation_id)
                self.assertEqual(first["conversation_id"], conversation_id)
                self.assertEqual(second["conversation_id"], conversation_id)
                self.assertEqual(second["tool_calls"][0]["name"], expected_tool)
        # The follow-up planner receives the preceding natural turn and answer,
        # independent of voice state or a deterministic follow-up intent router.
        followup_contexts = {question: prior for question, prior in planner_inputs if question in plans and question.startswith(("What about", "Was that", "What was"))}
        self.assertEqual(followup_contexts["What about tomorrow?"][0]["user"], "What is the weather today?")
        self.assertEqual(followup_contexts["Was that my exact arrival?"][0]["user"], "When was I first confirmed today?")
        self.assertEqual(followup_contexts["What was it again?"][0]["user"], "Do I have a reminder?")
        # A direct, unambiguous contextual mutation still uses the normal host
        # validation and one-mutation request budget.
        cancelled = orchestrator.ask("Cancel it.", conversation_id="reminder-focus")
        self.assertEqual(cancelled["tool_calls"][0]["name"], "cancel_pending_office_reminder")

    def test_tool_host_uses_local_api_and_keeps_current_truthfulness(self):
        with tempfile.TemporaryDirectory() as directory, PresenceStore(Path(directory) / "sentry.db") as store:
            server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
            server.store = store
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host = ConversationToolHost(base_url=f"http://127.0.0.1:{server.server_port}")
                current = host.execute("get_current_office_state", {})
                reminders = host.execute("get_office_reminders", {})
                preference = host.execute("get_acknowledgement_preference", {})
                self.assertEqual(current["status"], "unavailable")
                self.assertEqual(reminders["status"], "supported")
                self.assertEqual(preference["facts"][0]["data"]["current_value"], "default")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_weather_tool_presents_current_nws_temperatures_in_fahrenheit(self):
        response = {
            "status": "fresh",
            "snapshot": {
                "fetched_at": "2026-09-03T01:00:00+00:00",
                "current": {
                    "observed_at": "2026-09-03T00:50:00+00:00",
                    "temperature": {"value": 33, "unit": "wmoUnit:degC"},
                    "apparent_temperature": {"value": 35, "unit": "wmoUnit:degC"},
                    "wind_chill": None,
                },
                "hourly": [{
                    "start": "2026-09-03T08:00:00-04:00",
                    "end": "2026-09-03T09:00:00-04:00",
                    "temperature": 76,
                    "temperature_unit": "F",
                    "short_forecast": "Sunny",
                }],
            },
        }
        host = ConversationToolHost(
            base_url="http://127.0.0.1:48174",
            get_json=lambda *_args, **_kwargs: response,
        )
        result = host.execute("get_weather", {"topic": "current"})
        current = next(fact for fact in result["facts"] if fact["fact_id"] == "weather:current")
        self.assertEqual(current["data"]["temperature"], {"value": 91.4, "unit": "degrees Fahrenheit"})
        self.assertEqual(current["data"]["apparent_temperature"], {"value": 95.0, "unit": "degrees Fahrenheit"})
        self.assertIsNone(current["data"]["wind_chill"])
        forecast_result = host.execute("get_weather", {"topic": "forecast"})
        forecast = next(fact for fact in forecast_result["facts"] if fact["fact_id"] == "weather:forecast:near-term")
        self.assertEqual(forecast["data"]["periods"][0]["temperature_unit"], "degrees Fahrenheit")
        self.assertEqual(response["snapshot"]["current"]["temperature"]["unit"], "wmoUnit:degC")

    def test_tool_host_mutation_result_reflects_persisted_state(self):
        with tempfile.TemporaryDirectory() as directory, PresenceStore(Path(directory) / "sentry.db") as store:
            server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
            server.store = store
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host = ConversationToolHost(base_url=f"http://127.0.0.1:{server.server_port}", source_request_id="request-1")
                created = host.execute("create_next_office_reminder", {"message": "call Mom"})
                self.assertEqual(created["status"], "succeeded")
                read = host.execute("get_office_reminders", {})
                self.assertEqual(read["facts"][0]["data"]["reminders"][0]["message"], "call Mom")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
