"""Opt-in, metadata-only always-available local SENTRY voice listener."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterator, Protocol

import numpy as np

from .audio_timeline import (
    ActiveUtteranceCapture,
    AudioChunk,
    AudioTimelineGap,
    FrozenUtterance,
    PcmTimeline,
)
from .speech_activity import SpeechActivityGate
from .speaker_context import WakeIdentityCoordinator, unavailable_speaker_envelope
from .vosk_kws import CommandStreamProgress
from .voice import KOKORO_ENGLISH_VOICE_IDS, KOKORO_MAX_SPEED, KOKORO_MIN_SPEED, _terminate_capture_process, normalized_audio_level


class VoiceState(str, Enum):
    DISABLED = "DISABLED"
    SLEEPING = "SLEEPING"
    STARTING = "STARTING"
    LISTENING = "LISTENING"
    WAKE_DETECTED = "WAKE_DETECTED"
    CAPTURING = "CAPTURING"
    FINISHING_REQUEST = "FINISHING_REQUEST"
    TRANSCRIBING = "TRANSCRIBING"
    ARMED = "ARMED"
    AWAITING_OPERATOR_RESPONSE = "AWAITING_OPERATOR_RESPONSE"
    FOLLOWUP_LISTENING = "FOLLOWUP_LISTENING"
    PROCESSING = "PROCESSING"
    SPEAKING = "SPEAKING"


class PcmStream(Protocol):
    def iter_chunks(self, stop_event: threading.Event) -> Iterator[np.ndarray]: ...


class Vad(Protocol):
    def probability(self, samples: np.ndarray) -> float: ...

    def reset(self) -> None: ...


class Transcriber(Protocol):
    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str: ...


class Speaker(Protocol):
    def speak(self, text: str) -> bool: ...


class WakeDetector(Protocol):
    """Dedicated local wake authority; it never receives transcript text."""

    last_result_class: str

    def feed(self, pcm: np.ndarray) -> list[Any]: ...

    def reset(self) -> None: ...


class CommandRecognizer(Protocol):
    """Independent full-vocabulary Vosk stream for post-wake progress only."""

    last_result_class: str
    endpointer_mode: str

    def feed(self, pcm: np.ndarray) -> CommandStreamProgress: ...

    def reset(self) -> None: ...


@dataclass(frozen=True)
class AlwaysOnVoiceConfig:
    always_on_enabled: bool = False
    sleep_enabled: bool = False
    microphone_source: str | None = None
    sample_rate: int = 16_000
    wake_engine: str = "vosk"
    wake_token: str = "sentry"
    vosk_model_path: str | None = None
    vosk_grammar: tuple[str, ...] = ("sentry", "[unk]")
    wake_debounce_ms: int = 1000
    vad_backend: str = "silero_vad"
    # Live office qualification showed that 0.50 can classify a natural
    # utterance as a sub-minimum fragment.  Keep the gate conservative, but
    # admit normal speech before the existing bounded Whisper/wake boundary.
    vad_threshold: float = 0.35
    # Once an explicitly wake-authorized utterance has started, use a lower
    # continuation threshold. Natural speech contains low-energy consonants
    # and brief dips that must not be mistaken for end-of-speech.
    vad_continuation_threshold: float = 0.25
    # Preserve wake-adjacent lead-in before VAD crosses its threshold. Audio
    # remains bounded and in memory only.
    pre_speech_ms: int = 1000
    minimum_speech_ms: int = 250
    end_silence_ms: int = 1500
    endpoint_engine: str = "dual_vosk_streaming"
    command_continuation_idle_ms: int = 5000
    command_stability_recheck_ms: int = 400
    command_trailing_tail_ms: int = 500
    # Compound operator requests may contain several ordered actions. Keep the
    # audio buffer finite and memory-only without truncating natural requests
    # at the former short-command boundary.
    maximum_utterance_seconds: float = 45.0
    timeline_capacity_seconds: float = 50.0
    post_wake_overlap_ms: int = 500
    followup_window_seconds: float = 8.0
    conversation_followup_enabled: bool = True
    conversation_followup_window_seconds: float = 8.0
    conversation_followup_max_turns: int = 2
    action_response_window_seconds: float = 120.0
    wake_identity_refresh_idle_seconds: float = 7200.0
    wake_identity_context_ttl_seconds: float = 7200.0
    wake_identity_camera_duration_seconds: float = 3.0
    wake_identity_join_timeout_seconds: float = 5.0
    post_speech_rearm_ms: int = 500
    whisper_model: str = "tiny.en"
    kokoro_voice: str = "bm_george"
    kokoro_speed: float = 0.9
    base_url: str = "http://127.0.0.1:48174"
    room_id: str = "office"
    effort: str = "medium"
    timeout_seconds: int = 900

    def __post_init__(self) -> None:
        if self.sample_rate != 16_000:
            raise ValueError("always-on voice requires 16 kHz PCM")
        if self.vad_backend != "silero_vad":
            raise ValueError("only silero_vad is supported")
        if not 0 < self.vad_threshold < 1:
            raise ValueError("voice.vad_threshold must be between 0 and 1")
        if not 0 < self.vad_continuation_threshold <= self.vad_threshold:
            raise ValueError("voice.vad_continuation_threshold must be positive and no greater than vad_threshold")
        if self.wake_engine != "vosk":
            raise ValueError("voice.wake_engine must be vosk")
        if _normalize_phrase(self.wake_token) != "sentry":
            raise ValueError("voice.wake_token must be the exact token sentry")
        if self.vosk_grammar != ("sentry", "[unk]"):
            raise ValueError("voice.vosk_grammar must be [sentry, [unk]]")
        if self.wake_debounce_ms < 0:
            raise ValueError("voice.wake_debounce_ms must be non-negative")
        if self.always_on_enabled and not self.vosk_model_path:
            raise ValueError("voice.vosk_model_path is required when always-on voice is enabled")
        if self.pre_speech_ms < 0 or self.minimum_speech_ms <= 0 or self.end_silence_ms <= 0:
            raise ValueError("voice speech timings must be positive")
        if self.endpoint_engine != "dual_vosk_streaming":
            raise ValueError("voice.endpoint_engine must be dual_vosk_streaming")
        if self.command_continuation_idle_ms <= 0:
            raise ValueError("voice.command_continuation_idle_ms must be positive")
        if self.command_stability_recheck_ms <= 0:
            raise ValueError("voice.command_stability_recheck_ms must be positive")
        if not 0 <= self.command_trailing_tail_ms <= 1000:
            raise ValueError("voice.command_trailing_tail_ms must be from 0 through 1000")
        if self.maximum_utterance_seconds <= 0 or self.followup_window_seconds <= 0 or self.conversation_followup_window_seconds <= 0 or self.action_response_window_seconds <= 0 or self.post_speech_rearm_ms < 0:
            raise ValueError("voice duration limits are invalid")
        minimum_timeline = self.maximum_utterance_seconds + (self.pre_speech_ms + self.end_silence_ms) / 1000
        if self.timeline_capacity_seconds < minimum_timeline:
            raise ValueError("voice.timeline_capacity_seconds is too short for one maximum utterance")
        if self.post_wake_overlap_ms < 0 or self.post_wake_overlap_ms > 2_000:
            raise ValueError("voice.post_wake_overlap_ms must be from 0 through 2000")
        if self.conversation_followup_max_turns < 0:
            raise ValueError("voice.conversation_followup_max_turns must be non-negative")
        if min(
            self.wake_identity_refresh_idle_seconds,
            self.wake_identity_context_ttl_seconds,
            self.wake_identity_camera_duration_seconds,
            self.wake_identity_join_timeout_seconds,
        ) <= 0:
            raise ValueError("voice wake identity timings must be positive")
        if self.wake_identity_camera_duration_seconds > self.wake_identity_join_timeout_seconds:
            raise ValueError("voice wake identity camera duration cannot exceed join timeout")
        if not self.whisper_model or not self.base_url.startswith("http://127.0.0.1"):
            raise ValueError("voice must use local state API and a Whisper model")
        if self.kokoro_voice not in KOKORO_ENGLISH_VOICE_IDS:
            raise ValueError("voice.kokoro_voice must be a supported English Kokoro voice")
        if not KOKORO_MIN_SPEED <= self.kokoro_speed <= KOKORO_MAX_SPEED:
            raise ValueError(
                f"voice.kokoro_speed must be from {KOKORO_MIN_SPEED:.2f} "
                f"through {KOKORO_MAX_SPEED:.2f}"
            )

    @classmethod
    def from_mapping(cls, values: dict[str, Any] | None) -> "AlwaysOnVoiceConfig":
        values = values or {}
        if not isinstance(values, dict):
            raise ValueError("voice must be an object")
        grammar = values.get("vosk_grammar", ["sentry", "[unk]"])
        if not isinstance(grammar, list) or any(not isinstance(item, str) for item in grammar):
            raise ValueError("voice.vosk_grammar must be a string list")
        source = values.get("microphone_source")
        if source is not None and not isinstance(source, str):
            raise ValueError("voice.microphone_source must be a string or null")
        return cls(
            always_on_enabled=bool(values.get("always_on_enabled", False)),
            sleep_enabled=bool(values.get("sleep_enabled", False)),
            microphone_source=source,
            sample_rate=int(values.get("sample_rate", 16_000)),
            wake_engine=str(values.get("wake_engine", "vosk")),
            wake_token=str(values.get("wake_token", "sentry")),
            vosk_model_path=(str(values["vosk_model_path"]) if values.get("vosk_model_path") is not None else None),
            vosk_grammar=tuple(grammar),
            wake_debounce_ms=int(values.get("wake_debounce_ms", 1000)),
            vad_backend=str(values.get("vad_backend", "silero_vad")),
            vad_threshold=float(values.get("vad_threshold", 0.35)),
            vad_continuation_threshold=float(values.get("vad_continuation_threshold", 0.25)),
            pre_speech_ms=int(values.get("pre_speech_ms", 1000)),
            minimum_speech_ms=int(values.get("minimum_speech_ms", 250)),
            end_silence_ms=int(values.get("end_silence_ms", 1500)),
            endpoint_engine=str(values.get("endpoint_engine", "dual_vosk_streaming")),
            command_continuation_idle_ms=int(values.get("command_continuation_idle_ms", 5000)),
            command_stability_recheck_ms=int(values.get("command_stability_recheck_ms", 400)),
            command_trailing_tail_ms=int(values.get("command_trailing_tail_ms", 500)),
            maximum_utterance_seconds=float(values.get("maximum_utterance_seconds", 45.0)),
            timeline_capacity_seconds=float(values.get("timeline_capacity_seconds", 50.0)),
            post_wake_overlap_ms=int(values.get("post_wake_overlap_ms", 500)),
            followup_window_seconds=float(values.get("followup_window_seconds", 8.0)),
            conversation_followup_enabled=bool(values.get("conversation_followup_enabled", True)),
            conversation_followup_window_seconds=float(values.get("conversation_followup_window_seconds", 8.0)),
            conversation_followup_max_turns=int(values.get("conversation_followup_max_turns", 2)),
            action_response_window_seconds=float(values.get("action_response_window_seconds", 120.0)),
            wake_identity_refresh_idle_seconds=float(values.get("wake_identity_refresh_idle_seconds", 7200.0)),
            wake_identity_context_ttl_seconds=float(values.get("wake_identity_context_ttl_seconds", 7200.0)),
            wake_identity_camera_duration_seconds=float(values.get("wake_identity_camera_duration_seconds", 3.0)),
            wake_identity_join_timeout_seconds=float(values.get("wake_identity_join_timeout_seconds", 5.0)),
            post_speech_rearm_ms=int(values.get("post_speech_rearm_ms", 500)),
            whisper_model=str(values.get("whisper_model", "tiny.en")),
            kokoro_voice=str(values.get("kokoro_voice", "bm_george")),
            kokoro_speed=float(values.get("kokoro_speed", 0.9)),
            base_url=str(values.get("base_url", "http://127.0.0.1:48174")),
            room_id=str(values.get("room_id", "office")),
            effort=str(values.get("effort", "medium")),
            timeout_seconds=int(values.get("timeout_seconds", 900)),
        )


def _normalize_phrase(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.lower()).split())


class PipeWirePcmStream:
    """One local PipeWire process yielding fixed in-memory PCM chunks."""

    def __init__(self, *, source: str | None = None, executable: str | None = None, sample_rate: int = 16_000, chunk_samples: int = 512) -> None:
        self.source = source
        self.executable = executable or shutil.which("pw-record")
        self.sample_rate = sample_rate
        self.chunk_samples = chunk_samples
        if not self.executable:
            raise RuntimeError("pw-record was not found")

    def iter_chunks(self, stop_event: threading.Event) -> Iterator[np.ndarray]:
        command = [self.executable, "--rate", str(self.sample_rate), "--channels", "1", "--format", "s16"]
        if self.source:
            command.extend(["--target", self.source])
        command.append("-")
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        if process.stdout is None:
            _terminate_capture_process(process)
            raise RuntimeError("pw-record did not expose PCM stdout")
        chunk_bytes = self.chunk_samples * 2
        pending = bytearray()
        try:
            while not stop_event.is_set():
                data = process.stdout.read(chunk_bytes - len(pending))
                if not data:
                    if process.poll() is not None:
                        if pending:
                            raise RuntimeError("pw-record ended with an incomplete PCM chunk")
                        detail = (process.stderr.read() if process.stderr else b"").decode("utf-8", errors="replace")
                        raise RuntimeError(f"pw-record ended unexpectedly: {detail[-500:]}")
                    continue
                pending.extend(data)
                if len(pending) < chunk_bytes:
                    continue
                yield np.frombuffer(bytes(pending), dtype=np.int16).astype(np.float32) / 32768.0
                pending.clear()
        finally:
            _terminate_capture_process(process)


class SileroVad:
    """Local package-model VAD with no network calls or recorded audio."""

    def __init__(self) -> None:
        try:
            from silero_vad import load_silero_vad
            import torch
        except ImportError as exc:  # pragma: no cover - deployment dependent
            raise RuntimeError("silero-vad is required for always-on voice") from exc
        torch.set_num_threads(1)
        self._torch = torch
        self._model = load_silero_vad()
        self.reset()

    def reset(self) -> None:
        self._model.reset_states()

    def probability(self, samples: np.ndarray) -> float:
        if samples.shape != (512,):
            raise ValueError("Silero VAD requires 512-sample 16 kHz chunks")
        with self._torch.no_grad():
            result = self._model(self._torch.from_numpy(np.asarray(samples, dtype=np.float32)), 16_000)
        return float(result.item())


class VoiceDiagnostics:
    """Ephemeral metadata-only user-runtime status for operator diagnostics."""

    def __init__(self, path: str | Path | None = None) -> None:
        root = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "sentry"
        self.path = Path(path) if path else root / "voice.json"
        self.payload: dict[str, Any] = {"state": VoiceState.DISABLED.value, "vad_healthy": False}

    def update(self, **values: Any) -> None:
        self.payload.update(values)
        self.payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.payload, sort_keys=True) + "\n", encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(self.path)

    def increment(self, key: str, amount: int = 1, **values: Any) -> None:
        self.update(**{key: int(self.payload.get(key, 0)) + amount}, **values)

    def record_dispatch_latency(self, latency_ms: float) -> None:
        """Keep a bounded metadata-only latency sample history for qualification."""
        samples = list(self.payload.get("command_dispatch_latencies_ms", []))
        samples.append(round(float(latency_ms), 3))
        self.update(
            command_dispatch_latencies_ms=samples[-64:],
            last_command_dispatch_latency_ms=samples[-1],
        )

    def record_answer_latency(self, latency_ms: float) -> None:
        """Record STT-complete through grounded-answer latency, never transcript text."""
        samples = list(self.payload.get("conversation_answer_latencies_ms", []))
        samples.append(round(float(latency_ms), 3))
        self.update(
            conversation_answer_latencies_ms=samples[-64:],
            last_conversation_answer_latency_ms=samples[-1],
        )


class AlwaysOnVoiceLoop:
    """Finite-state controller for wake-required turns and bounded follow-ups."""

    def __init__(
        self,
        config: AlwaysOnVoiceConfig,
        *,
        stream: PcmStream,
        vad: Vad,
        wake_detector: WakeDetector,
        command_recognizer: CommandRecognizer,
        transcriber: Transcriber,
        speaker: Speaker,
        ask_fn: Callable[..., dict[str, Any]],
        action_presentation_completed_fn: Callable[..., dict[str, Any]] | None = None,
        action_presentation_failed_fn: Callable[..., dict[str, Any]] | None = None,
        action_response_expired_fn: Callable[..., dict[str, Any]] | None = None,
        diagnostics: VoiceDiagnostics | None = None,
        speech_activity: SpeechActivityGate | None = None,
        identity_coordinator: WakeIdentityCoordinator | None = None,
        wake_chime_fn: Callable[[], bool] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config
        self.stream = stream
        self.vad = vad
        self.wake_detector = wake_detector
        self.command_recognizer = command_recognizer
        self.transcriber = transcriber
        self.speaker = speaker
        self.ask_fn = ask_fn
        self.action_presentation_completed_fn = action_presentation_completed_fn
        self.action_presentation_failed_fn = action_presentation_failed_fn
        self.action_response_expired_fn = action_response_expired_fn
        self.diagnostics = diagnostics or VoiceDiagnostics()
        self.speech_activity = speech_activity or SpeechActivityGate()
        self.identity_coordinator = identity_coordinator
        self.wake_chime_fn = wake_chime_fn
        self.clock = clock
        self.state = VoiceState.DISABLED
        self._timeline = PcmTimeline(
            capacity_samples=int(config.timeline_capacity_seconds * config.sample_rate)
        )
        self._active_capture: ActiveUtteranceCapture | None = None
        self._speech_epoch_start_sample: int | None = None
        self._last_voice_sample: int | None = None
        self._speech_samples = 0
        self._silence_samples = 0
        self._command_stream_active = False
        self._command_stream_end_sample: int | None = None
        self._command_stream_started_at: float | None = None
        self._last_command_progress_at: float | None = None
        self._last_command_progress_sample: int | None = None
        self._command_close_candidate_at: float | None = None
        self._armed_until: float | None = None
        self._focus_deadline: float | None = None
        self._focus_pending = False
        self._focus_id: str | None = None
        self._followup_turn_count = 0
        self._scheduled_action_response_id: str | None = None
        self._action_response_authorization_id: str | None = None
        self._action_response_deadline: float | None = None
        self._action_response_target_summary: str | None = None
        self._rearm_until = 0.0
        self._last_speech_at: float | None = None
        self._last_completed_speech_at: float | None = None
        self._speech_suppressed = False
        # A focus session owns one RAM-only conversational context. It is not
        # written to diagnostics and disappears on listener restart.
        self._conversation_id: str | None = None

    def _set_state(self, state: VoiceState, **extra: Any) -> None:
        self.state = state
        vad_healthy = bool(extra.pop("vad_healthy", True))
        self.diagnostics.update(state=state.value, vad_healthy=vad_healthy, **extra)

    def _reset_capture(self, *, clear_timeline: bool = False) -> None:
        self._active_capture = None
        self._speech_epoch_start_sample = None
        self._last_voice_sample = None
        self._speech_samples = 0
        self._silence_samples = 0
        self._reset_command_stream("capture_reset")
        self._last_speech_at = None
        if clear_timeline:
            self._timeline.clear_audio()
        self.vad.reset()

    def _reset_wake_detector(self, reason: str) -> None:
        self.wake_detector.reset()
        self.diagnostics.update(wake_engine="vosk", wake_engine_state="listening", last_wake_reset_reason=reason)

    def _reset_command_stream(self, reason: str) -> None:
        if self._command_stream_active:
            try:
                self.command_recognizer.reset()
            except Exception as exc:  # noqa: BLE001 - cleanup remains best effort
                self.diagnostics.update(last_error=f"command_vosk_reset: {type(exc).__name__}")
            self.diagnostics.update(
                command_stream_active=False,
                command_stream_reset_reason=reason,
                command_close_candidate=False,
            )
        self._command_stream_active = False
        self._command_stream_end_sample = None
        self._command_stream_started_at = None
        self._last_command_progress_at = None
        self._last_command_progress_sample = None
        self._command_close_candidate_at = None

    def _discard_to_listening(self, *, reason: str | None = None) -> None:
        self._reset_capture(clear_timeline=True)
        self._set_state(VoiceState.LISTENING, last_segment_outcome=reason)

    def _focus_active(self) -> bool:
        return self._focus_deadline is not None

    def _action_response_active(self) -> bool:
        return self._action_response_authorization_id is not None

    def _clear_action_response(self, reason: str) -> None:
        was_active = self._action_response_active() or self._scheduled_action_response_id is not None
        self._scheduled_action_response_id = None
        self._action_response_authorization_id = None
        self._action_response_deadline = None
        self._action_response_target_summary = None
        if was_active:
            self.diagnostics.update(
                action_response_active=False,
                action_response_authorization_id=None,
                action_response_deadline=None,
                action_response_close_reason=reason,
            )

    def _schedule_action_response_after_speech(
        self, authorization_id: str, *, target_summary: str | None = None,
    ) -> None:
        self._close_focus("action_dialogue")
        self._scheduled_action_response_id = authorization_id
        self._action_response_target_summary = target_summary
        self.diagnostics.update(
            action_response_active=False,
            action_response_authorization_id=authorization_id,
            action_response_deadline=None,
            action_response_close_reason=None,
        )

    def _open_scheduled_action_response(self) -> None:
        authorization_id = self._scheduled_action_response_id
        if authorization_id is None:
            return
        if self.action_presentation_completed_fn is None:
            if self.action_presentation_failed_fn is not None:
                try:
                    self.action_presentation_failed_fn(authorization_id, surface="kokoro_voice")
                except Exception:  # noqa: BLE001 - action remains non-actionable
                    pass
            self._clear_action_response("presentation_callback_unavailable")
            self._set_state(VoiceState.LISTENING, last_segment_outcome="action_presentation_failed")
            return
        try:
            pending = self.action_presentation_completed_fn(
                authorization_id,
                surface="kokoro_voice",
                response_window_seconds=int(self.config.action_response_window_seconds),
            )
        except Exception as exc:  # noqa: BLE001 - never leave an action ambiguously actionable
            if self.action_presentation_failed_fn is not None:
                try:
                    self.action_presentation_failed_fn(authorization_id, surface="kokoro_voice")
                except Exception:  # noqa: BLE001 - original error remains diagnostic authority
                    pass
            self._clear_action_response("presentation_callback_failed")
            self.diagnostics.update(last_error=f"action_presentation: {type(exc).__name__}")
            self._set_state(VoiceState.LISTENING, last_segment_outcome="action_presentation_failed")
            return
        self._scheduled_action_response_id = None
        self._action_response_authorization_id = authorization_id
        self._action_response_deadline = self.clock() + self.config.action_response_window_seconds
        self.diagnostics.increment(
            "action_response_windows_opened",
            action_response_active=True,
            action_response_authorization_id=authorization_id,
            action_response_deadline=round(self._action_response_deadline, 3),
            action_response_target_summary=str(pending.get("target_summary") or self._action_response_target_summary or ""),
            action_response_close_reason=None,
        )
        self._set_state(
            VoiceState.AWAITING_OPERATOR_RESPONSE,
            last_segment_outcome="awaiting_operator_response",
        )

    def _expire_action_response(self, reason: str = "response_timeout") -> None:
        authorization_id = self._action_response_authorization_id
        if authorization_id and self.action_response_expired_fn is not None:
            try:
                self.action_response_expired_fn(authorization_id, reason=reason)
            except Exception as exc:  # noqa: BLE001 - expiration remains fail closed
                self.diagnostics.update(last_error=f"action_expiry: {type(exc).__name__}")
        self._clear_action_response(reason)
        self._reset_wake_detector("action_response_timeout")
        self._discard_to_listening(reason=f"action_response_{reason}")

    def _begin_wake_conversation(self) -> None:
        """Start a new RAM-only context only for an explicit Vosk wake."""
        self._close_focus("explicit_new_wake")
        self._conversation_id = f"always-on-{uuid.uuid4()}"
        self._followup_turn_count = 0
        if self.identity_coordinator is not None:
            epoch_id, started = self.identity_coordinator.begin_explicit_wake()
            identity_status = self.identity_coordinator.diagnostics()
            identity_status.update(
                speaker_context_conversation_epoch=epoch_id,
                speaker_context_preflight_active=started,
            )
            self.diagnostics.update(**identity_status)

    def _close_focus(self, reason: str) -> None:
        was_active = self._focus_active() or self._focus_pending or self._focus_id is not None
        self._focus_deadline = None
        self._focus_pending = False
        self._focus_id = None
        if was_active:
            self.diagnostics.update(
                conversation_focus_active=False,
                followup_turn_index=self._followup_turn_count,
                followup_turn_limit=self.config.conversation_followup_max_turns,
                followup_window_deadline=None,
                followup_close_reason=reason,
            )

    def _schedule_focus_after_speech(self) -> None:
        if not self.config.conversation_followup_enabled or self.config.conversation_followup_max_turns <= 0:
            self._close_focus("disabled")
            return
        self._focus_pending = True
        self.diagnostics.update(
            conversation_focus_active=False,
            followup_turn_index=self._followup_turn_count,
            followup_turn_limit=self.config.conversation_followup_max_turns,
            followup_close_reason=None,
        )

    def _open_scheduled_focus(self) -> None:
        if not self._focus_pending:
            return
        self._focus_pending = False
        self._focus_id = f"focus-{uuid.uuid4()}"
        self._focus_deadline = self.clock() + self.config.conversation_followup_window_seconds
        self.diagnostics.increment(
            "followup_windows_opened",
            conversation_focus_active=True,
            conversation_focus_id=self._focus_id,
            followup_turn_index=self._followup_turn_count,
            followup_turn_limit=self.config.conversation_followup_max_turns,
            followup_window_opened_at=datetime.now(timezone.utc).isoformat(),
            followup_window_deadline=round(self._focus_deadline, 3),
            followup_close_reason=None,
        )
        self._set_state(VoiceState.FOLLOWUP_LISTENING, last_segment_outcome="followup_listening")

    def _promote_capture(
        self,
        chunk: AudioChunk,
        *,
        mode: str,
        wake_event_id: str | None = None,
        wake_detected_sample: int | None = None,
        wake_token_end_sample: int | None = None,
        command_speech_seen: bool = False,
    ) -> None:
        if self._active_capture is not None:
            return
        pre_speech_samples = int(self.config.pre_speech_ms * self.config.sample_rate / 1000)
        anchor = (
            self._speech_epoch_start_sample
            if self._speech_epoch_start_sample is not None
            else (wake_detected_sample if wake_detected_sample is not None else chunk.start_sample)
        )
        capture_start = max(self._timeline.earliest_sample, anchor - pre_speech_samples)
        self._active_capture = ActiveUtteranceCapture.promote(
            self._timeline,
            capture_id=str(uuid.uuid4()),
            wake_event_id=wake_event_id,
            capture_mode=mode,
            capture_start_sample=capture_start,
            capture_end_sample=chunk.end_sample,
            wake_detected_sample=wake_detected_sample,
            wake_token_end_sample=wake_token_end_sample,
            speech_epoch_start_sample=self._speech_epoch_start_sample,
            last_voice_sample=self._last_voice_sample,
            command_speech_seen=command_speech_seen,
        )
        self.diagnostics.update(
            stream_sequence=self._timeline.stream_sequence,
            stream_end_sample=self._timeline.stream_end_sample,
            wake_detected_sample=wake_detected_sample,
            speech_epoch_start_sample=self._speech_epoch_start_sample,
            capture_start_sample=capture_start,
            capture_end_sample=chunk.end_sample,
            capture_duration_ms=round(
                (chunk.end_sample - capture_start) * 1000 / self.config.sample_rate
            ),
            capture_chunk_count=self._active_capture.chunk_count,
            capture_sample_count=self._active_capture.sample_count,
            capture_gap_count=0,
            capture_mode=mode,
            capture_start_reason=("speech_epoch_history" if self._speech_epoch_start_sample is not None else "wake_preroll"),
            endpoint_reason=None,
        )
        self._start_command_stream()
        self._set_state(VoiceState.CAPTURING, last_segment_outcome=f"{mode}_capturing")

    @staticmethod
    def _to_int16(pcm: np.ndarray) -> np.ndarray:
        return np.clip(np.asarray(pcm, dtype=np.float32) * 32767.0, -32768, 32767).astype(np.int16)

    def _start_command_stream(self) -> None:
        capture = self._active_capture
        if capture is None:
            return
        self.command_recognizer.reset()
        self._command_stream_active = True
        self._command_stream_end_sample = capture.capture_start_sample
        self._command_stream_started_at = self.clock()
        self._last_command_progress_at = self._last_speech_at
        self._last_command_progress_sample = capture.capture_start_sample
        self._command_close_candidate_at = None
        audio = capture.view()
        offset = 0
        while offset < audio.size:
            end = min(audio.size, offset + 512)
            self._feed_command_stream(
                self._to_int16(audio[offset:end]),
                start_sample=capture.capture_start_sample + offset,
                end_sample=capture.capture_start_sample + end,
            )
            offset = end
        self.diagnostics.update(
            command_stream_active=True,
            command_stream_start_sample=capture.capture_start_sample,
            command_stream_end_sample=self._command_stream_end_sample,
            command_stream_backfill_samples=audio.size,
            command_recognizer_endpointer_mode=self.command_recognizer.endpointer_mode,
        )

    def _feed_command_stream(
        self,
        pcm: np.ndarray,
        *,
        start_sample: int,
        end_sample: int,
    ) -> None:
        if not self._command_stream_active:
            return
        if self._command_stream_end_sample != start_sample:
            raise AudioTimelineGap(
                "command recognizer chronology discontinuity: "
                f"expected {self._command_stream_end_sample}, received {start_sample}"
            )
        try:
            progress = self.command_recognizer.feed(pcm)
        except Exception as exc:  # noqa: BLE001 - command authority must fail closed
            self.diagnostics.update(
                command_stream_state="degraded",
                last_command_transcription_status="unavailable",
                last_error=f"command_vosk: {type(exc).__name__}",
            )
            raise
        self._command_stream_end_sample = end_sample
        if progress.progressed:
            self._last_command_progress_at = self.clock()
            self._last_command_progress_sample = end_sample
            self._cancel_close_candidate("stream_progress")
        processing = list(self.diagnostics.payload.get("command_stream_processing_ms", []))
        processing.append(round(progress.processing_ms, 3))
        self.diagnostics.update(
            command_stream_state="active",
            command_stream_result_class=progress.result_class,
            command_stream_progress_observed=bool(progress.progressed),
            command_stream_finalized_segment_count=progress.finalized_segment_count,
            command_stream_partial_word_count=progress.partial_word_count,
            command_stream_observed_word_count=progress.observed_word_count,
            command_stream_end_sample=end_sample,
            command_stream_processing_ms=processing[-128:],
        )

    def _cancel_close_candidate(self, reason: str) -> None:
        if self._command_close_candidate_at is not None:
            self.diagnostics.increment(
                "command_close_candidate_cancellations",
                command_close_candidate=False,
                command_close_cancel_reason=reason,
            )
            if self._active_capture is not None:
                self._set_state(
                    VoiceState.CAPTURING,
                    last_segment_outcome="command_continuation_resumed",
                )
        self._command_close_candidate_at = None

    def _evaluate_command_boundary(self, now: float) -> None:
        capture = self._active_capture
        if capture is None or not self._command_stream_active:
            return
        activity_times = [value for value in (self._last_speech_at, self._last_command_progress_at, self._command_stream_started_at) if value is not None]
        last_activity = max(activity_times) if activity_times else now
        idle_seconds = now - last_activity
        required_idle = self.config.command_continuation_idle_ms / 1000.0
        if idle_seconds < required_idle:
            self._cancel_close_candidate("activity_resumed")
            return
        if self._command_close_candidate_at is None:
            self._command_close_candidate_at = now
            self.diagnostics.increment(
                "command_close_candidates",
                command_close_candidate=True,
                command_idle_ms=round(idle_seconds * 1000, 3),
            )
            self._set_state(
                VoiceState.FINISHING_REQUEST,
                last_segment_outcome="streaming_idle_candidate",
            )
            return
        recheck_seconds = self.config.command_stability_recheck_ms / 1000.0
        if now - self._command_close_candidate_at < recheck_seconds:
            return
        self.diagnostics.update(
            command_close_candidate=False,
            command_stability_recheck_ms=self.config.command_stability_recheck_ms,
        )
        self._complete_segment(endpoint_reason="streaming_command_idle")

    def _fail_active_capture(self, reason: str) -> None:
        gap_count = self._active_capture.gap_count if self._active_capture is not None else 1
        self.diagnostics.update(
            capture_gap_count=gap_count,
            endpoint_reason=reason,
            last_command_transcription_status="unavailable",
            last_segment_outcome=reason,
        )
        self._close_focus("capture_failure")
        if self._action_response_active():
            self._expire_action_response("capture_failure")
            return
        self._discard_to_listening(reason=reason)

    def _complete_segment(self, *, endpoint_reason: str = "silence") -> None:
        capture = self._active_capture
        if capture is None:
            return
        speech_seconds = self._speech_samples / self.config.sample_rate
        self._last_completed_speech_at = self._last_speech_at
        source_end_sample = capture.current_end_sample
        activity_samples = [
            value
            for value in (
                capture.last_voice_sample,
                self._last_command_progress_sample,
                capture.wake_detected_sample,
            )
            if value is not None
        ]
        if endpoint_reason == "maximum_duration" or not activity_samples:
            freeze_end_sample = source_end_sample
        else:
            tail_samples = int(
                self.config.command_trailing_tail_ms * self.config.sample_rate / 1000
            )
            freeze_end_sample = min(source_end_sample, max(activity_samples) + tail_samples)
            freeze_end_sample = max(capture.capture_start_sample, freeze_end_sample)
        try:
            frozen = capture.freeze(endpoint_reason, end_sample=freeze_end_sample)
        except AudioTimelineGap:
            self._fail_active_capture("audio_gap")
            return
        finalized_segment_count = int(
            self.diagnostics.payload.get("command_stream_finalized_segment_count", 0)
        )
        observed_word_count = int(
            self.diagnostics.payload.get("command_stream_observed_word_count", 0)
        )
        self._reset_command_stream("command_finalized")
        self._active_capture = None
        self._timeline.clear_audio()
        self._speech_epoch_start_sample = None
        self._last_voice_sample = None
        self._speech_samples = 0
        self._silence_samples = 0
        self._last_speech_at = None
        self.vad.reset()
        self.diagnostics.update(
            capture_end_sample=frozen.capture_end_sample,
            capture_source_end_sample=frozen.source_end_sample,
            capture_duration_ms=round(frozen.sample_count * 1000 / self.config.sample_rate),
            capture_source_duration_ms=round(
                (frozen.source_end_sample - frozen.capture_start_sample)
                * 1000
                / self.config.sample_rate
            ),
            trailing_idle_trimmed_ms=round(
                frozen.trailing_samples_trimmed * 1000 / self.config.sample_rate
            ),
            capture_chunk_count=frozen.chunk_count,
            capture_sample_count=frozen.sample_count,
            capture_gap_count=frozen.gap_count,
            capture_mode=frozen.capture_mode,
            endpoint_reason=frozen.endpoint_reason,
            whisper_input_duration_ms=round(frozen.sample_count * 1000 / self.config.sample_rate),
            command_stream_finalized_segment_count=finalized_segment_count,
            command_stream_observed_word_count=observed_word_count,
        )
        if endpoint_reason == "maximum_duration":
            self._close_focus("capture_failure")
            if self._action_response_active():
                self._expire_action_response("maximum_duration")
            self._set_state(
                VoiceState.SPEAKING,
                last_segment_outcome="maximum_duration",
                last_command_transcription_status="truncated",
            )
            self.speaker.speak(
                "That request was too long for me to capture safely. Please shorten it and try again."
            )
            self._rearm_until = self.clock() + self.config.post_speech_rearm_ms / 1000
            self._reset_wake_detector("maximum_duration")
            return
        if frozen.capture_mode == "wake_inline":
            self._handle_wake_segment(frozen)
            return
        if speech_seconds * 1000 < self.config.minimum_speech_ms:
            if self._action_response_active():
                self._expire_action_response("unusable_capture")
                return
            if self._focus_active():
                self._close_focus("capture_failure")
                self._discard_to_listening(reason="followup_too_short")
                return
            self._set_state(VoiceState.ARMED if self._armed_until else VoiceState.LISTENING, last_segment_outcome="too_short")
            return
        if frozen.capture_mode == "action_response" and self._action_response_active():
            self._transcribe_action_response(frozen.pcm)
            return
        if self._focus_active():
            self._transcribe_followup(frozen.pcm, focus=True)
            return
        if frozen.capture_mode == "armed_followup" and self._armed_until is not None:
            self._transcribe_followup(frozen.pcm, focus=False)
            return
        self._discard_to_listening(reason="capture_without_authority")

    def _transcribe_followup(self, audio: np.ndarray, *, focus: bool) -> None:
        self._set_state(
            VoiceState.TRANSCRIBING,
            last_command_audio_duration_ms=round(audio.size * 1000 / self.config.sample_rate),
            stt_start_sample=None,
            transcription_view="full_followup",
            transcription_attempt_count=1,
        )
        try:
            transcript = self.transcriber.transcribe(audio, self.config.sample_rate)
        except Exception as exc:  # noqa: BLE001 - keep listener alive after STT fault
            if focus:
                self._close_focus("capture_failure")
            self._discard_to_listening(reason="whisper_failed")
            self.diagnostics.update(last_error=f"whisper: {type(exc).__name__}")
            return
        transcript = " ".join(str(transcript).split())
        if focus:
            transcript = self._strip_optional_wake_token(transcript)
        if not transcript:
            if focus:
                self._close_focus("capture_failure")
            self._discard_to_listening(reason="no_transcript")
            return
        self._armed_until = None
        self._dispatch_command(transcript, is_followup=focus)

    def _transcribe_action_response(self, audio: np.ndarray) -> None:
        self._set_state(
            VoiceState.TRANSCRIBING,
            last_command_audio_duration_ms=round(audio.size * 1000 / self.config.sample_rate),
            stt_start_sample=None,
            transcription_view="action_response",
            transcription_attempt_count=1,
        )
        try:
            transcript = " ".join(str(self.transcriber.transcribe(audio, self.config.sample_rate)).split())
        except Exception as exc:  # noqa: BLE001 - pending action must remain fail closed
            self._expire_action_response("whisper_failure")
            self.diagnostics.update(last_error=f"whisper: {type(exc).__name__}")
            return
        if not transcript:
            self._expire_action_response("unusable_capture")
            return
        self._dispatch_command(transcript, is_followup=False, is_action_response=True)

    @staticmethod
    def _command_after_wake(transcript: str) -> str:
        match = re.search(r"\bsentry\b(?P<command>.*)$", transcript, flags=re.IGNORECASE)
        if not match:
            return ""
        return re.sub(r"^[\s,;:!?.-]+", "", match.group("command")).strip()

    @staticmethod
    def _strip_optional_wake_token(transcript: str) -> str:
        """A repeated wake token inside focus remains one follow-up request."""
        return re.sub(r"^\s*sentry\b[\s,;:!?.-]*", "", transcript, flags=re.IGNORECASE).strip()

    def _handle_wake_segment(self, frozen: FrozenUtterance) -> None:
        """Extract one command from one immutable Vosk-authorized capture."""
        full_audio = frozen.pcm
        self._set_state(
            VoiceState.TRANSCRIBING,
            last_command_audio_duration_ms=round(full_audio.size * 1000 / self.config.sample_rate),
            stt_start_sample=frozen.capture_start_sample,
            post_wake_duration_ms=(
                round(
                    (frozen.capture_end_sample - (frozen.wake_token_end_sample or frozen.wake_detected_sample or frozen.capture_start_sample))
                    * 1000
                    / self.config.sample_rate
                )
            ),
            command_boundary="shared_timeline",
            transcription_view="full_utterance",
            transcription_attempt_count=1,
        )
        try:
            transcript = " ".join(str(self.transcriber.transcribe(full_audio, self.config.sample_rate)).split())
        except Exception as exc:  # noqa: BLE001
            self._enter_armed("whisper_failed_after_wake", error=f"whisper: {type(exc).__name__}")
            return
        command = self._command_after_wake(transcript)
        if command:
            self.diagnostics.update(command_extraction_mode="full_transcript_after_wake_token")
        elif re.fullmatch(r"\s*sentry[\s,;:!?.-]*", transcript, flags=re.IGNORECASE):
            self._enter_armed("wake_only_or_command_unavailable")
            return
        elif transcript and frozen.command_speech_seen:
            # Vosk already established the wake. Batch Whisper is command STT,
            # not a second wake authority, and therefore need not rediscover
            # the token in a clearly non-empty post-wake command capture.
            command = transcript
            self.diagnostics.update(command_extraction_mode="vosk_authorized_full_transcript")
        if not command:
            self._enter_armed("wake_only_or_command_unavailable")
            return
        self.diagnostics.update(last_command_transcription_status="usable")
        self._dispatch_command(command, is_followup=False)

    def _enter_armed(self, reason: str, *, error: str | None = None) -> None:
        self._armed_until = self.clock() + self.config.followup_window_seconds
        values: dict[str, Any] = {"last_segment_outcome": reason, "last_command_transcription_status": "unavailable"}
        if error:
            values["last_error"] = error
        self._set_state(VoiceState.ARMED, **values)

    def _dispatch_command(
        self, command: str, *, is_followup: bool,
        is_action_response: bool = False,
    ) -> None:
        if self._last_completed_speech_at is not None:
            self.diagnostics.record_dispatch_latency((self.clock() - self._last_completed_speech_at) * 1000)
        self._last_completed_speech_at = None
        command_dispatch_count = int(self.diagnostics.payload.get("command_dispatches", 0)) + 1
        self.diagnostics.update(
            command_dispatches=command_dispatch_count,
            command_dispatch_count=command_dispatch_count,
        )
        self._set_state(VoiceState.PROCESSING, last_command_outcome="processing")
        if self.identity_coordinator is not None:
            self.identity_coordinator.record_accepted_user_utterance()
            speaker_context = self.identity_coordinator.current_envelope(wait_for_preflight=True)
            self.diagnostics.update(**self.identity_coordinator.diagnostics())
        else:
            speaker_context = unavailable_speaker_envelope()
        answer_started_at = self.clock()
        try:
            response = self.ask_fn(
                command,
                base_url=self.config.base_url,
                room_id=self.config.room_id,
                effort=self.config.effort,
                timeout_seconds=self.config.timeout_seconds,
                source_surface="always_on_voice",
                conversation_id=self._conversation_id,
                speaker_context=speaker_context,
            )
        except Exception as exc:  # noqa: BLE001
            self._reset_wake_detector("ask_failed")
            self._close_focus("capture_failure")
            if is_action_response and self._action_response_active():
                self._expire_action_response("agent_failure")
                self.diagnostics.update(last_error=f"ask: {type(exc).__name__}")
                return
            self._discard_to_listening(reason="ask_failed")
            self.diagnostics.update(last_error=f"ask: {type(exc).__name__}")
            return
        self.diagnostics.record_answer_latency((self.clock() - answer_started_at) * 1000)
        answer = response.get("answer") if isinstance(response, dict) else None
        luna_invocations = int(response.get("luna_invocations", 0)) if isinstance(response, dict) else 0
        action_dialogue = response.get("action_dialogue") if isinstance(response, dict) else None
        action_authorization_id = (
            str(action_dialogue.get("authorization_id"))
            if isinstance(action_dialogue, dict) and action_dialogue.get("pending") and action_dialogue.get("authorization_id")
            else None
        )
        if isinstance(response, dict):
            # Host-owned confirmation/status handlers intentionally bypass
            # Codex and omit thread metrics.  Do not let an absent field erase
            # the last observed persistent-thread state.
            codex_status: dict[str, Any] = {}
            if "thread_id" in response:
                codex_status["codex_thread_active"] = bool(response.get("thread_id"))
            if "session_resumed" in response:
                codex_status["codex_session_resumed"] = bool(response.get("session_resumed"))
            if "context_utilization" in response:
                codex_status["codex_context_utilization"] = response.get("context_utilization")
            if "auto_compact_token_limit" in response:
                codex_status["codex_auto_compact_token_limit"] = response.get("auto_compact_token_limit")
            if "compactions_observed" in response:
                codex_status["codex_compactions_observed"] = response.get("compactions_observed", 0)
            if codex_status:
                self.diagnostics.update(**codex_status)
        if not isinstance(answer, str) or not answer.strip():
            self._reset_wake_detector("no_answer")
            self._close_focus("capture_failure")
            if is_action_response and self._action_response_active():
                self._expire_action_response("agent_failure")
                return
            self._discard_to_listening(reason="no_answer")
            return
        self._set_state(VoiceState.SPEAKING, last_command_outcome="answered", last_command_luna_invocations=luna_invocations)
        self.diagnostics.increment("command_luna_invocations", luna_invocations)
        delivered = bool(self.speaker.speak(answer))
        self.diagnostics.update(last_speech_delivery_success=delivered)
        self._rearm_until = self.clock() + self.config.post_speech_rearm_ms / 1000
        self._reset_wake_detector("speech_completed")
        if not delivered:
            if action_authorization_id and self.action_presentation_failed_fn is not None:
                try:
                    self.action_presentation_failed_fn(
                        action_authorization_id, surface="kokoro_voice",
                    )
                except Exception as exc:  # noqa: BLE001 - action remains non-executable
                    self.diagnostics.update(last_error=f"action_presentation_failure: {type(exc).__name__}")
            self._clear_action_response("delivery_failed")
            self._close_focus("capture_failure")
            self._discard_to_listening(reason="delivery_failed")
            return
        if action_authorization_id:
            self._clear_action_response("replaced")
            self._schedule_action_response_after_speech(
                action_authorization_id,
                target_summary=str(action_dialogue.get("target_summary") or ""),
            )
            return
        if is_action_response:
            self._clear_action_response("resolved")
            self._close_focus("action_dialogue_resolved")
            self._set_state(VoiceState.LISTENING, last_segment_outcome="action_response_resolved")
            return
        if is_followup:
            self._followup_turn_count += 1
        if not is_followup or self._followup_turn_count < self.config.conversation_followup_max_turns:
            self._schedule_focus_after_speech()
            return
        self._close_focus("turn_limit")
        self._set_state(VoiceState.LISTENING, last_segment_outcome="followup_turn_limit")

    def _handle_wake_detection(self, detection: Any, chunk: AudioChunk) -> None:
        """Promote shared chronology after a dedicated Vosk wake event."""
        if self._action_response_active() or self._scheduled_action_response_id is not None:
            self.diagnostics.increment("action_response_wake_suppressions", last_segment_outcome="action_response_wake_suppressed")
            return
        if self._focus_active():
            # The current VAD segment remains the one focus-authorized turn.
            # Its optional leading token is stripped after Whisper; it cannot
            # create a second dispatch or another focus session.
            self.diagnostics.increment("focus_wake_token_suppressions", last_segment_outcome="focus_wake_token")
            return
        if self._active_capture is not None or self._armed_until is not None or self.state in {VoiceState.PROCESSING, VoiceState.SPEAKING}:
            self.diagnostics.increment("wake_debounce_suppressions", last_segment_outcome="wake_debounced")
            return
        detected_at_monotonic = float(getattr(detection, "detected_at_monotonic", self.clock()))
        wake_chime_ok = False
        if self.wake_chime_fn is not None:
            try:
                wake_chime_ok = bool(self.wake_chime_fn())
            except Exception:  # noqa: BLE001 - a cue must never break capture
                wake_chime_ok = False
        wake_chime_request_latency_ms = max(0.0, (self.clock() - detected_at_monotonic) * 1000)
        self._begin_wake_conversation()
        wake_detected_sample = chunk.end_sample
        samples_after_token = getattr(detection, "samples_after_token", None)
        wake_token_end_sample: int | None = None
        if isinstance(samples_after_token, int) and 0 <= samples_after_token <= chunk.end_sample:
            wake_token_end_sample = chunk.end_sample - samples_after_token
        wake_event_id = str(getattr(detection, "wake_event_id", "") or uuid.uuid4())
        detection_source = str(getattr(detection, "detection_source", "unknown"))
        command_speech_seen = bool(
            isinstance(samples_after_token, int)
            and samples_after_token >= int(self.config.minimum_speech_ms * self.config.sample_rate / 1000)
        )
        self.diagnostics.increment(
            "wake_detections",
            wake_engine="vosk",
            wake_token="sentry",
            wake_engine_state="detected",
            last_wake_at=datetime.now(timezone.utc).isoformat(),
            last_vosk_result_class="wake",
            wake_detected_sample=wake_detected_sample,
            wake_token_end_sample=wake_token_end_sample,
            wake_detected_monotonic=round(detected_at_monotonic, 6),
            wake_detection_source=detection_source,
            wake_chime_requested=wake_chime_ok,
            wake_chime_request_latency_ms=round(wake_chime_request_latency_ms, 3),
        )
        self._set_state(VoiceState.WAKE_DETECTED, last_segment_outcome="vosk_wake")
        try:
            self._promote_capture(
                chunk,
                mode="wake_inline",
                wake_event_id=wake_event_id,
                wake_detected_sample=wake_detected_sample,
                wake_token_end_sample=wake_token_end_sample,
                command_speech_seen=command_speech_seen,
            )
        except AudioTimelineGap:
            self._fail_active_capture("audio_gap")
            return
        self._reset_wake_detector("accepted_wake")

    def process_chunk(
        self,
        chunk: np.ndarray,
        *,
        sequence_number: int | None = None,
        start_sample: int | None = None,
    ) -> None:
        now = self.clock()
        if self._action_response_active() and now >= (self._action_response_deadline or now):
            self._expire_action_response("response_timeout")
        if self._armed_until is not None and now >= self._armed_until:
            self._armed_until = None
            self._reset_wake_detector("armed_timeout")
            self._discard_to_listening(reason="armed_timeout")
        if self._focus_active() and now >= self._focus_deadline:
            self._close_focus("timeout")
            self._reset_wake_detector("followup_timeout")
            self._discard_to_listening(reason="followup_timeout")
        samples = np.asarray(chunk, dtype=np.float32)
        if samples.shape != (512,):
            raise ValueError("voice stream must yield 512-sample chunks")
        if self.speech_activity.is_active():
            try:
                self._timeline.publish(
                    samples,
                    monotonic_timestamp=now,
                    vad_probability=None,
                    sequence_number=sequence_number,
                    start_sample=start_sample,
                )
            except AudioTimelineGap:
                self._fail_active_capture("audio_gap")
                return
            if not self._speech_suppressed:
                self.diagnostics.increment("speech_activity_suppressions")
                self._close_focus("speech_activity")
                self._reset_capture(clear_timeline=True)
                self._reset_wake_detector("speech_activity")
                self._speech_suppressed = True
            else:
                self._timeline.clear_audio()
            self._set_state(VoiceState.SPEAKING, last_segment_outcome="speech_activity_suppressed")
            return
        self._speech_suppressed = False
        if now < self._rearm_until:
            try:
                self._timeline.publish(
                    samples,
                    monotonic_timestamp=now,
                    vad_probability=None,
                    sequence_number=sequence_number,
                    start_sample=start_sample,
                )
            except AudioTimelineGap:
                self._fail_active_capture("audio_gap")
                return
            self._reset_capture(clear_timeline=True)
            self._reset_wake_detector("post_speech_rearm")
            self._set_state(VoiceState.SPEAKING, last_segment_outcome="post_speech_rearm")
            return
        if self.state == VoiceState.SPEAKING and not self._focus_pending and self._scheduled_action_response_id is None:
            self._set_state(VoiceState.LISTENING, last_segment_outcome="post_speech_rearmed")
        self._open_scheduled_action_response()
        self._open_scheduled_focus()
        was_capturing = self._active_capture is not None
        probability = self.vad.probability(samples)
        continuation_authorized = was_capturing or self._armed_until is not None or self._focus_active() or self._action_response_active()
        threshold = self.config.vad_continuation_threshold if continuation_authorized else self.config.vad_threshold
        speaking = probability >= threshold
        try:
            audio_chunk = self._timeline.publish(
                samples,
                monotonic_timestamp=now,
                vad_probability=probability,
                sequence_number=sequence_number,
                start_sample=start_sample,
            )
        except AudioTimelineGap:
            if self._active_capture is not None:
                self._active_capture.gap_count += 1
            self._fail_active_capture("audio_gap")
            return
        self.diagnostics.update(
            stream_sequence=self._timeline.stream_sequence,
            stream_end_sample=self._timeline.stream_end_sample,
            vad_probability=round(probability, 4),
            microphone_audio_level=normalized_audio_level(samples),
        )
        if speaking:
            if self._active_capture is not None:
                self._cancel_close_candidate("speech_resumed")
            if self._speech_epoch_start_sample is None:
                self._speech_epoch_start_sample = audio_chunk.start_sample
                self._speech_samples = 0
            self._last_voice_sample = audio_chunk.end_sample
            self._speech_samples += samples.size
            self._silence_samples = 0
            self._last_speech_at = now
        elif self._speech_epoch_start_sample is not None or self._active_capture is not None:
            self._silence_samples += samples.size
        pcm = np.clip(samples * 32767.0, -32768, 32767).astype(np.int16)
        detections = self.wake_detector.feed(pcm)
        vosk_result_class = getattr(self.wake_detector, "last_result_class", "unknown")
        for detection in detections:
            self._handle_wake_detection(detection, audio_chunk)
            break
        self.diagnostics.update(last_vosk_result_class=vosk_result_class)
        if self._active_capture is None and speaking:
            mode: str | None = None
            if self._action_response_active():
                mode = "action_response"
            elif self._focus_active():
                mode = "focus_followup"
            elif self._armed_until is not None:
                mode = "armed_followup"
            if mode is not None:
                try:
                    self._promote_capture(audio_chunk, mode=mode, command_speech_seen=True)
                except AudioTimelineGap:
                    self._fail_active_capture("audio_gap")
                    return
        capture = self._active_capture
        if capture is not None and capture.current_end_sample == audio_chunk.start_sample:
            try:
                capture.append(audio_chunk, speaking=speaking)
                self._feed_command_stream(
                    pcm,
                    start_sample=audio_chunk.start_sample,
                    end_sample=audio_chunk.end_sample,
                )
            except AudioTimelineGap:
                self._fail_active_capture("audio_gap")
                return
            self.diagnostics.update(
                capture_end_sample=capture.current_end_sample,
                capture_duration_ms=round(capture.sample_count * 1000 / self.config.sample_rate),
                capture_chunk_count=capture.chunk_count,
                capture_sample_count=capture.sample_count,
                capture_gap_count=capture.gap_count,
            )
        elif capture is not None and capture.current_end_sample != audio_chunk.end_sample:
            capture.gap_count += 1
            self._fail_active_capture("audio_gap")
            return
        if self._active_capture is not None:
            duration_seconds = self._active_capture.sample_count / self.config.sample_rate
            if duration_seconds >= self.config.maximum_utterance_seconds:
                self._complete_segment(endpoint_reason="maximum_duration")
            else:
                self._evaluate_command_boundary(now)
            return
        if (
            self._speech_epoch_start_sample is not None
            and self._silence_samples * 1000 / self.config.sample_rate >= self.config.end_silence_ms
        ):
            self.diagnostics.increment("non_wake_segments", last_segment_outcome="non_wake")
            self._reset_capture(clear_timeline=True)
            self._set_state(VoiceState.LISTENING, last_segment_outcome="non_wake")

    def run(self, stop_event: threading.Event) -> int:
        if self.config.sleep_enabled:
            self._set_state(
                VoiceState.SLEEPING,
                sleep_enabled=True,
                wake_enabled=False,
                vad_healthy=False,
                last_segment_outcome="sleep_enabled",
            )
            return 0
        self._set_state(
            VoiceState.LISTENING,
            sleep_enabled=False,
            wake_enabled=True,
            command_endpoint_engine=self.config.endpoint_engine,
            command_recognizer="vosk_full_vocabulary",
            command_recognizer_endpointer_mode=self.command_recognizer.endpointer_mode,
            command_continuation_idle_ms=self.config.command_continuation_idle_ms,
            command_stability_recheck_ms=self.config.command_stability_recheck_ms,
            timeline_capacity_samples=self._timeline.capacity_samples,
            timeline_capacity_seconds=self.config.timeline_capacity_seconds,
            stream_sequence=self._timeline.stream_sequence,
            stream_end_sample=self._timeline.stream_end_sample,
            **(
                self.identity_coordinator.diagnostics()
                if self.identity_coordinator is not None
                else {
                    "speaker_context_active": False,
                    "speaker_context_state": "unavailable",
                    "speaker_context_image_shared": False,
                    "speaker_context_frames_persisted": False,
                }
            ),
        )
        try:
            for chunk in self.stream.iter_chunks(stop_event):
                if stop_event.is_set():
                    break
                self.process_chunk(chunk)
        except Exception as exc:  # noqa: BLE001 - systemd should receive a clear failure
            self.diagnostics.update(state=VoiceState.DISABLED.value, vad_healthy=False, last_error=f"voice: {type(exc).__name__}")
            self._reset_capture(clear_timeline=True)
            return 1
        self._close_focus("shutdown")
        self._clear_action_response("shutdown")
        if self.identity_coordinator is not None:
            self.identity_coordinator.clear("shutdown")
            self.diagnostics.update(**self.identity_coordinator.diagnostics())
        self._reset_capture(clear_timeline=True)
        self._set_state(VoiceState.DISABLED, last_segment_outcome="stopped")
        return 0
