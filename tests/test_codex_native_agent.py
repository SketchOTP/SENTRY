import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tools.sentry_codex_agent import (
    AUTO_COMPACT_TOKEN_LIMIT,
    CodexNativeAgent,
    CodexSessionStore,
    _prompt,
    invoke_sentry_agent,
)


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
        self.assertEqual(args[:2], ["/usr/bin/codex", "--search"])
        self.assertIn("exec", args)
        self.assertNotIn("--ephemeral", args)
        self.assertIn(f"model_auto_compact_token_limit={AUTO_COMPACT_TOKEN_LIMIT}", args)
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

    def test_second_request_resumes_the_persisted_codex_thread(self):
        observed = []

        def invoker(question, prior, **_kwargs):
            observed.append((question, prior, _kwargs.get("session_id")))
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
                "thread_id": "f8b4e0b6-ae62-4d75-99fb-a69a935b9baf",
                "usage": {"input_tokens": 1200},
                "compactions": 0,
            }

        with tempfile.TemporaryDirectory() as tmp:
            store = CodexSessionStore(Path(tmp, "session.json"))
            agent = CodexNativeAgent(session_store=store, invoker=invoker)
            first = agent.ask("What is the weather?", conversation_id="voice-1")
            second = agent.ask("What about tomorrow?", conversation_id="voice-1")
            persisted = json.loads(Path(tmp, "session.json").read_text(encoding="utf-8"))
            self.assertEqual(oct(Path(tmp, "session.json").stat().st_mode & 0o777), "0o600")

        self.assertEqual(observed[0], ("What is the weather?", [], None))
        self.assertEqual(observed[1], ("What about tomorrow?", [], "f8b4e0b6-ae62-4d75-99fb-a69a935b9baf"))
        self.assertFalse(first["session_resumed"])
        self.assertTrue(second["session_resumed"])
        self.assertEqual(persisted["auto_compact_token_limit"], AUTO_COMPACT_TOKEN_LIMIT)
        self.assertEqual(persisted["turn_count"], 2)
        self.assertNotIn("transcript", persisted)
        self.assertNotIn("question", persisted)

    def test_resume_invocation_uses_exact_session_id(self):
        payload = {
            "answer": "Continuing our conversation.", "status": "completed", "capabilities_used": [],
            "local_fact_ids": [], "artifacts": [], "steps": [], "limitations": [],
        }
        stdout = "\n".join([
            json.dumps({"type": "thread.started", "thread_id": "f8b4e0b6-ae62-4d75-99fb-a69a935b9baf"}),
            json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps(payload)}}),
            json.dumps({"type": "turn.completed", "usage": {"input_tokens": 100, "output_tokens": 10}}),
        ])
        calls = []

        def runner(args, **kwargs):
            calls.append((args, kwargs))
            return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"CODEX_HOME": tmp}, clear=False), patch(
            "tools.sentry_codex_agent._launcher_args", return_value=["/usr/bin/codex"]
        ):
            Path(tmp, "sentry.config.toml").write_text("model='fixture'\n", encoding="utf-8")
            result = invoke_sentry_agent(
                "continue", [], session_id="f8b4e0b6-ae62-4d75-99fb-a69a935b9baf",
                working_directory=Path(tmp), runner=runner,
            )

        args = calls[0][0]
        resume_index = args.index("resume")
        self.assertEqual(args[resume_index + 1], "f8b4e0b6-ae62-4d75-99fb-a69a935b9baf")
        self.assertTrue(result["ok"])

    def test_codex_failure_is_not_mislabeled_as_sentry_state_outage(self):
        def invoker(_question, _prior, **_kwargs):
            return {"ok": False, "error": {"code": "codex_failed", "message": "execution unavailable"}}

        with tempfile.TemporaryDirectory() as tmp:
            agent = CodexNativeAgent(session_store=CodexSessionStore(Path(tmp, "session.json")), invoker=invoker)
            result = agent.ask("Tell me a joke")
        self.assertIn("Codex execution session", result["answer"])
        self.assertNotIn("SENTRY state", result["answer"])

    def test_prompt_makes_sentry_visible_and_executes_compound_work_in_order(self):
        prompt = _prompt("Open a browser, create an image, then set an alarm.", [], "medium")
        self.assertIn("SENTRY is the name and persona", prompt)
        self.assertIn("execute them strictly in the spoken order", prompt)
        self.assertIn("do not silently omit a step", prompt)
        self.assertIn("create_one_shot_alarm", prompt)
        self.assertIn("open_local_artifact", prompt)
        self.assertIn("never collapse a general request", prompt)


if __name__ == "__main__":
    unittest.main()
