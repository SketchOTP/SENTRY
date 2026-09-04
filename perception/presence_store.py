"""Metadata-only SQLite history for SENTRY room presence.

This is the first M2 persistence slice.  It records room state transitions and
presence sessions, never camera frames.  The store is deliberately independent
of the detector and tracker so the sensing backend can change without changing
the history contract.
"""

from __future__ import annotations

import json
import hashlib
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .presence_state import RoomState
from .storage_mirror import (
    AtlasSnapshotMirror,
    ensure_local_database_path,
    recover_local_database,
)


SCHEMA_VERSION = 9
PREFERENCE_KEY = "proactivity.primary_user_session_acknowledgement"
PREFERENCE_VALUES = {"allow", "suppress"}
FEEDBACK_TYPES = {"helpful", "not_helpful", "too_frequent", "do_not_repeat"}


def _utc_iso(value: datetime | str) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("history timestamps must be timezone-aware")
        return value.astimezone(timezone.utc).isoformat()
    return value


def _parse_utc_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class RoomStateRecord:
    room_id: str
    state: str
    updated_at: str
    camera_state: str | None
    person_count: int
    people: list[dict[str, Any]] = field(default_factory=list)


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
        self.reconcile_claimed_reminders()
        self.reconcile_claimed_alarms()

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
        migrated = False
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
                migrated = True
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
                migrated = True
            if 3 not in applied:
                columns = {row[1] for row in self._connection.execute("PRAGMA table_info(room_state)")}
                if "people_json" not in columns:
                    self._connection.execute(
                        "ALTER TABLE room_state ADD COLUMN people_json TEXT NOT NULL DEFAULT '[]'"
                    )
                self._connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS persons (
                        person_id TEXT PRIMARY KEY,
                        display_name TEXT NOT NULL,
                        enrollment_status TEXT NOT NULL CHECK (enrollment_status IN ('active', 'removed')),
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS identity_profiles (
                        person_id TEXT PRIMARY KEY,
                        backend TEXT NOT NULL,
                        model_version TEXT NOT NULL,
                        model_checksum TEXT NOT NULL,
                        prototype BLOB NOT NULL,
                        embedding_dim INTEGER NOT NULL,
                        calibrated_threshold REAL NOT NULL,
                        sample_count INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY (person_id) REFERENCES persons(person_id) ON DELETE CASCADE
                    );
                    """
                )
                self._connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (3, datetime.now(timezone.utc).isoformat()),
                )
                applied.add(3)
                migrated = True
            if 4 not in applied:
                self._connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS proactive_actions (
                        action_id TEXT PRIMARY KEY,
                        source_event_id TEXT NOT NULL UNIQUE,
                        candidate_key TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        person_id TEXT,
                        session_id INTEGER,
                        event_timestamp TEXT NOT NULL,
                        evaluated_at TEXT NOT NULL,
                        eligibility_result TEXT NOT NULL CHECK (eligibility_result IN ('eligible', 'suppressed')),
                        suppression_reason TEXT,
                        judge_invoked INTEGER NOT NULL DEFAULT 0 CHECK (judge_invoked IN (0, 1)),
                        judge_model TEXT,
                        judge_effort TEXT,
                        judge_decision TEXT CHECK (judge_decision IS NULL OR judge_decision IN ('speak', 'silent')),
                        cited_fact_ids_json TEXT NOT NULL DEFAULT '[]',
                        utterance TEXT,
                        delivery_status TEXT NOT NULL DEFAULT 'not_attempted'
                            CHECK (delivery_status IN ('not_attempted', 'delivered', 'failed', 'suppressed')),
                        delivered_at TEXT,
                        FOREIGN KEY (session_id) REFERENCES presence_sessions(session_id)
                    );
                    CREATE INDEX IF NOT EXISTS idx_proactive_actions_candidate
                        ON proactive_actions(candidate_key, evaluated_at);
                    CREATE INDEX IF NOT EXISTS idx_proactive_actions_person_time
                        ON proactive_actions(person_id, evaluated_at);
                    """
                )
                self._connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (4, datetime.now(timezone.utc).isoformat()),
                )
                applied.add(4)
                migrated = True
            if 5 not in applied:
                self._connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS routine_snapshots (
                        snapshot_id TEXT PRIMARY KEY,
                        routine_key TEXT NOT NULL,
                        routine_type TEXT NOT NULL,
                        scope TEXT NOT NULL,
                        room_id TEXT NOT NULL,
                        person_id TEXT,
                        timezone TEXT NOT NULL,
                        algorithm_version TEXT NOT NULL,
                        window_start TEXT NOT NULL,
                        window_end TEXT NOT NULL,
                        source_as_of TEXT NOT NULL,
                        source_fingerprint TEXT NOT NULL,
                        generated_at TEXT NOT NULL,
                        sample_count INTEGER NOT NULL,
                        distinct_date_count INTEGER NOT NULL,
                        maturity_status TEXT NOT NULL CHECK (maturity_status IN ('insufficient', 'observed', 'stable')),
                        statistics_json TEXT NOT NULL,
                        exclusions_json TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_routine_snapshots_key_generated
                        ON routine_snapshots(routine_key, generated_at DESC);
                    CREATE INDEX IF NOT EXISTS idx_routine_snapshots_source
                        ON routine_snapshots(source_fingerprint, algorithm_version);
                    """
                )
                self._connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (5, datetime.now(timezone.utc).isoformat()),
                )
                applied.add(5)
                migrated = True
            if 6 not in applied:
                self._connection.executescript(
                    f"""
                    CREATE TABLE IF NOT EXISTS preference_events (
                        preference_event_id TEXT PRIMARY KEY,
                        person_id TEXT NOT NULL,
                        preference_key TEXT NOT NULL CHECK (preference_key = '{PREFERENCE_KEY}'),
                        operation TEXT NOT NULL CHECK (operation IN ('set', 'clear')),
                        value_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        source_surface TEXT NOT NULL,
                        source_request_id TEXT NOT NULL,
                        supersedes_event_id TEXT,
                        UNIQUE(source_surface, source_request_id)
                    );
                    CREATE INDEX IF NOT EXISTS idx_preference_events_current
                        ON preference_events(person_id, preference_key, created_at DESC);
                    CREATE TABLE IF NOT EXISTS proactive_feedback (
                        feedback_id TEXT PRIMARY KEY,
                        action_id TEXT NOT NULL,
                        person_id TEXT NOT NULL,
                        feedback_type TEXT NOT NULL CHECK (feedback_type IN ('helpful', 'not_helpful', 'too_frequent', 'do_not_repeat')),
                        created_at TEXT NOT NULL,
                        source_surface TEXT NOT NULL,
                        source_request_id TEXT NOT NULL UNIQUE,
                        resulting_preference_event_id TEXT,
                        FOREIGN KEY (action_id) REFERENCES proactive_actions(action_id),
                        FOREIGN KEY (resulting_preference_event_id) REFERENCES preference_events(preference_event_id)
                    );
                    CREATE INDEX IF NOT EXISTS idx_proactive_feedback_action
                        ON proactive_feedback(action_id, created_at DESC);
                    """
                )
                self._connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (6, datetime.now(timezone.utc).isoformat()),
                )
                migrated = True
                applied.add(6)
            if 7 not in applied:
                self._connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS weather_snapshots (
                        snapshot_id TEXT PRIMARY KEY,
                        provider TEXT NOT NULL CHECK (provider = 'nws'),
                        location_label TEXT NOT NULL,
                        latitude REAL NOT NULL,
                        longitude REAL NOT NULL,
                        timezone TEXT NOT NULL,
                        fetched_at TEXT NOT NULL,
                        source_updated_at TEXT,
                        fresh_until TEXT NOT NULL,
                        source_fingerprint TEXT NOT NULL,
                        current_json TEXT NOT NULL,
                        hourly_json TEXT NOT NULL,
                        alerts_json TEXT NOT NULL,
                        source_metadata_json TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_weather_snapshots_location_time
                        ON weather_snapshots(location_label, fetched_at DESC);
                    CREATE INDEX IF NOT EXISTS idx_weather_snapshots_fingerprint
                        ON weather_snapshots(source_fingerprint, fetched_at DESC);
                    """
                )
                self._connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (7, datetime.now(timezone.utc).isoformat()),
                )
                migrated = True
            if 8 not in applied:
                self._connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS event_reminders (
                        reminder_id TEXT PRIMARY KEY,
                        person_id TEXT NOT NULL CHECK (person_id = 'primary_user'),
                        room_id TEXT NOT NULL CHECK (room_id = 'office'),
                        trigger_kind TEXT NOT NULL CHECK (trigger_kind = 'next_primary_user_office_session'),
                        message TEXT NOT NULL CHECK (length(message) BETWEEN 1 AND 120),
                        created_at TEXT NOT NULL,
                        created_session_id INTEGER,
                        source_surface TEXT NOT NULL,
                        source_request_id TEXT NOT NULL,
                        status TEXT NOT NULL CHECK (status IN ('pending', 'claimed', 'delivered', 'failed', 'cancelled')),
                        claimed_at TEXT,
                        trigger_event_id TEXT,
                        trigger_session_id INTEGER,
                        delivery_action_id TEXT,
                        delivered_at TEXT,
                        failed_at TEXT,
                        cancelled_at TEXT,
                        cancelled_source_surface TEXT,
                        cancelled_source_request_id TEXT,
                        failure_reason TEXT,
                        UNIQUE(source_surface, source_request_id),
                        FOREIGN KEY (created_session_id) REFERENCES presence_sessions(session_id),
                        FOREIGN KEY (trigger_session_id) REFERENCES presence_sessions(session_id),
                        FOREIGN KEY (delivery_action_id) REFERENCES proactive_actions(action_id)
                    );
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_one_pending_event_reminder
                        ON event_reminders(person_id, room_id, trigger_kind) WHERE status = 'pending';
                    CREATE INDEX IF NOT EXISTS idx_event_reminders_status
                        ON event_reminders(status, created_at);
                    """
                )
                self._connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (8, datetime.now(timezone.utc).isoformat()),
                )
                migrated = True
                applied.add(8)
            if 9 not in applied:
                self._connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS alarms (
                        alarm_id TEXT PRIMARY KEY,
                        person_id TEXT NOT NULL CHECK (person_id = 'primary_user'),
                        label TEXT NOT NULL CHECK (length(label) BETWEEN 1 AND 120),
                        scheduled_for TEXT NOT NULL,
                        display_timezone TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        source_surface TEXT NOT NULL,
                        source_request_id TEXT NOT NULL,
                        status TEXT NOT NULL CHECK (status IN ('pending', 'claimed', 'delivered', 'failed', 'cancelled')),
                        claimed_at TEXT,
                        delivered_at TEXT,
                        failed_at TEXT,
                        cancelled_at TEXT,
                        cancelled_source_surface TEXT,
                        cancelled_source_request_id TEXT,
                        failure_reason TEXT,
                        UNIQUE(source_surface, source_request_id)
                    );
                    CREATE INDEX IF NOT EXISTS idx_alarms_due
                        ON alarms(status, scheduled_for);
                    CREATE INDEX IF NOT EXISTS idx_alarms_person_time
                        ON alarms(person_id, created_at DESC);
                    """
                )
                self._connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (9, datetime.now(timezone.utc).isoformat()),
                )
                migrated = True
                applied.add(9)
        if migrated:
            self._maybe_mirror(force=True)

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
        people_payload = self._people_payload(people)
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
                "INSERT INTO room_state(room_id, state, updated_at, camera_state, person_count, people_json) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(room_id) DO UPDATE SET state=excluded.state, "
                "updated_at=excluded.updated_at, camera_state=excluded.camera_state, "
                "person_count=excluded.person_count, people_json=excluded.people_json",
                (room_id, state_value, occurred_at, camera_state, payload["people_visible"], json.dumps(people_payload, sort_keys=True)),
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
            self._record_identity_events(people_payload, room_id, occurred_at, confidence)
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
            # The room remained occupied across a process gap, but continuity of
            # that presence was not observed. Preserve that boundary on new
            # records; older records derive it from their restart/system events.
            self._connection.execute(
                "UPDATE presence_sessions SET recovered_after_restart = 1 WHERE session_id = ?",
                (session_id,),
            )
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

    @staticmethod
    def _people_payload(people: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Allow-list track/identity metadata; never persist pixels or embeddings."""

        allowed = {
            "track_id", "bbox", "confidence", "visible", "missed_frames",
            "person_id", "identity_state", "identity_confidence", "face_quality",
        }
        return [{key: value for key, value in person.items() if key in allowed} for person in people]

    def _record_identity_events(
        self, people: list[dict[str, Any]], room_id: str, occurred_at: str, confidence: float | None
    ) -> None:
        for person in people:
            if person.get("identity_state") != "recognized" or not person.get("person_id"):
                continue
            session = self._connection.execute(
                "SELECT session_id FROM presence_sessions WHERE room_id = ? AND status = 'open' "
                "ORDER BY session_id DESC LIMIT 1", (room_id,)
            ).fetchone()
            session_id = session[0] if session else None
            duplicate = self._connection.execute(
                "SELECT 1 FROM events WHERE event_type = 'person.identified' AND room_id = ? "
                "AND COALESCE(session_id, -1) = COALESCE(?, -1) "
                "AND json_extract(payload_json, '$.track_id') = ? "
                "AND json_extract(payload_json, '$.person_id') = ? LIMIT 1",
                (room_id, session_id, person.get("track_id"), str(person["person_id"])),
            ).fetchone()
            if duplicate:
                continue
            self._insert_event(
                "person.identified", occurred_at, room_id, session_id,
                person.get("identity_confidence", confidence),
                {
                    "track_id": person.get("track_id"),
                    "person_id": person["person_id"],
                    "identity_state": "recognized",
                    "identity_confidence": person.get("identity_confidence"),
                },
            )

    def _upsert_room_state(self, observation: Any, room_id: str) -> None:
        state_value = self._observation_value(observation, "room_state", RoomState.EMPTY)
        state_value = str(getattr(state_value, "value", state_value))
        occurred_at = _utc_iso(self._observation_value(observation, "captured_at"))
        camera_state = self._observation_value(observation, "camera_state")
        camera_state = str(getattr(camera_state, "value", camera_state)) if camera_state is not None else None
        payload = self._observation_payload(observation)
        people = self._observation_value(observation, "people", []) or []
        self._connection.execute(
            "INSERT INTO room_state(room_id, state, updated_at, camera_state, person_count, people_json) VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(room_id) DO UPDATE SET state=excluded.state, updated_at=excluded.updated_at, "
            "camera_state=excluded.camera_state, person_count=excluded.person_count, people_json=excluded.people_json",
            (room_id, state_value, occurred_at, camera_state, payload["people_visible"], json.dumps(self._people_payload(people), sort_keys=True)),
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
                "SELECT room_id, state, updated_at, camera_state, person_count, people_json FROM room_state WHERE room_id = ?",
                (room_id,),
            ).fetchone()
        if not row:
            return None
        value = dict(row)
        value["people"] = json.loads(value.pop("people_json") or "[]")
        return RoomStateRecord(**value)

    def persons(self) -> list[dict[str, Any]]:
        """Return enrolled metadata without biometric prototype bytes."""

        with self._lock:
            rows = self._connection.execute(
                "SELECT person_id, display_name, enrollment_status, created_at, updated_at "
                "FROM persons WHERE enrollment_status = 'active' ORDER BY person_id"
            ).fetchall()
        return [dict(row) for row in rows]

    def identity_profile(self, person_id: str = "primary_user") -> dict[str, Any] | None:
        """Load a profile for in-memory matching; it is never an API/event field."""

        with self._lock:
            row = self._connection.execute(
                "SELECT p.person_id, p.display_name, i.backend, i.model_version, i.model_checksum, "
                "i.prototype, i.embedding_dim, i.calibrated_threshold, i.sample_count, i.created_at "
                "FROM persons p JOIN identity_profiles i ON i.person_id = p.person_id "
                "WHERE p.person_id = ? AND p.enrollment_status = 'active'", (person_id,)
            ).fetchone()
        if not row:
            return None
        import numpy as np
        value = dict(row)
        prototype = np.frombuffer(value.pop("prototype"), dtype=np.float32).copy()
        if prototype.size != int(value["embedding_dim"]):
            raise RuntimeError("stored identity prototype dimension mismatch")
        value["prototype"] = prototype
        return value

    def identity_profiles(self) -> list[dict[str, Any]]:
        """Load all active profiles for local in-memory matching only."""

        with self._lock:
            rows = self._connection.execute(
                "SELECT p.person_id, p.display_name, i.backend, i.model_version, i.model_checksum, "
                "i.prototype, i.embedding_dim, i.calibrated_threshold, i.sample_count, i.created_at "
                "FROM persons p JOIN identity_profiles i ON i.person_id = p.person_id "
                "WHERE p.enrollment_status = 'active' ORDER BY p.person_id"
            ).fetchall()
        import numpy as np
        profiles: list[dict[str, Any]] = []
        for row in rows:
            value = dict(row)
            prototype = np.frombuffer(value.pop("prototype"), dtype=np.float32).copy()
            if prototype.size != int(value["embedding_dim"]):
                raise RuntimeError("stored identity prototype dimension mismatch")
            value["prototype"] = prototype
            profiles.append(value)
        return profiles

    def identity_profile_revision(self) -> str:
        """Return a privacy-safe revision for the active enrollment catalog."""

        with self._lock:
            rows = self._connection.execute(
                "SELECT p.person_id, p.display_name, p.updated_at, i.backend, i.model_version, "
                "i.model_checksum, i.sample_count, i.created_at "
                "FROM persons p JOIN identity_profiles i ON i.person_id = p.person_id "
                "WHERE p.enrollment_status = 'active' ORDER BY p.person_id"
            ).fetchall()
        payload = json.dumps([dict(row) for row in rows], sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def enroll_identity(
        self, *, person_id: str, display_name: str, backend: str, model_version: str,
        model_checksum: str, prototype: Any, calibrated_threshold: float,
        sample_count: int, created_at: datetime | str | None = None,
    ) -> None:
        import numpy as np
        values = np.asarray(prototype, dtype=np.float32).reshape(-1)
        if not person_id or not display_name or not backend or not model_version or not model_checksum:
            raise ValueError("identity profile metadata is required")
        if values.size == 0 or not np.all(np.isfinite(values)) or sample_count <= 0:
            raise ValueError("identity prototype and sample_count are invalid")
        norm = float(np.linalg.norm(values))
        if norm <= 0:
            raise ValueError("identity prototype and sample_count are invalid")
        values = (values / norm).astype(np.float32)
        if not 0 <= float(calibrated_threshold) <= 1:
            raise ValueError("identity threshold must be between 0 and 1")
        timestamp = _utc_iso(created_at or datetime.now(timezone.utc))
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO persons(person_id, display_name, enrollment_status, created_at, updated_at) VALUES (?, ?, 'active', ?, ?) "
                "ON CONFLICT(person_id) DO UPDATE SET display_name=excluded.display_name, enrollment_status='active', updated_at=excluded.updated_at",
                (person_id, display_name, timestamp, timestamp),
            )
            self._connection.execute("DELETE FROM identity_profiles WHERE person_id = ?", (person_id,))
            self._connection.execute(
                "INSERT INTO identity_profiles(person_id, backend, model_version, model_checksum, prototype, embedding_dim, calibrated_threshold, sample_count, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (person_id, backend, model_version, model_checksum, sqlite3.Binary(values.tobytes()), int(values.size), float(calibrated_threshold), int(sample_count), timestamp),
            )
        self._maybe_mirror(force=True)

    def delete_identity(self, person_id: str = "primary_user") -> None:
        with self._lock, self._connection:
            self._connection.execute("DELETE FROM persons WHERE person_id = ?", (person_id,))
        self._maybe_mirror(force=True)

    def set_identity_threshold(self, threshold: float, person_id: str = "primary_user") -> None:
        if not 0 <= float(threshold) <= 1:
            raise ValueError("identity threshold must be between 0 and 1")
        with self._lock, self._connection:
            updated = self._connection.execute(
                "UPDATE identity_profiles SET calibrated_threshold = ? "
                "WHERE person_id = ? AND EXISTS ("
                "SELECT 1 FROM persons WHERE persons.person_id = identity_profiles.person_id "
                "AND enrollment_status = 'active')",
                (float(threshold), person_id),
            ).rowcount
        if updated != 1:
            raise ValueError(f"active identity profile not found: {person_id}")
        self._maybe_mirror(force=True)

    def sessions(self, room_id: str = "office", limit: int = 100) -> list[dict[str, Any]]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        with self._lock:
            rows = self._connection.execute(
                "SELECT session_id, room_id, started_at, ended_at, status, start_reason, end_reason, "
                "recovered_after_restart, end_time_uncertain, "
                "CASE WHEN recovered_after_restart = 1 OR EXISTS ("
                "SELECT 1 FROM events restart_event "
                "WHERE restart_event.room_id = presence_sessions.room_id "
                "AND restart_event.occurred_at >= presence_sessions.started_at "
                "AND (presence_sessions.ended_at IS NULL OR restart_event.occurred_at <= presence_sessions.ended_at) "
                "AND restart_event.event_type IN ('system.stopped', 'presence.restart_reconciled')"
                ") THEN 1 ELSE 0 END AS continuity_uncertain "
                "FROM presence_sessions "
                "WHERE room_id = ? ORDER BY started_at DESC LIMIT ?",
                (room_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def events(
        self,
        room_id: str = "office",
        limit: int = 100,
        *,
        event_type: str | None = None,
        person_id: str | None = None,
        since: str | None = None,
    ) -> list[dict[str, Any]]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        if (event_type is None) != (person_id is None):
            raise ValueError("event type and person id filters must be supplied together")
        if event_type is not None and event_type != "person.identified":
            raise ValueError("only primary-user identification filtering is supported")
        if person_id is not None and person_id != "primary_user":
            raise ValueError("only primary-user identification filtering is supported")
        if since is not None and _parse_utc_time(since) is None:
            raise ValueError("since must be a timezone-aware timestamp")
        query = (
            "SELECT event_id, event_type, occurred_at, room_id, session_id, source, confidence, payload_json, schema_version "
            "FROM events WHERE room_id = ?"
        )
        parameters: list[Any] = [room_id]
        if event_type is not None:
            query += " AND event_type = ? AND json_extract(payload_json, '$.person_id') = ?"
            parameters.extend((event_type, person_id))
        if since is not None:
            query += " AND occurred_at >= ?"
            parameters.append(_utc_iso(_parse_utc_time(since)))
        query += " ORDER BY occurred_at DESC LIMIT ?"
        parameters.append(limit)
        with self._lock:
            rows = self._connection.execute(query, parameters).fetchall()
        values = []
        for row in rows:
            value = dict(row)
            value["payload"] = json.loads(value.pop("payload_json"))
            values.append(value)
        return values

    def proactive_actions(self, room_id: str = "office", limit: int = 100) -> list[dict[str, Any]]:
        """Return metadata-only proactive decisions for diagnostics and API-free policy use."""

        if limit <= 0:
            raise ValueError("limit must be positive")
        with self._lock:
            rows = self._connection.execute(
                "SELECT a.action_id, a.source_event_id, a.candidate_key, a.event_type, a.person_id, "
                "a.session_id, a.event_timestamp, a.evaluated_at, a.eligibility_result, a.suppression_reason, "
                "a.judge_invoked, a.judge_model, a.judge_effort, a.judge_decision, a.cited_fact_ids_json, "
                "a.utterance, a.delivery_status, a.delivered_at "
                "FROM proactive_actions a LEFT JOIN events e ON e.event_id = a.source_event_id "
                "WHERE COALESCE(e.room_id, 'office') = ? ORDER BY a.evaluated_at DESC LIMIT ?",
                (room_id, limit),
            ).fetchall()
        values = []
        for row in rows:
            value = dict(row)
            value["judge_invoked"] = bool(value["judge_invoked"])
            value["cited_fact_ids"] = json.loads(value.pop("cited_fact_ids_json") or "[]")
            values.append(value)
        return values

    def proactive_action_for_event(self, event_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT action_id, source_event_id, candidate_key, event_type, person_id, session_id, "
                "event_timestamp, evaluated_at, eligibility_result, suppression_reason, judge_invoked, "
                "judge_model, judge_effort, judge_decision, cited_fact_ids_json, utterance, delivery_status, delivered_at "
                "FROM proactive_actions WHERE source_event_id = ?", (event_id,)
            ).fetchone()
        if row is None:
            return None
        value = dict(row)
        value["judge_invoked"] = bool(value["judge_invoked"])
        value["cited_fact_ids"] = json.loads(value.pop("cited_fact_ids_json") or "[]")
        return value

    def proactive_actions_for_candidate(self, candidate_key: str) -> list[dict[str, Any]]:
        return [item for item in self.proactive_actions(limit=1000) if item["candidate_key"] == candidate_key]

    def event_reminders(self, *, person_id: str = "primary_user", room_id: str = "office", limit: int = 100) -> list[dict[str, Any]]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        with self._lock:
            rows = self._connection.execute(
                "SELECT reminder_id, person_id, room_id, trigger_kind, message, created_at, created_session_id, "
                "source_surface, source_request_id, status, claimed_at, trigger_event_id, trigger_session_id, "
                "delivery_action_id, delivered_at, failed_at, cancelled_at, cancelled_source_surface, "
                "cancelled_source_request_id, failure_reason "
                "FROM event_reminders WHERE person_id = ? AND room_id = ? "
                "ORDER BY created_at DESC, rowid DESC LIMIT ?",
                (person_id, room_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def event_reminder(self, reminder_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT reminder_id, person_id, room_id, trigger_kind, message, created_at, created_session_id, "
                "source_surface, source_request_id, status, claimed_at, trigger_event_id, trigger_session_id, "
                "delivery_action_id, delivered_at, failed_at, cancelled_at, cancelled_source_surface, "
                "cancelled_source_request_id, failure_reason "
                "FROM event_reminders WHERE reminder_id = ?", (reminder_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    @staticmethod
    def _validate_reminder_message(message: str) -> str:
        if not isinstance(message, str):
            raise ValueError("reminder message must be a string")
        if any(ord(char) < 32 for char in message):
            raise ValueError("reminder message must be 1-120 characters without control characters")
        normalized = " ".join(message.strip().split())
        if not normalized or len(normalized) > 120:
            raise ValueError("reminder message must be 1-120 characters without control characters")
        return normalized

    def create_event_reminder(
        self, *, message: str, person_id: str = "primary_user", room_id: str = "office",
        trigger_kind: str = "next_primary_user_office_session", source_surface: str,
        source_request_id: str, created_at: datetime | str | None = None,
    ) -> dict[str, Any]:
        if person_id != "primary_user" or room_id != "office" or trigger_kind != "next_primary_user_office_session":
            raise ValueError("only the primary-user next-office-session reminder is supported")
        if not source_surface or not source_request_id:
            raise ValueError("reminder provenance is required")
        normalized = self._validate_reminder_message(message)
        timestamp = _utc_iso(created_at or datetime.now(timezone.utc))
        with self._lock, self._connection:
            existing = self._connection.execute(
                "SELECT * FROM event_reminders WHERE source_surface = ? AND source_request_id = ?",
                (source_surface, source_request_id),
            ).fetchone()
            if existing is not None:
                return dict(existing)
            active = self._connection.execute(
                "SELECT reminder_id FROM event_reminders WHERE person_id = ? AND room_id = ? "
                "AND trigger_kind = ? AND status = 'pending' LIMIT 1",
                (person_id, room_id, trigger_kind),
            ).fetchone()
            if active is not None:
                raise ValueError("an office reminder is already pending; cancel it first")
            open_session = self._connection.execute(
                "SELECT session_id FROM presence_sessions WHERE room_id = ? AND status = 'open' "
                "ORDER BY started_at DESC LIMIT 1", (room_id,),
            ).fetchone()
            reminder_id = str(uuid.uuid4())
            self._connection.execute(
                "INSERT INTO event_reminders(reminder_id, person_id, room_id, trigger_kind, message, created_at, "
                "created_session_id, source_surface, source_request_id, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')",
                (reminder_id, person_id, room_id, trigger_kind, normalized, timestamp,
                 open_session[0] if open_session else None, source_surface, source_request_id),
            )
            row = self._connection.execute("SELECT * FROM event_reminders WHERE reminder_id = ?", (reminder_id,)).fetchone()
        self._maybe_mirror(force=True)
        return dict(row)

    def cancel_event_reminder(self, reminder_id: str, *, source_surface: str, source_request_id: str,
                              cancelled_at: datetime | str | None = None) -> dict[str, Any]:
        if not reminder_id or not source_surface or not source_request_id:
            raise ValueError("reminder id and cancellation provenance are required")
        timestamp = _utc_iso(cancelled_at or datetime.now(timezone.utc))
        with self._lock, self._connection:
            row = self._connection.execute("SELECT * FROM event_reminders WHERE reminder_id = ?", (reminder_id,)).fetchone()
            if row is None:
                raise KeyError(f"reminder not found: {reminder_id}")
            if row["status"] == "cancelled":
                return dict(row)
            if row["status"] != "pending":
                raise ValueError(f"reminder cannot be cancelled from status {row['status']}")
            self._connection.execute(
                "UPDATE event_reminders SET status = 'cancelled', cancelled_at = ?, cancelled_source_surface = ?, "
                "cancelled_source_request_id = ? WHERE reminder_id = ? AND status = 'pending'",
                (timestamp, source_surface, source_request_id, reminder_id),
            )
            updated = self._connection.execute("SELECT * FROM event_reminders WHERE reminder_id = ?", (reminder_id,)).fetchone()
        self._maybe_mirror(force=True)
        return dict(updated)

    def pending_event_reminder_for_event(self, event: dict[str, Any]) -> dict[str, Any] | None:
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if event.get("event_type") != "person.identified" or payload.get("person_id") != "primary_user":
            return None
        event_time = _parse_utc_time(event.get("occurred_at"))
        session_id = event.get("session_id")
        if event_time is None or session_id is None:
            return None
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM event_reminders WHERE person_id = 'primary_user' AND room_id = ? "
                "AND trigger_kind = 'next_primary_user_office_session' AND status = 'pending' "
                "ORDER BY created_at ASC, rowid ASC", (event.get("room_id", "office"),),
            ).fetchall()
        for row in rows:
            created_at = _parse_utc_time(row["created_at"])
            if created_at is None or event_time <= created_at:
                continue
            if row["created_session_id"] is not None and row["created_session_id"] == session_id:
                continue
            return dict(row)
        return None

    def claim_event_reminder(
        self, *, reminder_id: str, action_id: str, source_event_id: str, session_id: int,
        event_timestamp: str, evaluated_at: str,
    ) -> dict[str, Any] | None:
        """Atomically reserve a pending reminder and its proactive action before speech."""

        with self._lock:
            try:
                with self._connection:
                    reminder = self._connection.execute(
                        "SELECT * FROM event_reminders WHERE reminder_id = ? AND status = 'pending'", (reminder_id,)
                    ).fetchone()
                    if reminder is None:
                        return None
                    self._connection.execute(
                        "INSERT INTO proactive_actions(action_id, source_event_id, candidate_key, event_type, person_id, session_id, "
                        "event_timestamp, evaluated_at, eligibility_result, suppression_reason, delivery_status) "
                        "VALUES (?, ?, ?, 'person.identified', 'primary_user', ?, ?, ?, 'eligible', NULL, 'not_attempted')",
                        (action_id, source_event_id, f"reminder:{reminder_id}:session:{session_id}", session_id, event_timestamp, evaluated_at),
                    )
                    updated = self._connection.execute(
                        "UPDATE event_reminders SET status = 'claimed', claimed_at = ?, trigger_event_id = ?, "
                        "trigger_session_id = ?, delivery_action_id = ? WHERE reminder_id = ? AND status = 'pending'",
                        (evaluated_at, source_event_id, session_id, action_id, reminder_id),
                    ).rowcount
                    if updated != 1:
                        raise sqlite3.IntegrityError("reminder was claimed concurrently")
            except sqlite3.IntegrityError:
                return None
        self._maybe_mirror(force=True)
        return dict(reminder)

    def finalize_event_reminder(self, reminder_id: str, *, status: str, timestamp: str,
                                action_id: str, failure_reason: str | None = None) -> None:
        if status not in {"delivered", "failed"}:
            raise ValueError("invalid reminder final status")
        with self._lock, self._connection:
            if status == "delivered":
                updated = self._connection.execute(
                    "UPDATE event_reminders SET status = 'delivered', delivered_at = ? "
                    "WHERE reminder_id = ? AND status = 'claimed'", (timestamp, reminder_id),
                ).rowcount
            else:
                updated = self._connection.execute(
                    "UPDATE event_reminders SET status = 'failed', failed_at = ?, failure_reason = ? "
                    "WHERE reminder_id = ? AND status = 'claimed'", (timestamp, failure_reason, reminder_id),
                ).rowcount
        if updated != 1:
            raise ValueError(f"reminder is not claimed: {reminder_id}")
        self._maybe_mirror(force=True)

    def reconcile_claimed_reminders(self) -> int:
        timestamp = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connection:
            rows = self._connection.execute(
                "SELECT reminder_id, delivery_action_id FROM event_reminders WHERE status = 'claimed'"
            ).fetchall()
            for row in rows:
                self._connection.execute(
                    "UPDATE event_reminders SET status = 'failed', failed_at = ?, failure_reason = ? "
                    "WHERE reminder_id = ? AND status = 'claimed'",
                    (timestamp, "unknown_delivery_after_restart", row["reminder_id"]),
                )
                if row["delivery_action_id"]:
                    self._connection.execute(
                        "UPDATE proactive_actions SET delivery_status = 'failed', suppression_reason = 'delivery_failed' "
                        "WHERE action_id = ?", (row["delivery_action_id"],),
                    )
        if rows:
            self._maybe_mirror(force=True)
        return len(rows)

    @staticmethod
    def _validate_alarm_label(label: str) -> str:
        if not isinstance(label, str) or any(ord(char) < 32 for char in label):
            raise ValueError("alarm label must be 1-120 characters without control characters")
        normalized = " ".join(label.strip().split())
        if not normalized or len(normalized) > 120:
            raise ValueError("alarm label must be 1-120 characters without control characters")
        return normalized

    @staticmethod
    def _validate_display_timezone(display_timezone: str) -> str:
        if not isinstance(display_timezone, str) or not display_timezone:
            raise ValueError("alarm display timezone is required")
        try:
            ZoneInfo(display_timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("alarm display timezone must be a valid IANA timezone") from exc
        return display_timezone

    def alarms(
        self, *, person_id: str = "primary_user", status: str | None = None, limit: int = 100,
    ) -> list[dict[str, Any]]:
        if person_id != "primary_user":
            raise ValueError("only primary_user alarms are supported")
        if status is not None and status not in {"pending", "claimed", "delivered", "failed", "cancelled"}:
            raise ValueError("alarm status is invalid")
        if not 1 <= limit <= 100:
            raise ValueError("alarm limit must be from 1 through 100")
        sql = (
            "SELECT alarm_id, person_id, label, scheduled_for, display_timezone, created_at, "
            "source_surface, source_request_id, status, claimed_at, delivered_at, failed_at, "
            "cancelled_at, cancelled_source_surface, cancelled_source_request_id, failure_reason "
            "FROM alarms WHERE person_id = ?"
        )
        parameters: list[Any] = [person_id]
        if status is not None:
            sql += " AND status = ?"
            parameters.append(status)
        sql += " ORDER BY scheduled_for ASC, rowid ASC LIMIT ?"
        parameters.append(limit)
        with self._lock:
            rows = self._connection.execute(sql, parameters).fetchall()
        return [dict(row) for row in rows]

    def alarm(self, alarm_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute("SELECT * FROM alarms WHERE alarm_id = ?", (alarm_id,)).fetchone()
        return dict(row) if row is not None else None

    def create_alarm(
        self, *, scheduled_for: datetime | str, display_timezone: str, source_surface: str,
        source_request_id: str, label: str = "Alarm", person_id: str = "primary_user",
        created_at: datetime | str | None = None,
    ) -> dict[str, Any]:
        if person_id != "primary_user":
            raise ValueError("only primary_user alarms are supported")
        if not source_surface or not source_request_id:
            raise ValueError("alarm provenance is required")
        with self._lock:
            existing = self._connection.execute(
                "SELECT * FROM alarms WHERE source_surface = ? AND source_request_id = ?",
                (source_surface, source_request_id),
            ).fetchone()
        if existing is not None:
            return dict(existing)
        normalized_label = self._validate_alarm_label(label)
        timezone_name = self._validate_display_timezone(display_timezone)
        scheduled = _parse_utc_time(_utc_iso(scheduled_for))
        created = _parse_utc_time(_utc_iso(created_at or datetime.now(timezone.utc)))
        if scheduled is None or created is None:
            raise ValueError("alarm timestamps must be timezone-aware")
        if scheduled <= created:
            raise ValueError("alarm must be scheduled in the future")
        if scheduled - created > timedelta(days=366):
            raise ValueError("alarm must be within 366 days")
        with self._lock, self._connection:
            pending_count = int(self._connection.execute(
                "SELECT COUNT(*) FROM alarms WHERE person_id = ? AND status = 'pending'", (person_id,),
            ).fetchone()[0])
            if pending_count >= 32:
                raise ValueError("the maximum of 32 pending alarms has been reached")
            alarm_id = str(uuid.uuid4())
            try:
                self._connection.execute(
                    "INSERT INTO alarms(alarm_id, person_id, label, scheduled_for, display_timezone, created_at, "
                    "source_surface, source_request_id, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')",
                    (
                        alarm_id, person_id, normalized_label, scheduled.isoformat(), timezone_name,
                        created.isoformat(), source_surface, source_request_id,
                    ),
                )
            except sqlite3.IntegrityError:
                existing = self._connection.execute(
                    "SELECT * FROM alarms WHERE source_surface = ? AND source_request_id = ?",
                    (source_surface, source_request_id),
                ).fetchone()
                if existing is None:
                    raise
                return dict(existing)
            row = self._connection.execute("SELECT * FROM alarms WHERE alarm_id = ?", (alarm_id,)).fetchone()
        self._maybe_mirror(force=True)
        return dict(row)

    def cancel_alarm(
        self, alarm_id: str, *, source_surface: str, source_request_id: str,
        cancelled_at: datetime | str | None = None,
    ) -> dict[str, Any]:
        if not alarm_id or not source_surface or not source_request_id:
            raise ValueError("alarm id and cancellation provenance are required")
        timestamp = _utc_iso(cancelled_at or datetime.now(timezone.utc))
        with self._lock, self._connection:
            row = self._connection.execute("SELECT * FROM alarms WHERE alarm_id = ?", (alarm_id,)).fetchone()
            if row is None:
                raise KeyError(f"alarm not found: {alarm_id}")
            if row["status"] == "cancelled":
                return dict(row)
            if row["status"] != "pending":
                raise ValueError(f"alarm cannot be cancelled from status {row['status']}")
            self._connection.execute(
                "UPDATE alarms SET status = 'cancelled', cancelled_at = ?, cancelled_source_surface = ?, "
                "cancelled_source_request_id = ? WHERE alarm_id = ? AND status = 'pending'",
                (timestamp, source_surface, source_request_id, alarm_id),
            )
            updated = self._connection.execute("SELECT * FROM alarms WHERE alarm_id = ?", (alarm_id,)).fetchone()
        self._maybe_mirror(force=True)
        return dict(updated)

    def claim_due_alarms(self, *, now: datetime | str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        if not 1 <= limit <= 32:
            raise ValueError("due alarm limit must be from 1 through 32")
        evaluated = _parse_utc_time(_utc_iso(now or datetime.now(timezone.utc)))
        if evaluated is None:
            raise ValueError("alarm evaluation time must be timezone-aware")
        claimed: list[dict[str, Any]] = []
        with self._lock, self._connection:
            rows = self._connection.execute(
                "SELECT * FROM alarms WHERE status = 'pending' AND scheduled_for <= ? "
                "ORDER BY scheduled_for ASC, rowid ASC LIMIT ?",
                (evaluated.isoformat(), limit),
            ).fetchall()
            for row in rows:
                updated = self._connection.execute(
                    "UPDATE alarms SET status = 'claimed', claimed_at = ? "
                    "WHERE alarm_id = ? AND status = 'pending'",
                    (evaluated.isoformat(), row["alarm_id"]),
                ).rowcount
                if updated == 1:
                    value = dict(row)
                    value["status"] = "claimed"
                    value["claimed_at"] = evaluated.isoformat()
                    claimed.append(value)
        if claimed:
            self._maybe_mirror(force=True)
        return claimed

    def finalize_alarm(
        self, alarm_id: str, *, status: str, timestamp: datetime | str | None = None,
        failure_reason: str | None = None,
    ) -> dict[str, Any]:
        if status not in {"delivered", "failed"}:
            raise ValueError("invalid alarm final status")
        finished_at = _utc_iso(timestamp or datetime.now(timezone.utc))
        with self._lock, self._connection:
            if status == "delivered":
                updated = self._connection.execute(
                    "UPDATE alarms SET status = 'delivered', delivered_at = ? "
                    "WHERE alarm_id = ? AND status = 'claimed'",
                    (finished_at, alarm_id),
                ).rowcount
            else:
                updated = self._connection.execute(
                    "UPDATE alarms SET status = 'failed', failed_at = ?, failure_reason = ? "
                    "WHERE alarm_id = ? AND status = 'claimed'",
                    (finished_at, failure_reason or "delivery_failed", alarm_id),
                ).rowcount
            row = self._connection.execute("SELECT * FROM alarms WHERE alarm_id = ?", (alarm_id,)).fetchone()
        if updated != 1 or row is None:
            raise ValueError(f"alarm is not claimed: {alarm_id}")
        self._maybe_mirror(force=True)
        return dict(row)

    def reconcile_claimed_alarms(self) -> int:
        timestamp = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connection:
            rows = self._connection.execute("SELECT alarm_id FROM alarms WHERE status = 'claimed'").fetchall()
            for row in rows:
                self._connection.execute(
                    "UPDATE alarms SET status = 'failed', failed_at = ?, failure_reason = ? "
                    "WHERE alarm_id = ? AND status = 'claimed'",
                    (timestamp, "unknown_delivery_after_restart", row["alarm_id"]),
                )
        if rows:
            self._maybe_mirror(force=True)
        return len(rows)

    def latest_weather_snapshot(self, location_label: str = "home") -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM weather_snapshots WHERE location_label = ? ORDER BY fetched_at DESC LIMIT 1",
                (location_label,),
            ).fetchone()
        if row is None:
            return None
        value = dict(row)
        for key in ("current_json", "hourly_json", "alerts_json", "source_metadata_json"):
            decoded_key = key[:-5]
            value[decoded_key] = json.loads(value.pop(key) or ("[]" if decoded_key in {"hourly", "alerts"} else "{}"))
        return value

    def weather_status(self, location_label: str = "home", *, now: datetime | None = None) -> dict[str, Any]:
        snapshot = self.latest_weather_snapshot(location_label)
        if snapshot is None:
            return {"status": "unavailable", "snapshot": None, "age_seconds": None}
        evaluated = now or datetime.now(timezone.utc)
        fetched = _parse_utc_time(snapshot.get("fetched_at"))
        fresh_until = _parse_utc_time(snapshot.get("fresh_until"))
        age = max(0.0, (evaluated.astimezone(timezone.utc) - fetched).total_seconds()) if fetched else None
        status = "fresh" if fresh_until and evaluated.astimezone(timezone.utc) <= fresh_until else "stale"
        return {"status": status, "snapshot": snapshot, "age_seconds": age}

    def persist_weather_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        required = (
            "provider", "location_label", "latitude", "longitude", "timezone", "fetched_at",
            "fresh_until", "source_fingerprint", "current", "hourly", "alerts", "source_metadata",
        )
        if any(key not in snapshot for key in required):
            raise ValueError("weather snapshot is incomplete")
        if snapshot["provider"] != "nws":
            raise ValueError("unsupported weather provider")
        with self._lock, self._connection:
            existing = self._connection.execute(
                "SELECT snapshot_id FROM weather_snapshots WHERE location_label = ? AND source_fingerprint = ? LIMIT 1",
                (snapshot["location_label"], snapshot["source_fingerprint"]),
            ).fetchone()
            if existing is not None:
                self._connection.execute(
                    "UPDATE weather_snapshots SET fetched_at = ?, source_updated_at = ?, fresh_until = ?, "
                    "current_json = ?, hourly_json = ?, alerts_json = ?, source_metadata_json = ? WHERE snapshot_id = ?",
                    (
                        snapshot["fetched_at"], snapshot.get("source_updated_at"), snapshot["fresh_until"],
                        json.dumps(snapshot["current"], sort_keys=True), json.dumps(snapshot["hourly"], sort_keys=True),
                        json.dumps(snapshot["alerts"], sort_keys=True), json.dumps(snapshot["source_metadata"], sort_keys=True),
                        existing[0],
                    ),
                )
                refreshed_id = existing[0]
            else:
                refreshed_id = None
            if refreshed_id is not None:
                snapshot_id = refreshed_id
            else:
                snapshot_id = str(snapshot.get("snapshot_id") or uuid.uuid4())
                self._connection.execute(
                    "INSERT INTO weather_snapshots(snapshot_id, provider, location_label, latitude, longitude, timezone, fetched_at, source_updated_at, fresh_until, source_fingerprint, current_json, hourly_json, alerts_json, source_metadata_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        snapshot_id, snapshot["provider"], snapshot["location_label"], float(snapshot["latitude"]),
                        float(snapshot["longitude"]), snapshot["timezone"], snapshot["fetched_at"], snapshot.get("source_updated_at"),
                        snapshot["fresh_until"], snapshot["source_fingerprint"], json.dumps(snapshot["current"], sort_keys=True),
                        json.dumps(snapshot["hourly"], sort_keys=True), json.dumps(snapshot["alerts"], sort_keys=True),
                        json.dumps(snapshot["source_metadata"], sort_keys=True),
                    ),
                )
        self._maybe_mirror(force=True)
        return {"written": refreshed_id is None, "skipped": refreshed_id is not None, "refreshed": True, "snapshot_id": snapshot_id, "source_fingerprint": snapshot["source_fingerprint"]}

    def preference_events(self, person_id: str = "primary_user", *, limit: int = 100) -> list[dict[str, Any]]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        with self._lock:
            rows = self._connection.execute(
                "SELECT preference_event_id, person_id, preference_key, operation, value_json, created_at, "
                "source_surface, source_request_id, supersedes_event_id FROM preference_events "
                "WHERE person_id = ? ORDER BY created_at DESC, rowid DESC LIMIT ?",
                (person_id, limit),
            ).fetchall()
        values = []
        for row in rows:
            value = dict(row)
            value["value"] = json.loads(value.pop("value_json"))
            values.append(value)
        return values

    def preference_value(
        self, person_id: str = "primary_user", preference_key: str = PREFERENCE_KEY
    ) -> str:
        if preference_key != PREFERENCE_KEY:
            raise ValueError(f"unsupported preference key: {preference_key}")
        with self._lock:
            row = self._connection.execute(
                "SELECT operation, value_json FROM preference_events "
                "WHERE person_id = ? AND preference_key = ? ORDER BY created_at DESC, rowid DESC LIMIT 1",
                (person_id, preference_key),
            ).fetchone()
        if row is None or row[0] == "clear":
            return "default"
        value = json.loads(row[1])
        if value not in PREFERENCE_VALUES:
            return "default"
        return str(value)

    def _record_preference_event_locked(
        self, *, person_id: str, operation: str, value: str | None,
        source_surface: str, source_request_id: str, created_at: str,
    ) -> dict[str, Any]:
        if not person_id or operation not in {"set", "clear"}:
            raise ValueError("preference person_id and operation are invalid")
        if operation == "set" and value not in PREFERENCE_VALUES:
            raise ValueError("preference value is invalid")
        if not source_surface or not source_request_id:
            raise ValueError("preference provenance is required")
        existing = self._connection.execute(
            "SELECT preference_event_id, person_id, preference_key, operation, value_json, created_at, "
            "source_surface, source_request_id, supersedes_event_id FROM preference_events "
            "WHERE source_surface = ? AND source_request_id = ?",
            (source_surface, source_request_id),
        ).fetchone()
        if existing is not None:
            result = dict(existing)
            result["value"] = json.loads(result.pop("value_json"))
            return result
        previous = self._connection.execute(
            "SELECT preference_event_id FROM preference_events WHERE person_id = ? AND preference_key = ? "
            "ORDER BY created_at DESC, rowid DESC LIMIT 1",
            (person_id, PREFERENCE_KEY),
        ).fetchone()
        event_id = str(uuid.uuid4())
        self._connection.execute(
            "INSERT INTO preference_events(preference_event_id, person_id, preference_key, operation, value_json, "
            "created_at, source_surface, source_request_id, supersedes_event_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (event_id, person_id, PREFERENCE_KEY, operation, json.dumps(value), created_at,
             source_surface, source_request_id, previous[0] if previous else None),
        )
        return {
            "preference_event_id": event_id,
            "person_id": person_id,
            "preference_key": PREFERENCE_KEY,
            "operation": operation,
            "value": value,
            "created_at": created_at,
            "source_surface": source_surface,
            "source_request_id": source_request_id,
            "supersedes_event_id": previous[0] if previous else None,
        }

    def record_preference(
        self, *, person_id: str = "primary_user", operation: str, value: str | None = None,
        source_surface: str, source_request_id: str, created_at: datetime | str | None = None,
    ) -> dict[str, Any]:
        timestamp = _utc_iso(created_at or datetime.now(timezone.utc))
        with self._lock, self._connection:
            result = self._record_preference_event_locked(
                person_id=person_id, operation=operation, value=value,
                source_surface=source_surface, source_request_id=source_request_id,
                created_at=timestamp,
            )
        self._maybe_mirror(force=True)
        return result

    def recent_delivered_proactive_action(
        self, person_id: str = "primary_user", *, now: datetime | None = None, window_seconds: float = 600.0,
    ) -> dict[str, Any] | None:
        if window_seconds <= 0:
            raise ValueError("feedback window must be positive")
        cutoff = _parse_utc_time((now or datetime.now(timezone.utc)).isoformat())
        assert cutoff is not None
        candidates = []
        for action in self.proactive_actions(limit=1000):
            if action.get("person_id") != person_id or action.get("delivery_status") != "delivered":
                continue
            delivered_at = _parse_utc_time(action.get("delivered_at"))
            if delivered_at is not None and timedelta(seconds=0) <= cutoff - delivered_at <= timedelta(seconds=window_seconds):
                candidates.append(action)
        return candidates[0] if len(candidates) == 1 else None

    def proactive_feedback(self, *, limit: int = 100) -> list[dict[str, Any]]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        with self._lock:
            rows = self._connection.execute(
                "SELECT feedback_id, action_id, person_id, feedback_type, created_at, source_surface, "
                "source_request_id, resulting_preference_event_id FROM proactive_feedback "
                "ORDER BY created_at DESC, rowid DESC LIMIT ?", (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def record_proactive_feedback(
        self, *, action_id: str, person_id: str = "primary_user", feedback_type: str,
        source_surface: str, source_request_id: str, created_at: datetime | str | None = None,
    ) -> dict[str, Any]:
        if feedback_type not in FEEDBACK_TYPES:
            raise ValueError("feedback type is invalid")
        if not source_surface or not source_request_id:
            raise ValueError("feedback provenance is required")
        timestamp = _utc_iso(created_at or datetime.now(timezone.utc))
        with self._lock, self._connection:
            existing = self._connection.execute(
                "SELECT feedback_id, action_id, person_id, feedback_type, created_at, source_surface, "
                "source_request_id, resulting_preference_event_id FROM proactive_feedback WHERE source_request_id = ?",
                (source_request_id,),
            ).fetchone()
            if existing is not None:
                return dict(existing)
            action = self._connection.execute(
                "SELECT event_type, person_id, delivery_status FROM proactive_actions WHERE action_id = ?", (action_id,)
            ).fetchone()
            if action is None:
                raise ValueError(f"proactive action not found: {action_id}")
            if action[1] != person_id:
                raise ValueError("feedback person does not match proactive action")
            if action[0] != "person.identified" or person_id != "primary_user":
                raise ValueError("feedback action is outside the supported acknowledgement scope")
            if action[2] != "delivered":
                raise ValueError("feedback action was not delivered")
            preference_event_id = None
            if feedback_type == "do_not_repeat":
                preference = self._record_preference_event_locked(
                    person_id=person_id, operation="set", value="suppress",
                    source_surface=source_surface, source_request_id=f"{source_request_id}:preference",
                    created_at=timestamp,
                )
                preference_event_id = preference["preference_event_id"]
            feedback_id = str(uuid.uuid4())
            self._connection.execute(
                "INSERT INTO proactive_feedback(feedback_id, action_id, person_id, feedback_type, created_at, "
                "source_surface, source_request_id, resulting_preference_event_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (feedback_id, action_id, person_id, feedback_type, timestamp, source_surface, source_request_id, preference_event_id),
            )
            result = {
                "feedback_id": feedback_id, "action_id": action_id, "person_id": person_id,
                "feedback_type": feedback_type, "created_at": timestamp, "source_surface": source_surface,
                "source_request_id": source_request_id, "resulting_preference_event_id": preference_event_id,
            }
        self._maybe_mirror(force=True)
        return result

    def routine_source(self, window_start: str, window_end: str, *, room_id: str = "office") -> dict[str, list[dict[str, Any]]]:
        """Return bounded metadata-only source rows for routine derivation."""

        with self._lock:
            sessions = self._connection.execute(
                "SELECT session_id, room_id, started_at, ended_at, status, start_reason, end_reason, "
                "recovered_after_restart, end_time_uncertain FROM presence_sessions "
                "WHERE room_id = ? AND ((started_at BETWEEN ? AND ?) OR (ended_at BETWEEN ? AND ?) "
                "OR (started_at <= ? AND (ended_at IS NULL OR ended_at >= ?))) "
                "ORDER BY started_at, session_id",
                (room_id, window_start, window_end, window_start, window_end, window_start, window_start),
            ).fetchall()
            events = self._connection.execute(
                "SELECT event_id, event_type, occurred_at, room_id, session_id, source, confidence, payload_json, schema_version "
                "FROM events WHERE room_id = ? AND occurred_at BETWEEN ? AND ? ORDER BY occurred_at, event_id",
                (room_id, window_start, window_end),
            ).fetchall()
        return {
            "sessions": [dict(row) for row in sessions],
            "events": [
                {**dict(row), "payload": json.loads(row["payload_json"] or "{}")}
                for row in events
            ],
        }

    def persist_routine_snapshots(self, snapshots: list[dict[str, Any]]) -> dict[str, Any]:
        """Append a derived snapshot batch unless the exact source is already present."""

        if not snapshots:
            return {"written": 0, "skipped": True, "source_fingerprint": None}
        fingerprints = {str(item["source_fingerprint"]) for item in snapshots}
        algorithms = {str(item["algorithm_version"]) for item in snapshots}
        if len(fingerprints) != 1 or len(algorithms) != 1:
            raise ValueError("routine snapshot batch must have one source fingerprint and algorithm version")
        source_fingerprint = next(iter(fingerprints))
        algorithm_version = next(iter(algorithms))
        routine_keys = {str(item["routine_key"]) for item in snapshots}
        with self._lock:
            existing = {
                row[0]
                for row in self._connection.execute(
                    "SELECT routine_key FROM routine_snapshots WHERE source_fingerprint = ? AND algorithm_version = ?",
                    (source_fingerprint, algorithm_version),
                )
            }
            pending = [item for item in snapshots if item["routine_key"] not in existing]
            if not pending:
                return {
                    "written": 0,
                    "skipped": True,
                    "source_fingerprint": source_fingerprint,
                    "routine_keys": sorted(routine_keys),
                }
            with self._connection:
                self._connection.executemany(
                    "INSERT INTO routine_snapshots("
                    "snapshot_id, routine_key, routine_type, scope, room_id, person_id, timezone, algorithm_version, "
                    "window_start, window_end, source_as_of, source_fingerprint, generated_at, sample_count, "
                    "distinct_date_count, maturity_status, statistics_json, exclusions_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        (
                            str(item["snapshot_id"]), item["routine_key"], item["routine_type"], item["scope"],
                            item["room_id"], item.get("person_id"), item["timezone"], item["algorithm_version"],
                            item["window_start"], item["window_end"], item["source_as_of"], item["source_fingerprint"],
                            item["generated_at"], int(item["sample_count"]), int(item["distinct_date_count"]),
                            item["maturity_status"], json.dumps(item["statistics"], sort_keys=True),
                            json.dumps(item["exclusions"], sort_keys=True),
                        )
                        for item in pending
                    ],
                )
        self._maybe_mirror(force=True)
        return {
            "written": len(pending),
            "skipped": False,
            "source_fingerprint": source_fingerprint,
            "routine_keys": sorted(routine_keys),
        }

    def routine_snapshots(self, *, latest_only: bool = True, limit: int = 200) -> list[dict[str, Any]]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        with self._lock:
            if latest_only:
                rows = self._connection.execute(
                    "SELECT r.* FROM routine_snapshots r JOIN ("
                    "SELECT routine_key, MAX(generated_at) AS generated_at FROM routine_snapshots "
                    "GROUP BY routine_key) latest ON latest.routine_key = r.routine_key "
                    "AND latest.generated_at = r.generated_at ORDER BY r.routine_key LIMIT ?",
                    (limit,),
                ).fetchall()
            else:
                rows = self._connection.execute(
                    "SELECT * FROM routine_snapshots ORDER BY generated_at DESC, routine_key LIMIT ?",
                    (limit,),
                ).fetchall()
        values = []
        for row in rows:
            value = dict(row)
            value["statistics"] = json.loads(value.pop("statistics_json") or "{}")
            value["exclusions"] = json.loads(value.pop("exclusions_json") or "{}")
            values.append(value)
        return values

    def claim_proactive_action(
        self, *, action_id: str, source_event_id: str, candidate_key: str, event_type: str,
        person_id: str | None, session_id: int | None, event_timestamp: str, evaluated_at: str,
        eligibility_result: str, suppression_reason: str | None,
    ) -> bool:
        """Atomically reserve one event for proactive evaluation.

        Reserving before Luna/TTS prevents a crash after delivery from causing a
        duplicate utterance after restart.  The reservation itself is a durable
        decision record and is finalized by ``update_proactive_action``.
        """

        if eligibility_result not in {"eligible", "suppressed"}:
            raise ValueError("invalid proactive eligibility result")
        with self._lock, self._connection:
            try:
                self._connection.execute(
                    "INSERT INTO proactive_actions("
                    "action_id, source_event_id, candidate_key, event_type, person_id, session_id, "
                    "event_timestamp, evaluated_at, eligibility_result, suppression_reason, delivery_status"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        action_id, source_event_id, candidate_key, event_type, person_id, session_id,
                        event_timestamp, evaluated_at, eligibility_result, suppression_reason,
                        "suppressed" if eligibility_result == "suppressed" else "not_attempted",
                    ),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def update_proactive_action(
        self, action_id: str, *, judge_invoked: bool | None = None, judge_model: str | None = None,
        judge_effort: str | None = None, judge_decision: str | None = None,
        cited_fact_ids: list[str] | None = None, utterance: str | None = None,
        delivery_status: str | None = None, delivered_at: str | None = None,
        eligibility_result: str | None = None, suppression_reason: str | None = None,
    ) -> None:
        updates: list[str] = []
        values: list[Any] = []
        fields = {
            "judge_invoked": (int(bool(judge_invoked)) if judge_invoked is not None else None),
            "judge_model": judge_model,
            "judge_effort": judge_effort,
            "judge_decision": judge_decision,
            "cited_fact_ids_json": json.dumps(cited_fact_ids, sort_keys=True) if cited_fact_ids is not None else None,
            "utterance": utterance,
            "delivery_status": delivery_status,
            "delivered_at": delivered_at,
            "eligibility_result": eligibility_result,
            "suppression_reason": suppression_reason,
        }
        for column, value in fields.items():
            if value is not None:
                updates.append(f"{column} = ?")
                values.append(value)
        if not updates:
            return
        values.append(action_id)
        with self._lock, self._connection:
            updated = self._connection.execute(
                f"UPDATE proactive_actions SET {', '.join(updates)} WHERE action_id = ?", values
            ).rowcount
        if updated != 1:
            raise ValueError(f"proactive action not found: {action_id}")
        self._maybe_mirror(force=True)
