"""Keep resident SENTRY voice aligned with ANIMA-owned sleep mode."""

from __future__ import annotations

import argparse
import signal
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.sentry_anima import AnimaConfig

VOICE_UNIT = "sentry-voice.service"


def _systemctl(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["systemctl", "--user", *arguments],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )


def voice_is_active() -> bool:
    return _systemctl("is-active", "--quiet", VOICE_UNIT).returncode == 0


def reconcile_once() -> str:
    """Apply the server-owned desired state once; never read local sleep config."""

    config = AnimaConfig.load()
    if config is None:
        if voice_is_active():
            result = _systemctl("stop", VOICE_UNIT)
            return "anima_unavailable_stopped" if result.returncode == 0 else "anima_unavailable_stop_failed"
        return "anima_unavailable"
    value = config.client().voice_settings()
    sleep_enabled = value.get("sleep_enabled")
    if not isinstance(sleep_enabled, bool):
        return "invalid_anima_setting"
    active = voice_is_active()
    if sleep_enabled:
        if active:
            # Let the voice process perform its normal ANIMA read and publish
            # an explicit SLEEPING diagnostic before it exits cleanly.
            result = _systemctl("restart", VOICE_UNIT)
            if result.returncode != 0:
                return "sleep_restart_failed"
        return "sleeping"
    if active:
        return "standby"
    _systemctl("reset-failed", VOICE_UNIT)
    result = _systemctl("start", VOICE_UNIT)
    return "starting" if result.returncode == 0 else "start_failed"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args(argv)
    if args.poll_seconds <= 0:
        raise SystemExit("--poll-seconds must be positive")
    stop = False

    def request_stop(*_signals: int) -> None:
        nonlocal stop
        stop = True

    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, request_stop)
    while not stop:
        try:
            status = reconcile_once()
        except Exception as exc:  # noqa: BLE001 - supervisor must keep retrying
            status = f"supervisor_error:{type(exc).__name__}"
        print(status, flush=True)
        if args.once:
            return 0 if status not in {"start_failed", "sleep_restart_failed", "invalid_anima_setting"} else 1
        time.sleep(args.poll_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
