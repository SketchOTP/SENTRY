"""Run a bounded physical SENTRY perception + persisted-event M5 proof.

The perception service and proactive processor use separate local SQLite
connections.  The processor observes committed metadata events after they are
written, so perception itself remains free of Luna calls.

The qualification protocol is deliberately operator-gated: perception starts
first, an operator confirms an empty frame, the persisted room state must stay
empty for a bounded interval, and only then is physical entry requested.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

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


def _empty_baseline_ready(store: PresenceStore) -> bool:
    """Return true only for a persisted, healthy, session-free empty room."""

    state = store.current_state("office")
    if state is None or state.state != "empty" or state.camera_state != "online":
        return False
    return not any(item.get("status") == "open" for item in store.sessions("office", limit=20))


def _wait_for_stable_empty_baseline(
    store: PresenceStore,
    *,
    stable_seconds: float,
    timeout_seconds: float,
    service_alive: Callable[[], bool],
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> tuple[bool, float | None, str | None]:
    """Wait for persisted empty/online state before allowing physical entry."""

    deadline = monotonic() + timeout_seconds
    stable_at: float | None = None
    while monotonic() < deadline:
        if not service_alive():
            return False, stable_at, "perception stopped before empty baseline stabilized"
        if _empty_baseline_ready(store):
            if stable_at is None:
                stable_at = monotonic()
            if monotonic() - stable_at >= stable_seconds:
                return True, stable_at, None
        else:
            stable_at = None
        sleep(0.25)
    return False, stable_at, "persisted empty baseline did not stabilize before timeout"


def run_live(
    config_path: Path,
    duration: float,
    *,
    database: Path | None = None,
    mirror: Path | None = None,
    profile_source: Path | None = None,
    baseline_stable_seconds: float = 7.0,
    baseline_timeout_seconds: float = 45.0,
    post_entry_timeout_seconds: float = 90.0,
    operator_input=input,
) -> dict:
    if baseline_stable_seconds <= 0 or baseline_timeout_seconds <= 0 or post_entry_timeout_seconds <= 0:
        raise ValueError("qualification timing values must be positive")
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
    processor_store = PresenceStore(
        live_database,
        atlas_mirror_path=live_mirror,
        mirror_interval_seconds=float(config["storage"].get("mirror_interval_seconds", 60.0)),
    )
    processor = ProactiveProcessor(processor_store, policy, speech=SpeechDispatcher())
    stop = threading.Event()
    outcomes = []
    service = PerceptionService(config)
    service_result: dict[str, object] = {}

    def run_perception() -> None:
        try:
            service_result["summary"] = service.run(duration_seconds=max(0.0, duration))
        except Exception as exc:  # diagnostic result, never a reason to fabricate presence
            service_result["error"] = f"{type(exc).__name__}: {exc}"

    def poll() -> None:
        while not stop.is_set():
            try:
                outcomes.extend(processor.process_pending())
            except Exception as exc:  # diagnostic result, never a reason to fabricate presence
                outcomes.append({"error": f"{type(exc).__name__}: {exc}"})
            stop.wait(0.2)

    poll_thread = threading.Thread(target=poll, name="sentry-proactive", daemon=True)
    poll_thread.start()
    service_thread = threading.Thread(target=run_perception, name="sentry-perception", daemon=True)
    service_thread.start()
    started = time.monotonic()
    baseline_confirmed_at: str | None = None
    baseline_stable_at: float | None = None
    baseline_completed_at: str | None = None
    entry_prompted_at: str | None = None
    event_seen: dict | None = None
    action_seen: dict | None = None
    protocol_error: str | None = None
    try:
        print(json.dumps({
            "ready": True,
            "perception_started": True,
            "startup_suppression_seconds": policy.startup_suppression_seconds,
            "operator_action": "confirm_empty_frame",
        }, sort_keys=True), flush=True)
        marker = str(operator_input("Type CONFIRMED_EMPTY when nobody is visible: ")).strip()
        if marker != "CONFIRMED_EMPTY":
            protocol_error = f"unexpected operator marker: {marker!r}"
        else:
            baseline_confirmed_at = datetime.now(timezone.utc).isoformat()
            baseline_ok, baseline_stable_at, baseline_error = _wait_for_stable_empty_baseline(
                processor_store,
                stable_seconds=baseline_stable_seconds,
                timeout_seconds=baseline_timeout_seconds,
                service_alive=service_thread.is_alive,
            )
            if baseline_ok:
                baseline_completed_at = datetime.now(timezone.utc).isoformat()
            else:
                protocol_error = baseline_error

        if protocol_error is None:
            suppression_remaining = policy.startup_suppression_seconds - (time.monotonic() - started)
            if suppression_remaining > 0:
                print(json.dumps({
                    "waiting_for_startup_suppression_seconds": round(suppression_remaining, 3),
                }, sort_keys=True), flush=True)
                suppression_deadline = time.monotonic() + suppression_remaining
                while time.monotonic() < suppression_deadline and service_thread.is_alive():
                    time.sleep(0.25)
            if not service_thread.is_alive():
                protocol_error = "perception stopped before entry prompt"
            else:
                entry_prompted_at = datetime.now(timezone.utc).isoformat()
                print(json.dumps({
                    "operator_action": "PRIMARY_USER_ENTER_NOW",
                    "timestamp": entry_prompted_at,
                }, sort_keys=True), flush=True)
                entry_deadline = time.monotonic() + post_entry_timeout_seconds
                while time.monotonic() < entry_deadline:
                    events = [
                        event for event in processor_store.events("office", limit=200)
                        if event.get("event_type") == "person.identified"
                        and event.get("session_id") is not None
                        and baseline_completed_at is not None
                        and str(event.get("occurred_at", "")) >= baseline_completed_at
                    ]
                    if events:
                        event_seen = sorted(events, key=lambda item: str(item.get("occurred_at", "")))[-1]
                        action_seen = processor_store.proactive_action_for_event(str(event_seen["event_id"]))
                        if action_seen and (
                            action_seen.get("judge_decision") in {"speak", "silent"}
                            or action_seen.get("eligibility_result") == "suppressed"
                        ):
                            break
                    if not service_thread.is_alive():
                        protocol_error = "perception stopped before persisted primary-user event"
                        break
                    time.sleep(0.25)
                if event_seen is None and protocol_error is None:
                    protocol_error = "timed out waiting for persisted person.identified"
    except (EOFError, KeyboardInterrupt) as exc:
        protocol_error = f"operator input unavailable: {type(exc).__name__}"
    finally:
        stop.set()
        service.stop()
        service_thread.join(timeout=10)
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
    summary = service_result.get("summary")
    if not isinstance(summary, dict):
        summary = service.summary()
    processor_store.close()
    return {
        "ok": protocol_error is None and event_seen is not None and action_seen is not None,
        "protocol": {
            "baseline_marker": "CONFIRMED_EMPTY" if baseline_confirmed_at else None,
            "baseline_confirmed_at": baseline_confirmed_at,
            "baseline_completed_at": baseline_completed_at,
            "entry_prompted_at": entry_prompted_at,
            "event_id": event_seen.get("event_id") if event_seen else None,
            "session_id": event_seen.get("session_id") if event_seen else None,
            "action_id": action_seen.get("action_id") if action_seen else None,
            "error": protocol_error,
        },
        "perception": summary,
        "proactive_metrics": metrics,
        "proactive_outcomes": action_rows,
        "proactive_actions": action_log,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "perception/config.example.json")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--mirror", type=Path, required=True)
    parser.add_argument("--profile-source", type=Path, default=Path("~/.local/share/sentry/sentry.db"))
    parser.add_argument("--duration", type=float, default=150.0, help="maximum total perception runtime")
    parser.add_argument("--baseline-stable-seconds", type=float, default=7.0)
    parser.add_argument("--baseline-timeout-seconds", type=float, default=45.0)
    parser.add_argument("--post-entry-timeout-seconds", type=float, default=90.0)
    args = parser.parse_args(argv)
    try:
        result = run_live(
            args.config,
            args.duration,
            database=args.database,
            mirror=args.mirror,
            profile_source=args.profile_source,
            baseline_stable_seconds=args.baseline_stable_seconds,
            baseline_timeout_seconds=args.baseline_timeout_seconds,
            post_entry_timeout_seconds=args.post_entry_timeout_seconds,
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, KeyError, RuntimeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
