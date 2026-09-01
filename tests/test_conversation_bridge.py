import unittest
from unittest.mock import patch

from tools import sentry_codex_bridge
from tools.sentry_codex_bridge import invoke_conversation_planner, invoke_conversation_synthesis


class ConversationBridgeTests(unittest.TestCase):
    def test_planner_prompt_makes_recent_turns_explicit_followup_context(self):
        with patch("tools.sentry_codex_bridge._invoke_prompt", return_value=({"tool_calls": [], "needs_final_synthesis": True}, "thread", {}, None)) as invoke:
            result = invoke_conversation_planner(
                "What about tomorrow?",
                [],
                [{"user": "What is the weather today?", "assistant": "The weather data is stale."}],
            )
        self.assertTrue(result["ok"])
        prompt = invoke.call_args.args[0]
        self.assertIn("elliptical or referential", prompt)
        self.assertIn("'What about tomorrow?' normally selects the bounded weather forecast tool", prompt)
        self.assertIn("The weather data is stale.", prompt)
        self.assertIn("use_native_web_search", prompt)
        self.assertIn("SENTRY private identity", prompt)

    def test_synthesis_prompt_keeps_context_semantic_not_a_fact_substitute(self):
        with patch("tools.sentry_codex_bridge._invoke_prompt", return_value=({"answer": "fixture"}, "thread", {}, None)) as invoke:
            result = invoke_conversation_synthesis(
                "Was that my exact arrival?",
                [],
                [{"user": "When was I first confirmed today?", "assistant": "I first confirmed you at 6 AM."}],
            )
        self.assertTrue(result["ok"])
        prompt = invoke.call_args.args[0]
        self.assertIn("resolve what the current user turn refers to", prompt)
        self.assertIn("substitute for current tool facts", prompt)
        self.assertIn("No native web search is available", prompt)

    def test_synthesis_enables_native_web_only_after_typed_authorization(self):
        authorized = [{"tool": "use_native_web_search", "status": "supported", "facts": [{"fact_id": "web:native-search-authorized"}]}]
        with patch("tools.sentry_codex_bridge._invoke_prompt", return_value=({"answer": "fixture"}, "thread", {}, None)) as invoke:
            result = invoke_conversation_synthesis("Search for current OpenAI news.", authorized, [])
        self.assertTrue(result["ok"])
        self.assertTrue(invoke.call_args.kwargs["native_web_search"])
        prompt = invoke.call_args.args[0]
        self.assertIn("native read-only web-search capability is active", prompt)
        self.assertIn("web:native-search-authorized", prompt)

    def test_native_web_search_is_a_global_codex_cli_option(self):
        completed = type("Completed", (), {
            "returncode": 0,
            "stdout": '{"type":"item.completed","item":{"type":"agent_message","text":"{}"}}\n',
            "stderr": "",
        })()
        with patch("tools.sentry_codex_bridge._launcher_args", return_value=["/opt/codex"]), patch(
            "tools.sentry_codex_bridge.subprocess.run", return_value=completed
        ) as run:
            result, _thread, _usage, error = sentry_codex_bridge._invoke_prompt(
                "fixture", schema_filename="sentry_grounded_response.schema.json", effort="low",
                timeout_seconds=1, native_web_search=True,
            )
        self.assertEqual(result, {})
        self.assertIsNone(error)
        self.assertEqual(run.call_args.args[0][:3], ["/opt/codex", "--search", "exec"])


if __name__ == "__main__":
    unittest.main()
