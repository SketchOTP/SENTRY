"""Deterministic recognition of SENTRY's deliberately narrow preference vocabulary."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PreferenceIntent:
    kind: str
    operation: str | None = None
    value: str | None = None
    feedback_type: str | None = None
    query_topic: str | None = None


_GREETING = r"(?:greet|greeting|acknowledge|acknowledgement|welcome)"


def select_preference_intent(question: str) -> PreferenceIntent | None:
    if not isinstance(question, str):
        return None
    text = " ".join(question.lower().split()).strip(" .!?\"")

    if re.search(r"\b(that was helpful|that was useful)\b", text):
        return PreferenceIntent("feedback", feedback_type="helpful")
    if re.search(r"\b(that (?:wasn't|was not) helpful|that wasn't useful|that was not useful)\b", text):
        return PreferenceIntent("feedback", feedback_type="not_helpful")
    if re.search(r"\b(that was too much|that was too frequent|too many greetings?)\b", text):
        return PreferenceIntent("feedback", feedback_type="too_frequent")
    if re.search(r"\b(?:don't|do not|dont) (?:do )?(?:that|it) again\b", text) or re.search(r"\bdo not repeat (?:that|it)\b", text):
        return PreferenceIntent("feedback", feedback_type="do_not_repeat")

    if re.search(rf"\b(?:don't|do not|dont|stop)\s+{_GREETING}.*\b(?:come in|enter|recognize|recognised|recognized|arrival)\b", text):
        return PreferenceIntent("write", operation="set", value="suppress")
    if re.search(rf"\b(?:you can|you may|please)\s+{_GREETING}.*\b(?:again|come in|enter|recognize|arrival)\b", text):
        return PreferenceIntent("write", operation="set", value="allow")
    if re.search(rf"\b(?:forget|reset)\b.*\b{_GREETING}\b", text):
        return PreferenceIntent("write", operation="clear")

    if (
        re.search(r"\bwhat do you remember\b.*\b(?:greeting|acknowledg|welcome)\b", text)
        or re.search(r"\bdo i have\b.*\b(?:arrival|greeting|acknowledg|welcome)\b.*\bdisabled\b", text)
        or re.search(r"\bdo you greet me\b.*\brecogn", text)
        or re.search(r"\bwhy didn['’]?t you greet me\b", text)
    ):
        return PreferenceIntent("query", query_topic="why" if re.search(r"\bwhy didn['’]?t you greet me\b", text) else "status")

    if re.search(r"\bremember\b|\bkeep in mind\b", text):
        return PreferenceIntent("unsupported_memory")
    return None
