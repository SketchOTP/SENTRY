import unittest
from datetime import datetime, timedelta, timezone

from perception.calibration import evaluate_asymmetric_thresholds


class AsymmetricCalibrationTests(unittest.TestCase):
    def _record(self, segment, seconds, confidence=None):
        candidates = [] if confidence is None else [{"confidence": confidence, "bbox": [0, 0, 1, 1]}]
        return {
            "segment": segment,
            "captured_at": (datetime(2026, 8, 28, tzinfo=timezone.utc) + timedelta(seconds=seconds)).isoformat(),
            "candidates": candidates,
        }

    def test_weak_support_can_qualify_hold_without_starting_occupancy(self):
        records = [self._record("empty", seconds) for seconds in range(0, 21)]
        records += [self._record("one_person", 0, 0.50), self._record("one_person", 1, 0.50)]
        records += [self._record("one_person", seconds, 0.25) for seconds in range(2, 21)]
        result = evaluate_asymmetric_thresholds(records, support_thresholds=(0.20, 0.40))
        self.assertIn("0.20", result["qualifying_support_thresholds"])
        self.assertNotIn("0.40", result["qualifying_support_thresholds"])
        self.assertEqual(result["thresholds"]["0.20"]["occupied"]["strong_evidence_observations"], 2)
        self.assertEqual(result["thresholds"]["0.20"]["occupied"]["false_empty_transition"], False)

    def test_sparse_false_support_still_allows_bounded_exit(self):
        records = [self._record("empty", seconds, 0.20 if seconds == 0 else None) for seconds in range(0, 21)]
        result = evaluate_asymmetric_thresholds(records, support_thresholds=(0.20,))
        exit_result = result["thresholds"]["0.20"]["post_exit_empty"]
        self.assertTrue(exit_result["reaches_empty_within_25s"])
        self.assertLessEqual(exit_result["simulated_empty_seconds"], 25.0)


if __name__ == "__main__":
    unittest.main()
