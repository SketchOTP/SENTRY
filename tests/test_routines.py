import json
import tempfile
import unittest
from datetime import datetime, timezone
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from perception.presence_store import PresenceStore
from perception.routines import (
    ROUTINE_TYPES,
    RoutineConfig,
    build_snapshots,
    circular_statistics,
    robust_statistics,
)
from tools.sentry_state_api import _Handler


AS_OF = datetime(2026, 8, 30, 12, tzinfo=timezone.utc)


def session(number, started, ended=None, *, status="completed", end_reason="observed", uncertain=0, recovered=0):
    return {
        "session_id": number,
        "room_id": "office",
        "started_at": started,
        "ended_at": ended,
        "status": status,
        "start_reason": "observed",
        "end_reason": end_reason,
        "recovered_after_restart": recovered,
        "end_time_uncertain": uncertain,
    }


def event(event_type, timestamp, session_id=None, payload=None, event_id=None):
    return {
        "event_id": event_id or f"event-{timestamp}-{event_type}",
        "event_type": event_type,
        "occurred_at": timestamp,
        "room_id": "office",
        "session_id": session_id,
        "source": "test",
        "confidence": None,
        "payload": payload or {},
        "schema_version": 5,
    }


def source_with_days(days=8, *, interrupted=False):
    sessions = []
    events = []
    for index in range(days):
        day = f"2026-08-{10 + index:02d}"
        start = f"{day}T09:00:00+00:00"
        end = f"{day}T17:00:00+00:00"
        sessions.append(session(index + 1, start, end))
        events.append(event("person.identified", f"{day}T09:01:00+00:00", index + 1, {"person_id": "primary_user"}))
    if interrupted and len(sessions) >= 2:
        events.append(event("room.camera_degraded", "2026-08-10T18:00:00+00:00"))
    return {"sessions": sessions, "events": events}


class RoutineStatisticsTests(unittest.TestCase):
    def test_no_history_is_insufficient(self):
        snapshots = build_snapshots({"sessions": [], "events": []}, as_of=AS_OF, config=RoutineConfig())
        self.assertEqual(len(snapshots), len(ROUTINE_TYPES) * 10)
        self.assertTrue(all(item["maturity_status"] == "insufficient" for item in snapshots))

    def test_one_or_two_observations_are_insufficient(self):
        source = {"sessions": [session(1, "2026-08-29T09:00:00+00:00", "2026-08-29T10:00:00+00:00")], "events": []}
        snapshots = build_snapshots(source, as_of=AS_OF, config=RoutineConfig())
        self.assertEqual(next(item for item in snapshots if item["routine_key"] == "office_session_start_time:all_days")["sample_count"], 1)
        self.assertEqual(next(item for item in snapshots if item["routine_key"] == "office_session_start_time:all_days")["maturity_status"], "insufficient")

    def test_enough_samples_on_one_date_remain_insufficient(self):
        sessions = [session(i, f"2026-08-29T09:{i:02d}:00+00:00", f"2026-08-29T10:{i:02d}:00+00:00") for i in range(8)]
        item = next(item for item in build_snapshots({"sessions": sessions, "events": []}, as_of=AS_OF, config=RoutineConfig()) if item["routine_key"] == "office_session_duration:all_days")
        self.assertEqual(item["sample_count"], 8)
        self.assertEqual(item["distinct_date_count"], 1)
        self.assertEqual(item["maturity_status"], "insufficient")

    def test_tight_clock_pattern_is_stable(self):
        item = next(item for item in build_snapshots(source_with_days(), as_of=AS_OF, config=RoutineConfig()) if item["routine_key"] == "office_session_start_time:all_days")
        self.assertEqual(item["maturity_status"], "stable")
        self.assertEqual(item["statistics"]["circular_center_local_time"], "05:00:00")
        self.assertGreaterEqual(item["statistics"]["mean_resultant_length"], 0.80)

    def test_widely_dispersed_clock_pattern_is_not_stable(self):
        sessions = [session(i, f"2026-08-{10 + i:02d}T{(i * 3) % 24:02d}:00:00+00:00", f"2026-08-{10 + i:02d}T{((i * 3) % 24 + 1) % 24:02d}:00:00+00:00") for i in range(8)]
        item = next(item for item in build_snapshots({"sessions": sessions, "events": []}, as_of=AS_OF, config=RoutineConfig()) if item["routine_key"] == "office_session_start_time:all_days")
        self.assertEqual(item["maturity_status"], "observed")

    def test_midnight_clock_wrap_uses_circular_center(self):
        stats = circular_statistics([23 * 3600 + 55 * 60, 5 * 60, 10 * 60] * 3)
        self.assertIn(stats["circular_center_local_time"], {"00:03:20", "00:03:19"})
        self.assertGreater(stats["mean_resultant_length"], 0.95)

    def test_duration_statistics_are_robust_and_keep_outlier(self):
        values = [3600.0] * 7 + [86400.0]
        stats = robust_statistics(values)
        self.assertEqual(stats["median"], 3600.0)
        self.assertEqual(stats["maximum"], 86400.0)
        self.assertEqual(stats["mad"], 0.0)

    def test_uncertain_and_restart_reconciled_ends_are_excluded(self):
        source = {"sessions": [session(1, "2026-08-20T09:00:00+00:00", "2026-08-20T10:00:00+00:00", end_reason="restart_reconciled", uncertain=1, recovered=1)], "events": []}
        item = next(item for item in build_snapshots(source, as_of=AS_OF, config=RoutineConfig()) if item["routine_key"] == "office_session_duration:all_days")
        self.assertEqual(item["sample_count"], 0)
        self.assertGreaterEqual(item["exclusions"]["uncertain_end"], 1)
        self.assertGreaterEqual(item["exclusions"]["restart_reconciled"], 1)

    def test_trustworthy_absence_is_included(self):
        source = {"sessions": [session(1, "2026-08-20T09:00:00+00:00", "2026-08-20T10:00:00+00:00"), session(2, "2026-08-21T09:00:00+00:00", "2026-08-21T10:00:00+00:00")], "events": []}
        item = next(item for item in build_snapshots(source, as_of=AS_OF, config=RoutineConfig()) if item["routine_key"] == "office_absence_between_sessions:all_days")
        self.assertEqual(item["sample_count"], 1)
        self.assertEqual(item["statistics"]["median"], 23 * 3600)

    def test_absence_crossing_camera_or_system_interruption_is_excluded(self):
        source = {"sessions": [session(1, "2026-08-20T09:00:00+00:00", "2026-08-20T10:00:00+00:00"), session(2, "2026-08-21T09:00:00+00:00", "2026-08-21T10:00:00+00:00")], "events": [event("room.camera_degraded", "2026-08-20T12:00:00+00:00"), event("system.started", "2026-08-20T12:01:00+00:00")]}
        item = next(item for item in build_snapshots(source, as_of=AS_OF, config=RoutineConfig()) if item["routine_key"] == "office_absence_between_sessions:all_days")
        self.assertEqual(item["sample_count"], 0)

    def test_multiple_identity_events_in_one_session_are_one_sample(self):
        source = source_with_days(1)
        source["events"].extend([event("person.identified", "2026-08-10T09:02:00+00:00", 1, {"person_id": "primary_user"}), event("person.identified", "2026-08-10T09:03:00+00:00", 1, {"person_id": "primary_user"})])
        snapshots = build_snapshots(source, as_of=AS_OF, config=RoutineConfig())
        item = next(item for item in snapshots if item["routine_key"] == "primary_user_session_first_confirmed_time:all_days")
        self.assertEqual(item["sample_count"], 1)

    def test_dst_conversion_uses_configured_iana_zone(self):
        config = RoutineConfig(timezone="America/New_York")
        source = {"sessions": [session(1, "2026-03-08T13:00:00+00:00", "2026-03-08T14:00:00+00:00")], "events": []}
        item = next(item for item in build_snapshots(source, as_of=datetime(2026, 3, 9, tzinfo=timezone.utc), config=config) if item["routine_key"] == "office_session_start_time:all_days")
        self.assertEqual(item["statistics"]["circular_center_local_time"], "09:00:00")
        self.assertEqual(item["timezone"], "America/New_York")

    def test_lookback_excludes_old_evidence(self):
        source = {"sessions": [session(1, "2025-01-01T09:00:00+00:00", "2025-01-01T10:00:00+00:00")], "events": []}
        item = next(item for item in build_snapshots(source, as_of=AS_OF, config=RoutineConfig()) if item["routine_key"] == "office_session_start_time:all_days")
        self.assertEqual(item["sample_count"], 0)

    def test_schema_v5_persistence_and_refresh_idempotence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sentry.db"
            source = source_with_days()
            with PresenceStore(path) as store:
                self.assertEqual(store.health()["schema_version"], 5)
                snapshots = build_snapshots(source, as_of=AS_OF, config=RoutineConfig())
                first = store.persist_routine_snapshots(snapshots)
                second = store.persist_routine_snapshots(build_snapshots(source, as_of=AS_OF.replace(minute=30), config=RoutineConfig()))
                self.assertEqual(first["written"], 40)
                self.assertTrue(second["skipped"])
                self.assertEqual(len(store.routine_snapshots()), 40)

    def test_changed_source_appends_new_snapshot_batch(self):
        with tempfile.TemporaryDirectory() as directory:
            with PresenceStore(Path(directory) / "sentry.db") as store:
                first = build_snapshots(source_with_days(), as_of=AS_OF, config=RoutineConfig())
                changed = source_with_days()
                changed["sessions"].append(session(99, "2026-08-30T09:00:00+00:00", "2026-08-30T10:00:00+00:00"))
                second = build_snapshots(changed, as_of=AS_OF, config=RoutineConfig())
                store.persist_routine_snapshots(first)
                result = store.persist_routine_snapshots(second)
                self.assertEqual(result["written"], 40)
                self.assertEqual(len(store.routine_snapshots(latest_only=False, limit=100)), 80)

    def test_atlas_restore_preserves_routine_snapshots(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local, atlas = root / "local" / "sentry.db", root / "atlas" / "sentry.db"
            with PresenceStore(local, atlas_mirror_path=atlas) as store:
                store.persist_routine_snapshots(build_snapshots(source_with_days(), as_of=AS_OF, config=RoutineConfig()))
            local.unlink()
            with PresenceStore(local, atlas_mirror_path=atlas) as restored:
                self.assertEqual(len(restored.routine_snapshots()), 40)
                self.assertEqual(restored.health()["schema_version"], 5)

    def test_api_returns_latest_routines_without_sensitive_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sentry.db"
            with PresenceStore(path) as store:
                store.persist_routine_snapshots(build_snapshots(source_with_days(), as_of=AS_OF, config=RoutineConfig()))
                server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
                server.store = store
                thread = Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
                    connection.request("GET", "/v1/routines")
                    response = connection.getresponse()
                    payload = json.loads(response.read())
                    self.assertEqual(response.status, 200)
                    self.assertEqual(len(payload["routines"]), 40)
                    self.assertTrue(all("prototype" not in item and "embedding" not in json.dumps(item) for item in payload["routines"]))
                finally:
                    server.shutdown()
                    thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
