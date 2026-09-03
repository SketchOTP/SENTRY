"""Host-owned SENTRY execution authority, confirmation broker, and audit ledger.

The resident Codex sandbox can propose actions through MCP, but this module is
the only component that classifies and executes host mutations.  Its private
state lives outside the resident workspace and never stores transcripts,
secrets, file contents, audio, images, or biometric data.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping


DEFAULT_RESPONSE_WINDOW_SECONDS = 120
ACTIVE_ACTION_STATES = {"DRAFTED", "PRESENTING", "AWAITING_RESPONSE"}
APPROVE_FORMS = {
    "confirm", "confirmed", "confirm that action", "yes", "yes please", "yeah", "yep",
    "sure", "okay", "ok", "go ahead", "yes go ahead", "yeah go ahead", "please go ahead",
    "do it", "please do", "please proceed", "proceed",
    "carry on", "make it happen", "sounds good", "sounds good do it", "that s right", "thats right",
    "approved", "execute it", "move it", "go for it",
}
CANCEL_FORMS = {
    "cancel", "cancel that", "actually cancel that", "no", "nope", "don t", "dont",
    "don t do it", "dont do it", "stop", "never mind", "nevermind", "forget it", "leave it",
    "leave it alone", "actually leave it where it is", "hold off", "not now", "scratch that",
    "actually no", "no leave it alone", "nah", "nah don t do it", "nah dont do it",
}
DEFER_REQUEST = re.compile(
    r"\b(?:"
    r"wait (?:for|until) (?:me to )?(?:explicitly )?(?:confirm|approve)|"
    r"wait for (?:my )?(?:confirmation|approval)|"
    r"ask me before|"
    r"prepare (?:it|that|to .+?) but (?:do not|don't|dont) (?:execute|move|run|do)|"
    r"show me what (?:you are|you're) going to do first|"
    r"(?:do not|don't|dont) .+ until (?:i )?(?:explicitly )?(?:confirm|approve)|"
    r"(?:do not|don't|dont) (?:execute|move|run|do)(?: it| that)? yet|"
    r"prepare (?:it|that) only"
    r")\b",
    re.IGNORECASE,
)
REVISION_REQUEST = re.compile(
    r"\b(?:actually\s+)?(?:no\s*,?\s*)?(?:call|name|rename)\s+it\b|"
    r"\b(?:put|move)\s+it\s+(?:in|into|to)\b|"
    r"\buse\s+(?:hyphens?|dashes?|underscores?|spaces?|no spaces|all lowercase)\b",
    re.IGNORECASE,
)
QUESTION_REQUEST = re.compile(
    r"^(?:what|where|which|who|when|why|how|does|do|is|are|will|would|can|could)\b",
    re.IGNORECASE,
)
SECRET_KEY = re.compile(r"(?i)(secret|token|password|credential|api[_-]?key|private[_-]?key)")
META_DISCUSSION = re.compile(
    r"^(please\s+)?((can|could|would)\s+you\s+)?(explain|define|what does|tell me whether|summari[sz]e|describe an? article|give an? example of)\b"
)
PROTECTED_PARTS = {
    ".ssh", ".gnupg", ".aws", ".azure", ".kube", ".git-credentials",
    ".local/share/keyrings", ".config/gh", ".config/gcloud",
}
PROTECTED_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".env"}


RISK_TIERS: dict[str, int] = {
    "get_current_office_state": 0, "get_office_history": 0, "get_office_reminders": 0,
    "get_acknowledgement_preference": 0, "get_recent_proactive_action": 0,
    "get_routines": 0, "get_home_weather": 0, "get_local_time": 0, "get_alarms": 0,
    "get_system_volume": 0, "get_active_window": 0, "find_applications": 0,
    "get_execution_authority_status": 0, "get_recent_execution_audit": 0,
    "get_pending_authorization": 0,
    "capture_desktop": 1, "inspect_office_camera": 1,
    "create_next_office_reminder": 1, "cancel_pending_office_reminder": 1,
    "set_acknowledgement_preference": 1, "create_one_shot_alarm": 1, "cancel_alarm": 1,
    "launch_application": 1, "open_web_page": 1, "open_local_artifact": 1,
    "set_system_volume": 1, "adjust_system_volume": 1, "set_system_muted": 1,
    "control_media": 1,
    "propose_file_move": 2, "press_keys": 2, "type_into_active_window": 2,
    "click_desktop": 2,
}

DIRECT_REQUEST_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "capture_desktop": (re.compile(r"\b(capture|take|show|inspect|look at)\b.*\b(screen|desktop|screenshot)\b"),),
    "inspect_office_camera": (
        re.compile(r"\b(inspect|check|show|use|look at)\b.*\b(camera|office)\b"),
        re.compile(r"\b(who|anyone|someone)\b.*\b(office|here|room)\b"),
    ),
    "create_next_office_reminder": (re.compile(r"\b(remind me|create|set|add)\b.*\breminder\b"),),
    "cancel_pending_office_reminder": (re.compile(r"\b(cancel|delete|remove|clear)\b.*\breminder\b"),),
    "set_acknowledgement_preference": (re.compile(r"\b(set|change|allow|suppress|disable|enable)\b.*\b(preference|greet|greeting|acknowledg\w*)\b"),),
    "create_one_shot_alarm": (
        re.compile(r"\b(set|create|add|schedule)\b.*\balarm\b"),
        re.compile(r"\bwake me\b"),
    ),
    "cancel_alarm": (re.compile(r"\b(cancel|delete|remove|clear)\b.*\balarm\b"),),
    "launch_application": (re.compile(r"\b(open|launch|start|run)\b.*\b(app|application|program|[a-z0-9_.-]+)\b"),),
    "open_web_page": (re.compile(r"\b(open|visit|go to|show)\b.*\b(browser|page|website|site|https?://|www\.)\b"),),
    "open_local_artifact": (re.compile(r"\b(open|show|display|view)\b.*\b(image|file|artifact|document|picture)\b"),),
    "set_system_volume": (re.compile(r"\b(set|change|turn|adjust)\b.*\b(volume|sound)\b"),),
    "adjust_system_volume": (
        re.compile(r"\b(turn|adjust|raise|lower|increase|decrease)\b.*\b(volume|sound)\b"),
        re.compile(r"\b(louder|quieter)\b"),
    ),
    "set_system_muted": (re.compile(r"\b(mute|unmute)\b"),),
    "control_media": (re.compile(r"\b(play|pause|resume|next|previous|stop)\b.*\b(media|music|song|track|playlist)?\b"),),
    "propose_file_move": (
        re.compile(r"\b(move|relocate)\b.*\b(file|image|document|folder|/|\\)\b"),
        re.compile(r"\b(move|relocate)\b.*\b[a-z0-9][a-z0-9_.-]*\.[a-z0-9]{1,16}\b"),
    ),
    "press_keys": (re.compile(r"\b(press|hit)\b.*\b(key|keys|keyboard|enter|escape|tab)\b"),),
    "type_into_active_window": (re.compile(r"\b(type|enter|fill)\b.*\b(text|field|window|application|app|form|box)\b"),),
    "click_desktop": (re.compile(r"\b(click|select)\b.*\b(button|control|item|at|coordinate)\b"),),
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _utcnow()).isoformat()


def _canonical(arguments: Mapping[str, Any]) -> str:
    if any(SECRET_KEY.search(str(key)) for key in arguments):
        raise ValueError("sensitive arguments are prohibited")
    return json.dumps(arguments, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _hash(arguments: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(arguments).encode("utf-8")).hexdigest()


def _authorization_binding(value: Mapping[str, Any]) -> str:
    """Bind immutable authorization identity separately from action arguments."""

    fields = {
        "authorization_id": value.get("authorization_id"),
        "request_id": value.get("request_id"),
        "thread_id": value.get("thread_id"),
        "restart_epoch": value.get("restart_epoch"),
        "risk_tier": value.get("risk_tier"),
        "action_type": value.get("action_type"),
        "argument_hash": value.get("argument_hash"),
        "maximum_uses": value.get("maximum_uses"),
    }
    return hashlib.sha256(json.dumps(fields, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _default_root() -> Path:
    state = Path(os.environ.get("XDG_STATE_HOME", "~/.local/state")).expanduser()
    return state / "sentry" / "execution-authority"


def _default_workspace() -> Path:
    data = Path(os.environ.get("XDG_DATA_HOME", "~/.local/share")).expanduser()
    return data / "sentry" / "agent-workspace"


@dataclass(frozen=True)
class RequestContext:
    request_id: str
    thread_id: str
    operator_request: str
    restart_epoch: str

    @classmethod
    def from_environment(cls) -> "RequestContext":
        return cls(
            request_id=os.environ.get("SENTRY_REQUEST_ID", ""),
            thread_id=os.environ.get("SENTRY_THREAD_ID", "new-thread"),
            operator_request=os.environ.get("SENTRY_OPERATOR_REQUEST", ""),
            restart_epoch=os.environ.get("SENTRY_AUTHORITY_EPOCH", ""),
        )

    def validate(self) -> None:
        if not self.request_id or not self.thread_id or not self.operator_request.strip() or not self.restart_epoch:
            raise PermissionError("trusted SENTRY request context is unavailable")


class DialogueAct(StrEnum):
    APPROVE = "APPROVE"
    CANCEL = "CANCEL"
    REVISE = "REVISE"
    QUESTION = "QUESTION"
    UNRELATED = "UNRELATED"
    UNUSABLE = "UNUSABLE"


@dataclass(frozen=True)
class ActionResponse:
    dialogue_act: DialogueAct
    revised_request: str | None = None
    question: str | None = None
    source: str = "deterministic"


class NaturalActionResponseInterpreter:
    """Classify one reply in the context of one active pending action.

    The optional semantic fallback is classification-only. It receives only a
    sanitized summary, action type, and current reply and cannot execute.
    """

    def __init__(self, semantic_fallback: Callable[[str, str, str], Mapping[str, Any]] | None = None) -> None:
        self.semantic_fallback = semantic_fallback

    @staticmethod
    def _normalized(text: str) -> str:
        return " ".join(re.sub(r"[^a-z0-9 ]+", " ", text.casefold()).split())

    def interpret(self, *, summary: str, action_type: str, response: str) -> ActionResponse:
        normalized = self._normalized(response)
        if not normalized:
            return ActionResponse(DialogueAct.UNUSABLE)
        if REVISION_REQUEST.search(response):
            return ActionResponse(DialogueAct.REVISE, revised_request=response.strip())
        if normalized in CANCEL_FORMS:
            return ActionResponse(DialogueAct.CANCEL)
        if normalized in APPROVE_FORMS:
            return ActionResponse(DialogueAct.APPROVE)
        if QUESTION_REQUEST.search(normalized) or response.rstrip().endswith("?"):
            return ActionResponse(DialogueAct.QUESTION, question=response.strip())
        if self.semantic_fallback is None:
            return ActionResponse(DialogueAct.UNRELATED)
        try:
            result = self.semantic_fallback(summary, action_type, response)
            act = DialogueAct(str(result.get("dialogue_act", "UNUSABLE")))
        except (KeyError, TypeError, ValueError):
            return ActionResponse(DialogueAct.UNUSABLE, source="semantic_fallback_invalid")
        revised = result.get("revised_request")
        question = result.get("question")
        if revised is not None and not isinstance(revised, str):
            return ActionResponse(DialogueAct.UNUSABLE, source="semantic_fallback_invalid")
        if question is not None and not isinstance(question, str):
            return ActionResponse(DialogueAct.UNUSABLE, source="semantic_fallback_invalid")
        return ActionResponse(act, revised_request=revised, question=question, source="semantic_fallback")


def requires_deferred_confirmation(operator_request: str) -> bool:
    return DEFER_REQUEST.search(operator_request) is not None


def normalize_spoken_filename(name: str, *, source_suffix: str = "") -> str:
    """Resolve explicit spoken punctuation without guessing absent punctuation."""

    value = name.strip().strip("\"'")
    lowercase = bool(re.search(r"\ball lowercase\b", value, re.IGNORECASE))
    no_spaces = bool(re.search(r"\bno spaces\b", value, re.IGNORECASE))
    value = re.sub(r"\ball lowercase\b", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\bno spaces\b", "", value, flags=re.IGNORECASE)
    substitutions = ((r"\b(?:hyphen|dash)\b", "-"), (r"\bunderscore\b", "_"), (r"\b(?:dot|period)\b", "."), (r"\bspace\b", " "))
    for pattern, replacement in substitutions:
        value = re.sub(pattern, replacement, value, flags=re.IGNORECASE)
    value = re.sub(r"\s*([._-])\s*", r"\1", value)
    value = re.sub(r"\s+", "", value) if no_spaces else re.sub(r"\s+", " ", value).strip()
    if lowercase:
        value = value.casefold()
    if source_suffix and not Path(value).suffix:
        value += source_suffix
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError("resolved filename is invalid")
    return value


def resolve_file_move_destination(source: str, destination: str) -> str:
    source_path = Path(source).expanduser()
    destination_path = Path(destination).expanduser()
    name = normalize_spoken_filename(destination_path.name, source_suffix=source_path.suffix)
    return str(destination_path.with_name(name))


class ExecutionAuthority:
    """Private host policy and at-most-once authorization state."""

    def __init__(
        self,
        root: Path | None = None,
        *,
        workspace: Path | None = None,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self.root = Path(root or os.environ.get("SENTRY_AUTHORITY_ROOT", _default_root())).expanduser()
        self.workspace = Path(workspace or os.environ.get("SENTRY_AGENT_WORKSPACE", _default_workspace())).expanduser().resolve()
        self.pending_path = self.root / "pending.json"
        self.audit_path = self.root / "execution-audit.jsonl"
        self.lock_path = self.root / "authority.lock"
        self.clock = clock

    def _prepare(self) -> None:
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.root.chmod(0o700)
        self.workspace.mkdir(mode=0o700, parents=True, exist_ok=True)

    @contextmanager
    def locked(self) -> Iterator[None]:
        self._prepare()
        with self.lock_path.open("a+", encoding="utf-8") as handle:
            self.lock_path.chmod(0o600)
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _write_pending(self, value: dict[str, Any] | None) -> None:
        if value is None:
            self.pending_path.unlink(missing_ok=True)
            return
        temporary = self.pending_path.with_suffix(f".json.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
        temporary.chmod(0o600)
        os.replace(temporary, self.pending_path)
        self.pending_path.chmod(0o600)

    def _load_pending_unlocked(self) -> dict[str, Any] | None:
        if not self.pending_path.is_file():
            return None
        try:
            value = json.loads(self.pending_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

    def _append_audit(self, record: Mapping[str, Any]) -> None:
        self._prepare()
        sanitized = {
            "action_id": str(record.get("action_id") or uuid.uuid4()),
            "request_id": str(record.get("request_id") or "unknown"),
            "thread_id": str(record.get("thread_id") or "unknown"),
            "timestamp": str(record.get("timestamp") or _iso(self.clock())),
            "capability": str(record.get("capability") or "unknown"),
            "risk_tier": int(record.get("risk_tier", -1)),
            "action_type": str(record.get("action_type") or "unknown"),
            "target_summary": str(record.get("target_summary") or "")[:500],
            "authorization_id": record.get("authorization_id"),
            "authorization_status": str(record.get("authorization_status") or "not_required"),
            "execution_surface": str(record.get("execution_surface") or "sentry_host"),
            "outcome": str(record.get("outcome") or "unknown"),
            "error_class": record.get("error_class"),
            "duration_ms": round(float(record.get("duration_ms", 0.0)), 3),
            "authority_source": record.get("authority_source"),
            "dialogue_act": record.get("dialogue_act"),
            "actionable_at": record.get("actionable_at"),
            "response_deadline": record.get("response_deadline"),
            "presentation_surface": record.get("presentation_surface"),
            "presentation_completed_at": record.get("presentation_completed_at"),
        }
        serialized = json.dumps(sanitized, ensure_ascii=True, sort_keys=True) + "\n"
        descriptor = os.open(self.audit_path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
        try:
            os.write(descriptor, serialized.encode("utf-8"))
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        self.audit_path.chmod(0o600)

    def audit_external_action(
        self, *, context: RequestContext, capability: str, risk_tier: int,
        action_type: str, target_summary: str, outcome: str, duration_ms: float = 0,
        error_class: str | None = None, authority_source: str | None = None,
    ) -> None:
        self._append_audit({
            "request_id": context.request_id, "thread_id": context.thread_id,
            "capability": capability, "risk_tier": risk_tier, "action_type": action_type,
            "target_summary": target_summary, "outcome": outcome,
            "error_class": error_class, "duration_ms": duration_ms,
            "authority_source": authority_source,
        })

    def direct_request_allows(self, capability: str, context: RequestContext) -> bool:
        context.validate()
        patterns = DIRECT_REQUEST_PATTERNS.get(capability)
        if not patterns:
            return False
        request = " ".join(context.operator_request.casefold().split())
        if META_DISCUSSION.search(request):
            return False
        return any(pattern.search(request) for pattern in patterns)

    def execute_tier1(
        self, capability: str, arguments: Mapping[str, Any], target_summary: str,
        executor: Callable[[], Any], *, context: RequestContext | None = None,
    ) -> Any:
        context = context or RequestContext.from_environment()
        started = time.monotonic()
        action_id = str(uuid.uuid4())
        try:
            if RISK_TIERS.get(capability) != 1 or not self.direct_request_allows(capability, context):
                raise PermissionError("Tier-1 action was not directly requested in the current operator turn")
            _canonical(arguments)
            # A required pre-execution record also proves the audit store is writable.
            self._append_audit({
                "action_id": action_id, "request_id": context.request_id, "thread_id": context.thread_id,
                "capability": capability, "risk_tier": 1, "action_type": capability,
                "target_summary": target_summary, "outcome": "execution_started",
            })
            result = executor()
        except Exception as exc:
            self._append_audit({
                "action_id": action_id, "request_id": context.request_id or "unknown", "thread_id": context.thread_id or "unknown",
                "capability": capability, "risk_tier": 1, "action_type": capability,
                "target_summary": target_summary, "outcome": "blocked" if isinstance(exc, PermissionError) else "failed",
                "error_class": type(exc).__name__, "duration_ms": (time.monotonic() - started) * 1000,
            })
            raise
        self._append_audit({
            "action_id": action_id, "request_id": context.request_id, "thread_id": context.thread_id,
            "capability": capability, "risk_tier": 1, "action_type": capability,
            "target_summary": target_summary, "outcome": "completed",
            "duration_ms": (time.monotonic() - started) * 1000,
        })
        return result

    def _validate_sensitive_action(
        self, action_type: str, arguments: Mapping[str, Any], *,
        risk_tier: int, context: RequestContext, target_summary: str,
    ) -> tuple[str, str]:
        context = context or RequestContext.from_environment()
        context.validate()
        capability = "propose_file_move" if action_type == "move_file" else action_type
        if not self.direct_request_allows(capability, context):
            self._append_audit({
                "request_id": context.request_id, "thread_id": context.thread_id,
                "capability": capability, "risk_tier": risk_tier, "action_type": action_type,
                "target_summary": target_summary, "authorization_status": "not_created",
                "outcome": "blocked", "error_class": "NotDirectlyRequested",
            })
            raise PermissionError("sensitive action was not directly requested in the current operator turn")
        if action_type not in {"move_file", "press_keys", "type_into_active_window", "click_desktop"}:
            self._append_audit({
                "request_id": context.request_id, "thread_id": context.thread_id,
                "capability": "authorization_broker", "risk_tier": max(risk_tier, 3),
                "action_type": action_type, "target_summary": target_summary,
                "authorization_status": "prohibited", "outcome": "blocked", "error_class": "UnsupportedAction",
            })
            raise PermissionError("the requested elevated operation is not supported by the resident authority broker")
        if action_type in {"press_keys", "type_into_active_window", "click_desktop"}:
            expected_window_id = arguments.get("expected_window_id")
            if not isinstance(expected_window_id, str) or not expected_window_id.isdigit():
                raise ValueError("desktop input authorization requires an exact active-window identifier")
        if risk_tier not in {2, 3}:
            raise ValueError("sensitive proposals must be Tier 2 or Tier 3")
        canonical = _canonical(arguments)
        if action_type == "type_into_active_window" and (SECRET_KEY.search(context.operator_request) or SECRET_KEY.search(canonical)):
            self._append_audit({
                "request_id": context.request_id, "thread_id": context.thread_id,
                "capability": action_type, "risk_tier": 3, "action_type": action_type,
                "target_summary": "active-window credential-bearing input",
                "authorization_status": "prohibited", "outcome": "blocked", "error_class": "SensitiveInput",
            })
            raise PermissionError("credential-bearing typed input is blocked in the resident authority broker")
        if action_type == "move_file":
            source = self._safe_path(str(arguments.get("source", "")), require_workspace=True)
            destination = self._safe_path(str(arguments.get("destination", "")), require_workspace=False)
            if not source.is_file():
                raise FileNotFoundError("requested source is not a regular file")
            if destination.exists():
                raise FileExistsError("requested destination already exists; replace or rename must be explicit")
        return capability, canonical

    def request_action(
        self, action_type: str, arguments: Mapping[str, Any], target_summary: str,
        *, risk_tier: int = 2, context: RequestContext | None = None,
    ) -> dict[str, Any]:
        """Execute a clear current request or draft it when deferral was explicit."""

        context = context or RequestContext.from_environment()
        _, canonical = self._validate_sensitive_action(
            action_type, arguments, risk_tier=risk_tier, context=context,
            target_summary=target_summary,
        )
        if requires_deferred_confirmation(context.operator_request):
            return self._draft_action(
                action_type, canonical, target_summary, risk_tier=risk_tier,
                context=context, authority_source="explicit_deferred_confirmation",
            )
        return self._execute_recorded(
            action_type, json.loads(canonical), target_summary,
            risk_tier=risk_tier, context=context,
            authority_source="direct_current_turn",
        )

    def propose(
        self, action_type: str, arguments: Mapping[str, Any], target_summary: str,
        *, risk_tier: int = 2, context: RequestContext | None = None,
    ) -> dict[str, Any]:
        """Explicitly draft an action for compatibility and controlled tests."""

        context = context or RequestContext.from_environment()
        _, canonical = self._validate_sensitive_action(
            action_type, arguments, risk_tier=risk_tier, context=context,
            target_summary=target_summary,
        )
        return self._draft_action(
            action_type, canonical, target_summary, risk_tier=risk_tier,
            context=context, authority_source="explicit_deferred_confirmation",
        )

    def _draft_action(
        self, action_type: str, canonical: str, target_summary: str, *,
        risk_tier: int, context: RequestContext, authority_source: str,
    ) -> dict[str, Any]:
        now = self.clock()
        with self.locked():
            pending = self._load_pending_unlocked()
            if pending and pending.get("status") in ACTIVE_ACTION_STATES:
                if pending.get("status") == "AWAITING_RESPONSE" and self._deadline_passed(pending, now):
                    pending["status"] = "EXPIRED"
                    pending["outcome"] = "not_executed"
                    self._write_pending(pending)
                else:
                    raise RuntimeError("one sensitive action dialogue is already active")
            authorization_id = str(uuid.uuid4())
            value = {
                "authorization_id": authorization_id, "request_id": context.request_id,
                "thread_id": context.thread_id, "restart_epoch": context.restart_epoch,
                "risk_tier": risk_tier, "action_type": action_type,
                "canonical_arguments": json.loads(canonical), "target_summary": target_summary[:500],
                "argument_hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
                "created_at": _iso(now), "actionable_at": None, "response_deadline": None,
                "maximum_uses": 1, "status": "DRAFTED", "presentation_surface": None,
                "presentation_started_at": None, "presentation_completed_at": None,
                "response_received_at": None, "authority_source": authority_source,
                "dialogue_act": None, "confirmed_at": None, "used_at": None,
                "outcome": None, "error_class": None,
            }
            value["binding_hash"] = _authorization_binding(value)
            self._write_pending(value)
        self._append_audit({
            "request_id": context.request_id, "thread_id": context.thread_id,
            "capability": "authorization_broker", "risk_tier": risk_tier, "action_type": action_type,
            "target_summary": target_summary, "authorization_id": authorization_id,
            "authorization_status": "DRAFTED", "outcome": "confirmation_required",
            "authority_source": authority_source,
        })
        return {
            "status": "DRAFTED", "authorization_id": authorization_id,
            "risk_tier": risk_tier, "action_type": action_type, "target_summary": target_summary,
            "actionable_at": None, "response_deadline": None, "maximum_uses": 1,
            "confirmation_prompt": self._confirmation_prompt(value),
        }

    def _execute_recorded(
        self, action_type: str, arguments: Mapping[str, Any], target_summary: str, *,
        risk_tier: int, context: RequestContext, authority_source: str,
        authorization_id: str | None = None,
    ) -> dict[str, Any]:
        action_id = str(uuid.uuid4())
        started = time.monotonic()
        self._append_audit({
            "action_id": action_id, "request_id": context.request_id,
            "thread_id": context.thread_id, "capability": "authorization_broker",
            "risk_tier": risk_tier, "action_type": action_type,
            "target_summary": target_summary, "authorization_id": authorization_id,
            "authorization_status": "EXECUTING", "outcome": "execution_started",
            "authority_source": authority_source,
        })
        try:
            result = self._execute(action_type, arguments)
        except Exception as exc:
            self._append_audit({
                "action_id": action_id, "request_id": context.request_id,
                "thread_id": context.thread_id, "capability": "authorization_broker",
                "risk_tier": risk_tier, "action_type": action_type,
                "target_summary": target_summary, "authorization_id": authorization_id,
                "authorization_status": "FAILED", "outcome": "failed",
                "authority_source": authority_source, "error_class": type(exc).__name__,
                "duration_ms": (time.monotonic() - started) * 1000,
            })
            raise
        self._append_audit({
            "action_id": action_id, "request_id": context.request_id,
            "thread_id": context.thread_id, "capability": "authorization_broker",
            "risk_tier": risk_tier, "action_type": action_type,
            "target_summary": target_summary, "authorization_id": authorization_id,
            "authorization_status": "EXECUTED", "outcome": "completed",
            "authority_source": authority_source,
            "duration_ms": (time.monotonic() - started) * 1000,
        })
        return {
            "status": "completed", "authorization_id": authorization_id,
            "executed": True, "result": result, "authority_source": authority_source,
        }

    @staticmethod
    def _deadline_passed(pending: Mapping[str, Any], now: datetime) -> bool:
        deadline = pending.get("response_deadline")
        return isinstance(deadline, str) and datetime.fromisoformat(deadline) <= now

    @staticmethod
    def _confirmation_prompt(pending: Mapping[str, Any]) -> str:
        arguments = pending.get("canonical_arguments") or {}
        if pending.get("action_type") == "move_file":
            source = Path(str(arguments.get("source", "file"))).name
            destination = Path(str(arguments.get("destination", "destination")))
            folder = destination.parent.name or str(destination.parent)
            return f'I\'m ready to move "{source}" into {folder} as "{destination.name}". Shall I do that?'
        return f"I'm ready to {pending.get('target_summary')}. Shall I do that?"

    def begin_presentation(
        self, authorization_id: str, *, surface: str,
        context: RequestContext | None = None,
    ) -> dict[str, Any]:
        with self.locked():
            pending = self._load_pending_unlocked()
            if not pending or pending.get("authorization_id") != authorization_id:
                raise PermissionError("no matching pending action exists")
            if context and pending.get("thread_id") != context.thread_id:
                raise PermissionError("the pending action belongs to another thread")
            if pending.get("status") not in {"DRAFTED", "PRESENTING"}:
                raise PermissionError("the pending action is not available for presentation")
            pending["status"] = "PRESENTING"
            pending["presentation_surface"] = surface
            pending["presentation_started_at"] = _iso(self.clock())
            pending["actionable_at"] = None
            pending["response_deadline"] = None
            self._write_pending(pending)
        return self._public_pending(pending)

    def complete_presentation(
        self, authorization_id: str, *, surface: str,
        response_window_seconds: int = DEFAULT_RESPONSE_WINDOW_SECONDS,
    ) -> dict[str, Any]:
        if response_window_seconds <= 0:
            raise ValueError("response window must be positive")
        now = self.clock()
        with self.locked():
            pending = self._load_pending_unlocked()
            if not pending or pending.get("authorization_id") != authorization_id or pending.get("status") != "PRESENTING":
                raise PermissionError("no matching action is awaiting completed presentation")
            pending["status"] = "AWAITING_RESPONSE"
            pending["presentation_surface"] = surface
            pending["presentation_completed_at"] = _iso(now)
            pending["actionable_at"] = _iso(now)
            pending["response_deadline"] = _iso(now + timedelta(seconds=response_window_seconds))
            pending["response_received_at"] = None
            self._write_pending(pending)
        self._append_audit({
            "request_id": pending["request_id"], "thread_id": pending["thread_id"],
            "capability": "authorization_broker", "risk_tier": pending["risk_tier"],
            "action_type": pending["action_type"], "target_summary": pending["target_summary"],
            "authorization_id": authorization_id, "authorization_status": "AWAITING_RESPONSE",
            "outcome": "presented", "authority_source": pending.get("authority_source"),
            "actionable_at": pending["actionable_at"], "response_deadline": pending["response_deadline"],
            "presentation_surface": surface, "presentation_completed_at": pending["presentation_completed_at"],
        })
        return self._public_pending(pending)

    def presentation_failed(self, authorization_id: str, *, surface: str) -> dict[str, Any]:
        with self.locked():
            pending = self._load_pending_unlocked()
            if not pending or pending.get("authorization_id") != authorization_id or pending.get("status") not in {"DRAFTED", "PRESENTING"}:
                raise PermissionError("no matching pending presentation exists")
            pending["status"] = "FAILED"
            pending["outcome"] = "not_executed"
            pending["error_class"] = "PresentationFailed"
            pending["presentation_surface"] = surface
            self._write_pending(pending)
        self._append_audit({
            "request_id": pending["request_id"], "thread_id": pending["thread_id"],
            "capability": "authorization_broker", "risk_tier": pending["risk_tier"],
            "action_type": pending["action_type"], "target_summary": pending["target_summary"],
            "authorization_id": authorization_id, "authorization_status": "FAILED",
            "outcome": "not_executed", "error_class": "PresentationFailed",
            "authority_source": pending.get("authority_source"), "presentation_surface": surface,
        })
        return self._public_pending(pending)

    def expire(self, authorization_id: str, *, reason: str = "response_timeout") -> dict[str, Any]:
        with self.locked():
            pending = self._load_pending_unlocked()
            if not pending or pending.get("authorization_id") != authorization_id or pending.get("status") not in ACTIVE_ACTION_STATES:
                raise PermissionError("no matching active action can expire")
            pending["status"] = "EXPIRED"
            pending["outcome"] = "not_executed"
            pending["error_class"] = reason
            self._write_pending(pending)
        self._append_audit({
            "request_id": pending["request_id"], "thread_id": pending["thread_id"],
            "capability": "authorization_broker", "risk_tier": pending["risk_tier"],
            "action_type": pending["action_type"], "target_summary": pending["target_summary"],
            "authorization_id": authorization_id, "authorization_status": "EXPIRED",
            "outcome": "not_executed", "error_class": reason,
            "authority_source": pending.get("authority_source"),
            "actionable_at": pending.get("actionable_at"),
            "response_deadline": pending.get("response_deadline"),
        })
        return self._public_pending(pending)

    def invalidate_active_for_restart(self, current_epoch: str) -> dict[str, Any]:
        with self.locked():
            pending = self._load_pending_unlocked()
            if not pending or pending.get("status") not in ACTIVE_ACTION_STATES or pending.get("restart_epoch") == current_epoch:
                return {"invalidated": False}
            pending["status"] = "FAILED"
            pending["outcome"] = "not_executed"
            pending["error_class"] = "ServiceRestart"
            self._write_pending(pending)
        self._append_audit({
            "request_id": pending["request_id"], "thread_id": pending["thread_id"],
            "capability": "authorization_broker", "risk_tier": pending["risk_tier"],
            "action_type": pending["action_type"], "target_summary": pending["target_summary"],
            "authorization_id": pending["authorization_id"], "authorization_status": "FAILED",
            "outcome": "not_executed", "error_class": "ServiceRestart",
            "authority_source": pending.get("authority_source"),
        })
        return {"invalidated": True, "authorization_id": pending["authorization_id"]}

    @staticmethod
    def _public_pending(pending: Mapping[str, Any], *, include_arguments: bool = False) -> dict[str, Any]:
        result = {
            "pending": pending.get("status") in ACTIVE_ACTION_STATES,
            "authorization_id": pending.get("authorization_id"),
            "risk_tier": pending.get("risk_tier"), "action_type": pending.get("action_type"),
            "target_summary": pending.get("target_summary"), "status": pending.get("status"),
            "actionable_at": pending.get("actionable_at"),
            "response_deadline": pending.get("response_deadline"),
            "presentation_surface": pending.get("presentation_surface"),
            "presentation_completed_at": pending.get("presentation_completed_at"),
            "authority_source": pending.get("authority_source"),
        }
        if include_arguments:
            result["canonical_arguments"] = pending.get("canonical_arguments")
        return result

    def pending_status(
        self, *, context: RequestContext | None = None,
        include_arguments: bool = False,
    ) -> dict[str, Any]:
        expired: dict[str, Any] | None = None
        with self.locked():
            pending = self._load_pending_unlocked()
            if not pending:
                return {"pending": False}
            if pending.get("status") == "pending":  # Legacy unreleased working-tree state.
                pending["status"] = "EXPIRED"
                pending["outcome"] = "not_executed"
                self._write_pending(pending)
                expired = pending
            elif pending.get("status") == "AWAITING_RESPONSE" and self._deadline_passed(pending, self.clock()):
                pending["status"] = "EXPIRED"
                pending["outcome"] = "not_executed"
                self._write_pending(pending)
                expired = pending
            if context and pending.get("thread_id") != context.thread_id:
                return {"pending": False}
            result = self._public_pending(pending, include_arguments=include_arguments)
        if expired:
            self._append_audit({
                "request_id": expired.get("request_id"), "thread_id": expired.get("thread_id"),
                "capability": "authorization_broker", "risk_tier": expired.get("risk_tier", 2),
                "action_type": expired.get("action_type"), "target_summary": expired.get("target_summary"),
                "authorization_id": expired.get("authorization_id"), "authorization_status": "EXPIRED",
                "outcome": "not_executed", "authority_source": expired.get("authority_source"),
                "actionable_at": expired.get("actionable_at"), "response_deadline": expired.get("response_deadline"),
            })
        return result

    def claim_response(self, *, context: RequestContext) -> dict[str, Any]:
        context.validate()
        now = self.clock()
        with self.locked():
            pending = self._load_pending_unlocked()
            if not pending or pending.get("status") != "AWAITING_RESPONSE":
                raise PermissionError("no action is awaiting an operator response")
            if self._deadline_passed(pending, now):
                pending["status"] = "EXPIRED"
                pending["outcome"] = "not_executed"
                self._write_pending(pending)
                raise PermissionError("the pending action response window expired")
            if pending.get("thread_id") != context.thread_id:
                raise PermissionError("the pending action belongs to another thread")
            if pending.get("restart_epoch") != context.restart_epoch:
                raise PermissionError("the pending action was invalidated by a restart")
            pending["status"] = "PRESENTING"
            pending["response_received_at"] = _iso(now)
            self._write_pending(pending)
        return self._public_pending(pending, include_arguments=True)

    def record_dialogue_act(self, authorization_id: str, act: DialogueAct) -> dict[str, Any]:
        with self.locked():
            pending = self._load_pending_unlocked()
            if not pending or pending.get("authorization_id") != authorization_id or pending.get("status") != "PRESENTING":
                raise PermissionError("no matching action response is being handled")
            pending["dialogue_act"] = act.value.casefold()
            self._write_pending(pending)
        self._append_audit({
            "request_id": pending["request_id"], "thread_id": pending["thread_id"],
            "capability": "authorization_broker", "risk_tier": pending["risk_tier"],
            "action_type": pending["action_type"], "target_summary": pending["target_summary"],
            "authorization_id": authorization_id, "authorization_status": "PRESENTING",
            "outcome": "dialogue_continues", "dialogue_act": act.value.casefold(),
            "authority_source": pending.get("authority_source"),
        })
        return self._public_pending(pending, include_arguments=True)

    def supersede(self, authorization_id: str, *, context: RequestContext) -> dict[str, Any]:
        with self.locked():
            pending = self._load_pending_unlocked()
            if not pending or pending.get("authorization_id") != authorization_id or pending.get("status") != "PRESENTING":
                raise PermissionError("no matching pending action can be revised")
            if pending.get("thread_id") != context.thread_id or pending.get("restart_epoch") != context.restart_epoch:
                raise PermissionError("the pending action context changed")
            pending["status"] = "REVISED"
            pending["dialogue_act"] = "revise"
            pending["outcome"] = "superseded"
            self._write_pending(pending)
        self._append_audit({
            "request_id": context.request_id, "thread_id": context.thread_id,
            "capability": "authorization_broker", "risk_tier": pending["risk_tier"],
            "action_type": pending["action_type"], "target_summary": pending["target_summary"],
            "authorization_id": authorization_id, "authorization_status": "REVISED",
            "outcome": "superseded", "dialogue_act": "revise",
            "authority_source": pending.get("authority_source"),
        })
        return self._public_pending(pending, include_arguments=True)

    def cancel(self, *, context: RequestContext | None = None) -> dict[str, Any]:
        context = context or RequestContext.from_environment()
        context.validate()
        pending = self.claim_response(context=context)
        return self.cancel_claimed(str(pending["authorization_id"]), context=context)

    def cancel_claimed(self, authorization_id: str, *, context: RequestContext) -> dict[str, Any]:
        with self.locked():
            pending = self._load_pending_unlocked()
            if not pending or pending.get("authorization_id") != authorization_id or pending.get("status") != "PRESENTING" or pending.get("thread_id") != context.thread_id:
                raise PermissionError("no matching pending authorization exists")
            pending["status"] = "CANCELLED"
            pending["dialogue_act"] = "cancel"
            pending["outcome"] = "not_executed"
            self._write_pending(pending)
        self._append_audit({
            "request_id": context.request_id, "thread_id": context.thread_id,
            "capability": "authorization_broker", "risk_tier": pending["risk_tier"],
            "action_type": pending["action_type"], "target_summary": pending["target_summary"],
            "authorization_id": pending["authorization_id"], "authorization_status": "CANCELLED",
            "outcome": "cancelled", "dialogue_act": "cancel",
            "authority_source": pending.get("authority_source"),
        })
        return {"status": "cancelled", "authorization_id": pending["authorization_id"], "executed": False}

    def confirm(self, *, context: RequestContext | None = None) -> dict[str, Any]:
        context = context or RequestContext.from_environment()
        context.validate()
        pending = self.claim_response(context=context)
        return self.approve_claimed(str(pending["authorization_id"]), context=context)

    def approve_claimed(self, authorization_id: str, *, context: RequestContext) -> dict[str, Any]:
        with self.locked():
            pending = self._load_pending_unlocked()
            if not pending or pending.get("authorization_id") != authorization_id or pending.get("status") != "PRESENTING":
                raise PermissionError("no valid pending authorization exists")
            if pending.get("thread_id") != context.thread_id:
                raise PermissionError("the pending authorization belongs to another thread")
            if pending.get("restart_epoch") != context.restart_epoch:
                raise PermissionError("the pending authorization was invalidated by a restart")
            if pending.get("binding_hash") != _authorization_binding(pending):
                raise PermissionError("the pending authorization binding changed")
            arguments = pending.get("canonical_arguments") or {}
            if _hash(arguments) != pending.get("argument_hash"):
                raise PermissionError("the pending authorization arguments changed")
            # Consume before execution for at-most-once crash behavior.
            pending["status"] = "EXECUTING"
            pending["dialogue_act"] = "approve"
            pending["confirmed_at"] = _iso(self.clock())
            pending["used_at"] = pending["confirmed_at"]
            self._write_pending(pending)
        try:
            outcome = self._execute_recorded(
                pending["action_type"], arguments, pending["target_summary"],
                risk_tier=int(pending["risk_tier"]), context=context,
                authority_source=str(pending.get("authority_source") or "explicit_deferred_confirmation"),
                authorization_id=authorization_id,
            )
        except Exception as exc:
            result_status, error_class = "FAILED", type(exc).__name__
            result = None
        else:
            result_status, error_class = "EXECUTED", None
            result = outcome.get("result")
        with self.locked():
            current = self._load_pending_unlocked() or pending
            current["status"] = result_status
            current["outcome"] = "completed" if error_class is None else "failed"
            current["error_class"] = error_class
            self._write_pending(current)
        if error_class:
            raise RuntimeError(f"authorized operation failed: {error_class}")
        return {"status": "completed", "authorization_id": pending["authorization_id"], "executed": True, "result": result}

    def _execute(self, action_type: str, arguments: Mapping[str, Any]) -> Any:
        if action_type == "move_file":
            source = self._safe_path(str(arguments.get("source", "")), require_workspace=True)
            destination = self._safe_path(str(arguments.get("destination", "")), require_workspace=False)
            if not source.is_file():
                raise FileNotFoundError("authorized source is not a regular file")
            if destination.exists():
                raise FileExistsError("authorized destination already exists")
            destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            return {"source": str(source), "destination": str(shutil.move(str(source), str(destination)))}
        from tools import sentry_desktop
        if action_type in {"press_keys", "type_into_active_window", "click_desktop"}:
            current = sentry_desktop.active_window()
            if current.get("status") != "available" or current.get("window_id") != arguments.get("expected_window_id"):
                raise PermissionError("the active desktop window changed after authorization was proposed")
        if action_type == "press_keys":
            return sentry_desktop.send_key_combo(str(arguments["keys"]))
        if action_type == "type_into_active_window":
            return sentry_desktop.type_text(str(arguments["text"]))
        if action_type == "click_desktop":
            return sentry_desktop.click_pointer(int(arguments["x"]), int(arguments["y"]), int(arguments.get("button", 1)))
        raise PermissionError("unsupported authorized action")

    def _safe_path(self, raw: str, *, require_workspace: bool) -> Path:
        if not raw or "\x00" in raw:
            raise ValueError("path is invalid")
        lexical = Path(raw).expanduser()
        if ".." in lexical.parts:
            raise ValueError("path traversal is prohibited")
        lexical_absolute = lexical if lexical.is_absolute() else (Path.cwd() / lexical)
        probe = lexical_absolute
        while probe != probe.parent:
            if probe.is_symlink():
                raise PermissionError("symlink targets are not authorizable")
            probe = probe.parent
        path = lexical.resolve(strict=False)
        home = Path.home().resolve()
        try:
            path.relative_to(self.workspace if require_workspace else home)
        except ValueError as exc:
            raise PermissionError("path is outside the authorized root") from exc
        relative_home = str(path.relative_to(home)) if path.is_relative_to(home) else str(path)
        if any(part in relative_home for part in PROTECTED_PARTS) or path.suffix.casefold() in PROTECTED_SUFFIXES or SECRET_KEY.search(path.name):
            raise PermissionError("protected path is not authorizable")
        return path

    def validate_home_artifact(self, raw: str) -> Path:
        path = self._safe_path(raw, require_workspace=False)
        if not path.is_file():
            raise FileNotFoundError("artifact is not a regular file")
        return path

    def recent_audit(self, limit: int = 20) -> dict[str, Any]:
        if not 1 <= limit <= 100:
            raise ValueError("audit limit must be from 1 through 100")
        if not self.audit_path.is_file():
            return {"records": [], "count": 0}
        records: list[dict[str, Any]] = []
        for line in self.audit_path.read_text(encoding="utf-8").splitlines()[-limit:]:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                records.append(value)
        return {"records": records, "count": len(records)}

    def status(self) -> dict[str, Any]:
        pending = self.pending_status()
        return {
            "resident_profile": "sentry-resident", "authority_available": True,
            "operating_mode": "agent_on_demand",
            "physical_limitations": [
                "continuous perception is preserved but inactive",
                "current physical state is unavailable until on-demand inspection or perception is active",
                "event-driven physical history and proactivity are limited while perception is inactive",
            ],
            "default_workspace": str(self.workspace), "command_network": "blocked",
            "native_web_search": "enabled", "browser_automation": "disabled",
            "computer_use": "disabled", "plugins": "disabled", "codex_memories": "disabled",
            "pending_authorization": pending, "risk_tiers": {str(level): sum(1 for value in RISK_TIERS.values() if value == level) for level in range(4)},
        }


def normalize_confirmation(text: str) -> str | None:
    act = NaturalActionResponseInterpreter().interpret(
        summary="pending action", action_type="unknown", response=text,
    ).dialogue_act
    if act == DialogueAct.APPROVE:
        return "confirm"
    if act == DialogueAct.CANCEL:
        return "cancel"
    return None
