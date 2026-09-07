"""Synthetic lifecycle checks; no production claim, model, file, or TTS calls."""

import time
import unittest
from unittest.mock import Mock, patch

from tools.sentry_anima_events import EventResult, QueuedEventLease


class QueuedEventLeaseTests(unittest.TestCase):
    def setUp(self):
        self.request = "cb0f06e3-c10b-40a7-b661-a1a352fe26ec"
        self.household = "392c547b-6ccb-4861-8a49-335757663fa1"
        self.claim = {
            "status": "CLAIMED", "origin": "AUTONOMOUS_ATTENTION",
            "provider_id": "sentry", "request_id": self.request,
            "household_id": self.household, "fencing_generation": 4,
            "binding": "synthetic-private-binding",
        }
        self.client = Mock(spec=["provider_start", "renew", "submit_result"])
        self.client.provider_start.return_value = {"status": "PROVIDER_RUNNING"}
        self.client.renew.return_value = {"status": "RENEWED"}
        self.client.submit_result.return_value = {"status": "RECORDED"}
        self.revoke = Mock()

    def lease(self):
        return QueuedEventLease(
            self.client, self.claim, expected_request_id=self.request,
            household_id=self.household, deadline=time.monotonic() + 270,
            revoke=self.revoke,
        )

    def test_dormant_construction_has_no_client_calls(self):
        self.lease()
        self.assertEqual(self.client.mock_calls, [])

    def test_exact_claim_scope_required_before_start(self):
        for key, value in (
            ("origin", "DIRECT_SENTRY_INTERACTION"), ("provider_id", "other"),
            ("request_id", self.household), ("household_id", self.request),
            ("status", "PENDING"), ("fencing_generation", True),
            ("fencing_generation", 0), ("binding", ""),
        ):
            with (
                self.subTest(key=key, value=value),
                patch.dict(self.claim, {key: value}),
                self.assertRaises(ValueError),
            ):
                self.lease()
        self.assertEqual(self.client.mock_calls, [])

    def test_start_before_executor_revoke_before_single_actual_result(self):
        def execute(lease):
            self.client.provider_start.assert_called_once_with(self.request, self.claim["binding"])
            self.client.submit_result.assert_not_called()
            self.assertLessEqual(lease.remaining_seconds, 255)
            return EventResult("RESPONSE", "Synthetic actual final")

        def submit(*args, **kwargs):
            self.revoke.assert_called_once()
            self.assertEqual(kwargs["response"], "Synthetic actual final")
            return {"status": "RECORDED"}

        self.client.submit_result.side_effect = submit
        lease = self.lease()
        result = lease.run(execute)
        self.assertEqual(result["status"], "RECORDED")
        self.assertEqual(result["delivery_status"], "NOT_ATTEMPTED")
        self.assertNotIn("Synthetic actual final", str(result))
        self.client.renew.assert_not_called()
        with self.assertRaises(RuntimeError):
            lease.run(execute)
        self.client.submit_result.assert_called_once()

    def test_ambiguous_provider_start_never_executes_or_retries(self):
        self.client.provider_start.side_effect = OSError("PRIVATE ERROR CONTENT")
        execute = Mock()
        result = self.lease().run(execute)
        execute.assert_not_called()
        self.client.provider_start.assert_called_once()
        self.assertEqual(result["result_status"], "UNKNOWN_RESULT")
        self.assertEqual(result["stage"], "PROVIDER_START")
        self.assertEqual(result["exception_type"], "OSError")
        self.assertNotIn("PRIVATE", str(result))

    def test_executor_failure_is_unknown_without_error_text_or_replay(self):
        result = self.lease().run(Mock(side_effect=TimeoutError("PRIVATE")))
        self.assertEqual(result["result_status"], "UNKNOWN_RESULT")
        self.assertEqual(result["stage"], "EXECUTE")
        self.assertIsNone(self.client.submit_result.call_args.kwargs["response"])
        self.revoke.assert_called_once()

    def test_provider_start_consuming_execution_budget_never_runs_executor(self):
        lease = self.lease()

        def start(*args):
            lease.deadline = time.monotonic() + 10
            return {"status": "PROVIDER_RUNNING"}

        self.client.provider_start.side_effect = start
        execute = Mock()
        result = lease.run(execute)
        execute.assert_not_called()
        self.client.renew.assert_not_called()
        self.assertEqual(result["result_status"], "UNKNOWN_RESULT")

    def test_lease_loss_cancels_and_revokes_without_promoting_late_final(self):
        lease = self.lease()
        self.client.renew.return_value = {"status": "CLAIM_LOST"}
        # Run the real renewal path deterministically, without a 15-second wait.
        def execute(active):
            with patch.object(active._stop, "wait", return_value=False):
                active._renew()
            self.assertTrue(active.cancelled.is_set())
            self.revoke.assert_called_once()
            return EventResult("RESPONSE", "Must not be submitted")

        result = lease.run(execute)
        self.assertEqual(result["result_status"], "UNKNOWN_RESULT")
        self.assertIsNone(self.client.submit_result.call_args.kwargs["response"])
        self.client.renew.assert_called_once_with(self.request, self.claim["binding"])

    def test_core_gate_is_preserved_and_not_called_speech_delivery(self):
        result = self.lease().run(lambda _: EventResult("WAITING_STRONGER_AUTH"))
        self.assertEqual(result["result_status"], "WAITING_STRONGER_AUTH")
        self.assertEqual(result["delivery_status"], "NOT_ATTEMPTED")

    def test_submission_failure_not_retried(self):
        self.client.submit_result.side_effect = OSError("PRIVATE")
        result = self.lease().run(lambda _: EventResult("NO_ACTION"))
        self.assertEqual(result["status"], "UNKNOWN_RESULT")
        self.assertEqual(result["stage"], "RESULT_SUBMIT")
        self.client.submit_result.assert_called_once()

    def test_actual_recorded_status_supersedes_requested_response(self):
        self.client.submit_result.return_value = {"status": "RECORDED", "result_status": "NO_ACTION"}
        lease = self.lease()
        result = lease.run(lambda _: EventResult("RESPONSE", "Synthetic withheld response"))
        self.assertEqual(result["result_status"], "NO_ACTION")
        self.assertFalse(result["notification"]["allowed"])
        self.client.submit_result.assert_called_once()
        with self.assertRaises(RuntimeError):
            lease.run(lambda _: EventResult("RESPONSE", "Must never retry"))

    def test_legacy_recorded_response_is_not_authority_to_speak(self):
        result = self.lease().run(lambda _: EventResult("RESPONSE", "Synthetic final"))
        self.assertEqual(result["status"], "RECORDED")
        self.assertEqual(result["result_status"], "UNKNOWN_RESULT")
        self.assertFalse(result["notification"]["allowed"])
        self.client.submit_result.assert_called_once()

    def test_invalid_output_is_unknown(self):
        for output in (
            None, EventResult("invented"), EventResult("RESPONSE", ""), EventResult("RESPONSE", "x" * 4001),
            EventResult("PARTIAL", detail="PRIVATE MODEL CONTENT"),
            EventResult("NO_ACTION", detail="REQUIRED_NOTIFICATION_NOT_PRODUCED"),
        ):
            with self.subTest(output_type=type(output).__name__):
                result = self.lease().run(lambda _, value=output: value)
                self.assertEqual(result["result_status"], "UNKNOWN_RESULT")

    def test_revoke_failure_cannot_report_success(self):
        self.revoke.side_effect = OSError("PRIVATE")
        result = self.lease().run(lambda _: EventResult("RESPONSE", "Synthetic"))
        self.assertEqual(result["result_status"], "UNKNOWN_RESULT")
        self.assertEqual(result["stage"], "REVOKE")


if __name__ == "__main__":
    unittest.main()
