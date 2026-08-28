"""Compare legacy SENTRY and official YOLOX postprocessing metadata only."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from perception.sentry_perception import (
    OpenVINOYOLOXSPersonDetector,
    _yolox_decode_arrays,
    _yolox_nms_indices,
    load_config,
    yolox_decode_output,
    yolox_decode_reference_output,
)


def _legacy_person_rows(output, *, width: int, height: int, ratio: float, threshold: float, nms_threshold: float):
    import numpy as np

    decoded, boxes = _yolox_decode_arrays(output, width=width, height=height, ratio=ratio)
    scores = decoded[:, 4] * decoded[:, 5]
    valid = (
        np.isfinite(decoded[:, 4])
        & np.isfinite(decoded[:, 5])
        & np.isfinite(scores)
        & (scores > threshold)
        & (boxes[:, 2] > boxes[:, 0])
        & (boxes[:, 3] > boxes[:, 1])
    )
    indices = np.flatnonzero(valid)
    if indices.size == 0:
        return []
    keep = set(_yolox_nms_indices(boxes[indices], scores[indices], nms_threshold))
    return [
        {
            "source_index": int(source_index),
            "final_class_id": 0,
            "objectness": float(decoded[source_index, 4]),
            "person_probability": float(decoded[source_index, 5]),
            "top_class_probability": float(decoded[source_index, 5]),
            "top_class_id": 0,
            "final_score": float(scores[source_index]),
            "bbox": [float(value) for value in boxes[source_index]],
            "nms_kept": local_index in keep,
        }
        for local_index, source_index in enumerate(indices)
    ]


def _compact(row):
    return {
        key: row[key]
        for key in (
            "source_index",
            "final_class_id",
            "objectness",
            "person_probability",
            "top_class_probability",
            "top_class_id",
            "final_score",
            "bbox",
            "nms_kept",
        )
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("perception/config.example.json"))
    parser.add_argument("--frames", type=int, default=10)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.frames <= 0:
        parser.error("--frames must be positive")

    import cv2

    config = load_config(args.config)
    camera = config["camera"]
    detector_config = config["detector"]
    detector = OpenVINOYOLOXSPersonDetector(detector_config)
    source = camera.get("device_path") or int(camera.get("index", 0))
    capture = cv2.VideoCapture(source, cv2.CAP_V4L2 if camera.get("backend") == "v4l2" else cv2.CAP_ANY)
    if not capture.isOpened():
        raise RuntimeError(f"unable to open camera source: {source}")
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, int(camera["width"]))
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, int(camera["height"]))
    capture.set(cv2.CAP_PROP_FPS, float(camera["fps"]))
    if camera.get("fourcc"):
        capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*camera["fourcc"]))

    threshold = float(detector_config["confidence_threshold"])
    nms_threshold = float(detector_config.get("nms_threshold", 0.45))
    records = []
    try:
        while len(records) < args.frames:
            ok, image = capture.read()
            if not ok or image is None:
                continue
            started = time.perf_counter()
            raw, ratio, width, height = detector._infer(image)
            reference = yolox_decode_reference_output(
                raw,
                width=width,
                height=height,
                ratio=ratio,
                confidence_threshold=threshold,
                nms_threshold=nms_threshold,
            )
            legacy = _legacy_person_rows(
                raw,
                width=width,
                height=height,
                ratio=ratio,
                threshold=threshold,
                nms_threshold=nms_threshold,
            )
            sentry = yolox_decode_output(
                raw,
                width=width,
                height=height,
                ratio=ratio,
                confidence_threshold=threshold,
                nms_threshold=nms_threshold,
            )
            reference_person = [row for row in reference if row["nms_kept"] and row["final_class_id"] == 0]
            records.append(
                {
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    "frame_sequence": len(records) + 1,
                    "threshold": threshold,
                    "nms_threshold": nms_threshold,
                    "reference_candidates": [_compact(row) for row in reference],
                    "legacy_person_candidates": [_compact(row) for row in legacy],
                    "reference_final_person_count": len(reference_person),
                    "legacy_final_person_count": sum(row["nms_kept"] for row in legacy),
                    "sentry_final_person_count": len(sentry),
                    "postprocess_ms": round((time.perf_counter() - started) * 1000, 3),
                }
            )
    finally:
        capture.release()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(record, sort_keys=True) + "\n" for record in records), encoding="utf-8")
    mismatches = sum(
        record["reference_final_person_count"] != record["sentry_final_person_count"]
        for record in records
    )
    legacy_mismatches = sum(
        record["reference_final_person_count"] != record["legacy_final_person_count"]
        for record in records
    )
    print(
        json.dumps(
            {
                "frames": len(records),
                "reference_vs_corrected_sentry_count_mismatches": mismatches,
                "reference_vs_legacy_sentry_count_mismatches": legacy_mismatches,
                "reference_person_detections": sum(record["reference_final_person_count"] for record in records),
                "legacy_person_detections": sum(record["legacy_final_person_count"] for record in records),
                "output": str(args.output),
                "raw_frames_persisted": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
