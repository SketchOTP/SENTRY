"""Deterministic managed alert transport; no model, Core or physical audio."""

import hashlib
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from tools.sentry_anima_events import AttentionQueueSource, configured_attention_source


class RequiredAlertDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.source = AttentionQueueSource(object(), household_id=str(uuid4()),
            not_before=datetime.now(timezone.utc) - timedelta(seconds=1), enabled=True, context_ready=True)
        self.claim = {"status": "CLAIMED", "request_id": str(uuid4()), "generation": 1,
            "delivery_token": "isolated-token", "active_instance_id": "office", "phase": "CANONICAL",
            "announcement": {"text": "Canonical isolated alert."}}
        self.calls = []
        self.client = Mock()
        self.client.call.side_effect = self.call
        self.speaker = SimpleNamespace(is_speaking=False, speak_with_timing=Mock(return_value={
            "delivered": True, "playback_state": "DELIVERED", "timing_source": "LOCAL_PLAYBACK_PROCESS",
            "playback_process_started_at": "isolated-process-time",
            "playback_completed_at": "isolated-completion-time", "actual_audible_start_at": None}))
        config = patch("tools.sentry_anima.AnimaConfig.load", return_value=SimpleNamespace(client=lambda: self.client))
        config.start()
        self.addCleanup(config.stop)

    def call(self, path, body):
        self.calls.append((path, body))
        if path.endswith("/next"):
            return self.claim
        return {"status": "RECORDED", "delivery_status": {"UNSTARTED": "PENDING",
            "PLAYBACK_INTENT": "PLAYBACK_INTENT"}.get(body.get("outcome"), body.get("outcome"))}

    def test_latched_model_and_held_turn_do_not_block_separately_fenced_speech(self):
        self.source._halted = True
        self.source._lock.acquire()
        self.addCleanup(self.source._lock.release)
        def spoken(text):
            self.assertEqual(self.calls[-1][1]["outcome"], "PLAYBACK_INTENT")
            return {"delivered": True, "playback_state": "DELIVERED",
                    "timing_source": "LOCAL_PLAYBACK_PROCESS", "actual_audible_start_at": None}
        self.speaker.speak_with_timing.side_effect = spoken
        result = self.source.deliver_required(speaker=self.speaker)
        self.assertEqual(result["delivery_status"], "DELIVERED")
        self.assertTrue(self.source._halted)
        self.assertEqual([body.get("outcome") for _, body in self.calls], [None, "PLAYBACK_INTENT", "DELIVERED"])
        self.assertIsNone(self.calls[-1][1]["evidence"]["actual_audible_start_at"])

    def test_busy_retains_pending_without_start_and_failure_is_unknown(self):
        self.speaker.is_speaking = True
        self.assertEqual(self.source.deliver_required(speaker=self.speaker)["delivery_status"], "PENDING")
        self.speaker.speak_with_timing.assert_not_called()
        self.assertNotIn("PLAYBACK_INTENT", [body.get("outcome") for _, body in self.calls])
        self.speaker.is_speaking = False
        self.speaker.speak_with_timing.side_effect = RuntimeError("isolated playback uncertainty")
        self.assertEqual(self.source.deliver_required(speaker=self.speaker)["delivery_status"], "UNKNOWN")
        self.assertEqual(self.calls[-1][1]["outcome"], "PLAYBACK_INTENT")

    def test_unstarted_is_only_retryable_speech_outcome(self):
        for state, expected in [("UNSTARTED", "PENDING"), ("STARTED", "UNKNOWN"), ("UNKNOWN", "UNKNOWN")]:
            self.speaker.speak_with_timing.return_value = {"delivered": False, "playback_state": state}
            self.assertEqual(self.source.deliver_required(speaker=self.speaker)["delivery_status"], expected)

    def test_accountable_followup_waits_for_canonical_and_missing_content_escalates(self):
        text = "Different useful context."
        request = self.claim["request_id"]
        original_claim = self.claim
        self.claim = {"status": "EMPTY"}
        def failed_ack(path, body):
            if path.endswith("/followup-ready"):
                raise OSError("PRIVATE notification payload must not escape")
            return self.call(path, body)
        self.client.call.side_effect = failed_ack
        with patch("tools.sentry_anima_events.run_resident_event", return_value={
                "status": "COMPLETED", "request_id": request, "followup_queued": True,
                "pending_followup": text}):
            result = self.source()
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["followup_content_status"], "ACK_PENDING")
        self.assertEqual(result["followup_ack_exception_type"], "OSError")
        self.assertNotIn("pending_followup", result)
        self.source._halted = True
        result = self.source.deliver_required(speaker=self.speaker)
        self.assertEqual(result, {"status": "EMPTY", "delivery_status": "NOT_ATTEMPTED",
            "followup_content_status": "ACK_PENDING", "followup_ack_exception_type": "OSError"})
        self.assertIn(request, self.source._followups)
        self.assertNotIn(request, self.source._followup_ready)
        self.assertTrue(self.source._halted)
        self.speaker.speak_with_timing.assert_not_called()
        self.client.call.side_effect = self.call
        result = self.source.deliver_required(speaker=self.speaker)
        self.assertNotIn("followup_content_status", result)
        self.assertIsNone(self.source._followup_ack_fault)
        self.assertIn(request, self.source._followup_ready)
        self.assertTrue(self.source._halted)
        self.claim = original_claim
        self.source.deliver_required(speaker=self.speaker)
        self.speaker.speak_with_timing.assert_called_once_with("Canonical isolated alert.")
        self.claim.update(phase="FOLLOWUP", announcement={"response_digest": hashlib.sha256(text.encode()).hexdigest()})
        self.source.deliver_required(speaker=self.speaker)
        self.speaker.speak_with_timing.assert_called_with(text)
        self.assertNotIn(request, self.source._followups)
        self.source.deliver_required(speaker=self.speaker)
        self.assertEqual(self.calls[-1][1]["outcome"], "CONTENT_UNAVAILABLE")
        self.assertEqual(self.speaker.speak_with_timing.call_count, 2)

    def test_empty_poll_never_speaks_or_announces_work(self):
        self.claim = {"status": "EMPTY"}
        started = Mock()
        self.assertEqual(self.source.deliver_required(speaker=self.speaker, on_speech_started=started)["status"], "EMPTY")
        started.assert_not_called()
        self.speaker.speak_with_timing.assert_not_called()

    def test_missing_cli_auth_or_preflight_does_not_remove_mandatory_source(self):
        configuration = {"auto_wake": {"enabled": True, "context_ready": True,
            "enabled_at": self.source.not_before.isoformat(), "household_id": self.source.household_id}}
        for failure in [FileNotFoundError("missing CLI"), PermissionError("missing model auth"),
                        ValueError("failed profile preflight")]:
            with patch("tools.sentry_anima.private_json", return_value=configuration), patch.object(
                    AttentionQueueSource, "warm_runtime", side_effect=failure), patch(
                    "tools.sentry_anima.AnimaConfig.load",
                    return_value=SimpleNamespace(path="isolated-path", client=lambda: self.client)):
                source = configured_attention_source(object())
                self.assertIsNotNone(source)
                self.assertEqual(source()["gate"], "REASONING_PREFLIGHT_UNAVAILABLE")
                source._next_preflight_retry = 0.0
                self.assertEqual(source()["gate"], "REASONING_PREFLIGHT_UNAVAILABLE")
                self.assertEqual(source.deliver_required(speaker=self.speaker)["delivery_status"], "DELIVERED")
