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
from .storage_mirror import (
    AtlasSnapshotMirror,
    ensure_local_database_path,
    recover_local_database,
)


SCHEMA_VERSION = 2


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

    def __init__(
        self,
        database_path: str | Path,
        *,
        atlas_mirror_path: str | Path | None = None,
        mirror_interval_seconds: float = 60.0,
    ) -> None:
        self.database_path = ensure_local_database_path(database_path)
        self.atlas_mirror_path = Path(atlas_mirror_path).expanduser() if atlas_mirror_path else None
        self.recovery_info = recover_local_database(self.database_path, self.atlas_mirror_path)
        self._connection = sqlite3.connect(self.database_path, timeout=5.0, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA busy_timeout = 5000")
        self._lock = threading.RLock()
        self._started = False
        self._mirror = (
            AtlasSnapshotMirror(self.database_path, self.atlas_mirror_path, mirror_interval_seconds)
            if self.atlas_mirror_path
            else None
        )
        self._migrate()

    def close(self) -> None:
        with self._lock:
            if self._connection is None:
                return
            if self._started:
                self.stop()
            self._connection.close()
            self._connection = None  # type: ignore[assignment]

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
            if 1 not in applied:
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
                    (1, datetime.now(timezone.utc).isoformat()),
                )
                applied.add(1)
            if 2 not in applied:
                columns = {
                    row[1]
                    for row in self._connection.execute("PRAGMA table_info(presence_sessions)")
                }
                if "start_reason" not in columns:
                    self._connection.execute(
                        "ALTER TABLE presence_sessions ADD COLUMN start_reason TEXT NOT NULL DEFAULT 'observed'"
                    )
                if "end_reason" not in columns:
                    self._connection.execute("ALTER TABLE presence_sessions ADD COLUMN end_reason TEXT")
                if "recovered_after_restart" not in columns:
                    self._connection.execute(
                        "ALTER TABLE presence_sessions ADD COLUMN recovered_after_restart INTEGER NOT NULL DEFAULT 0"
                    )
                if "end_time_uncertain" not in columns:
                    self._connection.execute(
                        "ALTER TABLE presence_sessions ADD COLUMN end_time_uncertain INTEGER NOT NULL DEFAULT 0"
                    )
                self._connection.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_one_open_presence_session "
                    "ON presence_sessions(room_id) WHERE status = 'open'"
                )
                self._connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (2, datetime.now(timezone.utc).isoformat()),
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

        mirror_required = False
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
                        "INSERT INTO presence_sessions(room_id, started_at, status, start_reason) VALUES (?, ?, 'open', 'observed')",
                        (room_id, occurred_at),
                    ).lastrowid
                    self._insert_event("room.became_occupied", occurred_at, room_id, session_id, confidence, payload)
                    self._insert_event("presence.session_started", occurred_at, room_id, session_id, confidence, payload)
                    mirror_required = True
            elif transition == "occupied->empty":
                session = self._connection.execute(
                    "SELECT session_id FROM presence_sessions "
                    "WHERE room_id = ? AND status = 'open' ORDER BY session_id DESC LIMIT 1",
                    (room_id,),
                ).fetchone()
                session_id = session[0] if session else None
                if session_id is not None:
                    self._connection.execute(
                        "UPDATE presence_sessions SET ended_at = ?, status = 'completed', end_reason = 'observed', "
                        "end_time_uncertain = 0 WHERE session_id = ?",
                        (occurred_at, session_id),
                    )
                self._insert_event("room.became_empty", occurred_at, room_id, session_id, confidence, payload)
                self._insert_event("presence.session_ended", occurred_at, room_id, session_id, confidence, payload)
                mirror_required = True
            elif state_value in {RoomState.DEGRADED.value, RoomState.OFFLINE.value} and state_value != previous_state:
                self._insert_event(
                    f"room.camera_{state_value}", occurred_at, room_id, None, confidence, payload
                )
                mirror_required = True
            elif previous_state in {RoomState.DEGRADED.value, RoomState.OFFLINE.value} and state_value in {
                RoomState.EMPTY.value,
                RoomState.OCCUPIED.value,
            }:
                self._insert_event("room.camera_online", occurred_at, room_id, None, confidence, payload)
                mirror_required = True
        self._maybe_mirror(force=mirror_required)

    def start(self, started_at: datetime | str | None = None) -> None:
        """Record one process start and any local-database recovery provenance."""

        occurred_at = _utc_iso(started_at or datetime.now(timezone.utc))
        with self._lock, self._connection:
            if self._started:
                return
            payload = {"recovery": self.recovery_info} if self.recovery_info.get("recovered") else {}
            self._insert_event("system.started", occurred_at, "office", None, None, payload)
            self._started = True
        self._maybe_mirror(force=True)

    def stop(self, stopped_at: datetime | str | None = None) -> None:
        """Record a clean process stop; crashes do not call this method."""

        occurred_at = _utc_iso(stopped_at or datetime.now(timezone.utc))
        with self._lock, self._connection:
            if not self._started:
                return
            self._insert_event("system.stopped", occurred_at, "office", None, None, {})
            self._started = False
        self._maybe_mirror(force=True)

    def reconcile_after_restart(self, observation: Any, *, room_id: str = "office") -> None:
        """Reconcile the first structured observation after a process restart."""

        state_value = self._observation_value(observation, "room_state", RoomState.EMPTY)
        state_value = str(getattr(state_value, "value", state_value))
        occurred_at = _utc_iso(self._observation_value(observation, "captured_at"))
        confidence = self._observation_value(observation, "max_person_confidence")
        payload = {
            "recovered_after_restart": True,
            "end_time_uncertain": state_value == RoomState.EMPTY.value,
        }
        with self._lock:
            previous = self._connection.execute(
                "SELECT state FROM room_state WHERE room_id = ?", (room_id,)
            ).fetchone()
            open_session = self._connection.execute(
                "SELECT session_id FROM presence_sessions WHERE room_id = ? AND status = 'open'",
                (room_id,),
            ).fetchone()
        if previous is None:
            self.record_observation(observation, room_id=room_id)
            return
        if state_value == RoomState.OCCUPIED.value and open_session:
            self._record_reconciled_observation(observation, room_id, "occupied", open_session[0], payload)
            return
        if state_value == RoomState.EMPTY.value and open_session:
            with self._lock, self._connection:
                session_id = open_session[0]
                self._upsert_room_state(observation, room_id)
                self._connection.execute(
                    "UPDATE presence_sessions SET ended_at = ?, status = 'completed', end_reason = 'restart_reconciled', "
                    "recovered_after_restart = 1, end_time_uncertain = 1 WHERE session_id = ?",
                    (occurred_at, session_id),
                )
                self._insert_event(
                    "room.became_empty", occurred_at, room_id, session_id, confidence,
                    {**self._observation_payload(observation), **payload},
                )
                self._insert_event(
                    "presence.session_ended", occurred_at, room_id, session_id, confidence,
                    {**self._observation_payload(observation), **payload},
                )
                self._insert_event(
                    "presence.session_reconciled", occurred_at, room_id, session_id, confidence, payload
                )
            self._maybe_mirror(force=True)
            return
        self.record_observation(observation, room_id=room_id)

    def _record_reconciled_observation(
        self, observation: Any, room_id: str, state_value: str, session_id: int, payload: dict[str, Any]
    ) -> None:
        occurred_at = _utc_iso(self._observation_value(observation, "captured_at"))
        confidence = self._observation_value(observation, "max_person_confidence")
        with self._lock, self._connection:
            self._upsert_room_state(observation, room_id)
            self._insert_event(
                "presence.restart_reconciled", occurred_at, room_id, session_id, confidence, payload
            )
        self._maybe_mirror(force=True)

    def _observation_payload(self, observation: Any) -> dict[str, Any]:
        people = self._observation_value(observation, "people", []) or []
        return {
            "frame_sequence": self._observation_value(observation, "frame_sequence"),
            "detector_evidence": bool(self._observation_value(observation, "detector_evidence", False)),
            "people_visible": sum(1 for person in people if person.get("visible", True)),
        }

    def _upsert_room_state(self, observation: Any, room_id: str) -> None:
        state_value = self._observation_value(observation, "room_state", RoomState.EMPTY)
        state_value = str(getattr(state_value, "value", state_value))
        occurred_at = _utc_iso(self._observation_value(observation, "captured_at"))
        camera_state = self._observation_value(observation, "camera_state")
        camera_state = str(getattr(camera_state, "value", camera_state)) if camera_state is not None else None
        payload = self._observation_payload(observation)
        self._connection.execute(
            "INSERT INTO room_state(room_id, state, updated_at, camera_state, person_count) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(room_id) DO UPDATE SET state=excluded.state, updated_at=excluded.updated_at, "
            "camera_state=excluded.camera_state, person_count=excluded.person_count",
            (room_id, state_value, occurred_at, camera_state, payload["people_visible"]),
        )

    def _maybe_mirror(self, *, force: bool = False) -> None:
        if self._mirror is None:
            return
        with self._lock:
            self._mirror.mirror(self._connection, force=force)

    def mirror_status(self) -> dict[str, Any]:
        if self._mirror is None:
            return {"enabled": False, "status": "disabled"}
        return self._mirror.status.as_dict()

    def health(self) -> dict[str, Any]:
        with self._lock:
            try:
                schema_version = self._connection.execute(
                    "SELECT MAX(version) FROM schema_migrations"
                ).fetchone()[0]
                db_available = True
            except sqlite3.Error as exc:
                schema_version = None
                db_available = False
                database_error = f"{type(exc).__name__}: {exc}"
        result = {
            "db_available": db_available,
            "schema_version": schema_version,
            "atlas_mirror": self.mirror_status(),
        }
        if not db_available:
            result["last_persistence_error"] = database_error
        elif self._mirror is not None and self._mirror.status.last_error:
            result["last_persistence_error"] = self._mirror.status.last_error
        else:
            result["last_persistence_error"] = None
        return result

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
                SCHEMA_VERSION,
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
                "SELECT session_id, room_id, started_at, ended_at, status, start_reason, end_reason, "
                "recovered_after_restart, end_time_uncertain FROM presence_sessions "
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
