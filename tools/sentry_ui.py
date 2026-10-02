"""Native GTK display surface for SENTRY voice state."""

from __future__ import annotations

import argparse
import base64
import json
import math
import os
import sys
import threading
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DESKTOP_ORB_SIZE = 600
PROJECTION_ORB_SIZE = DESKTOP_ORB_SIZE * 2
SENSOR_DRAWER_DEFAULT_WIDTH = 128
SENSOR_DRAWER_MIN_WIDTH = 128
SENSOR_DRAWER_MAX_WIDTH = 480

from perception.remote_voice import authorization_header, read_private_token
from perception.voice import (
    KOKORO_ENGLISH_VOICE_IDS,
    KOKORO_ENGLISH_VOICES,
    KOKORO_MAX_SPEED,
    KOKORO_MIN_SPEED,
)
from tools.sentry_anima import AnimaConfig


def orb_canvas_size(*, projection_mode: bool) -> int:
    """Use a TV-appropriate orb canvas while preserving desktop composition."""

    return PROJECTION_ORB_SIZE if projection_mode else DESKTOP_ORB_SIZE


def load_voice_preferences(config_path: Path) -> tuple[str, float]:
    """Read the validated resident Kokoro preference without exposing other config."""

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("SENTRY config must be an object")
    voice = payload.get("voice", {})
    if not isinstance(voice, dict):
        raise TypeError("SENTRY voice config must be an object")
    identifier = str(voice.get("kokoro_voice", "bm_george"))
    speed = float(voice.get("kokoro_speed", 0.9))
    if identifier not in KOKORO_ENGLISH_VOICE_IDS:
        raise ValueError("configured Kokoro voice is not supported")
    if not KOKORO_MIN_SPEED <= speed <= KOKORO_MAX_SPEED:
        raise ValueError("configured Kokoro speed is outside the supported range")
    return identifier, speed


def _persist_voice_settings(config_path: Path, updates: dict[str, Any]) -> None:
    """Atomically persist validated voice settings while preserving all others."""

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("SENTRY config must be an object")
    voice = payload.setdefault("voice", {})
    if not isinstance(voice, dict):
        raise TypeError("SENTRY voice config must be an object")
    voice.update(updates)

    temporary = config_path.with_name(f".{config_path.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, config_path)
        config_path.chmod(0o600)
        directory_fd = os.open(config_path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def load_sensor_order(config_path: Path) -> list[str]:
    """Load the local desktop drawer order without exposing household data."""

    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return []
        ui = payload.get("ui", {})
        if not isinstance(ui, dict) or not isinstance(ui.get("sensor_panel_order"), list):
            return []
        return [str(value)[:128] for value in ui["sensor_panel_order"] if value]
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return []


def save_sensor_order(config_path: Path, order: list[str]) -> None:
    """Atomically persist only the desktop drawer order, retaining other config."""

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("SENTRY config must be an object")
    ui = payload.setdefault("ui", {})
    if not isinstance(ui, dict):
        raise TypeError("SENTRY UI config must be an object")
    ui["sensor_panel_order"] = [str(value)[:128] for value in order]

    temporary = config_path.with_name(f".{config_path.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, config_path)
        config_path.chmod(0o600)
        directory_fd = os.open(config_path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def sensor_drawer_width(value: Any) -> int:
    """Clamp a persisted drawer width to a usable, compact desktop range."""

    if isinstance(value, bool):
        return SENSOR_DRAWER_DEFAULT_WIDTH
    try:
        width = int(value)
    except (TypeError, ValueError):
        return SENSOR_DRAWER_DEFAULT_WIDTH
    return max(SENSOR_DRAWER_MIN_WIDTH, min(SENSOR_DRAWER_MAX_WIDTH, width))


def load_sensor_drawer_width(config_path: Path) -> int:
    """Load the local desktop drawer width, failing closed to the compact default."""

    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return SENSOR_DRAWER_DEFAULT_WIDTH
        ui = payload.get("ui", {})
        if not isinstance(ui, dict):
            return SENSOR_DRAWER_DEFAULT_WIDTH
        return sensor_drawer_width(ui.get("sensor_panel_width"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return SENSOR_DRAWER_DEFAULT_WIDTH


def save_sensor_drawer_width(config_path: Path, width: int) -> None:
    """Atomically persist only the drawer width while retaining other config."""

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("SENTRY config must be an object")
    ui = payload.setdefault("ui", {})
    if not isinstance(ui, dict):
        raise TypeError("SENTRY UI config must be an object")
    ui["sensor_panel_width"] = sensor_drawer_width(width)

    temporary = config_path.with_name(f".{config_path.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, config_path)
        config_path.chmod(0o600)
        directory_fd = os.open(config_path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def save_voice_preferences(config_path: Path, identifier: str, speed: float) -> None:
    """Atomically update only resident voice preferences and retain mode 0600."""

    if identifier not in KOKORO_ENGLISH_VOICE_IDS:
        raise ValueError("selected Kokoro voice is not supported")
    speed = round(float(speed), 2)
    if not KOKORO_MIN_SPEED <= speed <= KOKORO_MAX_SPEED:
        raise ValueError("selected Kokoro speed is outside the supported range")
    _persist_voice_settings(
        config_path,
        {"kokoro_voice": identifier, "kokoro_speed": speed},
    )


def preview_voice(identifier: str, speed: float) -> bool:
    """Speak one bounded local sample without changing the saved preference."""

    from perception.voice import KokoroSpeaker

    return KokoroSpeaker(voice=identifier, speed=speed).speak(
        "Hello, operator. I am Sentry. This is how my voice will sound."
    )


VOICE_GUIDANCE = {
    "SLEEPING": "Sleeping",
    "STARTING": "Waking SENTRY…",
    "LISTENING": "Standby",
    "WAKE_DETECTED": "Wake detected",
    "CAPTURING": "Listening",
    "FINISHING_REQUEST": "Finishing request",
    "TRANSCRIBING": "Understanding",
    "ARMED": "Listening",
    "AWAITING_OPERATOR_RESPONSE": "Waiting for response",
    "FOLLOWUP_LISTENING": "Listening for follow-up",
    "PROCESSING": "Processing",
    "SPEAKING": "Speaking",
    "DISABLED": "Offline",
}

RUNTIME_TO_ORB_STATE = {
    "SLEEPING": "OFFLINE",
    "STARTING": "PROCESSING",
    "LISTENING": "STANDBY",
    "WAKE_DETECTED": "WAKE_DETECTED",
    "CAPTURING": "LISTENING",
    "ARMED": "LISTENING",
    "AWAITING_OPERATOR_RESPONSE": "LISTENING",
    "FINISHING_REQUEST": "PROCESSING",
    "TRANSCRIBING": "PROCESSING",
    "PROCESSING": "PROCESSING",
    "SPEAKING": "SPEAKING",
    "FOLLOWUP_LISTENING": "FOLLOWUP_LISTENING",
    "DISABLED": "OFFLINE",
    "UNAVAILABLE": "OFFLINE",
}


def projection_instance_payload(
    payload: dict[str, Any], *, projection_instance_id: str = "living_room"
) -> dict[str, Any]:
    """Keep an inactive projection dormant rather than mirroring another room."""

    active_instance_id = payload.get("active_instance_id")
    if isinstance(active_instance_id, str) and active_instance_id != projection_instance_id:
        return {
            "state": "INACTIVE",
            "reason": f"SENTRY is active in {active_instance_id.replace('_', ' ')}.",
            "active_instance_id": active_instance_id,
            "sleep_enabled": False,
            "wake_enabled": False,
        }
    return payload

ORB_STYLES = {
    "STANDBY": {
        "color": (0.20, 0.16, 0.55), "secondary": (0.08, 0.28, 0.62),
        "brightness": 0.42, "shell": 1.0, "deform": 0.008, "halo": 0.02,
        "energy": 0.18, "float": 1.0, "mode": "dormant",
    },
    "WAKE_DETECTED": {
        "color": (0.34, 0.94, 1.0), "secondary": (0.95, 1.0, 1.0),
        "brightness": 1.0, "shell": 0.92, "deform": 0.02, "halo": 1.0,
        "energy": 1.0, "float": 0.7, "mode": "ignition",
    },
    "LISTENING": {
        "color": (0.08, 0.98, 0.56), "secondary": (0.12, 0.68, 1.0),
        "brightness": 0.82, "shell": 1.0, "deform": 0.05, "halo": 0.14,
        "energy": 0.58, "float": 1.0, "mode": "receptive",
    },
    "PROCESSING": {
        "color": (0.54, 0.20, 1.0), "secondary": (0.08, 0.76, 1.0),
        "brightness": 0.78, "shell": 1.0, "deform": 0.012, "halo": 0.08,
        "energy": 0.82, "float": 1.0, "mode": "orbiting",
    },
    "SPEAKING": {
        "color": (0.65, 0.24, 1.0), "secondary": (0.96, 0.88, 1.0),
        "brightness": 0.90, "shell": 1.0, "deform": 0.0, "halo": 0.15,
        "energy": 0.75, "float": 1.0, "mode": "emissive",
    },
    "FOLLOWUP_LISTENING": {
        "color": (0.08, 0.90, 0.62), "secondary": (0.10, 0.62, 1.0),
        "brightness": 0.76, "shell": 1.0, "deform": 0.045, "halo": 0.10,
        "energy": 0.48, "float": 1.0, "mode": "receptive",
    },
    "OFFLINE": {
        "color": (0.22, 0.21, 0.28), "secondary": (0.34, 0.31, 0.42),
        "brightness": 0.24, "shell": 1.0, "deform": 0.0, "halo": 0.0,
        "energy": 0.0, "float": 0.0, "mode": "offline",
    },
}

ORB_STATE_INDEX = {
    "OFFLINE": 0,
    "STANDBY": 1,
    "WAKE_DETECTED": 2,
    "LISTENING": 3,
    "PROCESSING": 4,
    "SPEAKING": 5,
    "FOLLOWUP_LISTENING": 6,
}


def voice_indicator_model(payload: dict[str, Any]) -> dict[str, Any]:
    """Map detailed runtime states onto one accessible semantic orb state."""

    state = str(payload.get("state") or payload.get("status") or "UNAVAILABLE").upper()
    semantic_state = RUNTIME_TO_ORB_STATE.get(state, "OFFLINE")
    return {
        "state": state,
        "semantic_state": semantic_state,
        "label": semantic_state.replace("_", " "),
        "microphone_level": max(0.0, min(1.0, float(payload.get("microphone_audio_level", 0.0) or 0.0))),
        "output_level": max(0.0, min(1.0, float(payload.get("output_audio_level", 0.0) or 0.0))),
    }


def _lerp(left: float, right: float, amount: float) -> float:
    return left + (right - left) * max(0.0, min(1.0, amount))


class OrbStateController:
    """Central semantic, transition, and audio-intensity controller for the orb."""

    def __init__(self, *, now: float | None = None) -> None:
        started = time.monotonic() if now is None else float(now)
        self.state = "STANDBY"
        self.previous_state = self.state
        self.previous_style = dict(ORB_STYLES[self.state])
        self.target_style = dict(ORB_STYLES[self.state])
        self.transition_started = started
        self.transition_duration = 0.8
        self.last_frame_at = started
        self.mic_level = 0.0
        self.output_level = 0.0
        self.target_mic_level = 0.0
        self.target_output_level = 0.0
        self.previous_audio_level = 0.0
        self.wake_started: float | None = None

    def update(self, payload: dict[str, Any], *, now: float | None = None) -> dict[str, Any]:
        timestamp = time.monotonic() if now is None else float(now)
        model = voice_indicator_model(payload)
        state = str(model["semantic_state"])
        if state != self.state:
            self.previous_audio_level = (
                self.mic_level
                if self.state in {"LISTENING", "FOLLOWUP_LISTENING"}
                else (self.output_level if self.state == "SPEAKING" else 0.0)
            )
            self.previous_style = self._interpolated_style(timestamp)
            self.previous_state = self.state
            self.state = state
            self.target_style = dict(ORB_STYLES[state])
            self.transition_started = timestamp
            if state == "WAKE_DETECTED":
                self.transition_duration = 0.18
            elif state == "STANDBY":
                self.transition_duration = 0.9
            elif state == "LISTENING" and self.previous_state == "WAKE_DETECTED":
                self.transition_duration = 0.82
            elif (
                self.previous_state in {"LISTENING", "FOLLOWUP_LISTENING"} and state == "PROCESSING"
            ) or (self.previous_state == "PROCESSING" and state == "SPEAKING"):
                self.transition_duration = 1.55
            elif state in {"SPEAKING", "FOLLOWUP_LISTENING"}:
                self.transition_duration = 0.72
            else:
                self.transition_duration = 0.62
        self.target_mic_level = float(model["microphone_level"])
        self.target_output_level = float(model["output_level"])
        return model

    def acknowledge_wake(self, *, now: float | None = None) -> None:
        self.wake_started = time.monotonic() if now is None else float(now)

    def _interpolated_style(self, now: float) -> dict[str, Any]:
        amount = self._transition_amount(now)
        amount = amount * amount * (3.0 - 2.0 * amount)
        style: dict[str, Any] = {}
        for key, target in self.target_style.items():
            previous = self.previous_style.get(key, target)
            if isinstance(target, tuple):
                style[key] = tuple(_lerp(float(a), float(b), amount) for a, b in zip(previous, target))
            elif isinstance(target, (int, float)):
                style[key] = _lerp(float(previous), float(target), amount)
            else:
                style[key] = target if amount >= 0.5 else previous
        return style

    def _transition_amount(self, now: float) -> float:
        return min(1.0, max(0.0, (now - self.transition_started) / max(0.001, self.transition_duration)))

    def frame(self, *, now: float | None = None, reduced_motion: bool = False) -> dict[str, Any]:
        timestamp = time.monotonic() if now is None else float(now)
        elapsed = max(0.0, timestamp - self.last_frame_at)
        self.last_frame_at = timestamp
        mic_rate = 3.2 if self.target_mic_level > self.mic_level else 1.7
        output_rate = 14.0 if self.target_output_level > self.output_level else 8.0
        self.mic_level = _lerp(
            self.mic_level,
            self.target_mic_level,
            1.0 - math.exp(-elapsed * mic_rate),
        )
        self.output_level = _lerp(
            self.output_level,
            self.target_output_level,
            1.0 - math.exp(-elapsed * output_rate),
        )
        style = self._interpolated_style(timestamp)
        active_level = self.mic_level if self.state in {"LISTENING", "FOLLOWUP_LISTENING"} else (
            self.output_level if self.state == "SPEAKING" else 0.0
        )
        motion_scale = 0.24 if reduced_motion else 1.0
        breathe = (math.sin(timestamp * math.tau / 4.0) + 1.0) * 0.5
        shell_scale = float(style["shell"])
        if self.state == "STANDBY":
            shell_scale += breathe * 0.018 * motion_scale
        elif self.state not in {"SPEAKING", "OFFLINE"}:
            shell_scale += breathe * 0.006 * motion_scale
        shell_scale += active_level * float(style["deform"]) * motion_scale
        if self.state == "SPEAKING":
            shell_scale = 1.0
        wake_progress = None
        if self.wake_started is not None:
            wake_progress = (timestamp - self.wake_started) / 0.24
            if wake_progress >= 1.8:
                self.wake_started = None
                wake_progress = None
            elif wake_progress < 0.55:
                shell_scale *= _lerp(1.0, 0.90, wake_progress / 0.55)
            elif wake_progress < 1.0:
                shell_scale *= _lerp(0.90, 1.045, (wake_progress - 0.55) / 0.45)
        return {
            **style,
            "state": self.state,
            "previous_state": self.previous_state,
            "transition_progress": self._transition_amount(timestamp),
            "shell_scale": shell_scale,
            "audio_level": active_level,
            "previous_audio_level": self.previous_audio_level,
            "life_breath": breathe,
            "float_offset": math.sin(timestamp * 0.9) * 5.0 * float(style["float"]) * motion_scale,
            "wake_progress": wake_progress,
            "reduced_motion": reduced_motion,
            "time": timestamp,
        }


def should_acknowledge_wake(previous_wake_at: object, current_wake_at: object) -> bool:
    """Animate once when a new explicit wake timestamp appears after startup."""

    previous = str(previous_wake_at or "").strip()
    current = str(current_wake_at or "").strip()
    return bool(previous and current and previous != current)
def voice_status_path() -> Path:
    return Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "sentry" / "voice.json"


def projection_io_request(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    *,
    config_path: Path | None = None,
) -> dict[str, Any]:
    """Call one fixed Pi projection endpoint through the private token boundary."""

    if path != "/v1/output" or method not in {"GET", "POST"}:
        raise ValueError("unsupported projection control")

    base_url = os.environ.get("SENTRY_PROJECTION_IO_BASE_URL")
    token_path = os.environ.get("SENTRY_PROJECTION_TOKEN_FILE")
    if not base_url or not token_path:
        source = config_path or Path(os.environ.get("SENTRY_CONFIG_PATH", "~/.config/sentry/config.json")).expanduser()
        try:
            configuration = json.loads(source.read_text(encoding="utf-8"))
            voice = configuration.get("voice", {}) if isinstance(configuration, dict) else {}
            playback_url = voice.get("projection_playback_url") if isinstance(voice, dict) else None
            if not base_url and isinstance(playback_url, str):
                parsed = urllib.parse.urlsplit(playback_url)
                if parsed.scheme == "http" and parsed.netloc:
                    base_url = f"{parsed.scheme}://{parsed.netloc}"
            if not token_path and isinstance(voice, dict) and isinstance(voice.get("projection_token_file"), str):
                token_path = voice["projection_token_file"]
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            pass
    base_url = (base_url or "http://127.0.0.1:48221").rstrip("/")
    token_file = Path(token_path or "~/.config/sentry/projection.token").expanduser()
    token = read_private_token(token_file)
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Authorization": authorization_header(token)}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(f"{base_url}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=3) as response:
        value = json.loads(response.read(8192).decode("utf-8"))
    if not isinstance(value, dict):
        raise TypeError("projection response must be an object")
    return value


def read_voice_status(path: Path | None = None) -> dict[str, Any]:
    from perception.voice_status import read_runtime_voice

    return read_runtime_voice(path or voice_status_path())


def sensor_status_message(payload: dict[str, Any]) -> str:
    if payload.get("status") != "CURRENT":
        return "Household signals are temporarily unavailable."
    return "No signals are registered."


def read_sensor_status() -> dict[str, Any]:
    """Read the authenticated, sanitized household signal snapshot from ANIMA."""

    try:
        configuration = AnimaConfig.load()
        if configuration is None:
            return {"status": "UNAVAILABLE", "items": [], "reason": "ANIMA is not connected."}
        payload = configuration.client().call("/v1/sentry/sensor-status", {})
        if not isinstance(payload, dict):
            raise TypeError("ANIMA sensor status must be an object")
        return payload
    except Exception:
        # The display must remain useful when the household service is down;
        # do not surface transport, credential, or database details here.
        return {
            "status": "UNAVAILABLE",
            "items": [],
            "reason": "Household signals are temporarily unavailable.",
        }


def sensor_indicator_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Keep only the small display contract returned by the ANIMA boundary."""

    if payload.get("status") != "CURRENT":
        return []

    items = payload.get("items")
    if not isinstance(items, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "Signal")[:96]
        kind = str(item.get("kind") or "event")[:32]
        status = str(item.get("status") or "UNKNOWN").upper()[:32]
        trigger = str(item.get("trigger") or "event")[:96]
        last_event = item.get("last_event")
        last_event_at = item.get("last_event_at")
        rows.append(
            {
                "sensor_id": str(item.get("sensor_id") or "")[:128],
                "key": str(item.get("key") or item.get("sensor_id") or label)[:128],
                "label": label,
                "kind": kind,
                "status": status,
                "trigger": trigger,
                "active": bool(item.get("active")),
                "last_event": str(last_event)[:96] if last_event is not None else None,
                "last_event_at": str(last_event_at)[:64] if last_event_at is not None else None,
            }
        )
    return rows


SENSOR_ICON_SPECS: dict[str, tuple[str | None, str | None]] = {
    "ring": (None, "🔔"),
    "tapo": ("system-lock-screen-symbolic", None),
    "wansview_backyard": ("camera-photo-symbolic", "2"),
    "wansview_garage": ("camera-photo-symbolic", "1"),
    "senseguard_basement": ("window-new-symbolic", None),
    "senseguard_kitchen": (None, "🚪"),
    "presence": ("avatar-default-symbolic", None),
}


def sensor_icon_spec(row: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return the semantic icon and optional badge for one display row."""

    key = str(row.get("key") or "")
    if key.startswith("person:"):
        return SENSOR_ICON_SPECS["presence"]
    return SENSOR_ICON_SPECS.get(key, ("sensors-symbolic", None))


SENSOR_ICON_FALLBACKS = {
    "ring": "🔔",
    "tapo": "🔒",
    "wansview_backyard": "📷",
    "wansview_garage": "📷",
    "senseguard_basement": "🪟",
    "senseguard_kitchen": "🚪",
    "presence": "●",
}


def sensor_icon_fallback(row: dict[str, Any]) -> str:
    """Return a visible glyph if a desktop icon theme lacks a symbol."""

    key = str(row.get("key") or "")
    if key.startswith("person:"):
        return SENSOR_ICON_FALLBACKS["presence"]
    return SENSOR_ICON_FALLBACKS.get(key, "•")


def local_signal_timestamp(value: Any) -> str | None:
    """Format a sanitized ISO timestamp in the operator's local timezone."""

    if value is None:
        return None
    try:
        timestamp = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if timestamp.tzinfo is None:
        return None
    return timestamp.astimezone().strftime("%m/%d %-I:%M %p")


def order_sensor_rows(
    rows: list[dict[str, Any]], saved_order: list[str] | tuple[str, ...] = ()
) -> list[dict[str, Any]]:
    """Order cards deterministically, then apply the owner's saved arrangement."""

    by_key = {str(row.get("key") or ""): row for row in rows}
    devices = [row for row in rows if row.get("kind") != "presence"]
    people = [row for row in rows if row.get("kind") == "presence"]
    people.sort(
        key=lambda row: (
            str(row.get("label") or "").casefold() != "tym",
            str(row.get("label") or "").casefold(),
        )
    )
    default_rows = devices + people
    default_keys = [str(row.get("key") or "") for row in default_rows]
    ordered_keys: list[str] = []
    for key in saved_order:
        normalized = str(key)
        if normalized in by_key and normalized not in ordered_keys:
            ordered_keys.append(normalized)
    ordered_keys.extend(key for key in default_keys if key not in ordered_keys)
    return [by_key[key] for key in ordered_keys if key in by_key]


def resolve_sleep_transition_status(
    runtime_payload: dict[str, Any],
    *,
    sleep_enabled: bool,
    transition_state: str | None,
) -> tuple[dict[str, Any], str | None]:
    """Prevent a stale sleeping record from masking listener startup."""

    runtime_state = str(runtime_payload.get("state") or "UNAVAILABLE").upper()
    if runtime_state == "UNAVAILABLE":
        return runtime_payload, None
    listener_ready = (
        runtime_state == "LISTENING"
        and runtime_payload.get("sleep_enabled") is False
        and runtime_payload.get("wake_enabled") is True
    )
    if transition_state == "STARTING" and listener_ready:
        return runtime_payload, None
    if transition_state == "STARTING" or (not sleep_enabled and runtime_state == "SLEEPING"):
        return {
            "state": "STARTING",
            "sleep_enabled": False,
            "wake_enabled": False,
            "speaker_context_active": False,
        }, "STARTING"
    if transition_state == "SLEEPING" or sleep_enabled:
        return {
            "state": "SLEEPING",
            "sleep_enabled": True,
            "wake_enabled": False,
            "speaker_context_active": False,
        }, transition_state
    return runtime_payload, None


def voice_status_summary(payload: dict[str, Any]) -> tuple[str, str, str]:
    state = str(payload.get("state") or payload.get("status") or "UNAVAILABLE").upper()
    guidance = VOICE_GUIDANCE.get(state, str(payload.get("reason") or "Voice status is unavailable."))
    if state == "UNAVAILABLE" and isinstance(payload.get("desired_sleep_enabled"), bool):
        intent = "Sleep requested" if payload["desired_sleep_enabled"] else "Awake requested"
        guidance = f"{intent} · {guidance}"
    if state == "SLEEPING":
        identity = "Speaker context is inactive while sleeping"
    elif payload.get("speaker_context_preflight_active"):
        identity = "Checking who is speaking…"
    elif payload.get("speaker_context_active") and payload.get("speaker_context_state") == "recognized":
        identity = f"Current speaker: {payload.get('speaker_context_display_name') or 'enrolled user'}"
    elif payload.get("speaker_context_active"):
        identity = "Speaker: operator — identity was not resolved"
    else:
        identity = "Speaker context will be checked on the next eligible wake"
    return state, guidance, identity


def build_application(config_path: Path, *, projection_mode: bool = False):
    distro_packages = Path("/usr/lib/python3/dist-packages")
    if distro_packages.is_dir() and str(distro_packages) not in sys.path:
        # GTK is supplied by Ubuntu while OpenCV/Vosk remain in SENTRY's venv.
        sys.path.append(str(distro_packages))
    try:
        import gi

        gi.require_version("Gtk", "4.0")
        gi.require_version("Gdk", "4.0")
        gi.require_version("GdkPixbuf", "2.0")
        import cairo
        from gi.repository import Gdk, GdkPixbuf, Gio, GLib, GObject, Gtk
        from OpenGL import GL
        from OpenGL.GL import shaders
    except (ImportError, ValueError) as exc:  # pragma: no cover - host dependency
        raise RuntimeError(f"GTK 4 is required for the native SENTRY application: {exc}") from exc

    class StatusOrb(Gtk.GLArea):
        """GPU-rendered refractive shell, internal energy, and external field."""

        VERTEX_SHADER = """
            #version 330 core
            out vec2 v_uv;
            void main() {
                vec2 positions[3] = vec2[3](
                    vec2(-1.0, -1.0), vec2(3.0, -1.0), vec2(-1.0, 3.0)
                );
                vec2 position = positions[gl_VertexID];
                v_uv = position * 0.5 + 0.5;
                gl_Position = vec4(position, 0.0, 1.0);
            }
        """

        FRAGMENT_SHADER = """
            #version 330 core
            in vec2 v_uv;
            out vec4 frag_color;

            uniform vec2 u_resolution;
            uniform float u_time;
            uniform float u_audio;
            uniform float u_previous_audio;
            uniform float u_shell_scale;
            uniform float u_float_offset;
            uniform float u_wake_progress;
            uniform float u_transition;
            uniform float u_reduced_motion;
            uniform float u_life_breath;
            uniform int u_state;
            uniform int u_previous_state;
            uniform vec3 u_primary;
            uniform vec3 u_secondary;

            const float PI = 3.14159265359;

            float hash21(vec2 p) {
                vec3 p3 = fract(vec3(p.xyx) * 0.1031);
                p3 += dot(p3, p3.yzx + 33.33);
                return fract((p3.x + p3.y) * p3.z);
            }

            float hash31(vec3 p) {
                p = fract(p * 0.1031);
                p += dot(p, p.yzx + 33.33);
                return fract((p.x + p.y) * p.z);
            }

            float noise3(vec3 p) {
                vec3 i = floor(p);
                vec3 f = fract(p);
                vec3 u = f * f * (3.0 - 2.0 * f);
                return mix(
                    mix(
                        mix(hash31(i + vec3(0, 0, 0)), hash31(i + vec3(1, 0, 0)), u.x),
                        mix(hash31(i + vec3(0, 1, 0)), hash31(i + vec3(1, 1, 0)), u.x), u.y
                    ),
                    mix(
                        mix(hash31(i + vec3(0, 0, 1)), hash31(i + vec3(1, 0, 1)), u.x),
                        mix(hash31(i + vec3(0, 1, 1)), hash31(i + vec3(1, 1, 1)), u.x), u.y
                    ), u.z
                );
            }

            float fbm3(vec3 p) {
                float value = 0.0;
                float amplitude = 0.52;
                for (int i = 0; i < 4; i++) {
                    value += amplitude * noise3(p);
                    p = p * 2.03 + vec3(13.7, 7.1, 19.3);
                    amplitude *= 0.48;
                }
                return value;
            }

            mat2 rotate2(float angle) {
                float c = cos(angle);
                float s = sin(angle);
                return mat2(c, -s, s, c);
            }

            float gaussian(float distance_value, float width) {
                float ratio = distance_value / max(width, 0.0001);
                return exp(-ratio * ratio);
            }

            float tube(vec2 offset, float width) {
                return gaussian(length(offset), width);
            }

            vec4 spirit_field(vec3 q, float time_value) {
                float radial = length(q);
                vec3 spirit_space = q * 1.64;
                float spirit_warp = fbm3(
                    spirit_space * 1.14
                    + vec3(time_value * 0.018, -time_value * 0.012, time_value * 0.010)
                );
                spirit_space += vec3(
                    sin(q.y * 2.0 + time_value * 0.052 + spirit_warp * 2.5),
                    cos(q.z * 1.7 - time_value * 0.041 + spirit_warp * 2.1),
                    sin(q.x * 2.2 + time_value * 0.034 - spirit_warp * 2.3)
                ) * 0.27;
                float spirit_noise = fbm3(
                    spirit_space
                    + vec3(-time_value * 0.020, time_value * 0.015, time_value * 0.011)
                );
                float spirit_ridges = 1.0 - abs(spirit_noise * 2.0 - 1.0);
                float free_spirit_vapor = smoothstep(0.34, 0.74, spirit_noise)
                    * (0.30 + spirit_ridges * 0.70)
                    * gaussian(radial, 0.78)
                    * smoothstep(0.045, 0.17, radial);
                float spirit_mist = gaussian(radial, 0.64)
                    * (0.12 + spirit_noise * 0.46);
                return vec4(spirit_noise, spirit_ridges, free_spirit_vapor, spirit_mist);
            }

            float halo_width_for_state(int state) {
                if (state == 2) {
                    return 0.30;
                }
                if (state == 5) {
                    return 0.20;
                }
                return 0.14;
            }

            float halo_strength_for_state(int state, float audio) {
                if (state == 0) {
                    return 0.0;
                }
                if (state == 1) {
                    return 0.020;
                }
                return 0.045 + audio * 0.075;
            }

            float state_deformation(int state, float angle, float audio, float time_value) {
                float motion = mix(1.0, 0.24, u_reduced_motion);
                if (state == 3 || state == 6) {
                    float surface = sin(angle * 7.0 + time_value * 0.052);
                    surface += sin(angle * 11.0 - time_value * 0.026) * 0.18;
                    return surface * (0.0012 + audio * 0.0038) * motion;
                }
                if (state == 5) {
                    return 0.0;
                }
                if (state == 1) {
                    return sin(angle * 2.0 + time_value * 0.35) * 0.0035 * motion;
                }
                return 0.0;
            }

            vec4 energy_for_state(int state, vec3 q, float time_value, float audio) {
                float motion = mix(1.0, 0.24, u_reduced_motion);
                float t = time_value * motion;
                float radial = length(q);
                float mist = fbm3(q * 2.15 + vec3(t * 0.12, -t * 0.08, t * 0.05));
                vec3 cyan = vec3(0.05, 0.86, 1.0);
                vec3 violet = vec3(0.74, 0.16, 1.0);
                vec3 white_hot = vec3(0.94, 0.98, 1.0);
                vec3 color = mix(u_primary, u_secondary, clamp(q.x * 0.46 + mist * 0.30 + 0.34, 0.0, 1.0));
                float density = 0.0;
                float brilliance = 0.0;

                // One persistent spirit field exists in every active state. Its
                // state-specific containment changes, but its underlying flow
                // coordinates remain continuous through visual crossfades.
                vec4 spirit = spirit_field(q, t);
                float spirit_noise = spirit.x;
                float spirit_ridges = spirit.y;
                float free_spirit_vapor = spirit.z;
                float spirit_mist = spirit.w;

                if (state == 0) {
                    return vec4(vec3(0.03, 0.025, 0.06), 0.015);
                }

                if (state == 1) {
                    float phase_a = q.x * 2.55 + t * 0.26;
                    float phase_b = q.x * 2.22 - t * 0.20 + 2.3;
                    vec2 center_a = vec2(sin(phase_a) * 0.105, cos(phase_a * 0.78) * 0.11);
                    vec2 center_b = vec2(sin(phase_b) * 0.09, cos(phase_b * 0.92) * 0.13);
                    float ribbon_a = tube(q.yz - center_a, 0.075);
                    float ribbon_b = tube(q.yz - center_b, 0.064);
                    float envelope = exp(-q.x * q.x * 0.78);
                    density = (ribbon_a * 0.62 + ribbon_b * 0.45) * envelope;
                    density += free_spirit_vapor * 0.40;
                    density += spirit_mist * 0.10;
                    brilliance = density * (0.34 + mist * 0.26);
                    brilliance += free_spirit_vapor * (0.11 + spirit_ridges * 0.065);
                    color = mix(violet, cyan, smoothstep(-0.7, 0.7, q.x + q.z * 0.25));
                } else if (state == 2) {
                    float core = gaussian(radial, 0.24);
                    float ignition = tube(q.yz - vec2(sin(q.x * 3.2 + t * 1.8) * 0.06, 0.0), 0.105);
                    float gathering_vapor = free_spirit_vapor * gaussian(radial, 0.46);
                    float forming_wave = free_spirit_vapor
                        * gaussian(q.y - sin(q.x * 2.0 + q.z * 1.3) * 0.10, 0.16);
                    density = core * 1.8 + ignition * exp(-q.x * q.x * 0.7);
                    density += gathering_vapor * 0.34 + forming_wave * 0.22;
                    brilliance = density * 1.75;
                    color = mix(white_hot, cyan, smoothstep(0.08, 0.72, radial));
                } else if (state == 3 || state == 6) {
                    float focus = state == 6 ? 0.78 : 1.0;
                    float drive = (0.22 + audio * 0.52) * focus;
                    float speed = 0.022;
                    float slow_mist = fbm3(
                        q * 2.15 + vec3(t * 0.012, -t * 0.008, t * 0.005)
                    );
                    float broad_wave = sin(q.x * 2.05 - t * speed + q.z * 1.34);
                    float fine_wave = sin(q.x * 3.45 + q.z * 2.56 + t * speed * 0.08);
                    float counter_wave = cos(q.x * 1.24 - q.z * 2.12 - t * speed * 0.04);
                    float wave_height = 0.15 * focus;
                    float membrane_height = broad_wave * wave_height;
                    membrane_height += fine_wave * 0.028;
                    membrane_height += counter_wave * 0.025;

                    float membrane_distance = q.y - membrane_height;
                    float membrane = gaussian(membrane_distance, 0.072 + audio * 0.022);
                    float crest = gaussian(membrane_distance, 0.026 + audio * 0.009);
                    float envelope = exp(-q.x * q.x * 0.34 - q.z * q.z * 0.18);
                    float folds = 0.52 + 0.48 * sin(
                        q.z * 4.2 - q.x * 1.8 + t * 0.028 + slow_mist * 1.35
                    );

                    float trailing_height = membrane_height * 0.48 - 0.11
                        + sin(q.z * 2.0 + t * 0.014) * 0.030;
                    float trailing_veil = gaussian(q.y - trailing_height, 0.145) * envelope;
                    float side_reception = gaussian(abs(q.x) - 0.72, 0.19)
                        * gaussian(membrane_distance, 0.18)
                        * smoothstep(0.92, 0.05, abs(q.z));

                    density = membrane * envelope * (0.52 + folds * 0.48);
                    density += trailing_veil * (0.10 + drive * 0.12);
                    density += side_reception * drive * 0.18;
                    density *= 0.72;
                    float captured_vapor = free_spirit_vapor
                        * gaussian(membrane_distance, 0.16)
                        * envelope;
                    density += captured_vapor * (0.20 + drive * 0.18);
                    brilliance = density * (0.48 + drive * 0.28)
                        + crest * envelope * (0.10 + audio * 0.19)
                        + captured_vapor * (0.06 + audio * 0.10);
                    color = mix(cyan, violet, clamp(0.12 + q.z * 0.31 + folds * 0.50, 0.0, 1.0));
                    color = mix(color, u_primary, 0.10 + audio * 0.05);
                } else if (state == 4) {
                    vec3 a = q;
                    a.xz = rotate2(t * 0.22) * a.xz;
                    a.xy = rotate2(-0.44 + sin(t * 0.19) * 0.18) * a.xy;
                    float angle_a = atan(a.z, a.x);
                    float radius_a = length(a.xz);
                    float flow_a = 0.38 + sin(angle_a * 2.0 - t * 1.25 + mist * 2.2) * 0.12;
                    float vortex_a = tube(vec2(radius_a - flow_a, a.y - sin(angle_a * 1.55 + t * 0.68) * 0.16), 0.105);

                    vec3 b = q.yzx;
                    b.xz = rotate2(-t * 0.17 + 1.1) * b.xz;
                    float angle_b = atan(b.z, b.x);
                    float radius_b = length(b.xz);
                    float flow_b = 0.30 + cos(angle_b * 2.35 + t * 0.92 - mist) * 0.10;
                    float vortex_b = tube(vec2(radius_b - flow_b, b.y - cos(angle_b * 1.7 - t * 0.52) * 0.13), 0.088);
                    float plasma = gaussian(radial, 0.33) * (0.44 + mist * 0.82);
                    density = vortex_a * 0.86 + vortex_b * 0.64 + plasma * 0.74;
                    density += free_spirit_vapor * gaussian(radial, 0.50) * 0.035;
                    brilliance = density * (0.82 + mist * 0.56);
                    color = mix(violet, cyan, clamp(0.12 + mist * 0.68 + q.z * 0.18, 0.0, 1.0));
                } else if (state == 5) {
                    float drive = 0.20 + audio * 0.86;
                    vec3 knot = q;
                    knot.xy = rotate2(t * 0.10) * knot.xy;
                    knot.yz = rotate2(-t * 0.07 + 0.42) * knot.yz;
                    float slow_flow = fbm3(knot * 3.0 + vec3(t * 0.030, -t * 0.018, t * 0.022));
                    float fine_flow = fbm3(knot * 5.6 + vec3(-t * 0.022, t * 0.030, t * 0.014));

                    float core_radius = radial + (fine_flow - 0.50) * 0.090;
                    float plasma_core = gaussian(core_radius, 0.180) * (0.40 + audio * 0.78);
                    float corona_radius = 0.235 + (slow_flow - 0.50) * 0.075;
                    float corona = gaussian(radial - corona_radius, 0.082)
                        * (0.26 + fine_flow * 0.74) * (0.38 + audio * 0.70);

                    vec2 filament_center_a = vec2(
                        sin(knot.z * 5.2 + t * 0.17) * 0.070,
                        cos(knot.z * 3.8 - t * 0.12) * 0.062
                    );
                    vec2 filament_center_b = vec2(
                        cos(knot.x * 4.6 - t * 0.14) * 0.064,
                        sin(knot.x * 5.4 + t * 0.10) * 0.070
                    );
                    float filament_a = tube(knot.xy - filament_center_a, 0.052)
                        * gaussian(radial, 0.38);
                    float filament_b = tube(knot.yz - filament_center_b, 0.047)
                        * gaussian(radial, 0.35);
                    float azimuth_a = atan(knot.y, knot.x);
                    float spiral_a = tube(
                        vec2(
                            length(knot.xy) - (0.19 + sin(azimuth_a * 3.0 + t * 0.11) * 0.034),
                            knot.z - sin(azimuth_a * 2.0 - t * 0.09) * 0.070
                        ),
                        0.052
                    );
                    float azimuth_b = atan(knot.z, knot.y);
                    float spiral_b = tube(
                        vec2(
                            length(knot.yz) - (0.16 + cos(azimuth_b * 3.0 - t * 0.09) * 0.030),
                            knot.x - cos(azimuth_b * 2.0 + t * 0.08) * 0.060
                        ),
                        0.046
                    );

                    vec3 current_a_space = knot;
                    current_a_space.yz = rotate2(0.58) * current_a_space.yz;
                    vec2 current_a_path = vec2(
                        sin(current_a_space.x * 3.0 + t * 0.21) * 0.19,
                        cos(current_a_space.x * 2.4 - t * 0.16) * 0.17
                    );
                    float current_a = tube(current_a_space.yz - current_a_path, 0.072)
                        * smoothstep(0.13, 0.25, radial)
                        * (1.0 - smoothstep(0.50, 0.80, radial));

                    vec3 current_b_space = knot.zxy;
                    current_b_space.yz = rotate2(-0.74) * current_b_space.yz;
                    vec2 current_b_path = vec2(
                        cos(current_b_space.x * 2.7 - t * 0.18) * 0.17,
                        sin(current_b_space.x * 3.3 + t * 0.13) * 0.16
                    );
                    float current_b = tube(current_b_space.yz - current_b_path, 0.064)
                        * smoothstep(0.12, 0.24, radial)
                        * (1.0 - smoothstep(0.46, 0.76, radial));

                    vec3 current_c_space = knot.yzx;
                    current_c_space.yz = rotate2(1.04) * current_c_space.yz;
                    vec2 current_c_path = vec2(
                        sin(current_c_space.x * 2.5 - t * 0.15) * 0.15,
                        cos(current_c_space.x * 3.1 + t * 0.12) * 0.18
                    );
                    float current_c = tube(current_c_space.yz - current_c_path, 0.058)
                        * smoothstep(0.16, 0.27, radial)
                        * (1.0 - smoothstep(0.44, 0.72, radial));

                    float inner_breath = 0.88 + sin(t * 0.76 + slow_flow * 1.8) * 0.12;
                    float outward_front = gaussian(
                        radial - (0.47 + sin(azimuth_a * 2.0 - t * 0.15) * 0.045),
                        0.085
                    ) * (0.22 + slow_flow * 0.44) * (0.24 + audio * 0.46);

                    float spirit_vapor = free_spirit_vapor * gaussian(radial, 0.70);
                    float inner_mist = gaussian(radial, 0.54)
                        * (0.16 + spirit_noise * 0.42)
                        * (0.68 + inner_breath * 0.32);
                    float vocal_aurora = gaussian(radial - 0.39, 0.24)
                        * (0.18 + slow_flow * 0.50 + fine_flow * 0.18)
                        * (0.28 + audio * 0.46);
                    float luminous_cloud = gaussian(radial, 0.43)
                        * (0.12 + slow_flow * 0.50 + fine_flow * 0.12);
                    float outer_haze = gaussian(radial - 0.48 + (slow_flow - 0.5) * 0.09, 0.25)
                        * (0.13 + fine_flow * 0.30);

                    density = plasma_core * (0.38 + drive * 0.24) * inner_breath;
                    density += corona * (0.28 + drive * 0.24);
                    density += (filament_a + filament_b) * (0.12 + audio * 0.22);
                    density += (spiral_a + spiral_b) * (0.15 + audio * 0.27);
                    density += (current_a + current_b + current_c) * (0.13 + audio * 0.27);
                    density += outward_front * (0.13 + audio * 0.24);
                    density += vocal_aurora * (0.11 + audio * 0.16);
                    density += spirit_vapor * (0.13 + audio * 0.12);
                    density += inner_mist * (0.08 + audio * 0.08);
                    density += luminous_cloud * (0.18 + drive * 0.25);
                    density += outer_haze * drive * 0.10;
                    brilliance = density * (0.44 + drive * 0.30);
                    brilliance += plasma_core * (0.20 + audio * 0.34);
                    brilliance += corona * (0.10 + audio * 0.20);
                    brilliance += (spiral_a + spiral_b) * (0.10 + audio * 0.16);
                    brilliance += (current_a + current_b + current_c) * (0.07 + audio * 0.15);
                    color = mix(
                        violet,
                        cyan,
                        clamp(
                            0.02 + radial * 0.60 + slow_flow * 0.22
                            + current_a * 0.16 + spirit_noise * 0.10,
                            0.0,
                            1.0
                        )
                    );
                    color = mix(
                        color,
                        white_hot,
                        clamp(plasma_core * (0.10 + audio * 0.16) + corona * 0.050, 0.0, 0.24)
                    );
                }

                float listening = (state == 3 || state == 6) ? 1.0 : 0.0;
                float white_mix = mix(
                    clamp(brilliance * 0.20, 0.0, 0.42),
                    clamp(brilliance * 0.075, 0.0, 0.14),
                    listening
                );
                if (state == 5) {
                    white_mix = clamp(brilliance * 0.070, 0.0, 0.12);
                } else if (state == 4) {
                    white_mix = clamp(brilliance * 0.060, 0.0, 0.11);
                }
                float emission_gain = mix(
                    0.34 + brilliance * 1.34,
                    0.26 + brilliance * 0.78,
                    listening
                );
                emission_gain *= 0.95 + u_life_breath * 0.05;
                if (state == 4) {
                    emission_gain *= 0.64;
                }
                color = mix(color, white_hot, white_mix);
                return vec4(color * emission_gain, clamp(density, 0.0, 2.4));
            }

            vec4 reformation_vapor_energy(
                vec3 q,
                float time_value,
                float progress,
                vec4 source_energy,
                vec4 target_energy
            ) {
                // The transition is one continuous volume. The source loosens
                // into a slow domain-warped mist while the destination field
                // progressively attracts that same material. There are no
                // screen-space cells or thresholded particles to reveal the
                // renderer's sampling structure.
                float arc = sin(progress * PI);
                float release = smoothstep(0.02, 0.56, progress);
                float attraction = smoothstep(0.34, 0.98, progress);
                float source_presence = 1.0 - smoothstep(0.08, 0.74, progress);
                float target_presence = smoothstep(0.26, 0.96, progress);

                vec3 flow_space = q;
                flow_space.xy = rotate2(
                    (progress - 0.5) * 0.34 + time_value * 0.014
                ) * flow_space.xy;
                flow_space.yz = rotate2(
                    -arc * 0.20 - time_value * 0.010
                ) * flow_space.yz;

                float broad_warp = fbm3(
                    flow_space * 1.34
                    + vec3(
                        time_value * 0.018,
                        -time_value * 0.013,
                        time_value * 0.009
                    )
                );
                float folded_warp = fbm3(
                    flow_space * 2.08
                    + vec3(
                        11.7 - time_value * 0.011,
                        5.3 + time_value * 0.015,
                        19.1 - time_value * 0.008
                    )
                );
                vec3 flow_offset = vec3(
                    sin(flow_space.y * 1.82 + broad_warp * 3.0 + time_value * 0.035),
                    cos(flow_space.z * 1.66 - folded_warp * 2.7 - time_value * 0.028),
                    sin(flow_space.x * 1.74 + (broad_warp - folded_warp) * 2.4
                        + time_value * 0.024)
                );
                flow_space += flow_offset * arc * 0.135;

                vec4 spirit = spirit_field(flow_space, time_value);
                float source_guide = smoothstep(0.015, 0.64, source_energy.a);
                float target_guide = smoothstep(0.015, 0.64, target_energy.a);
                float guide = mix(source_guide, target_guide, attraction);
                float radial_envelope = gaussian(length(flow_space), 0.82);
                float vapor_body = (
                    spirit.z * 0.72
                    + spirit.w * 0.22
                    + broad_warp * folded_warp * 0.085
                ) * radial_envelope;
                vapor_body *= 0.42 + guide * 0.58;

                float source_density = source_energy.a
                    * source_presence
                    * (1.0 - release * 0.40);
                float target_density = target_energy.a
                    * target_presence
                    * (0.62 + attraction * 0.38);
                float vapor_density = vapor_body
                    * pow(max(arc, 0.0), 0.72)
                    * (0.84 + u_life_breath * 0.16);
                float density = source_density + target_density + vapor_density;

                vec3 material_color = mix(
                    source_energy.rgb,
                    target_energy.rgb,
                    smoothstep(0.18, 0.86, progress)
                );
                vec3 vapor_color = mix(
                    vec3(0.72, 0.16, 1.0),
                    vec3(0.04, 0.84, 1.0),
                    clamp(0.15 + flow_space.x * 0.26 + spirit.x * 0.54, 0.0, 1.0)
                );
                float material_weight = clamp(
                    (source_density + target_density) / max(density, 0.001),
                    0.0,
                    1.0
                );
                vec3 color = mix(vapor_color, material_color, material_weight * 0.78);
                color = mix(color, vec3(0.84, 0.93, 1.0), guide * arc * 0.055);
                return vec4(
                    color * (0.38 + density * 0.98),
                    clamp(density, 0.0, 1.65)
                );
            }

            vec3 studio_environment(vec3 direction) {
                float overhead = pow(max(direction.y, 0.0), 18.0) * smoothstep(-0.75, 0.30, direction.x);
                float left_strip = gaussian(direction.x + 0.58, 0.15) * smoothstep(-0.45, 0.72, direction.y);
                float right_strip = gaussian(direction.x - 0.72, 0.17) * smoothstep(-0.30, 0.82, direction.y);
                float horizon = gaussian(direction.y + 0.18, 0.17) * 0.10;
                vec3 environment = vec3(0.008, 0.010, 0.022);
                environment += vec3(0.68, 0.78, 1.0) * overhead * 0.44;
                environment += vec3(0.22, 0.72, 1.0) * left_strip * 0.13;
                environment += vec3(0.84, 0.30, 1.0) * right_strip * 0.11;
                environment += vec3(0.13, 0.16, 0.28) * horizon;
                return environment;
            }

            vec3 filmic_tonemap(vec3 color) {
                color *= 1.34;
                return clamp(
                    (color * (2.51 * color + 0.03)) /
                    (color * (2.43 * color + 0.59) + 0.14),
                    0.0, 1.0
                );
            }

            void main() {
                vec2 p = v_uv * 2.0 - 1.0;
                p.x *= u_resolution.x / max(1.0, u_resolution.y);
                p.y -= u_float_offset;
                float angle = atan(p.y, p.x);
                float transition = smoothstep(0.0, 1.0, u_transition);
                float deformation = mix(
                    state_deformation(u_previous_state, angle, u_previous_audio, u_time),
                    state_deformation(u_state, angle, u_audio, u_time), transition
                );
                if (u_state == 5) {
                    deformation = 0.0;
                }
                float sphere_radius = 0.735 * u_shell_scale * (1.0 + deformation);
                float distance_to_center = length(p);
                float normalized_radius = distance_to_center / sphere_radius;

                vec3 background = vec3(0.0015, 0.0018, 0.0045);
                float stage_light = exp(-dot(p, p) * 0.52);
                background += mix(vec3(0.010, 0.008, 0.022), u_primary * 0.032, 0.42) * stage_light;
                float floor_shadow = exp(-pow(p.x / 0.66, 2.0) - pow((p.y + 0.84) / 0.070, 2.0));
                background *= 1.0 - floor_shadow * 0.56;

                float mixed_audio = mix(u_previous_audio, u_audio, transition);
                float halo_width = mix(
                    halo_width_for_state(u_previous_state),
                    halo_width_for_state(u_state),
                    transition
                );
                float halo = gaussian(distance_to_center - sphere_radius * 1.01, halo_width);
                float halo_strength = mix(
                    halo_strength_for_state(u_previous_state, u_previous_audio),
                    halo_strength_for_state(u_state, u_audio),
                    transition
                );
                halo_strength *= 0.96 + u_life_breath * 0.04;
                vec3 final_color = background + mix(u_primary, u_secondary, 0.34) * halo * halo_strength;

                if (u_wake_progress >= 0.0 && u_wake_progress <= 1.0) {
                    float ring_radius = sphere_radius * mix(0.88, 1.62, u_wake_progress);
                    float ignition = gaussian(distance_to_center - ring_radius, 0.012 + u_wake_progress * 0.022);
                    final_color += mix(vec3(1.0), vec3(0.12, 0.88, 1.0), u_wake_progress) * ignition * (1.0 - u_wake_progress);
                }

                float previous_speaking = u_previous_state == 5 ? 1.0 : 0.0;
                float current_speaking = u_state == 5 ? 1.0 : 0.0;
                float speaking_blend = mix(previous_speaking, current_speaking, transition);
                bool material_reformation = (
                    ((u_previous_state == 3 || u_previous_state == 6) && u_state == 4)
                    || (u_previous_state == 4 && u_state == 5)
                );
                if (speaking_blend > 0.001 && distance_to_center > sphere_radius) {
                    float near_field = gaussian(distance_to_center - sphere_radius * 1.025, 0.115);
                    float far_field = gaussian(distance_to_center - sphere_radius * 1.09, 0.245);
                    float light_response = 0.10 + mixed_audio * 0.34;
                    final_color += mix(u_primary, u_secondary, 0.28)
                        * (near_field * 0.11 + far_field * 0.035)
                        * light_response * speaking_blend;
                }

                if (normalized_radius <= 1.012) {
                    float front_z = sqrt(max(0.0, sphere_radius * sphere_radius - dot(p, p)));
                    float path_length = (front_z * 2.0) / sphere_radius;
                    float jitter = hash21(gl_FragCoord.xy + floor(u_time * 12.0)) - 0.5;
                    vec3 volume_color = vec3(0.0);
                    float transmittance = 1.0;
                    const int STEPS = 36;
                    for (int i = 0; i < STEPS; i++) {
                        float sample_position = (float(i) + 0.5 + jitter * 0.12) / float(STEPS);
                        float sample_z = mix(front_z, -front_z, sample_position);
                        vec3 q = vec3(p, sample_z) / sphere_radius;
                        vec4 current_energy = energy_for_state(u_state, q, u_time, u_audio);
                        vec4 energy = current_energy;
                        if (transition < 0.999) {
                            vec4 previous_energy = energy_for_state(
                                u_previous_state, q, u_time, u_previous_audio
                            );
                            if (material_reformation) {
                                float expansion_arc = sin(transition * PI);
                                vec3 released_q = q;
                                released_q.xy = rotate2(expansion_arc * 0.18) * released_q.xy;
                                released_q.yz = rotate2(-expansion_arc * 0.12) * released_q.yz;
                                released_q /= 1.0 + expansion_arc * 0.18;
                                float release_warp = fbm3(
                                    q * 1.72
                                    + vec3(
                                        u_time * 0.014,
                                        -u_time * 0.010,
                                        u_time * 0.008
                                    )
                                );
                                released_q += normalize(q + vec3(0.001))
                                    * expansion_arc
                                    * (release_warp - 0.5)
                                    * 0.052;

                                vec4 released_source = energy_for_state(
                                    u_previous_state, released_q, u_time, u_previous_audio
                                );
                                vec4 forming_target = energy_for_state(
                                    u_state, released_q, u_time, u_audio
                                );
                                energy = reformation_vapor_energy(
                                    released_q,
                                    u_time,
                                    transition,
                                    released_source,
                                    forming_target
                                );
                            } else {
                                energy = mix(previous_energy, current_energy, transition);
                            }
                        }
                        float sample_alpha = 1.0 - exp(-energy.a * path_length * 0.105);
                        volume_color += transmittance * energy.rgb * sample_alpha * 1.14;
                        transmittance *= 1.0 - sample_alpha * 0.68;
                    }

                    vec2 sphere_p = p / sphere_radius;
                    float sphere_z = front_z / sphere_radius;
                    vec3 normal = normalize(vec3(sphere_p, sphere_z));
                    vec3 view_ray = normalize(vec3(sphere_p * 0.11, -1.0));
                    vec3 reflection = reflect(view_ray, normal);
                    float fresnel = pow(1.0 - max(0.0, dot(normal, vec3(0.0, 0.0, 1.0))), 4.2);
                    float glass_depth = smoothstep(0.0, 1.0, path_length);
                    vec3 absorption = exp(-vec3(0.22, 0.12, 0.08) * path_length);
                    vec3 interior = volume_color * absorption;
                    interior += mix(vec3(0.002, 0.004, 0.012), u_primary * 0.020, glass_depth);

                    vec3 environment = studio_environment(reflection);
                    float micro_surface = noise3(normal * 7.0 + vec3(u_time * 0.025));
                    interior += environment * (0.40 + fresnel * 0.96);
                    interior += mix(vec3(0.03, 0.20, 0.34), vec3(0.42, 0.12, 0.62), sphere_p.x * 0.5 + 0.5)
                        * fresnel * (0.22 + micro_surface * 0.09);

                    float key_highlight = pow(max(0.0, dot(normal, normalize(vec3(0.44, 0.57, 0.82)))), 96.0);
                    float soft_highlight = pow(max(0.0, dot(normal, normalize(vec3(-0.42, 0.68, 0.62)))), 22.0);
                    float rim = smoothstep(0.80, 1.0, normalized_radius);
                    float edge = smoothstep(0.935, 1.0, normalized_radius);
                    interior += vec3(1.0, 0.985, 1.0) * key_highlight * 1.12;
                    interior += vec3(0.48, 0.68, 1.0) * soft_highlight * 0.24;
                    interior += mix(u_secondary, vec3(0.75, 0.90, 1.0), 0.66) * rim * 0.12;
                    interior += mix(vec3(0.36, 0.76, 1.0), vec3(0.86, 0.36, 1.0), sphere_p.x * 0.5 + 0.5) * edge * 0.42;

                    float edge_width = max(fwidth(normalized_radius) * 1.35, 0.0025);
                    float coverage = 1.0 - smoothstep(1.0 - edge_width, 1.0 + edge_width, normalized_radius);
                    final_color = mix(final_color, interior, coverage * 0.972);

                }

                final_color = filmic_tonemap(max(final_color, vec3(0.0)));
                final_color = pow(final_color, vec3(0.92));
                float vignette = 1.0 - smoothstep(0.58, 1.38, length(p)) * 0.16;
                final_color *= vignette;
                frag_color = vec4(final_color, 1.0);
            }
        """

        def __init__(
            self,
            *,
            on_context_failure: Callable[[], None] | None = None,
            projection_mode: bool = False,
        ):
            super().__init__()
            orb_size = orb_canvas_size(projection_mode=projection_mode)
            self.set_size_request(orb_size, orb_size)
            self.set_required_version(3, 3)
            if hasattr(self, "set_allowed_apis"):
                self.set_allowed_apis(Gdk.GLAPI.GL)
            self.set_auto_render(False)
            self.controller = OrbStateController()
            self._program: int | None = None
            self._vertex_array: int | None = None
            self._gl = None
            self._on_context_failure = on_context_failure
            self._context_failed = False
            settings = Gtk.Settings.get_default()
            self.reduced_motion = bool(settings and not settings.get_property("gtk-enable-animations"))
            self.connect("realize", self._realize)
            self.connect("unrealize", self._unrealize)
            self.connect("render", self._render)
            GLib.timeout_add(16, self._animate)

        def present(self, payload: dict[str, Any], *, acknowledge_wake: bool = False) -> None:
            self.controller.update(payload)
            if acknowledge_wake:
                self.controller.acknowledge_wake()
            self.queue_render()

        def _animate(self) -> bool:
            self.queue_render()
            return True

        def _realize(self, _area) -> None:
            self.make_current()
            if self.get_error() is not None:
                self._context_failed = True
                if self._on_context_failure is not None:
                    GLib.idle_add(self._on_context_failure)
                return
            try:
                self._gl = GL
                self._program = shaders.compileProgram(
                    shaders.compileShader(self.VERTEX_SHADER, GL.GL_VERTEX_SHADER),
                    shaders.compileShader(self.FRAGMENT_SHADER, GL.GL_FRAGMENT_SHADER),
                )
                self._vertex_array = int(GL.glGenVertexArrays(1))
            except (RuntimeError, ValueError) as exc:
                # A Pi compositor/driver can expose a GLArea and still fail to
                # create the requested context. Keep the projection visible by
                # switching to the bounded Cairo orb instead of crashing or
                # leaving an empty white/black surface.
                print(f"SENTRY GL orb unavailable: {type(exc).__name__}: {exc}", file=sys.stderr)
                self._context_failed = True
                self._gl = None
                self._program = None
                self._vertex_array = None
                if self._on_context_failure is not None:
                    GLib.idle_add(self._on_context_failure)

        def _unrealize(self, _area) -> None:
            self.make_current()
            if self._gl is not None:
                if self._vertex_array is not None:
                    self._gl.glDeleteVertexArrays(1, [self._vertex_array])
                if self._program is not None:
                    self._gl.glDeleteProgram(self._program)
            self._vertex_array = None
            self._program = None
            self._gl = None

        def _uniform(self, name: str) -> int:
            assert self._gl is not None and self._program is not None
            return int(self._gl.glGetUniformLocation(self._program, name))

        def _render(self, _area, _context) -> bool:
            if self._gl is None or self._program is None or self._vertex_array is None:
                return False
            gl = self._gl
            width = max(1, self.get_width())
            height = max(1, self.get_height())
            scale = max(1, self.get_scale_factor())
            pixel_width = width * scale
            pixel_height = height * scale
            frame = self.controller.frame(reduced_motion=self.reduced_motion)
            red, green, blue = frame["color"]
            secondary_red, secondary_green, secondary_blue = frame["secondary"]
            wake = frame["wake_progress"]

            gl.glViewport(0, 0, pixel_width, pixel_height)
            gl.glDisable(gl.GL_DEPTH_TEST)
            gl.glUseProgram(self._program)
            gl.glBindVertexArray(self._vertex_array)
            gl.glUniform2f(self._uniform("u_resolution"), float(pixel_width), float(pixel_height))
            gl.glUniform1f(self._uniform("u_time"), float(frame["time"]))
            gl.glUniform1f(self._uniform("u_audio"), float(frame["audio_level"]))
            gl.glUniform1f(self._uniform("u_previous_audio"), float(frame["previous_audio_level"]))
            gl.glUniform1f(self._uniform("u_shell_scale"), float(frame["shell_scale"]))
            gl.glUniform1f(self._uniform("u_float_offset"), float(frame["float_offset"]) / max(1.0, height / 2.0))
            gl.glUniform1f(self._uniform("u_wake_progress"), -1.0 if wake is None else float(wake))
            gl.glUniform1f(self._uniform("u_transition"), float(frame["transition_progress"]))
            gl.glUniform1f(self._uniform("u_reduced_motion"), 1.0 if frame["reduced_motion"] else 0.0)
            gl.glUniform1f(self._uniform("u_life_breath"), float(frame["life_breath"]))
            gl.glUniform1i(self._uniform("u_state"), ORB_STATE_INDEX[str(frame["state"])] )
            gl.glUniform1i(self._uniform("u_previous_state"), ORB_STATE_INDEX[str(frame["previous_state"])] )
            gl.glUniform3f(self._uniform("u_primary"), float(red), float(green), float(blue))
            gl.glUniform3f(
                self._uniform("u_secondary"),
                float(secondary_red), float(secondary_green), float(secondary_blue),
            )
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
            gl.glBindVertexArray(0)
            gl.glUseProgram(0)
            return True

    class SignalIcon(Gtk.DrawingArea):
        """Small, theme-independent line icon for one household signal."""

        def __init__(self, row_key: str, *, active: bool):
            super().__init__()
            self.row_key = row_key
            self.active = active
            self.set_content_width(34)
            self.set_content_height(30)
            self.set_halign(Gtk.Align.CENTER)
            self.set_valign(Gtk.Align.CENTER)
            self.add_css_class("sensor-icon")
            self.set_draw_func(self._draw)

        def _draw(self, _area, context, _width: int, _height: int) -> None:
            color = (0.32, 0.90, 0.54) if self.active else (0.51, 0.46, 0.56)
            context.set_source_rgb(*color)
            context.set_line_width(2.0)
            context.set_line_cap(cairo.LineCap.ROUND)
            context.set_line_join(cairo.LineJoin.ROUND)
            key = self.row_key.removeprefix("person:")

            if key == "ring":
                context.move_to(7, 22)
                context.line_to(27, 22)
                context.move_to(10, 22)
                context.line_to(10, 16)
                context.curve_to(10, 10, 12, 7, 17, 7)
                context.curve_to(22, 7, 24, 10, 24, 16)
                context.line_to(24, 22)
                context.move_to(14, 25)
                context.curve_to(14, 28, 20, 28, 20, 25)
                context.stroke()
            elif key == "tapo":
                context.move_to(11, 14)
                context.line_to(11, 11)
                context.curve_to(11, 4, 23, 4, 23, 11)
                context.line_to(23, 14)
                context.stroke()
                context.rectangle(7, 13, 20, 14)
                context.stroke()
                context.arc(17, 20, 1.5, 0, math.tau)
                context.stroke()
            elif key.startswith("wansview_"):
                context.rectangle(4, 11, 23, 15)
                context.move_to(10, 11)
                context.line_to(12, 8)
                context.line_to(19, 8)
                context.line_to(21, 11)
                context.stroke()
                context.arc(15.5, 18.5, 4.5, 0, math.tau)
                context.stroke()
                if key in {"wansview_garage", "wansview_backyard"}:
                    context.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
                    context.set_font_size(9)
                    context.move_to(27, 9)
                    context.show_text("1" if key == "wansview_garage" else "2")
            elif key == "senseguard_basement":
                context.rectangle(6, 5, 20, 21)
                context.move_to(16, 5)
                context.line_to(16, 26)
                context.move_to(6, 15.5)
                context.line_to(26, 15.5)
                context.stroke()
            elif key == "senseguard_kitchen":
                context.rectangle(8, 4, 18, 25)
                context.move_to(11, 7)
                context.line_to(21, 9)
                context.line_to(21, 26)
                context.stroke()
                context.arc(18, 18, 1.2, 0, math.tau)
                context.stroke()
            elif self.row_key.startswith("person:"):
                context.arc(16, 9, 4, 0, math.tau)
                context.stroke()
                context.move_to(8, 27)
                context.curve_to(9, 19, 23, 19, 24, 27)
                context.stroke()
            else:
                context.arc(16, 15, 7, 0, math.tau)
                context.stroke()

    class SignalDot(Gtk.DrawingArea):
        """The empty/green event indicator kept beside every signal icon."""

        def __init__(self, *, active: bool):
            super().__init__()
            self.set_content_width(14)
            self.set_content_height(14)
            self.set_halign(Gtk.Align.CENTER)
            self.set_valign(Gtk.Align.CENTER)
            self.set_draw_func(self._draw)
            self.active = active

        def _draw(self, _area, context, _width: int, _height: int) -> None:
            context.arc(7, 7, 4.5, 0, math.tau)
            if self.active:
                context.set_source_rgb(0.32, 0.90, 0.54)
                context.fill()
            else:
                context.set_source_rgb(0.34, 0.29, 0.39)
                context.set_line_width(1.7)
                context.stroke()

    class SentryWindow(Gtk.ApplicationWindow):
        def __init__(self, app, *, projection_mode: bool = False):
            super().__init__(application=app, title="SENTRY")
            self.set_icon_name("sentry")
            self.set_default_size(1120, 760)
            self.set_size_request(880, 620)
            self.projection_mode = projection_mode
            if projection_mode:
                self.set_decorated(False)
                self.set_cursor(Gdk.Cursor.new_from_name("none", None))
            self._last_state: str | None = None
            self._last_wake_at: str | None = None
            self._status_initialized = False
            # Sleep/standby is an ANIMA household setting. This UI only
            # reflects the resident status and never writes a local mode.
            self.sleep_enabled = False
            self._sleep_transition_state: str | None = None
            self.sensor_drawer = None
            self.sensor_toggle = None
            self.sensor_scroll = None
            self.sensor_resize_handle = None
            self.sensor_list = None
            self._sensor_refresh_source_id: int | None = None
            self._sensor_fetch_busy = False
            self._sensor_order = load_sensor_order(config_path)
            self._sensor_drawer_width = load_sensor_drawer_width(config_path)
            self._sensor_resize_start_width: int | None = None
            self._sensor_payload: dict[str, Any] | None = None
            self._build()
            self._refresh_status()
            GLib.timeout_add(40, self._refresh_status)

        @staticmethod
        def _card(title: str):
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            box.add_css_class("card")
            heading = Gtk.Label(label=title, xalign=0)
            heading.add_css_class("card-title")
            box.append(heading)
            return box

        def _build(self) -> None:
            css = Gtk.CssProvider()
            css.load_from_data(b"""
                window { background: #030305; color: #ffffff; }
                .main-canvas { background: #030305; }
                .projection-canvas { background: #000000; }
                .settings-drawer { background: #09080d; border-left: 1px solid #302040; }
                .settings-panel { background: #09080d; padding: 24px; }
                .sensor-drawer { background: #09080d; border-left: 1px solid #302040; }
                .sensor-panel { background: #09080d; padding: 8px 6px; min-width: 0; }
                .sensor-row { background: #100d17; border: 1px solid #2b2039; border-radius: 10px; padding: 6px; }
                .sensor-visual { min-width: 0; }
                .sensor-resize-handle { min-width: 10px; background: transparent; }
                .sensor-resize-handle:hover { background: rgba(181, 108, 255, 0.24); }
                .sensor-icon { color: #82768f; }
                .sensor-icon.active { color: #52e58a; }
                .sensor-dot { color: #554a63; }
                .sensor-dot.active { color: #52e58a; }
                .sensor-signal-time { color: #aaa2b9; font-size: 10px; line-height: 1.1; }
                .sensor-person-name { color: #ffffff; font-size: 10px; font-weight: 700; line-height: 1.1; }
                .sensor-drawer-toggle { min-width: 18px; min-height: 24px; padding: 0; margin: 0; background: transparent; border: 0; border-radius: 0; }
                .sensor-drawer-toggle:hover { background: transparent; border: 0; }
                .sensor-label { color: #ffffff; font-weight: 700; }
                .sensor-summary { color: #c88cff; font-size: 12px; }
                .card { background: #0d0b12; border: 1px solid #2f2240; border-radius: 16px; padding: 18px; }
                .card-title { font-size: 16px; font-weight: 700; color: #ffffff; }
                .state { font-family: Inter, Cantarell, sans-serif; font-size: 18px; font-weight: 650; letter-spacing: 1.4px; color: #f7f5fb; }
                .muted { color: #a9a5b5; }
                .profile-name { font-weight: 700; font-size: 16px; }
                .profile-row { padding: 10px; border-bottom: 1px solid #25202e; }
                .preference-label { color: #f7f5fb; font-weight: 650; }
                .preference-value { color: #c88cff; font-weight: 700; }
                .settings-title { font-size: 22px; font-weight: 750; color: #ffffff; }
                .drawer-toggle { background: rgba(10, 8, 14, 0.94); color: #ffffff; border: 1px solid #4a3162; border-right-width: 0; border-radius: 14px 0 0 14px; padding: 12px 9px; }
                .drawer-toggle:hover { background: #241932; border-color: #b56cff; }
                button { background: #17131f; color: #ffffff; border: 1px solid #3b2c4e; border-radius: 10px; padding: 8px 12px; }
                button:hover { background: #241932; border-color: #b56cff; }
                button.suggested-action { background: #9d4dff; color: #ffffff; border-color: #c68cff; font-weight: 700; }
                button.destructive-action { color: #ff8890; }
                entry { background: #0f0d14; color: #ffffff; border: 1px solid #3b2c4e; border-radius: 10px; padding: 10px; }
                progressbar trough { min-height: 8px; background: #17131f; }
                progressbar progress { background: #b56cff; }
            """)
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )
            root = Gtk.Overlay()
            main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            main.add_css_class("main-canvas")
            if self.projection_mode:
                main.add_css_class("projection-canvas")
            main.set_hexpand(True)
            main.set_vexpand(True)

            status = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            status.set_halign(Gtk.Align.CENTER)
            status.set_valign(Gtk.Align.CENTER)
            status.set_vexpand(True)
            self.projection_fallback_orb = Gtk.DrawingArea()
            orb_size = orb_canvas_size(projection_mode=self.projection_mode)
            self.projection_fallback_orb.set_content_width(orb_size)
            self.projection_fallback_orb.set_content_height(orb_size)
            self.projection_fallback_orb.set_halign(Gtk.Align.CENTER)
            self.projection_fallback_orb.set_valign(Gtk.Align.CENTER)
            self.projection_fallback_orb.set_draw_func(self._draw_projection_fallback)
            self.projection_fallback_orb.set_visible(False)
            self.status_orb = StatusOrb(
                on_context_failure=self._show_projection_fallback if self.projection_mode else None,
                projection_mode=self.projection_mode,
            )
            self.status_orb.set_halign(Gtk.Align.CENTER)
            orb_stack = Gtk.Overlay()
            orb_stack.set_halign(Gtk.Align.CENTER)
            orb_stack.set_valign(Gtk.Align.CENTER)
            # The live orb must be the measuring child. Making it an overlay
            # over a hidden fallback collapses the stack to the label height,
            # which pushes the 600 px desktop orb below the window center.
            orb_stack.set_child(self.status_orb)
            orb_stack.add_overlay(self.projection_fallback_orb)
            status.append(orb_stack)
            self.state_label = Gtk.Label(label="Standby", xalign=0.5)
            self.state_label.add_css_class("state")
            status.append(self.state_label)
            main.append(status)

            root.set_child(main)

            # A projection renders the same state animation but owns no local
            # voice, identity, or household state. Those remain on the PC.
            if self.projection_mode:
                self.set_child(root)
                self.fullscreen()
                return

            # Household signal inspection is read-only. Voice, wake/sleep,
            # active-location, and identity enrollment remain ANIMA-owned.
            self._build_sensor_drawer(root)
            self.set_child(root)
            return

            scroll = Gtk.ScrolledWindow()
            scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            scroll.set_size_request(480, -1)
            scroll.set_vexpand(True)
            scroll.add_css_class("settings-drawer")
            settings = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
            settings.add_css_class("settings-panel")
            settings_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            title = Gtk.Label(label="Settings", xalign=0)
            title.add_css_class("settings-title")
            title.set_hexpand(True)
            settings_header.append(title)
            settings.append(settings_header)

            sleep_card = self._card("Wake availability")
            sleep_message = Gtk.Label(
                label="Sleep and standby are managed in ANIMA Settings for the active projection.",
                xalign=0,
                wrap=True,
            )
            sleep_message.add_css_class("muted")
            sleep_card.append(sleep_message)
            settings.append(sleep_card)

            self.settings_runtime_label = Gtk.Label(label="Voice: unavailable", xalign=0)
            self.settings_runtime_label.add_css_class("muted")
            self.settings_speaker_label = Gtk.Label(label="Speaker context unavailable", xalign=0, wrap=True)
            self.settings_speaker_label.add_css_class("muted")
            settings.append(self.settings_runtime_label)
            settings.append(self.settings_speaker_label)

            voice_card = self._card("Voice")
            voice_help = Gtk.Label(
                label="Voice, speaking pace, and wake availability are managed by ANIMA for the active SENTRY projection.",
                xalign=0,
                wrap=True,
            )
            voice_help.add_css_class("muted")
            voice_card.append(voice_help)
            current_voice, current_speed = load_voice_preferences(config_path)
            voice_label = Gtk.Label(label="Voice", xalign=0)
            voice_label.add_css_class("preference-label")
            voice_card.append(voice_label)
            self.voice_choice = Gtk.ComboBoxText()
            for identifier, label in KOKORO_ENGLISH_VOICES:
                self.voice_choice.append(identifier, label)
            self.voice_choice.set_active_id(current_voice)
            self.voice_choice.set_sensitive(False)
            voice_card.append(self.voice_choice)

            speed_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            speed_label = Gtk.Label(label="Speech speed", xalign=0)
            speed_label.add_css_class("preference-label")
            speed_label.set_hexpand(True)
            self.voice_speed_value = Gtk.Label(xalign=1)
            self.voice_speed_value.add_css_class("preference-value")
            speed_header.append(speed_label)
            speed_header.append(self.voice_speed_value)
            voice_card.append(speed_header)
            self.voice_speed = Gtk.Scale.new_with_range(
                Gtk.Orientation.HORIZONTAL,
                KOKORO_MIN_SPEED,
                KOKORO_MAX_SPEED,
                0.05,
            )
            self.voice_speed.set_draw_value(False)
            self.voice_speed.set_hexpand(True)
            self.voice_speed.set_value(current_speed)
            self.voice_speed.add_mark(0.75, Gtk.PositionType.BOTTOM, "Slower")
            self.voice_speed.add_mark(1.0, Gtk.PositionType.BOTTOM, "Natural")
            self.voice_speed.add_mark(1.30, Gtk.PositionType.BOTTOM, "Faster")
            self.voice_speed.connect("value-changed", self._voice_speed_changed)
            self.voice_speed.set_sensitive(False)
            self._voice_speed_changed(self.voice_speed)
            voice_card.append(self.voice_speed)

            voice_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            self.preview_voice_button = Gtk.Button(label="Preview voice")
            self.save_voice_button = Gtk.Button(label="Save and apply")
            self.save_voice_button.add_css_class("suggested-action")
            self.preview_voice_button.connect("clicked", self._preview_selected_voice)
            self.save_voice_button.connect("clicked", self._save_selected_voice)
            voice_actions.append(self.preview_voice_button)
            voice_actions.append(self.save_voice_button)
            self.preview_voice_button.set_sensitive(False)
            self.save_voice_button.set_sensitive(False)
            voice_card.append(voice_actions)
            self.voice_message = Gtk.Label(
                label="Open ANIMA → Settings → SENTRY voice to change the household voice. Changes are read by the processing host through the authenticated ANIMA bridge.",
                xalign=0,
                wrap=True,
            )
            self.voice_message.add_css_class("muted")
            voice_card.append(self.voice_message)
            settings.append(voice_card)

            profiles = self._card("Enrolled people")
            self.profile_list = Gtk.ListBox()
            self.profile_list.set_selection_mode(Gtk.SelectionMode.NONE)
            profiles.append(self.profile_list)
            self.test_button = Gtk.Button(label="Test recognition now")
            self.test_button.connect("clicked", self._test_recognition)
            profiles.append(self.test_button)
            settings.append(profiles)

            enroll = self._card("Add or update a person")
            self.name_entry = Gtk.Entry(placeholder_text="Username, for example Sketch")
            enroll.append(self.name_entry)
            controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            self.start_button = Gtk.Button(label="Start enrollment")
            self.start_button.add_css_class("suggested-action")
            self.capture_button = Gtk.Button(label="Take picture", sensitive=False)
            self.save_button = Gtk.Button(label="Save profile", sensitive=False)
            self.cancel_button = Gtk.Button(label="Cancel", sensitive=False)
            for button in (self.start_button, self.capture_button, self.save_button, self.cancel_button):
                controls.append(button)
            self.start_button.connect("clicked", self._start)
            self.capture_button.connect("clicked", self._capture)
            self.save_button.connect("clicked", self._save)
            self.cancel_button.connect("clicked", self._cancel)
            enroll.append(controls)
            self.progress = Gtk.ProgressBar(show_text=True)
            enroll.append(self.progress)
            self.preview = Gtk.Picture()
            self.preview.set_size_request(420, 250)
            self.preview.set_content_fit(Gtk.ContentFit.CONTAIN)
            enroll.append(self.preview)
            self.message = Gtk.Label(label="Enter a username to begin.", xalign=0, wrap=True)
            self.message.add_css_class("muted")
            enroll.append(self.message)
            privacy = Gtk.Label(
                label="Enrollment images stay in memory. Only a normalized local face profile and username are saved. Unrecognized speakers are called operator.",
                xalign=0, wrap=True,
            )
            privacy.add_css_class("muted")
            enroll.append(privacy)
            settings.append(enroll)
            scroll.set_child(settings)

            gtk_settings = Gtk.Settings.get_default()
            animations_enabled = bool(
                gtk_settings and gtk_settings.get_property("gtk-enable-animations")
            )
            drawer = Gtk.Revealer()
            drawer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_LEFT)
            drawer.set_transition_duration(260 if animations_enabled else 0)
            drawer.set_reveal_child(False)
            drawer.set_child(scroll)
            toggle = Gtk.Button(icon_name="go-previous-symbolic")
            toggle.set_tooltip_text("Open SENTRY settings and people")
            toggle.add_css_class("drawer-toggle")
            toggle.set_valign(Gtk.Align.START)
            toggle.set_margin_top(24)
            toggle.connect("clicked", self._toggle_settings)
            drawer_host = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            drawer_host.set_halign(Gtk.Align.END)
            drawer_host.set_valign(Gtk.Align.FILL)
            drawer_host.set_vexpand(True)
            drawer_host.append(toggle)
            drawer_host.append(drawer)
            root.add_overlay(drawer_host)
            root.set_measure_overlay(drawer_host, False)
            root.set_clip_overlay(drawer_host, True)
            self.settings_drawer = drawer
            self.settings_toggle = toggle
            self.set_child(root)

        def _build_sensor_drawer(self, root) -> None:
            """Add the desktop-only live signal drawer without touching the orb."""

            scroll = Gtk.ScrolledWindow()
            scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            # Keep the signal drawer compact: the icon, dot, and one-line
            # timestamp remain visible while avoiding a large empty panel.
            scroll.set_size_request(self._sensor_drawer_width, -1)
            scroll.set_hexpand(False)
            scroll.set_vexpand(True)
            scroll.add_css_class("sensor-drawer")

            panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
            panel.add_css_class("sensor-panel")
            panel.set_hexpand(True)
            self.sensor_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            self.sensor_list.set_hexpand(True)
            panel.append(self.sensor_list)
            scroll.set_child(panel)

            resize_handle = Gtk.Box()
            resize_handle.add_css_class("sensor-resize-handle")
            resize_handle.set_size_request(10, -1)
            resize_handle.set_vexpand(True)
            motion = Gtk.EventControllerMotion()
            motion.connect("enter", self._sensor_resize_pointer_enter)
            motion.connect("leave", self._sensor_resize_pointer_leave)
            resize_handle.add_controller(motion)
            gesture = Gtk.GestureDrag()
            gesture.set_button(1)
            gesture.connect("drag-begin", self._begin_sensor_resize)
            gesture.connect("drag-update", self._update_sensor_resize)
            gesture.connect("drag-end", self._end_sensor_resize)
            resize_handle.add_controller(gesture)

            drawer_body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            drawer_body.set_hexpand(False)
            drawer_body.set_vexpand(True)
            drawer_body.append(resize_handle)
            drawer_body.append(scroll)

            gtk_settings = Gtk.Settings.get_default()
            animations_enabled = bool(
                gtk_settings and gtk_settings.get_property("gtk-enable-animations")
            )
            drawer = Gtk.Revealer()
            drawer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_LEFT)
            drawer.set_transition_duration(260 if animations_enabled else 0)
            drawer.set_reveal_child(False)
            drawer.set_child(drawer_body)
            toggle = Gtk.Button(icon_name="go-previous-symbolic")
            toggle.add_css_class("sensor-drawer-toggle")
            toggle.set_size_request(18, 24)
            toggle.set_valign(Gtk.Align.START)
            toggle.set_margin_top(8)
            toggle.connect("clicked", self._toggle_sensor_drawer)
            drawer_host = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            drawer_host.set_halign(Gtk.Align.END)
            drawer_host.set_valign(Gtk.Align.FILL)
            drawer_host.set_vexpand(True)
            drawer_host.append(toggle)
            drawer_host.append(drawer)
            root.add_overlay(drawer_host)
            root.set_measure_overlay(drawer_host, False)
            root.set_clip_overlay(drawer_host, True)
            self.sensor_drawer = drawer
            self.sensor_toggle = toggle
            self.sensor_scroll = scroll
            self.sensor_resize_handle = resize_handle

        def _set_sensor_drawer_width(self, width: int, *, persist: bool) -> None:
            width = sensor_drawer_width(width)
            self._sensor_drawer_width = width
            if self.sensor_scroll is not None:
                self.sensor_scroll.set_size_request(width, -1)
                self.sensor_scroll.queue_resize()
            if persist:
                try:
                    save_sensor_drawer_width(config_path, width)
                except (OSError, TypeError, ValueError, json.JSONDecodeError):
                    # A local UI preference must never take down the voice display.
                    pass

        def _sensor_resize_pointer_enter(self, _controller, _x: float, _y: float) -> None:
            if self.sensor_resize_handle is not None:
                self.sensor_resize_handle.set_cursor(Gdk.Cursor.new_from_name("ew-resize", None))

        def _sensor_resize_pointer_leave(self, _controller) -> None:
            if self.sensor_resize_handle is not None:
                self.sensor_resize_handle.set_cursor(None)

        def _begin_sensor_resize(self, _gesture, _start_x: float, _start_y: float) -> None:
            if self.projection_mode or self.sensor_drawer is None:
                return
            self._sensor_resize_start_width = self._sensor_drawer_width

        def _update_sensor_resize(self, _gesture, offset_x: float, _offset_y: float) -> None:
            if self._sensor_resize_start_width is None:
                return
            # The handle is the drawer's left edge: dragging left widens it;
            # dragging right makes it more compact.
            self._set_sensor_drawer_width(
                self._sensor_resize_start_width - round(offset_x), persist=False
            )

        def _end_sensor_resize(self, _gesture, _offset_x: float, _offset_y: float) -> None:
            if self._sensor_resize_start_width is None:
                return
            self._set_sensor_drawer_width(self._sensor_drawer_width, persist=True)
            self._sensor_resize_start_width = None

        def _toggle_sensor_drawer(self, _button) -> None:
            if self.projection_mode or self.sensor_drawer is None:
                return
            opening = not self.sensor_drawer.get_reveal_child()
            self.sensor_drawer.set_reveal_child(opening)
            if self.sensor_toggle is not None:
                self.sensor_toggle.set_icon_name(
                    "go-next-symbolic" if opening else "go-previous-symbolic"
                )
            if opening:
                if self._sensor_refresh_source_id is None:
                    self._sensor_refresh_source_id = GLib.timeout_add_seconds(
                        2, self._refresh_sensor_status
                    )
                self._refresh_sensor_status()
            elif self._sensor_refresh_source_id is not None:
                GLib.source_remove(self._sensor_refresh_source_id)
                self._sensor_refresh_source_id = None

        def _apply_sensor_status(self, payload: dict[str, Any]) -> bool:
            self._sensor_fetch_busy = False
            self._sensor_payload = payload
            if self.sensor_drawer is None or not self.sensor_drawer.get_reveal_child():
                return False
            rows = order_sensor_rows(sensor_indicator_rows(payload), self._sensor_order)
            if self.sensor_list is None:
                return False
            child = self.sensor_list.get_first_child()
            while child is not None:
                next_child = child.get_next_sibling()
                self.sensor_list.remove(child)
                child = next_child
            if not rows:
                empty = Gtk.Label(label=sensor_status_message(payload), xalign=0)
                empty.add_css_class("muted")
                self.sensor_list.append(empty)
                return False
            for row in rows:
                sensor_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                sensor_row.add_css_class("sensor-row")
                sensor_row.set_hexpand(True)
                sensor_row.set_name(row["key"])
                sensor_row.set_tooltip_text("Drag to rearrange")
                icon_cell = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                icon_cell.set_halign(Gtk.Align.CENTER)
                icon_cell.set_valign(Gtk.Align.CENTER)
                icon_cell.add_css_class("sensor-visual")
                icon = SignalIcon(row["key"], active=bool(row["active"]))
                icon.set_tooltip_text(row["label"])
                icon_cell.append(icon)
                icon_cell.append(SignalDot(active=bool(row["active"])))
                visual = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
                visual.set_halign(Gtk.Align.CENTER)
                visual.set_hexpand(True)
                visual.append(icon_cell)
                signal_time = local_signal_timestamp(row["last_event_at"])
                if row["kind"] == "presence":
                    person_meta = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                    person_meta.set_halign(Gtk.Align.CENTER)
                    person_name = Gtk.Label(label=row["label"], xalign=0)
                    person_name.set_size_request(34, -1)
                    person_name.set_xalign(0.5)
                    person_name.add_css_class("sensor-person-name")
                    person_meta.append(person_name)
                    time_label = Gtk.Label(label=signal_time or "—", xalign=0)
                    time_label.add_css_class("sensor-signal-time")
                    person_meta.append(time_label)
                    visual.append(person_meta)
                else:
                    time_label = Gtk.Label(label=signal_time or "—", xalign=0.5)
                    time_label.set_halign(Gtk.Align.CENTER)
                    time_label.add_css_class("sensor-signal-time")
                    visual.append(time_label)
                sensor_row.append(visual)
                self.sensor_list.append(sensor_row)

                drag_source = Gtk.DragSource()
                drag_source.set_actions(Gdk.DragAction.MOVE)
                drag_source.connect("prepare", self._prepare_sensor_drag, row["key"])
                sensor_row.add_controller(drag_source)
                drop_target = Gtk.DropTarget.new(GObject.TYPE_STRING, Gdk.DragAction.MOVE)
                drop_target.connect("drop", self._drop_sensor_row, row["key"])
                sensor_row.add_controller(drop_target)
            return False

        def _prepare_sensor_drag(self, _source, _x: float, _y: float, key: str):
            return Gdk.ContentProvider.new_for_value(key)

        def _drop_sensor_row(
            self, _target, value: object, _x: float, _y: float, target_key: str
        ) -> bool:
            if not isinstance(value, str):
                return False
            self._reorder_sensor_rows(value, target_key)
            return True

        def _reorder_sensor_rows(self, dragged_key: str, target_key: str) -> None:
            if dragged_key == target_key or self.sensor_list is None:
                return
            current: list[str] = []
            child = self.sensor_list.get_first_child()
            while child is not None:
                key = child.get_name()
                if key:
                    current.append(key)
                child = child.get_next_sibling()
            if dragged_key not in current or target_key not in current:
                return
            current.remove(dragged_key)
            current.insert(current.index(target_key), dragged_key)
            self._sensor_order = current
            try:
                save_sensor_order(config_path, current)
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                # A drawer preference must never take down the voice display.
                pass
            if self._sensor_payload is not None:
                self._apply_sensor_status(self._sensor_payload)

        def _refresh_sensor_status(self) -> bool:
            if (
                self.projection_mode
                or self.sensor_drawer is None
                or not self.sensor_drawer.get_reveal_child()
            ):
                return False
            if self._sensor_fetch_busy:
                return True
            self._sensor_fetch_busy = True

            def fetch() -> None:
                payload = read_sensor_status()
                GLib.idle_add(self._apply_sensor_status, payload)

            threading.Thread(target=fetch, name="sentry-sensor-status", daemon=True).start()
            return True

        def _show_projection_fallback(self) -> bool:
            if not self.projection_mode:
                return False
            self.projection_fallback_orb.set_visible(True)
            return False

        def _draw_projection_fallback(self, _area, context, width: int, height: int) -> None:
            # GPU-safe rendering for compositors that cannot create the
            # requested GL 3.3 context. This intentionally mirrors the desktop
            # scene language: a dark stage, luminous field, layered shell,
            # orbital structure, and state-driven material rather than a plain
            # filled circle. It remains bounded and cheap enough for a Pi 5.
            frame = self.status_orb.controller.frame(reduced_motion=self.status_orb.reduced_motion)
            red, green, blue = frame["color"]
            cx, cy = width / 2.0, height / 2.0
            t = float(frame["time"])
            audio = max(0.0, min(1.0, float(frame.get("audio_level") or 0.0)))
            wake = max(0.0, min(1.0, float(frame.get("wake_progress") or 0.0)))
            radius = min(width, height) * (0.31 + audio * 0.018)
            context.set_operator(cairo.OPERATOR_SOURCE)
            context.set_source_rgb(0.0, 0.0, 0.0)
            context.paint()
            stage = cairo.RadialGradient(cx, cy * 0.92, radius * 0.05, cx, cy * 0.92, radius * 2.0)
            stage.add_color_stop_rgba(0.0, red * 0.20, green * 0.20, blue * 0.20, 0.34)
            stage.add_color_stop_rgba(0.42, red * 0.07, green * 0.07, blue * 0.12, 0.14)
            stage.add_color_stop_rgba(1.0, 0.0, 0.0, 0.0, 0.0)
            context.set_source(stage)
            context.arc(cx, cy, radius * 1.95, 0, math.tau)
            context.fill()

            # A soft floor reflection gives the projection a stable visual
            # anchor and makes the orb read as a designed scene on a TV.
            floor = cairo.RadialGradient(cx, cy + radius * 1.12, 0.0, cx, cy + radius * 1.12, radius * 0.95)
            floor.add_color_stop_rgba(0.0, red * 0.18, green * 0.18, blue * 0.22, 0.24)
            floor.add_color_stop_rgba(1.0, red * 0.02, green * 0.02, blue * 0.02, 0.0)
            context.save()
            context.scale(1.0, 0.16)
            context.set_source(floor)
            context.arc(cx, (cy + radius * 1.12) / 0.16, radius * 0.95, 0, math.tau)
            context.fill()
            context.restore()

            glow = cairo.RadialGradient(cx, cy, radius * 0.10, cx, cy, radius * 1.55)
            glow.add_color_stop_rgba(0.0, min(1.0, red * 1.35), min(1.0, green * 1.35), min(1.0, blue * 1.35), 0.68)
            glow.add_color_stop_rgba(0.42, red * 0.34, green * 0.34, blue * 0.34, 0.22)
            glow.add_color_stop_rgba(1.0, red * 0.03, green * 0.03, blue * 0.03, 0.0)
            context.set_source(glow)
            context.arc(cx, cy, radius * 1.55, 0, math.tau)
            context.fill()

            context.save()
            context.translate(cx, cy)
            # Three translucent orbital shells echo the full renderer's
            # dimensional glass and remain crisp with Cairo antialiasing.
            for index, tilt in enumerate((0.38, 0.57, 0.78)):
                context.save()
                context.rotate(t * (0.035 + index * 0.017) * (0.25 if self.status_orb.reduced_motion else 1.0) + index * 0.82)
                context.scale(1.0, tilt)
                context.set_line_width(max(1.4, radius * (0.010 - index * 0.001)))
                context.set_source_rgba(red, green, blue, 0.25 - index * 0.045)
                context.arc(0.0, 0.0, radius * (1.12 + index * 0.045), 0.0, math.tau)
                context.stroke()
                context.restore()

            # Animated field contours provide recognizable structure when the
            # GL shader is unavailable, while using deterministic trigonometry
            # instead of random particles or external state.
            for layer in range(3):
                path_radius = radius * (0.77 + layer * 0.085)
                for point in range(49):
                    angle = math.tau * point / 48.0
                    wave = math.sin(angle * (3.0 + layer) + t * (0.16 + layer * 0.05)) * (0.018 + audio * 0.020)
                    wave += math.sin(angle * 7.0 - t * 0.11) * 0.010
                    distance = path_radius * (1.0 + wave)
                    x = math.cos(angle) * distance
                    y = math.sin(angle) * distance
                    if point == 0:
                        context.move_to(x, y)
                    else:
                        context.line_to(x, y)
                context.set_line_width(max(1.0, radius * 0.006))
                context.set_source_rgba(
                    red if layer % 2 == 0 else min(1.0, red + 0.18),
                    green if layer % 2 == 0 else min(1.0, green + 0.18),
                    blue if layer % 2 == 0 else min(1.0, blue + 0.18),
                    0.42 - layer * 0.09,
                )
                context.stroke()

            # A restrained set of orbiting sparks supplies the desktop scene's
            # sense of motion without becoming visually noisy at TV scale.
            for index in range(18):
                angle = t * (0.10 + (index % 4) * 0.018) + index * 0.87
                distance = radius * (0.86 + (index % 5) * 0.075)
                spark = 1.0 + math.sin(t * 0.9 + index) * 0.20
                context.arc(math.cos(angle) * distance, math.sin(angle) * distance * 0.86, max(1.0, radius * 0.009 * spark), 0, math.tau)
                context.set_source_rgba(min(1.0, red + 0.30), min(1.0, green + 0.30), min(1.0, blue + 0.30), 0.34)
                context.fill()

            context.restore()

            core_radius = radius * (0.58 + audio * 0.025)
            core = cairo.RadialGradient(cx, cy, radius * 0.06, cx, cy, core_radius)
            core.add_color_stop_rgba(0.0, min(1.0, red + 0.35), min(1.0, green + 0.35), min(1.0, blue + 0.35), 0.50)
            core.add_color_stop_rgba(0.38, red * 0.60, green * 0.60, blue * 0.60, 0.28)
            core.add_color_stop_rgba(0.90, red * 0.20, green * 0.20, blue * 0.20, 0.10)
            core.add_color_stop_rgba(1.0, red * 0.06, green * 0.06, blue * 0.06, 0.0)
            context.set_source(core)
            context.arc(cx, cy, core_radius, 0, math.tau)
            context.fill()

            context.set_line_width(max(2.0, radius * 0.018))
            context.set_source_rgba(min(1.0, red + 0.18), min(1.0, green + 0.18), min(1.0, blue + 0.18), 0.70)
            context.arc(cx, cy, radius * (0.89 + 0.018 * math.sin(t * 0.7)), 0, math.tau)
            context.stroke()

            if 0.0 <= wake <= 1.0:
                ring_radius = radius * (0.92 + wake * 0.72)
                context.set_line_width(max(2.0, radius * (0.024 - wake * 0.012)))
                context.set_source_rgba(0.74, 0.92, 1.0, (1.0 - wake) * 0.78)
                context.arc(cx, cy, ring_radius, 0, math.tau)
                context.stroke()

        def _toggle_settings(self, _button) -> None:
            """Compatibility alias for the removed local-settings drawer."""
            self._toggle_sensor_drawer(_button)

        def close_settings(self) -> None:
            """Close the optional read-only drawer when the app is activated."""
            if self.sensor_drawer is None:
                return
            self.sensor_drawer.set_reveal_child(False)
            if self.sensor_toggle is not None:
                self.sensor_toggle.set_icon_name("go-previous-symbolic")
            if self._sensor_refresh_source_id is not None:
                GLib.source_remove(self._sensor_refresh_source_id)
                self._sensor_refresh_source_id = None

        def _refresh_status(self) -> bool:
            runtime_payload = read_voice_status()
            if self.projection_mode:
                runtime_payload = projection_instance_payload(runtime_payload)
            if isinstance(runtime_payload.get("desired_sleep_enabled"), bool):
                self.sleep_enabled = runtime_payload["desired_sleep_enabled"]
            # Observed state is never fabricated from desired sleep/instance.
            payload = runtime_payload
            state, guidance, _identity = voice_status_summary(payload)
            wake_at = str(payload.get("last_wake_at") or "") or None
            acknowledge = should_acknowledge_wake(self._last_wake_at, wake_at) if self._status_initialized else False
            self.status_orb.present(payload, acknowledge_wake=acknowledge)
            if self.projection_mode and self.projection_fallback_orb.get_visible():
                self.projection_fallback_orb.queue_draw()
            self.state_label.set_text(guidance)
            self._last_state = state
            self._last_wake_at = wake_at
            self._status_initialized = True
            return True

        def _run(self, operation: Callable[[], Any], complete: Callable[[Any], None]) -> None:
            if self._busy:
                return
            self._busy = True
            self._set_controls()

            def worker() -> None:
                try:
                    result = operation()
                except Exception as exc:  # noqa: BLE001 - display bounded local failure
                    GLib.idle_add(self._finish_error, f"{type(exc).__name__}: {exc}")
                else:
                    GLib.idle_add(self._finish, complete, result)

            threading.Thread(target=worker, name="sentry-ui-operation", daemon=True).start()

        def _finish(self, complete: Callable[[Any], None], result: Any) -> bool:
            self._busy = False
            complete(result)
            self._set_controls()
            return False

        def _finish_error(self, message: str) -> bool:
            self._busy = False
            self.message.set_text(message)
            self._set_controls()
            return False

        def _set_controls(self) -> None:
            active = self.session is not None
            accepted = int(self.session.get("accepted_samples", 0)) if active else 0
            target = int(self.session.get("target_samples", 8)) if active else 8
            ready = bool(self.session.get("ready_to_save")) if active else False
            self.start_button.set_sensitive(not self._busy and not active)
            self.capture_button.set_sensitive(not self._busy and active and accepted < target)
            self.save_button.set_sensitive(not self._busy and active and ready)
            self.cancel_button.set_sensitive(not self._busy and active)
            self.test_button.set_sensitive(not self._busy)
            self.preview_voice_button.set_sensitive(not self._busy)
            self.save_voice_button.set_sensitive(not self._busy)
            self.voice_choice.set_sensitive(not self._busy)
            self.voice_speed.set_sensitive(not self._busy)
            self.progress.set_fraction(accepted / target if active else 0)
            self.progress.set_text(f"{accepted} of {target}" if active else "No enrollment active")

        def _voice_speed_changed(self, scale) -> None:
            self.voice_speed_value.set_text(f"{scale.get_value():.2f}×")

        def _selected_voice_preferences(self) -> tuple[str, float]:
            identifier = self.voice_choice.get_active_id()
            if identifier is None:
                raise ValueError("Select a voice first")
            return identifier, round(float(self.voice_speed.get_value()), 2)

        def _run_voice_operation(
            self,
            operation: Callable[[], Any],
            complete: Callable[[Any], None],
            *,
            failed: Callable[[str], None] | None = None,
        ) -> None:
            if self._busy:
                return
            self._busy = True
            self._set_controls()

            def worker() -> None:
                try:
                    result = operation()
                except Exception as exc:  # noqa: BLE001 - bounded local UI result
                    GLib.idle_add(
                        self._finish_voice_error,
                        f"{type(exc).__name__}: {exc}",
                        failed,
                    )
                else:
                    GLib.idle_add(self._finish_voice_operation, complete, result)

            threading.Thread(
                target=worker,
                name="sentry-ui-voice-preference",
                daemon=True,
            ).start()

        def _finish_voice_operation(
            self,
            complete: Callable[[Any], None],
            result: Any,
        ) -> bool:
            self._busy = False
            complete(result)
            self._set_controls()
            return False

        def _finish_voice_error(
            self,
            message: str,
            failed: Callable[[str], None] | None = None,
        ) -> bool:
            self._busy = False
            if failed is None:
                self.voice_message.set_text(message)
            else:
                failed(message)
            self._set_controls()
            return False

        def _preview_selected_voice(self, _button) -> None:
            identifier, speed = self._selected_voice_preferences()
            label = self.voice_choice.get_active_text() or identifier
            self.voice_message.set_text(f"Preparing {label} at {speed:.2f}×…")

            def complete(delivered: bool) -> None:
                self.voice_message.set_text(
                    f"Previewed {label} at {speed:.2f}×."
                    if delivered
                    else "The local Kokoro preview could not be delivered."
                )

            self._run_voice_operation(
                lambda: preview_voice(identifier, speed),
                complete,
            )

        def _load_profiles(self) -> None:
            while child := self.profile_list.get_first_child():
                self.profile_list.remove(child)
            values = self.manager.profiles()
            if not values:
                label = Gtk.Label(label="No people enrolled.", xalign=0)
                label.add_css_class("muted")
                self.profile_list.append(label)
                return
            for profile in values:
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                row.add_css_class("profile-row")
                text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                name = Gtk.Label(label=str(profile["display_name"]), xalign=0)
                name.add_css_class("profile-name")
                identifier = Gtk.Label(label=str(profile["person_id"]), xalign=0)
                identifier.add_css_class("muted")
                text.append(name)
                text.append(identifier)
                text.set_hexpand(True)
                remove = Gtk.Button(label="Remove")
                remove.add_css_class("destructive-action")
                remove.connect("clicked", self._remove, str(profile["person_id"]), str(profile["display_name"]))
                row.append(text)
                row.append(remove)
                self.profile_list.append(row)

        def _start(self, _button) -> None:
            def complete(value):
                self.session = value
                self.message.set_text("Ready. Face the camera and vary your angle slightly between pictures.")
            self._run(lambda: self.manager.start(self.name_entry.get_text(), 8), complete)

        def _capture(self, _button) -> None:
            if self.session is None:
                return
            session_id = str(self.session["session_id"])
            self.message.set_text("Opening the camera for one deliberate picture…")

            def complete(value):
                self.session = value
                if value.get("accepted"):
                    self.message.set_text(f"Picture {value['accepted_samples']} accepted. Change pose slightly.")
                    encoded = value.get("preview_jpeg_base64")
                    if encoded:
                        loader = GdkPixbuf.PixbufLoader.new_with_type("jpeg")
                        loader.write(base64.b64decode(encoded))
                        loader.close()
                        self._preview_texture = Gdk.Texture.new_for_pixbuf(loader.get_pixbuf())
                        self.preview.set_paintable(self._preview_texture)
                else:
                    self.message.set_text(f"Picture not accepted: {value.get('reason', 'face was not clear')}.")
            self._run(lambda: self.manager.capture(session_id), complete)

        def _save(self, _button) -> None:
            if self.session is None:
                return
            session_id = str(self.session["session_id"])

            def complete(value):
                self.session = None
                self._preview_texture = None
                self.preview.set_paintable(None)
                self.message.set_text(f"Saved {value['display_name']}. The next Sentry wake will run a fresh identity check.")
                self._load_profiles()
            self._run(lambda: self.manager.commit(session_id), complete)

        def _cancel(self, _button) -> None:
            if self.session is None:
                return
            session_id = str(self.session["session_id"])

            def complete(_value):
                self.session = None
                self._preview_texture = None
                self.preview.set_paintable(None)
                self.message.set_text("Enrollment cancelled; temporary samples were discarded.")
            self._run(lambda: self.manager.cancel(session_id), complete)

        def _remove(self, _button, person_id: str, display_name: str) -> None:
            if self._delete_candidate != person_id:
                self._delete_candidate = person_id
                self.message.set_text(f"Click Remove beside {display_name} again to confirm.")
                return

            def complete(_value):
                self._delete_candidate = None
                self.message.set_text(f"Removed {display_name}. The next Sentry wake will refresh identity.")
                self._load_profiles()
            self._run(lambda: self.manager.delete(person_id), complete)

        def _test_recognition(self, _button) -> None:
            from tools.sentry_office_vision import OfficeVisionInspector

            self.message.set_text("Opening the camera for a bounded recognition check…")

            def operation():
                metadata, image = OfficeVisionInspector(config_path).inspect(
                    duration_seconds=3.0, include_image=True, completion_timeout_seconds=5.0,
                )
                return metadata, image

            def complete(value):
                metadata, image = value
                if image:
                    loader = GdkPixbuf.PixbufLoader.new_with_type("jpeg")
                    loader.write(image)
                    loader.close()
                    self._preview_texture = Gdk.Texture.new_for_pixbuf(loader.get_pixbuf())
                    self.preview.set_paintable(self._preview_texture)
                people = [item for item in metadata.get("people", []) if item.get("visible", True)]
                recognized = next((item for item in people if item.get("identity_state") == "recognized"), None)
                if recognized:
                    self.message.set_text(f"Recognized {recognized.get('display_name') or recognized.get('person_id')}.")
                elif not people:
                    self.message.set_text("No person was visible. Adjust the camera or move into view and try again.")
                else:
                    self.message.set_text("A person was visible, but no clear enrolled face matched. Face the camera and try again.")
            self._run(operation, complete)

    class SentryApplication(Gtk.Application):
        def __init__(self, *, projection_mode: bool = False):
            super().__init__(application_id="local.sentry.Control", flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
            self.projection_mode = projection_mode

        def do_activate(self):
            window = self.props.active_window
            if window is None:
                window = SentryWindow(self, projection_mode=self.projection_mode)
            window.close_settings()
            window.present()

    return SentryApplication(projection_mode=projection_mode)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("~/.config/sentry/config.json"))
    parser.add_argument(
        "--projection",
        action="store_true",
        help="render the state-only projection; voice and identity remain on the processing host",
    )
    args = parser.parse_args(argv)
    try:
        application = build_application(args.config.expanduser(), projection_mode=args.projection)
        return int(application.run([sys.argv[0]]))
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"SENTRY UI failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
