import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import numpy as np

from perception.identity import (
    FaceDetection,
    FaceQualityConfig,
    IdentityResolver,
    OpenCVFaceBackend,
    build_prototype,
    identity_config_from_mapping,
)
from perception.presence_store import PresenceStore
from perception.sentry_perception import CameraState, Detection, IoUTracker, PerceptionEngine
from perception.presence_state import PresenceStateConfig, PresenceStateMachine
from tools.sentry_state_api import _Handler


class FakeCV2:
    FaceRecognizerSF_FR_COSINE = 0


class FakeRecognizer:
    def __init__(self, score=0.9):
        self.score = score

    def match(self, query, prototype, method):
        return self.score


class FakeBackend:
    _cv2 = FakeCV2()

    def __init__(self, *, faces=None, accepted=True, score=0.9):
        self.faces = faces or []
        self.accepted = accepted
        self.recognizer = FakeRecognizer(score)

    def detect_faces(self, image):
        return self.faces

    def accepted_embedding(self, image, face):
        if not self.accepted:
            return None
        return np.array([1.0, 0.0, 0.0], dtype=np.float32), {"accepted": True, "sharpness": 100.0}


def person(track_id=1):
    return {"track_id": track_id, "bbox": [0, 0, 100, 200], "visible": True}


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.when = datetime(2026, 8, 29, tzinfo=timezone.utc)
        self.face = FaceDetection((20, 20, 60, 80), 0.99, tuple(float(v) for v in range(10)))
        self.profile = {"person_id": "primary_user", "prototype": np.array([1.0, 0.0, 0.0], dtype=np.float32)}

    def resolver(self, **kwargs):
        return IdentityResolver(
            FakeBackend(faces=kwargs.pop("faces", [self.face]), **kwargs),
            profile_provider=lambda: self.profile,
            confirmation_count=3,
            confirmation_window_seconds=2.0,
        )

    def test_identity_states_are_conservative(self):
        no_face = self.resolver(faces=[])
        self.assertEqual(no_face.resolve(object(), [person()], self.when)[0]["identity_state"], "unresolved")
        ambiguous = self.resolver(faces=[self.face, self.face])
        self.assertEqual(ambiguous.resolve(object(), [person()], self.when)[0]["identity_state"], "unresolved")
        poor = self.resolver(accepted=False)
        self.assertEqual(poor.resolve(object(), [person()], self.when)[0]["identity_state"], "unresolved")
        nonmatch = self.resolver(score=0.2)
        self.assertEqual(nonmatch.resolve(object(), [person()], self.when)[0]["identity_state"], "unknown")

    def test_face_to_person_association_requires_unique_geometry(self):
        outside = FaceDetection((200, 20, 60, 80), 0.99, tuple(float(v) for v in range(10)))
        result = self.resolver(faces=[outside]).resolve(object(), [person()], self.when)
        self.assertEqual(result[0]["identity_state"], "unresolved")

    def test_three_matching_observations_confirm_identity(self):
        resolver = self.resolver()
        results = [resolver.resolve(object(), [person()], self.when + timedelta(seconds=offset))[0] for offset in (0, 0.5, 1.0)]
        self.assertEqual([result["identity_state"] for result in results], ["unresolved", "unresolved", "recognized"])
        self.assertEqual(results[-1]["person_id"], "primary_user")

    def test_calibrated_profile_threshold_overrides_starting_config(self):
        self.profile["calibrated_threshold"] = 0.95
        resolver = self.resolver(score=0.90)
        result = resolver.resolve(object(), [person()], self.when)[0]
        self.assertEqual(result["identity_state"], "unknown")

    def test_confirmation_window_expires_and_face_loss_is_unresolved(self):
        resolver = self.resolver()
        resolver.resolve(object(), [person()], self.when)
        resolver.resolve(object(), [person()], self.when + timedelta(seconds=0.5))
        expired = resolver.resolve(object(), [person()], self.when + timedelta(seconds=3.0))
        self.assertEqual(expired[0]["identity_state"], "unresolved")
        self.assertEqual(resolver.resolve(object(), [person()], self.when + timedelta(seconds=3.5))[0]["identity_state"], "unresolved")

    def test_prototype_is_normalized_mean(self):
        prototype = build_prototype([np.array([2.0, 0.0]), np.array([0.0, 2.0])])
        self.assertAlmostEqual(float(np.linalg.norm(prototype)), 1.0, places=6)
        self.assertAlmostEqual(float(prototype[0]), float(prototype[1]), places=6)

    def test_config_is_explicit_and_validated(self):
        config = identity_config_from_mapping({"enabled": False, "match_threshold": 0.45})
        self.assertEqual(config["confirmation_count"], 3)
        with self.assertRaises(ValueError):
            identity_config_from_mapping({"enabled": True})
        with self.assertRaises(ValueError):
            FaceQualityConfig.from_mapping({"min_face_size": 0})

    def test_models_load_and_zero_frame_has_no_face(self):
        root = Path("perception-data/models/opencv-zoo")
        backend = OpenCVFaceBackend({
            "yunet_model": str(root / "yunet/face_detection_yunet_2023mar.onnx"),
            "sface_model": str(root / "sface/face_recognition_sface_2021dec.onnx"),
            "yunet_sha256": "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
            "sface_sha256": "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
        })
        self.assertEqual(backend.detect_faces(np.zeros((240, 320, 3), dtype=np.uint8)), [])

    def test_profile_persists_deletes_and_is_not_exposed_by_api(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sentry.db"
            with PresenceStore(path) as store:
                store.enroll_identity(
                    person_id="primary_user", display_name="Operator", backend="opencv_yunet_sface",
                    model_version="opencv_zoo@test", model_checksum="sha256:test",
                    prototype=np.array([1.0, 0.0, 0.0], dtype=np.float32), calibrated_threshold=0.45,
                    sample_count=16, created_at="2026-08-29T12:00:00+00:00",
                )
                self.assertEqual(store.persons()[0]["person_id"], "primary_user")
                self.assertNotIn("prototype", store.persons()[0])
                profile = store.identity_profile()
                self.assertEqual(profile["sample_count"], 16)
                self.assertAlmostEqual(float(np.linalg.norm(profile["prototype"])), 1.0, places=6)
                server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
                server.store = store
                thread = Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                    connection.request("GET", "/v1/persons")
                    response = connection.getresponse()
                    payload = json.loads(response.read())
                    self.assertEqual(response.status, 200)
                    self.assertEqual(payload["persons"][0]["display_name"], "Operator")
                    self.assertNotIn("prototype", payload["persons"][0])
                    connection.close()
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=5)
                store.delete_identity()
                self.assertEqual(store.persons(), [])

    def test_identity_annotation_does_not_change_room_presence_and_event_is_deduplicated(self):
        class FakeDetector:
            confidence_threshold = 0.8

            def detect(self, image):
                return [Detection((0, 0, 100, 200), 0.9)]

        class FakeResolver:
            def resolve(self, image, people, evaluated_at):
                return [{**people[0], "person_id": "primary_user", "identity_state": "recognized", "identity_confidence": 0.9}]

        engine = PerceptionEngine(
            FakeDetector(), IoUTracker(new_track_confidence_threshold=0.1),
            PresenceStateMachine(PresenceStateConfig(entry_confirmation_seconds=0.1)),
            identity_resolver=FakeResolver(), identity_cadence_seconds=0.01,
        )
        first = engine.process(object(), frame_sequence=1, captured_at=self.when)
        second = engine.process(object(), frame_sequence=2, captured_at=self.when + timedelta(seconds=1))
        self.assertEqual(first.room_state.value, "empty")
        self.assertEqual(second.room_state.value, "occupied")
        self.assertEqual(second.people[0]["identity_state"], "recognized")

        with tempfile.TemporaryDirectory() as directory, PresenceStore(Path(directory) / "sentry.db") as store:
            for observation in (first, second):
                store.record_observation(observation)
            third = engine.process(object(), frame_sequence=3, captured_at=self.when + timedelta(seconds=2))
            store.record_observation(third)
            identified = [event for event in store.events() if event["event_type"] == "person.identified"]
            self.assertEqual(len(identified), 1)
            self.assertNotIn("prototype", identified[0]["payload"])

    def test_identity_failure_keeps_presence_and_marks_people_unresolved(self):
        class FakeDetector:
            confidence_threshold = 0.8

            def detect(self, image):
                return [Detection((0, 0, 100, 200), 0.9)]

        class FailingResolver:
            def resolve(self, image, people, evaluated_at):
                raise RuntimeError("face backend unavailable")

            @staticmethod
            def _unresolved(people):
                return [{**value, "person_id": None, "identity_state": "unresolved"} for value in people]

        engine = PerceptionEngine(
            FakeDetector(), IoUTracker(new_track_confidence_threshold=0.1),
            PresenceStateMachine(PresenceStateConfig(entry_confirmation_seconds=0.1)),
            identity_resolver=FailingResolver(), identity_cadence_seconds=0.01,
        )
        engine.process(object(), frame_sequence=1, captured_at=self.when)
        observation = engine.process(object(), frame_sequence=2, captured_at=self.when + timedelta(seconds=1))
        self.assertEqual(observation.room_state, "occupied")
        self.assertEqual(observation.people[0]["identity_state"], "unresolved")
        self.assertIn("face backend unavailable", observation.identity_error)

    def test_profile_survives_atlas_snapshot_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local, atlas = root / "local" / "sentry.db", root / "atlas" / "sentry.db"
            with PresenceStore(local, atlas_mirror_path=atlas) as store:
                store.enroll_identity(
                    person_id="primary_user", display_name="Operator", backend="opencv_yunet_sface",
                    model_version="v", model_checksum="s", prototype=np.array([1.0, 0.0]),
                    calibrated_threshold=0.45, sample_count=16,
                )
            local.unlink()
            with PresenceStore(local, atlas_mirror_path=atlas) as restored:
                self.assertEqual(restored.identity_profile()["person_id"], "primary_user")

    def test_one_active_enrolled_identity_is_enforced(self):
        with tempfile.TemporaryDirectory() as directory, PresenceStore(Path(directory) / "sentry.db") as store:
            kwargs = dict(backend="opencv_yunet_sface", model_version="v", model_checksum="s", prototype=np.ones(3), calibrated_threshold=0.45, sample_count=16)
            store.enroll_identity(person_id="primary_user", display_name="Operator", **kwargs)
            with self.assertRaisesRegex(ValueError, "exactly one"):
                store.enroll_identity(person_id="other", display_name="Other", **kwargs)


if __name__ == "__main__":
    unittest.main()
