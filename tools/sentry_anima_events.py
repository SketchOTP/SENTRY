"""Opt-in host event hook for the existing SENTRY session and voice.

The bounded queue callback is enabled only by the private owner-commissioned
``auto_wake`` object; it is independent of microphone listening and therefore
can wake the resident SENTRY brain for eligible household events while sleep
mode remains off.
Eligibility is selected atomically by Core, not by the model or request text.
Persistent history must never receive EPHEMERAL_RESTRICTED data; the per-turn
restriction overlay does not isolate history from subsequent broad-tool turns.
No request, response, or binding is logged by this module. Installed CLI tool
 isolation and Core context/claim policy remain required before enabling.
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

_RESULT_STATUSES = frozenset({
    "RESPONSE", "NO_ACTION", "TOOL_ACTIVITY_COMPLETED", "PARTIAL",
    "WAITING_CONFIRMATION", "WAITING_STRONGER_AUTH", "FAILED",
    "UNAVAILABLE", "UNKNOWN_RESULT",
})
_PREFLIGHT_LOCK = threading.Lock()
_VERIFIED_PREFLIGHTS: set[str] = set()

_TRIAL_FIELDS = (
    "recorded_at",
    "request_id",
    "status",
    "result_status",
    "model_status",
    "decision",
    "initiative_reason",
    "notification_allowed",
    "notification_required",
    "notification_delivery_status",
    "delivery_status",
    "stage",
    "exception_type",
    "event_occurred_at",
    "request_created_at",
    "claim_received_at",
    "provider_started_at",
    "model_started_at",
    "model_completed_at",
    "tts_requested_at",
    "tts_start_at",
    "tts_timing_source",
    "tts_completed_at",
    "immediate_delivery",
    "event_to_tts_start_ms",
    "event_to_tts_complete_ms",
    "request_to_claim_ms",
    "request_to_model_complete_ms",
    "provider_model_ms",
    "audible_start_objective",
    "contextual_response_objective",
)


def _record_operational_trial(request_id: str, receipt: dict[str, Any]) -> str:
    """Append a private, content-free event/TTS outcome when explicitly enabled."""
    configured = os.environ.get("SENTRY_ANIMA_TRIAL_LEDGER", "").strip()
    if not configured:
        return "DISABLED"
    target = Path(configured).expanduser()
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if target.parent.is_symlink() or stat.S_IMODE(target.parent.stat().st_mode) != 0o700:
        raise ValueError("TRIAL_LEDGER_PARENT_NOT_PRIVATE")
    record = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "request_id": request_id,
        **{key: receipt[key] for key in _TRIAL_FIELDS if key in receipt},
    }
    flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(target, flags, 0o600)
    try:
        with os.fdopen(descriptor, "a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise
    if stat.S_IMODE(target.stat().st_mode) != 0o600:
        raise ValueError("TRIAL_LEDGER_NOT_PRIVATE")
    return "RECORDED"


def _initiative_notification(context: Any, request_id: str, *, now: datetime | None = None) -> dict[str, Any]:
    """Validate only a host-fetched, request-bound Core disposition.

    No model text, readiness counters, or inferred urgency can grant delivery.
    Core owns observed-day thresholds and policy; this is a short-lived check,
    not a cached permission for later events. Extra context is never retained.
    """
    denied = {"allowed": False, "required": False, "reason": "UNAVAILABLE"}
    try:
        initiative = context["household_context"]["initiative"]
        notification = initiative["notification"]
        if (
            initiative["status"] != "AVAILABLE"
            or notification["request_id"] != request_id
            or type(notification["allowed"]) is not bool
            or type(notification["required"]) is not bool
            or notification["reason"] not in {
                "ALWAYS_NOTIFY", "LEARNING_REQUIRED", "PROACTIVE_DISABLED",
                "LEARNED_PROACTIVE", "REVIEW_SILENT", "UNAVAILABLE",
            }
            or not isinstance(notification["evaluated_at"], str)
        ):
            return denied
        evaluated = datetime.fromisoformat(notification["evaluated_at"])
        age = ((now or datetime.now(timezone.utc)) - evaluated).total_seconds()
        if evaluated.tzinfo is None or not -5 <= age <= 30:
            return denied
        allowed = notification["allowed"]
        required = notification["required"]
        reason = notification["reason"]
        if (
            (allowed and reason not in {"ALWAYS_NOTIFY", "LEARNED_PROACTIVE"})
            or (required and (not allowed or reason != "ALWAYS_NOTIFY"))
        ):
            return denied
        result = {key: notification[key] for key in (
            "allowed", "required", "reason", "request_id", "evaluated_at",
        )}
        announcement = notification.get("announcement")
        if announcement is not None:
            required_fields = {
                "schema_version", "text", "event_id", "event_type", "occurred_at",
                "canonical_resource_id", "canonical_resource_name", "authority",
            }
            if (
                set(announcement) != required_fields
                or announcement.get("schema_version") != 1
                or announcement.get("authority") != "ANIMA_CANONICAL_EVENT"
                or not all(
                    isinstance(announcement.get(key), str) and announcement[key]
                    for key in required_fields - {"schema_version"}
                )
                or len(announcement["text"]) > 400
            ):
                return denied
            occurred = datetime.fromisoformat(announcement["occurred_at"])
            if occurred.tzinfo is None or not -5 <= (
                (now or datetime.now(timezone.utc)) - occurred
            ).total_seconds() <= 120:
                return denied
            result["announcement"] = dict(announcement)
        return result
    except (KeyError, TypeError, ValueError, OverflowError):
        return denied


def verify_autonomous_cli(launcher: list[str], codex_home: Path, workspace: Path, profile: dict) -> None:
    """Resolve effective MCP configuration, without starting MCP or a model.

    Named profiles merge with base/project config. Reject unexpected enabled
    servers rather than assuming the profile file describes the whole runtime.
    Output stays in memory; it may contain private host configuration.
    """
    import subprocess

    from tools.sentry_codex_profile import autonomous_turn_overrides

    fingerprint = json.dumps(
        [launcher, str(codex_home), str(workspace), profile],
        sort_keys=True,
        separators=(",", ":"),
    )
    with _PREFLIGHT_LOCK:
        if fingerprint in _VERIFIED_PREFLIGHTS:
            return

    environment = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "CODEX_HOME": str(codex_home)}
    for key in ("XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME", "XDG_RUNTIME_DIR"):
        if key in os.environ:
            environment[key] = os.environ[key]
    # mcp/list does not implement strict-config and can accept keys exec rejects.
    # A private nonexistent schema is a deliberate stop after strict config load,
    # before any model, session resume, MCP startup, or request execution.
    with tempfile.TemporaryDirectory(prefix="sentry-strict-config-") as temporary:
        missing_schema = Path(temporary) / "deliberately-missing-schema.json"
        probe = subprocess.run(
            [*launcher, *autonomous_turn_overrides(profile), "--profile", "sentry-resident",
             "exec", "--strict-config", "--output-schema", str(missing_schema),
             "--json", "--skip-git-repo-check", "-"],
            cwd=workspace, env=environment, input="Configuration-only validation.",
            capture_output=True, text=True, timeout=5, check=False,
        )
        if probe.returncode == 0 or f"Failed to read output schema file {missing_schema}:" not in probe.stderr:
            raise ValueError("AUTONOMOUS_STRICT_CONFIG_UNAVAILABLE")
    result = subprocess.run(
        [*launcher, *autonomous_turn_overrides(profile), "--profile", "sentry-resident", "mcp", "list", "--json"],
        cwd=workspace, env=environment, capture_output=True, text=True, timeout=5, check=False,
    )
    if result.returncode != 0 or len(result.stdout) > 65536:
        raise ValueError("AUTONOMOUS_EFFECTIVE_CONFIG_UNAVAILABLE")
    servers = json.loads(result.stdout)
    if not isinstance(servers, list) or [item.get("name") for item in servers if item.get("enabled") is True] != ["anima_household"]:
        raise ValueError("AUTONOMOUS_UNEXPECTED_MCP_ENABLED")
    with _PREFLIGHT_LOCK:
        _VERIFIED_PREFLIGHTS.add(fingerprint)


def configured_attention_source(agent: Any) -> AttentionQueueSource | None:
    """Read host-only opt-in; never create an epoch or infer context readiness.

    Called once by the existing voice startup. Nonrestricted household context
    is owner-approved for this same persistent brain; restricted MCP data stays
    excluded. This constructor makes no service, claim, model, or speech call.
    """
    from tools.sentry_anima import AnimaConfig, private_json

    config = AnimaConfig.load()
    if config is None:
        return None
    settings = private_json(config.path).get("auto_wake", {})
    if not isinstance(settings, dict):
        raise TypeError("EVENT_AUTOWAKE_CONFIG_INVALID")
    if settings.get("enabled") is not True or settings.get("context_ready") is not True:
        return None
    if set(settings) != {"enabled", "context_ready", "enabled_at", "household_id"}:
        raise ValueError("EVENT_AUTOWAKE_CONFIG_INVALID")
    source = AttentionQueueSource(
        agent, household_id=str(settings["household_id"]),
        not_before=datetime.fromisoformat(str(settings["enabled_at"])),
        enabled=True, context_ready=True, persistent_history_allowed=True,
    )
    source.warm_runtime()
    return source


class AttentionQueueSource:
    """One eligible request per idle callback, using only the client transport.

    Core MUST implement the filtered route; never fall back to interactions/open.
    The enable epoch is host-owned and fixed for this source's lifetime. A
    transient transport failure before provider execution is safe to poll again;
    a lost result or uncertain provider execution latches this source closed
    until reviewed. There is no second agent or automatic model replay.
    """

    def __init__(
        self, agent: Any, *, household_id: str, not_before: datetime,
        enabled: bool = False, context_ready: bool = False,
        persistent_history_allowed: bool = False,
    ) -> None:
        UUID(household_id)
        if not_before.tzinfo is None or not_before.utcoffset() is None:
            raise ValueError("EVENT_ENABLE_EPOCH_REQUIRES_TIMEZONE")
        self.agent = agent
        self.household_id = household_id
        self.not_before = not_before.astimezone(timezone.utc)
        self.enabled = enabled
        self.context_ready = context_ready
        # Owner permits nonrestricted household context in the same thread.
        # This host input never overrides the persistent MCP restricted gate.
        self.persistent_history_allowed = persistent_history_allowed
        self._halted = False
        self._lock = threading.Lock()
        self._ready_lock = threading.Lock()
        self._available_candidate: dict[str, Any] | None = None

    def warm_runtime(self) -> None:
        """Qualify the CLI/profile at voice startup, before any event is claimed."""
        import tomllib

        from tools.sentry_codex_agent import (
            _default_workspace,
            _launcher_args,
            _resident_codex_home,
        )

        workspace = Path(
            os.environ.get("SENTRY_AGENT_WORKSPACE", _default_workspace())
        ).expanduser().resolve()
        launcher = _launcher_args()
        if launcher is None or not workspace.is_dir():
            raise ValueError("RESIDENT_EXECUTOR_UNAVAILABLE")
        codex_home = _resident_codex_home()
        profile = tomllib.loads((codex_home / "sentry-resident.config.toml").read_text())
        verify_autonomous_cli(launcher, codex_home, workspace, profile)

    def _filters(self) -> dict[str, Any]:
        return {
            "origin": "AUTONOMOUS_ATTENTION",
            "not_before": self.not_before.isoformat(),
            "max_age_seconds": 120,
        }

    def wait_until_ready(self, stop_event: threading.Event) -> bool:
        """Block on Core's authenticated push channel; never contact the model."""
        if self._halted or stop_event.is_set():
            return False
        with self._ready_lock:
            if self._available_candidate is not None:
                stop_event.wait(0.05)
                return not stop_event.is_set()
        try:
            from tools.sentry_anima import AnimaConfig

            config = AnimaConfig.load()
            if config is None:
                stop_event.wait(1.0)
                return False
            listing = config.client().wait_eligible(
                {**self._filters(), "limit": 1}, wait_seconds=25
            )
            if listing == {"status": "EMPTY", "items": []}:
                return False
            items = listing.get("items")
            if listing.get("status") != "AVAILABLE" or not isinstance(items, list) or len(items) != 1:
                raise ValueError("EVENT_QUEUE_CONTRACT_MISMATCH")
            candidate = items[0]
            self._validate_candidate(candidate)
            with self._ready_lock:
                self._available_candidate = candidate
            return True
        except Exception as exc:  # noqa: BLE001 - a push transport failure is pre-provider
            if not _retryable_pre_provider_failure(exc):
                self._halted = True
            stop_event.wait(1.0)
            return False

    def _claim_next(self, client: Any, correlation_id: str, source_surface: str) -> dict[str, Any]:
        filters = self._filters()
        with self._ready_lock:
            candidate = self._available_candidate
            self._available_candidate = None
        if candidate is None:
            listing = client.call("/v1/provider/requests/eligible", {**filters, "limit": 1})
            if listing == {"status": "EMPTY", "items": []}:
                return {"status": "EMPTY"}
            items = listing.get("items")
            if (
                listing.get("status") != "AVAILABLE"
                or not isinstance(items, list)
                or len(items) != 1
            ):
                raise ValueError("EVENT_QUEUE_CONTRACT_MISMATCH")
            candidate = items[0]
            self._validate_candidate(candidate)
        claim = client.call("/v1/provider/claims/exact", {
            **filters,
            "request_id": candidate["request_id"],
            "worker_id": client.worker_id,
            "sentry_request_id": correlation_id,
            "source_surface": source_surface,
        })
        if claim.get("status") == "EMPTY":
            return claim
        self._validate_candidate(claim)
        if (
            claim.get("status") != "CLAIMED"
            or claim.get("request_id") != candidate["request_id"]
            or claim.get("provider_started") is not False
        ):
            raise ValueError("EVENT_QUEUE_CONTRACT_MISMATCH")
        return claim

    def _validate_candidate(self, value: dict[str, Any]) -> None:
        created = datetime.fromisoformat(str(value.get("created_at", "")))
        now = datetime.now(timezone.utc)
        if (
            value.get("origin") != "AUTONOMOUS_ATTENTION"
            or value.get("household_id") != self.household_id
            or value.get("provider_id") != "sentry"
            or created.tzinfo is None or created < self.not_before
            or not timedelta(0) <= now - created <= timedelta(seconds=120)
        ):
            raise ValueError("EVENT_QUEUE_CONTRACT_MISMATCH")
        UUID(value["request_id"])

    def __call__(
        self,
        *,
        speaker: Any = None,
        on_work_started: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        not_ready = {"status": "NOT_READY", "delivery_status": "NOT_ATTEMPTED"}
        if not self._lock.acquire(blocking=False):
            return {**not_ready, "gate": "EVENT_SOURCE_BUSY"}
        try:
            if self._halted:
                return {**not_ready, "gate": "EVENT_SOURCE_REVIEW_REQUIRED"}
            try:
                result = run_resident_event(
                    self.agent, request_id=None, household_id=self.household_id,
                    claim_next=self._claim_next, speaker=speaker,
                    enabled=self.enabled, context_ready=self.context_ready,
                    persistent_history_allowed=self.persistent_history_allowed,
                    on_work_started=on_work_started,
                )
            except Exception as exc:  # noqa: BLE001 - never retry an ambiguous claim
                if _retryable_pre_provider_failure(exc):
                    return {
                        **not_ready,
                        "gate": "EVENT_CORE_TEMPORARILY_UNAVAILABLE",
                        "exception_type": type(exc).__name__,
                    }
                self._halted = True
                return {"status": "UNKNOWN_RESULT", "delivery_status": "NOT_ATTEMPTED",
                        "stage": "EVENT_SOURCE", "exception_type": type(exc).__name__}
            if result.get("status") == "UNKNOWN_RESULT" or result.get("result_status") == "UNKNOWN_RESULT":
                self._halted = True
            return result
        finally:
            self._lock.release()


def _retryable_pre_provider_failure(exc: Exception) -> bool:
    """Classify only failures that occur before provider/model execution.

    This helper is used solely by ``AttentionQueueSource`` around setup and
    queue claim. ``QueuedEventLease`` contains every post-provider-start error
    and returns UNKNOWN_RESULT, which remains permanently latched above.
    """

    transport_code = getattr(exc, "transport_code", None)
    http_status = getattr(exc, "http_status", None)
    return (
        isinstance(exc, (ConnectionError, TimeoutError, OSError))
        or transport_code in {
            "TIMEOUT",
            "REMOTE_DISCONNECTED",
            "CONNECTION_REFUSED",
            "CONNECTION_RESET",
            "SOCKET_NOT_FOUND",
            "HTTP_PROTOCOL_ERROR",
            "OS_ERROR",
            "TRANSPORT_ERROR",
        }
        or (type(http_status) is int and (http_status in {408, 425, 429} or 500 <= http_status <= 599))
    )


def validate_event_binding(path: Path, profile: dict, workspace: Path, request_id: str | None) -> dict:
    """Validate host private binding without trusting a model-supplied path."""
    from tools.sentry_anima import (
        AnimaConfig,
        binding_root,
        filesystem_denies,
        private_json,
    )

    config = AnimaConfig.load()
    if config is None:
        raise ValueError("EVENT_CONFIG_UNAVAILABLE")
    config.validate_workspace(workspace)
    value = private_json(path)
    filesystem = profile.get("permissions", {}).get("sentry-resident", {}).get("filesystem", {})
    expires = datetime.fromisoformat(str(value.get("expires_at", "")))
    parent = path.parent.stat()
    if (
        not path.is_absolute() or not path.resolve().is_relative_to(binding_root().resolve())
        or parent.st_uid != os.geteuid() or stat.S_IMODE(parent.st_mode) != 0o700
        or value.get("version") != 1 or value.get("persistent_thread") is not True
        or value.get("source_surface") != "anima_attention"
        or value.get("sentry_request_id") != request_id
        or value.get("endpoint") != config.endpoint or value.get("token_file") != str(config.token_file)
        or value.get("worker_id") != config.worker_id
        or value.get("workspace_root") != str(workspace.resolve())
        or not isinstance(value.get("binding"), str) or not value["binding"]
        or expires.tzinfo is None or not 0 < (expires - datetime.now(timezone.utc)).total_seconds() <= 270
        or profile.get("mcp_servers", {}).get("anima_household", {}).get("args")
        != [str(config.client_directory / "anima_household_mcp.py")]
        or any(not filesystem_denies(filesystem, target) for target in (config.path, config.token_file, path))
    ):
        raise ValueError("EVENT_BINDING_INVALID")
    UUID(value["request_id"])
    return value


@dataclass(frozen=True)
class EventResult:
    status: str
    response: str | None = None
    detail: str | None = None


class QueuedEventLease:
    """One-shot fencing/lease coordination, dormant until explicitly called."""

    def __init__(
        self, client: Any, claim: dict[str, Any], *, expected_request_id: str,
        household_id: str, deadline: float, revoke: Callable[[], None],
    ) -> None:
        if (
            claim.get("status") != "CLAIMED"
            or claim.get("origin") != "AUTONOMOUS_ATTENTION"
            or claim.get("provider_id") != "sentry"
            or claim.get("request_id") != expected_request_id
            or claim.get("household_id") != household_id
            or type(claim.get("fencing_generation")) is not int
            or claim["fencing_generation"] < 1
            or not isinstance(claim.get("binding"), str)
            or not claim["binding"]
            or not 0 < deadline - time.monotonic() <= 270
        ):
            raise ValueError("EVENT_CLAIM_INVALID")
        UUID(expected_request_id)
        UUID(household_id)
        self.client = client
        self.request_id = expected_request_id
        self._binding = claim["binding"]
        self.deadline = deadline
        self.cancelled = threading.Event()
        self._stop = threading.Event()
        self._revoke_callback = revoke
        self._revoke_lock = threading.Lock()
        self._run_lock = threading.Lock()
        self._revoked = False
        self._attempted = False
        self._failure: dict[str, str] = {}

    @property
    def remaining_seconds(self) -> float:
        return max(0.0, self.deadline - time.monotonic() - 15)

    def _revoke(self) -> None:
        with self._revoke_lock:
            if self._revoked:
                return
            self._revoked = True
            try:
                self._revoke_callback()
            except Exception as exc:  # noqa: BLE001 - cleanup failure must invalidate success
                self.cancelled.set()
                self._failure = {"stage": "REVOKE", "exception_type": type(exc).__name__}

    def _renew(self) -> None:
        while not self._stop.wait(min(15.0, self.remaining_seconds)):
            try:
                if self.remaining_seconds <= 0:
                    raise TimeoutError
                value = self.client.renew(self.request_id, self._binding)
                if value.get("status") != "RENEWED":
                    raise RuntimeError
            except Exception as exc:  # noqa: BLE001 - any transport failure revokes the binding
                self._failure = {"stage": "LEASE_RENEW", "exception_type": type(exc).__name__}
                self.cancelled.set()
                self._revoke()
                return

    def run(
        self,
        execute: Callable[[QueuedEventLease], EventResult],
        *,
        after_provider_start: Callable[[], None] | None = None,
        telemetry: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Caller owns executor qualification and the resident session lock.

        Client calls must have bounded transport timeouts (the host client uses
        two seconds). Result recording is not speech delivery. Never retry this
        object, even after a transport error or an ambiguous provider start.
        """
        with self._run_lock:
            if self._attempted:
                raise RuntimeError("EVENT_ALREADY_ATTEMPTED")
            self._attempted = True
        renewal = None
        outcome = EventResult("UNKNOWN_RESULT")
        stage = "PROVIDER_START"
        try:
            if self.remaining_seconds <= 0:
                raise TimeoutError
            started = self.client.provider_start(self.request_id, self._binding)
            if started.get("status") != "PROVIDER_RUNNING":
                raise RuntimeError
            if telemetry is not None:
                telemetry["provider_started_at"] = datetime.now(timezone.utc).isoformat()
            if after_provider_start is not None:
                after_provider_start()
            if self.remaining_seconds <= 0:
                raise TimeoutError
            stage = "EXECUTE"
            renewal = threading.Thread(target=self._renew, daemon=True, name="sentry-event-lease")
            renewal.start()
            outcome = execute(self)
            if (
                not isinstance(outcome, EventResult)
                or outcome.status not in _RESULT_STATUSES
                or (outcome.response is not None and (
                    not isinstance(outcome.response, str) or len(outcome.response) > 4000
                ))
                or (outcome.status == "RESPONSE" and not (outcome.response or "").strip())
                or (outcome.detail is not None and (
                    outcome.status != "PARTIAL" or outcome.detail != "REQUIRED_NOTIFICATION_NOT_PRODUCED"
                ))
            ):
                raise ValueError
        except Exception as exc:  # noqa: BLE001 - executor ambiguity is terminal, never replayed
            self._failure = {"stage": stage, "exception_type": type(exc).__name__}
            self.cancelled.set()
        finally:
            self._stop.set()
            if renewal is not None:
                renewal.join(timeout=3)
                if renewal.is_alive():
                    self.cancelled.set()
            self._revoke()
        if self.cancelled.is_set() or time.monotonic() >= self.deadline:
            outcome = EventResult("UNKNOWN_RESULT")
        if outcome.status == "UNKNOWN_RESULT":
            outcome = EventResult("UNKNOWN_RESULT")
        receipt = "UNKNOWN_RESULT"
        recorded_status = outcome.status
        notification = _initiative_notification({}, self.request_id)
        try:
            value = self.client.submit_result(
                self.request_id, self._binding, status=outcome.status,
                response=outcome.response, provider_ambiguous=outcome.status == "UNKNOWN_RESULT",
                **({"detail": outcome.detail} if outcome.detail is not None else {}),
            )
            if value.get("status") == "RECORDED":
                receipt = "RECORDED"
                actual = value.get("result_status")
                if isinstance(actual, str) and actual in _RESULT_STATUSES:
                    recorded_status = actual
                elif "result_status" in value or outcome.status == "RESPONSE":
                    # Legacy receipts cannot authorize autonomous speech. Keep
                    # non-response compatibility, never invent recorded success.
                    recorded_status = "UNKNOWN_RESULT"
                if outcome.status == "RESPONSE":
                    notification = _initiative_notification(
                        {"household_context": {"initiative": {
                            "status": "AVAILABLE", "notification": value.get("notification"),
                        }}}, self.request_id,
                    )
        except Exception as exc:  # noqa: BLE001 - result transport ambiguity must not be retried
            self._failure = {"stage": "RESULT_SUBMIT", "exception_type": type(exc).__name__}
        finally:
            self._binding = ""
        return {
            "status": receipt, "result_status": recorded_status,
            "notification": notification,
            **({"detail": outcome.detail} if outcome.detail is not None else {}),
            "delivery_status": "NOT_ATTEMPTED", **self._failure,
            **(telemetry or {}),
        }


def run_resident_event(
    agent: Any, *, request_id: str | None, household_id: str,
    claim_exact: Callable[[str, str], dict[str, Any]] | None = None,
    claim_next: Callable[[Any, str, str], dict[str, Any]] | None = None,
    speaker: Any = None,
    enabled: bool = False, context_ready: bool = False,
    persistent_history_allowed: bool = False, runner: Callable[..., Any] | None = None,
    on_work_started: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Explicit same-resident hook; no polling or production enablement.

    The three gates are trusted host commissioning inputs, never event/model
    fields. claim_exact must atomically claim ONLY this eligible, never-started
    Attention request. Its Core transport contract is owned by the integration
    lead. Do not supply the unfiltered open_interaction method here.
    """
    import tomllib

    from tools.sentry_anima import (
        AnimaConfig,
        binding_root,
        filesystem_denies,
        private_json,
    )
    from tools.sentry_codex_agent import (
        _default_workspace,
        _launcher_args,
        _resident_codex_home,
        invoke_sentry_agent,
    )
    from tools.sentry_codex_profile import autonomous_turn_overrides

    blocked = {"status": "NOT_READY", "delivery_status": "NOT_ATTEMPTED"}
    for name, passed in (
        ("AUTONOMY_DISABLED", enabled), ("CONTEXT_NOT_COMMISSIONED", context_ready),
        ("PERSISTENT_HISTORY_NOT_APPROVED", persistent_history_allowed),
    ):
        if passed is not True:
            return {**blocked, "gate": name}
    if (claim_next is None) == (claim_exact is None) or (request_id is None) != (claim_next is not None):
        raise ValueError("EVENT_CLAIM_SOURCE_INVALID")
    correlation_id = request_id or str(uuid4())
    UUID(correlation_id)
    UUID(household_id)
    config = AnimaConfig.load()
    if config is None:
        return {**blocked, "gate": "ANIMA_DISABLED"}
    workspace = Path(os.environ.get("SENTRY_AGENT_WORKSPACE", _default_workspace())).expanduser().resolve()
    config.validate_workspace(workspace)
    profile = tomllib.loads((_resident_codex_home() / "sentry-resident.config.toml").read_text())
    autonomous_turn_overrides(profile)
    # All deterministic local setup and secret-file access precede queue mutation.
    launcher = _launcher_args()
    if not workspace.is_dir() or launcher is None:
        return {**blocked, "gate": "RESIDENT_EXECUTOR_UNAVAILABLE"}
    verify_autonomous_cli(launcher, _resident_codex_home(), workspace, profile)
    schema = Path(__file__).with_name("sentry_anima_event_response.schema.json")
    json.loads(schema.read_text(encoding="utf-8"))
    client = config.client()
    root = binding_root()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = root.stat()
    filesystem = profile["permissions"]["sentry-resident"]["filesystem"]
    if (
        info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700 or root.is_symlink()
        or profile["mcp_servers"]["anima_household"].get("args") != [str(config.client_directory / "anima_household_mcp.py")]
        or not (config.client_directory / "anima_household_mcp.py").is_file()
        or any(not filesystem_denies(filesystem, target) for target in (config.path, config.token_file, root))
    ):
        raise ValueError("EVENT_PREFLIGHT_INVALID")
    # One resident lock before any claim; never call ask() and re-acquire it.
    with agent.session_store.locked():
        session = agent.session_store.load()
        thread_id = session.get("thread_id")
        if not thread_id:
            return {**blocked, "gate": "RESIDENT_THREAD_UNAVAILABLE"}
        with tempfile.TemporaryDirectory(prefix="event-", dir=root) as temporary:
            path = Path(temporary) / "binding.json"
            # Allocate both private files before claiming (permissions/disk failure).
            preload_targets = (
                path,
                path.with_name("metadata.json"),
                path.with_name("health.json"),
                path.with_name("context.json"),
                path.with_name("tools.json"),
            )
            for target in preload_targets:
                with open(target, "x", encoding="utf-8", opener=lambda p, f: os.open(p, f, 0o600)) as stream:
                    stream.write("{}")
            deadline = time.monotonic() + 270
            claim = (
                claim_next(client, correlation_id, "anima_attention") if claim_next is not None
                else claim_exact(correlation_id, "anima_attention")
            )
            if claim.get("status") == "EMPTY":
                return {"status": "EMPTY", "delivery_status": "NOT_ATTEMPTED"}
            if claim_next is not None:
                request_id = claim["request_id"]
            lease = QueuedEventLease(
                client, claim, expected_request_id=request_id, household_id=household_id,
                deadline=deadline, revoke=lambda: path.unlink(missing_ok=True),
            )
            value = {
                "version": 1, "request_id": request_id, "binding": claim["binding"],
                "sentry_request_id": correlation_id, "source_surface": "anima_attention",
                "endpoint": config.endpoint, "token_file": str(config.token_file),
                "worker_id": config.worker_id, "persistent_thread": True,
                "workspace_root": str(workspace),
                "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=max(0, deadline - time.monotonic()))).isoformat(),
            }
            for target, payload in (
                (path, value), (path.with_name("metadata.json"), {"version": 1, "status": "READY", "calls": 0}),
            ):
                with open(target, "w", encoding="utf-8") as stream:
                    json.dump(payload, stream)
            validate_event_binding(path, profile, workspace, correlation_id)
            final: dict[str, Any] = {}
            telemetry: dict[str, Any] = {
                "request_created_at": str(claim.get("created_at", "")),
                "claim_received_at": datetime.now(timezone.utc).isoformat(),
                "immediate_delivery": False,
            }
            try:
                request_created = datetime.fromisoformat(telemetry["request_created_at"])
                claim_received = datetime.fromisoformat(telemetry["claim_received_at"])
                telemetry["request_to_claim_ms"] = round(
                    (claim_received - request_created).total_seconds() * 1000, 3
                )
            except (TypeError, ValueError):
                pass
            try:
                health = client.call("/v1/health")
                context = client.context(request_id, claim["binding"])
                tools = client.tools(request_id, claim["binding"])
            except Exception as exc:  # noqa: BLE001 - provider has not started; reclaim stays safe
                return {
                    **blocked,
                    "gate": "EVENT_PRELOAD_UNAVAILABLE",
                    "exception_type": type(exc).__name__,
                }
            initiative = _initiative_notification(context, request_id)
            announcement = initiative.get("announcement")
            if isinstance(announcement, dict):
                telemetry["event_occurred_at"] = announcement["occurred_at"]
            for target, payload in (
                (path.with_name("health.json"), health),
                (path.with_name("context.json"), context),
                (path.with_name("tools.json"), tools),
            ):
                encoded = json.dumps(
                    {"version": 1, "request_id": request_id, "value": payload},
                    sort_keys=True,
                    separators=(",", ":"),
                )
                if len(encoded.encode()) > 512 * 1024:
                    raise ValueError("EVENT_PRELOAD_TOO_LARGE")
                target.write_text(encoded, encoding="utf-8")
                target.chmod(0o600)
            immediate: dict[str, Any] = {
                "attempted": False,
                "delivered": False,
                "thread": None,
            }

            def deliver_immediate() -> None:
                if (
                    not isinstance(announcement, dict)
                    or initiative.get("allowed") is not True
                    or initiative.get("required") is not True
                    or initiative.get("reason") != "ALWAYS_NOTIFY"
                    or speaker is None
                    or getattr(speaker, "is_speaking", False)
                ):
                    return
                immediate["attempted"] = True

                def speak() -> None:
                    telemetry["tts_requested_at"] = datetime.now(timezone.utc).isoformat()
                    try:
                        timed_speech = getattr(speaker, "speak_with_timing", None)
                        if callable(timed_speech):
                            delivery = timed_speech(announcement["text"])
                        else:
                            delivery = None
                        if isinstance(delivery, dict):
                            immediate["delivered"] = delivery.get("delivered") is True
                            if isinstance(delivery.get("tts_start_at"), str):
                                telemetry["tts_start_at"] = delivery["tts_start_at"]
                                telemetry["tts_timing_source"] = delivery.get("timing_source")
                        else:
                            # Compatibility speakers expose invocation timing only;
                            # production Kokoro records the playback-owned timestamp.
                            telemetry["tts_start_at"] = telemetry["tts_requested_at"]
                            telemetry["tts_timing_source"] = "HOST_SPEAK_INVOCATION"
                            immediate["delivered"] = bool(speaker.speak(announcement["text"]))
                    except Exception as exc:  # noqa: BLE001 - speech cannot replay provider work
                        immediate["exception_type"] = type(exc).__name__
                    finally:
                        telemetry["tts_completed_at"] = datetime.now(timezone.utc).isoformat()

                immediate["thread"] = threading.Thread(
                    target=speak,
                    daemon=True,
                    name="sentry-immediate-alert",
                )
                immediate["thread"].start()

            def execute(active: QueuedEventLease) -> EventResult:
                if on_work_started is not None:
                    on_work_started()
                telemetry["model_started_at"] = datetime.now(timezone.utc).isoformat()
                invocation = invoke_sentry_agent(
                    "ANIMA autonomous Attention event", [], session_id=thread_id,
                    working_directory=workspace, request_id=correlation_id,
                    timeout_seconds=max(1, int(active.remaining_seconds)),
                    autonomous_binding=path,
                    effort="low",
                    runner=runner or (lambda args, **kwargs: _event_process(args, active, **kwargs)),
                )
                telemetry["model_completed_at"] = datetime.now(timezone.utc).isoformat()
                if not invocation.get("ok") or invocation.get("thread_id", thread_id) not in {None, thread_id}:
                    return EventResult("UNKNOWN_RESULT")
                final.update(invocation["result"])
                decision = final.get("decision")
                answer = final.get("answer")
                if decision not in {"silent", "speak", "notify"} or (decision == "speak" and not isinstance(answer, str)):
                    return EventResult("UNKNOWN_RESULT")
                metadata = private_json(path.with_name("metadata.json"))
                if metadata.get("version") != 1 or type(metadata.get("calls")) is not int or not 0 <= metadata["calls"] <= 8:
                    return EventResult("UNKNOWN_RESULT")
                status = metadata.get("status")
                if status in {"WAITING_CONFIRMATION", "WAITING_STRONGER_AUTH", "UNKNOWN_RESULT", "UNAVAILABLE", "FAILED", "PARTIAL"}:
                    return EventResult(status)
                model_status = final.get("status")
                if model_status == "unavailable":
                    return EventResult("UNAVAILABLE")
                if model_status == "partial":
                    return EventResult("PARTIAL")
                if status not in {"READY", "SUCCEEDED"} or model_status != "completed":
                    return EventResult("PARTIAL")
                immediate_thread = immediate.get("thread")
                if isinstance(immediate_thread, threading.Thread):
                    immediate_thread.join(timeout=30)
                required_unproduced = (
                    decision == "silent"
                    and initiative["required"]
                    and not immediate["delivered"]
                )
                session["turn_count"] = int(session.get("turn_count", 0)) + 1
                session["updated_at"] = datetime.now(timezone.utc).isoformat()
                session["last_status"] = "autonomous_partial" if required_unproduced else "autonomous_completed"
                agent.session_store.save(session)
                if decision == "silent":
                    if required_unproduced:
                        return EventResult("PARTIAL", detail="REQUIRED_NOTIFICATION_NOT_PRODUCED")
                    if immediate["delivered"] and isinstance(announcement, dict):
                        return EventResult("RESPONSE", announcement["text"])
                    return EventResult("NO_ACTION")
                # Notification tools must also enforce this in Core BEFORE
                # dispatch: a host final guard cannot undo an earlier MCP call.
                if not initiative["allowed"]:
                    return EventResult("PARTIAL" if decision == "notify" else "NO_ACTION")
                if decision == "notify":
                    # Tool success alone cannot prove notification delivery.
                    if immediate["delivered"] and isinstance(announcement, dict):
                        return EventResult("RESPONSE", announcement["text"])
                    return EventResult("TOOL_ACTIVITY_COMPLETED" if status == "SUCCEEDED" else "PARTIAL")
                if (
                    immediate["delivered"]
                    and isinstance(announcement, dict)
                    and " ".join(str(answer).lower().split())
                    == " ".join(announcement["text"].lower().split())
                ):
                    return EventResult("RESPONSE", announcement["text"])
                return EventResult("RESPONSE", answer)

            receipt = lease.run(
                execute,
                after_provider_start=deliver_immediate,
                telemetry=telemetry,
            )
            immediate_thread = immediate.get("thread")
            if isinstance(immediate_thread, threading.Thread):
                immediate_thread.join(timeout=30)
            if telemetry.get("model_started_at") and telemetry.get("model_completed_at"):
                telemetry["provider_model_ms"] = round(
                    (
                        datetime.fromisoformat(telemetry["model_completed_at"])
                        - datetime.fromisoformat(telemetry["model_started_at"])
                    ).total_seconds()
                    * 1000,
                    3,
                )
            if telemetry.get("request_created_at") and telemetry.get("model_completed_at"):
                try:
                    request_at = datetime.fromisoformat(telemetry["request_created_at"])
                    model_at = datetime.fromisoformat(telemetry["model_completed_at"])
                    response_ms = round((model_at - request_at).total_seconds() * 1000, 3)
                    telemetry["request_to_model_complete_ms"] = response_ms
                    if not immediate["delivered"]:
                        telemetry["contextual_response_objective"] = (
                            "MET" if response_ms <= 12_000 else "MISSED"
                        )
                except (TypeError, ValueError):
                    pass
            if telemetry.get("event_occurred_at") and telemetry.get("tts_start_at"):
                event_at = datetime.fromisoformat(telemetry["event_occurred_at"])
                tts_start = datetime.fromisoformat(telemetry["tts_start_at"])
                start_ms = round((tts_start - event_at).total_seconds() * 1000, 3)
                telemetry["event_to_tts_start_ms"] = start_ms
                telemetry["audible_start_objective"] = "MET" if start_ms <= 3000 else "MISSED"
            if telemetry.get("event_occurred_at") and telemetry.get("tts_completed_at"):
                telemetry["event_to_tts_complete_ms"] = round(
                    (
                        datetime.fromisoformat(telemetry["tts_completed_at"])
                        - datetime.fromisoformat(telemetry["event_occurred_at"])
                    ).total_seconds()
                    * 1000,
                    3,
                )
            receipt.update(telemetry)
            receipt["immediate_delivery"] = bool(immediate["delivered"])
            receipt["decision"] = final.get("decision")
            if final.get("status") in {"completed", "partial", "unavailable"}:
                receipt["model_status"] = final["status"]
            # Permission comes from the authenticated result response. Never
            # fall back to the snapshot read before submission/settings changes.
            returned_notification = receipt.pop("notification")
            receipt["initiative_reason"] = initiative["reason"]
            receipt["notification_allowed"] = initiative["allowed"]
            receipt["notification_required"] = initiative["required"]
            if not initiative["allowed"]:
                receipt["delivery_status"] = "BLOCKED_INITIATIVE"
            if final.get("decision") == "notify":
                # The sidecar aggregates tool status, not a route-specific
                # delivery receipt. Never turn a model decision into delivery.
                receipt["notification_delivery_status"] = "NOT_VERIFIED"
            if immediate["delivered"]:
                receipt["delivery_status"] = "DELIVERED"
            elif immediate["attempted"]:
                receipt["delivery_status"] = "FAILED"
                if immediate.get("exception_type"):
                    receipt.update(stage="TTS", exception_type=immediate["exception_type"])
            if (
                final.get("decision") == "speak"
                and initiative.get("allowed")
                and receipt["status"] == "RECORDED"
                and not immediate["delivered"]
            ):
                current = _initiative_notification(
                    {"household_context": {"initiative": {"status": "AVAILABLE", "notification": returned_notification}}},
                    request_id,
                )
                receipt["initiative_reason"] = current["reason"]
                if not current["allowed"]:
                    receipt["delivery_status"] = "BLOCKED_INITIATIVE"
                elif receipt["result_status"] != "RESPONSE" or speaker is None:
                    pass
                elif getattr(speaker, "is_speaking", False):
                    receipt["delivery_status"] = "BUSY_NOT_DELIVERED"
                else:
                    try:
                        delivered = bool(speaker.speak(final["answer"]))
                        receipt["delivery_status"] = "DELIVERED" if delivered else "FAILED"
                    except Exception as exc:  # noqa: BLE001 - delivery cannot turn into model replay
                        receipt.update(delivery_status="FAILED", stage="TTS", exception_type=type(exc).__name__)
            receipt["trial_record_status"] = _record_operational_trial(request_id, receipt)
            return receipt


def _event_process(args: list[str], lease: QueuedEventLease, **kwargs: Any) -> Any:
    """Existing CLI process only, cancelled with its MCP children on lease loss."""
    import signal
    import subprocess

    prompt = kwargs.pop("input")
    timeout = kwargs.pop("timeout")
    kwargs.pop("capture_output", None)
    kwargs.pop("check", None)
    if lease.cancelled.is_set() or lease.remaining_seconds <= 0:
        raise subprocess.TimeoutExpired(args, timeout)
    started = time.monotonic()
    process = subprocess.Popen(
        args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        start_new_session=True, **kwargs,
    )
    try:
        while True:
            if lease.cancelled.is_set() or lease.remaining_seconds <= 0 or time.monotonic() - started >= timeout:
                raise subprocess.TimeoutExpired(args, timeout)
            try:
                stdout, stderr = process.communicate(input=prompt, timeout=0.25)
                return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)
            except subprocess.TimeoutExpired:
                prompt = None
    finally:
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=0.5)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=2)
        for pipe in (process.stdin, process.stdout, process.stderr):
            if pipe is not None:
                pipe.close()
