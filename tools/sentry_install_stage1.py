"""Plan/install reviewed startup units only; no settings, enable or restart.

The general resident installer owns first-time provisioning. This preservation-
first reconciler renders current checkout paths without invoking that broader
installer. --anima-core adds only the existing authenticated Core dependency.
Existing profile/config/thread state is neither regenerated nor edited here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from tools.sentry_install_user_services import LEGACY_REPO_ROOT, REPO_ROOT

UNITS = ("sentry-voice.service", "sentry-voice-supervisor.service", "sentry-ui.service",
         "sentry-state-api.service", "sentry-perception.service", "sentry-proactive.service",
         "sentry-weather.service", "sentry-routines.service", "sentry-alarms.service",
         "sentry-projection-status.service")


def deployment_files(home: Path, *, anima_core: bool = False) -> dict[Path, bytes]:
    root = home / ".config/systemd/user"
    files = {}
    for name in UNITS:
        text = (REPO_ROOT / "deploy/systemd/user" / name).read_text()
        files[root / name] = text.replace(LEGACY_REPO_ROOT, str(REPO_ROOT).replace("%", "%%")).encode()
    if anima_core:
        for name in ("sentry-voice.service", "sentry-voice-supervisor.service"):
            files[root / f"{name}.d/20-anima-core.conf"] = (
                "[Unit]\nRequires=anima-core.service\nAfter=anima-core.service\n"
            ).encode()
    return files


def install_files(files: dict[Path, bytes]) -> None:
    for path in files:
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise ValueError("unsafe deployment destination")
        if any(parent.is_symlink() for parent in path.parents):
            raise ValueError("unsafe deployment parent")
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--anima-core", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    files = deployment_files(Path.home(), anima_core=args.anima_core)
    if args.apply:
        install_files(files)
    print(json.dumps({"applied": args.apply, "services_started": False,
                      "files": [{"path": str(path), "sha256": hashlib.sha256(content).hexdigest()}
                                for path, content in sorted(files.items())]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
