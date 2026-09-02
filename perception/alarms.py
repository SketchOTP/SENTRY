"""Durable one-shot SENTRY alarm delivery.

Alarms are claimed in SQLite before local speech. A claimed alarm found after a
restart is failed rather than replayed, providing the same honest at-most-once
crash policy as event reminders.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .presence_store import PresenceStore


@dataclass(frozen=True)
class AlarmOutcome:
    alarm_id: str
    scheduled_for: str
    status: str
    delivered_at: str | None = None
    failure_reason: str | None = None


class AlarmDispatcher:
    """Claim and deliver due alarms without invoking Codex/Luna."""

    def __init__(self, store: PresenceStore, *, speaker: Any) -> None:
        self.store = store
        self.speaker = speaker

    def process_due(self, *, now: datetime | None = None, limit: int = 10) -> list[AlarmOutcome]:
        evaluated = now or datetime.now(timezone.utc)
        outcomes: list[AlarmOutcome] = []
        for alarm in self.store.claim_due_alarms(now=evaluated, limit=limit):
            alarm_id = str(alarm["alarm_id"])
            try:
                delivered = bool(self.speaker.speak(f"Alarm. {alarm['label']}."))
            except Exception as exc:  # noqa: BLE001 - delivery failure must be persisted
                delivered = False
                reason = f"speaker_error:{type(exc).__name__}"
            else:
                reason = None if delivered else "speech_delivery_failed"
            finished = datetime.now(timezone.utc)
            status = "delivered" if delivered else "failed"
            record = self.store.finalize_alarm(
                alarm_id,
                status=status,
                timestamp=finished,
                failure_reason=reason,
            )
            outcomes.append(AlarmOutcome(
                alarm_id=alarm_id,
                scheduled_for=str(alarm["scheduled_for"]),
                status=status,
                delivered_at=record.get("delivered_at"),
                failure_reason=record.get("failure_reason"),
            ))
        return outcomes
