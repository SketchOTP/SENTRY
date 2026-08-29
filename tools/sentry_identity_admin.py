"""Explicitly remove the active local primary-user identity profile."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from perception.presence_store import PresenceStore
from perception.sentry_perception import load_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["delete", "set-threshold"])
    parser.add_argument("--person-id", default="primary_user")
    parser.add_argument("--threshold", type=float)
    parser.add_argument("--config", type=Path, default=Path(__file__).parents[1] / "perception/config.example.json")
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        storage = config.get("storage", {})
        with PresenceStore(
            storage["database_path"],
            atlas_mirror_path=storage.get("atlas_mirror_path"),
            mirror_interval_seconds=float(storage.get("mirror_interval_seconds", 60.0)),
        ) as store:
            if args.command == "delete":
                store.delete_identity(args.person_id)
            else:
                if args.threshold is None:
                    raise ValueError("--threshold is required for set-threshold")
                store.set_identity_threshold(args.threshold, args.person_id)
        result = {"ok": True, "person_id": args.person_id, "command": args.command}
        if args.command == "delete":
            result["deleted_person_id"] = args.person_id
        else:
            result["calibrated_threshold"] = args.threshold
        print(json.dumps(result))
        return 0
    except (KeyError, OSError, RuntimeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
