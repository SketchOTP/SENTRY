"""Conservative, metadata-only proactive policy for SENTRY.

The processor runs after persistence, not inside the camera/perception loop.
It reserves each source event before invoking Luna or speech so restart and
replay cannot produce duplicate interruptions.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from .presence_store import PREFERENCE_KEY, PresenceStore
from .weather import WeatherConfig


SUPPRESSION_REASONS = {
    "disabled", "unsupported_event", "non_primary", "stale", "room_not_occupied",
    "source_unhealthy", "restart_reconciled", "duplicate", "already_handled_session",
    "cooldown", "hourly_budget", "startup_suppression", "speech_busy", "judge_silent",
    "judge_invalid", "delivery_failed", "user_preference", "weather_unconfigured",
    "weather_unavailable", "weather_stale", "weather_insufficient", "weather_not_relevant",
}
_ALLOWED_DECISIONS = {"speak", "silent"}
_BANNED_UTTERANCE_PATTERNS = (
    re.compile(r"\bi detected you\b", re.IGNORECASE),
    re.compile(r"\bthe camera detected\b", re.IGNORECASE),
    re.compile(r"\bI see you on camera\b", re.IGNORECASE),
)


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("proactive timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class ProactivePolicyConfig:
    enabled: bool = False
    event_ttl_seconds: float = 30.0
    same_session_max_actions: int = 1
    person_cooldown_minutes: float = 30.0
    global_max_spoken_actions_per_hour: int = 2
    startup_suppression_seconds: float = 30.0
    judge_effort: str = "low"
    judge_timeout_seconds: int = 120
    max_utterance_words: int = 20
    max_utterance_chars: int = 160

    def __post_init__(self) -> None:
        if self.event_ttl_seconds <= 0 or self.person_cooldown_minutes < 0 or self.startup_suppression_seconds < 0:
            raise ValueError("proactive time limits are invalid")
        if self.same_session_max_actions <= 0 or self.global_max_spoken_actions_per_hour < 0:
            raise ValueError("proactive action limits are invalid")
        if self.judge_effort not in {"none", "low", "medium", "high", "xhigh", "max"}:
            raise ValueError("proactive judge effort is invalid")
        if self.judge_timeout_seconds <= 0 or self.max_utterance_words <= 0 or self.max_utterance_chars <= 0:
            raise ValueError("proactive output limits are invalid")

    @classmethod
    def from_mapping(cls, values: dict[str, Any] | None) -> "ProactivePolicyConfig":
        values = values or {}
        if not isinstance(values, dict):
            raise ValueError("proactivity must be an object")
        return cls(
            enabled=bool(values.get("enabled", False)),
            event_ttl_seconds=float(values.get("event_ttl_seconds", 30.0)),
            same_session_max_actions=int(values.get("same_session_max_actions", 1)),
            person_cooldown_minutes=float(values.get("person_cooldown_minutes", 30.0)),
            global_max_spoken_actions_per_hour=int(values.get("global_max_spoken_actions_per_hour", 2)),
            startup_suppression_seconds=float(values.get("startup_suppression_seconds", 30.0)),
            judge_effort=str(values.get("judge_effort", "low")),
            judge_timeout_seconds=int(values.get("judge_timeout_seconds", 120)),
            max_utterance_words=int(values.get("max_utterance_words", 20)),
            max_utterance_chars=int(values.get("max_utterance_chars", 160)),
        )


@dataclass(frozen=True)
class WeatherContextPolicy:
    """Deterministic policy for consuming an already-cached weather snapshot."""

    configured: bool = False
    location_label: str = "home"
    horizon_minutes: int = 120
    precipitation_probability_threshold: float = 60.0

    def __post_init__(self) -> None:
        if self.horizon_minutes <= 0:
            raise ValueError("weather context horizon must be positive")
        if not 0 <= self.precipitation_probability_threshold <= 100:
            raise ValueError("weather context precipitation threshold must be 0..100")
        if not self.location_label:
            raise ValueError("weather context location_label must not be empty")

    @classmethod
    def from_mapping(cls, values: dict[str, Any] | None) -> "WeatherContextPolicy":
        weather = WeatherConfig.from_mapping(values)
        contextual = values.get("contextual_proactivity", {}) if isinstance(values, dict) else {}
        if contextual is None:
            contextual = {}
        if not isinstance(contextual, dict):
            raise ValueError("weather contextual_proactivity must be an object")
        return cls(
            configured=weather.enabled and weather.latitude is not None and weather.longitude is not None,
            location_label=weather.location_label,
            horizon_minutes=int(contextual.get("horizon_minutes", 120)),
            precipitation_probability_threshold=float(contextual.get("precipitation_probability_threshold", 60)),
        )


@dataclass(frozen=True)
class ProactiveOutcome:
    action_id: str | None
    source_event_id: str
    candidate_key: str
    suppression_reason: str | None
    judge_invoked: bool
    judge_decision: str | None
    delivery_status: str
    utterance: str | None = None
    judge_latency_ms: float | None = None


class SpeechDispatcher:
    """Small bounded Speech Dispatcher adapter with cancellation."""

    def __init__(self, executable: str | None = None, *, application_name: str = "SENTRY") -> None:
        self.executable = executable or shutil.which("spd-say")
        self.application_name = application_name
        self._lock = threading.RLock()
        self._process: subprocess.Popen[str] | None = None

    @property
    def available(self) -> bool:
        return bool(self.executable)

    @property
    def is_speaking(self) -> bool:
        with self._lock:
            return self._process is not None and self._process.poll() is None

    def speak(self, text: str) -> bool:
        if not self.available:
            return False
        if not isinstance(text, str) or not text.strip():
            return False
        with self._lock:
            if self.is_speaking:
                return False
            try:
                self._process = subprocess.Popen(
                    [self.executable, "--wait", "--priority", "notification", "--application-name", self.application_name, text],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                )
            except OSError:
                self._process = None
                return False
            process = self._process
        returncode = process.wait()
        with self._lock:
            if self._process is process:
                self._process = None
        return returncode == 0

    def cancel(self) -> bool:
        if not self.available:
            return False
        try:
            subprocess.run(
                [self.executable, "--cancel", "--application-name", self.application_name],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        with self._lock:
            process = self._process
            if process is not None and process.poll() is None:
                process.terminate()
        return True


def validate_proactive_judgment(
    result: Any,
    supplied_fact_ids: set[str],
    *,
    max_words: int = 20,
    max_chars: int = 160,
) -> str | None:
    if not isinstance(result, dict) or set(result) != {"decision", "message", "fact_ids", "reason_code"}:
        return "judge response fields are invalid"
    decision = result.get("decision")
    message = result.get("message")
    fact_ids = result.get("fact_ids")
    if decision not in _ALLOWED_DECISIONS:
        return "judge decision is invalid"
    if not isinstance(fact_ids, list) or not fact_ids or any(not isinstance(item, str) for item in fact_ids):
        return "judge fact_ids must be a non-empty string list"
    if len(set(fact_ids)) != len(fact_ids) or not set(fact_ids) <= supplied_fact_ids:
        return "judge cited an unknown or duplicate fact_id"
    if not isinstance(result.get("reason_code"), str) or not result["reason_code"].strip():
        return "judge reason_code is invalid"
    if decision == "silent":
        if message is not None:
            return "silent judge decision must not contain a message"
        return None
    if not isinstance(message, str) or not message.strip():
        return "speak judge decision requires a message"
    if len(message) > max_chars or len(message.split()) > max_words:
        return "judge message exceeds configured limit"
    if any(pattern.search(message) for pattern in _BANNED_UTTERANCE_PATTERNS):
        return "judge message exposes technical perception details"
    return None


class ProactiveProcessor:
    """Evaluate persisted identity events and record every policy outcome."""

    def __init__(
        self,
        store: PresenceStore,
        config: ProactivePolicyConfig | None = None,
        *,
        judge: Callable[..., dict[str, Any]] | None = None,
        speech: SpeechDispatcher | Any | None = None,
        started_at: datetime | None = None,
        weather_policy: WeatherContextPolicy | None = None,
    ) -> None:
        self.store = store
        self.config = config or ProactivePolicyConfig()
        self._judge = judge
        self.speech = speech or SpeechDispatcher()
        self.started_at = _utc(started_at or datetime.now(timezone.utc))
        self.weather_policy = weather_policy
        self._seen_event_ids: set[str] = set()

    def _candidate_key(self, event: dict[str, Any]) -> str:
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        person_id = payload.get("person_id") or "unknown"
        session_id = event.get("session_id")
        return f"{person_id}:session:{session_id}" if session_id is not None else f"{person_id}:event:{event.get('event_id')}"

    def _counts(self, candidate_key: str, person_id: str | None, now: datetime) -> dict[str, Any]:
        actions = self.store.proactive_actions(limit=1000)
        same_session = [item for item in actions if item["candidate_key"] == candidate_key]
        cooldown_cutoff = now - timedelta(minutes=self.config.person_cooldown_minutes)
        cooldown_active = any(
            item.get("eligibility_result") == "eligible"
            and (_parse_time(item.get("evaluated_at")) or datetime.min.replace(tzinfo=timezone.utc)) >= cooldown_cutoff
            for item in actions if item.get("person_id") == person_id
        )
        hour_cutoff = now - timedelta(hours=1)
        hourly_spoken = sum(
            1 for item in actions
            if item.get("delivery_status") == "delivered"
            and (_parse_time(item.get("delivered_at")) or _parse_time(item.get("evaluated_at")) or datetime.min.replace(tzinfo=timezone.utc)) >= hour_cutoff
        )
        return {
            "same_session_action_count": len(same_session),
            "cooldown_active": cooldown_active,
            "hourly_spoken_count": hourly_spoken,
        }

    def _eligibility(self, event: dict[str, Any], now: datetime) -> tuple[str | None, str, dict[str, Any]]:
        event_id = event.get("event_id")
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        person_id = payload.get("person_id")
        candidate_key = self._candidate_key(event)
        counts = self._counts(candidate_key, person_id, now)
        context = {**counts, "candidate_key": candidate_key, "hourly_spoken_limit": self.config.global_max_spoken_actions_per_hour, "same_session_action_limit": self.config.same_session_max_actions}
        if not self.config.enabled:
            return "disabled", candidate_key, context
        if event.get("event_type") != "person.identified":
            return "unsupported_event", candidate_key, context
        if person_id != "primary_user":
            return "non_primary", candidate_key, context
        occurred_at = _parse_time(event.get("occurred_at"))
        if occurred_at is None or now - occurred_at > timedelta(seconds=self.config.event_ttl_seconds) or occurred_at - now > timedelta(seconds=5):
            return "stale", candidate_key, context
        if bool(payload.get("recovered_after_restart")) or bool(payload.get("restart_reconciled")):
            return "restart_reconciled", candidate_key, context
        state = self.store.current_state(event.get("room_id", "office"))
        if state is None or state.state != "occupied":
            return "room_not_occupied", candidate_key, context
        if state.camera_state not in {"online", "v4l2", "camera_online"}:
            return "source_unhealthy", candidate_key, context
        sessions = self.store.sessions(event.get("room_id", "office"), limit=10)
        current = next((item for item in sessions if item.get("status") == "open"), None)
        if current is None or current.get("session_id") != event.get("session_id"):
            return "room_not_occupied", candidate_key, context
        if now - self.started_at < timedelta(seconds=self.config.startup_suppression_seconds):
            return "startup_suppression", candidate_key, context
        if self.store.preference_value("primary_user", PREFERENCE_KEY) == "suppress":
            return "user_preference", candidate_key, context
        if counts["same_session_action_count"] >= self.config.same_session_max_actions:
            return "already_handled_session", candidate_key, context
        if counts["cooldown_active"]:
            return "cooldown", candidate_key, context
        if counts["hourly_spoken_count"] >= self.config.global_max_spoken_actions_per_hour:
            return "hourly_budget", candidate_key, context
        if getattr(self.speech, "is_speaking", False):
            return "speech_busy", candidate_key, context
        if self.weather_policy is not None:
            weather_reason, weather_context = self._weather_context(event, now)
            if weather_reason is not None:
                return weather_reason, candidate_key, context
            context["weather_context"] = weather_context
        return None, candidate_key, context

    def _weather_context(self, event: dict[str, Any], now: datetime) -> tuple[str | None, dict[str, Any] | None]:
        policy = self.weather_policy
        if policy is None:
            return None, None
        if not policy.configured:
            return "weather_unconfigured", None
        status = self.store.weather_status(policy.location_label, now=now)
        state = status.get("status")
        if state == "unavailable" or not isinstance(status.get("snapshot"), dict):
            return "weather_unavailable", None
        if state != "fresh":
            return "weather_stale", None
        snapshot = status["snapshot"]
        occurred_at = _parse_time(event.get("occurred_at")) or now
        horizon_end = occurred_at + timedelta(minutes=policy.horizon_minutes)
        periods = snapshot.get("hourly") if isinstance(snapshot.get("hourly"), list) else []
        candidates: list[dict[str, Any]] = []
        saw_overlapping_period = False
        saw_overlapping_probability = False
        for period in periods:
            if not isinstance(period, dict):
                continue
            start = _parse_time(period.get("start"))
            end = _parse_time(period.get("end"))
            if start is None:
                continue
            if end is None or end <= start:
                end = start + timedelta(hours=1)
            if start >= horizon_end or end <= occurred_at:
                continue
            saw_overlapping_period = True
            probability = period.get("precipitation_probability")
            if isinstance(probability, bool):
                continue
            try:
                probability = float(probability)
            except (TypeError, ValueError):
                continue
            if not 0 <= probability <= 100:
                continue
            saw_overlapping_probability = True
            candidates.append({
                "start": period.get("start"),
                "end": period.get("end"),
                "precipitation_probability": probability,
                "short_forecast": period.get("short_forecast") if isinstance(period.get("short_forecast"), str) else None,
            })
        if not saw_overlapping_period:
            return "weather_not_relevant", None
        if not saw_overlapping_probability or not candidates:
            return "weather_insufficient", None
        relevant = max(candidates, key=lambda item: item["precipitation_probability"])
        if relevant["precipitation_probability"] < policy.precipitation_probability_threshold:
            return "weather_not_relevant", None
        return None, {
            "status": "fresh",
            "location_label": snapshot.get("location_label", policy.location_label),
            "fetched_at": snapshot.get("fetched_at"),
            "horizon_minutes": policy.horizon_minutes,
            "threshold": policy.precipitation_probability_threshold,
            "max_precipitation_probability": relevant["precipitation_probability"],
            "earliest_relevant_period_start": relevant.get("start"),
            "forecast_period_start": relevant.get("start"),
            "forecast_period_end": relevant.get("end"),
            "short_forecast": relevant.get("short_forecast"),
        }

    def _persist_suppression(
        self, event: dict[str, Any], now: datetime, candidate_key: str, reason: str
    ) -> ProactiveOutcome:
        action_id = str(uuid.uuid4())
        claimed = self.store.claim_proactive_action(
            action_id=action_id,
            source_event_id=str(event["event_id"]), candidate_key=candidate_key,
            event_type=str(event.get("event_type", "unknown")),
            person_id=(event.get("payload") or {}).get("person_id"), session_id=event.get("session_id"),
            event_timestamp=str(event.get("occurred_at")), evaluated_at=now.isoformat(),
            eligibility_result="suppressed", suppression_reason=reason,
        )
        if not claimed:
            existing = self.store.proactive_action_for_event(str(event["event_id"]))
            return ProactiveOutcome(existing["action_id"] if existing else None, str(event["event_id"]), candidate_key, "duplicate", False, None, "suppressed")
        return ProactiveOutcome(action_id, str(event["event_id"]), candidate_key, reason, False, None, "suppressed")

    def process_event(self, event: dict[str, Any], *, now: datetime | None = None) -> ProactiveOutcome:
        evaluated_at = _utc(now or datetime.now(timezone.utc))
        event_id = str(event.get("event_id"))
        candidate_key = self._candidate_key(event)
        existing = self.store.proactive_action_for_event(event_id)
        if existing:
            return ProactiveOutcome(existing["action_id"], event_id, candidate_key, "duplicate", bool(existing.get("judge_invoked")), existing.get("judge_decision"), existing.get("delivery_status", "suppressed"), existing.get("utterance"))
        reason, candidate_key, context = self._eligibility(event, evaluated_at)
        if reason is not None:
            return self._persist_suppression(event, evaluated_at, candidate_key, reason)

        action_id = str(uuid.uuid4())
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        claimed = self.store.claim_proactive_action(
            action_id=action_id, source_event_id=event_id, candidate_key=candidate_key,
            event_type=str(event.get("event_type")), person_id=payload.get("person_id"),
            session_id=event.get("session_id"), event_timestamp=str(event.get("occurred_at")),
            evaluated_at=evaluated_at.isoformat(), eligibility_result="eligible", suppression_reason=None,
        )
        if not claimed:
            existing = self.store.proactive_action_for_event(event_id)
            return ProactiveOutcome(existing["action_id"] if existing else None, event_id, candidate_key, "duplicate", False, None, "suppressed")
        from tools.sentry_grounding import build_proactive_fact_packet
        packet = build_proactive_fact_packet(self.store, event, context, as_of=evaluated_at.isoformat())
        supplied_fact_ids = {fact["fact_id"] for fact in packet["facts"]}
        judge_invoked = True
        judge_model = "gpt-5.6-luna"
        judge_effort = self.config.judge_effort
        self.store.update_proactive_action(action_id, judge_invoked=True, judge_model=judge_model, judge_effort=judge_effort)
        started = datetime.now(timezone.utc)
        try:
            if self._judge is None:
                from tools.sentry_codex_bridge import invoke_proactive_judgment
                response = invoke_proactive_judgment(packet, effort=judge_effort, timeout_seconds=self.config.judge_timeout_seconds)
            else:
                response = self._judge(packet, effort=judge_effort, timeout_seconds=self.config.judge_timeout_seconds)
        except Exception:
            response = {"ok": False}
        latency_ms = (datetime.now(timezone.utc) - started).total_seconds() * 1000
        result = response.get("result") if isinstance(response, dict) else None
        if not isinstance(response, dict) or not response.get("ok") or validate_proactive_judgment(
            result, supplied_fact_ids, max_words=self.config.max_utterance_words, max_chars=self.config.max_utterance_chars
        ) is not None:
            self.store.update_proactive_action(
                action_id, judge_decision=None, cited_fact_ids=[], delivery_status="suppressed", suppression_reason="judge_invalid"
            )
            return ProactiveOutcome(action_id, event_id, candidate_key, "judge_invalid", judge_invoked, None, "suppressed", judge_latency_ms=latency_ms)
        cited = list(result["fact_ids"])
        if result["decision"] == "silent":
            self.store.update_proactive_action(
                action_id, judge_decision="silent", cited_fact_ids=cited, delivery_status="suppressed", suppression_reason="judge_silent"
            )
            return ProactiveOutcome(action_id, event_id, candidate_key, "judge_silent", judge_invoked, "silent", "suppressed", judge_latency_ms=latency_ms)
        utterance = result["message"].strip()
        if getattr(self.speech, "is_speaking", False):
            self.store.update_proactive_action(
                action_id, judge_decision="speak", cited_fact_ids=cited, utterance=utterance,
                delivery_status="suppressed", suppression_reason="speech_busy",
            )
            return ProactiveOutcome(action_id, event_id, candidate_key, "speech_busy", judge_invoked, "speak", "suppressed", utterance, latency_ms)
        delivered = False
        try:
            delivered = bool(self.speech.speak(utterance))
        except Exception:
            delivered = False
        if delivered:
            delivered_at = datetime.now(timezone.utc).isoformat()
            self.store.update_proactive_action(
                action_id, judge_decision="speak", cited_fact_ids=cited, utterance=utterance,
                delivery_status="delivered", delivered_at=delivered_at,
            )
            return ProactiveOutcome(action_id, event_id, candidate_key, None, judge_invoked, "speak", "delivered", utterance, latency_ms)
        self.store.update_proactive_action(
            action_id, judge_decision="speak", cited_fact_ids=cited, utterance=utterance,
            delivery_status="failed", suppression_reason="delivery_failed",
        )
        return ProactiveOutcome(action_id, event_id, candidate_key, "delivery_failed", judge_invoked, "speak", "failed", utterance, latency_ms)

    def process_pending(self, *, now: datetime | None = None, room_id: str = "office") -> list[ProactiveOutcome]:
        events = [event for event in self.store.events(room_id, limit=100) if event.get("event_type") == "person.identified"]
        events.sort(key=lambda item: str(item.get("occurred_at", "")))
        pending = [event for event in events if str(event.get("event_id")) not in self._seen_event_ids]
        outcomes = [self.process_event(event, now=now) for event in pending]
        self._seen_event_ids.update(str(event.get("event_id")) for event in pending)
        return outcomes
