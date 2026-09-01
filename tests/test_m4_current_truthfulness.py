import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from tools.sentry_ask import ask
from tools.sentry_grounding import build_fact_packet
from tools.sentry_state_api import perception_runtime_health, serve


def _responses(*, runtime: dict | None = None) -> dict:
    return {
        "health": {
            "ok": True,
            "db_available": True,
            "schema_version": 8,
            "atlas_mirror": {"status": "ok"},
            "display_timezone": "America/New_York",
            "perception": runtime or {
                "status": "fresh", "heartbeat_updated_at": "2026-08-31T14:00:00+00:00",
                "age_seconds": 1.0, "process_alive": True, "camera_state": "online",
                "room_state": "occupied", "current_physical_available": True, "reason": None,
            },
        },
        "state": {
            "room_id": "office", "state": "occupied", "camera_state": "online",
            "updated_at": "2026-08-30T14:24:29+00:00", "person_count": 1,
            "people": [{"track_id": 1, "person_id": "primary_user", "identity_state": "recognized"}],
        },
        "persons": {"persons": [{"person_id": "primary_user", "display_name": "Sketch"}]},
        "sessions": {"sessions": [{
            "session_id": 7, "room_id": "office", "started_at": "2026-08-30T14:00:00+00:00",
            "status": "open", "start_reason": "observed",
        }]},
        "events": {"events": [{
            "event_id": "id-1", "event_type": "person.identified", "occurred_at": "2026-08-30T14:24:29+00:00",
            "room_id": "office", "session_id": 7, "source": "sentry_perception",
            "payload": {"person_id": "primary_user"},
        }, {
            "event_id": "empty-1", "event_type": "room.became_empty", "occurred_at": "2026-08-29T21:00:00+00:00",
            "room_id": "office", "session_id": 6, "source": "sentry_perception", "payload": {},
        }]},
    }


class CurrentStateTruthfulnessTests(unittest.TestCase):
    def _heartbeat(self, directory: str, payload: object) -> Path:
        path = Path(directory) / "perception.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_runtime_health_distinguishes_fresh_stopped_stale_missing_and_malformed(self):
        now = datetime(2026, 8, 31, 15, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(perception_runtime_health(None, freshness_seconds=75, now=now)["status"], "missing")
            malformed = self._heartbeat(directory, {"not": "a heartbeat"})
            self.assertEqual(perception_runtime_health(malformed, freshness_seconds=75, now=now)["status"], "malformed")
            stopped = self._heartbeat(directory, {
                "updated_at": now.isoformat(), "process_alive": False,
                "summary": {"camera_state": "online", "room_state": "empty"},
            })
            self.assertEqual(perception_runtime_health(stopped, freshness_seconds=75, now=now)["status"], "stopped")
            stale = self._heartbeat(directory, {
                "updated_at": "2026-08-31T14:58:00+00:00", "process_alive": True,
                "summary": {"camera_state": "online", "room_state": "empty"},
            })
            self.assertEqual(perception_runtime_health(stale, freshness_seconds=75, now=now)["status"], "stale")
            fresh = self._heartbeat(directory, {
                "updated_at": now.isoformat(), "process_alive": True,
                "summary": {"camera_state": "online", "room_state": "occupied"},
            })
            self.assertTrue(perception_runtime_health(fresh, freshness_seconds=75, now=now)["current_physical_available"])

    def test_degraded_or_offline_fresh_heartbeat_does_not_support_current_occupancy(self):
        now = datetime(2026, 8, 31, 15, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as directory:
            for camera_state in ("degraded", "offline"):
                with self.subTest(camera_state=camera_state):
                    heartbeat = self._heartbeat(directory, {
                        "updated_at": now.isoformat(), "process_alive": True,
                        "summary": {"camera_state": camera_state, "room_state": "empty"},
                    })
                    health = perception_runtime_health(heartbeat, freshness_seconds=75, now=now)
                    self.assertEqual(health["status"], "fresh")
                    self.assertFalse(health["current_physical_available"])

    def test_stopped_perception_omits_current_facts_but_retains_history(self):
        stopped = {
            "status": "stopped", "heartbeat_updated_at": "2026-08-31T14:00:00+00:00",
            "age_seconds": 60.0, "process_alive": False, "camera_state": "online",
            "room_state": "empty", "current_physical_available": False, "reason": "perception process is stopped",
        }
        packet = build_fact_packet(_responses(runtime=stopped), as_of="2026-08-31T15:00:00+00:00")
        facts = {fact["fact_id"]: fact for fact in packet["facts"]}
        self.assertNotIn("current-room-state", facts)
        self.assertNotIn("current-room-people", facts)
        self.assertNotIn("current-open-session", facts)
        self.assertIn("room-sessions", facts)
        self.assertIn("room-events", facts)
        self.assertIn("primary-user-identification", facts)
        self.assertIn("last-confirmed-empty", facts)
        self.assertFalse(facts["perception-runtime"]["data"]["current_physical_available"])

    def test_current_fact_is_absent_when_stopped(self):
        responses = _responses(runtime={
            "status": "stopped", "heartbeat_updated_at": "2026-08-31T14:00:00+00:00",
            "age_seconds": 60.0, "process_alive": False, "camera_state": "online",
            "room_state": "empty", "current_physical_available": False, "reason": "perception process is stopped",
        })
        packet = build_fact_packet(responses)
        self.assertNotIn("current-room-state", {fact["fact_id"] for fact in packet["facts"]})

    def test_historical_facts_remain_usable_when_perception_is_stopped(self):
        responses = _responses(runtime={
            "status": "stopped", "heartbeat_updated_at": "2026-08-31T14:00:00+00:00",
            "age_seconds": 60.0, "process_alive": False, "camera_state": "online",
            "room_state": "empty", "current_physical_available": False, "reason": "perception process is stopped",
        })
        packet = build_fact_packet(responses)
        ids = {fact["fact_id"] for fact in packet["facts"]}
        self.assertNotIn("current-room-state", ids)
        self.assertIn("primary-user-identification", ids)

    def test_local_display_uses_eastern_12_hour_time_and_preserves_raw_timestamp(self):
        for raw, expected in (
            ("2026-08-30T14:24:29+00:00", "August 30, 2026 at 10:24 AM EDT"),
            ("2026-01-15T14:24:29+00:00", "January 15, 2026 at 9:24 AM EST"),
            ("2026-03-08T07:30:00+00:00", "March 8, 2026 at 3:30 AM EDT"),
            ("2026-11-01T05:30:00+00:00", "November 1, 2026 at 1:30 AM EDT"),
            ("2026-11-01T06:30:00+00:00", "November 1, 2026 at 1:30 AM EST"),
        ):
            with self.subTest(raw=raw):
                responses = _responses()
                responses["events"]["events"][0]["occurred_at"] = raw
                packet = build_fact_packet(responses, as_of="2026-08-31T15:00:00+00:00")
                event = next(fact for fact in packet["facts"] if fact["fact_id"] == "room-events")["data"]["events"][0]
                self.assertEqual(event["occurred_at"], raw)
                self.assertEqual(event["occurred_at_local_display"], expected)

    def test_invalid_display_timezone_is_rejected(self):
        with self.assertRaises(ValueError):
            serve(Path("/tmp/unused-sentry.db"), port=0, display_timezone="Not/A_Zone")

    def test_production_state_api_unit_passes_explicit_runtime_contract(self):
        unit = Path("deploy/systemd/user/sentry-state-api.service").read_text(encoding="utf-8")
        self.assertIn("--perception-heartbeat /srv/ATLAS/100_ACTIVE/Projects/SENTRY/perception-data/runtime/health/perception.json", unit)
        self.assertIn("--perception-freshness-seconds 75", unit)
        self.assertIn("--display-timezone America/New_York", unit)


if __name__ == "__main__":
    unittest.main()
