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
    _thread_metrics,
    invoke_action_response_classifier,
    invoke_sentry_agent,
)
from tools.sentry_execution_authority import (
    ExecutionAuthority,
    NaturalActionResponseInterpreter,
    RequestContext,
)


class CodexNativeAgentTests(unittest.TestCase):
    def test_thread_metrics_reads_only_latest_token_metadata(self):
        thread_id = "f8b4e0b6-ae62-4d75-99fb-a69a935b9baf"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "sessions", "2026", "09", "01", f"rollout-{thread_id}.jsonl")
            path.parent.mkdir(parents=True)
            path.write_text("\n".join([
                json.dumps({"type": "response_item", "payload": {"text": "must not be returned"}}),
                json.dumps({"type": "event_msg", "payload": {"type": "token_count", "info": {
                    "last_token_usage": {"input_tokens": 42000}, "model_context_window": 258400,
                }}}),
            ]) + "\n", encoding="utf-8")
            metrics = _thread_metrics(Path(tmp), thread_id)
        self.assertEqual(metrics, {
            "context_input_tokens": 42000,
            "effective_context_window_tokens": 258400,
            "thread_compaction_count": 0,
        })
    def test_direct_invocation_uses_resident_profile_with_minimal_environment(self):
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
            json.dumps({"type": "event_msg", "payload": {"type": "token_count", "info": {
                "last_token_usage": {"input_tokens": 7}, "model_context_window": 258400,
            }}}),
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
            "AWS_ACCESS_KEY_ID": "must-not-leak",
            "GH_TOKEN": "must-not-leak",
            "SUPABASE_SERVICE_ROLE_KEY": "must-not-leak",
            "DBUS_SESSION_BUS_ADDRESS": "must-not-leak",
            "DISPLAY": ":99",
        }, clear=False), patch("tools.sentry_codex_agent._launcher_args", return_value=["/usr/bin/codex"]):
            Path(tmp, "sentry-resident.config.toml").write_text("model='fixture'\n", encoding="utf-8")
            result = invoke_sentry_agent(
                "find Ted", [], working_directory=Path(tmp), runner=runner,
                request_id="request-1", thread_binding="thread-scope", authority_epoch="epoch-1",
            )

        self.assertTrue(result["ok"])
        args, kwargs = calls[0]
        self.assertEqual(args[:2], ["/usr/bin/codex", "--search"])
        self.assertIn("exec", args)
        self.assertNotIn("--ephemeral", args)
        self.assertIn(f"model_auto_compact_token_limit={AUTO_COMPACT_TOKEN_LIMIT}", args)
        self.assertNotIn("danger-full-access", args)
        self.assertIn("sentry-resident", args)
        self.assertNotIn("--ignore-user-config", args)
        self.assertNotIn("OPENAI_API_KEY", kwargs["env"])
        self.assertNotIn("OPENAI_ADMIN_KEY", kwargs["env"])
        self.assertNotIn("AWS_ACCESS_KEY_ID", kwargs["env"])
        self.assertNotIn("GH_TOKEN", kwargs["env"])
        self.assertNotIn("SUPABASE_SERVICE_ROLE_KEY", kwargs["env"])
        self.assertNotIn("DBUS_SESSION_BUS_ADDRESS", kwargs["env"])
        self.assertNotIn("SSH_AUTH_SOCK", kwargs["env"])
        self.assertNotIn("DISPLAY", kwargs["env"])
        self.assertEqual(kwargs["env"]["SENTRY_REQUEST_ID"], "request-1")
        self.assertIn("sentry_office.find_applications", result["observed_tools"])
        self.assertEqual(result["context_input_tokens"], 7)
        self.assertEqual(result["effective_context_window_tokens"], 258400)

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
            Path(tmp, "sentry-resident.config.toml").write_text("model='fixture'\n", encoding="utf-8")
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

    def test_unwritable_execution_audit_prevents_codex_turn(self):
        called = False

        def invoker(*_args, **_kwargs):
            nonlocal called
            called = True
            raise AssertionError("Codex must not run without a writable audit ledger")

        with tempfile.TemporaryDirectory() as tmp:
            authority = ExecutionAuthority(Path(tmp, "authority"), workspace=Path(tmp, "workspace"))
            with patch.object(authority, "audit_external_action", side_effect=OSError("read-only ledger")):
                agent = CodexNativeAgent(
                    session_store=CodexSessionStore(Path(tmp, "session.json")),
                    invoker=invoker,
                    authority=authority,
                    authority_epoch="epoch-1",
                )
                result = agent.ask("Create a workspace file", conversation_id="voice")

        self.assertFalse(called)
        self.assertEqual(result["security_handler"], "execution_audit_unavailable")
        self.assertEqual(result["luna_invocations"], 0)
        self.assertIn("did not run", result["answer"])

    def test_prompt_makes_sentry_visible_and_executes_compound_work_in_order(self):
        prompt = _prompt("Open a browser, create an image, then set an alarm.", [], "medium")
        self.assertIn("SENTRY is the name and persona", prompt)
        self.assertIn("execute them strictly in the spoken order", prompt)
        self.assertIn("do not silently omit a step", prompt)
        self.assertIn("create_one_shot_alarm", prompt)
        self.assertIn("open_local_artifact", prompt)
        self.assertIn("dedicated resident workspace", prompt)
        self.assertIn("propose_file_move", prompt)
        self.assertIn("Browser automation", prompt)
        self.assertIn("never collapse a general request", prompt)
        self.assertIn("prior turn's tool failure", prompt)

    def test_host_security_status_and_rotation_do_not_call_model(self):
        def fail_invoker(*_args, **_kwargs):
            raise AssertionError("security handler must not invoke the model")

        with tempfile.TemporaryDirectory() as tmp:
            store = CodexSessionStore(Path(tmp, "session.json"))
            store.save({
                "thread_id": "f8b4e0b6-ae62-4d75-99fb-a69a935b9baf", "authority_scope_id": "scope-1",
                "turn_count": 4, "last_context_utilization": 0.25, "compaction_count": 0,
            })
            authority = ExecutionAuthority(Path(tmp, "authority"), workspace=Path(tmp, "workspace"))
            agent = CodexNativeAgent(session_store=store, invoker=fail_invoker, authority=authority, authority_epoch="epoch-1")
            status = agent.ask("execution authority status", conversation_id="voice")
            rotated = agent.ask("rotate conversation", conversation_id="voice")
            saved = store.load()
        self.assertEqual(status["luna_invocations"], 0)
        self.assertEqual(status["execution_authority"]["operating_mode"], "agent_on_demand")
        self.assertFalse(rotated["old_thread_deleted"])
        self.assertIsNone(saved.get("thread_id"))
        self.assertEqual(saved["rotated_threads"][0]["thread_id"], "f8b4e0b6-ae62-4d75-99fb-a69a935b9baf")

    def test_pending_action_forces_exact_host_prompt_then_confirm_executes_once(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            source = workspace / "fixture.txt"
            source.write_text("fixture", encoding="utf-8")
            destination = root / "outside" / "fixture.txt"
            authority = ExecutionAuthority(root / "authority", workspace=workspace)

            def invoker(_question, _prior, **kwargs):
                if "move" in kwargs["operator_request"].casefold():
                    authority.propose(
                        "move_file", {"source": str(source), "destination": str(destination)}, "controlled fixture",
                        context=RequestContext(kwargs["request_id"], kwargs["thread_binding"], kwargs["operator_request"], kwargs["authority_epoch"]),
                    )
                return {
                    "ok": True, "result": {"answer": "I moved it.", "status": "completed", "capabilities_used": [],
                    "local_fact_ids": [], "artifacts": [], "steps": [], "limitations": []},
                    "observed_tools": [], "thread_id": "f8b4e0b6-ae62-4d75-99fb-a69a935b9baf", "usage": {}, "compactions": 0,
                }

            store = CodexSessionStore(root / "session.json")
            agent = CodexNativeAgent(session_store=store, invoker=invoker, authority=authority, authority_epoch="epoch-1")
            proposed = agent.ask("Move the fixture file", conversation_id="voice")
            confirmed = agent.ask("confirm", conversation_id="voice")
            replay = agent.ask("confirm", conversation_id="voice")
            self.assertIn("Shall I do that?", proposed["answer"])
            self.assertFalse(source.exists())
            self.assertTrue(destination.exists())
            self.assertEqual(confirmed["luna_invocations"], 0)
            self.assertFalse(authority.pending_status()["pending"])
            self.assertEqual(destination.read_text(encoding="utf-8"), "fixture")
            self.assertEqual(replay["luna_invocations"], 1)

    def test_always_on_pending_action_waits_for_spoken_presentation_completion(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            source = workspace / "fixture.txt"
            source.write_text("fixture", encoding="utf-8")
            destination = root / "outside" / "fixture.txt"
            authority = ExecutionAuthority(root / "authority", workspace=workspace)

            def invoker(_question, _prior, **kwargs):
                authority.propose(
                    "move_file", {"source": str(source), "destination": str(destination)}, "controlled fixture",
                    context=RequestContext(kwargs["request_id"], kwargs["thread_binding"], kwargs["operator_request"], kwargs["authority_epoch"]),
                )
                return {
                    "ok": True, "result": {"answer": "prepared", "status": "completed", "capabilities_used": [],
                    "local_fact_ids": [], "artifacts": [], "steps": [], "limitations": []},
                    "observed_tools": [], "thread_id": "f8b4e0b6-ae62-4d75-99fb-a69a935b9baf", "usage": {}, "compactions": 0,
                }

            agent = CodexNativeAgent(
                session_store=CodexSessionStore(root / "session.json"), invoker=invoker,
                authority=authority, authority_epoch="epoch-1",
            )
            proposed = agent.ask("Move the fixture file, but wait for my confirmation", source_surface="always_on_voice")
            before = authority.pending_status()
            self.assertEqual(before["status"], "PRESENTING")
            self.assertIsNone(before["response_deadline"])
            agent.complete_action_presentation(proposed["authorization"]["authorization_id"], response_window_seconds=120)
            awaiting = authority.pending_status()
            self.assertEqual(awaiting["status"], "AWAITING_RESPONSE")
            confirmed = agent.ask("Yeah, go ahead", source_surface="always_on_voice")
            self.assertEqual(confirmed["security_handler"], "action_approved")
            self.assertTrue(destination.exists())

    def test_action_response_classifier_is_ephemeral_and_tool_free(self):
        payload = {"dialogue_act": "REVISE", "revised_request": "name it final.txt", "question": None}
        stdout = "\n".join([
            json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps(payload)}}),
            json.dumps({"type": "turn.completed", "usage": {}}),
        ])
        calls = []

        def runner(args, **kwargs):
            calls.append((args, kwargs))
            return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"CODEX_HOME": tmp}, clear=False), patch(
            "tools.sentry_codex_agent._launcher_args", return_value=["/usr/bin/codex"]
        ):
            result = invoke_action_response_classifier("move fixture", "move_file", "Actually call it final.txt", runner=runner)
        args, kwargs = calls[0]
        self.assertEqual(result["dialogue_act"], "REVISE")
        self.assertIn("--ephemeral", args)
        self.assertIn("--ignore-user-config", args)
        self.assertNotIn("--search", args)
        self.assertNotIn("SENTRY_OPERATOR_REQUEST", kwargs["env"])
        self.assertNotIn("SSH_AUTH_SOCK", kwargs["env"])

    def test_pending_action_question_then_natural_cancellation_never_executes(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            source = workspace / "fixture.txt"
            source.write_text("fixture", encoding="utf-8")
            destination = root / "outside" / "fixture.txt"
            authority = ExecutionAuthority(root / "authority", workspace=workspace)
            store = CodexSessionStore(root / "session.json")
            store.save({"thread_id": "f8b4e0b6-ae62-4d75-99fb-a69a935b9baf", "authority_scope_id": "scope-1"})
            proposal = authority.propose(
                "move_file", {"source": str(source), "destination": str(destination)}, "move fixture.txt into outside",
                context=RequestContext("original", "scope-1", "Move the fixture file but wait for my confirmation", "epoch-1"),
            )
            authority.begin_presentation(proposal["authorization_id"], surface="voice")
            authority.complete_presentation(proposal["authorization_id"], surface="voice")
            agent = CodexNativeAgent(
                session_store=store, invoker=lambda *_args, **_kwargs: self.fail("question/cancel must not call Codex"),
                authority=authority, authority_epoch="epoch-1",
            )
            question = agent.ask("What file are you moving?", conversation_id="voice")
            self.assertEqual(question["security_handler"], "action_question_answered")
            self.assertEqual(authority.pending_status()["status"], "AWAITING_RESPONSE")
            cancelled = agent.ask("Actually, leave it where it is.", conversation_id="voice")
            self.assertEqual(cancelled["security_handler"], "action_cancelled")
            self.assertTrue(source.exists())
            self.assertFalse(destination.exists())

    def test_unrelated_reply_is_answered_then_pending_action_is_represented(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            source = workspace / "fixture.txt"
            source.write_text("fixture", encoding="utf-8")
            destination = root / "outside" / "fixture.txt"
            authority = ExecutionAuthority(root / "authority", workspace=workspace)
            store = CodexSessionStore(root / "session.json")
            store.save({"thread_id": "f8b4e0b6-ae62-4d75-99fb-a69a935b9baf", "authority_scope_id": "scope-1"})
            proposal = authority.propose(
                "move_file", {"source": str(source), "destination": str(destination)}, "move fixture.txt into outside",
                context=RequestContext("original", "scope-1", "Move the fixture file but wait for my confirmation", "epoch-1"),
            )
            authority.begin_presentation(proposal["authorization_id"], surface="voice")
            authority.complete_presentation(proposal["authorization_id"], surface="voice")

            def invoker(*_args, **_kwargs):
                return {
                    "ok": True, "result": {"answer": "It is sunny.", "status": "completed", "capabilities_used": [],
                    "local_fact_ids": [], "artifacts": [], "steps": [], "limitations": []},
                    "observed_tools": [], "thread_id": "f8b4e0b6-ae62-4d75-99fb-a69a935b9baf", "usage": {}, "compactions": 0,
                }

            interpreter = NaturalActionResponseInterpreter(
                lambda *_args: {"dialogue_act": "UNRELATED", "revised_request": None, "question": None}
            )
            agent = CodexNativeAgent(
                session_store=store, invoker=invoker, authority=authority,
                authority_epoch="epoch-1", response_interpreter=interpreter,
            )
            response = agent.ask("Tell me the weather", conversation_id="voice")
            self.assertIn("It is sunny.", response["answer"])
            self.assertIn("Shall I do that?", response["answer"])
            self.assertEqual(authority.pending_status()["status"], "AWAITING_RESPONSE")
            self.assertTrue(source.exists())
            self.assertFalse(destination.exists())

    def test_natural_revision_supersedes_old_arguments_and_requires_new_approval(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            source = workspace / "fixture.txt"
            source.write_text("fixture", encoding="utf-8")
            original_destination = root / "outside" / "original.txt"
            revised_destination = root / "outside" / "revised.txt"
            authority = ExecutionAuthority(root / "authority", workspace=workspace)
            store = CodexSessionStore(root / "session.json")
            store.save({"thread_id": "f8b4e0b6-ae62-4d75-99fb-a69a935b9baf", "authority_scope_id": "scope-1"})
            proposal = authority.propose(
                "move_file", {"source": str(source), "destination": str(original_destination)}, "move fixture as original.txt",
                context=RequestContext("original", "scope-1", "Move the file but wait for confirmation", "epoch-1"),
            )
            authority.begin_presentation(proposal["authorization_id"], surface="voice")
            authority.complete_presentation(proposal["authorization_id"], surface="voice")

            def invoker(_question, _prior, **kwargs):
                authority.propose(
                    "move_file", {"source": str(source), "destination": str(revised_destination)}, "move fixture as revised.txt",
                    context=RequestContext(kwargs["request_id"], kwargs["thread_binding"], kwargs["operator_request"], kwargs["authority_epoch"]),
                )
                return {
                    "ok": True, "result": {"answer": "Revised.", "status": "completed", "capabilities_used": [],
                    "local_fact_ids": [], "artifacts": [], "steps": [], "limitations": []},
                    "observed_tools": [], "thread_id": "f8b4e0b6-ae62-4d75-99fb-a69a935b9baf", "usage": {}, "compactions": 0,
                }

            agent = CodexNativeAgent(
                session_store=store, invoker=invoker, authority=authority, authority_epoch="epoch-1",
            )
            revised = agent.ask("Actually name it revised dot txt", conversation_id="voice")
            pending = authority.pending_status(include_arguments=True)
            self.assertIn("revised.txt", revised["answer"])
            self.assertEqual(pending["canonical_arguments"]["destination"], str(revised_destination))
            self.assertFalse(original_destination.exists())
            confirmed = agent.ask("Sounds good, do it", conversation_id="voice")
            self.assertEqual(confirmed["security_handler"], "action_approved")
            self.assertTrue(revised_destination.exists())


if __name__ == "__main__":
    unittest.main()
