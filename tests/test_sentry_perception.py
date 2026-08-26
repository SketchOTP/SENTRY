import builtins
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from perception.sentry_perception import (
    CameraState,
    Detection,
    IoUTracker,
    LatestFrameBuffer,
    OpenVINOPersonDetector,
    PerceptionEngine,
    load_config,
    validate_config,
)
from perception.calibration import evaluate_thresholds


class FakeDetector:
    def __init__(self, frames):
        self.frames = iter(frames)

    def detect(self, image):
        return next(self.frames)


class PerceptionTests(unittest.TestCase):
    def test_config_requires_latest_frame_buffer(self):
        config = load_config(__import__("pathlib").Path("perception/config.example.json"))
        self.assertEqual(config["camera"]["buffer_size"], 1)
        config["camera"]["buffer_size"] = 2
        with self.assertRaises(ValueError):
            validate_config(config)

    def test_latest_frame_buffer_drops_stale_frame(self):
        buffer = LatestFrameBuffer()
        first = buffer.push("first")
        second = buffer.push("second")
        frame = buffer.pop_latest()
        self.assertEqual(first, 1)
        self.assertEqual(second, 2)
        self.assertEqual(frame.image, "second")
        self.assertEqual(buffer.dropped_frames, 1)

    def test_multiple_tracks_stay_stable_through_dropout(self):
        tracker = IoUTracker(max_missing_frames=2, match_iou_threshold=0.2, new_track_confidence_threshold=0.1)
        frame_one = tracker.update([
            Detection((0, 0, 100, 200), 0.9),
            Detection((300, 0, 400, 200), 0.8),
        ])
        frame_two = tracker.update([
            Detection((5, 0, 105, 200), 0.9),
            Detection((305, 0, 405, 200), 0.8),
        ])
        frame_three = tracker.update([])
        frame_four = tracker.update([
            Detection((10, 0, 110, 200), 0.9),
            Detection((310, 0, 410, 200), 0.8),
        ])
        self.assertEqual([person["track_id"] for person in frame_one], [1, 2])
        self.assertEqual([person["track_id"] for person in frame_two], [1, 2])
        self.assertEqual([person["track_id"] for person in frame_three], [1, 2])
        self.assertTrue(all(not person["visible"] for person in frame_three))
        self.assertEqual([person["track_id"] for person in frame_four], [1, 2])

    def test_engine_returns_structured_online_observation(self):
        detector = FakeDetector([[Detection((1, 2, 20, 40), 0.8)]])
        engine = PerceptionEngine(detector, IoUTracker(new_track_confidence_threshold=0.1))
        observation = engine.process(
            object(),
            frame_sequence=7,
            captured_at=datetime(2026, 8, 24, tzinfo=timezone.utc),
        )
        result = observation.as_dict()
        self.assertEqual(result["camera_state"], CameraState.ONLINE.value)
        self.assertEqual(result["frame_sequence"], 7)
        self.assertEqual(result["people"][0]["track_id"], 1)
        self.assertEqual(result["people"][0]["bbox"], [1, 2, 20, 40])

    def test_detector_output_contract(self):
        detector = OpenVINOPersonDetector({
            "model_xml": "perception-data/models/person-detection-0202/FP32/person-detection-0202.xml",
            "model_bin": "perception-data/models/person-detection-0202/FP32/person-detection-0202.bin",
            "device": "CPU",
            "confidence_threshold": 0.5,
        })
        import numpy as np

        detections = detector.detect(np.zeros((240, 320, 3), dtype=np.uint8))
        self.assertIsInstance(detections, list)
        for detection in detections:
            self.assertIsInstance(detection, Detection)
            self.assertGreaterEqual(detection.confidence, 0.0)
            self.assertLessEqual(detection.confidence, 1.0)

    def test_detector_decodes_person_boxes_and_filters_other_classes(self):
        import numpy as np

        output = np.full((1, 1, 200, 7), -1.0, dtype=np.float32)
        output[0, 0, 0] = [0, 0, 0.8, 0.1, 0.2, 0.6, 0.9]
        output[0, 0, 1] = [0, 1, 0.99, 0.0, 0.0, 1.0, 1.0]
        output[0, 0, 2] = [0, 0, 0.2, 0.0, 0.0, 1.0, 1.0]
        detections = OpenVINOPersonDetector._decode_detections(output, 320, 240, 0.5)
        self.assertEqual(len(detections), 1)
        for actual, expected in zip(detections[0].bbox, (32.0, 48.0, 192.0, 216.0)):
            self.assertAlmostEqual(actual, expected, places=4)
        self.assertAlmostEqual(detections[0].confidence, 0.8, places=6)

    def test_detector_decodes_raw_person_candidates_before_threshold(self):
        import numpy as np

        output = np.full((1, 1, 200, 7), -1.0, dtype=np.float32)
        output[0, 0, 0] = [0, 0, 0.2, 0.1, 0.2, 0.6, 0.9]
        output[0, 0, 1] = [0, 1, 0.99, 0.0, 0.0, 1.0, 1.0]
        raw = OpenVINOPersonDetector._decode_detections(output, 320, 240, None)
        filtered = [detection for detection in raw if detection.confidence >= 0.5]
        self.assertEqual(len(raw), 1)
        self.assertEqual(len(filtered), 0)
        self.assertAlmostEqual(raw[0].confidence, 0.2, places=6)

    def test_threshold_evaluation_uses_same_raw_records(self):
        records = [
            {"segment": "empty", "captured_at": "2026-08-26T15:00:00+00:00", "candidates": []},
            {"segment": "empty", "captured_at": "2026-08-26T15:00:01+00:00", "candidates": [{"confidence": 0.2}]},
            {"segment": "one_person", "captured_at": "2026-08-26T15:00:00+00:00", "candidates": [{"confidence": 0.2}]},
            {"segment": "one_person", "captured_at": "2026-08-26T15:00:01+00:00", "candidates": [{"confidence": 0.8}]},
        ]
        results = evaluate_thresholds(records, (0.1, 0.5))
        self.assertEqual(results["empty"]["0.10"]["zero_detections"], 1)
        self.assertEqual(results["empty"]["0.50"]["zero_detections"], 2)
        self.assertEqual(results["one_person"]["0.10"]["any_detection_rate"], 1.0)
        self.assertEqual(results["one_person"]["0.50"]["any_detection_rate"], 0.5)
        self.assertEqual(results["one_person"]["0.10"]["duplicate_detection_rate"], 0.0)

    def test_missing_model_fails_explicitly(self):
        with self.assertRaisesRegex(RuntimeError, "model XML file not found"):
            OpenVINOPersonDetector({
                "model_xml": str(Path("perception-data/models/person-detection-0202/FP32/missing.xml")),
                "model_bin": "perception-data/models/person-detection-0202/FP32/person-detection-0202.bin",
            })

    def test_corrupt_model_fails_explicitly(self):
        with tempfile.TemporaryDirectory() as directory:
            corrupt_bin = Path(directory) / "person-detection-0202.bin"
            corrupt_bin.write_bytes(b"corrupt model")
            with self.assertRaisesRegex(RuntimeError, "unable to load or compile OpenVINO model"):
                OpenVINOPersonDetector({
                    "model_xml": "perception-data/models/person-detection-0202/FP32/person-detection-0202.xml",
                    "model_bin": str(corrupt_bin),
                    "device": "CPU",
                })

    def test_openvino_unavailable_fails_explicitly(self):
        real_import = builtins.__import__

        def import_without_openvino(name, *args, **kwargs):
            if name == "openvino":
                raise ImportError("simulated missing OpenVINO")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=import_without_openvino):
            with self.assertRaisesRegex(RuntimeError, "openvino is required"):
                OpenVINOPersonDetector({})


if __name__ == "__main__":
    unittest.main()
