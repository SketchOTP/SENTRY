"""Install the SENTRY resident stack as native systemd user services."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
UNIT_ROOT = REPO_ROOT / "deploy" / "systemd" / "user"
UNIT_NAMES = ("sentry-perception.service", "sentry-state-api.service", "sentry-proactive.service")
ROUTINE_UNIT_NAMES = ("sentry-routines.service", "sentry-routines.timer")


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


def install(config_path: Path, *, start: bool = True, systemd_user_dir: Path | None = None) -> Path:
    """Install units and create a production config without overwriting one."""

    config_path = config_path.expanduser()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if config_path.exists():
        existing = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(existing, dict) or not existing.get("proactivity", {}).get("enabled", False):
            raise RuntimeError(f"existing production config is not enabled for proactivity: {config_path}")
    else:
        config_path.write_text(json.dumps(production_config(REPO_ROOT / "perception" / "config.example.json"), indent=2) + "\n", encoding="utf-8")
        config_path.chmod(0o600)

    unit_dir = systemd_user_dir or (Path.home() / ".config" / "systemd" / "user")
    unit_dir.mkdir(parents=True, exist_ok=True)
    for name in (*UNIT_NAMES, *ROUTINE_UNIT_NAMES):
        source = UNIT_ROOT / name
        if not source.is_file():
            raise FileNotFoundError(source)
        shutil.copyfile(source, unit_dir / name)
    _run_systemctl("daemon-reload")
    _run_systemctl("enable", *UNIT_NAMES)
    _run_systemctl("enable", "sentry-routines.timer")
    if start:
        _run_systemctl("restart", *UNIT_NAMES)
        _run_systemctl("start", "sentry-routines.timer")
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
