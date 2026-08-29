"""Explicitly remove the active local primary-user identity profile."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from perception.presence_store import PresenceStore
from perception.sentry_perception import load_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("delete", choices=["delete"])
    parser.add_argument("--person-id", default="primary_user")
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
            store.delete_identity(args.person_id)
        print(json.dumps({"ok": True, "deleted_person_id": args.person_id}))
        return 0
    except (KeyError, OSError, RuntimeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
