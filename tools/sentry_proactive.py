"""Process persisted SENTRY identity events through the M5 proactive policy."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from perception.presence_store import PresenceStore
from perception.proactive import ProactivePolicyConfig, ProactiveProcessor, SpeechDispatcher
from perception.sentry_perception import load_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "perception/config.example.json")
    parser.add_argument("--database", type=Path)
    parser.add_argument("--no-speech", action="store_true", help="record judge decisions without local delivery")
    parser.add_argument("--process-all", action="store_true", help="scan the bounded recent event window")
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        storage = config.get("storage", {})
        database = args.database or Path(storage["database_path"]).expanduser()
        mirror = storage.get("atlas_mirror_path")
        policy = ProactivePolicyConfig.from_mapping(config.get("proactivity"))
        speech = SpeechDispatcher() if not args.no_speech else SpeechDispatcher(executable="")
        with PresenceStore(database, atlas_mirror_path=mirror, mirror_interval_seconds=float(storage.get("mirror_interval_seconds", 60.0))) as store:
            processor = ProactiveProcessor(store, policy, speech=speech)
            outcomes = processor.process_pending() if args.process_all else []
            print(json.dumps({"ok": True, "outcomes": [outcome.__dict__ for outcome in outcomes]}, sort_keys=True))
        return 0
    except (OSError, KeyError, RuntimeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
