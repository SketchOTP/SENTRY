"""Launch the configured SENTRY resident stack and present its native UI."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable


CORE_UNITS = (
    "sentry-state-api.service",
    "sentry-routines.timer",
    "sentry-ui.service",
)
UI_APPLICATION_ID = "local.sentry.Control"
UI_UNIT = "sentry-ui.service"
UI_DISPLAY_ENVIRONMENT_PATH = Path("~/.config/sentry/ui-display.env")
DISPLAY_TARGET_SCREENS = {"main": 0, "rtx": 1}
DISCRETE_GPU_ENVIRONMENT_KEYS = (
    "__NV_PRIME_RENDER_OFFLOAD",
    "__VK_LAYER_NV_optimus",
    "DRI_PRIME",
)


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
    # Wake availability is household-owned by ANIMA. Always start the
    # resident boundary when locally enabled; the voice process and its
    # supervisor apply ANIMA's current sleep/standby decision.
    if bool(voice.get("always_on_enabled")):
        units.append("sentry-voice.service")
    return tuple(units)


def _run(
    command: list[str],
    *,
    check: bool = True,
    stdout: int | None = subprocess.DEVNULL,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=check,
        stdout=stdout,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
        env=env,
    )


def display_for_target(target: str, current_display: str) -> str:
    """Resolve a named target against the current independent X display."""

    if target not in DISPLAY_TARGET_SCREENS:
        raise ValueError(f"unsupported SENTRY display target: {target}")
    match = re.fullmatch(r"(?P<base>.*:\d+)(?:\.\d+)?", current_display.strip())
    if match is None:
        raise ValueError(f"cannot resolve X screen from DISPLAY={current_display!r}")
    return f"{match.group('base')}.{DISPLAY_TARGET_SCREENS[target]}"


def effective_display_target(
    explicit_target: str | None,
    environment: dict[str, str],
) -> str | None:
    """Map GNOME's generic discrete-GPU launch context to the RTX screen."""

    if explicit_target is not None:
        return explicit_target
    if any(environment.get(key) for key in DISCRETE_GPU_ENVIRONMENT_KEYS):
        return "rtx"
    return None


def audio_sink_for_target(target: str, sink_listing: str) -> str:
    """Select the sole HDMI or non-HDMI output for the requested screen."""

    if target not in DISPLAY_TARGET_SCREENS:
        raise ValueError(f"unsupported SENTRY display target: {target}")
    names = [
        line.split("\t", 2)[1]
        for line in sink_listing.splitlines()
        if "\t" in line and len(line.split("\t", 2)) >= 2
    ]
    if target == "rtx":
        candidates = [name for name in names if "hdmi" in name.lower()]
    else:
        candidates = [name for name in names if "hdmi" not in name.lower()]
    if len(candidates) != 1:
        raise RuntimeError(
            f"expected exactly one {target} playback sink, found {len(candidates)}"
        )
    return candidates[0]


def _write_ui_environment(path: Path, *, display: str, xauthority: str) -> None:
    """Atomically persist the target X screen consumed by sentry-ui.service."""

    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as temporary:
            temporary.write(f"DISPLAY={display}\nXAUTHORITY={xauthority}\n")
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_name = temporary.name
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, path)
        temporary_name = ""
    finally:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)


def configure_ui_target(
    target: str,
    *,
    run: Callable[..., subprocess.CompletedProcess[str]] = _run,
    environment: dict[str, str] | None = None,
    display_environment_path: Path = UI_DISPLAY_ENVIRONMENT_PATH,
) -> tuple[str, str]:
    """Validate and persist one display/output pair without changing audio input."""

    current_environment = dict(os.environ if environment is None else environment)
    display = display_for_target(target, current_environment.get("DISPLAY", ""))
    xauthority = current_environment.get("XAUTHORITY") or str(
        Path(f"/run/user/{os.getuid()}/gdm/Xauthority")
    )
    display_probe_environment = dict(current_environment)
    display_probe_environment.update({"DISPLAY": display, "XAUTHORITY": xauthority})
    run(["xdpyinfo", "-display", display], env=display_probe_environment)
    sinks = run(
        ["pactl", "list", "short", "sinks"],
        stdout=subprocess.PIPE,
    )
    sink = audio_sink_for_target(target, sinks.stdout)
    _write_ui_environment(
        display_environment_path,
        display=display,
        xauthority=xauthority,
    )
    run(["pactl", "set-default-sink", sink])
    return display, sink


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
    display_target: str | None = None,
    run: Callable[..., subprocess.CompletedProcess[str]] = _run,
    sleep: Callable[[float], None] = time.sleep,
    environment: dict[str, str] | None = None,
    display_environment_path: Path = UI_DISPLAY_ENVIRONMENT_PATH,
) -> tuple[str, ...]:
    """Start missing configured units and bring the native SENTRY window forward."""

    units = configured_launch_units(config_path)
    if display_target is None:
        run(["systemctl", "--user", "start", *units])
    else:
        configure_ui_target(
            display_target,
            run=run,
            environment=environment,
            display_environment_path=display_environment_path,
        )
        supporting_units = tuple(unit for unit in units if unit != UI_UNIT)
        if supporting_units:
            run(["systemctl", "--user", "start", *supporting_units])
        run(["systemctl", "--user", "restart", UI_UNIT])
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
    parser.add_argument("--display", choices=tuple(DISPLAY_TARGET_SCREENS))
    args = parser.parse_args(argv)
    display_target = effective_display_target(args.display, dict(os.environ))
    try:
        units = launch(args.config.expanduser(), display_target=display_target)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        message = f"{type(exc).__name__}: {exc}"
        print(f"SENTRY launch failed: {message}", file=sys.stderr)
        _notify_failure(message)
        return 2
    target = f" on {display_target}" if display_target else ""
    print(f"SENTRY ready{target} ({', '.join(units)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
