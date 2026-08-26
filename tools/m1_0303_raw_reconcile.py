"""Capture metadata-only raw 0303 outputs for the decoder investigation."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from perception.sentry_perception import (
    CameraState,
    LatestFrameBuffer,
    OpenVINOPersonDetector,
    _CameraWorker,
    load_config,
)


def _stats(boxes: Any, labels: Any) -> dict[str, Any]:
    confidence = np.asarray(boxes)[:, 4].astype(float)
    order = np.argsort(confidence)[::-1]
    label_counts = Counter(int(value) for value in np.asarray(labels).reshape(-1))
    return {
        "boxes_rows": int(len(boxes)),
        "positive_confidence_rows": int(np.count_nonzero(confidence > 0.0)),
        "confidence_ge_0_10_rows": int(np.count_nonzero(confidence >= 0.10)),
        "confidence_percentiles": {
            key: round(float(np.percentile(confidence, percentile)), 6)
            for key, percentile in (("p50", 50), ("p75", 75), ("p90", 90), ("p95", 95))
        },
        "confidence_max": round(float(np.max(confidence)), 6),
        "raw_coordinate_min": round(float(np.min(np.asarray(boxes)[:, :4])), 6),
        "raw_coordinate_max": round(float(np.max(np.asarray(boxes)[:, :4])), 6),
        "top_confidence_rows": [
            {"box": [round(float(value), 6) for value in boxes[index]], "label": int(labels[index])}
            for index in order[:5]
        ],
        "label_counts": {str(key): int(value) for key, value in sorted(label_counts.items())},
        "top_confidence_labels": [int(labels[index]) for index in order[:5]],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("perception/config.example.json"))
    parser.add_argument("--duration-seconds", type=float, default=20.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = load_config(args.config)
    detector = OpenVINOPersonDetector(config["detector"])
    buffer = LatestFrameBuffer()
    worker = _CameraWorker(config, buffer)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    observations = 0
    positive_rows = 0
    confidence_ge_010_rows = 0
    current_candidate_rows = 0
    maximum_confidence = float("-inf")
    total_labels: Counter[int] = Counter()
    started = time.perf_counter()
    deadline = started + args.duration_seconds
    print(f"GROUND_TRUTH_MARKER CONFIRMED_ONE_PERSON {datetime.now(timezone.utc).isoformat()}", flush=True)
    with args.output.open("w", encoding="utf-8") as output:
        worker.start()
        try:
            while time.perf_counter() < deadline:
                frame = buffer.pop_latest()
                if frame is None:
                    time.sleep(0.01)
                    continue
                state, _, *_ = worker.snapshot()
                if state != CameraState.ONLINE:
                    continue
                boxes, labels, width, height = detector.infer_raw_outputs(frame.image)
                raw_stats = _stats(boxes, labels)
                current_candidates = detector._decode_detections(boxes, labels, width, height, None)
                record = {
                    "captured_at": frame.captured_at.astimezone(timezone.utc).isoformat(),
                    "frame_sequence": frame.sequence,
                    "camera_state": state.value,
                    **raw_stats,
                    "sentry_current_candidate_count": len(current_candidates),
                }
                output.write(json.dumps(record, sort_keys=True) + "\n")
                output.flush()
                observations += 1
                positive_rows += raw_stats["positive_confidence_rows"]
                confidence_ge_010_rows += raw_stats["confidence_ge_0_10_rows"]
                current_candidate_rows += len(current_candidates)
                maximum_confidence = max(maximum_confidence, raw_stats["confidence_max"])
                total_labels.update({int(key): int(value) for key, value in raw_stats["label_counts"].items()})
                if observations % 25 == 0:
                    print(
                        f"RAW_PROGRESS observations={observations} positive={raw_stats['positive_confidence_rows']} "
                        f"ge_0_10={raw_stats['confidence_ge_0_10_rows']} max={raw_stats['confidence_max']} "
                        f"sentry_candidates={len(current_candidates)}",
                        flush=True,
                    )
        finally:
            worker.stop()
    print(f"GROUND_TRUTH_MARKER CONFIRMED_ONE_PERSON_END {datetime.now(timezone.utc).isoformat()}", flush=True)
    print(
        json.dumps(
            {
                "ok": True,
                "observations": observations,
                "positive_rows_total": positive_rows,
                "confidence_ge_0_10_rows_total": confidence_ge_010_rows,
                "sentry_current_candidate_rows_total": current_candidate_rows,
                "maximum_confidence": None if observations == 0 else maximum_confidence,
                "label_counts_total": {str(key): value for key, value in sorted(total_labels.items())},
                "output": str(args.output),
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
