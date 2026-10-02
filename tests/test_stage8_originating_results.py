"""Host playback composition only; no provider, owner profile, model or audio."""

import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from tools.sentry_anima_events import AttentionQueueSource, configured_attention_source


class OriginatingResultTests(unittest.TestCase):
    def setUp(self):
        self.source = AttentionQueueSource(object(), household_id=str(uuid4()),
            not_before=datetime.now(timezone.utc)-timedelta(seconds=1),
            enabled=True, context_ready=True)
        self.calls = []
        self.claim = {"status": "CLAIMED", "request_id": str(uuid4()), "generation": 1,
            "delivery_token": "synthetic-reply-token", "active_instance_id": "office",
            "phase": "APPROVAL", "announcement": {"text": "The approved action's outcome is unknown. It will not be replayed."}}
        self.started_ack = "RECORDED"
        self.client = Mock()
        self.client.call.side_effect = self.call
        self.speaker = SimpleNamespace(is_speaking=False, speak_with_timing=Mock(return_value={
            "delivered": True, "playback_state": "DELIVERED", "timing_source": "SYNTHETIC_CALLBACK", "actual_audible_start_at": None}))
        patched = patch("tools.sentry_anima.AnimaConfig.load", return_value=SimpleNamespace(client=lambda: self.client))
        patched.start()
        self.addCleanup(patched.stop)

    def call(self, path, body):
        self.calls.append((path, body))
        if path == "/v1/provider/alerts/next":
            return {"status": "EMPTY"}
        if path.endswith("/next"):
            return self.claim
        if body["outcome"] == "PLAYBACK_INTENT":
            return {"status": self.started_ack, "delivery_status": "PLAYBACK_INTENT"}
        return {"status": "RECORDED", "delivery_status": "PENDING" if body["outcome"] == "UNSTARTED" else body["outcome"]}

    def test_verified_reply_uses_current_host_playback_without_model_or_action(self):
        self.source._halted = True
        self.source._lock.acquire()
        self.addCleanup(self.source._lock.release)
        result = self.source.deliver_required(speaker=self.speaker)
        self.assertEqual(result["delivery_status"], "DELIVERED")
        self.speaker.speak_with_timing.assert_called_once_with(self.claim["announcement"]["text"])
        self.assertEqual([path for path, _ in self.calls], ["/v1/provider/alerts/next",
            "/v1/provider/approval-results/next", "/v1/provider/approval-results/receipt",
            "/v1/provider/approval-results/receipt"])
        self.assertTrue(self.source._halted)

    def test_busy_reply_unstarted_and_denied_intent_never_speaks(self):
        self.speaker.is_speaking = True
        self.assertEqual(self.source.deliver_required(speaker=self.speaker)["delivery_status"], "PENDING")
        self.speaker.speak_with_timing.assert_not_called()
        self.speaker.is_speaking = False
        self.started_ack = "EMPTY"
        self.assertEqual(self.source.deliver_required(speaker=self.speaker)["delivery_status"], "NOT_ATTEMPTED")
        self.speaker.speak_with_timing.assert_not_called()

    def test_mandatory_alert_first_has_no_optional_reply_dependency(self):
        original = self.call
        def current(path, body):
            if path == "/v1/provider/alerts/next":
                self.calls.append((path, body))
                return {**self.claim, "phase": "CANONICAL", "announcement": {"text": "Canonical alert."}}
            if "approval-results" in path:
                raise AssertionError("Optional reply on mandatory critical path")
            return original(path, body)
        self.client.call.side_effect = current
        self.assertEqual(self.source.deliver_required(speaker=self.speaker)["delivery_status"], "DELIVERED")
        self.speaker.speak_with_timing.assert_called_once_with("Canonical alert.")

    def test_autonomous_opt_out_retains_direct_drain_with_zero_reasoning(self):
        config = SimpleNamespace(path="synthetic-not-read", client=lambda: self.client)
        for settings in [{}, {"auto_wake": {"enabled": False, "context_ready": False,
                "household_id": self.source.household_id,
                "enabled_at": self.source.not_before.isoformat()}}]:
            with patch("tools.sentry_anima.AnimaConfig.load", return_value=config), patch(
                    "tools.sentry_anima.private_json", return_value=settings), patch.object(
                    AttentionQueueSource, "warm_runtime") as preflight, patch(
                    "tools.sentry_anima_events.run_resident_event") as cognition:
                source = configured_attention_source(object())
                self.assertIsNotNone(source)
                self.assertFalse(source.enabled)
                self.assertEqual(source()["gate"], "AUTONOMOUS_NOT_ENABLED")
                self.assertEqual(source.deliver_required(speaker=self.speaker)["delivery_status"], "DELIVERED")
                preflight.assert_not_called()
                cognition.assert_not_called()

    def test_optional_outage_is_not_empty_and_does_not_speak(self):
        original = self.call
        def unavailable(path, body):
            if path == "/v1/provider/approval-results/next":
                raise OSError("Synthetic private message must not escape")
            return original(path, body)
        self.client.call.side_effect = unavailable
        result = self.source.deliver_required(speaker=self.speaker)
        self.assertEqual(result, {"status": "NOT_READY", "delivery_status": "NOT_ATTEMPTED",
            "reason": "ORIGINATING_RESULT_TRANSPORT_UNAVAILABLE", "exception_type": "OSError"})
        self.speaker.speak_with_timing.assert_not_called()
