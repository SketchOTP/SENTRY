"""Install the SENTRY resident stack as native systemd user services."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
UNIT_ROOT = REPO_ROOT / "deploy" / "systemd" / "user"
ICON_SOURCE = REPO_ROOT / "deploy" / "icons" / "hicolor" / "512x512" / "apps" / "sentry.png"
UNIT_NAMES = ("sentry-perception.service", "sentry-state-api.service", "sentry-proactive.service")
ROUTINE_UNIT_NAMES = ("sentry-routines.service", "sentry-routines.timer")
WEATHER_UNIT_NAMES = ("sentry-weather.service", "sentry-weather.timer")
VOICE_UNIT_NAMES = ("sentry-voice.service", "sentry-ui.service")
ALARM_UNIT_NAMES = ("sentry-alarms.service", "sentry-alarms.timer")
LEGACY_UI_UNIT_NAMES = ("sentry-voice-status.service", "sentry-identity-ui.service")


def production_config(example_path: Path) -> dict:
    config = json.loads(example_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("production config source must be a JSON object")
    proactivity = config.setdefault("proactivity", {})
    if not isinstance(proactivity, dict):
        raise ValueError("production config proactivity must be an object")
    proactivity["enabled"] = True
    return config


def _run_systemctl(*arguments: str) -> None:
    subprocess.run(["systemctl", "--user", *arguments], check=True)


def _desktop_directory() -> Path:
    executable = shutil.which("xdg-user-dir")
    if executable is not None:
        result = subprocess.run(
            [executable, "DESKTOP"],
            check=False,
            capture_output=True,
            text=True,
        )
        resolved = result.stdout.strip()
        if result.returncode == 0 and resolved:
            return Path(resolved).expanduser()
    return Path.home() / "Desktop"


def _install_desktop_launcher(source: Path, destination: Path, *, trust: bool) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    destination.chmod(0o755)
    if trust and shutil.which("gio") is not None:
        subprocess.run(
            ["gio", "set", str(destination), "metadata::trusted", "true"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def _weather_configured(config: dict) -> bool:
    weather = config.get("weather")
    return isinstance(weather, dict) and bool(weather.get("enabled")) and weather.get("latitude") is not None and weather.get("longitude") is not None


def _voice_enabled(config: dict) -> bool:
    voice = config.get("voice")
    return isinstance(voice, dict) and bool(voice.get("always_on_enabled"))


def _alarms_enabled(config: dict) -> bool:
    alarms = config.get("alarms", {})
    return isinstance(alarms, dict) and bool(alarms.get("enabled", True))


def _continuous_perception_enabled(config: dict) -> bool:
    resident = config.get("resident", {})
    return isinstance(resident, dict) and bool(resident.get("continuous_perception_enabled", False))


def _continuous_proactivity_enabled(config: dict) -> bool:
    resident = config.get("resident", {})
    proactivity = config.get("proactivity", {})
    return (
        isinstance(resident, dict)
        and bool(resident.get("continuous_proactivity_enabled", False))
        and isinstance(proactivity, dict)
        and bool(proactivity.get("enabled", False))
    )


def install(config_path: Path, *, start: bool = True, systemd_user_dir: Path | None = None) -> Path:
    """Install units and create a production config without overwriting one."""

    config_path = config_path.expanduser()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if config_path.exists():
        existing = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(existing, dict):
            raise RuntimeError(f"existing production config must be an object: {config_path}")
    else:
        config_path.write_text(json.dumps(production_config(REPO_ROOT / "perception" / "config.example.json"), indent=2) + "\n", encoding="utf-8")
        config_path.chmod(0o600)
        existing = json.loads(config_path.read_text(encoding="utf-8"))

    unit_dir = systemd_user_dir or (Path.home() / ".config" / "systemd" / "user")
    unit_dir.mkdir(parents=True, exist_ok=True)
    for name in (*UNIT_NAMES, *ROUTINE_UNIT_NAMES, *WEATHER_UNIT_NAMES, *VOICE_UNIT_NAMES, *ALARM_UNIT_NAMES):
        source = UNIT_ROOT / name
        if not source.is_file():
            raise FileNotFoundError(source)
        shutil.copyfile(source, unit_dir / name)
    for name in LEGACY_UI_UNIT_NAMES:
        legacy = unit_dir / name
        if legacy.exists():
            _run_systemctl("disable", "--now", name)
            legacy.unlink()
    application_dir = (
        Path.home() / ".local" / "share" / "applications"
        if systemd_user_dir is None
        else unit_dir.parent / "applications"
    )
    application_dir.mkdir(parents=True, exist_ok=True)
    launcher_source = REPO_ROOT / "deploy" / "applications" / "sentry-ui.desktop"
    shutil.copyfile(launcher_source, application_dir / "sentry-ui.desktop")
    icon_root = (
        Path.home() / ".local" / "share" / "icons"
        if systemd_user_dir is None
        else unit_dir.parent / "icons"
    )
    icon_destination = icon_root / "hicolor" / "512x512" / "apps" / "sentry.png"
    icon_destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ICON_SOURCE, icon_destination)
    desktop_dir = _desktop_directory() if systemd_user_dir is None else unit_dir.parent / "Desktop"
    _install_desktop_launcher(
        launcher_source,
        desktop_dir / "SENTRY.desktop",
        trust=systemd_user_dir is None,
    )
    legacy_desktop = application_dir / "sentry-identity-ui.desktop"
    if legacy_desktop.exists():
        legacy_desktop.unlink()
    _run_systemctl("daemon-reload")
    _run_systemctl("enable", "sentry-state-api.service")
    if _continuous_perception_enabled(existing):
        _run_systemctl("enable", "sentry-perception.service")
    else:
        _run_systemctl("disable", "sentry-perception.service")
    if _continuous_proactivity_enabled(existing):
        _run_systemctl("enable", "sentry-proactive.service")
    else:
        _run_systemctl("disable", "sentry-proactive.service")
    _run_systemctl("enable", "sentry-routines.timer")
    if _weather_configured(existing):
        _run_systemctl("enable", "sentry-weather.timer")
    else:
        _run_systemctl("disable", "sentry-weather.timer")
    if _voice_enabled(existing):
        _run_systemctl("enable", "sentry-voice.service")
    else:
        _run_systemctl("disable", *VOICE_UNIT_NAMES)
    if _alarms_enabled(existing):
        _run_systemctl("enable", "sentry-alarms.timer")
    else:
        _run_systemctl("disable", "sentry-alarms.timer")
    if start:
        _run_systemctl("restart", "sentry-state-api.service")
        if _continuous_perception_enabled(existing):
            _run_systemctl("restart", "sentry-perception.service")
        else:
            _run_systemctl("stop", "sentry-perception.service")
        if _continuous_proactivity_enabled(existing):
            _run_systemctl("restart", "sentry-proactive.service")
        else:
            _run_systemctl("stop", "sentry-proactive.service")
        _run_systemctl("start", "sentry-routines.timer")
        if _weather_configured(existing):
            _run_systemctl("start", "sentry-weather.timer")
        if _voice_enabled(existing):
            _run_systemctl("start", "sentry-voice.service")
        if _alarms_enabled(existing):
            _run_systemctl("start", "sentry-alarms.timer")
    return config_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("~/.config/sentry/config.json"))
    parser.add_argument("--no-start", action="store_true", help="install and enable units without starting them")
    args = parser.parse_args(argv)
    try:
        config_path = install(args.config, start=not args.no_start)
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"SENTRY resident install failed: {type(exc).__name__}: {exc}")
        return 2
    print(f"Installed SENTRY user services with production config {config_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
