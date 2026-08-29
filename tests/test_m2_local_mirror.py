import os
import sqlite3
import subprocess
import sys
import tempfile
import json
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread
from unittest.mock import patch

from perception.presence_store import PresenceStore
from perception.storage_mirror import validate_sqlite_file
from tools.sentry_state_api import _Handler
from http.server import ThreadingHTTPServer


def observation(state: str, timestamp: str, transition: str | None = None, camera_state: str = "online") -> dict:
    return {
        "room_state": state,
        "captured_at": timestamp,
        "camera_state": camera_state,
        "room_state_transition": transition,
        "frame_sequence": 1,
        "people": [{"visible": True}] if state == "occupied" else [],
        "detector_evidence": state == "occupied",
        "max_person_confidence": 0.8 if state == "occupied" else None,
    }


class LocalMirrorTests(unittest.TestCase):
    def test_existing_schema_v1_migrates_idempotently_to_v2(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.db"
            connection = sqlite3.connect(path)
            connection.executescript(
                """
                CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
                INSERT INTO schema_migrations VALUES (1, '2026-08-28T12:00:00+00:00');
                CREATE TABLE room_state(room_id TEXT PRIMARY KEY, state TEXT NOT NULL,
                    updated_at TEXT NOT NULL, camera_state TEXT, person_count INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE presence_sessions(session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id TEXT NOT NULL, started_at TEXT NOT NULL, ended_at TEXT,
                    status TEXT NOT NULL, FOREIGN KEY(room_id) REFERENCES room_state(room_id));
                CREATE TABLE events(event_id TEXT PRIMARY KEY, event_type TEXT NOT NULL,
                    occurred_at TEXT NOT NULL, room_id TEXT NOT NULL, session_id INTEGER,
                    source TEXT NOT NULL, confidence REAL, payload_json TEXT NOT NULL,
                    schema_version INTEGER NOT NULL);
                """
            )
            connection.close()
            with PresenceStore(path) as store:
                self.assertEqual(store.health()["schema_version"], 3)
                columns = {row[1] for row in store._connection.execute("PRAGMA table_info(presence_sessions)")}
                self.assertTrue({"start_reason", "end_reason", "recovered_after_restart", "end_time_uncertain"} <= columns)
            with PresenceStore(path) as reopened:
                self.assertEqual(reopened.health()["schema_version"], 3)

    def test_snapshot_is_integrity_checked_and_health_reports_mirror(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local = root / "local" / "sentry.db"
            atlas = root / "atlas" / "sentry.db"
            with PresenceStore(local, atlas_mirror_path=atlas) as store:
                store.start("2026-08-28T12:00:00+00:00")
                store.record_observation(observation("empty", "2026-08-28T12:00:01+00:00"))
                store.stop("2026-08-28T12:00:02+00:00")
                health = store.health()
                self.assertEqual(health["db_available"], True)
                self.assertEqual(health["schema_version"], 3)
                self.assertEqual(health["atlas_mirror"]["status"], "ok")
                self.assertIsNotNone(health["atlas_mirror"]["snapshot_sha256"])
            self.assertTrue(atlas.is_file())
            validate_sqlite_file(atlas)

    def test_failed_atlas_publication_preserves_previous_snapshot_and_local_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local = root / "local" / "sentry.db"
            atlas = root / "atlas" / "sentry.db"
            with PresenceStore(local, atlas_mirror_path=atlas) as store:
                store.start("2026-08-28T12:00:00+00:00")
                store.record_observation(observation("empty", "2026-08-28T12:00:01+00:00"))
                original = atlas.read_bytes()
                with patch("perception.storage_mirror.shutil.copyfile", side_effect=OSError("Atlas unavailable")):
                    store.record_observation(
                        observation("occupied", "2026-08-28T12:00:03+00:00", "empty->occupied")
                    )
                self.assertEqual(store.current_state().state, "occupied")
                self.assertEqual(atlas.read_bytes(), original)
                self.assertEqual(store.health()["atlas_mirror"]["status"], "degraded")
                store.stop("2026-08-28T12:00:04+00:00")
            self.assertNotEqual(atlas.read_bytes(), original)
            validate_sqlite_file(atlas)

    def test_missing_local_database_restores_from_atlas(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local = root / "local" / "sentry.db"
            atlas = root / "atlas" / "sentry.db"
            with PresenceStore(local, atlas_mirror_path=atlas) as store:
                store.start("2026-08-28T12:00:00+00:00")
                store.record_observation(observation("empty", "2026-08-28T12:00:01+00:00"))
                store.record_observation(
                    observation("occupied", "2026-08-28T12:00:02+00:00", "empty->occupied")
                )
                store.stop("2026-08-28T12:00:03+00:00")
            local.unlink()
            with PresenceStore(local, atlas_mirror_path=atlas) as restored:
                self.assertTrue(restored.recovery_info["recovered"])
                self.assertEqual(restored.current_state().state, "occupied")
                self.assertEqual(restored.sessions()[0]["status"], "open")

    def test_corrupt_local_database_is_quarantined_before_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local = root / "local" / "sentry.db"
            atlas = root / "atlas" / "sentry.db"
            with PresenceStore(local, atlas_mirror_path=atlas) as store:
                store.start("2026-08-28T12:00:00+00:00")
                store.record_observation(observation("empty", "2026-08-28T12:00:01+00:00"))
                store.stop("2026-08-28T12:00:02+00:00")
            local.write_bytes(b"not sqlite")
            with PresenceStore(local, atlas_mirror_path=atlas) as restored:
                self.assertEqual(restored.recovery_info["reason"], "corrupt_local_database")
                self.assertEqual(restored.current_state().state, "empty")
            quarantined = list(local.parent.glob("sentry.db.corrupt-*"))
            self.assertEqual(len(quarantined), 1)
            self.assertEqual(quarantined[0].read_bytes(), b"not sqlite")

    def test_occupied_restart_continues_same_session(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sentry.db"
            with PresenceStore(path) as first:
                first.record_observation(observation("empty", "2026-08-28T12:00:00+00:00"))
                first.record_observation(
                    observation("occupied", "2026-08-28T12:00:02+00:00", "empty->occupied")
                )
                session_id = first.sessions()[0]["session_id"]
            with PresenceStore(path) as second:
                second.start("2026-08-28T12:01:00+00:00")
                second.reconcile_after_restart(observation("occupied", "2026-08-28T12:01:01+00:00"))
                self.assertEqual(second.sessions()[0]["session_id"], session_id)
                self.assertEqual(second.sessions()[0]["status"], "open")
                self.assertEqual(
                    len([e for e in second.events() if e["event_type"] == "presence.session_started"]), 1
                )
                self.assertEqual(
                    len([e for e in second.events() if e["event_type"] == "presence.restart_reconciled"]), 1
                )

    def test_occupied_empty_restart_closes_with_uncertain_reconciliation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sentry.db"
            with PresenceStore(path) as first:
                first.record_observation(observation("empty", "2026-08-28T12:00:00+00:00"))
                first.record_observation(
                    observation("occupied", "2026-08-28T12:00:02+00:00", "empty->occupied")
                )
            with PresenceStore(path) as second:
                second.start("2026-08-28T12:01:00+00:00")
                second.reconcile_after_restart(observation("empty", "2026-08-28T12:01:05+00:00"))
                session = second.sessions()[0]
                self.assertEqual(session["status"], "completed")
                self.assertEqual(session["end_reason"], "restart_reconciled")
                self.assertEqual(session["recovered_after_restart"], 1)
                self.assertEqual(session["end_time_uncertain"], 1)
                self.assertIn("presence.session_reconciled", [e["event_type"] for e in second.events()])

    def test_degraded_restart_leaves_open_session(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sentry.db"
            with PresenceStore(path) as first:
                first.record_observation(observation("empty", "2026-08-28T12:00:00+00:00"))
                first.record_observation(
                    observation("occupied", "2026-08-28T12:00:02+00:00", "empty->occupied")
                )
            with PresenceStore(path) as second:
                second.reconcile_after_restart(
                    observation("offline", "2026-08-28T12:01:05+00:00", camera_state="offline")
                )
                self.assertEqual(second.current_state().state, "offline")
                self.assertEqual(second.sessions()[0]["status"], "open")
                self.assertNotIn("presence.session_ended", [e["event_type"] for e in second.events()])

    def test_localhost_api_reports_live_health_and_persisted_history(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sentry.db"
            with PresenceStore(path) as store:
                store.record_observation(observation("empty", "2026-08-28T12:00:00+00:00"))
                store.record_observation(
                    observation("occupied", "2026-08-28T12:00:02+00:00", "empty->occupied")
                )
                server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
                server.store = store
                thread = Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                    connection.request("GET", "/health")
                    response = connection.getresponse()
                    health = json.loads(response.read())
                    self.assertEqual(response.status, 200)
                    self.assertTrue(health["ok"])
                    self.assertTrue(health["db_available"])
                    self.assertEqual(health["schema_version"], 3)
                    self.assertEqual(health["atlas_mirror"]["status"], "disabled")
                    connection.request("GET", "/v1/rooms/office/sessions")
                    sessions = json.loads(connection.getresponse().read())
                    self.assertEqual(sessions["sessions"][0]["status"], "open")
                    connection.close()
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=5)

    def test_localhost_reads_remain_safe_during_local_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sentry.db"
            with PresenceStore(path) as store:
                store.record_observation(observation("empty", "2026-08-28T12:00:00+00:00"))
                store.record_observation(
                    observation("occupied", "2026-08-28T12:00:01+00:00", "empty->occupied")
                )
                server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
                server.store = store
                server_thread = Thread(target=server.serve_forever, daemon=True)
                server_thread.start()
                errors: list[Exception] = []

                def write_observations() -> None:
                    try:
                        for index in range(20):
                            store.record_observation(
                                observation("occupied", f"2026-08-28T12:00:{2 + index:02d}+00:00")
                            )
                    except Exception as exc:  # pragma: no cover - assertion below reports any race
                        errors.append(exc)

                writer = Thread(target=write_observations)
                writer.start()
                try:
                    for _ in range(20):
                        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                        connection.request("GET", "/v1/rooms/office/state")
                        response = connection.getresponse()
                        self.assertEqual(response.status, 200)
                        json.loads(response.read())
                        connection.close()
                    writer.join(timeout=10)
                    self.assertFalse(writer.is_alive())
                    self.assertEqual(errors, [])
                finally:
                    server.shutdown()
                    server.server_close()
                    server_thread.join(timeout=5)

    def test_process_level_clean_abrupt_and_restore_scenarios(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "sentry.db"
            atlas = root / "atlas" / "sentry.db"
            script = r'''
import os
import sys
from perception.presence_store import PresenceStore

path, atlas, mode = sys.argv[1:]


def obs(state, at, transition=None, camera_state="online"):
    return {
        "room_state": state,
        "captured_at": at,
        "camera_state": camera_state,
        "room_state_transition": transition,
        "frame_sequence": 1,
        "people": [{"visible": True}] if state == "occupied" else [],
        "detector_evidence": state == "occupied",
        "max_person_confidence": 0.8 if state == "occupied" else None,
    }


if mode == "seed-clean":
    with PresenceStore(path, atlas_mirror_path=atlas) as store:
        store.start("2026-08-28T12:00:00+00:00")
        store.record_observation(obs("empty", "2026-08-28T12:00:01+00:00"))
        store.record_observation(obs("occupied", "2026-08-28T12:00:02+00:00", "empty->occupied"))
        store.stop("2026-08-28T12:00:03+00:00")
elif mode == "reconcile-clean":
    with PresenceStore(path, atlas_mirror_path=atlas) as store:
        store.start("2026-08-28T12:01:00+00:00")
        store.reconcile_after_restart(obs("occupied", "2026-08-28T12:01:01+00:00"))
        session_id = store.sessions()[0]["session_id"]
        assert len(store.sessions()) == 1
        assert store.sessions()[0]["status"] == "open"
        store.reconcile_after_restart(obs("empty", "2026-08-28T12:01:05+00:00"))
        assert store.sessions()[0]["session_id"] == session_id
        assert store.sessions()[0]["end_time_uncertain"] == 1
elif mode == "reconcile-abrupt":
    with PresenceStore(path, atlas_mirror_path=atlas) as store:
        store.start("2026-08-28T12:03:00+00:00")
        assert not [event for event in store.events() if event["event_type"] == "system.stopped"]
        store.reconcile_after_restart(obs("empty", "2026-08-28T12:03:05+00:00"))
        assert store.sessions()[0]["end_time_uncertain"] == 1
elif mode == "seed-abrupt":
    store = PresenceStore(path, atlas_mirror_path=atlas)
    store.start("2026-08-28T12:02:00+00:00")
    store.record_observation(obs("empty", "2026-08-28T12:02:01+00:00"))
    store.record_observation(obs("occupied", "2026-08-28T12:02:02+00:00", "empty->occupied"))
    os._exit(0)
elif mode == "restore":
    with PresenceStore(path, atlas_mirror_path=atlas) as store:
        assert store.recovery_info["recovered"]
        assert store.current_state().state == "occupied"
'''
            def run(mode: str) -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    [sys.executable, "-c", script, str(path), str(atlas), mode],
                    cwd=Path(__file__).resolve().parents[1],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )

            result = run("seed-clean")
            self.assertEqual(result.returncode, 0, result.stderr)
            path.unlink()
            result = run("restore")
            self.assertEqual(result.returncode, 0, result.stderr)
            result = run("reconcile-clean")
            self.assertEqual(result.returncode, 0, result.stderr)

            path.unlink()
            atlas.unlink()
            manifest = atlas.with_name(atlas.name + ".manifest.json")
            manifest.unlink(missing_ok=True)
            result = run("seed-abrupt")
            self.assertEqual(result.returncode, 0, result.stderr)
            result = run("reconcile-abrupt")
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
