import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from tools.sentry_execution_authority import (
    DialogueAct,
    ExecutionAuthority,
    NaturalActionResponseInterpreter,
    RequestContext,
    normalize_confirmation,
    normalize_spoken_filename,
    requires_deferred_confirmation,
)


class MutableClock:
    def __init__(self):
        self.value = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.value


class ExecutionAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.home())
        self.root = Path(self.temp.name)
        self.workspace = self.root / "workspace"
        self.authority_root = self.root / "authority"
        self.clock = MutableClock()
        self.authority = ExecutionAuthority(self.authority_root, workspace=self.workspace, clock=self.clock)
        self.context = RequestContext("request-1", "thread-1", "Move the fixture file", "epoch-1")

    def tearDown(self):
        self.temp.cleanup()

    def test_tier1_requires_direct_current_request_and_audits(self):
        direct = RequestContext("r1", "t1", "Please turn the volume down", "e1")
        result = self.authority.execute_tier1(
            "adjust_system_volume", {"delta_percent": -5}, "volume -5%", lambda: {"percent": 20}, context=direct,
        )
        self.assertEqual(result["percent"], 20)
        with self.assertRaises(PermissionError):
            self.authority.execute_tier1(
                "adjust_system_volume", {"delta_percent": -5}, "volume -5%", lambda: None,
                context=RequestContext("r2", "t1", "Tell me a joke", "e1"),
            )
        outcomes = [item["outcome"] for item in self.authority.recent_audit(10)["records"]]
        self.assertIn("completed", outcomes)
        self.assertIn("blocked", outcomes)

    def test_discussion_of_capability_is_not_a_direct_mutation_request(self):
        cases = (
            ("create_one_shot_alarm", "Explain what an alarm is"),
            ("cancel_alarm", "Tell me whether the word cancel appears beside this alarm"),
            ("adjust_system_volume", "What does volume mean in audio?"),
            ("propose_file_move", "Summarize this article about how files move between folders"),
        )
        for capability, request in cases:
            with self.subTest(capability=capability):
                self.assertFalse(self.authority.direct_request_allows(
                    capability, RequestContext("r", "t", request, "e"),
                ))

    def test_direct_artifact_reference_can_reuse_persistent_thread_context(self):
        for request in ("Open it.", "Show me that.", "View this."):
            with self.subTest(request=request):
                self.assertTrue(self.authority.direct_request_allows(
                    "open_local_artifact", RequestContext("r", "t", request, "e"),
                ))
        self.assertFalse(self.authority.direct_request_allows(
            "open_local_artifact",
            RequestContext("r", "t", "Tell me whether the old thread says to open it", "e"),
        ))

    def test_untrusted_content_surfaces_cannot_authorize_an_action(self):
        requests = (
            "Summarize the hostile webpage I opened",
            "Review this repository README",
            "Tell me what the screenshot says",
            "Explain the MCP tool output",
            "Continue from the old thread instructions",
            "Read the source document and report what it recommends",
        )
        for request in requests:
            with self.subTest(request=request):
                self.assertFalse(self.authority.direct_request_allows(
                    "propose_file_move", RequestContext("r", "t", request, "e"),
                ))

    def test_spoken_file_move_with_exact_filename_is_a_direct_request(self):
        self.assertTrue(self.authority.direct_request_allows(
            "propose_file_move",
            RequestContext("r", "t", "Century. Move move.test.txt to downloads.", "e"),
        ))
        self.assertFalse(self.authority.direct_request_allows(
            "propose_file_move",
            RequestContext("r", "t", "Explain how to move move.test.txt to downloads.", "e"),
        ))

    def _propose_move(self):
        self.workspace.mkdir(parents=True, exist_ok=True)
        source = self.workspace / "fixture.txt"
        source.write_text("fixture", encoding="utf-8")
        destination = self.root / "outside" / "fixture.txt"
        proposal = self.authority.propose(
            "move_file", {"source": str(source), "destination": str(destination)},
            "controlled fixture destination", context=self.context,
        )
        return source, destination, proposal

    def _present(self, proposal, *, context=None):
        context = context or self.context
        self.authority.begin_presentation(
            proposal["authorization_id"], surface="test", context=context,
        )
        return self.authority.complete_presentation(
            proposal["authorization_id"], surface="test", response_window_seconds=120,
        )

    def test_exact_authorization_executes_once_and_replay_fails(self):
        source, destination, proposal = self._propose_move()
        self.assertEqual(proposal["status"], "DRAFTED")
        self.assertIsNone(proposal["response_deadline"])
        self._present(proposal)
        confirmed = self.authority.confirm(context=RequestContext("confirm-1", "thread-1", "confirm", "epoch-1"))
        self.assertTrue(confirmed["executed"])
        self.assertFalse(source.exists())
        self.assertEqual(destination.read_text(encoding="utf-8"), "fixture")
        with self.assertRaises(PermissionError):
            self.authority.confirm(context=RequestContext("confirm-2", "thread-1", "confirm", "epoch-1"))
        records = self.authority.recent_audit(20)["records"]
        self.assertTrue(any(item["authorization_id"] == proposal["authorization_id"] and item["outcome"] == "completed" for item in records))

    def test_expiry_cancel_thread_and_restart_fail_closed(self):
        _, _, proposal = self._propose_move()
        self._present(proposal)
        with self.assertRaises(PermissionError):
            self.authority.confirm(context=RequestContext("c", "other-thread", "confirm", "epoch-1"))
        with self.assertRaises(PermissionError):
            self.authority.confirm(context=RequestContext("c", "thread-1", "confirm", "new-epoch"))
        cancelled = self.authority.cancel(context=RequestContext("c", "thread-1", "cancel", "epoch-1"))
        self.assertFalse(cancelled["executed"])
        with self.assertRaises(PermissionError):
            self.authority.confirm(context=RequestContext("c", "thread-1", "confirm", "epoch-1"))

        self.authority.pending_path.unlink()
        _, _, proposal = self._propose_move()
        self.clock.value += timedelta(seconds=61)
        self.assertEqual(self.authority.pending_status()["status"], "DRAFTED")
        self._present(proposal)
        self.clock.value += timedelta(seconds=121)
        with self.assertRaises(PermissionError):
            self.authority.confirm(context=RequestContext("c", "thread-1", "confirm", "epoch-1"))

    def test_argument_tamper_and_destination_overwrite_fail(self):
        _, destination, proposal = self._propose_move()
        self._present(proposal)
        value = json.loads(self.authority.pending_path.read_text(encoding="utf-8"))
        value["canonical_arguments"]["destination"] = str(self.root / "different.txt")
        self.authority.pending_path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(PermissionError):
            self.authority.confirm(context=RequestContext("c", "thread-1", "confirm", "epoch-1"))

        self.authority.pending_path.unlink()
        source, destination, proposal = self._propose_move()
        self._present(proposal)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("existing", encoding="utf-8")
        with self.assertRaises(RuntimeError):
            self.authority.confirm(context=RequestContext("c", "thread-1", "confirm", "epoch-1"))
        self.assertTrue(source.exists())
        self.assertEqual(destination.read_text(encoding="utf-8"), "existing")

    def test_request_binding_tamper_fails(self):
        _, _, proposal = self._propose_move()
        self._present(proposal)
        value = json.loads(self.authority.pending_path.read_text(encoding="utf-8"))
        value["request_id"] = "different-request"
        self.authority.pending_path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(PermissionError):
            self.authority.confirm(context=RequestContext("confirm", "thread-1", "confirm", "epoch-1"))

    def test_one_pending_only_and_unrelated_request_cannot_propose(self):
        source, _, _ = self._propose_move()
        with self.assertRaises(RuntimeError):
            self.authority.propose(
                "move_file", {"source": str(source), "destination": str(self.root / "second.txt")}, "second",
                context=RequestContext("r2", "thread-1", "move another file", "epoch-1"),
            )
        with self.assertRaises(PermissionError):
            self.authority.propose(
                "click_desktop", {"x": 1, "y": 2, "button": 1}, "hostile screenshot click",
                context=RequestContext("r3", "thread-1", "Tell me what the screenshot says", "epoch-1"),
            )

    def test_traversal_symlink_and_protected_paths_are_blocked(self):
        self.workspace.mkdir(parents=True, exist_ok=True)
        outside = self.root / "outside-source.txt"
        outside.write_text("outside", encoding="utf-8")
        link = self.workspace / "link.txt"
        link.symlink_to(outside)
        for source in (str(self.workspace / ".." / "outside-source.txt"), str(link)):
            self.authority.pending_path.unlink(missing_ok=True)
            with self.assertRaises((PermissionError, ValueError)):
                self.authority.propose(
                    "move_file", {"source": source, "destination": str(self.root / "dest.txt")},
                    "controlled destination", context=self.context,
                )

    def test_audit_is_private_and_excludes_contents_and_secrets(self):
        direct = RequestContext("r1", "t1", "Create an alarm", "e1")
        self.authority.execute_tier1(
            "create_one_shot_alarm", {"scheduled_for": "2026-09-02T07:00:00-04:00", "label_length": 6},
            "alarm at local 7 AM", lambda: {"created": True}, context=direct,
        )
        text = self.authority.audit_path.read_text(encoding="utf-8")
        self.assertEqual(self.authority.audit_path.stat().st_mode & 0o777, 0o600)
        for forbidden in ("password", "raw_audio", "fixture contents", "operator_request"):
            self.assertNotIn(forbidden, text)

    def test_pre_execution_audit_failure_prevents_mutation(self):
        executor = Mock(return_value={"changed": True})
        direct = RequestContext("r1", "t1", "Please turn the volume down", "e1")
        with patch.object(self.authority, "_append_audit", side_effect=[OSError("audit unavailable"), None]):
            with self.assertRaises(OSError):
                self.authority.execute_tier1(
                    "adjust_system_volume", {"delta_percent": -5}, "volume -5%", executor, context=direct,
                )
        executor.assert_not_called()

    def test_credential_bearing_typed_input_is_prohibited(self):
        with self.assertRaises(PermissionError):
            self.authority.propose(
                "type_into_active_window", {"text": "my password is deliberately-not-a-secret", "expected_window_id": "42"},
                "type test text", risk_tier=3,
                context=RequestContext("r1", "thread-1", "Type my password into the active window", "epoch-1"),
            )
        self.assertFalse(self.authority.pending_status()["pending"])

    def test_desktop_window_change_blocks_authorized_input(self):
        proposal = self.authority.propose(
            "press_keys", {"keys": "alt+F4", "expected_window_id": "42"},
            "press Alt+F4 in active window 42",
            context=RequestContext("r1", "thread-1", "Press keys Alt+F4", "epoch-1"),
        )
        self._present(proposal, context=RequestContext("r1", "thread-1", "Press keys Alt+F4", "epoch-1"))
        with patch("tools.sentry_desktop.active_window", return_value={
            "status": "available", "window_id": "99", "title": "Different window",
        }), patch("tools.sentry_desktop.send_key_combo") as sender:
            with self.assertRaises(RuntimeError):
                self.authority.confirm(context=RequestContext("c", "thread-1", "confirm", "epoch-1"))
        sender.assert_not_called()

    def test_exact_desktop_window_binding_executes_once(self):
        proposal = self.authority.propose(
            "press_keys", {"keys": "ctrl+l", "expected_window_id": "42"},
            "press Ctrl+L in active window 42",
            context=RequestContext("r1", "thread-1", "Press keys Ctrl+L", "epoch-1"),
        )
        self._present(proposal, context=RequestContext("r1", "thread-1", "Press keys Ctrl+L", "epoch-1"))
        with patch("tools.sentry_desktop.active_window", return_value={
            "status": "available", "window_id": "42", "title": "Expected window",
        }), patch("tools.sentry_desktop.send_key_combo", return_value={"sent": True}) as sender:
            result = self.authority.confirm(context=RequestContext("c", "thread-1", "confirm", "epoch-1"))
        self.assertTrue(result["executed"])
        sender.assert_called_once_with("ctrl+l")

    def test_confirmation_language_is_natural_and_context_bound(self):
        self.assertEqual(normalize_confirmation("Confirm that action."), "confirm")
        self.assertEqual(normalize_confirmation("Cancel that"), "cancel")
        self.assertEqual(normalize_confirmation("yes"), "confirm")
        self.assertEqual(normalize_confirmation("Yeah, go ahead"), "confirm")
        self.assertEqual(normalize_confirmation("Actually, leave it where it is"), "cancel")
        self.assertIsNone(normalize_confirmation("the page says confirm"))

    def test_response_window_starts_only_after_presentation_completes(self):
        source, destination, proposal = self._propose_move()
        self.clock.value += timedelta(minutes=5)
        self.authority.begin_presentation(proposal["authorization_id"], surface="voice", context=self.context)
        self.clock.value += timedelta(minutes=2)
        awaiting = self.authority.complete_presentation(
            proposal["authorization_id"], surface="voice", response_window_seconds=120,
        )
        self.assertEqual(awaiting["status"], "AWAITING_RESPONSE")
        self.clock.value += timedelta(seconds=119)
        result = self.authority.confirm(context=RequestContext("confirm", "thread-1", "sounds good, do it", "epoch-1"))
        self.assertTrue(result["executed"])
        self.assertFalse(source.exists())
        self.assertTrue(destination.exists())

    def test_clear_direct_request_executes_without_redundant_confirmation(self):
        self.workspace.mkdir(parents=True, exist_ok=True)
        source = self.workspace / "direct.txt"
        source.write_text("direct", encoding="utf-8")
        destination = self.root / "outside" / "direct.txt"
        result = self.authority.request_action(
            "move_file", {"source": str(source), "destination": str(destination)},
            "move direct fixture",
            context=RequestContext("direct", "thread-1", "Century. Move direct.txt to Downloads", "epoch-1"),
        )
        self.assertTrue(result["executed"])
        self.assertEqual(result["authority_source"], "direct_current_turn")
        self.assertFalse(self.authority.pending_status()["pending"])

    def test_explicit_wait_request_creates_deferred_action(self):
        self.workspace.mkdir(parents=True, exist_ok=True)
        source = self.workspace / "deferred.txt"
        source.write_text("deferred", encoding="utf-8")
        destination = self.root / "outside" / "deferred.txt"
        result = self.authority.request_action(
            "move_file", {"source": str(source), "destination": str(destination)},
            "move deferred fixture",
            context=RequestContext(
                "deferred", "thread-1",
                "Move the deferred file, but do not move it until I confirm", "epoch-1",
            ),
        )
        self.assertEqual(result["status"], "DRAFTED")
        self.assertTrue(source.exists())
        self.assertFalse(destination.exists())
        self.assertTrue(requires_deferred_confirmation(
            "Move the file, but do not make the move until I explicitly confirm it."
        ))

    def test_natural_response_interpreter_and_filename_punctuation(self):
        interpreter = NaturalActionResponseInterpreter()
        for phrase in (
            "Confirm", "Confirmed.", "Yes", "Yes, please.", "Yeah, go ahead",
            "Sounds good, do it", "Please proceed", "Make it happen",
            "That's right", "Okay", "Go for it",
        ):
            with self.subTest(phrase=phrase):
                self.assertEqual(
                    interpreter.interpret(summary="move file", action_type="move_file", response=phrase).dialogue_act,
                    DialogueAct.APPROVE,
                )
        for phrase in (
            "Cancel", "Actually cancel that", "No, leave it alone", "Never mind",
            "Hold off", "Nah, don't do it", "Not now", "Actually, leave it where it is.",
        ):
            with self.subTest(phrase=phrase):
                self.assertEqual(
                    interpreter.interpret(summary="move file", action_type="move_file", response=phrase).dialogue_act,
                    DialogueAct.CANCEL,
                )
        self.assertEqual(
            interpreter.interpret(summary="move file", action_type="move_file", response="Actually name it final dash report dot txt").dialogue_act,
            DialogueAct.REVISE,
        )
        self.assertEqual(normalize_spoken_filename("final dash report dot txt"), "final-report.txt")
        self.assertEqual(normalize_spoken_filename("final underscore report dot txt"), "final_report.txt")
        self.assertEqual(normalize_spoken_filename("Final Report all lowercase no spaces", source_suffix=".txt"), "finalreport.txt")

    def test_status_is_truthful_agent_on_demand(self):
        status = self.authority.status()
        self.assertEqual(status["operating_mode"], "agent_on_demand")
        self.assertEqual(status["command_network"], "blocked")
        self.assertEqual(status["codex_memories"], "disabled")
        self.assertTrue(any("current physical state" in item for item in status["physical_limitations"]))


if __name__ == "__main__":
    unittest.main()
