"""Refresh or inspect SENTRY's derived routine-statistics snapshots."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from perception.presence_store import PresenceStore
from perception.routines import RoutineConfig, build_snapshots


def _load_config(path: Path) -> dict:
    value = json.loads(path.expanduser().read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("configuration must be a JSON object")
    return value


def _paths(config: dict) -> tuple[Path, Path | None]:
    storage = config.get("storage", {})
    database = Path(str(storage.get("database_path", "~/.local/share/sentry/sentry.db"))).expanduser()
    mirror_value = storage.get("atlas_mirror_path")
    mirror = (REPO_ROOT / str(mirror_value)).resolve() if mirror_value and not Path(str(mirror_value)).is_absolute() else (Path(str(mirror_value)).expanduser() if mirror_value else None)
    return database, mirror


def refresh(config: dict, *, as_of: datetime | None = None) -> dict:
    routine_config = RoutineConfig.from_mapping(config.get("routines"))
    database, mirror = _paths(config)
    as_of = as_of or datetime.now(timezone.utc)
    with PresenceStore(database, atlas_mirror_path=mirror) as store:
        window_start = as_of.astimezone(timezone.utc) - timedelta(days=routine_config.lookback_days)
        window_end = as_of.astimezone(timezone.utc)
        source = store.routine_source(window_start.isoformat(), window_end.isoformat())
        snapshots = build_snapshots(source, as_of=as_of, config=routine_config)
        result = store.persist_routine_snapshots(snapshots)
        result.update({
            "schema_version": store.health()["schema_version"],
            "window_start": snapshots[0]["window_start"],
            "window_end": snapshots[0]["window_end"],
            "source_as_of": snapshots[0]["source_as_of"],
            "snapshot_count": len(snapshots),
            "statuses": {status: sum(1 for item in snapshots if item["maturity_status"] == status) for status in ("insufficient", "observed", "stable")},
        })
        return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("refresh", "show"))
    parser.add_argument("--config", type=Path, default=Path("~/.config/sentry/config.json"))
    parser.add_argument("--as-of", help="UTC ISO timestamp for deterministic refresh testing")
    parser.add_argument("--history", action="store_true", help="show snapshot history instead of latest per routine")
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args(argv)
    try:
        config = _load_config(args.config)
        if args.command == "refresh":
            as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00")) if args.as_of else None
            print(json.dumps(refresh(config, as_of=as_of), indent=2, sort_keys=True))
        else:
            database, mirror = _paths(config)
            with PresenceStore(database, atlas_mirror_path=mirror) as store:
                print(json.dumps({"routines": store.routine_snapshots(latest_only=not args.history, limit=args.limit)}, indent=2, sort_keys=True))
    except (OSError, ValueError, TypeError) as exc:
        print(f"SENTRY routine command failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
