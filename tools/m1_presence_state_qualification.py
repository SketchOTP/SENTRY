"""Run one operator-labeled, metadata-only room-state qualification segment."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from perception.sentry_perception import PerceptionService, _system_snapshot, load_config


MARKERS = {
    "empty": "CONFIRMED_EMPTY",
    "entry": "CONFIRMED_ENTRY",
    "occupied": "CONFIRMED_OCCUPIED",
    "one_person": "CONFIRMED_ONE_PERSON",
    "exit": "CONFIRMED_EXIT",
    "dim_usable": "CONFIRMED_DIM_USABLE",
    "insufficient_light": "CONFIRMED_INSUFFICIENT_LIGHT",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("perception/config.example.json"))
    parser.add_argument("--segment", choices=tuple(MARKERS), required=True)
    parser.add_argument("--duration-seconds", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.duration_seconds <= 0:
        parser.error("--duration-seconds must be positive")

    config = load_config(args.config)
    records: list[dict[str, object]] = []
    marker = MARKERS[args.segment]

    def emit(observation) -> None:
        record = observation.as_dict()
        record["segment"] = args.segment
        records.append(record)
        if len(records) % 50 == 0:
            print(
                f"STATE_PROGRESS segment={args.segment} observations={len(records)} "
                f"room_state={record['room_state']} detector_evidence={record['detector_evidence']}",
                flush=True,
            )

    service = PerceptionService(config, emit)
    # Model initialization can take tens of seconds. Emit the operator marker
    # only after that blind interval so entry timing is correlated with the
    # actual camera run rather than process startup.
    print(f"GROUND_TRUTH_MARKER {marker} {datetime.now(timezone.utc).isoformat()}", flush=True)
    metrics_start = _system_snapshot()
    summary = service.run(args.duration_seconds)
    metrics_end = _system_snapshot()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as output:
        for record in records:
            output.write(json.dumps(record, sort_keys=True) + "\n")

    state_counts: dict[str, int] = {}
    transitions: list[dict[str, object]] = []
    for record in records:
        state = str(record["room_state"])
        state_counts[state] = state_counts.get(state, 0) + 1
        if record.get("room_state_transition"):
            transitions.append({
                "captured_at": record["captured_at"],
                "transition": record["room_state_transition"],
            })
    end_marker = f"{marker}_END"
    print(f"GROUND_TRUTH_MARKER {end_marker} {datetime.now(timezone.utc).isoformat()}", flush=True)
    print(
        json.dumps(
            {
                "ok": summary["camera_state"] != "offline",
                "segment": args.segment,
                "observations": len(records),
                "state_counts": state_counts,
                "transitions": transitions,
                "summary": summary,
                "metrics_start": metrics_start,
                "metrics_end": metrics_end,
                "raw_frames_persisted": False,
                "codex_luna_calls": 0,
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )
    return 0 if summary["camera_state"] != "offline" else 3


if __name__ == "__main__":
    raise SystemExit(main())
