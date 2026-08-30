"""Refresh or inspect SENTRY's bounded NWS weather snapshot."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from perception.presence_store import PresenceStore  # noqa: E402
from perception.weather import NWSWeatherProvider, WeatherConfig, WeatherError  # noqa: E402


def _load_config(path: Path) -> dict:
    value = json.loads(path.expanduser().read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("configuration must be a JSON object")
    return value


def _paths(config: dict) -> tuple[Path, Path | None]:
    storage = config.get("storage", {})
    if not isinstance(storage, dict):
        raise ValueError("storage must be an object")
    database = Path(str(storage.get("database_path", "~/.local/share/sentry/sentry.db"))).expanduser()
    mirror_value = storage.get("atlas_mirror_path")
    mirror = (
        (REPO_ROOT / str(mirror_value)).resolve()
        if mirror_value and not Path(str(mirror_value)).is_absolute()
        else (Path(str(mirror_value)).expanduser() if mirror_value else None)
    )
    return database, mirror


def refresh(config: dict, *, provider: NWSWeatherProvider | None = None) -> dict:
    weather = WeatherConfig.from_mapping(config.get("weather"))
    database, mirror = _paths(config)
    if not weather.enabled:
        if weather.latitude is None or weather.longitude is None:
            return {"status": "unavailable", "error": "WEATHER LOCATION CONFIG REQUIRED", "configured": False}
        return {"status": "disabled", "message": "weather is disabled"}
    with PresenceStore(database, atlas_mirror_path=mirror) as store:
        previous = store.latest_weather_snapshot(weather.location_label)
        try:
            snapshot = (provider or NWSWeatherProvider()).refresh(weather, previous=previous)
        except WeatherError as exc:
            status = store.weather_status(weather.location_label)
            return {
                "status": "unavailable",
                "error": str(exc),
                "last_good_status": status["status"],
                "last_good_fetched_at": (status.get("snapshot") or {}).get("fetched_at"),
            }
        result = store.persist_weather_snapshot(snapshot)
        result.update({
            "status": store.weather_status(weather.location_label)["status"],
            "provider": snapshot["provider"],
            "location_label": snapshot["location_label"],
            "fetched_at": snapshot["fetched_at"],
            "fresh_until": snapshot["fresh_until"],
            "component_errors": snapshot["source_metadata"].get("component_errors", []),
            "schema_version": store.health()["schema_version"],
        })
        return result


def show(config: dict) -> dict:
    weather = WeatherConfig.from_mapping(config.get("weather"))
    database, mirror = _paths(config)
    with PresenceStore(database, atlas_mirror_path=mirror) as store:
        result = store.weather_status(weather.location_label)
        result["location_label"] = weather.location_label
        result["enabled"] = weather.enabled
        result["schema_version"] = store.health()["schema_version"]
        return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("refresh", "show"))
    parser.add_argument("--config", type=Path, default=Path("~/.config/sentry/config.json"))
    args = parser.parse_args(argv)
    try:
        config = _load_config(args.config)
        result = refresh(config) if args.command == "refresh" else show(config)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result.get("status") not in {"unavailable"} else 2
    except (OSError, ValueError, TypeError, WeatherError) as exc:
        print(f"SENTRY weather command failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
