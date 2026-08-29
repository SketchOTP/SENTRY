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
    OpenVINOYOLOXSPersonDetector,
    PerceptionEngine,
    load_config,
    validate_config,
    yolox_decode_output,
    yolox_decode_reference_output,
    yolox_preprocess,
)
from perception.presence_state import PresenceStateConfig, PresenceStateMachine


class FakeDetector:
    def __init__(self, frames):
        self.frames = iter(frames)

    def detect(self, image):
        return next(self.frames)


class FakeRawDetector:
    confidence_threshold = 0.40

    def __init__(self, frames):
        self.frames = iter(frames)
        self.raw_calls = 0
        self.detect_calls = 0

    def detect_raw(self, image):
        self.raw_calls += 1
        return next(self.frames)

    def detect(self, image):
        self.detect_calls += 1
        raise AssertionError("raw-capable detector must not infer twice")


class PerceptionTests(unittest.TestCase):
    def test_config_requires_latest_frame_buffer(self):
        config = load_config(__import__("pathlib").Path("perception/config.example.json"))
        self.assertEqual(config["camera"]["buffer_size"], 1)
        config["camera"]["buffer_size"] = 2
        with self.assertRaises(ValueError):
            validate_config(config)

    def test_config_accepts_linux_v4l2_device_path_without_numeric_index(self):
        config = load_config(Path("perception/config.example.json"))
        config["camera"]["backend"] = "v4l2"
        config["camera"]["device_path"] = "/dev/v4l/by-id/example-video-index0"
        config["camera"].pop("index")
        validate_config(config)

    def test_config_accepts_ignored_presence_database_path(self):
        config = load_config(Path("perception/config.example.json"))
        self.assertEqual(config["storage"]["database_path"], "~/.local/share/sentry/sentry.db")
        self.assertEqual(config["storage"]["atlas_mirror_path"], "perception-data/runtime/backups/sentry.db")
        validate_config(config)

    def test_config_rejects_non_string_presence_database_path(self):
        config = load_config(Path("perception/config.example.json"))
        config["storage"]["database_path"] = 123
        with self.assertRaisesRegex(ValueError, "storage.database_path"):
            validate_config(config)

    def test_config_rejects_invalid_fourcc(self):
        config = load_config(Path("perception/config.example.json"))
        config["camera"]["fourcc"] = "MJ"
        with self.assertRaisesRegex(ValueError, "camera.fourcc"):
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

    def test_engine_exposes_binary_room_state_and_quality_metadata(self):
        import numpy as np

        detector = FakeDetector([
            [Detection((1, 2, 20, 40), 0.8)],
            [Detection((1, 2, 20, 40), 0.8)],
        ])
        engine = PerceptionEngine(
            detector,
            IoUTracker(new_track_confidence_threshold=0.1),
            PresenceStateMachine(PresenceStateConfig(entry_confirmation_seconds=1.0)),
        )
        image = np.zeros((10, 10, 3), dtype=np.uint8)
        first = engine.process(
            image,
            frame_sequence=1,
            captured_at=datetime(2026, 8, 27, tzinfo=timezone.utc),
        )
        second = engine.process(
            image,
            frame_sequence=2,
            captured_at=datetime(2026, 8, 27, 0, 0, 1, 100000, tzinfo=timezone.utc),
        )
        self.assertEqual(first.as_dict()["room_state"], "empty")
        self.assertEqual(second.as_dict()["room_state"], "occupied")
        self.assertEqual(second.as_dict()["room_state_transition"], "empty->occupied")
        self.assertTrue(second.as_dict()["detector_evidence"])
        self.assertIn("mean_luminance", second.as_dict()["image_quality"])
        self.assertEqual(second.as_dict()["candidates"][0]["confidence"], 0.8)

    def test_engine_uses_one_raw_inference_for_strong_and_support_evidence(self):
        detector = FakeRawDetector([
            [Detection((1, 2, 20, 40), 0.42)],
            [Detection((1, 2, 20, 40), 0.42)],
            [Detection((1, 2, 20, 40), 0.25)],
        ])
        engine = PerceptionEngine(
            detector,
            IoUTracker(new_track_confidence_threshold=0.1),
            PresenceStateMachine(PresenceStateConfig(entry_confirmation_seconds=1.0)),
            entry_confidence_threshold=0.40,
            hold_confidence_threshold=0.20,
        )
        import numpy as np

        image = np.zeros((10, 10, 3), dtype=np.uint8)
        first = engine.process(image, frame_sequence=1, captured_at=datetime(2026, 8, 27, tzinfo=timezone.utc))
        second = engine.process(
            image,
            frame_sequence=2,
            captured_at=datetime(2026, 8, 27, 0, 0, 1, 100000, tzinfo=timezone.utc),
        )
        third = engine.process(
            image,
            frame_sequence=3,
            captured_at=datetime(2026, 8, 27, 0, 0, 2, 100000, tzinfo=timezone.utc),
        )
        self.assertEqual(detector.raw_calls, 3)
        self.assertEqual(detector.detect_calls, 0)
        self.assertEqual(first.as_dict()["strong_detector_evidence"], True)
        self.assertEqual(first.as_dict()["support_detector_evidence"], True)
        self.assertEqual(second.as_dict()["strong_detector_evidence"], True)
        self.assertEqual(second.as_dict()["support_detector_evidence"], True)
        self.assertEqual(second.as_dict()["room_state"], "occupied")
        self.assertEqual(third.as_dict()["strong_detector_evidence"], False)
        self.assertEqual(third.as_dict()["support_detector_evidence"], True)
        self.assertEqual(third.as_dict()["room_state"], "occupied")

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

    def test_yolox_preprocess_preserves_aspect_ratio_and_top_left_padding(self):
        import numpy as np

        tensor, ratio = yolox_preprocess(np.zeros((720, 1280, 3), dtype=np.uint8))
        self.assertEqual(tensor.shape, (3, 640, 640))
        self.assertEqual(tensor.dtype, np.float32)
        self.assertAlmostEqual(ratio, 0.5)
        self.assertEqual(float(tensor[:, 400:, :].max()), 114.0)

    def test_yolox_decode_matches_winning_class_and_nms_semantics(self):
        import numpy as np

        output = np.zeros((1, 8400, 85), dtype=np.float32)
        output[0, 0, :6] = [10.0, 10.0, 3.0, 3.0, 0.9, 0.8]
        output[0, 1, :6] = [9.0, 10.0, 3.0, 3.0, 0.95, 0.9]
        output[0, 1, 6] = 0.99
        reference = yolox_decode_reference_output(
            output,
            width=1280,
            height=720,
            ratio=0.5,
            confidence_threshold=0.5,
            nms_threshold=0.45,
        )
        kept = [row for row in reference if row["nms_kept"]]
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["final_class_id"], 1)
        self.assertAlmostEqual(kept[0]["final_score"], 0.9405, places=5)
        detections = yolox_decode_output(
            output,
            width=1280,
            height=720,
            ratio=0.5,
            confidence_threshold=0.5,
            nms_threshold=0.45,
        )
        self.assertEqual(detections, [])

        person_only = np.zeros((1, 8400, 85), dtype=np.float32)
        person_only[0, 0, :6] = [10.0, 10.0, 3.0, 3.0, 0.9, 0.8]
        detections = yolox_decode_output(
            person_only,
            width=1280,
            height=720,
            ratio=0.5,
            confidence_threshold=0.5,
            nms_threshold=0.45,
        )
        self.assertEqual(len(detections), 1)
        self.assertAlmostEqual(detections[0].confidence, 0.72, places=5)
        for actual, expected in zip(detections[0].bbox, (0.0, 0.0, 320.6843, 320.6843)):
            self.assertAlmostEqual(actual, expected, places=3)

    def test_yolox_decode_rejects_nonpositive_and_malformed_output(self):
        import numpy as np

        output = np.zeros((1, 8400, 85), dtype=np.float32)
        output[0, 0, 4] = -1.0
        output[0, 0, 5] = 1.0
        self.assertEqual(
            yolox_decode_output(output, width=320, height=240, ratio=1.0, confidence_threshold=0.0),
            [],
        )
        with self.assertRaisesRegex(ValueError, "expected YOLOX output shape"):
            yolox_decode_output(np.zeros((1, 10, 85), dtype=np.float32), width=320, height=240, ratio=1.0, confidence_threshold=0.0)

    def test_yolox_config_and_official_ir_contract(self):
        config = load_config(Path("perception/config.example.json"))
        self.assertEqual(config["detector"]["name"], "openvino_yolox_s")
        detector = OpenVINOYOLOXSPersonDetector(config["detector"])
        import numpy as np

        raw = detector.detect_raw(np.zeros((240, 320, 3), dtype=np.uint8))
        self.assertIsInstance(raw, list)
        for detection in raw:
            self.assertIsInstance(detection, Detection)
            self.assertGreaterEqual(detection.confidence, 0.0)
            self.assertLessEqual(detection.confidence, 1.0)


if __name__ == "__main__":
    unittest.main()
