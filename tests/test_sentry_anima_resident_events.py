"""Same-resident synthetic integration only: no Core, model, or physical speech."""

import fcntl
import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import tomllib

from tools.sentry_anima import AnimaConfig
from tools.sentry_anima_events import (
    AttentionQueueSource,
    _event_process,
    _initiative_notification,
    configured_attention_source,
    verify_autonomous_cli,
)
from tools.sentry_codex_agent import (
    CodexNativeAgent,
    CodexSessionStore,
    _event_prompt,
    _prompt,
)
from tools.sentry_codex_profile import autonomous_turn_overrides, profile_text
from tools.sentry_execution_authority import ExecutionAuthority


class ResidentEventIntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.codex_home = self.root / "codex-home"
        self.codex_home.mkdir()
        self.package = self.root / "client"
        self.package.mkdir()
        (self.package / "anima_household_mcp.py").touch()
        self.config = self.root / "anima.json"
        self.config.write_text(json.dumps({
            "enabled": True, "endpoint": "/synthetic/core.sock",
            "token_file": str(self.root / "token"), "worker_id": "synthetic",
            "client_directory": str(self.package),
        }))
        self.config.chmod(0o600)
        environment = patch.dict(os.environ, {
            "SENTRY_ANIMA_CONFIG": str(self.config),
            "SENTRY_AGENT_WORKSPACE": str(self.workspace),
            "SENTRY_CODEX_HOME": str(self.codex_home),
            "XDG_STATE_HOME": str(self.root / "state"),
        })
        environment.start()
        self.addCleanup(environment.stop)
        self.profile = profile_text(
            python_executable=Path("/usr/bin/python3"), config_path=self.root / "sentry.json",
            anima_config_path=self.config, workspace_path=self.workspace,
            authority_root=self.root / "authority", resident_codex_home=self.codex_home,
        )
        (self.codex_home / "sentry-resident.config.toml").write_text(self.profile)
        self.thread_id = "cef5392b-d9e6-4187-801f-5544a3d81c36"
        self.request_id = "cb0f06e3-c10b-40a7-b661-a1a352fe26ec"
        self.household_id = "392c547b-6ccb-4861-8a49-335757663fa1"
        self.store = CodexSessionStore(self.root / "session.json")
        self.store.save({"thread_id": self.thread_id, "turn_count": 5, "authority_scope_id": "unchanged"})
        self.agent = CodexNativeAgent(
            session_store=self.store,
            authority=ExecutionAuthority(self.root / "authority", workspace=self.workspace),
        )
        self.client = Mock(spec=["provider_start", "renew", "submit_result", "call", "context", "worker_id"])
        self.client.worker_id = "synthetic"
        self.client.provider_start.return_value = {"status": "PROVIDER_RUNNING"}
        self.client.submit_result.side_effect = lambda *_, **kw: {
            "status": "RECORDED", "result_status": kw["status"],
            "notification": self.initiative_context()["household_context"]["initiative"]["notification"],
        }
        self.client.context.side_effect = lambda *_: self.initiative_context()
        client_patch = patch.object(AnimaConfig, "client", return_value=self.client)
        client_patch.start()
        self.addCleanup(client_patch.stop)
        launcher = patch("tools.sentry_codex_agent._launcher_args", return_value=["codex"])
        launcher.start()
        self.addCleanup(launcher.stop)
        cli_check = patch("tools.sentry_anima_events.verify_autonomous_cli")
        cli_check.start()
        self.addCleanup(cli_check.stop)
        self.claim = Mock(side_effect=self.exact_claim)
        self.speaker = Mock()
        self.speaker.is_speaking = False
        self.speaker.speak.return_value = True
        self.decision = "speak"
        self.tool_status = "SUCCEEDED"
        self.runner = Mock(side_effect=self.model)
        self.enable_epoch = datetime.now(timezone.utc) - timedelta(seconds=60)

    def initiative_context(self, **updates):
        return {"household_context": {"initiative": {
            "status": "AVAILABLE", "notification": {
                "allowed": True, "required": True, "reason": "ALWAYS_NOTIFY",
                "request_id": self.request_id,
                "evaluated_at": datetime.now(timezone.utc).isoformat(), **updates,
            },
        }}}

    def exact_claim(self, request_id, source_surface):
        self.assertEqual((request_id, source_surface), (self.request_id, "anima_attention"))
        with self.store.lock_path.open() as handle, self.assertRaises(BlockingIOError):
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return {
            "status": "CLAIMED", "origin": "AUTONOMOUS_ATTENTION", "provider_id": "sentry",
            "request_id": request_id, "household_id": self.household_id,
            "fencing_generation": 1, "binding": "synthetic-private-binding",
        }

    def model(self, args, **kwargs):
        self.client.provider_start.assert_called_once()
        self.assertEqual(args[args.index("resume") + 1], self.thread_id)
        self.assertNotIn("--search", args)
        self.assertNotIn("--ephemeral", args)
        self.assertIn('web_search="disabled"', args)
        overlay = self.overlay_values(args)
        self.assertIs(overlay["mcp_servers"]["sentry_office"]["enabled"], False)
        self.assertIn("features.shell_tool=false", args)
        self.assertIn("features.js_repl=false", args)
        self.assertNotIn("SENTRY_OPERATOR_REQUEST", kwargs["env"])
        self.assertNotIn("SENTRY_AUTHORITY_EPOCH", kwargs["env"])
        self.assertNotIn("synthetic-private-binding", kwargs["input"])
        self.assertIn("not an operator request", kwargs["input"])
        self.assertLessEqual(kwargs["timeout"], 255)
        path = Path(kwargs["env"]["ANIMA_PREBOUND_FILE"])
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        path.with_name("metadata.json").write_text(json.dumps({"version": 1, "status": self.tool_status, "calls": 1}))
        final = {"decision": self.decision, "answer": "Synthetic current result.", "status": "completed", "local_fact_ids": [], "limitations": []}
        stdout = "\n".join([
            json.dumps({"type": "thread.started", "thread_id": self.thread_id}),
            json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps(final)}}),
        ])
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    def run_event(self, **gates):
        settings = {"enabled": True, "context_ready": True, "persistent_history_allowed": True, **gates}
        return self.agent.process_anima_event(
            request_id=self.request_id, household_id=self.household_id,
            claim_exact=self.claim, speaker=self.speaker, runner=self.runner, **settings,
        )

    def test_commissioning_gates_prevent_claim_model_and_tts(self):
        for field in ("enabled", "context_ready", "persistent_history_allowed"):
            with self.subTest(field=field):
                self.assertEqual(self.run_event(**{field: False})["status"], "NOT_READY")
        self.claim.assert_not_called()
        self.runner.assert_not_called()
        self.speaker.speak.assert_not_called()

    def test_same_thread_fenced_model_actual_final_and_existing_speaker(self):
        result = self.run_event()
        self.assertEqual((result["status"], result["delivery_status"]), ("RECORDED", "DELIVERED"))
        self.runner.assert_called_once()
        self.client.submit_result.assert_called_once()
        self.speaker.speak.assert_called_once_with("Synthetic current result.")
        self.assertEqual(self.store.load()["thread_id"], self.thread_id)
        self.assertEqual(self.store.load()["turn_count"], 6)
        self.assertNotIn("Synthetic current result", self.store.path.read_text())
        self.assertEqual((self.codex_home / "sentry-resident.config.toml").read_text(), self.profile)

    def test_unattended_wake_records_core_result_before_existing_tts(self):
        order = []

        def submit(*args, **kwargs):
            order.append("core")
            return {
                "status": "RECORDED",
                "result_status": kwargs["status"],
                "notification": self.initiative_context()["household_context"]["initiative"]["notification"],
            }

        self.client.submit_result.side_effect = submit
        self.speaker.speak.side_effect = lambda _text: (order.append("tts"), True)[1]
        result = self.run_event()
        self.assertEqual(result["delivery_status"], "DELIVERED")
        self.assertEqual(order, ["core", "tts"])

    def test_provider_start_outage_is_terminal_without_model_or_tts_fallback(self):
        self.client.provider_start.side_effect = OSError("PRIVATE PROVIDER CONTENT")
        result = self.run_event()
        self.assertEqual(result["result_status"], "UNKNOWN_RESULT")
        self.assertEqual(result["stage"], "PROVIDER_START")
        self.assertTrue(self.client.submit_result.call_args.kwargs["provider_ambiguous"])
        self.runner.assert_not_called()
        self.speaker.speak.assert_not_called()
        self.assertNotIn("PRIVATE", json.dumps(result))

    def test_model_silence_never_speaks(self):
        self.decision = "silent"
        self.client.context.side_effect = lambda *_: self.initiative_context(
            required=False, reason="LEARNED_PROACTIVE",
        )
        self.assertEqual(self.run_event()["result_status"], "NO_ACTION")
        self.speaker.speak.assert_not_called()
        self.client.context.assert_called_once_with(self.request_id, "synthetic-private-binding")

    def test_required_notification_silence_is_partial_evidence_without_forced_tts_or_retry(self):
        self.decision = "silent"
        result = self.run_event()
        self.assertEqual(result["result_status"], "PARTIAL")
        self.assertEqual(result["detail"], "REQUIRED_NOTIFICATION_NOT_PRODUCED")
        self.assertEqual(result["delivery_status"], "NOT_ATTEMPTED")
        self.assertEqual(self.store.load()["last_status"], "autonomous_partial")
        self.client.context.assert_called_once_with(self.request_id, "synthetic-private-binding")
        self.client.submit_result.assert_called_once_with(
            self.request_id, "synthetic-private-binding", status="PARTIAL", response=None,
            provider_ambiguous=False, detail="REQUIRED_NOTIFICATION_NOT_PRODUCED",
        )
        self.runner.assert_called_once()
        self.speaker.speak.assert_not_called()

    def test_review_silence_is_not_a_missing_required_notification(self):
        self.decision = "silent"
        self.client.context.side_effect = lambda *_: self.initiative_context(
            allowed=False, required=False, reason="REVIEW_SILENT",
        )
        result = self.run_event()
        self.assertEqual(result["result_status"], "NO_ACTION")
        self.assertNotIn("detail", result)
        self.assertNotIn("detail", self.client.submit_result.call_args.kwargs)
        self.client.context.assert_called_once()
        self.speaker.speak.assert_not_called()

    def test_initiative_contract_fails_closed_for_invalid_and_cross_request_values(self):
        now = datetime.now(timezone.utc)
        invalid = [None, {}, {"household_context": None},
                   {"household_context": {"initiative": {"status": "UNAVAILABLE"}}}]
        for updates in (
            {"allowed": 1}, {"allowed": "true"}, {"required": 1},
            {"request_id": self.household_id}, {"reason": "MODEL_SAYS_URGENT"},
            {"reason": []}, {"reason": "LEARNING_REQUIRED"},
            {"reason": "PROACTIVE_DISABLED"}, {"reason": "REVIEW_SILENT"},
            {"reason": "UNAVAILABLE"}, {"reason": "LEARNED_PROACTIVE", "required": True},
            {"allowed": False, "required": True},
            {"evaluated_at": now.replace(tzinfo=None).isoformat()},
            {"evaluated_at": (now - timedelta(seconds=31)).isoformat()},
            {"evaluated_at": (now + timedelta(seconds=6)).isoformat()},
            {"evaluated_at": "not-an-iso-date"}, {"evaluated_at": None},
        ):
            invalid.append(self.initiative_context(**updates))
        for context in invalid:
            with self.subTest(context=context):
                self.assertFalse(_initiative_notification(context, self.request_id, now=now)["allowed"])

    def test_learning_and_reviews_stay_silent_despite_model_speech(self):
        for reason in ("LEARNING_REQUIRED", "PROACTIVE_DISABLED", "REVIEW_SILENT", "UNAVAILABLE"):
            with self.subTest(reason=reason):
                self.client.reset_mock()
                self.client.context.side_effect = lambda *_, r=reason: self.initiative_context(
                    allowed=False, required=False, reason=r,
                )
                result = self.run_event()
                self.assertEqual(result["result_status"], "NO_ACTION")
                self.assertEqual(result["delivery_status"], "BLOCKED_INITIATIVE")
                self.assertEqual(result["initiative_reason"], reason)
                self.assertIsNone(self.client.submit_result.call_args.kwargs["response"])
        self.assertEqual(self.runner.call_count, 4)  # Silent reasoning is still allowed.
        self.speaker.speak.assert_not_called()

    def test_missing_context_and_transport_failure_never_speak_or_expose_error(self):
        for value in ({}, OSError("PRIVATE HOUSEHOLD CONTENT")):
            self.client.reset_mock()
            self.client.context.side_effect = value if isinstance(value, Exception) else lambda *_, v=value: v
            result = self.run_event()
            self.assertEqual(result["delivery_status"], "BLOCKED_INITIATIVE")
            self.assertNotIn("PRIVATE", json.dumps(result))
        self.speaker.speak.assert_not_called()

    def test_context_is_fetched_after_model_before_submit_with_exact_binding(self):
        def context(request_id, binding):
            self.runner.assert_called_once()
            self.client.submit_result.assert_not_called()
            self.assertEqual((request_id, binding), (self.request_id, "synthetic-private-binding"))
            return self.initiative_context(allowed=False, required=False, reason="PROACTIVE_DISABLED")
        self.client.context.side_effect = context
        self.assertEqual(self.run_event()["delivery_status"], "BLOCKED_INITIATIVE")
        self.speaker.speak.assert_not_called()

    def test_learned_proactive_permission_allows_model_choice_not_forced_speech(self):
        self.client.context.side_effect = lambda *_: self.initiative_context(
            required=False, reason="LEARNED_PROACTIVE",
        )
        self.assertEqual(self.run_event()["delivery_status"], "DELIVERED")
        self.client.reset_mock()
        self.decision = "silent"
        self.assertEqual(self.run_event()["result_status"], "NO_ACTION")
        self.speaker.speak.assert_called_once()

    def test_delayed_submit_cannot_reuse_expired_disposition_for_speech(self):
        real_datetime = datetime
        future = real_datetime.now(timezone.utc) + timedelta(seconds=40)
        with patch("tools.sentry_anima_events.datetime", wraps=real_datetime) as clock:
            clock.now.side_effect = lambda *args: real_datetime.now(*args)
            def submit(*_, **__):
                notification = self.initiative_context()["household_context"]["initiative"]["notification"]
                clock.now.side_effect = None
                clock.now.return_value = future
                return {"status": "RECORDED", "result_status": "RESPONSE", "notification": notification}
            self.client.submit_result.side_effect = submit
            result = self.run_event()
        self.assertEqual(result["result_status"], "RESPONSE")
        self.assertEqual(result["delivery_status"], "BLOCKED_INITIATIVE")
        self.speaker.speak.assert_not_called()

    def test_core_settings_changed_during_submission_normalizes_response_without_tts(self):
        def submit(request_id, binding, **payload):
            self.assertEqual((request_id, binding), (self.request_id, "synthetic-private-binding"))
            self.assertEqual(payload["status"], "RESPONSE")
            self.assertIsInstance(payload["response"], str)
            self.client.context.assert_called_once()
            # Fake the real finalize_result wire: settings changed after the
            # host's allowed context read; Core records no response text.
            return {
                "status": "RECORDED", "result_status": "NO_ACTION",
                "notification": self.initiative_context(
                    allowed=False, required=False, reason="PROACTIVE_DISABLED",
                )["household_context"]["initiative"]["notification"],
            }
        self.client.submit_result.side_effect = submit
        result = self.run_event()
        self.assertEqual(result["status"], "RECORDED")
        self.assertEqual(result["result_status"], "NO_ACTION")
        self.assertEqual(result["initiative_reason"], "PROACTIVE_DISABLED")
        self.assertEqual(result["delivery_status"], "BLOCKED_INITIATIVE")
        self.client.submit_result.assert_called_once()
        self.runner.assert_called_once()
        self.speaker.speak.assert_not_called()

    def test_missing_invalid_or_denied_receipt_never_uses_presubmit_permission(self):
        good = self.initiative_context()["household_context"]["initiative"]["notification"]
        for receipt in (
            {"status": "RECORDED"},
            {"status": "RECORDED", "notification": good},
            {"status": "RECORDED", "result_status": "invalid", "notification": good},
            {"status": "RECORDED", "result_status": [], "notification": good},
            {"status": "RECORDED", "result_status": "RESPONSE"},
            {"status": "RECORDED", "result_status": "RESPONSE", "notification": {}},
            {"status": "RECORDED", "result_status": "RESPONSE", "notification": {**good, "allowed": False, "required": False}},
            {"status": "RECORDED", "result_status": "RESPONSE", "notification": {**good, "request_id": self.household_id}},
            {"status": "RECORDED", "result_status": "RESPONSE", "notification": {**good, "evaluated_at": "invalid"}},
            {"status": "RECORDED", "result_status": "NO_ACTION", "notification": good},
        ):
            with self.subTest(receipt=receipt):
                self.client.reset_mock()
                self.client.submit_result.side_effect = None
                self.client.submit_result.return_value = receipt
                result = self.run_event()
                self.assertNotEqual(result["delivery_status"], "DELIVERED")
                self.client.submit_result.assert_called_once()
        self.speaker.speak.assert_not_called()

    def test_denied_notification_is_not_promoted_to_success_or_delivery(self):
        self.decision = "notify"
        self.client.context.side_effect = lambda *_: self.initiative_context(
            allowed=False, required=False, reason="LEARNING_REQUIRED",
        )
        result = self.run_event()
        self.assertEqual(result["result_status"], "PARTIAL")
        self.assertEqual(result["delivery_status"], "BLOCKED_INITIATIVE")
        # This is not proof that an earlier MCP dispatch was blocked by Core.
        self.assertEqual(result["notification_delivery_status"], "NOT_VERIFIED")
        self.speaker.speak.assert_not_called()

    def test_model_claimed_permission_cannot_replace_missing_core_disposition(self):
        self.client.context.side_effect = lambda *_: {}
        with patch("tools.sentry_codex_agent.invoke_sentry_agent", return_value={
            "ok": True, "thread_id": self.thread_id, "result": {
                "decision": "speak", "answer": "I claim urgent permission.", "status": "completed",
                "household_context": self.initiative_context()["household_context"],
            },
        }):
            result = self.run_event()
        self.assertEqual(result["result_status"], "NO_ACTION")
        self.assertEqual(result["initiative_reason"], "UNAVAILABLE")
        self.assertIsNone(self.client.submit_result.call_args.kwargs["response"])
        self.speaker.speak.assert_not_called()

    def test_notify_is_tool_activity_not_claimed_tts_or_notification_delivery(self):
        self.decision = "notify"
        result = self.run_event()
        self.assertEqual(result["result_status"], "TOOL_ACTIVITY_COMPLETED")
        self.assertEqual(result["delivery_status"], "NOT_ATTEMPTED")
        self.assertEqual(result["notification_delivery_status"], "NOT_VERIFIED")
        self.assertNotIn("detail", result)
        self.client.context.assert_called_once()
        self.speaker.speak.assert_not_called()

    def test_notification_confirmation_gate_is_not_delivery(self):
        self.decision = "notify"
        self.tool_status = "WAITING_CONFIRMATION"
        result = self.run_event()
        self.assertEqual(result["result_status"], "WAITING_CONFIRMATION")
        self.assertEqual(result["notification_delivery_status"], "NOT_VERIFIED")
        self.speaker.speak.assert_not_called()

    def test_restricted_or_auth_gate_cannot_promote_model_final_to_speech(self):
        for status in ("UNAVAILABLE", "WAITING_STRONGER_AUTH", "UNKNOWN_RESULT"):
            with self.subTest(status=status):
                self.client.reset_mock()
                self.tool_status = status
                self.assertEqual(self.run_event()["result_status"], status)
        self.speaker.speak.assert_not_called()

    def test_failed_result_recording_never_speaks(self):
        self.client.submit_result.side_effect = OSError("synthetic")
        self.assertEqual(self.run_event()["status"], "UNKNOWN_RESULT")
        self.speaker.speak.assert_not_called()

    def test_tts_failure_keeps_actual_model_result_distinct(self):
        self.speaker.speak.return_value = False
        result = self.run_event()
        self.assertEqual((result["result_status"], result["delivery_status"]), ("RESPONSE", "FAILED"))
        self.runner.assert_called_once()

    def test_no_persistent_thread_never_claims(self):
        self.store.save({})
        self.assertEqual(self.run_event()["gate"], "RESIDENT_THREAD_UNAVAILABLE")
        self.claim.assert_not_called()

    def test_overlay_disables_other_mcp_and_native_surfaces_without_mutation(self):
        profile = tomllib.loads(self.profile)
        profile["mcp_servers"]["unrelated"] = {"enabled": True}
        before = json.dumps(profile, sort_keys=True)
        args = autonomous_turn_overrides(profile)
        overlay = self.overlay_values(args)
        self.assertIs(overlay["mcp_servers"]["unrelated"]["enabled"], False)
        self.assertEqual(overlay["permissions.sentry-resident.filesystem"][":workspace_roots"]["."], "read")
        self.assertEqual(json.dumps(profile, sort_keys=True), before)

    @staticmethod
    def overlay_values(args):
        return {args[i + 1].split("=", 1)[0]: tomllib.loads("value=" + args[i + 1].split("=", 1)[1])["value"]
                for i in range(len(args) - 1) if args[i] == "-c"}

    def test_guidance_is_bounded_provenance_aware_not_authority(self):
        for prompt in (_prompt("Synthetic request", [], "medium"), _event_prompt()):
            for text in ("household_context", "authority NONE", "personal preferences", "family routines", "knowledge.search_notes", "never dump all memory", "EPHEMERAL_RESTRICTED", "Never store transcripts"):
                self.assertIn(text, prompt)

    def test_initiative_and_review_guidance_preserves_manual_voice_and_no_auto_code(self):
        instructions = Path("integrations/codex/SENTRY_AGENT_INSTRUCTIONS.md").read_text()
        for prompt in (_prompt("Synthetic request", [], "medium"), _event_prompt(), instructions):
            for text in ("ALWAYS_NOTIFY", "LEARNED_PROACTIVE", "request_id", "evaluated_at",
                         "observed days", "inferred routines", "versioned", "reviewable", "Ring"):
                self.assertIn(text, prompt)
        self.assertIn("does not silence an ordinary current owner voice request", _event_prompt())
        self.assertIn("not arbitrary auto-created code execution", _event_prompt())
        self.assertIn("required true, do not call silence handled", _event_prompt())
        self.assertIn("do not retry the model", _event_prompt())

    def queue_source(self, **gates):
        return AttentionQueueSource(
            self.agent, household_id=self.household_id,
            not_before=self.enable_epoch,
            **{"enabled": True, "context_ready": True, "persistent_history_allowed": True, **gates},
        )

    def queue_claim(self, **updates):
        return {
            "status": "CLAIMED", "origin": "AUTONOMOUS_ATTENTION", "provider_id": "sentry",
            "request_id": self.request_id, "household_id": self.household_id,
            "fencing_generation": 1, "binding": "synthetic-private-binding",
            "created_at": datetime.now(timezone.utc).isoformat(), "provider_started": False,
            **updates,
        }

    def serve_queue(self, claim):
        metadata = {key: claim[key] for key in ("request_id", "household_id", "provider_id", "origin", "created_at")}
        self.client.call.side_effect = lambda path, payload: (
            {"status": "AVAILABLE", "items": [metadata]} if path.endswith("/eligible") else claim
        )

    def test_queue_claim_is_filtered_under_resident_lock_then_same_model_and_speaker(self):
        def claim(path, payload):
            self.assertEqual(payload["origin"], "AUTONOMOUS_ATTENTION")
            self.assertEqual(payload["not_before"], self.enable_epoch.isoformat())
            self.assertEqual(payload["max_age_seconds"], 120)
            with self.store.lock_path.open() as handle, self.assertRaises(BlockingIOError):
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            if path == "/v1/provider/requests/eligible":
                self.assertEqual(payload["limit"], 1)
                return {"status": "AVAILABLE", "items": [self.queue_claim()]}
            self.assertEqual(path, "/v1/provider/claims/exact")
            self.assertEqual(payload["request_id"], self.request_id)
            self.assertEqual(payload["source_surface"], "anima_attention")
            return self.queue_claim()
        self.client.call.side_effect = claim
        with patch("tools.sentry_anima_events._event_process", side_effect=lambda args, lease, **kw: self.model(args, **kw)):
            result = self.queue_source()(speaker=self.speaker)
        self.assertEqual(result["delivery_status"], "DELIVERED")
        self.assertEqual(self.client.call.call_count, 2)
        self.client.provider_start.assert_called_once_with(self.request_id, "synthetic-private-binding")
        self.speaker.speak.assert_called_once()
        self.assertEqual(self.store.load()["thread_id"], self.thread_id)

    def test_queue_gates_do_not_contact_core(self):
        for name in ("enabled", "context_ready", "persistent_history_allowed"):
            self.assertEqual(self.queue_source(**{name: False})()["status"], "NOT_READY")
        self.client.call.assert_not_called()

    def test_queue_empty_is_throttled_without_start_or_model(self):
        self.client.call.return_value = {"status": "EMPTY", "items": []}
        source = self.queue_source()
        with patch("tools.sentry_anima_events.time.monotonic", return_value=100.0):
            self.assertEqual(source()["status"], "EMPTY")
            self.assertEqual(source()["gate"], "EVENT_POLL_INTERVAL")
        with patch("tools.sentry_anima_events.time.monotonic", return_value=115.0):
            self.assertEqual(source()["status"], "EMPTY")
        self.assertEqual(self.client.call.call_count, 2)
        self.client.provider_start.assert_not_called()

    def test_old_wrong_origin_started_and_cross_household_claims_never_start(self):
        for fields in (
            {"created_at": (self.enable_epoch - timedelta(seconds=1)).isoformat()},
            {"created_at": "2026-09-07T00:00:01"},
            {"origin": "DIRECT_SENTRY_INTERACTION"},
            {"provider_started": True}, {"provider_started": None},
            {"provider_id": "other"}, {"household_id": self.request_id},
            {"fencing_generation": 0},
        ):
            with self.subTest(fields=fields):
                self.serve_queue(self.queue_claim(**fields))
                source = self.queue_source()
                self.assertEqual(source()["status"], "UNKNOWN_RESULT")
                self.assertEqual(source()["gate"], "EVENT_SOURCE_REVIEW_REQUIRED")
        self.client.provider_start.assert_not_called()
        self.speaker.speak.assert_not_called()

    def test_unsupported_or_lost_claim_response_halts_without_fallback_or_retry(self):
        self.client.call.side_effect = OSError("secret payload must not appear")
        source = self.queue_source()
        result = source()
        self.assertEqual(result["exception_type"], "OSError")
        self.assertNotIn("secret", json.dumps(result))
        self.assertEqual(source()["gate"], "EVENT_SOURCE_REVIEW_REQUIRED")
        self.client.call.assert_called_once()
        self.client.provider_start.assert_not_called()

    def test_unknown_execution_latches_source_no_next_claim(self):
        self.serve_queue(self.queue_claim())
        source = self.queue_source()
        with patch("tools.sentry_codex_agent.invoke_sentry_agent", return_value={"ok": False}):
            self.assertEqual(source()["result_status"], "UNKNOWN_RESULT")
        self.assertEqual(source()["gate"], "EVENT_SOURCE_REVIEW_REQUIRED")
        self.assertEqual(self.client.call.call_count, 2)

    def test_setup_failures_happen_before_claim(self):
        for target in ("tools.sentry_anima.AnimaConfig.client", "tools.sentry_anima_events.tempfile.TemporaryDirectory"):
            with self.subTest(target=target), patch(target, side_effect=OSError("synthetic setup failure")):
                self.assertEqual(self.queue_source()()["status"], "UNKNOWN_RESULT")
        self.client.call.assert_not_called()
        self.claim.assert_not_called()

    def test_weak_filesystem_or_missing_executor_never_claims(self):
        with patch("tools.sentry_codex_agent._launcher_args", return_value=None):
            self.assertEqual(self.queue_source()()["gate"], "RESIDENT_EXECUTOR_UNAVAILABLE")
        with patch("tools.sentry_anima.filesystem_denies", return_value=False):
            self.assertEqual(self.queue_source()()["status"], "UNKNOWN_RESULT")
        self.client.call.assert_not_called()

    def test_enable_epoch_requires_timezone_and_is_not_advanced_on_poll(self):
        with self.assertRaises(ValueError):
            AttentionQueueSource(self.agent, household_id=self.household_id, not_before=datetime(2026, 9, 7))  # noqa: DTZ001 - rejected fixture
        source = self.queue_source()
        epoch = source.not_before
        self.client.call.return_value = {"status": "EMPTY", "items": []}
        source()
        self.assertEqual(source.not_before, epoch)

    def test_process_not_started_if_lease_already_revoked(self):
        import subprocess
        lease = SimpleNamespace(cancelled=Mock(), remaining_seconds=10)
        lease.cancelled.is_set.return_value = True
        with patch("subprocess.Popen") as launch, self.assertRaises(subprocess.TimeoutExpired):
            _event_process(["codex"], lease, input="synthetic", timeout=10)
        launch.assert_not_called()

    def test_installed_cli_parses_overlay_and_only_enables_anima_mcp(self):
        cli = shutil.which("codex")
        if cli is None:
            self.skipTest("installed Codex CLI unavailable")
        verify_autonomous_cli([cli], self.codex_home, self.workspace, tomllib.loads(self.profile))

    def test_installed_cli_base_config_extra_mcp_is_rejected(self):
        cli = shutil.which("codex")
        if cli is None:
            self.skipTest("installed Codex CLI unavailable")
        (self.codex_home / "config.toml").write_text('[mcp_servers.hidden_extra]\ncommand="/usr/bin/false"\nenabled=true\n')
        with self.assertRaisesRegex(ValueError, "AUTONOMOUS_UNEXPECTED_MCP_ENABLED"):
            verify_autonomous_cli([cli], self.codex_home, self.workspace, tomllib.loads(self.profile))

    def test_installed_cli_strict_probe_rejects_unsupported_view_image_override(self):
        cli = shutil.which("codex")
        if cli is None:
            self.skipTest("installed Codex CLI unavailable")
        profile = tomllib.loads(self.profile)
        args = autonomous_turn_overrides(profile)
        self.assertNotIn("tools.view_image", self.overlay_values(args))
        args.extend(["-c", "tools.view_image=false"])
        with patch("tools.sentry_codex_profile.autonomous_turn_overrides", return_value=args), self.assertRaisesRegex(ValueError, "AUTONOMOUS_STRICT_CONFIG_UNAVAILABLE"):
            verify_autonomous_cli([cli], self.codex_home, self.workspace, profile)

    def test_installed_cli_disables_native_egress_features(self):
        import subprocess
        cli = shutil.which("codex")
        if cli is None:
            self.skipTest("installed Codex CLI unavailable")
        # features/list rejects --profile, so load the generated synthetic
        # profile as this isolated CODEX_HOME's base config for this check.
        (self.codex_home / "config.toml").write_text(self.profile)
        result = subprocess.run(
            [cli, *autonomous_turn_overrides(tomllib.loads(self.profile)), "features", "list"],
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "CODEX_HOME": str(self.codex_home),
                 "XDG_CONFIG_HOME": str(self.root / "config"), "XDG_STATE_HOME": str(self.root / "state"),
                 "XDG_CACHE_HOME": str(self.root / "cache")},
            cwd=self.workspace, capture_output=True, text=True, timeout=5, check=False,
        )
        self.assertEqual(result.returncode, 0)
        states = {line.split()[0]: line.split()[-1] for line in result.stdout.splitlines()}
        for name in (
            "shell_tool", "apps", "plugins", "browser_use", "computer_use", "image_generation",
            "view_image", "workspace_dependencies", "multi_agent", "code_mode_host", "hooks",
            "in_app_browser", "skill_mcp_dependency_install", "remote_plugin", "shell_snapshot",
        ):
            self.assertEqual(states.get(name), "false", name)

    def test_profile_has_no_filesystem_writes_or_network_and_no_native_search(self):
        profile = tomllib.loads(self.profile)
        profile["permissions"]["sentry-resident"]["filesystem"]["/synthetic/extra"] = "write"
        values = self.overlay_values(autonomous_turn_overrides(profile))
        def access_modes(node):
            if isinstance(node, dict):
                return [access for child in node.values() for access in access_modes(child)]
            return [node]
        self.assertNotIn("write", access_modes(values["permissions.sentry-resident.filesystem"]))
        self.assertEqual(values["web_search"], "disabled")
        self.assertEqual(values["skills.config"], [])
        self.assertIs(profile["permissions"]["sentry-resident"]["network"]["enabled"], False)

    def test_private_optin_builds_source_with_exact_existing_agent_without_claim(self):
        settings = json.loads(self.config.read_text())
        self.assertIsNone(configured_attention_source(self.agent))
        settings["auto_wake"] = {
            "enabled": True, "context_ready": False, "enabled_at": self.enable_epoch.isoformat(),
            "household_id": self.household_id,
        }
        self.config.write_text(json.dumps(settings))
        self.assertIsNone(configured_attention_source(self.agent))
        settings["auto_wake"]["context_ready"] = True
        self.config.write_text(json.dumps(settings))
        source = configured_attention_source(self.agent)
        self.assertIs(source.agent, self.agent)
        self.assertTrue(source.persistent_history_allowed)
        self.assertEqual(source.not_before, self.enable_epoch)
        self.client.call.assert_not_called()

    def test_voice_startup_resolves_same_singleton_source_not_new_brain(self):
        from tools import sentry_ask
        from tools.sentry_always_on_voice import _optional_anima_events
        settings = json.loads(self.config.read_text())
        settings["auto_wake"] = {
            "enabled": True, "context_ready": True, "enabled_at": self.enable_epoch.isoformat(),
            "household_id": self.household_id,
        }
        self.config.write_text(json.dumps(settings))
        with patch.object(sentry_ask, "_AGENT", self.agent):
            source = _optional_anima_events(Mock())
        self.assertIs(source.agent, self.agent)
        self.client.call.assert_not_called()

    def test_invalid_autowake_optin_leaves_ordinary_voice_without_private_error_text(self):
        from tools.sentry_always_on_voice import _optional_anima_events
        diagnostics = Mock()
        with patch("tools.sentry_always_on_voice.configured_anima_events", side_effect=ValueError("secret")):
            self.assertIsNone(_optional_anima_events(diagnostics))
        diagnostics.update.assert_called_once_with(anima_event_status="NOT_READY", anima_event_exception_type="ValueError")

    def test_autowake_never_invents_epoch_or_accepts_arbitrary_config_fields(self):
        settings = json.loads(self.config.read_text())
        for bad in (
            {"enabled": True, "context_ready": True, "household_id": self.household_id},
            {"enabled": True, "context_ready": True, "household_id": self.household_id,
             "enabled_at": self.enable_epoch.isoformat(), "role": "owner"},
        ):
            settings["auto_wake"] = bad
            self.config.write_text(json.dumps(settings))
            with self.assertRaises(ValueError):
                configured_attention_source(self.agent)
        self.client.call.assert_not_called()

    def test_lost_exact_claim_is_empty_not_another_candidate_or_model(self):
        self.client.call.side_effect = [
            {"status": "AVAILABLE", "items": [self.queue_claim()]}, {"status": "EMPTY"},
        ]
        self.assertEqual(self.queue_source()()["status"], "EMPTY")
        self.assertEqual(self.client.call.call_count, 2)
        self.client.provider_start.assert_not_called()

    def test_age_filter_rejects_recent_epoch_but_stale_or_future_item_before_claim(self):
        for delta in (-121, 30):
            self.enable_epoch = datetime.now(timezone.utc) - timedelta(seconds=300)
            self.serve_queue(self.queue_claim(created_at=(datetime.now(timezone.utc) + timedelta(seconds=delta)).isoformat()))
            self.client.call.reset_mock()
            self.assertEqual(self.queue_source()()["status"], "UNKNOWN_RESULT")
            self.client.call.assert_called_once()
        self.client.provider_start.assert_not_called()

    def test_process_group_cancelled_and_pipes_closed_after_lease_loss(self):
        import subprocess
        lease = SimpleNamespace(cancelled=Mock(), remaining_seconds=10)
        lease.cancelled.is_set.side_effect = [False, True]
        process = Mock()
        process.pid = 123456789
        process.poll.return_value = None
        with patch("subprocess.Popen", return_value=process), patch("os.killpg") as kill, self.assertRaises(subprocess.TimeoutExpired):
            _event_process(["codex"], lease, input="synthetic", timeout=10)
        kill.assert_called_once()
        process.communicate.assert_not_called()
        for pipe in (process.stdin, process.stdout, process.stderr):
            pipe.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
