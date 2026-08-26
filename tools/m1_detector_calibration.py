"""Capture operator-confirmed raw detector candidates for M1 calibration.

Only JSONL metadata is written: timestamps, frame sequence, confidences, and
boxes. Camera frames are never written to disk and raw candidates never enter
the production tracker.
"""

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

from perception.calibration import DEFAULT_THRESHOLDS, evaluate_thresholds
from perception.sentry_perception import CameraState, LatestFrameBuffer, OpenVINOPersonDetector, _CameraWorker, load_config


def _marker_name(segment: str) -> str:
    return "CONFIRMED_EMPTY" if segment == "empty" else "CONFIRMED_ONE_PERSON"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("perception/config.example.json"))
    parser.add_argument("--segment", choices=("empty", "one_person"), required=True)
    parser.add_argument("--duration-seconds", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.duration_seconds <= 0:
        parser.error("--duration-seconds must be positive")
    config = load_config(args.config)
    detector = OpenVINOPersonDetector(config["detector"])
    buffer = LatestFrameBuffer()
    worker = _CameraWorker(config, buffer)
    records: list[dict[str, object]] = []
    start_marker = _marker_name(args.segment)
    print(f"GROUND_TRUTH_MARKER {start_marker} {datetime.now(timezone.utc).isoformat()}", flush=True)
    started = time.perf_counter()
    deadline = started + args.duration_seconds
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
            inference_started = time.perf_counter()
            candidates = detector.detect_raw(frame.image)
            inference_ms = (time.perf_counter() - inference_started) * 1000
            records.append({
                "segment": args.segment,
                "camera_state": state.value,
                "captured_at": frame.captured_at.astimezone(timezone.utc).isoformat(),
                "frame_sequence": frame.sequence,
                "inference_ms": round(inference_ms, 3),
                "candidates": [
                    {"bbox": [round(value, 3) for value in candidate.bbox], "confidence": round(candidate.confidence, 6)}
                    for candidate in candidates
                ],
            })
            if len(records) % 50 == 0:
                max_confidence = max((candidate.confidence for candidate in candidates), default=0.0)
                print(
                    f"RAW_PROGRESS segment={args.segment} observations={len(records)} "
                    f"candidates={len(candidates)} max_confidence={max_confidence:.4f}",
                    flush=True,
                )
    finally:
        worker.stop()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as output:
        for record in records:
            output.write(json.dumps(record, sort_keys=True) + "\n")
    results = evaluate_thresholds(records, DEFAULT_THRESHOLDS)
    end_marker = f"{start_marker}_END"
    print(f"GROUND_TRUTH_MARKER {end_marker} {datetime.now(timezone.utc).isoformat()}", flush=True)
    print(json.dumps({"ok": True, "segment": args.segment, "records": len(records), "thresholds": results}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
