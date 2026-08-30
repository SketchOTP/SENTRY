"""Bounded metadata-only live probe for the supervised SENTRY runtime."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


UNITS = ("sentry-perception.service", "sentry-state-api.service", "sentry-proactive.service")


def _health(base_url: str) -> dict:
    with urllib.request.urlopen(f"{base_url}/health", timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _unit_states() -> dict[str, str]:
    result: dict[str, str] = {}
    for unit in UNITS:
        completed = subprocess.run(
            ["systemctl", "--user", "is-active", unit],
            capture_output=True,
            text=True,
            check=False,
        )
        result[unit] = completed.stdout.strip() or f"exit:{completed.returncode}"
    return result


def probe(duration_seconds: float, interval_seconds: float, output_path: Path) -> dict:
    if duration_seconds <= 0 or interval_seconds <= 0:
        raise ValueError("duration and interval must be positive")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    samples: list[dict] = []
    failures: list[str] = []
    with output_path.open("w", encoding="utf-8") as output:
        while time.monotonic() - started < duration_seconds:
            sample: dict = {"sampled_at": datetime.now(timezone.utc).isoformat()}
            states = _unit_states()
            sample["units"] = states
            if any(value != "active" for value in states.values()):
                failures.append(f"unit_not_active:{states}")
            try:
                health = _health("http://127.0.0.1:48174")
                sample["api_health"] = health
                if not health.get("db_available"):
                    failures.append("database_unavailable")
                mirror = health.get("atlas_mirror") or {}
                if mirror.get("enabled") and mirror.get("status") not in {"ok", "disabled"}:
                    failures.append(f"mirror_status:{mirror.get('status')}")
            except Exception as exc:
                sample["api_error"] = f"{type(exc).__name__}: {exc}"
                failures.append("api_unavailable")
            heartbeat_path = Path("perception-data/runtime/health/perception.json")
            try:
                heartbeat = json.loads(heartbeat_path.read_text(encoding="utf-8"))
                sample["perception"] = heartbeat
                summary = heartbeat.get("summary") or {}
                if not heartbeat.get("process_alive"):
                    failures.append("perception_not_alive")
                if summary.get("camera_state") not in {"online", "degraded", "offline"}:
                    failures.append(f"camera_state:{summary.get('camera_state')}")
                if time.monotonic() - started >= 120 and float(summary.get("processed_fps", 0.0)) < 5.0:
                    failures.append(f"fps_below_floor:{summary.get('processed_fps')}")
            except Exception as exc:
                sample["heartbeat_error"] = f"{type(exc).__name__}: {exc}"
                failures.append("heartbeat_unavailable")
            samples.append(sample)
            output.write(json.dumps(sample, sort_keys=True) + "\n")
            output.flush()
            if failures:
                break
            time.sleep(min(interval_seconds, max(0.0, duration_seconds - (time.monotonic() - started))))
    elapsed = time.monotonic() - started
    result = {
        "started_at": samples[0]["sampled_at"] if samples else None,
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(elapsed, 3),
        "sample_count": len(samples),
        "failures": failures,
        "last_sample": samples[-1] if samples else None,
        "output_path": str(output_path),
    }
    print(json.dumps(result, sort_keys=True))
    if failures:
        raise RuntimeError("; ".join(failures))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration-seconds", type=float, default=900.0)
    parser.add_argument("--interval-seconds", type=float, default=30.0)
    parser.add_argument("--output", type=Path, default=Path("perception-data/runtime/v0.2/resident-live.jsonl"))
    args = parser.parse_args()
    try:
        probe(args.duration_seconds, args.interval_seconds, args.output)
    except (OSError, RuntimeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, sort_keys=True))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
