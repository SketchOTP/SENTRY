"""Run a bounded physical SENTRY perception + persisted-event M5 proof.

The perception service and proactive processor use separate local SQLite
connections.  The processor observes committed metadata events after they are
written, so perception itself remains free of Luna calls.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from perception.presence_store import PresenceStore
from perception.proactive import ProactivePolicyConfig, ProactiveProcessor, SpeechDispatcher
from perception.sentry_perception import PerceptionService, load_config


def _seed_profile(source: Path, target: Path, mirror: Path | None) -> None:
    """Copy the active prototype in memory into the isolated qualification DB."""

    with PresenceStore(source) as source_store:
        profile = source_store.identity_profile("primary_user")
    if profile is None:
        raise RuntimeError("primary_user is not enrolled in the profile source")
    with PresenceStore(target, atlas_mirror_path=mirror) as target_store:
        target_store.enroll_identity(
            person_id="primary_user",
            display_name=str(profile["display_name"]),
            backend=str(profile["backend"]),
            model_version=str(profile["model_version"]),
            model_checksum=str(profile["model_checksum"]),
            prototype=profile["prototype"],
            calibrated_threshold=float(profile["calibrated_threshold"]),
            sample_count=int(profile["sample_count"]),
        )


def run_live(
    config_path: Path,
    duration: float,
    *,
    database: Path | None = None,
    mirror: Path | None = None,
    profile_source: Path | None = None,
    wait_before: float = 31.0,
) -> dict:
    config = load_config(config_path)
    storage = config.get("storage", {})
    if database is not None:
        config.setdefault("storage", {})["database_path"] = str(database)
    if mirror is not None:
        config.setdefault("storage", {})["atlas_mirror_path"] = str(mirror)
    config["proactivity"] = {**config.get("proactivity", {}), "enabled": True}
    policy = ProactivePolicyConfig.from_mapping(config["proactivity"])
    live_database = Path(config["storage"]["database_path"]).expanduser()
    live_mirror = config["storage"].get("atlas_mirror_path")
    if profile_source is not None and profile_source.expanduser().resolve() != live_database.expanduser().resolve() and not live_database.exists():
        _seed_profile(profile_source.expanduser(), live_database, Path(live_mirror).expanduser() if live_mirror else None)
    processor_store = PresenceStore(live_database, atlas_mirror_path=live_mirror, mirror_interval_seconds=float(config["storage"].get("mirror_interval_seconds", 60.0)))
    processor = ProactiveProcessor(processor_store, policy, speech=SpeechDispatcher())
    stop = threading.Event()
    outcomes = []

    def poll() -> None:
        while not stop.is_set():
            try:
                outcomes.extend(processor.process_pending())
            except Exception as exc:  # diagnostic result, never a reason to fabricate presence
                outcomes.append({"error": f"{type(exc).__name__}: {exc}"})
            stop.wait(0.2)

    poll_thread = threading.Thread(target=poll, name="sentry-proactive", daemon=True)
    poll_thread.start()
    service = PerceptionService(config)
    started = time.monotonic()
    try:
        print(json.dumps({"ready": True, "startup_suppression_seconds": policy.startup_suppression_seconds, "wait_before_seconds": wait_before}, sort_keys=True), flush=True)
        time.sleep(max(0.0, wait_before))
        print(json.dumps({"operator_action": "primary_user_enter_now", "timestamp": datetime.now(timezone.utc).isoformat()}, sort_keys=True), flush=True)
        summary = service.run(duration_seconds=max(0.0, duration - (time.monotonic() - started)))
    finally:
        stop.set()
        poll_thread.join(timeout=3)
    action_rows = [item.__dict__ if hasattr(item, "__dict__") else item for item in outcomes]
    action_log = processor_store.proactive_actions(limit=100)
    suppression_counts: dict[str, int] = {}
    for item in action_log:
        reason = item.get("suppression_reason")
        if reason:
            suppression_counts[reason] = suppression_counts.get(reason, 0) + 1
    metrics = {
        "candidate_events_seen": len(action_log),
        "deterministic_suppressions": sum(1 for item in action_log if not item.get("judge_invoked")),
        "candidates_passed_to_luna": sum(1 for item in action_log if item.get("judge_invoked")),
        "luna_speak_count": sum(1 for item in action_log if item.get("judge_decision") == "speak"),
        "luna_silent_count": sum(1 for item in action_log if item.get("judge_decision") == "silent"),
        "delivered_utterances": sum(1 for item in action_log if item.get("delivery_status") == "delivered"),
        "delivery_failures": sum(1 for item in action_log if item.get("delivery_status") == "failed"),
        "suppression_counts": suppression_counts,
    }
    processor_store.close()
    return {"perception": summary, "proactive_metrics": metrics, "proactive_outcomes": action_rows, "proactive_actions": action_log}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "perception/config.example.json")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--mirror", type=Path, required=True)
    parser.add_argument("--profile-source", type=Path, default=Path("~/.local/share/sentry/sentry.db"))
    parser.add_argument("--duration", type=float, default=75.0)
    parser.add_argument("--wait-before", type=float, default=31.0)
    args = parser.parse_args(argv)
    if args.duration <= args.wait_before:
        parser.error("--duration must exceed --wait-before")
    try:
        result = run_live(args.config, args.duration, database=args.database, mirror=args.mirror, profile_source=args.profile_source, wait_before=args.wait_before)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, KeyError, RuntimeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
