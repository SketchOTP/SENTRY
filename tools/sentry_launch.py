"""Launch the configured SENTRY resident stack and present its native UI."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable


CORE_UNITS = (
    "sentry-state-api.service",
    "sentry-routines.timer",
    "sentry-ui.service",
)
UI_APPLICATION_ID = "local.sentry.Control"


def _object(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key, {})
    if not isinstance(value, dict):
        raise ValueError(f"SENTRY config {key} must be an object")
    return value


def configured_launch_units(config_path: Path) -> tuple[str, ...]:
    """Return the resident units an explicit desktop launch should start."""

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("SENTRY config must be an object")

    voice = _object(payload, "voice")
    resident = _object(payload, "resident")
    proactivity = _object(payload, "proactivity")
    weather = _object(payload, "weather")
    alarms = _object(payload, "alarms")

    units = list(CORE_UNITS)
    if bool(alarms.get("enabled", True)):
        units.append("sentry-alarms.timer")
    if (
        bool(weather.get("enabled"))
        and weather.get("latitude") is not None
        and weather.get("longitude") is not None
    ):
        units.append("sentry-weather.timer")
    if bool(resident.get("continuous_perception_enabled", False)):
        units.append("sentry-perception.service")
    if (
        bool(resident.get("continuous_proactivity_enabled", False))
        and bool(proactivity.get("enabled", False))
    ):
        units.append("sentry-proactive.service")
    if bool(voice.get("always_on_enabled")) and not bool(voice.get("sleep_enabled", False)):
        units.append("sentry-voice.service")
    return tuple(units)


def _run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=check,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
    )


def _present_ui(
    *,
    run: Callable[..., subprocess.CompletedProcess[str]] = _run,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Activate the single-instance GTK app after systemd has started it."""

    if shutil.which("gapplication") is None:
        return
    last_error = ""
    for attempt in range(20):
        result = run(
            ["gapplication", "launch", UI_APPLICATION_ID],
            check=False,
        )
        if result.returncode == 0:
            return
        last_error = result.stderr.strip()
        if attempt < 19:
            sleep(0.1)
    raise RuntimeError(last_error or "native SENTRY application did not become available")


def launch(
    config_path: Path,
    *,
    run: Callable[..., subprocess.CompletedProcess[str]] = _run,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[str, ...]:
    """Start missing configured units and bring the native SENTRY window forward."""

    units = configured_launch_units(config_path)
    run(["systemctl", "--user", "start", *units])
    _present_ui(run=run, sleep=sleep)
    return units


def _notify_failure(message: str) -> None:
    if shutil.which("notify-send") is None:
        return
    subprocess.run(
        ["notify-send", "SENTRY could not start", message],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("~/.config/sentry/config.json"))
    args = parser.parse_args(argv)
    try:
        units = launch(args.config.expanduser())
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        message = f"{type(exc).__name__}: {exc}"
        print(f"SENTRY launch failed: {message}", file=sys.stderr)
        _notify_failure(message)
        return 2
    print(f"SENTRY ready ({', '.join(units)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
