"""Metadata-only SQLite history for SENTRY room presence.

This is the first M2 persistence slice.  It records room state transitions and
presence sessions, never camera frames.  The store is deliberately independent
of the detector and tracker so the sensing backend can change without changing
the history contract.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .presence_state import RoomState


SCHEMA_VERSION = 1


def _utc_iso(value: datetime | str) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("history timestamps must be timezone-aware")
        return value.astimezone(timezone.utc).isoformat()
    return value


@dataclass(frozen=True)
class RoomStateRecord:
    room_id: str
    state: str
    updated_at: str
    camera_state: str | None
    person_count: int


class PresenceStore:
    """Persist current room state, semantic transitions, and sessions."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.database_path, timeout=5.0, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._lock = threading.RLock()
        self._migrate()

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "PresenceStore":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()

    def _migrate(self) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
            )
            applied = {
                row[0]
                for row in self._connection.execute("SELECT version FROM schema_migrations")
            }
            if SCHEMA_VERSION in applied:
                return
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS room_state (
                    room_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL CHECK (state IN ('empty', 'occupied', 'degraded', 'offline')),
                    updated_at TEXT NOT NULL,
                    camera_state TEXT,
                    person_count INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS presence_sessions (
                    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    status TEXT NOT NULL CHECK (status IN ('open', 'completed')),
                    FOREIGN KEY (room_id) REFERENCES room_state(room_id)
                );
                CREATE INDEX IF NOT EXISTS idx_presence_sessions_room_time
                    ON presence_sessions(room_id, started_at);
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    room_id TEXT NOT NULL,
                    session_id INTEGER,
                    source TEXT NOT NULL,
                    confidence REAL,
                    payload_json TEXT NOT NULL,
                    schema_version INTEGER NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES presence_sessions(session_id)
                );
                CREATE INDEX IF NOT EXISTS idx_events_room_time
                    ON events(room_id, occurred_at);
                """
            )
            self._connection.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (SCHEMA_VERSION, datetime.now(timezone.utc).isoformat()),
            )

    @staticmethod
    def _observation_value(observation: Any, name: str, default: Any = None) -> Any:
        if isinstance(observation, dict):
            return observation.get(name, default)
        return getattr(observation, name, default)

    def record_observation(self, observation: Any, *, room_id: str = "office") -> None:
        """Record one structured observation and any state-derived events.

        The accepted input is either an ``Observation`` instance or its
        ``as_dict`` representation.  Only state, timestamps, counts, and
        bounded diagnostic metadata are persisted.
        """

        state_value = self._observation_value(observation, "room_state", RoomState.EMPTY)
        state_value = str(getattr(state_value, "value", state_value))
        if state_value not in {state.value for state in RoomState}:
            raise ValueError(f"invalid room state: {state_value}")
        occurred_at = _utc_iso(self._observation_value(observation, "captured_at"))
        camera_state = self._observation_value(observation, "camera_state")
        camera_state = str(getattr(camera_state, "value", camera_state)) if camera_state is not None else None
        people = self._observation_value(observation, "people", []) or []
        transition = self._observation_value(observation, "room_state_transition")
        confidence = self._observation_value(observation, "max_person_confidence")
        payload = {
            "frame_sequence": self._observation_value(observation, "frame_sequence"),
            "detector_evidence": bool(self._observation_value(observation, "detector_evidence", False)),
            "people_visible": sum(1 for person in people if person.get("visible", True)),
        }

        with self._lock, self._connection:
            previous = self._connection.execute(
                "SELECT state FROM room_state WHERE room_id = ?", (room_id,)
            ).fetchone()
            previous_state = previous[0] if previous else None
            self._connection.execute(
                "INSERT INTO room_state(room_id, state, updated_at, camera_state, person_count) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(room_id) DO UPDATE SET state=excluded.state, "
                "updated_at=excluded.updated_at, camera_state=excluded.camera_state, "
                "person_count=excluded.person_count",
                (room_id, state_value, occurred_at, camera_state, payload["people_visible"]),
            )
            if transition and transition != f"{previous_state}->{state_value}":
                # A transition from a fresh process may be supplied by the
                # state machine without a prior persisted row; trust the
                # structured transition only for event selection.
                transition = None
            if transition == "empty->occupied":
                session = self._connection.execute(
                    "SELECT session_id FROM presence_sessions "
                    "WHERE room_id = ? AND status = 'open' ORDER BY session_id DESC LIMIT 1",
                    (room_id,),
                ).fetchone()
                session_id = session[0] if session else None
                if session_id is None:
                    session_id = self._connection.execute(
                        "INSERT INTO presence_sessions(room_id, started_at, status) VALUES (?, ?, 'open')",
                        (room_id, occurred_at),
                    ).lastrowid
                self._insert_event("room.became_occupied", occurred_at, room_id, session_id, confidence, payload)
                self._insert_event("presence.session_started", occurred_at, room_id, session_id, confidence, payload)
            elif transition == "occupied->empty":
                session = self._connection.execute(
                    "SELECT session_id FROM presence_sessions "
                    "WHERE room_id = ? AND status = 'open' ORDER BY session_id DESC LIMIT 1",
                    (room_id,),
                ).fetchone()
                session_id = session[0] if session else None
                if session_id is not None:
                    self._connection.execute(
                        "UPDATE presence_sessions SET ended_at = ?, status = 'completed' WHERE session_id = ?",
                        (occurred_at, session_id),
                    )
                self._insert_event("room.became_empty", occurred_at, room_id, session_id, confidence, payload)
                self._insert_event("presence.session_ended", occurred_at, room_id, session_id, confidence, payload)
            elif state_value in {RoomState.DEGRADED.value, RoomState.OFFLINE.value} and state_value != previous_state:
                self._insert_event(
                    f"room.camera_{state_value}", occurred_at, room_id, None, confidence, payload
                )
            elif previous_state in {RoomState.DEGRADED.value, RoomState.OFFLINE.value} and state_value in {
                RoomState.EMPTY.value,
                RoomState.OCCUPIED.value,
            }:
                self._insert_event("room.camera_online", occurred_at, room_id, None, confidence, payload)

    def _insert_event(
        self,
        event_type: str,
        occurred_at: str,
        room_id: str,
        session_id: int | None,
        confidence: float | None,
        payload: dict[str, Any],
    ) -> None:
        self._connection.execute(
            "INSERT INTO events(event_id, event_type, occurred_at, room_id, session_id, source, confidence, payload_json, schema_version) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                event_type,
                occurred_at,
                room_id,
                session_id,
                "sentry_perception",
                float(confidence) if confidence is not None else None,
                json.dumps(payload, sort_keys=True),
                1,
            ),
        )

    def current_state(self, room_id: str = "office") -> RoomStateRecord | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT room_id, state, updated_at, camera_state, person_count FROM room_state WHERE room_id = ?",
                (room_id,),
            ).fetchone()
        return RoomStateRecord(**dict(row)) if row else None

    def sessions(self, room_id: str = "office", limit: int = 100) -> list[dict[str, Any]]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        with self._lock:
            rows = self._connection.execute(
                "SELECT session_id, room_id, started_at, ended_at, status FROM presence_sessions "
                "WHERE room_id = ? ORDER BY started_at DESC LIMIT ?",
                (room_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def events(self, room_id: str = "office", limit: int = 100) -> list[dict[str, Any]]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        with self._lock:
            rows = self._connection.execute(
                "SELECT event_id, event_type, occurred_at, room_id, session_id, source, confidence, payload_json, schema_version "
                "FROM events WHERE room_id = ? ORDER BY occurred_at DESC LIMIT ?",
                (room_id, limit),
            ).fetchall()
        values = []
        for row in rows:
            value = dict(row)
            value["payload"] = json.loads(value.pop("payload_json"))
            values.append(value)
        return values
