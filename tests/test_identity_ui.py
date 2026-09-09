import json
import tempfile
import threading
import unittest
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import numpy as np

from tools.sentry_identity_enrollment import IdentityEnrollmentManager, MINIMUM_SAMPLES
from tools.sentry_state_api import _Handler


class FakeFaceBackend:
    def __init__(self, _config):
        pass

    @staticmethod
    def detect_faces(_image):
        return [object()]

    @staticmethod
    def accepted_embedding(_image, _face):
        return np.array([1.0, 0.0, 0.0], dtype=np.float32), {
            "accepted": True,
            "sharpness": 100.0,
        }

    @staticmethod
    def pose_metrics(_face, pose):
        return {"pose": pose, "accepted": True}


class FakeCapture:
    def __init__(self, *_args):
        self.released = False

    @staticmethod
    def isOpened():
        return True

    @staticmethod
    def set(*_args):
        return True

    @staticmethod
    def read():
        return True, np.zeros((120, 160, 3), dtype=np.uint8)

    def release(self):
        self.released = True


@contextmanager
def unlocked(**_kwargs):
    yield


class IdentityUiTests(unittest.TestCase):
    def manager(self, directory):
        config = json.loads(Path("perception/config.example.json").read_text(encoding="utf-8"))
        config["storage"] = {
            "database_path": str(Path(directory) / "sentry.db"),
            "atlas_mirror_path": None,
            "mirror_interval_seconds": 60,
        }
        path = Path(directory) / "config.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        with patch("tools.sentry_identity_enrollment.OpenCVFaceBackend", FakeFaceBackend):
            return IdentityEnrollmentManager(path)

    def test_enrollment_persists_named_profiles_without_raw_photos(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = self.manager(directory)
            first = manager.start("Sketch", MINIMUM_SAMPLES)
            session = manager._session(first["session_id"])
            session.embeddings.extend([np.array([1.0, 0.0, 0.0])] * MINIMUM_SAMPLES)
            result = manager.commit(first["session_id"])
            self.assertEqual(result["display_name"], "Sketch")
            self.assertFalse(result["raw_images_persisted"])
            with manager._store() as store:
                first_revision = store.identity_profile_revision()
            second = manager.start("Guest User", MINIMUM_SAMPLES)
            other = manager._session(second["session_id"])
            other.embeddings.extend([np.array([0.0, 1.0, 0.0])] * MINIMUM_SAMPLES)
            manager.commit(second["session_id"])
            with manager._store() as store:
                second_revision = store.identity_profile_revision()
            self.assertNotEqual(first_revision, second_revision)
            self.assertEqual([item["display_name"] for item in manager.profiles()], ["Guest User", "Sketch"])
            self.assertEqual(
                sorted(path.suffix for path in Path(directory).iterdir() if path.is_file()),
                [".db", ".json"],
            )

    def test_deliberate_capture_returns_preview_but_writes_no_image(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = self.manager(directory)
            started = manager.start("Camera User", MINIMUM_SAMPLES)
            with (
                patch("tools.sentry_identity_enrollment.cv2.VideoCapture", FakeCapture),
                patch("tools.sentry_identity_enrollment.camera_activity_lock", unlocked),
                patch("tools.sentry_identity_enrollment.cv2.imencode", return_value=(True, np.array([1, 2, 3], dtype=np.uint8))),
            ):
                result = manager.capture(started["session_id"])
            self.assertTrue(result["accepted"])
            self.assertEqual(result["accepted_samples"], 1)
            self.assertEqual(result["preview_jpeg_base64"], "AQID")
            self.assertFalse(result["frame_persisted"])
            self.assertFalse(any(path.suffix.lower() in {".jpg", ".jpeg", ".png"} for path in Path(directory).iterdir()))

    def test_operator_can_review_and_remove_bad_ephemeral_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = self.manager(directory)
            started = manager.start("Camera User", MINIMUM_SAMPLES)
            with (
                patch("tools.sentry_identity_enrollment.cv2.VideoCapture", FakeCapture),
                patch("tools.sentry_identity_enrollment.camera_activity_lock", unlocked),
                patch("tools.sentry_identity_enrollment.cv2.imencode", return_value=(True, np.array([1, 2, 3], dtype=np.uint8))),
            ):
                captured = manager.capture(started["session_id"], "straight")
            sample = captured["samples"][0]
            self.assertEqual(sample["preview_jpeg_base64"], "AQID")
            removed = manager.remove_sample(started["session_id"], sample["sample_id"])
            self.assertEqual(removed["accepted_samples"], 0)
            self.assertEqual(removed["samples"], [])
            self.assertEqual(removed["accepted_poses"], {})

    def test_private_state_api_requires_token_for_identity_workflow(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = self.manager(directory)
            store = manager._store()
            server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
            server.store = store
            server.identity_manager = manager
            server.identity_token = "t" * 64
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            url = f"http://127.0.0.1:{server.server_port}/v1/identity/enrollment/start"
            payload = json.dumps(
                {"person_id": "person-123", "display_name": "Test User", "guided": True}
            ).encode()
            try:
                with self.assertRaises(HTTPError) as denied:
                    urlopen(Request(url, data=payload, method="POST", headers={"Content-Type": "application/json"}), timeout=2)
                self.assertEqual(denied.exception.code, 401)
                response = urlopen(
                    Request(
                        url,
                        data=payload,
                        method="POST",
                        headers={
                            "Authorization": f"Bearer {'t' * 64}",
                            "Content-Type": "application/json",
                        },
                    ),
                    timeout=2,
                )
                started = json.loads(response.read())
                self.assertEqual(started["person_id"], "person-123")
                self.assertTrue(started["guided"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
                store.close()

    def test_cancel_discards_ephemeral_samples_and_validation_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = self.manager(directory)
            with self.assertRaises(ValueError):
                manager.start("", MINIMUM_SAMPLES)
            with self.assertRaises(ValueError):
                manager.start("Name", MINIMUM_SAMPLES - 1)
            started = manager.start("Name", MINIMUM_SAMPLES)
            manager._session(started["session_id"]).embeddings.append(np.ones(3))
            self.assertTrue(manager.cancel(started["session_id"])["cancelled"])
            with self.assertRaises(ValueError):
                manager._session(started["session_id"])

    def test_guided_enrollment_requires_and_records_all_head_poses(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = self.manager(directory)
            started = manager.start(
                "Guided User", MINIMUM_SAMPLES, profile_id="person-123", guided=True
            )
            with (
                patch("tools.sentry_identity_enrollment.cv2.VideoCapture", FakeCapture),
                patch("tools.sentry_identity_enrollment.camera_activity_lock", unlocked),
                patch("tools.sentry_identity_enrollment.cv2.imencode", return_value=(False, None)),
            ):
                for pose in ("straight", "left", "right", "up", "down"):
                    result = manager.capture(started["session_id"], pose)
                    self.assertTrue(result["accepted"])
            result = manager.commit(started["session_id"])
            self.assertEqual(result["person_id"], "person-123")
            self.assertEqual(set(result["accepted_poses"]), {"straight", "left", "right", "up", "down"})

if __name__ == "__main__":
    unittest.main()
