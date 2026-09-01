"""Install or inspect SENTRY's dedicated Codex CLI profile."""

from __future__ import annotations

import argparse
import json
import os
import stat
import tomllib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PROFILE_NAME = "sentry"


def profile_text(*, python_executable: Path, config_path: Path) -> str:
    skill = REPO_ROOT / "integrations/codex/plugins/sentry-office/skills/sentry-office-agent"
    server = REPO_ROOT / "tools/sentry_mcp_server.py"
    instructions = REPO_ROOT / "integrations/codex/SENTRY_AGENT_INSTRUCTIONS.md"
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    dbus = os.environ.get("DBUS_SESSION_BUS_ADDRESS", f"unix:path={runtime_dir}/bus")
    display = os.environ.get("DISPLAY", ":0")
    xauthority = os.environ.get("XAUTHORITY", str(Path(runtime_dir) / "gdm/Xauthority"))
    return f'''model = "gpt-5.6-luna"
model_reasoning_effort = "medium"
sandbox_mode = "danger-full-access"
approval_policy = "never"
model_instructions_file = "{instructions}"

[features]
apps = true
browser_use = true
browser_use_external = true
browser_use_full_cdp_access = true
computer_use = true
image_generation = true
plugins = true
shell_tool = true
view_image = true
workspace_dependencies = true

[[skills.config]]
path = "{skill}"
enabled = true

[mcp_servers.sentry_office]
command = "{python_executable}"
args = ["{server}"]
cwd = "{REPO_ROOT}"
enabled = true
startup_timeout_sec = 30
tool_timeout_sec = 180

[mcp_servers.sentry_office.env]
SENTRY_BASE_URL = "http://127.0.0.1:48174"
SENTRY_CONFIG_PATH = "{config_path}"
SENTRY_DISPLAY_TIMEZONE = "America/New_York"
XDG_RUNTIME_DIR = "{runtime_dir}"
DBUS_SESSION_BUS_ADDRESS = "{dbus}"
DISPLAY = "{display}"
XAUTHORITY = "{xauthority}"
'''


def install(*, codex_home: Path, python_executable: Path, config_path: Path) -> dict:
    if not python_executable.is_file():
        raise ValueError(f"SENTRY Python runtime does not exist: {python_executable}")
    if not config_path.is_file():
        raise ValueError(f"SENTRY local config does not exist: {config_path}")
    destination = codex_home / f"{PROFILE_NAME}.config.toml"
    destination.parent.mkdir(parents=True, exist_ok=True)
    text = profile_text(python_executable=python_executable.resolve(), config_path=config_path.resolve())
    tomllib.loads(text)
    destination.write_text(text, encoding="utf-8")
    destination.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return {"installed": True, "profile": PROFILE_NAME, "path": str(destination), "mode": oct(destination.stat().st_mode & 0o777)}


def status(*, codex_home: Path) -> dict:
    destination = codex_home / f"{PROFILE_NAME}.config.toml"
    if not destination.is_file():
        return {"installed": False, "profile": PROFILE_NAME, "path": str(destination)}
    data = tomllib.loads(destination.read_text(encoding="utf-8"))
    return {
        "installed": True,
        "profile": PROFILE_NAME,
        "path": str(destination),
        "mode": oct(destination.stat().st_mode & 0o777),
        "model": data.get("model"),
        "sandbox_mode": data.get("sandbox_mode"),
        "approval_policy": data.get("approval_policy"),
        "mcp_servers": sorted((data.get("mcp_servers") or {}).keys()),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    install_parser = sub.add_parser("install")
    install_parser.add_argument("--python", type=Path, default=Path("~/.venvs/sentry-ubuntu/bin/python").expanduser())
    install_parser.add_argument("--config", type=Path, default=Path("~/.config/sentry/config.json").expanduser())
    sub.add_parser("status")
    args = parser.parse_args(argv)
    codex_home = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
    try:
        result = install(codex_home=codex_home, python_executable=args.python.expanduser(), config_path=args.config.expanduser()) if args.command == "install" else status(codex_home=codex_home)
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps({"ok": True, **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
