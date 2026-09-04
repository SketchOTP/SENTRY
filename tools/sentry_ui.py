"""Native GTK control surface for SENTRY voice status and identity enrollment."""

from __future__ import annotations

import argparse
import base64
import json
import math
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.sentry_identity_enrollment import IdentityEnrollmentManager  # noqa: E402
from perception.voice import (  # noqa: E402
    KOKORO_ENGLISH_VOICE_IDS,
    KOKORO_ENGLISH_VOICES,
    KOKORO_MAX_SPEED,
    KOKORO_MIN_SPEED,
)


def load_voice_preferences(config_path: Path) -> tuple[str, float]:
    """Read the validated resident Kokoro preference without exposing other config."""

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("SENTRY config must be an object")
    voice = payload.get("voice", {})
    if not isinstance(voice, dict):
        raise ValueError("SENTRY voice config must be an object")
    identifier = str(voice.get("kokoro_voice", "bm_george"))
    speed = float(voice.get("kokoro_speed", 0.9))
    if identifier not in KOKORO_ENGLISH_VOICE_IDS:
        raise ValueError("configured Kokoro voice is not supported")
    if not KOKORO_MIN_SPEED <= speed <= KOKORO_MAX_SPEED:
        raise ValueError("configured Kokoro speed is outside the supported range")
    return identifier, speed


def load_sleep_preference(config_path: Path) -> bool:
    """Read the persistent wake-suppression preference; absence means awake."""

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("SENTRY config must be an object")
    voice = payload.get("voice", {})
    if not isinstance(voice, dict):
        raise ValueError("SENTRY voice config must be an object")
    return bool(voice.get("sleep_enabled", False))


def _persist_voice_settings(config_path: Path, updates: dict[str, Any]) -> None:
    """Atomically persist validated voice settings while preserving all others."""

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("SENTRY config must be an object")
    voice = payload.setdefault("voice", {})
    if not isinstance(voice, dict):
        raise ValueError("SENTRY voice config must be an object")
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


def save_sleep_preference(config_path: Path, enabled: bool) -> None:
    """Persist the fail-closed wake suppression preference."""

    if not isinstance(enabled, bool):
        raise ValueError("sleep preference must be boolean")
    _persist_voice_settings(config_path, {"sleep_enabled": enabled})


def voice_service_is_active() -> bool:
    result = subprocess.run(
        ["systemctl", "--user", "is-active", "--quiet", "sentry-voice.service"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def apply_voice_preferences(config_path: Path, identifier: str, speed: float) -> bool:
    """Persist a selection and reload the active resident listener when needed."""

    was_active = voice_service_is_active()
    save_voice_preferences(config_path, identifier, speed)
    if was_active:
        subprocess.run(
            ["systemctl", "--user", "restart", "sentry-voice.service"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=30,
        )
    return was_active


def apply_sleep_preference(config_path: Path, enabled: bool) -> str:
    """Persist Sleep and enforce it at the resident service boundary."""

    save_sleep_preference(config_path, enabled)
    command = "stop" if enabled else "start"
    try:
        subprocess.run(
            ["systemctl", "--user", command, "sentry-voice.service"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=30,
        )
        active = voice_service_is_active()
        if enabled and active:
            raise RuntimeError("resident listener remained active after enabling Sleep")
        if not enabled and not active:
            raise RuntimeError("resident listener did not start after disabling Sleep")
    except Exception:
        # Keep the persisted setting aligned with the actual pre-toggle state.
        save_sleep_preference(config_path, not enabled)
        raise
    return "sleeping" if enabled else "starting"


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
            elif self.previous_state in {"LISTENING", "FOLLOWUP_LISTENING"} and state == "PROCESSING":
                self.transition_duration = 1.55
            elif self.previous_state == "PROCESSING" and state == "SPEAKING":
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


def read_voice_status(path: Path | None = None) -> dict[str, Any]:
    target = path or voice_status_path()
    if not target.is_file():
        return {"state": "UNAVAILABLE", "reason": "Voice listener has not published status."}
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"state": "UNAVAILABLE", "reason": type(exc).__name__}
    return value if isinstance(value, dict) else {"state": "UNAVAILABLE", "reason": "Invalid status payload."}


def resolve_sleep_transition_status(
    runtime_payload: dict[str, Any],
    *,
    sleep_enabled: bool,
    transition_state: str | None,
) -> tuple[dict[str, Any], str | None]:
    """Prevent a stale sleeping record from masking listener startup."""

    runtime_state = str(runtime_payload.get("state") or "UNAVAILABLE").upper()
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


def build_application(config_path: Path):
    distro_packages = Path("/usr/lib/python3/dist-packages")
    if distro_packages.is_dir() and str(distro_packages) not in sys.path:
        # GTK is supplied by Ubuntu while OpenCV/Vosk remain in SENTRY's venv.
        sys.path.append(str(distro_packages))
    try:
        import gi

        gi.require_version("Gtk", "4.0")
        gi.require_version("Gdk", "4.0")
        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk
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

        def __init__(self):
            super().__init__()
            self.set_size_request(600, 600)
            self.set_required_version(3, 3)
            if hasattr(self, "set_allowed_apis"):
                self.set_allowed_apis(Gdk.GLAPI.GL)
            self.set_auto_render(False)
            self.controller = OrbStateController()
            self._program: int | None = None
            self._vertex_array: int | None = None
            self._gl = None
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
                return
            self._gl = GL
            self._program = shaders.compileProgram(
                shaders.compileShader(self.VERTEX_SHADER, GL.GL_VERTEX_SHADER),
                shaders.compileShader(self.FRAGMENT_SHADER, GL.GL_FRAGMENT_SHADER),
            )
            self._vertex_array = int(GL.glGenVertexArrays(1))

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

    class SentryWindow(Gtk.ApplicationWindow):
        def __init__(self, app):
            super().__init__(application=app, title="SENTRY")
            self.set_icon_name("sentry")
            self.set_default_size(1120, 760)
            self.set_size_request(880, 620)
            self.manager = IdentityEnrollmentManager(config_path)
            self.session: dict[str, Any] | None = None
            self._busy = False
            self._delete_candidate: str | None = None
            self._preview_texture = None
            self._last_state: str | None = None
            self._last_wake_at: str | None = None
            self._status_initialized = False
            self.sleep_enabled = load_sleep_preference(config_path)
            self._sleep_transition_state: str | None = None
            self._setting_sleep_programmatically = False
            self._build()
            self._load_profiles()
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
                .settings-drawer { background: #09080d; border-left: 1px solid #302040; }
                .settings-panel { background: #09080d; padding: 24px; }
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
            main.set_hexpand(True)
            main.set_vexpand(True)

            status = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            status.set_halign(Gtk.Align.CENTER)
            status.set_valign(Gtk.Align.CENTER)
            status.set_vexpand(True)
            self.status_orb = StatusOrb()
            self.status_orb.set_halign(Gtk.Align.CENTER)
            status.append(self.status_orb)
            self.state_label = Gtk.Label(label="Standby", xalign=0.5)
            self.state_label.add_css_class("state")
            status.append(self.state_label)
            main.append(status)
            root.set_child(main)

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

            sleep_card = self._card("Sleep")
            sleep_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
            sleep_copy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            sleep_copy.set_hexpand(True)
            sleep_title = Gtk.Label(label="Disable wake listening", xalign=0)
            sleep_title.add_css_class("preference-label")
            sleep_help = Gtk.Label(
                label="While enabled, SENTRY cannot be activated by the wake word.",
                xalign=0,
                wrap=True,
            )
            sleep_help.add_css_class("muted")
            sleep_copy.append(sleep_title)
            sleep_copy.append(sleep_help)
            self.sleep_toggle = Gtk.Switch()
            self.sleep_toggle.set_valign(Gtk.Align.CENTER)
            self.sleep_toggle.set_active(self.sleep_enabled)
            self.sleep_toggle.set_tooltip_text("Prevent all wake-word activation")
            self.sleep_toggle.connect("notify::active", self._sleep_toggled)
            sleep_row.append(sleep_copy)
            sleep_row.append(self.sleep_toggle)
            sleep_card.append(sleep_row)
            self.sleep_message = Gtk.Label(
                label=(
                    "Sleeping. Wake-word listening is off."
                    if self.sleep_enabled
                    else "Sleep is off. Wake-word listening is available."
                ),
                xalign=0,
                wrap=True,
            )
            self.sleep_message.add_css_class("muted")
            sleep_card.append(self.sleep_message)
            settings.append(sleep_card)

            self.settings_runtime_label = Gtk.Label(label="Voice: unavailable", xalign=0)
            self.settings_runtime_label.add_css_class("muted")
            self.settings_speaker_label = Gtk.Label(label="Speaker context unavailable", xalign=0, wrap=True)
            self.settings_speaker_label.add_css_class("muted")
            settings.append(self.settings_runtime_label)
            settings.append(self.settings_speaker_label)

            voice_card = self._card("Voice")
            voice_help = Gtk.Label(
                label="Choose SENTRY's English Kokoro voice and speaking pace.",
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
            voice_card.append(voice_actions)
            self.voice_message = Gtk.Label(
                label="Preview a voice before applying it. Saved changes also affect alarms and proactive speech.",
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

        def _toggle_settings(self, _button) -> None:
            opening = not self.settings_drawer.get_reveal_child()
            self.settings_drawer.set_reveal_child(opening)
            self.settings_toggle.set_icon_name(
                "go-next-symbolic" if opening else "go-previous-symbolic"
            )
            self.settings_toggle.set_tooltip_text(
                "Close SENTRY settings" if opening else "Open SENTRY settings and people"
            )

        def close_settings(self) -> None:
            """Restore the clean main surface whenever the application is launched."""

            self.settings_drawer.set_reveal_child(False)
            self.settings_toggle.set_icon_name("go-previous-symbolic")
            self.settings_toggle.set_tooltip_text("Open SENTRY settings and people")

        def _refresh_status(self) -> bool:
            payload, self._sleep_transition_state = resolve_sleep_transition_status(
                read_voice_status(),
                sleep_enabled=self.sleep_enabled,
                transition_state=self._sleep_transition_state,
            )
            state, guidance, identity = voice_status_summary(payload)
            model = voice_indicator_model(payload)
            wake_at = str(payload.get("last_wake_at") or "") or None
            acknowledge = should_acknowledge_wake(self._last_wake_at, wake_at) if self._status_initialized else False
            self.status_orb.present(payload, acknowledge_wake=acknowledge)
            self.state_label.set_text(guidance)
            self.settings_runtime_label.set_text(f"Voice state: {state.replace('_', ' ').title()}")
            self.settings_speaker_label.set_text(identity)
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
            self.sleep_toggle.set_sensitive(not self._busy)
            self.progress.set_fraction(accepted / target if active else 0)
            self.progress.set_text(f"{accepted} of {target}" if active else "No enrollment active")

        def _voice_speed_changed(self, scale) -> None:
            self.voice_speed_value.set_text(f"{scale.get_value():.2f}×")

        def _set_sleep_toggle(self, enabled: bool) -> None:
            self._setting_sleep_programmatically = True
            try:
                self.sleep_toggle.set_active(enabled)
            finally:
                self._setting_sleep_programmatically = False

        def _sleep_toggled(self, switch, _property) -> None:
            if self._setting_sleep_programmatically:
                return
            enabled = bool(switch.get_active())
            previous = self.sleep_enabled
            self._sleep_transition_state = "SLEEPING" if enabled else "STARTING"
            self.sleep_message.set_text(
                "Enabling Sleep…" if enabled else "Waking SENTRY…"
            )
            self._refresh_status()

            def complete(_result: str) -> None:
                self.sleep_enabled = enabled
                if enabled:
                    self._sleep_transition_state = None
                self.sleep_message.set_text(
                    "Sleeping. Wake-word listening is off."
                    if enabled
                    else "Sleep is off. Wake-word listening is available."
                )

            def failed(message: str) -> None:
                self.sleep_enabled = previous
                self._sleep_transition_state = None
                self._set_sleep_toggle(previous)
                self.sleep_message.set_text(f"Sleep setting was not applied: {message}")

            self._run_voice_operation(
                lambda: apply_sleep_preference(config_path, enabled),
                complete,
                failed=failed,
            )

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

        def _save_selected_voice(self, _button) -> None:
            identifier, speed = self._selected_voice_preferences()
            label = self.voice_choice.get_active_text() or identifier
            self.voice_message.set_text(f"Applying {label} at {speed:.2f}×…")

            def complete(restarted: bool) -> None:
                suffix = " The resident listener was reloaded." if restarted else ""
                self.voice_message.set_text(
                    f"Saved {label} at {speed:.2f}×.{suffix}"
                )

            self._run_voice_operation(
                lambda: apply_voice_preferences(config_path, identifier, speed),
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
        def __init__(self):
            super().__init__(application_id="local.sentry.Control", flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

        def do_activate(self):
            window = self.props.active_window
            if window is None:
                window = SentryWindow(self)
            window.close_settings()
            window.present()

    return SentryApplication()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("~/.config/sentry/config.json"))
    args = parser.parse_args(argv)
    try:
        application = build_application(args.config.expanduser())
        return int(application.run([sys.argv[0]]))
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"SENTRY UI failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
