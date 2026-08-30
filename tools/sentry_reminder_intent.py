"""Deterministic intent routing for the single supported office reminder."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ReminderIntent:
    kind: str
    message: str | None = None


_CREATE_PATTERNS = (
    re.compile(r"^remind me next time (?:i come into|i am in|i'm in) the office to (.+?)[.!?]*$", re.IGNORECASE),
    re.compile(r"^next time (?:i am in|i'm in) the office,? remind me to (.+?)[.!?]*$", re.IGNORECASE),
    re.compile(r"^remind me when you next see me in the office to (.+?)[.!?]*$", re.IGNORECASE),
)


def select_reminder_intent(question: str) -> ReminderIntent | None:
    if not isinstance(question, str):
        return None
    text = " ".join(question.strip().split())
    lowered = text.casefold()
    for pattern in _CREATE_PATTERNS:
        match = pattern.match(text)
        if match:
            message = match.group(1).strip()
            return ReminderIntent("create", message=message)
    if (
        ("office reminder" in lowered or "reminder" in lowered)
        and any(token in lowered for token in ("do i have", "what are you supposed", "what's my", "what is my", "pending"))
    ):
        return ReminderIntent("query")
    if any(phrase in lowered for phrase in ("cancel my office reminder", "forget my pending office reminder", "never mind about that office reminder")):
        return ReminderIntent("cancel")
    if lowered.startswith("remind me") or "reminder" in lowered:
        return ReminderIntent("unsupported")
    return None
