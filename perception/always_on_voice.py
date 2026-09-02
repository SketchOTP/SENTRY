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

from .speech_activity import SpeechActivityGate
from .voice import _terminate_capture_process


class VoiceState(str, Enum):
    DISABLED = "DISABLED"
    LISTENING = "LISTENING"
    WAKE_DETECTED = "WAKE_DETECTED"
    CAPTURING = "CAPTURING"
    TRANSCRIBING = "TRANSCRIBING"
    ARMED = "ARMED"
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


@dataclass(frozen=True)
class AlwaysOnVoiceConfig:
    always_on_enabled: bool = False
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
    # Preserve wake-adjacent lead-in before VAD crosses its threshold. Audio
    # remains bounded and in memory only.
    pre_speech_ms: int = 1000
    minimum_speech_ms: int = 250
    end_silence_ms: int = 1000
    # Compound operator requests may contain several ordered actions. Keep the
    # audio buffer finite and memory-only without truncating natural requests
    # at the former short-command boundary.
    maximum_utterance_seconds: float = 45.0
    followup_window_seconds: float = 8.0
    conversation_followup_enabled: bool = True
    conversation_followup_window_seconds: float = 8.0
    conversation_followup_max_turns: int = 2
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
        if self.maximum_utterance_seconds <= 0 or self.followup_window_seconds <= 0 or self.conversation_followup_window_seconds <= 0 or self.post_speech_rearm_ms < 0:
            raise ValueError("voice duration limits are invalid")
        if self.conversation_followup_max_turns < 0:
            raise ValueError("voice.conversation_followup_max_turns must be non-negative")
        if not self.whisper_model or not self.base_url.startswith("http://127.0.0.1"):
            raise ValueError("voice must use local state API and a Whisper model")
        if not self.kokoro_voice.startswith("bm_"):
            raise ValueError("voice.kokoro_voice must be a British male Kokoro voice")
        if not 0.75 <= self.kokoro_speed <= 1.3:
            raise ValueError("voice.kokoro_speed must be from 0.75 through 1.3")

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
            microphone_source=source,
            sample_rate=int(values.get("sample_rate", 16_000)),
            wake_engine=str(values.get("wake_engine", "vosk")),
            wake_token=str(values.get("wake_token", "sentry")),
            vosk_model_path=(str(values["vosk_model_path"]) if values.get("vosk_model_path") is not None else None),
            vosk_grammar=tuple(grammar),
            wake_debounce_ms=int(values.get("wake_debounce_ms", 1000)),
            vad_backend=str(values.get("vad_backend", "silero_vad")),
            vad_threshold=float(values.get("vad_threshold", 0.35)),
            pre_speech_ms=int(values.get("pre_speech_ms", 1000)),
            minimum_speech_ms=int(values.get("minimum_speech_ms", 250)),
            end_silence_ms=int(values.get("end_silence_ms", 1000)),
            maximum_utterance_seconds=float(values.get("maximum_utterance_seconds", 45.0)),
            followup_window_seconds=float(values.get("followup_window_seconds", 8.0)),
            conversation_followup_enabled=bool(values.get("conversation_followup_enabled", True)),
            conversation_followup_window_seconds=float(values.get("conversation_followup_window_seconds", 8.0)),
            conversation_followup_max_turns=int(values.get("conversation_followup_max_turns", 2)),
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
        try:
            while not stop_event.is_set():
                data = process.stdout.read(chunk_bytes)
                if not data:
                    if process.poll() is not None:
                        detail = (process.stderr.read() if process.stderr else b"").decode("utf-8", errors="replace")
                        raise RuntimeError(f"pw-record ended unexpectedly: {detail[-500:]}")
                    continue
                if len(data) != chunk_bytes:
                    continue
                yield np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
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
        transcriber: Transcriber,
        speaker: Speaker,
        ask_fn: Callable[..., dict[str, Any]],
        diagnostics: VoiceDiagnostics | None = None,
        speech_activity: SpeechActivityGate | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config
        self.stream = stream
        self.vad = vad
        self.wake_detector = wake_detector
        self.transcriber = transcriber
        self.speaker = speaker
        self.ask_fn = ask_fn
        self.diagnostics = diagnostics or VoiceDiagnostics()
        self.speech_activity = speech_activity or SpeechActivityGate()
        self.clock = clock
        self.state = VoiceState.DISABLED
        self._capture: list[np.ndarray] = []
        self._pre_speech: list[np.ndarray] = []
        self._speech_samples = 0
        self._silence_samples = 0
        self._armed_until: float | None = None
        self._focus_deadline: float | None = None
        self._focus_pending = False
        self._focus_id: str | None = None
        self._followup_turn_count = 0
        self._rearm_until = 0.0
        self._last_speech_at: float | None = None
        self._last_completed_speech_at: float | None = None
        self._wake_pending = False
        self._last_completed_audio: np.ndarray | None = None
        self._last_completed_audio_at: float | None = None
        self._speech_suppressed = False
        # A focus session owns one RAM-only conversational context. It is not
        # written to diagnostics and disappears on listener restart.
        self._conversation_id: str | None = None

    def _set_state(self, state: VoiceState, **extra: Any) -> None:
        self.state = state
        self.diagnostics.update(state=state.value, vad_healthy=True, **extra)

    def _reset_capture(self) -> None:
        self._capture.clear()
        self._pre_speech.clear()
        self._speech_samples = 0
        self._silence_samples = 0
        self._last_speech_at = None
        self.vad.reset()

    def _reset_wake_detector(self, reason: str) -> None:
        self.wake_detector.reset()
        self.diagnostics.update(wake_engine="vosk", wake_engine_state="listening", last_wake_reset_reason=reason)

    def _remember_pre_speech(self, samples: np.ndarray) -> None:
        """Keep only a short ephemeral lead-in so VAD cannot clip speech."""
        if self.config.pre_speech_ms <= 0:
            return
        self._pre_speech.append(samples.copy())
        maximum_samples = int(self.config.pre_speech_ms * self.config.sample_rate / 1000)
        while sum(item.size for item in self._pre_speech) > maximum_samples:
            self._pre_speech.pop(0)

    def _discard_to_listening(self, *, reason: str | None = None) -> None:
        self._reset_capture()
        self._set_state(VoiceState.LISTENING, last_segment_outcome=reason)

    def _focus_active(self) -> bool:
        return self._focus_deadline is not None

    def _begin_wake_conversation(self) -> None:
        """Start a new RAM-only context only for an explicit Vosk wake."""
        self._close_focus("explicit_new_wake")
        self._conversation_id = f"always-on-{uuid.uuid4()}"
        self._followup_turn_count = 0

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

    def _segment_duration_seconds(self) -> float:
        return sum(item.size for item in self._capture) / self.config.sample_rate

    def _complete_segment(self) -> None:
        audio = np.concatenate(self._capture) if self._capture else np.zeros(0, dtype=np.float32)
        speech_seconds = self._speech_samples / self.config.sample_rate
        self._last_completed_speech_at = self._last_speech_at
        self._reset_capture()
        if speech_seconds * 1000 < self.config.minimum_speech_ms:
            if self._focus_active():
                self._close_focus("capture_failure")
                self._discard_to_listening(reason="followup_too_short")
                return
            self._set_state(VoiceState.ARMED if self._armed_until else VoiceState.LISTENING, last_segment_outcome="too_short")
            return
        self._last_completed_audio = audio
        self._last_completed_audio_at = self.clock()
        if self._wake_pending:
            self._wake_pending = False
            self._handle_wake_segment(audio)
            return
        if self._focus_active():
            self._transcribe_followup(audio, focus=True)
            return
        if self._armed_until is None:
            # Non-wake speech never reaches Whisper.  Keep only a short
            # in-memory segment in case Vosk finalizes one chunk later.
            self.diagnostics.increment("non_wake_segments", last_segment_outcome="non_wake")
            self._discard_to_listening(reason="non_wake")
            return
        self._transcribe_followup(audio, focus=False)

    def _transcribe_followup(self, audio: np.ndarray, *, focus: bool) -> None:
        self._set_state(VoiceState.TRANSCRIBING, last_command_audio_duration_ms=round(audio.size * 1000 / self.config.sample_rate))
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

    def _handle_wake_segment(self, audio: np.ndarray, *, audio_starts_after_wake: bool = False) -> None:
        """Use Whisper only after Vosk woke, preserving Vosk as authority."""
        self._set_state(VoiceState.TRANSCRIBING, last_command_audio_duration_ms=round(audio.size * 1000 / self.config.sample_rate), command_boundary="whisper_post_vosk")
        try:
            transcript = " ".join(str(self.transcriber.transcribe(audio, self.config.sample_rate)).split())
        except Exception as exc:  # noqa: BLE001
            self._enter_armed("whisper_failed_after_wake", error=f"whisper: {type(exc).__name__}")
            return
        if audio_starts_after_wake:
            # Word timing normally removes the token. Some decoder versions
            # include a small amount of it in the recovered queue, so strip it
            # when present without treating Whisper as a second wake judge.
            command = self._command_after_wake(transcript) if re.search(r"\bsentry\b", transcript, flags=re.IGNORECASE) else transcript
        else:
            command = self._command_after_wake(transcript)
        if not command:
            self._enter_armed("wake_only_or_command_unavailable")
            return
        self._dispatch_command(command, is_followup=False)

    def _enter_armed(self, reason: str, *, error: str | None = None) -> None:
        self._armed_until = self.clock() + self.config.followup_window_seconds
        values: dict[str, Any] = {"last_segment_outcome": reason, "last_command_transcription_status": "unavailable"}
        if error:
            values["last_error"] = error
        self._set_state(VoiceState.ARMED, **values)

    def _dispatch_command(self, command: str, *, is_followup: bool) -> None:
        if self._last_completed_speech_at is not None:
            self.diagnostics.record_dispatch_latency((self.clock() - self._last_completed_speech_at) * 1000)
        self._last_completed_speech_at = None
        self.diagnostics.increment("command_dispatches")
        self._set_state(VoiceState.PROCESSING, last_command_outcome="processing")
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
            )
        except Exception as exc:  # noqa: BLE001
            self._reset_wake_detector("ask_failed")
            self._close_focus("capture_failure")
            self._discard_to_listening(reason="ask_failed")
            self.diagnostics.update(last_error=f"ask: {type(exc).__name__}")
            return
        self.diagnostics.record_answer_latency((self.clock() - answer_started_at) * 1000)
        answer = response.get("answer") if isinstance(response, dict) else None
        luna_invocations = int(response.get("luna_invocations", 0)) if isinstance(response, dict) else 0
        if isinstance(response, dict):
            self.diagnostics.update(
                codex_thread_active=bool(response.get("thread_id")),
                codex_session_resumed=bool(response.get("session_resumed")),
                codex_context_utilization=response.get("context_utilization"),
                codex_auto_compact_token_limit=response.get("auto_compact_token_limit"),
                codex_compactions_observed=response.get("compactions_observed", 0),
            )
        if not isinstance(answer, str) or not answer.strip():
            self._reset_wake_detector("no_answer")
            self._close_focus("capture_failure")
            self._discard_to_listening(reason="no_answer")
            return
        self._set_state(VoiceState.SPEAKING, last_command_outcome="answered", last_command_luna_invocations=luna_invocations)
        self.diagnostics.increment("command_luna_invocations", luna_invocations)
        delivered = bool(self.speaker.speak(answer))
        self.diagnostics.update(last_speech_delivery_success=delivered)
        self._rearm_until = self.clock() + self.config.post_speech_rearm_ms / 1000
        self._reset_wake_detector("speech_completed")
        if not delivered:
            self._close_focus("capture_failure")
            self._discard_to_listening(reason="delivery_failed")
            return
        if is_followup:
            self._followup_turn_count += 1
        if not is_followup or self._followup_turn_count < self.config.conversation_followup_max_turns:
            self._schedule_focus_after_speech()
            return
        self._close_focus("turn_limit")
        self._set_state(VoiceState.LISTENING, last_segment_outcome="followup_turn_limit")

    def _handle_wake_detection(self, detection: Any) -> None:
        """Accept the dedicated Vosk wake event without consulting Whisper."""
        if self._focus_active():
            # The current VAD segment remains the one focus-authorized turn.
            # Its optional leading token is stripped after Whisper; it cannot
            # create a second dispatch or another focus session.
            self.diagnostics.increment("focus_wake_token_suppressions", last_segment_outcome="focus_wake_token")
            return
        if self._wake_pending or self._armed_until is not None or self.state in {VoiceState.PROCESSING, VoiceState.SPEAKING}:
            self.diagnostics.increment("wake_debounce_suppressions", last_segment_outcome="wake_debounced")
            return
        self._begin_wake_conversation()
        capture_in_progress = bool(self._capture)
        self.diagnostics.increment(
            "wake_detections",
            wake_engine="vosk",
            wake_token="sentry",
            wake_engine_state="detected",
            last_wake_at=datetime.now(timezone.utc).isoformat(),
            last_vosk_result_class="wake",
            queued_audio_duration_ms=3000,
        )
        self._set_state(VoiceState.WAKE_DETECTED, last_segment_outcome="vosk_wake")
        self._reset_wake_detector("accepted_wake")
        # A VAD-active segment is the reliable inline path: retain it through
        # endpointing so words spoken after the token cannot be lost because
        # Vosk finalized the token early.
        if capture_in_progress:
            self._wake_pending = True
            self._set_state(VoiceState.CAPTURING, last_segment_outcome="vosk_wake_capturing")
            return
        queued_after_token = getattr(detection, "queued_after_token", None)
        if isinstance(queued_after_token, np.ndarray) and queued_after_token.size:
            # Vosk word timing gives a tighter command boundary than asking
            # Whisper to rediscover the wake token inside a whole utterance.
            # The queue is bounded, RAM-only, and immediately discarded here.
            command_audio = np.asarray(queued_after_token, dtype=np.float32) / 32768.0
            self._reset_capture()
            self._wake_pending = False
            self._handle_wake_segment(command_audio, audio_starts_after_wake=True)
            return
        if self._last_completed_audio is not None and self._last_completed_audio_at is not None:
            if self.clock() - self._last_completed_audio_at <= 2.0:
                audio = self._last_completed_audio
                self._last_completed_audio = None
                self._last_completed_audio_at = None
                self._handle_wake_segment(audio)
                return
        self._enter_armed("wake_without_recoverable_segment")

    def process_chunk(self, chunk: np.ndarray) -> None:
        now = self.clock()
        if self._armed_until is not None and now >= self._armed_until:
            self._armed_until = None
            self._reset_wake_detector("armed_timeout")
            self._discard_to_listening(reason="armed_timeout")
        if self._focus_active() and now >= self._focus_deadline:
            self._close_focus("timeout")
            self._reset_wake_detector("followup_timeout")
            self._discard_to_listening(reason="followup_timeout")
        if self.speech_activity.is_active():
            if not self._speech_suppressed:
                self.diagnostics.increment("speech_activity_suppressions")
                self._close_focus("speech_activity")
                self._reset_capture()
                self._reset_wake_detector("speech_activity")
                self._speech_suppressed = True
            self._set_state(VoiceState.SPEAKING, last_segment_outcome="speech_activity_suppressed")
            return
        self._speech_suppressed = False
        if now < self._rearm_until:
            self._reset_capture()
            self._reset_wake_detector("post_speech_rearm")
            self._set_state(VoiceState.SPEAKING, last_segment_outcome="post_speech_rearm")
            return
        self._open_scheduled_focus()
        samples = np.asarray(chunk, dtype=np.float32)
        if samples.shape != (512,):
            raise ValueError("voice stream must yield 512-sample chunks")
        was_capturing = bool(self._capture)
        pcm = np.clip(samples * 32767.0, -32768, 32767).astype(np.int16)
        detections = self.wake_detector.feed(pcm)
        vosk_result_class = getattr(self.wake_detector, "last_result_class", "unknown")
        for detection in detections:
            self._handle_wake_detection(detection)
            break
        self.diagnostics.update(last_vosk_result_class=vosk_result_class)
        probability = self.vad.probability(samples)
        speaking = probability >= self.config.vad_threshold
        if not was_capturing:
            self._remember_pre_speech(samples)
        if self.state in {VoiceState.LISTENING, VoiceState.ARMED, VoiceState.FOLLOWUP_LISTENING, VoiceState.SPEAKING, VoiceState.WAKE_DETECTED} and speaking:
            self._capture.extend(self._pre_speech)
            self._pre_speech.clear()
            self._set_state(VoiceState.CAPTURING, vad_probability=round(probability, 4))
        if self.state != VoiceState.CAPTURING:
            return
        if was_capturing:
            self._capture.append(samples.copy())
        if speaking:
            self._speech_samples += samples.size
            self._silence_samples = 0
            self._last_speech_at = now
        else:
            self._silence_samples += samples.size
        if self._segment_duration_seconds() >= self.config.maximum_utterance_seconds:
            self._complete_segment()
        elif self._silence_samples * 1000 / self.config.sample_rate >= self.config.end_silence_ms:
            self._complete_segment()

    def run(self, stop_event: threading.Event) -> int:
        self._set_state(VoiceState.LISTENING)
        try:
            for chunk in self.stream.iter_chunks(stop_event):
                if stop_event.is_set():
                    break
                self.process_chunk(chunk)
        except Exception as exc:  # noqa: BLE001 - systemd should receive a clear failure
            self.diagnostics.update(state=VoiceState.DISABLED.value, vad_healthy=False, last_error=f"voice: {type(exc).__name__}")
            return 1
        self._close_focus("shutdown")
        self._set_state(VoiceState.DISABLED, last_segment_outcome="stopped")
        return 0
