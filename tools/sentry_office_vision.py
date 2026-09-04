"""Explicit on-demand office camera inspection with local identity matching.

Frames are held only in memory. The enrolled biometric prototype never leaves
the local SENTRY store; only the resulting identity label and, when requested,
one user-authorized still image are returned to the calling Codex turn.
"""

from __future__ import annotations

import time
import fcntl
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2

from perception.identity import MultiProfileIdentityResolver, OpenCVFaceBackend, identity_config_from_mapping
from perception.presence_state import PresenceStateConfig, PresenceStateMachine
from perception.presence_store import PresenceStore
from perception.sentry_perception import IoUTracker, OpenVINOYOLOXSPersonDetector, PerceptionEngine, load_config


def _camera_lock_path() -> Path:
    runtime_root = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "sentry"
    runtime_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    runtime_root.chmod(0o700)
    return runtime_root / "camera.lock"


@contextmanager
def camera_activity_lock(*, timeout_seconds: float = 5.0):
    """Serialize every host-owned on-demand camera operation."""

    if timeout_seconds <= 0:
        raise ValueError("camera lock timeout must be positive")
    path = _camera_lock_path()
    with path.open("a+", encoding="utf-8") as lock_file:
        path.chmod(0o600)
        deadline = time.monotonic() + timeout_seconds
        while True:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("office camera is busy with another bounded inspection")
                time.sleep(0.05)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def inspect_office_camera(
    config_path: Path,
    *,
    duration_seconds: float = 3.0,
    include_image: bool = True,
    completion_timeout_seconds: float = 8.0,
) -> tuple[dict[str, Any], bytes | None]:
    """Capture a bounded live segment and return local identity metadata plus one JPEG."""

    if not 0.5 <= duration_seconds <= 8.0:
        raise ValueError("camera inspection duration must be from 0.5 through 8 seconds")
    if completion_timeout_seconds < duration_seconds:
        raise ValueError("camera completion timeout cannot be shorter than inspection duration")
    with camera_activity_lock(timeout_seconds=max(0.1, completion_timeout_seconds - duration_seconds)):
        return OfficeVisionInspector(config_path).inspect_locked(
            duration_seconds=duration_seconds, include_image=include_image,
        )


class OfficeVisionInspector:
    """Preload existing local models; open the camera only for bounded calls."""

    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path.expanduser()
        self.config = load_config(self.config_path)
        self.identity = identity_config_from_mapping(self.config.get("identity"))
        if not self.identity["enabled"]:
            raise RuntimeError("local SENTRY identity is disabled")
        storage = self.config["storage"]
        self.database_path = Path(storage["database_path"]).expanduser()
        self.backend = OpenCVFaceBackend(self.identity)
        self.detector = OpenVINOYOLOXSPersonDetector(self.config["detector"])

    def _load_profiles(self) -> list[dict[str, Any]]:
        with PresenceStore(self.database_path, atlas_mirror_path=None) as store:
            return store.identity_profiles()

    def profile_revision(self) -> str:
        """Return a privacy-safe revision that changes after enrollment edits."""

        with PresenceStore(self.database_path, atlas_mirror_path=None) as store:
            return store.identity_profile_revision()

    def inspect(
        self, *, duration_seconds: float = 3.0, include_image: bool = True,
        completion_timeout_seconds: float = 8.0,
    ) -> tuple[dict[str, Any], bytes | None]:
        if not 0.5 <= duration_seconds <= 8.0:
            raise ValueError("camera inspection duration must be from 0.5 through 8 seconds")
        if completion_timeout_seconds < duration_seconds:
            raise ValueError("camera completion timeout cannot be shorter than inspection duration")
        with camera_activity_lock(timeout_seconds=max(0.1, completion_timeout_seconds - duration_seconds)):
            return self.inspect_locked(duration_seconds=duration_seconds, include_image=include_image)

    def inspect_locked(
        self, *, duration_seconds: float, include_image: bool,
    ) -> tuple[dict[str, Any], bytes | None]:
        profiles = self._load_profiles()
        resolver = MultiProfileIdentityResolver(
            self.backend,
            confirmation_count=self.identity["confirmation_count"],
            confirmation_window_seconds=self.identity["confirmation_window_seconds"],
            profile_provider=lambda: profiles,
            minimum_separation=float(self.identity.get("minimum_profile_separation", 0.05)),
        )
        tracker = self.config["tracker"]
        engine = PerceptionEngine(
            self.detector,
            IoUTracker(
                match_iou_threshold=tracker["match_iou_threshold"],
                high_confidence_threshold=tracker["high_confidence_threshold"],
                new_track_confidence_threshold=tracker["new_track_confidence_threshold"],
                max_missing_frames=tracker["max_missing_frames"],
            ),
            PresenceStateMachine(PresenceStateConfig.from_mapping(self.config.get("presence"))),
            entry_confidence_threshold=float(self.config["detector"].get("confidence_threshold", 0.50)),
            hold_confidence_threshold=float(self.config["detector"].get("hold_confidence_threshold", 0.50)),
            identity_resolver=resolver,
            identity_cadence_seconds=self.identity["cadence_seconds"],
        )
        camera = self.config["camera"]
        source = camera.get("device_path") or int(camera.get("index", 0))
        capture = cv2.VideoCapture(source, cv2.CAP_V4L2 if camera.get("backend") == "v4l2" else cv2.CAP_ANY)
        if not capture.isOpened():
            capture.release()
            raise RuntimeError("configured office camera is unavailable or owned by another process")
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, int(camera["width"]))
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, int(camera["height"]))
        capture.set(cv2.CAP_PROP_FPS, float(camera["fps"]))
        started = time.monotonic()
        frame_count = 0
        latest_image: Any | None = None
        latest_observation: Any | None = None
        try:
            while time.monotonic() - started < duration_seconds:
                ok, image = capture.read()
                if not ok or image is None:
                    continue
                frame_count += 1
                observation = engine.process(image, frame_sequence=frame_count, captured_at=datetime.now(timezone.utc))
                latest_image = image
                latest_observation = observation
                recognized = any(person.get("identity_state") == "recognized" for person in observation.people)
                if recognized and time.monotonic() - started >= 1.0:
                    break
        finally:
            capture.release()
        if latest_observation is None or latest_image is None:
            raise RuntimeError("office camera produced no usable frame")
        people = []
        for person in latest_observation.people:
            state = person.get("identity_state", "unresolved")
            people.append({
                "track_id": person.get("track_id"),
                "identity_state": state,
                "person_id": person.get("person_id") if state == "recognized" else None,
                "display_name": person.get("display_name") if state == "recognized" else None,
                "identity_confidence": person.get("identity_confidence"),
                "visible": bool(person.get("visible", True)),
            })
        jpeg_bytes: bytes | None = None
        if include_image:
            encoded, jpeg = cv2.imencode(".jpg", latest_image, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
            jpeg_bytes = jpeg.tobytes() if encoded else None
        return {
            "status": "observed",
            "observed_at": latest_observation.captured_at,
            "room_id": "office",
            "room_state": latest_observation.room_state,
            "people": people,
            "person_count": len([person for person in people if person["visible"]]),
            "identity_source": "local_yunet_sface_enrolled_profile",
            "exact_arrival_known": False,
            "frames_persisted": False,
            "image_shared_with_codex": bool(jpeg_bytes),
            "biometric_profile_exported": False,
            "frames_processed": frame_count,
        }, jpeg_bytes


def inspect_wake_speaker_context(
    config_path: Path, *, duration_seconds: float = 3.0, completion_timeout_seconds: float = 5.0,
) -> dict[str, Any]:
    """Return metadata-only local identity evidence for one explicit voice wake."""

    metadata, image = inspect_office_camera(
        config_path,
        duration_seconds=duration_seconds,
        include_image=False,
        completion_timeout_seconds=completion_timeout_seconds,
    )
    if image is not None:  # defense in depth for the automatic path
        raise RuntimeError("wake identity inspection unexpectedly produced image bytes")
    metadata["image_shared_with_codex"] = False
    metadata["frames_persisted"] = False
    return metadata
