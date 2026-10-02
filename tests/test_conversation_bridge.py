import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import sentry_codex_bridge
from tools.sentry_codex_bridge import (
    invoke_conversation_planner,
    invoke_conversation_synthesis,
)


class ConversationBridgeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sentry-bridge-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        environment = patch.dict("os.environ", {
            "SENTRY_AUTHORITY_ROOT": str(self.root / "authority"),
            "SENTRY_AGENT_WORKSPACE": str(self.root / "workspace"),
        })
        environment.start()
        self.addCleanup(environment.stop)

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
        args = run.call_args.args[0]
        self.assertEqual(args[:2], ["/opt/codex", "--search"])
        self.assertLess(args.index("--search"), args.index("exec"))
        self.assertIn("shell_tool", args)
        self.assertIn("mcp_servers={}", args)

    def test_ephemeral_bridge_has_no_host_tools_or_inherited_server_authority(self):
        completed = type("Completed", (), {
            "returncode": 0,
            "stdout": '{"type":"item.completed","item":{"type":"agent_message","text":"{}"}}\n',
            "stderr": "",
        })()
        environment = {
            "HOME": str(self.root),
            "CODEX_HOME": "/isolated-auth-location", "LANG": "C.UTF-8", "PATH": "/usr/bin:/bin",
            "OPENAI_API_KEY": "TEST_ONLY", "OPENAI_ADMIN_KEY": "TEST_ONLY",
            "ANIMA_HA_ACCESS_TOKEN": "TEST_ONLY", "ANIMA_DB_PASSWORD": "TEST_ONLY",
            "ANIMA_PREBOUND_FILE": "/not-a-real-binding", "SENTRY_OPERATOR_REQUEST": "TEST_ONLY",
            "AWS_SECRET_ACCESS_KEY": "TEST_ONLY",
            "SENTRY_AUTHORITY_ROOT": str(self.root / "authority"),
            "SENTRY_AGENT_WORKSPACE": str(self.root / "workspace"),
        }
        with patch.dict("tools.sentry_codex_bridge.os.environ", environment, clear=True), patch(
            "tools.sentry_codex_bridge._launcher_args", return_value=["/opt/codex"]
        ), patch("tools.sentry_codex_bridge.subprocess.run", return_value=completed) as run:
            result, _thread, _usage, error = sentry_codex_bridge._invoke_prompt(
                "fixture", schema_filename="sentry_grounded_response.schema.json", effort="low",
                timeout_seconds=1,
            )
        self.assertEqual(result, {})
        self.assertIsNone(error)
        args = run.call_args.args[0]
        self.assertNotIn("--search", args)
        disabled = {args[index + 1] for index, arg in enumerate(args) if arg == "--disable"}
        self.assertTrue({"shell_tool", "view_image", "code_mode_host", "plugins",
                         "browser_use", "computer_use", "skill_mcp_dependency_install"} <= disabled)
        self.assertIn("--ignore-user-config", args)
        self.assertIn("--ephemeral", args)
        self.assertIn("read-only", args)
        self.assertIn("mcp_servers={}", args)
        self.assertIn("skills.config=[]", args)
        self.assertEqual(args[args.index("--model") + 1], sentry_codex_bridge.MODEL)
        self.assertEqual(set(run.call_args.kwargs["env"]), {"PATH", "HOME", "LANG", "CODEX_HOME"})
        self.assertEqual(run.call_args.kwargs["env"]["CODEX_HOME"], environment["CODEX_HOME"])


if __name__ == "__main__":
    unittest.main()
