"""Install or inspect SENTRY's host-restricted resident Codex CLI profile."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import tomllib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PROFILE_NAME = "sentry-resident"
DEVELOPMENT_PROFILE_NAME = "sentry"
MODEL_CONTEXT_WINDOW_TOKENS = 272_000
AUTO_COMPACT_TOKEN_LIMIT = 217_600


def _default_workspace() -> Path:
    return Path(os.environ.get("SENTRY_AGENT_WORKSPACE", "~/.local/share/sentry/agent-workspace")).expanduser()


def _default_authority_root() -> Path:
    return Path(os.environ.get("SENTRY_AUTHORITY_ROOT", "~/.local/state/sentry/execution-authority")).expanduser()


def _default_resident_codex_home() -> Path:
    return Path(os.environ.get("SENTRY_CODEX_HOME", "~/.local/share/sentry/codex-home")).expanduser()


def _filesystem_rules(denied: list[str]) -> str:
    lines = ['":minimal" = "read"', "glob_scan_max_depth = 4"]
    lines.extend(f"{json.dumps(path)} = \"deny\"" for path in denied)
    return "\n".join(lines)


def profile_text(
    *, python_executable: Path, config_path: Path, workspace_path: Path | None = None,
    authority_root: Path | None = None, memory_vault_path: Path | None = None,
    resident_codex_home: Path | None = None,
) -> str:
    skill = REPO_ROOT / "integrations/codex/plugins/sentry-office/skills/sentry-office-agent"
    server = REPO_ROOT / "tools/sentry_mcp_server.py"
    instructions = REPO_ROOT / "integrations/codex/SENTRY_AGENT_INSTRUCTIONS.md"
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    dbus = os.environ.get("DBUS_SESSION_BUS_ADDRESS", f"unix:path={runtime_dir}/bus")
    display = os.environ.get("DISPLAY", ":0")
    xauthority = os.environ.get("XAUTHORITY", str(Path(runtime_dir) / "gdm/Xauthority"))
    home = Path.home().resolve()
    workspace = Path(workspace_path or _default_workspace()).expanduser().resolve()
    authority = Path(authority_root or _default_authority_root()).expanduser().resolve()
    resident_home = Path(resident_codex_home or _default_resident_codex_home()).expanduser().resolve()
    denied = [
        str(home / ".ssh"), str(home / ".gnupg"), str(home / ".aws"), str(home / ".azure"),
        str(home / ".config/gcloud"), str(home / ".kube"), str(home / ".docker/config.json"),
        str(home / ".npmrc"), str(home / ".pypirc"), str(home / ".netrc"),
        str(home / ".git-credentials"), str(home / ".config/gh"), str(home / ".local/share/keyrings"),
        str(home / ".config/chromium"), str(home / ".config/google-chrome"), str(home / ".mozilla"),
        str(home / ".bash_history"), str(home / ".zsh_history"), str(home / ".codex/auth.json"),
        str(home / ".config/sentry"), str(home / ".local/share/sentry/identity"),
        str(home / ".local/share/sentry/biometrics"), str(home / ".local/share/sentry/atlas"),
        str(authority), str(resident_home),
    ]
    if memory_vault_path:
        denied.append(str(Path(memory_vault_path).expanduser().resolve()))
    return f'''model = "gpt-5.6-luna"
model_reasoning_effort = "medium"
model_auto_compact_token_limit = {AUTO_COMPACT_TOKEN_LIMIT}
approval_policy = "never"
default_permissions = "sentry-resident"
model_instructions_file = "{instructions}"
allow_login_shell = false

[permissions.sentry-resident]
description = "SENTRY resident workspace with command network disabled"
extends = ":workspace"

[permissions.sentry-resident.workspace_roots]
"{workspace}" = true

[permissions.sentry-resident.filesystem]
{_filesystem_rules(denied)}

[permissions.sentry-resident.filesystem.":workspace_roots"]
"." = "write"
"*.env" = "deny"
".*.env" = "deny"
"**/*.env" = "deny"
"**/*credential*" = "deny"
"**/*secret*" = "deny"
"**/*token*" = "deny"

[permissions.sentry-resident.network]
enabled = false

[shell_environment_policy]
inherit = "none"
set = {{ PATH = "/usr/local/bin:/usr/bin:/bin", HOME = "{home}", LANG = "C.UTF-8", LC_ALL = "C.UTF-8", TMPDIR = "/tmp", SENTRY_AGENT_WORKSPACE = "{workspace}" }}

[features]
apps = false
browser_use = false
browser_use_external = false
browser_use_full_cdp_access = false
computer_use = false
image_generation = true
memories = false
plugins = false
shell_tool = true
view_image = true
workspace_dependencies = true

[memories]
generate_memories = false
use_memories = false
disable_on_external_context = true

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
env_vars = ["SENTRY_REQUEST_ID", "SENTRY_THREAD_ID", "SENTRY_OPERATOR_REQUEST", "SENTRY_AUTHORITY_EPOCH"]

[mcp_servers.sentry_office.env]
SENTRY_BASE_URL = "http://127.0.0.1:48174"
SENTRY_CONFIG_PATH = "{config_path}"
SENTRY_DISPLAY_TIMEZONE = "America/New_York"
SENTRY_AGENT_WORKSPACE = "{workspace}"
SENTRY_AUTHORITY_ROOT = "{authority}"
XDG_RUNTIME_DIR = "{runtime_dir}"
DBUS_SESSION_BUS_ADDRESS = "{dbus}"
DISPLAY = "{display}"
XAUTHORITY = "{xauthority}"
'''


def install(
    *, codex_home: Path, python_executable: Path, config_path: Path,
    workspace_path: Path | None = None, authority_root: Path | None = None,
    memory_vault_path: Path | None = None,
) -> dict:
    if not python_executable.is_file():
        raise ValueError(f"SENTRY Python runtime does not exist: {python_executable}")
    if not config_path.is_file():
        raise ValueError(f"SENTRY local config does not exist: {config_path}")
    if memory_vault_path is None:
        try:
            local_config = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("SENTRY local config is not valid JSON") from exc
        configured_vault = (local_config.get("agent") or {}).get("memory_vault_path")
        if configured_vault:
            memory_vault_path = Path(str(configured_vault)).expanduser()
    destination = codex_home / f"{PROFILE_NAME}.config.toml"
    destination.parent.mkdir(parents=True, exist_ok=True)
    workspace = Path(workspace_path or _default_workspace()).expanduser()
    authority = Path(authority_root or _default_authority_root()).expanduser()
    workspace.mkdir(mode=0o700, parents=True, exist_ok=True)
    workspace.chmod(0o700)
    authority.mkdir(mode=0o700, parents=True, exist_ok=True)
    authority.chmod(0o700)
    text = profile_text(
        python_executable=python_executable.absolute(), config_path=config_path.resolve(),
        workspace_path=workspace, authority_root=authority, memory_vault_path=memory_vault_path,
        resident_codex_home=codex_home,
    )
    tomllib.loads(text)
    destination.write_text(text, encoding="utf-8")
    destination.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return {
        "installed": True, "profile": PROFILE_NAME, "path": str(destination),
        "mode": oct(destination.stat().st_mode & 0o777), "workspace": str(workspace.resolve()),
        "workspace_mode": oct(workspace.stat().st_mode & 0o777),
        "development_profile_preserved": (codex_home / f"{DEVELOPMENT_PROFILE_NAME}.config.toml").is_file(),
        "memory_vault_denied": str(memory_vault_path.resolve()) if memory_vault_path else None,
    }


def link_resident_runtime(*, resident_codex_home: Path, source_codex_home: Path) -> dict:
    """Share only Codex-owned authentication/thread state with the private resident home."""

    resident_codex_home.mkdir(mode=0o700, parents=True, exist_ok=True)
    resident_codex_home.chmod(0o700)
    linked: list[str] = []
    for name in (
        "auth.json", "sessions", "archived_sessions", "session_index.jsonl",
        "thread_history_1.sqlite", "thread_history_1.sqlite-shm", "thread_history_1.sqlite-wal",
        "thread-writer-locks",
    ):
        source = source_codex_home / name
        destination = resident_codex_home / name
        if not source.exists() or destination.exists() or destination.is_symlink():
            continue
        destination.symlink_to(source, target_is_directory=source.is_dir())
        linked.append(name)
    if not (resident_codex_home / "auth.json").exists():
        raise ValueError("Codex authentication state is unavailable for the resident runtime")
    return {"runtime_home": str(resident_codex_home), "linked": linked}


def constrain_generated_images(*, resident_codex_home: Path, workspace_path: Path) -> dict:
    """Keep Codex image-generation staging inside the approved resident workspace."""

    target = workspace_path / ".codex-generated-images"
    target.mkdir(mode=0o700, parents=True, exist_ok=True)
    source = resident_codex_home / "generated_images"
    migrated: list[str] = []
    if source.is_symlink():
        if source.resolve() != target.resolve():
            raise ValueError("resident generated-images link points outside the approved workspace")
        return {"generated_images": str(target), "image_output_constrained": True, "migrated": migrated}
    if source.is_dir():
        for item in source.iterdir():
            destination = target / item.name
            if destination.exists():
                raise ValueError(f"generated-image migration collision: {destination}")
            shutil.move(str(item), str(destination))
            migrated.append(item.name)
        source.rmdir()
    elif source.exists():
        raise ValueError("resident generated-images path is not a directory")
    source.symlink_to(target, target_is_directory=True)
    return {"generated_images": str(target), "image_output_constrained": True, "migrated": migrated}


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
        "model_auto_compact_token_limit": data.get("model_auto_compact_token_limit"),
        "default_permissions": data.get("default_permissions"),
        "sandbox_mode": data.get("sandbox_mode"),
        "approval_policy": data.get("approval_policy"),
        "command_network": ((data.get("permissions") or {}).get("sentry-resident") or {}).get("network", {}).get("enabled"),
        "features": data.get("features", {}),
        "mcp_servers": sorted((data.get("mcp_servers") or {}).keys()),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    install_parser = sub.add_parser("install")
    install_parser.add_argument("--python", type=Path, default=Path("~/.venvs/sentry-ubuntu/bin/python").expanduser())
    install_parser.add_argument("--config", type=Path, default=Path("~/.config/sentry/config.json").expanduser())
    install_parser.add_argument("--workspace", type=Path, default=_default_workspace())
    install_parser.add_argument("--authority-root", type=Path, default=_default_authority_root())
    install_parser.add_argument("--memory-vault", type=Path)
    install_parser.add_argument("--resident-codex-home", type=Path, default=_default_resident_codex_home())
    sub.add_parser("status")
    args = parser.parse_args(argv)
    source_codex_home = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
    codex_home = args.resident_codex_home.expanduser() if args.command == "install" else _default_resident_codex_home()
    try:
        result = install(
            codex_home=codex_home, python_executable=args.python.expanduser(), config_path=args.config.expanduser(),
            workspace_path=args.workspace.expanduser(), authority_root=args.authority_root.expanduser(),
            memory_vault_path=args.memory_vault.expanduser() if args.memory_vault else None,
        ) if args.command == "install" else status(codex_home=codex_home)
        if args.command == "install":
            result.update(link_resident_runtime(resident_codex_home=codex_home, source_codex_home=source_codex_home))
            result.update(constrain_generated_images(resident_codex_home=codex_home, workspace_path=args.workspace.expanduser()))
            result["development_profile_preserved"] = (source_codex_home / f"{DEVELOPMENT_PROFILE_NAME}.config.toml").is_file()
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps({"ok": True, **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
