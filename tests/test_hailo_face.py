from __future__ import annotations

import unittest
from datetime import UTC, datetime
from uuid import UUID

from perception.hailo_face import (
    HailoFaceConfig,
    HailoFaceRuntime,
    HailoFaceUnavailable,
    parse_observation,
)


class HailoFaceTests(unittest.TestCase):
    def test_hailo_config_is_commissioned_and_camera_is_fixed(self) -> None:
        with self.assertRaisesRegex(ValueError, "fixed"):
            HailoFaceConfig.from_mapping(
                {
                    "device_path": "/dev/hailo0",
                    "detection_hef": "/opt/anima/detection.hef",
                    "recognition_hef": "/opt/anima/recognition.hef",
                    "hailo_apps_root": "/opt/hailo-apps",
                    "input_device": "/dev/video1",
                }
            )

    def test_hailo_runtime_reports_missing_model_gate_without_faking_availability(self) -> None:
        self.assertFalse(HailoFaceRuntime(HailoFaceConfig.from_mapping({})).status()["available"])
        runtime = HailoFaceRuntime(HailoFaceConfig())
        status = runtime.status()
        self.assertFalse(status["available"])
        self.assertIn("detection_hef", status["missing"])
        with self.assertRaisesRegex(HailoFaceUnavailable, "HAILO_FACE_MODELS_OR_RUNTIME_UNAVAILABLE"):
            runtime.command()

    def test_hailo_observation_is_bounded_and_identity_is_typed(self) -> None:
        person_id = UUID("00000000-0000-0000-0000-000000000013")
        result = parse_observation(
            {
                "observed_at": datetime.now(UTC).isoformat(),
                "track_id": 4,
                "identity_state": "recognized",
                "person_id": str(person_id),
                "confidence": 0.93,
            }
        )
        self.assertEqual(result.person_id, person_id)
        self.assertEqual(result.to_payload()["identity_state"], "recognized")
        with self.assertRaisesRegex(ValueError, "unexpected"):
            parse_observation({"observed_at": datetime.now(UTC).isoformat(), "frame": "raw"})
