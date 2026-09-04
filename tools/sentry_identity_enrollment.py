"""Private local identity enrollment operations for the native SENTRY UI."""

from __future__ import annotations

import base64
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2

from perception.identity import OpenCVFaceBackend, build_prototype, identity_config_from_mapping
from perception.presence_store import PresenceStore
from perception.sentry_perception import load_config
from tools.sentry_office_vision import camera_activity_lock


MINIMUM_SAMPLES = 5
TARGET_SAMPLES = 8
MAXIMUM_SAMPLES = 16
SESSION_TTL_SECONDS = 20 * 60


def _person_slug(display_name: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", display_name.casefold()).strip("-")[:48]
    return value or f"user-{uuid.uuid4().hex[:8]}"


@dataclass
class EnrollmentSession:
    session_id: str
    person_id: str
    display_name: str
    target_samples: int
    created_at: float
    embeddings: list[Any] = field(default_factory=list)


class IdentityEnrollmentManager:
    """Own ephemeral enrollment samples and private profile persistence."""

    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path.expanduser()
        self.config = load_config(self.config_path)
        self.identity = identity_config_from_mapping(self.config.get("identity"))
        if not self.identity["enabled"]:
            raise RuntimeError("local SENTRY identity is disabled")
        self.backend = OpenCVFaceBackend(self.identity)
        self._sessions: dict[str, EnrollmentSession] = {}
        self._lock = threading.Lock()

    @property
    def storage(self) -> dict[str, Any]:
        return self.config["storage"]

    def _store(self) -> PresenceStore:
        return PresenceStore(
            self.storage["database_path"],
            atlas_mirror_path=self.storage.get("atlas_mirror_path"),
            mirror_interval_seconds=float(self.storage.get("mirror_interval_seconds", 60.0)),
        )

    def profiles(self) -> list[dict[str, Any]]:
        with self._store() as store:
            return store.persons()

    def _purge_expired(self) -> None:
        cutoff = time.monotonic() - SESSION_TTL_SECONDS
        self._sessions = {
            key: value for key, value in self._sessions.items() if value.created_at >= cutoff
        }

    def start(self, display_name: object, target_samples: object = TARGET_SAMPLES) -> dict[str, Any]:
        name = " ".join(str(display_name or "").split())
        if not 1 <= len(name) <= 64:
            raise ValueError("username must contain from 1 through 64 characters")
        try:
            target = int(target_samples)
        except (TypeError, ValueError) as exc:
            raise ValueError("target sample count must be an integer") from exc
        if not MINIMUM_SAMPLES <= target <= MAXIMUM_SAMPLES:
            raise ValueError(f"target sample count must be {MINIMUM_SAMPLES} through {MAXIMUM_SAMPLES}")
        existing = self.profiles()
        matching = next(
            (profile for profile in existing if str(profile["display_name"]).casefold() == name.casefold()),
            None,
        )
        base = str(matching["person_id"]) if matching else _person_slug(name)
        used = {str(profile["person_id"]) for profile in existing}
        person_id = base
        suffix = 2
        while person_id in used and matching is None:
            person_id = f"{base}-{suffix}"
            suffix += 1
        session = EnrollmentSession(
            session_id=str(uuid.uuid4()), person_id=person_id, display_name=name,
            target_samples=target, created_at=time.monotonic(),
        )
        with self._lock:
            self._purge_expired()
            self._sessions[session.session_id] = session
        return self._session_payload(session)

    @staticmethod
    def _session_payload(session: EnrollmentSession) -> dict[str, Any]:
        return {
            "session_id": session.session_id,
            "person_id": session.person_id,
            "display_name": session.display_name,
            "accepted_samples": len(session.embeddings),
            "target_samples": session.target_samples,
            "ready_to_save": len(session.embeddings) >= MINIMUM_SAMPLES,
        }

    def _session(self, session_id: str) -> EnrollmentSession:
        with self._lock:
            self._purge_expired()
            session = self._sessions.get(session_id)
        if session is None:
            raise ValueError("enrollment session is missing or expired")
        return session

    def capture(self, session_id: str) -> dict[str, Any]:
        session = self._session(session_id)
        if len(session.embeddings) >= session.target_samples:
            raise ValueError("the enrollment session already has its target samples")
        camera = self.config["camera"]
        source = camera.get("device_path") or int(camera.get("index", 0))
        backend_name = cv2.CAP_V4L2 if camera.get("backend") == "v4l2" else cv2.CAP_ANY
        with camera_activity_lock(timeout_seconds=5.0):
            capture = cv2.VideoCapture(source, backend_name)
            if not capture.isOpened():
                capture.release()
                raise RuntimeError("the office camera is unavailable or busy")
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, int(camera["width"]))
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, int(camera["height"]))
            capture.set(cv2.CAP_PROP_FPS, float(camera["fps"]))
            deadline = time.monotonic() + 2.5
            image = None
            try:
                while time.monotonic() < deadline:
                    ok, candidate = capture.read()
                    if not ok or candidate is None:
                        continue
                    image = candidate
                    faces = self.backend.detect_faces(image)
                    if len(faces) != 1:
                        continue
                    extracted = self.backend.accepted_embedding(image, faces[0])
                    if extracted is None:
                        continue
                    embedding, quality = extracted
                    with self._lock:
                        session.embeddings.append(embedding)
                    encoded, jpeg = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
                    preview = base64.b64encode(jpeg.tobytes()).decode("ascii") if encoded else None
                    return {
                        **self._session_payload(session),
                        "accepted": True,
                        "quality": {
                            key: round(value, 2) if isinstance(value, float) else value
                            for key, value in quality.items()
                        },
                        "preview_jpeg_base64": preview,
                        "frame_persisted": False,
                    }
                face_count = len(self.backend.detect_faces(image)) if image is not None else 0
                return {
                    **self._session_payload(session),
                    "accepted": False,
                    "reason": "expected exactly one clear, well-lit face",
                    "visible_faces": face_count,
                    "frame_persisted": False,
                }
            finally:
                capture.release()

    def commit(self, session_id: str) -> dict[str, Any]:
        session = self._session(session_id)
        if len(session.embeddings) < MINIMUM_SAMPLES:
            raise ValueError(f"at least {MINIMUM_SAMPLES} accepted samples are required")
        prototype = build_prototype(session.embeddings)
        with self._store() as store:
            store.enroll_identity(
                person_id=session.person_id,
                display_name=session.display_name,
                backend=self.identity.get("backend", "opencv_yunet_sface"),
                model_version=self.identity.get("model_version", "opencv_zoo@unknown"),
                model_checksum=f"yunet:{self.identity['yunet_sha256']};sface:{self.identity['sface_sha256']}",
                prototype=prototype,
                calibrated_threshold=float(self.identity["match_threshold"]),
                sample_count=len(session.embeddings),
            )
        with self._lock:
            self._sessions.pop(session_id, None)
        return {
            "ok": True,
            "person_id": session.person_id,
            "display_name": session.display_name,
            "accepted_samples": len(session.embeddings),
            "raw_images_persisted": False,
        }

    def cancel(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            removed = self._sessions.pop(session_id, None)
        return {"ok": True, "cancelled": removed is not None}

    def delete(self, person_id: str) -> dict[str, Any]:
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", person_id):
            raise ValueError("invalid person profile identifier")
        with self._store() as store:
            if store.identity_profile(person_id) is None:
                raise ValueError("identity profile not found")
            store.delete_identity(person_id)
        return {"ok": True, "deleted_person_id": person_id}


__all__ = [
    "IdentityEnrollmentManager", "MAXIMUM_SAMPLES", "MINIMUM_SAMPLES", "TARGET_SAMPLES",
]
