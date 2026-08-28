"""Evaluate YOLOX-S metadata-only room-state thresholds from labeled runs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from perception.calibration import evaluate_thresholds


DEFAULT_THRESHOLDS = (0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    args = parser.parse_args(argv)
    records = []
    for path in args.inputs:
        records.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    result = evaluate_thresholds(records, DEFAULT_THRESHOLDS)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
