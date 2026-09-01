import tempfile
import unittest
from pathlib import Path

from perception.presence_store import PresenceStore


def observation(
    state: str,
    timestamp: str,
    transition: str | None = None,
    camera_state: str = "online",
    people: list[dict] | None = None,
) -> dict:
    return {
        "room_state": state,
        "captured_at": timestamp,
        "camera_state": camera_state,
        "room_state_transition": transition,
        "frame_sequence": 1,
        "people": people or [],
        "detector_evidence": state == "occupied",
        "max_person_confidence": 0.8 if state == "occupied" else None,
    }


class PresenceStoreTests(unittest.TestCase):
    def test_migration_and_current_state_survive_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime" / "sentry.db"
            with PresenceStore(path) as store:
                store.record_observation(observation("empty", "2026-08-28T12:00:00+00:00"))
                state = store.current_state()
                self.assertEqual(state.state, "empty")
                self.assertEqual(store._connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0], 8)
            with PresenceStore(path) as reopened:
                self.assertEqual(reopened.current_state().state, "empty")

    def test_occupied_and_empty_transitions_create_and_close_one_session(self):
        with tempfile.TemporaryDirectory() as directory, PresenceStore(Path(directory) / "sentry.db") as store:
            store.record_observation(observation("empty", "2026-08-28T12:00:00+00:00"))
            store.record_observation(
                observation("occupied", "2026-08-28T12:00:02+00:00", "empty->occupied", people=[{"visible": True}])
            )
            store.record_observation(
                observation("empty", "2026-08-28T12:00:20+00:00", "occupied->empty")
            )
            sessions = store.sessions()
            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0]["status"], "completed")
            self.assertEqual(sessions[0]["started_at"], "2026-08-28T12:00:02+00:00")
            events = [event["event_type"] for event in store.events()]
            self.assertEqual(
                set(events),
                {"room.became_occupied", "presence.session_started", "room.became_empty", "presence.session_ended"},
            )

    def test_camera_failure_is_recorded_without_fabricating_empty(self):
        with tempfile.TemporaryDirectory() as directory, PresenceStore(Path(directory) / "sentry.db") as store:
            store.record_observation(observation("empty", "2026-08-28T12:00:00+00:00"))
            store.record_observation(
                observation("offline", "2026-08-28T12:00:01+00:00", "empty->offline", camera_state="offline")
            )
            self.assertEqual(store.current_state().state, "offline")
            self.assertEqual(store.sessions(), [])
            self.assertIn("room.camera_offline", [event["event_type"] for event in store.events()])

    def test_duplicate_tracks_remain_metadata_not_occupant_count(self):
        with tempfile.TemporaryDirectory() as directory, PresenceStore(Path(directory) / "sentry.db") as store:
            store.record_observation(observation("empty", "2026-08-28T12:00:00+00:00"))
            store.record_observation(
                observation(
                    "occupied",
                    "2026-08-28T12:00:02+00:00",
                    "empty->occupied",
                    people=[{"visible": True}, {"visible": True}, {"visible": False}],
                )
            )
            self.assertEqual(store.current_state().person_count, 2)
            self.assertEqual(len(store.sessions()), 1)
            self.assertEqual(len(store.events()), 2)

    def test_restart_resumed_open_session_marks_continuity_uncertain(self):
        with tempfile.TemporaryDirectory() as directory, PresenceStore(Path(directory) / "sentry.db") as store:
            store.start("2026-09-01T09:00:00+00:00")
            store.record_observation(observation("empty", "2026-09-01T09:00:01+00:00"))
            store.record_observation(
                observation("occupied", "2026-09-01T09:00:02+00:00", "empty->occupied", people=[{"visible": True}])
            )
            store.stop("2026-09-01T09:01:00+00:00")
            store.reconcile_after_restart(
                observation("occupied", "2026-09-01T09:02:00+00:00", people=[{"visible": True}])
            )
            session = store.sessions()[0]
            self.assertEqual(session["recovered_after_restart"], 1)
            self.assertEqual(session["continuity_uncertain"], 1)
            self.assertIn("presence.restart_reconciled", [event["event_type"] for event in store.events()])

    def test_primary_confirmation_filter_is_bounded_and_timestamped(self):
        with tempfile.TemporaryDirectory() as directory, PresenceStore(Path(directory) / "sentry.db") as store:
            store.record_observation(observation("empty", "2026-09-01T09:00:00+00:00"))
            store.record_observation(observation(
                "occupied",
                "2026-09-01T09:01:00+00:00",
                "empty->occupied",
                people=[{
                    "visible": True,
                    "track_id": 3,
                    "person_id": "primary_user",
                    "identity_state": "recognized",
                    "identity_confidence": 0.9,
                }],
            ))
            matches = store.events(
                event_type="person.identified",
                person_id="primary_user",
                since="2026-09-01T00:00:00+00:00",
            )
            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0]["event_type"], "person.identified")
            with self.assertRaises(ValueError):
                store.events(event_type="room.became_occupied", person_id="primary_user")


if __name__ == "__main__":
    unittest.main()
