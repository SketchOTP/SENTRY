"""Explicit on-demand office camera inspection with local identity matching.

Frames are held only in memory. The enrolled biometric prototype never leaves
the local SENTRY store; only the resulting identity label and, when requested,
one user-authorized still image are returned to the calling Codex turn.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2

from perception.identity import IdentityResolver, OpenCVFaceBackend, identity_config_from_mapping
from perception.presence_state import PresenceStateConfig, PresenceStateMachine
from perception.presence_store import PresenceStore
from perception.sentry_perception import IoUTracker, OpenVINOYOLOXSPersonDetector, PerceptionEngine, load_config


def inspect_office_camera(config_path: Path, *, duration_seconds: float = 3.0) -> tuple[dict[str, Any], bytes | None]:
    """Capture a bounded live segment and return local identity metadata plus one JPEG."""

    if not 0.5 <= duration_seconds <= 8.0:
        raise ValueError("camera inspection duration must be from 0.5 through 8 seconds")
    config = load_config(config_path.expanduser())
    identity = identity_config_from_mapping(config.get("identity"))
    if not identity["enabled"]:
        raise RuntimeError("local SENTRY identity is disabled")
    storage = config["storage"]
    with PresenceStore(storage["database_path"], atlas_mirror_path=None) as store:
        profile = store.identity_profile("primary_user")
    if profile is None:
        raise RuntimeError("primary_user is not enrolled")
    backend = OpenCVFaceBackend(identity)
    resolver = IdentityResolver(
        backend,
        match_threshold=float(profile["calibrated_threshold"]),
        confirmation_count=identity["confirmation_count"],
        confirmation_window_seconds=identity["confirmation_window_seconds"],
        profile_provider=lambda: profile,
    )
    detector = OpenVINOYOLOXSPersonDetector(config["detector"])
    tracker = config["tracker"]
    engine = PerceptionEngine(
        detector,
        IoUTracker(
            match_iou_threshold=tracker["match_iou_threshold"],
            high_confidence_threshold=tracker["high_confidence_threshold"],
            new_track_confidence_threshold=tracker["new_track_confidence_threshold"],
            max_missing_frames=tracker["max_missing_frames"],
        ),
        PresenceStateMachine(PresenceStateConfig.from_mapping(config.get("presence"))),
        entry_confidence_threshold=float(config["detector"].get("confidence_threshold", 0.50)),
        hold_confidence_threshold=float(config["detector"].get("hold_confidence_threshold", 0.50)),
        identity_resolver=resolver,
        identity_cadence_seconds=identity["cadence_seconds"],
    )
    camera = config["camera"]
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
    recognized = False
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
            "display_name": profile.get("display_name") if state == "recognized" else None,
            "identity_confidence": person.get("identity_confidence"),
            "visible": bool(person.get("visible", True)),
        })
    encoded, jpeg = cv2.imencode(".jpg", latest_image, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
    metadata = {
        "status": "observed",
        "observed_at": latest_observation.captured_at,
        "room_id": "office",
        "room_state": latest_observation.room_state,
        "people": people,
        "person_count": len([person for person in people if person["visible"]]),
        "identity_source": "local_yunet_sface_enrolled_profile",
        "exact_arrival_known": False,
        "frames_persisted": False,
        "biometric_profile_exported": False,
    }
    return metadata, jpeg.tobytes() if encoded else None
