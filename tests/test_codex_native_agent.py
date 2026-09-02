import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tools.sentry_codex_agent import CodexNativeAgent, RecentAgentContext, _prompt, invoke_sentry_agent


class CodexNativeAgentTests(unittest.TestCase):
    def test_direct_invocation_uses_full_codex_profile_without_api_keys(self):
        payload = {
            "answer": "I found the application.",
            "status": "completed",
            "capabilities_used": ["sentry_office.find_applications"],
            "local_fact_ids": [],
            "artifacts": [],
            "steps": [{"sequence": 1, "request": "find Ted", "status": "completed", "outcome": "found", "artifacts": []}],
            "limitations": [],
        }
        stdout = "\n".join([
            json.dumps({"type": "thread.started", "thread_id": "thread-1"}),
            json.dumps({"type": "item.completed", "item": {"type": "mcp_tool_call", "server": "sentry_office", "tool": "find_applications"}}),
            json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps(payload)}}),
            json.dumps({"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 5}}),
        ])
        completed = SimpleNamespace(returncode=0, stdout=stdout, stderr="")
        calls = []

        def runner(args, **kwargs):
            calls.append((args, kwargs))
            return completed

        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {
            "CODEX_HOME": tmp,
            "OPENAI_API_KEY": "must-not-leak",
            "OPENAI_ADMIN_KEY": "must-not-leak",
        }, clear=False), patch("tools.sentry_codex_agent._launcher_args", return_value=["/usr/bin/codex"]):
            Path(tmp, "sentry.config.toml").write_text("model='fixture'\n", encoding="utf-8")
            result = invoke_sentry_agent("find Ted", [], working_directory=Path(tmp), runner=runner)

        self.assertTrue(result["ok"])
        args, kwargs = calls[0]
        self.assertEqual(args[:3], ["/usr/bin/codex", "--search", "exec"])
        self.assertIn("danger-full-access", args)
        self.assertIn("sentry", args)
        self.assertNotIn("--ignore-user-config", args)
        self.assertNotIn("OPENAI_API_KEY", kwargs["env"])
        self.assertNotIn("OPENAI_ADMIN_KEY", kwargs["env"])
        self.assertIn("sentry_office.find_applications", result["observed_tools"])

    def test_missing_profile_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"CODEX_HOME": tmp}, clear=False), patch(
            "tools.sentry_codex_agent._launcher_args", return_value=["codex"]
        ):
            result = invoke_sentry_agent("hello", [], working_directory=Path(tmp))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "profile_unavailable")

    def test_same_conversation_reuses_only_ram_context(self):
        observed = []

        def invoker(question, prior, **_kwargs):
            observed.append((question, prior))
            return {
                "ok": True,
                "result": {
                    "answer": f"answer {len(observed)}",
                    "status": "completed",
                    "capabilities_used": [],
                    "local_fact_ids": [],
                    "artifacts": [],
                    "steps": [],
                    "limitations": [],
                },
                "observed_tools": [],
            }

        agent = CodexNativeAgent(context=RecentAgentContext(max_turns=4), invoker=invoker)
        agent.ask("What is the weather?", conversation_id="voice-1")
        agent.ask("What about tomorrow?", conversation_id="voice-1")
        self.assertEqual(observed[0][1], [])
        self.assertEqual(observed[1][1], [{"user": "What is the weather?", "assistant": "answer 1"}])
        self.assertNotIn("transcript", agent.ask("And alerts?", conversation_id="voice-1"))

    def test_prompt_makes_sentry_visible_and_executes_compound_work_in_order(self):
        prompt = _prompt("Open a browser, create an image, then set an alarm.", [], "medium")
        self.assertIn("SENTRY is the name and persona", prompt)
        self.assertIn("execute them strictly in the spoken order", prompt)
        self.assertIn("do not silently omit a step", prompt)
        self.assertIn("create_one_shot_alarm", prompt)
        self.assertIn("open_local_artifact", prompt)


if __name__ == "__main__":
    unittest.main()
