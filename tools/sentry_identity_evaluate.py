"""Collect metadata-only held-out YuNet/SFace identity scores.

Frames and query embeddings remain transient. The output contains only bounded
quality metadata, cosine scores, and timestamps for offline threshold review.
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
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from perception.identity import OpenCVFaceBackend, identity_config_from_mapping
from perception.presence_store import PresenceStore
from perception.sentry_perception import load_config


def score_statistics(scores: list[float]) -> dict[str, float | int | None]:
    if not scores:
        return {"count": 0, "min": None, "p05": None, "p25": None, "median": None, "p75": None, "p95": None, "max": None}
    values = np.asarray(scores, dtype=np.float64)
    percentiles = np.percentile(values, [5, 25, 50, 75, 95])
    return {
        "count": int(values.size),
        "min": round(float(values.min()), 6),
        "p05": round(float(percentiles[0]), 6),
        "p25": round(float(percentiles[1]), 6),
        "median": round(float(percentiles[2]), 6),
        "p75": round(float(percentiles[3]), 6),
        "p95": round(float(percentiles[4]), 6),
        "max": round(float(values.max()), 6),
    }


def collect_scores(config: dict[str, Any], backend: OpenCVFaceBackend, profile: dict[str, Any], duration: float) -> dict[str, Any]:
    camera = config["camera"]
    source = camera.get("device_path") or int(camera.get("index", 0))
    backend_name = cv2.CAP_V4L2 if camera.get("backend") == "v4l2" else cv2.CAP_ANY
    capture = cv2.VideoCapture(source, backend_name)
    if not capture.isOpened():
        capture.release()
        raise RuntimeError(f"unable to open configured evaluation camera: {source}")
    for prop, value in (
        (cv2.CAP_PROP_FRAME_WIDTH, int(camera["width"])),
        (cv2.CAP_PROP_FRAME_HEIGHT, int(camera["height"])),
        (cv2.CAP_PROP_FPS, float(camera["fps"])),
    ):
        capture.set(prop, value)
    started = time.monotonic()
    frames = 0
    read_failures = 0
    no_face = 0
    ambiguous_faces = 0
    quality_rejected = 0
    scores: list[float] = []
    records: list[dict[str, Any]] = []
    try:
        while time.monotonic() - started < duration:
            ok, image = capture.read()
            now = datetime.now(timezone.utc).isoformat()
            if not ok or image is None:
                read_failures += 1
                continue
            frames += 1
            faces = backend.detect_faces(image)
            if not faces:
                no_face += 1
                continue
            if len(faces) != 1:
                ambiguous_faces += 1
                continue
            extracted = backend.accepted_embedding(image, faces[0])
            if extracted is None:
                quality_rejected += 1
                continue
            query, quality = extracted
            score = float(backend.recognizer.match(query, profile["prototype"], backend._cv2.FaceRecognizerSF_FR_COSINE))
            scores.append(score)
            records.append(
                {
                    "timestamp": now,
                    "detector_confidence": round(float(faces[0].confidence), 6),
                    "score": round(score, 6),
                    "quality": {
                        key: (round(float(value), 6) if isinstance(value, (float, int)) else bool(value))
                        for key, value in quality.items()
                    },
                }
            )
    finally:
        capture.release()
    elapsed = max(time.monotonic() - started, 1e-9)
    return {
        "frames": frames,
        "read_failures": read_failures,
        "no_face": no_face,
        "ambiguous_faces": ambiguous_faces,
        "quality_rejected": quality_rejected,
        "quality_qualified": len(records),
        "duration_seconds": round(elapsed, 3),
        "scores": score_statistics(scores),
        "observations": records,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("segment", choices=("genuine", "negative"))
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "perception/config.example.json")
    parser.add_argument("--duration", type=float, default=60.0)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--consent-confirmed", action="store_true", help="required for a non-primary segment")
    args = parser.parse_args(argv)
    if args.duration <= 0:
        parser.error("--duration must be positive")
    if args.segment == "negative" and not args.consent_confirmed:
        parser.error("--consent-confirmed is required for the non-primary segment")
    try:
        config = load_config(args.config)
        identity = identity_config_from_mapping(config.get("identity"))
        backend = OpenCVFaceBackend(identity)
        storage = config.get("storage", {})
        with PresenceStore(
            storage["database_path"],
            atlas_mirror_path=storage.get("atlas_mirror_path"),
            mirror_interval_seconds=float(storage.get("mirror_interval_seconds", 60.0)),
        ) as store:
            profile = store.identity_profile("primary_user")
            if profile is None:
                raise RuntimeError("primary_user is not enrolled")
            result = collect_scores(config, backend, profile, args.duration)
        result.update({"segment": args.segment, "person_id": "primary_user", "generated_at": datetime.now(timezone.utc).isoformat()})
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"ok": True, "segment": args.segment, "output": str(args.output), **result["scores"]}))
        return 0
    except (KeyError, OSError, RuntimeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
