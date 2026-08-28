import unittest
from datetime import datetime, timedelta, timezone

from perception.presence_state import (
    PresenceStateConfig,
    PresenceStateMachine,
    RoomState,
    measure_image_quality,
)


class PresenceStateMachineTests(unittest.TestCase):
    def setUp(self):
        self.origin = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)
        self.config = PresenceStateConfig(
            entry_confirmation_seconds=1.0,
            entry_evidence_gap_seconds=1.0,
            absence_grace_seconds=15.0,
        )

    def at(self, seconds: float) -> datetime:
        return self.origin + timedelta(seconds=seconds)

    def test_empty_becomes_occupied_after_sufficient_positive_evidence(self):
        machine = PresenceStateMachine(self.config)
        self.assertEqual(machine.update(self.at(0), camera_state="online", human_evidence=True).state, RoomState.EMPTY)
        self.assertEqual(machine.update(self.at(0.8), camera_state="online", human_evidence=True).state, RoomState.EMPTY)
        result = machine.update(self.at(1.1), camera_state="online", human_evidence=True)
        self.assertEqual(result.state, RoomState.OCCUPIED)
        self.assertEqual(result.transition, "empty->occupied")

    def test_single_frame_positive_below_confirmation_does_not_create_occupancy(self):
        machine = PresenceStateMachine(self.config)
        machine.update(self.at(0), camera_state="online", human_evidence=True)
        result = machine.update(self.at(1.1), camera_state="online", human_evidence=False)
        self.assertEqual(result.state, RoomState.EMPTY)

    def test_short_detector_dropout_while_occupied_remains_occupied(self):
        machine = PresenceStateMachine(self.config)
        machine.update(self.at(0), camera_state="online", human_evidence=True)
        machine.update(self.at(1.1), camera_state="online", human_evidence=True)
        result = machine.update(self.at(5), camera_state="online", human_evidence=False)
        self.assertEqual(result.state, RoomState.OCCUPIED)

    def test_long_absence_while_camera_usable_becomes_empty(self):
        machine = PresenceStateMachine(self.config)
        machine.update(self.at(0), camera_state="online", human_evidence=True)
        machine.update(self.at(1.1), camera_state="online", human_evidence=True)
        result = machine.update(self.at(16.2), camera_state="online", human_evidence=False)
        self.assertEqual(result.state, RoomState.EMPTY)
        self.assertEqual(result.transition, "occupied->empty")

    def test_camera_degraded_overrides_occupancy_inference(self):
        machine = PresenceStateMachine(self.config)
        machine.update(self.at(0), camera_state="online", human_evidence=True)
        machine.update(self.at(1.1), camera_state="online", human_evidence=True)
        result = machine.update(self.at(2), camera_state="degraded", human_evidence=True)
        self.assertEqual(result.state, RoomState.DEGRADED)

    def test_camera_offline_overrides_occupancy_inference(self):
        machine = PresenceStateMachine(self.config)
        machine.update(self.at(0), camera_state="online", human_evidence=True)
        machine.update(self.at(1.1), camera_state="online", human_evidence=True)
        result = machine.update(self.at(2), camera_state="offline", human_evidence=True)
        self.assertEqual(result.state, RoomState.OFFLINE)

    def test_detector_exception_cannot_create_empty_truth(self):
        machine = PresenceStateMachine(self.config)
        result = machine.update(
            self.at(0),
            camera_state="online",
            detector_usable=False,
        )
        self.assertEqual(result.state, RoomState.DEGRADED)

    def test_recovery_from_degraded_resumes_evaluation(self):
        machine = PresenceStateMachine(self.config)
        machine.update(self.at(0), camera_state="degraded")
        machine.update(self.at(1), camera_state="online", human_evidence=True)
        result = machine.update(self.at(2.1), camera_state="online", human_evidence=True)
        self.assertEqual(result.state, RoomState.OCCUPIED)

    def test_recovery_after_confirmed_occupancy_holds_until_grace_expires(self):
        machine = PresenceStateMachine(self.config)
        machine.update(self.at(0), camera_state="online", human_evidence=True)
        machine.update(self.at(1.1), camera_state="online", human_evidence=True)
        machine.update(self.at(2), camera_state="offline")
        result = machine.update(self.at(5), camera_state="online", human_evidence=False)
        self.assertEqual(result.state, RoomState.OCCUPIED)
        result = machine.update(self.at(17.1), camera_state="online", human_evidence=False)
        self.assertEqual(result.state, RoomState.EMPTY)

    def test_unconfirmed_entry_does_not_survive_source_loss(self):
        machine = PresenceStateMachine(self.config)
        machine.update(self.at(0), camera_state="online", human_evidence=True)
        machine.update(self.at(0.5), camera_state="offline")
        result = machine.update(self.at(5), camera_state="online", human_evidence=False)
        self.assertEqual(result.state, RoomState.EMPTY)

    def test_detector_failure_while_occupied_never_reports_empty(self):
        machine = PresenceStateMachine(self.config)
        machine.update(self.at(0), camera_state="online", human_evidence=True)
        machine.update(self.at(1.1), camera_state="online", human_evidence=True)
        result = machine.update(self.at(2), camera_state="online", detector_usable=False)
        self.assertEqual(result.state, RoomState.DEGRADED)
        result = machine.update(self.at(5), camera_state="online", human_evidence=False)
        self.assertEqual(result.state, RoomState.OCCUPIED)

    def test_duplicate_detections_are_binary_occupied_evidence(self):
        machine = PresenceStateMachine(self.config)
        machine.update(self.at(0), camera_state="online", human_evidence=True)
        result = machine.update(self.at(1.1), camera_state="online", human_evidence=True)
        self.assertEqual(result.state, RoomState.OCCUPIED)

    def test_support_evidence_cannot_start_occupancy(self):
        machine = PresenceStateMachine(self.config)
        machine.update(self.at(0), camera_state="online", entry_evidence=False, support_evidence=True)
        result = machine.update(self.at(1.1), camera_state="online", entry_evidence=False, support_evidence=True)
        self.assertEqual(result.state, RoomState.EMPTY)

    def test_support_evidence_refreshes_confirmed_occupancy(self):
        machine = PresenceStateMachine(self.config)
        machine.update(self.at(0), camera_state="online", entry_evidence=True, support_evidence=True)
        machine.update(self.at(1.1), camera_state="online", entry_evidence=True, support_evidence=True)
        self.assertEqual(
            machine.update(self.at(10), camera_state="online", entry_evidence=False, support_evidence=True).state,
            RoomState.OCCUPIED,
        )
        self.assertEqual(
            machine.update(self.at(25.1), camera_state="online", entry_evidence=False, support_evidence=False).state,
            RoomState.EMPTY,
        )

    def test_support_evidence_stops_and_occupancy_exits_within_grace(self):
        machine = PresenceStateMachine(self.config)
        machine.update(self.at(0), camera_state="online", entry_evidence=True, support_evidence=True)
        machine.update(self.at(1.1), camera_state="online", entry_evidence=True, support_evidence=True)
        result = machine.update(self.at(16.2), camera_state="online", entry_evidence=False, support_evidence=False)
        self.assertEqual(result.state, RoomState.EMPTY)
        self.assertLessEqual((result.evaluated_at - self.at(1.1)).total_seconds(), 15.1)

    def test_entry_timing_uses_elapsed_time_not_update_count(self):
        machine = PresenceStateMachine(self.config)
        machine.update(self.at(0), camera_state="online", human_evidence=True)
        for seconds in (0.1, 0.2, 0.3, 0.4, 0.5):
            self.assertEqual(
                machine.update(self.at(seconds), camera_state="online", human_evidence=True).state,
                RoomState.EMPTY,
            )
        self.assertEqual(
            machine.update(self.at(1.01), camera_state="online", human_evidence=True).state,
            RoomState.OCCUPIED,
        )

    def test_image_quality_returns_metadata_only_luminance_metrics(self):
        import numpy as np

        image = np.zeros((2, 2, 3), dtype=np.uint8)
        image[0, 0] = (255, 255, 255)
        metrics = measure_image_quality(image)
        self.assertGreater(metrics.mean_luminance, 0)
        self.assertGreaterEqual(metrics.dynamic_range, 0)
        self.assertIn("contrast_stddev", metrics.as_dict())


if __name__ == "__main__":
    unittest.main()
