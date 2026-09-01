"""Bounded Luna-directed orchestration over approved SENTRY local tools.

The planner selects semantic capabilities but cannot execute anything. The host
strictly validates and performs at most three local tool calls (one mutation),
then a second Luna turn synthesizes only the returned facts.
"""

from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import threading
import uuid
import time
from typing import Any, Callable

from tools.sentry_codex_bridge import invoke_conversation_planner, invoke_conversation_synthesis
from tools.sentry_conversation_tools import (
    MUTATION_TOOLS,
    ConversationToolHost,
    tool_catalog,
)
from tools.sentry_grounding import unavailable_response, validate_grounded_response


MAX_LOCAL_TOOL_CALLS = 3
MAX_MUTATION_CALLS = 1
MAX_PRIOR_TURNS = 4
CONTEXT_TTL_SECONDS = 600


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class PlannedCall:
    name: str
    arguments: dict[str, Any]


class RecentConversationContext:
    """Process-local, expiring user/assistant turns; no file or DB persistence."""

    def __init__(self, *, max_turns: int = MAX_PRIOR_TURNS, ttl_seconds: int = CONTEXT_TTL_SECONDS) -> None:
        self.max_turns = max_turns
        self.ttl = timedelta(seconds=ttl_seconds)
        self._items: OrderedDict[str, deque[tuple[datetime, str, str]]] = OrderedDict()
        self._lock = threading.Lock()

    def _purge(self, now: datetime) -> None:
        expired = [key for key, turns in self._items.items() if not turns or now - turns[-1][0] > self.ttl]
        for key in expired:
            self._items.pop(key, None)

    def prior(self, conversation_id: str) -> list[dict[str, str]]:
        now = _now()
        with self._lock:
            self._purge(now)
            turns = self._items.get(conversation_id, ())
            return [{"user": user, "assistant": assistant} for _, user, assistant in turns]

    def add(self, conversation_id: str, user: str, assistant: str) -> None:
        now = _now()
        with self._lock:
            self._purge(now)
            turns = self._items.setdefault(conversation_id, deque(maxlen=self.max_turns))
            turns.append((now, user, assistant))
            self._items.move_to_end(conversation_id)

    def reset(self, conversation_id: str) -> None:
        with self._lock:
            self._items.pop(conversation_id, None)


def _planner_calls(value: Any) -> tuple[list[PlannedCall] | None, str | None]:
    if not isinstance(value, dict) or set(value) != {"tool_calls", "needs_final_synthesis"}:
        return None, "planner response does not match the strict plan contract"
    raw_calls = value.get("tool_calls")
    if not isinstance(raw_calls, list) or len(raw_calls) > MAX_LOCAL_TOOL_CALLS:
        return None, "planner exceeded the local tool-call budget"
    if value.get("needs_final_synthesis") is not True:
        return None, "planner did not request the required final synthesis"
    calls: list[PlannedCall] = []
    mutation_count = 0
    for item in raw_calls:
        if not isinstance(item, dict) or set(item) != {"name", "arguments"}:
            return None, "planner tool call shape is invalid"
        name, raw_arguments = item.get("name"), item.get("arguments")
        # The OAuth CLI strict-schema subset does not permit discriminated
        # argument objects.  The planner therefore returns one closed envelope
        # containing nullable fields for every approved tool argument.  Null is
        # not an argument: remove it before applying the normal per-tool host
        # validation below.
        if not isinstance(raw_arguments, dict):
            return None, "planner tool arguments are invalid"
        arguments = {key: item_value for key, item_value in raw_arguments.items() if item_value is not None}
        error = ConversationToolHost.validate_call(name, arguments)
        if error:
            return None, f"planner requested an invalid tool call: {error}"
        if name in MUTATION_TOOLS:
            mutation_count += 1
        calls.append(PlannedCall(name=name, arguments=arguments))
    if mutation_count > MAX_MUTATION_CALLS:
        return None, "planner exceeded the mutation-call budget"
    return calls, None


def _fact_ids(results: list[dict[str, Any]]) -> set[str]:
    output: set[str] = set()
    for result in results:
        facts = result.get("facts")
        if not isinstance(facts, list):
            continue
        for fact in facts:
            if isinstance(fact, dict) and isinstance(fact.get("fact_id"), str):
                output.add(fact["fact_id"])
    return output


class ConversationOrchestrator:
    """Two bounded Luna turns around a host-owned, typed local tool surface."""

    def __init__(
        self,
        *,
        context: RecentConversationContext | None = None,
        planner: Callable[..., dict[str, Any]] = invoke_conversation_planner,
        synthesizer: Callable[..., dict[str, Any]] = invoke_conversation_synthesis,
        host_factory: Callable[..., ConversationToolHost] = ConversationToolHost,
    ) -> None:
        self.context = context or RecentConversationContext()
        self.planner = planner
        self.synthesizer = synthesizer
        self.host_factory = host_factory

    def ask(
        self,
        question: str,
        *,
        base_url: str = "http://127.0.0.1:48174",
        room_id: str = "office",
        effort: str = "low",
        timeout_seconds: int = 120,
        source_surface: str = "sentry_ask",
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        started_at = time.monotonic()
        if not isinstance(question, str) or not question.strip():
            return {"query_id": str(uuid.uuid4()), "conversation_id": conversation_id, "as_of": None,
                    **unavailable_response("a non-empty user question is required"), "luna_invocations": 0,
                    "tool_calls": [], "tool_statuses": []}
        query_id = str(uuid.uuid4())
        conversation_id = conversation_id or f"one-shot-{query_id}"
        prior = self.context.prior(conversation_id)
        planner = self.planner(question, tool_catalog(), prior, effort=effort, timeout_seconds=timeout_seconds)
        if not planner.get("ok"):
            result = {"query_id": query_id, "conversation_id": conversation_id, "as_of": None,
                      **unavailable_response("bounded Luna planning failed"), "luna_invocations": 1,
                      "tool_calls": [], "tool_statuses": [], "luna_error": planner.get("error")}
            result["conversation_latency_ms"] = round((time.monotonic() - started_at) * 1000, 3)
            self.context.add(conversation_id, question, result["answer"])
            return result
        calls, validation_error = _planner_calls(planner.get("result"))
        if validation_error or calls is None:
            result = {"query_id": query_id, "conversation_id": conversation_id, "as_of": None,
                      **unavailable_response(validation_error or "planner result is invalid"), "luna_invocations": 1,
                      "tool_calls": [], "tool_statuses": []}
            result["conversation_latency_ms"] = round((time.monotonic() - started_at) * 1000, 3)
            self.context.add(conversation_id, question, result["answer"])
            return result
        host = self.host_factory(
            base_url=base_url, room_id=room_id, source_surface=source_surface,
            source_request_id=query_id,
        )
        tool_results = [host.execute(call.name, call.arguments) for call in calls]
        synthesis = self.synthesizer(question, tool_results, prior, effort=effort, timeout_seconds=timeout_seconds)
        common = {
            "query_id": query_id,
            "conversation_id": conversation_id,
            "as_of": _now().isoformat(),
            "tool_calls": [{"name": call.name, "arguments": call.arguments} for call in calls],
            "tool_statuses": [str(result.get("status", "unavailable")) for result in tool_results],
            "luna_invocations": 2,
            "conversation_latency_ms": round((time.monotonic() - started_at) * 1000, 3),
        }
        if not synthesis.get("ok"):
            result = {**common, **unavailable_response("bounded Luna synthesis failed"), "luna_error": synthesis.get("error")}
            self.context.add(conversation_id, question, result["answer"])
            return result
        answer = synthesis.get("result")
        validation_error = validate_grounded_response(answer, _fact_ids(tool_results))
        if validation_error:
            result = {**common, **unavailable_response(f"bounded Luna response failed validation: {validation_error}")}
            self.context.add(conversation_id, question, result["answer"])
            return result
        assert isinstance(answer, dict)
        result = {
            **common,
            **answer,
            "model": synthesis.get("model"),
            "reasoning_effort": synthesis.get("reasoning_effort"),
            "usage": {"planner": planner.get("usage", {}), "synthesis": synthesis.get("usage", {})},
        }
        self.context.add(conversation_id, question, answer["answer"])
        return result
