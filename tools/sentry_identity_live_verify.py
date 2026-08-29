"""Run a metadata-only live identity verification segment.

The configured YOLOX/person track, YuNet/SFace backend, and timestamp-based
presence engine run together. Frames and embeddings are never written.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import psutil

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from perception.identity import IdentityResolver, OpenCVFaceBackend, identity_config_from_mapping
from perception.presence_state import PresenceStateConfig, PresenceStateMachine
from perception.presence_store import PresenceStore
from perception.sentry_perception import IoUTracker, OpenVINOYOLOXSPersonDetector, PerceptionEngine, load_config


def run_segment(config: dict[str, Any], segment: str, duration: float) -> dict[str, Any]:
    identity = identity_config_from_mapping(config.get("identity"))
    backend = OpenCVFaceBackend(identity)
    storage = config["storage"]
    with PresenceStore(storage["database_path"], atlas_mirror_path=None) as store:
        profile = store.identity_profile("primary_user")
    if profile is None:
        raise RuntimeError("primary_user is not enrolled")
    resolver = IdentityResolver(
        backend,
        match_threshold=float(profile["calibrated_threshold"]),
        confirmation_count=identity["confirmation_count"],
        confirmation_window_seconds=identity["confirmation_window_seconds"],
        profile_provider=lambda: profile,
    )
    detector = OpenVINOYOLOXSPersonDetector(config["detector"])
    tracker_config = config["tracker"]
    engine = PerceptionEngine(
        detector,
        IoUTracker(
            match_iou_threshold=tracker_config["match_iou_threshold"],
            high_confidence_threshold=tracker_config["high_confidence_threshold"],
            new_track_confidence_threshold=tracker_config["new_track_confidence_threshold"],
            max_missing_frames=tracker_config["max_missing_frames"],
        ),
        PresenceStateMachine(PresenceStateConfig.from_mapping(config.get("presence"))),
        entry_confidence_threshold=float(config["detector"].get("confidence_threshold", 0.40)),
        hold_confidence_threshold=float(config["detector"].get("hold_confidence_threshold", 0.40)),
        identity_resolver=resolver,
        identity_cadence_seconds=identity["cadence_seconds"],
    )
    camera = config["camera"]
    source = camera.get("device_path") or int(camera.get("index", 0))
    capture = cv2.VideoCapture(source, cv2.CAP_V4L2 if camera.get("backend") == "v4l2" else cv2.CAP_ANY)
    if not capture.isOpened():
        capture.release()
        raise RuntimeError(f"unable to open configured verification camera: {source}")
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, int(camera["width"]))
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, int(camera["height"]))
    capture.set(cv2.CAP_PROP_FPS, float(camera["fps"]))
    process = psutil.Process()
    cpu_start = process.cpu_times()
    rss_start = process.memory_info().rss
    rss_peak = rss_start
    started = time.monotonic()
    observations: list[dict[str, Any]] = []
    processing_ms: list[float] = []
    room_states: dict[str, int] = {}
    identity_states: dict[str, int] = {"recognized": 0, "unknown": 0, "unresolved": 0}
    identity_transitions = 0
    last_identity_signature: tuple[tuple[Any, Any], ...] | None = None
    first_recognized_at: str | None = None
    first_recognized_elapsed: float | None = None
    read_failures = 0
    detector_errors = 0
    captured = 0
    try:
        while time.monotonic() - started < duration:
            ok, image = capture.read()
            if not ok or image is None:
                read_failures += 1
                continue
            captured += 1
            captured_at = datetime.now(timezone.utc)
            try:
                observation = engine.process(image, frame_sequence=captured, captured_at=captured_at)
            except Exception:
                detector_errors += 1
                continue
            processing_ms.append(observation.processing_ms)
            room_states[observation.room_state] = room_states.get(observation.room_state, 0) + 1
            people = [
                {
                    "track_id": person.get("track_id"),
                    "identity_state": person.get("identity_state", "unresolved"),
                    "identity_confidence": person.get("identity_confidence"),
                }
                for person in observation.people
            ]
            signature = tuple((person["track_id"], person["identity_state"]) for person in people)
            if last_identity_signature is not None and signature != last_identity_signature:
                identity_transitions += 1
            last_identity_signature = signature
            for person in people:
                state = person["identity_state"]
                identity_states[state] = identity_states.get(state, 0) + 1
                if state == "recognized" and first_recognized_at is None:
                    first_recognized_at = captured_at.isoformat()
                    first_recognized_elapsed = time.monotonic() - started
            observations.append(
                {
                    "timestamp": captured_at.isoformat(),
                    "room_state": observation.room_state,
                    "people": people,
                    "processing_ms": round(observation.processing_ms, 3),
                    "identity_error": observation.identity_error,
                }
            )
            rss_peak = max(rss_peak, process.memory_info().rss)
    finally:
        capture.release()
    elapsed = max(time.monotonic() - started, 1e-9)
    cpu_end = process.cpu_times()
    cpu_seconds = (cpu_end.user + cpu_end.system) - (cpu_start.user + cpu_start.system)
    ordered = sorted(processing_ms)
    median = ordered[len(ordered) // 2] if ordered else 0.0
    p95 = ordered[min(len(ordered) - 1, max(0, int(len(ordered) * 0.95) - 1))] if ordered else 0.0
    return {
        "segment": segment,
        "duration_seconds": round(elapsed, 3),
        "captured_frames": captured,
        "processed_observations": len(observations),
        "read_failures": read_failures,
        "detector_errors": detector_errors,
        "room_states": room_states,
        "identity_states": identity_states,
        "identity_state_transitions": identity_transitions,
        "first_recognized_at": first_recognized_at,
        "first_recognized_elapsed_seconds": round(first_recognized_elapsed, 3) if first_recognized_elapsed is not None else None,
        "processed_fps": round(len(observations) / elapsed, 3),
        "median_processing_ms": round(median, 3),
        "p95_processing_ms": round(p95, 3),
        "cpu_percent_of_one_core": round(cpu_seconds / elapsed * 100, 2),
        "rss_start_bytes": rss_start,
        "rss_end_bytes": process.memory_info().rss,
        "rss_peak_bytes": rss_peak,
        "camera_backend": "V4L2" if camera.get("backend") == "v4l2" else camera.get("backend", "any"),
        "observations": observations,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("segment", choices=("primary", "non-primary"))
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "perception/config.example.json")
    parser.add_argument("--duration", type=float, default=60.0)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--consent-confirmed", action="store_true", help="required for a non-primary segment")
    args = parser.parse_args(argv)
    if args.duration <= 0:
        parser.error("--duration must be positive")
    if args.segment == "non-primary" and not args.consent_confirmed:
        parser.error("--consent-confirmed is required for the non-primary segment")
    try:
        result = run_segment(load_config(args.config), args.segment, args.duration)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({key: value for key, value in result.items() if key != "observations"}))
        return 0
    except (KeyError, OSError, RuntimeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
