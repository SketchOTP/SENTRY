"""Fresh, metadata-only observations, separate from ANIMA's desired intent."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_STATUS_AGE_SECONDS = 60


def fresh_status(value: Any, *, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    if not isinstance(value, dict):
        return {"state": "UNAVAILABLE", "status": "INVALID", "reason": "Voice status is invalid."}
    try:
        timestamp = datetime.fromisoformat(str(value.get("updated_at", "")))
        if timestamp.tzinfo is None:
            raise ValueError("aware timestamp required")
        age = (now - timestamp).total_seconds()
        if not -5 <= age <= MAX_STATUS_AGE_SECONDS:
            raise ValueError("stale timestamp")
    except (ValueError, TypeError):
        return {
            "state": "UNAVAILABLE", "status": "STALE",
            "reason": "Voice status is stale or has no valid timestamp.",
            "observed_state": str(value.get("state", "UNKNOWN")),
        }
    return dict(value)


def _read(path: Path) -> dict[str, Any]:
    try:
        return fresh_status(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {"state": "UNAVAILABLE", "status": "UNAVAILABLE", "reason": "Voice status is unavailable."}


def read_runtime_voice(path: Path) -> dict[str, Any]:
    observed = _read(path)
    desired = _read(path.with_name("voice-supervisor.json"))
    if desired.get("status") == "CURRENT" and isinstance(desired.get("desired_sleep_enabled"), bool):
        observed["desired_sleep_enabled"] = desired["desired_sleep_enabled"]
        observed["desired_instance_id"] = desired.get("desired_instance_id")
    return observed
