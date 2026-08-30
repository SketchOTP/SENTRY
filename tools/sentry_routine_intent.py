"""Deterministic routing for the bounded routine-conversation vocabulary."""

from __future__ import annotations

from dataclasses import dataclass


ROUTINE_TYPES = (
    "office_session_start_time",
    "office_session_duration",
    "office_absence_between_sessions",
    "primary_user_session_first_confirmed_time",
)
HABITUAL_TERMS = (
    "usually", "normally", "typically", "typical", "routine", "pattern",
    "generally", "most days", "on average", "tend to", "always", "every day",
)
GENERAL_TERMS = (
    "what have you learned about my routine",
    "what have you learned about my patterns",
    "what do you know about my routine",
    "what have you learned about routine",
    "what is my routine",
    "tell me about my routine",
)


@dataclass(frozen=True)
class RoutineIntent:
    routine_types: tuple[str, ...]
    scope: str
    unsupported: bool = False


def _scope(question: str) -> str:
    for name in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"):
        if name in question:
            return name
    if "weekend" in question:
        return "weekend"
    if "weekday" in question or "weekdays" in question:
        return "weekday"
    return "all_days"


def select_routine_intent(question: str) -> RoutineIntent | None:
    """Select a routine concept conservatively, without an LLM classification turn."""

    lowered = " ".join(question.lower().split())
    if not any(term in lowered for term in HABITUAL_TERMS):
        return None
    scope = _scope(lowered)
    if any(term in lowered for term in GENERAL_TERMS):
        return RoutineIntent(ROUTINE_TYPES, scope)
    if "pattern" in lowered and ("my" in lowered or "office" in lowered):
        return RoutineIntent(ROUTINE_TYPES, scope)
    if (
        ("first" in lowered and ("recogn" in lowered or "see me" in lowered or "confirm" in lowered))
        or "first recognize me" in lowered
        or "first see me" in lowered
    ):
        return RoutineIntent(("primary_user_session_first_confirmed_time",), scope)
    if any(term in lowered for term in ("between sessions", "office empty", "usually gone", "normally gone", "typically gone", "absence")):
        return RoutineIntent(("office_absence_between_sessions",), scope)
    if any(term in lowered for term in ("how long", "duration", "stay", "stays")) and any(
        term in lowered for term in ("session", "office", "occupied", "stay")
    ):
        return RoutineIntent(("office_session_duration",), scope)
    if any(term in lowered for term in ("come in", "arrive", "get here", "occupied", "office start", "start time", "here by", "here at")):
        return RoutineIntent(("office_session_start_time",), scope)
    return RoutineIntent((), scope, unsupported=True)


def routine_keys(intent: RoutineIntent) -> tuple[str, ...]:
    return tuple(f"{routine_type}:{intent.scope}" for routine_type in intent.routine_types)
