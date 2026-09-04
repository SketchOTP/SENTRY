"""Ephemeral wake-triggered speaker context for agent-on-demand voice.

The coordinator owns only bounded metadata. Camera frames and biometric
features stay inside the local inspection call and are never retained here.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable


SOURCE = "wake_triggered_local_camera"
RETRYABLE_STATES = {"unknown", "unresolved", "ambiguous", "not_visible", "unavailable"}
VALID_STATES = {"recognized", *RETRYABLE_STATES, "expired"}


@dataclass(frozen=True)
class ConversationSpeakerContext:
    context_id: str
    conversation_epoch_id: str
    identity_state: str
    person_id: str | None
    display_name: str | None
    observed_at: str | None
    valid_until: str | None
    source: str
    visible_person_count: int
    identity_confidence: float | None
    exact_arrival_known: bool
    frames_persisted: bool
    image_shared_with_codex: bool
    frames_processed: int
    created_monotonic: float
    expires_monotonic: float
    reason: str | None = None

    def envelope(self, now: float) -> dict[str, Any]:
        state = self.identity_state if now < self.expires_monotonic else "expired"
        return {
            "context_id": self.context_id,
            "conversation_epoch_id": self.conversation_epoch_id,
            "status": state,
            "person_id": self.person_id if state == "recognized" else None,
            "display_name": self.display_name if state == "recognized" else None,
            "observed_at": self.observed_at,
            "valid_until": self.valid_until,
            "source": self.source,
            "visible_person_count": self.visible_person_count,
            "identity_confidence": self.identity_confidence if state == "recognized" else None,
            "exact_arrival_known": False,
            "frames_persisted": False,
            "image_shared_with_codex": False,
            "frames_processed": self.frames_processed,
            "reason": self.reason if state != "recognized" else None,
        }


def unavailable_speaker_envelope(reason: str = "no_current_voice_identity_context") -> dict[str, Any]:
    return {
        "status": "unavailable",
        "person_id": None,
        "display_name": None,
        "observed_at": None,
        "valid_until": None,
        "source": SOURCE,
        "visible_person_count": 0,
        "identity_confidence": None,
        "exact_arrival_known": False,
        "frames_persisted": False,
        "image_shared_with_codex": False,
        "reason": reason,
    }


def context_from_camera_metadata(
    metadata: dict[str, Any], *, conversation_epoch_id: str, now: float,
    ttl_seconds: float, wall_now: datetime | None = None,
) -> ConversationSpeakerContext:
    """Conservatively classify one metadata-only camera observation."""

    people = [person for person in metadata.get("people", []) if isinstance(person, dict) and person.get("visible", True)]
    visible_count = len(people)
    person_id: str | None = None
    display_name: str | None = None
    confidence: float | None = None
    reason: str | None = None
    if visible_count == 0:
        state = "not_visible"
        reason = "no_visible_person_in_bounded_view"
    elif visible_count > 1:
        state = "ambiguous"
        reason = "multiple_visible_people"
    else:
        person = people[0]
        raw_state = str(person.get("identity_state") or "unresolved")
        if raw_state == "recognized" and person.get("person_id"):
            state = "recognized"
            person_id = str(person["person_id"])
            display_name = str(person.get("display_name") or "").strip() or None
            raw_confidence = person.get("identity_confidence")
            if isinstance(raw_confidence, (int, float)):
                confidence = round(max(0.0, min(1.0, float(raw_confidence))), 4)
        elif raw_state == "unknown":
            state = "unknown"
            reason = "visible_person_did_not_match_enrolled_profile"
        else:
            state = "unresolved"
            reason = "visible_person_identity_unresolved"
    observed_at = metadata.get("observed_at")
    observed_text = str(observed_at) if observed_at else None
    current_wall = wall_now or datetime.now(timezone.utc)
    valid_until = (current_wall + timedelta(seconds=ttl_seconds)).isoformat()
    return ConversationSpeakerContext(
        context_id=str(uuid.uuid4()),
        conversation_epoch_id=conversation_epoch_id,
        identity_state=state,
        person_id=person_id,
        display_name=display_name,
        observed_at=observed_text,
        valid_until=valid_until,
        source=SOURCE,
        visible_person_count=visible_count,
        identity_confidence=confidence,
        exact_arrival_known=False,
        frames_persisted=False,
        image_shared_with_codex=False,
        frames_processed=max(0, int(metadata.get("frames_processed", 0) or 0)),
        created_monotonic=now,
        expires_monotonic=now + ttl_seconds,
        reason=reason,
    )


class WakeIdentityCoordinator:
    """Run one bounded metadata-only camera preflight per eligible wake."""

    def __init__(
        self,
        inspector: Callable[[float], dict[str, Any]],
        *,
        idle_seconds: float = 7200.0,
        ttl_seconds: float = 7200.0,
        inspection_duration_seconds: float = 3.0,
        join_timeout_seconds: float = 5.0,
        profile_revision_provider: Callable[[], str] | None = None,
        cache_path: str | Path | None = None,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        for value, name in (
            (idle_seconds, "idle_seconds"),
            (ttl_seconds, "ttl_seconds"),
            (inspection_duration_seconds, "inspection_duration_seconds"),
            (join_timeout_seconds, "join_timeout_seconds"),
        ):
            if value <= 0:
                raise ValueError(f"wake identity {name} must be positive")
        if inspection_duration_seconds > join_timeout_seconds:
            raise ValueError("wake identity inspection duration cannot exceed join timeout")
        self.inspector = inspector
        self.idle_seconds = idle_seconds
        self.ttl_seconds = ttl_seconds
        self.inspection_duration_seconds = inspection_duration_seconds
        self.join_timeout_seconds = join_timeout_seconds
        self.profile_revision_provider = profile_revision_provider
        self.cache_path = Path(cache_path) if cache_path is not None else None
        self.clock = clock
        self.wall_clock = wall_clock
        self._lock = threading.Lock()
        self._context: ConversationSpeakerContext | None = None
        self._conversation_epoch_id: str | None = None
        self._pending_epoch_id: str | None = None
        self._pending_started_at: float | None = None
        self._pending_event: threading.Event | None = None
        self._last_accepted_user_utterance_at: float | None = None
        self._inspection_count = 0
        self._reuse_count = 0
        self._late_result_count = 0
        self._refresh_reason: str | None = None
        self._last_camera_latency_ms: float | None = None
        self._profile_revision = self._read_profile_revision()
        self._profile_catalog_change_count = 0
        self._cache_loaded = False
        self._cache_write_failures = 0
        self._load_cached_context()

    def _load_cached_context(self) -> None:
        """Restore only an unexpired recognized identity from private runtime state."""

        path = self.cache_path
        if path is None or not path.is_file():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or payload.get("identity_state") != "recognized":
                raise ValueError("speaker cache is not a recognized identity")
            valid_until = datetime.fromisoformat(str(payload["valid_until"]))
            if valid_until.tzinfo is None:
                raise ValueError("speaker cache expiration must be timezone-aware")
            remaining = (valid_until - self.wall_clock()).total_seconds()
            if remaining <= 0 or remaining > self.ttl_seconds:
                raise ValueError("speaker cache is expired or exceeds configured TTL")
            cached_revision = payload.get("profile_revision")
            if (
                cached_revision is not None
                and self._profile_revision is not None
                and str(cached_revision) != self._profile_revision
            ):
                raise ValueError("speaker cache profile catalog changed")
            person_id = str(payload["person_id"]).strip()
            if not person_id:
                raise ValueError("speaker cache person id is empty")
            display_name = str(payload.get("display_name") or "").strip() or None
            confidence_value = payload.get("identity_confidence")
            confidence = (
                round(max(0.0, min(1.0, float(confidence_value))), 4)
                if isinstance(confidence_value, (int, float))
                else None
            )
            now = self.clock()
            context = ConversationSpeakerContext(
                context_id=str(payload.get("context_id") or uuid.uuid4()),
                conversation_epoch_id=str(payload.get("conversation_epoch_id") or uuid.uuid4()),
                identity_state="recognized",
                person_id=person_id,
                display_name=display_name,
                observed_at=str(payload.get("observed_at") or "") or None,
                valid_until=valid_until.isoformat(),
                source=SOURCE,
                visible_person_count=1,
                identity_confidence=confidence,
                exact_arrival_known=False,
                frames_persisted=False,
                image_shared_with_codex=False,
                frames_processed=max(0, int(payload.get("frames_processed", 0) or 0)),
                created_monotonic=now,
                expires_monotonic=now + remaining,
            )
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            self._remove_cached_context()
            return
        self._context = context
        self._conversation_epoch_id = context.conversation_epoch_id
        self._cache_loaded = True
        self._refresh_reason = "recognized_cache_restored"

    def _persist_recognized_context(self, context: ConversationSpeakerContext) -> None:
        path = self.cache_path
        if path is None or context.identity_state != "recognized" or not context.person_id:
            return
        payload = {
            "schema": 1,
            "context_id": context.context_id,
            "conversation_epoch_id": context.conversation_epoch_id,
            "identity_state": "recognized",
            "person_id": context.person_id,
            "display_name": context.display_name,
            "observed_at": context.observed_at,
            "valid_until": context.valid_until,
            "identity_confidence": context.identity_confidence,
            "frames_processed": context.frames_processed,
            "profile_revision": self._profile_revision,
        }
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            path.parent.chmod(0o700)
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            path.chmod(0o600)
        except OSError:
            self._cache_write_failures += 1
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def _remove_cached_context(self) -> None:
        if self.cache_path is None:
            return
        try:
            self.cache_path.unlink(missing_ok=True)
        except OSError:
            pass

    def _read_profile_revision(self) -> str | None:
        if self.profile_revision_provider is None:
            return None
        try:
            value = self.profile_revision_provider()
        except Exception:  # noqa: BLE001 - enrollment revision failure cannot block voice
            return None
        return str(value) if value else None

    def _refresh_reason_for_wake(self, now: float) -> str | None:
        context = self._context
        if context is None:
            return "no_context"
        if now >= context.expires_monotonic:
            return "absolute_ttl"
        if (
            self._last_accepted_user_utterance_at is not None
            and now - self._last_accepted_user_utterance_at >= self.idle_seconds
        ):
            return "voice_inactivity"
        if context.identity_state in RETRYABLE_STATES:
            return "unresolved_retry"
        return None

    def begin_explicit_wake(self) -> tuple[str, bool]:
        now = self.clock()
        current_profile_revision = self._read_profile_revision()
        with self._lock:
            reason = self._refresh_reason_for_wake(now)
            if (
                current_profile_revision is not None
                and self._profile_revision is not None
                and current_profile_revision != self._profile_revision
            ):
                reason = "profile_catalog_changed"
                self._profile_catalog_change_count += 1
            if current_profile_revision is not None:
                self._profile_revision = current_profile_revision
            if reason is None and self._context is not None:
                self._reuse_count += 1
                return self._context.conversation_epoch_id, False
            epoch_id = str(uuid.uuid4())
            self._conversation_epoch_id = epoch_id
            self._context = None
            self._pending_epoch_id = epoch_id
            self._pending_started_at = now
            event = threading.Event()
            self._pending_event = event
            self._inspection_count += 1
            self._refresh_reason = reason
        self._remove_cached_context()
        thread = threading.Thread(
            target=self._inspect,
            args=(epoch_id, now, event),
            name="sentry-wake-identity",
            daemon=True,
        )
        thread.start()
        return epoch_id, True

    def _inspect(self, epoch_id: str, started_at: float, event: threading.Event) -> None:
        try:
            metadata = self.inspector(self.inspection_duration_seconds)
            result_now = self.clock()
            context = context_from_camera_metadata(
                metadata,
                conversation_epoch_id=epoch_id,
                now=result_now,
                ttl_seconds=self.ttl_seconds,
                wall_now=self.wall_clock(),
            )
        except Exception as exc:  # noqa: BLE001 - camera failure cannot block conversation
            result_now = self.clock()
            wall_now = self.wall_clock()
            context = ConversationSpeakerContext(
                context_id=str(uuid.uuid4()), conversation_epoch_id=epoch_id,
                identity_state="unavailable", person_id=None, display_name=None,
                observed_at=None,
                valid_until=(wall_now + timedelta(seconds=self.ttl_seconds)).isoformat(),
                source=SOURCE, visible_person_count=0, identity_confidence=None,
                exact_arrival_known=False, frames_persisted=False,
                image_shared_with_codex=False, created_monotonic=result_now,
                frames_processed=0,
                expires_monotonic=result_now + self.ttl_seconds,
                reason=f"{type(exc).__name__}",
            )
        with self._lock:
            self._last_camera_latency_ms = round((self.clock() - started_at) * 1000, 3)
            if self._pending_epoch_id != epoch_id or self._conversation_epoch_id != epoch_id:
                self._late_result_count += 1
            else:
                self._context = context
                self._pending_epoch_id = None
                self._pending_started_at = None
                self._pending_event = None
                if context.identity_state == "recognized":
                    self._persist_recognized_context(context)
        event.set()

    def current_envelope(self, *, wait_for_preflight: bool = False) -> dict[str, Any]:
        event: threading.Event | None = None
        remaining = 0.0
        with self._lock:
            if wait_for_preflight and self._pending_event is not None and self._pending_started_at is not None:
                event = self._pending_event
                remaining = max(0.0, self.join_timeout_seconds - (self.clock() - self._pending_started_at))
        if event is not None and remaining > 0:
            event.wait(remaining)
        with self._lock:
            now = self.clock()
            if self._context is not None:
                return self._context.envelope(now)
            if self._pending_epoch_id is not None:
                timed_out_epoch = self._pending_epoch_id
                self._pending_epoch_id = None
                self._pending_started_at = None
                self._pending_event = None
                self._context = ConversationSpeakerContext(
                    context_id=str(uuid.uuid4()), conversation_epoch_id=timed_out_epoch,
                    identity_state="unavailable", person_id=None, display_name=None,
                    observed_at=None,
                    valid_until=(self.wall_clock() + timedelta(seconds=self.ttl_seconds)).isoformat(),
                    source=SOURCE, visible_person_count=0, identity_confidence=None,
                    exact_arrival_known=False, frames_persisted=False,
                    image_shared_with_codex=False, created_monotonic=now,
                    frames_processed=0,
                    expires_monotonic=now + self.ttl_seconds,
                    reason="inspection_timeout",
                )
                return self._context.envelope(now)
        return unavailable_speaker_envelope()

    def record_accepted_user_utterance(self) -> None:
        with self._lock:
            self._last_accepted_user_utterance_at = self.clock()

    def clear(self, reason: str) -> None:
        with self._lock:
            self._context = None
            self._conversation_epoch_id = None
            self._pending_epoch_id = None
            self._pending_started_at = None
            self._pending_event = None
            self._last_accepted_user_utterance_at = None
            self._refresh_reason = reason
        if reason != "shutdown":
            self._remove_cached_context()

    def diagnostics(self) -> dict[str, Any]:
        with self._lock:
            now = self.clock()
            context = self._context
            envelope = context.envelope(now) if context is not None else unavailable_speaker_envelope()
            return {
                "speaker_context_active": bool(context is not None and envelope["status"] != "expired"),
                "speaker_context_id": envelope.get("context_id"),
                "speaker_context_state": envelope["status"],
                "speaker_context_display_name": envelope.get("display_name"),
                "speaker_context_observed_at": envelope.get("observed_at"),
                "speaker_context_expires_at": envelope.get("valid_until"),
                "speaker_context_age_seconds": (
                    round(max(0.0, now - context.created_monotonic), 3) if context is not None else None
                ),
                "speaker_context_conversation_epoch": envelope.get("conversation_epoch_id"),
                "speaker_context_refresh_reason": self._refresh_reason,
                "speaker_context_inspection_count": self._inspection_count,
                "speaker_context_reuse_count": self._reuse_count,
                "speaker_context_camera_latency_ms": self._last_camera_latency_ms,
                "speaker_context_camera_frames_processed": (
                    context.frames_processed if context is not None else None
                ),
                "speaker_context_preflight_active": self._pending_epoch_id is not None,
                "speaker_context_late_result_count": self._late_result_count,
                "speaker_context_profile_catalog_change_count": self._profile_catalog_change_count,
                "speaker_context_cache_loaded": self._cache_loaded,
                "speaker_context_cache_write_failures": self._cache_write_failures,
                "speaker_context_image_shared": False,
                "speaker_context_frames_persisted": False,
            }
