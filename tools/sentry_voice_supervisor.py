"""Keep resident SENTRY voice aligned with ANIMA-owned sleep mode."""

from __future__ import annotations

import argparse
import json
import os
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
UI_UNIT = "sentry-ui.service"
VALID_INSTANCE_IDS = {"living_room", "office"}


def _voice_status_path() -> Path:
    return Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "sentry/voice.json"


def _systemctl(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["systemctl", "--user", *arguments],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )


def unit_is_active(unit: str) -> bool:
    return _systemctl("is-active", "--quiet", unit).returncode == 0


def voice_is_active() -> bool:
    return unit_is_active(VOICE_UNIT)


def _runtime_signature(path: Path | None = None) -> tuple[str, str, float] | None:
    target = path or _voice_status_path()
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    instance = value.get("active_instance_id")
    voice = value.get("voice_id")
    speed = value.get("speech_speed")
    if (
        not isinstance(instance, str)
        or instance not in VALID_INSTANCE_IDS
        or not isinstance(voice, str)
        or isinstance(speed, bool)
        or not isinstance(speed, (int, float))
    ):
        return None
    return instance, voice, round(float(speed), 2)


def _desired_signature(settings: dict[str, object]) -> tuple[str, str, float] | None:
    instance = settings.get("active_instance_id", "living_room")
    voice = settings.get("voice_id")
    speed = settings.get("speech_speed")
    if (
        not isinstance(instance, str)
        or instance not in VALID_INSTANCE_IDS
        or not isinstance(voice, str)
        or isinstance(speed, bool)
        or not isinstance(speed, (int, float))
    ):
        return None
    return instance, voice, round(float(speed), 2)


def reconcile_visible_face(active_instance_id: str) -> str:
    """Keep the PC face visible only when the office endpoint is selected."""

    active = unit_is_active(UI_UNIT)
    if active_instance_id == "office" and not active:
        return "office_ui_started" if _systemctl("start", UI_UNIT).returncode == 0 else "office_ui_failed"
    if active_instance_id == "living_room" and active:
        return "office_ui_stopped" if _systemctl("stop", UI_UNIT).returncode == 0 else "office_ui_failed"
    return "face_ready"


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
    signature = _desired_signature(value)
    if not isinstance(sleep_enabled, bool) or signature is None:
        return "invalid_anima_setting"
    active_instance_id = signature[0]
    if reconcile_visible_face(active_instance_id) == "office_ui_failed":
        return "face_switch_failed"
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
        if _runtime_signature() != signature:
            result = _systemctl("restart", VOICE_UNIT)
            return "switching_instance" if result.returncode == 0 else "instance_restart_failed"
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
            return 0 if status not in {
                "start_failed",
                "sleep_restart_failed",
                "invalid_anima_setting",
                "face_switch_failed",
                "instance_restart_failed",
            } else 1
        time.sleep(args.poll_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
