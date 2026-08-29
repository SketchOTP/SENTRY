"""Deliberately capture an in-memory primary-user face prototype.

This tool never writes captured frames or individual embeddings.  The only
durable result is the normalized prototype stored in the local M2 SQLite DB,
which is mirrored using the existing Atlas snapshot mechanism.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from perception.identity import OpenCVFaceBackend, build_prototype, identity_config_from_mapping
from perception.presence_store import PresenceStore
from perception.sentry_perception import load_config


def collect_samples(config: dict, backend: OpenCVFaceBackend, samples: int) -> list[np.ndarray]:
    camera = config["camera"]
    source = camera.get("device_path") or int(camera.get("index", 0))
    backend_name = getattr(cv2, "CAP_V4L2", cv2.CAP_ANY) if camera.get("backend") == "v4l2" else cv2.CAP_ANY
    capture = cv2.VideoCapture(source, backend_name)
    if not capture.isOpened():
        capture.release()
        raise RuntimeError(f"unable to open configured enrollment camera: {source}")
    try:
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, int(camera["width"]))
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, int(camera["height"]))
        capture.set(cv2.CAP_PROP_FPS, float(camera["fps"]))
        print("Enrollment is deliberate and interactive. Press Enter to sample the current frame; type q to cancel.")
        accepted: list[np.ndarray] = []
        while len(accepted) < samples:
            command = input(f"Sample {len(accepted) + 1}/{samples}: ")
            if command.strip().lower() == "q":
                raise RuntimeError("enrollment cancelled")
            ok, image = capture.read()
            if not ok or image is None:
                print("Camera read failed; sample not accepted.")
                continue
            faces = backend.detect_faces(image)
            if len(faces) != 1:
                print(f"Sample not accepted: expected exactly one face, found {len(faces)}.")
                continue
            extracted = backend.accepted_embedding(image, faces[0])
            if extracted is None:
                print("Sample not accepted: face quality gate rejected it.")
                continue
            accepted.append(extracted[0])
            print("Accepted. Vary pose/distance naturally before the next sample.")
        return accepted
    finally:
        capture.release()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(__file__).parents[1] / "perception/config.example.json")
    parser.add_argument("--person-id", default="primary_user")
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--samples", type=int, default=16)
    args = parser.parse_args(argv)
    if args.samples < 3:
        parser.error("--samples must be at least 3")
    try:
        config = load_config(args.config)
        identity = identity_config_from_mapping(config.get("identity"))
        if not identity["enabled"]:
            raise RuntimeError("identity.enabled must be true for enrollment")
        backend = OpenCVFaceBackend(identity)
        embeddings = collect_samples(config, backend, args.samples)
        prototype = build_prototype(embeddings)
        storage = config.get("storage", {})
        database_path = storage.get("database_path")
        if not database_path:
            raise RuntimeError("storage.database_path is required for enrollment")
        with PresenceStore(
            database_path,
            atlas_mirror_path=storage.get("atlas_mirror_path"),
            mirror_interval_seconds=float(storage.get("mirror_interval_seconds", 60.0)),
        ) as store:
            store.enroll_identity(
                person_id=args.person_id,
                display_name=args.display_name,
                backend=identity.get("backend", "opencv_yunet_sface"),
                model_version=identity.get("model_version", "opencv_zoo@unknown"),
                model_checksum=(
                    f"yunet:{identity['yunet_sha256']};"
                    f"sface:{identity['sface_sha256']}"
                ),
                prototype=prototype,
                calibrated_threshold=float(identity["match_threshold"]),
                sample_count=len(embeddings),
            )
        print(json.dumps({"ok": True, "person_id": args.person_id, "accepted_samples": len(embeddings)}))
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
