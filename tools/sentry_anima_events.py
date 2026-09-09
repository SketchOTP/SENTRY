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
        return {key: notification[key] for key in (
            "allowed", "required", "reason", "request_id", "evaluated_at",
        )}
    except (KeyError, TypeError, ValueError, OverflowError):
        return denied


def _fetch_initiative(client: Any, request_id: str, binding: str) -> dict[str, Any]:
    try:
        return _initiative_notification(client.context(request_id, binding), request_id)
    except Exception:  # noqa: BLE001 - missing authority blocks delivery, not silent reasoning
        return {"allowed": False, "required": False, "reason": "UNAVAILABLE"}


def verify_autonomous_cli(launcher: list[str], codex_home: Path, workspace: Path, profile: dict) -> None:
    """Resolve effective MCP configuration, without starting MCP or a model.

    Named profiles merge with base/project config. Reject unexpected enabled
    servers rather than assuming the profile file describes the whole runtime.
    Output stays in memory; it may contain private host configuration.
    """
    import subprocess

    from tools.sentry_codex_profile import autonomous_turn_overrides

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
    return AttentionQueueSource(
        agent, household_id=str(settings["household_id"]),
        not_before=datetime.fromisoformat(str(settings["enabled_at"])),
        enabled=True, context_ready=True, persistent_history_allowed=True,
    )


class AttentionQueueSource:
    """One eligible request per idle callback, using only the client transport.

    Core MUST implement the filtered route; never fall back to interactions/open.
    The enable epoch is host-owned and fixed for this source's lifetime. A lost
    response or uncertain execution latches this source closed until reviewed.
    There is no background thread, second agent, or automatic recovery/replay.
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
        self._next_poll = 0.0
        self._halted = False
        self._lock = threading.Lock()

    def _claim_next(self, client: Any, correlation_id: str, source_surface: str) -> dict[str, Any]:
        filters = {
            "origin": "AUTONOMOUS_ATTENTION",
            "not_before": self.not_before.isoformat(),
            "max_age_seconds": 120,
        }
        listing = client.call("/v1/provider/requests/eligible", {**filters, "limit": 1})
        if listing == {"status": "EMPTY", "items": []}:
            return {"status": "EMPTY"}
        items = listing.get("items")
        if listing.get("status") != "AVAILABLE" or not isinstance(items, list) or len(items) != 1:
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
            if time.monotonic() < self._next_poll:
                return {
                    "status": "EMPTY",
                    "delivery_status": "NOT_ATTEMPTED",
                    "gate": "EVENT_POLL_INTERVAL",
                }
            self._next_poll = time.monotonic() + 15.0
            try:
                result = run_resident_event(
                    self.agent, request_id=None, household_id=self.household_id,
                    claim_next=self._claim_next, speaker=speaker,
                    enabled=self.enabled, context_ready=self.context_ready,
                    persistent_history_allowed=self.persistent_history_allowed,
                    on_work_started=on_work_started,
                )
            except Exception as exc:  # noqa: BLE001 - never retry an ambiguous claim
                self._halted = True
                return {"status": "UNKNOWN_RESULT", "delivery_status": "NOT_ATTEMPTED",
                        "stage": "EVENT_SOURCE", "exception_type": type(exc).__name__}
            if result.get("status") == "UNKNOWN_RESULT" or result.get("result_status") == "UNKNOWN_RESULT":
                self._halted = True
            return result
        finally:
            self._lock.release()


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

    def run(self, execute: Callable[[QueuedEventLease], EventResult]) -> dict[str, Any]:
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
            for target in (path, path.with_name("metadata.json")):
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
            initiative: dict[str, Any] = {}

            def execute(active: QueuedEventLease) -> EventResult:
                if on_work_started is not None:
                    on_work_started()
                invocation = invoke_sentry_agent(
                    "ANIMA autonomous Attention event", [], session_id=thread_id,
                    working_directory=workspace, request_id=correlation_id,
                    timeout_seconds=max(1, int(active.remaining_seconds)),
                    autonomous_binding=path,
                    runner=runner or (lambda args, **kwargs: _event_process(args, active, **kwargs)),
                )
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
                # Fetch even for silence: a required notification cannot be
                # reported as handled merely because the model chose no channel.
                # Core/prefs decide permission; host never manufactures speech.
                initiative.update(_fetch_initiative(client, request_id, claim["binding"]))
                required_unproduced = decision == "silent" and initiative["required"]
                session["turn_count"] = int(session.get("turn_count", 0)) + 1
                session["updated_at"] = datetime.now(timezone.utc).isoformat()
                session["last_status"] = "autonomous_partial" if required_unproduced else "autonomous_completed"
                agent.session_store.save(session)
                if decision == "silent":
                    if required_unproduced:
                        return EventResult("PARTIAL", detail="REQUIRED_NOTIFICATION_NOT_PRODUCED")
                    return EventResult("NO_ACTION")
                # Notification tools must also enforce this in Core BEFORE
                # dispatch: a host final guard cannot undo an earlier MCP call.
                if not initiative["allowed"]:
                    return EventResult("PARTIAL" if decision == "notify" else "NO_ACTION")
                if decision == "notify":
                    # Tool success alone cannot prove notification delivery.
                    return EventResult("TOOL_ACTIVITY_COMPLETED" if status == "SUCCEEDED" else "PARTIAL")
                return EventResult("RESPONSE", answer)

            receipt = lease.run(execute)
            receipt["decision"] = final.get("decision")
            if final.get("status") in {"completed", "partial", "unavailable"}:
                receipt["model_status"] = final["status"]
            # Permission comes from the authenticated result response. Never
            # fall back to the snapshot read before submission/settings changes.
            returned_notification = receipt.pop("notification")
            if initiative:
                receipt["initiative_reason"] = initiative["reason"]
                receipt["notification_allowed"] = initiative["allowed"]
                receipt["notification_required"] = initiative["required"]
                if not initiative["allowed"]:
                    receipt["delivery_status"] = "BLOCKED_INITIATIVE"
            if final.get("decision") == "notify":
                # The sidecar aggregates tool status, not a route-specific
                # delivery receipt. Never turn a model decision into delivery.
                receipt["notification_delivery_status"] = "NOT_VERIFIED"
            if final.get("decision") == "speak" and initiative.get("allowed") and receipt["status"] == "RECORDED":
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
