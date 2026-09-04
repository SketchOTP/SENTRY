import json
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from perception.speaker_context import (
    SOURCE,
    WakeIdentityCoordinator,
    context_from_camera_metadata,
)


class Clock:
    def __init__(self, value=0.0):
        self.value = value

    def __call__(self):
        return self.value


def metadata(people):
    return {
        "observed_at": "2026-09-02T22:14:00+00:00",
        "people": people,
        "frames_persisted": False,
        "image_shared_with_codex": False,
    }


class SpeakerContextClassificationTests(unittest.TestCase):
    def classify(self, people):
        return context_from_camera_metadata(
            metadata(people), conversation_epoch_id="epoch-1", now=10.0,
            ttl_seconds=7200.0,
            wall_now=datetime(2026, 9, 2, 22, 14, tzinfo=timezone.utc),
        )

    def test_exactly_one_enrolled_match_is_recognized(self):
        context = self.classify([{
            "visible": True, "identity_state": "recognized",
            "person_id": "primary_user", "display_name": "Sketch",
            "identity_confidence": 1.5,
        }])
        self.assertEqual(context.identity_state, "recognized")
        self.assertEqual(context.person_id, "primary_user")
        self.assertEqual(context.display_name, "Sketch")
        self.assertEqual(context.identity_confidence, 1.0)
        self.assertFalse(context.exact_arrival_known)
        self.assertFalse(context.frames_persisted)
        self.assertFalse(context.image_shared_with_codex)
        self.assertEqual(context.source, SOURCE)

    def test_any_deliberately_enrolled_profile_can_name_the_speaker(self):
        context = self.classify([{
            "visible": True, "identity_state": "recognized",
            "person_id": "guest-user", "display_name": "Guest User",
            "identity_confidence": 0.88,
        }])
        self.assertEqual(context.identity_state, "recognized")
        self.assertEqual(context.person_id, "guest-user")
        self.assertEqual(context.display_name, "Guest User")

    def test_unknown_unresolved_empty_and_multiple_are_conservative(self):
        cases = [
            ([{"visible": True, "identity_state": "unknown"}], "unknown"),
            ([{"visible": True, "identity_state": "unresolved"}], "unresolved"),
            ([], "not_visible"),
            ([
                {"visible": True, "identity_state": "recognized", "person_id": "primary_user"},
                {"visible": True, "identity_state": "unknown"},
            ], "ambiguous"),
        ]
        for people, expected in cases:
            with self.subTest(expected=expected):
                context = self.classify(people)
                self.assertEqual(context.identity_state, expected)
                self.assertIsNone(context.person_id)
                self.assertIsNone(context.display_name)

    def test_expired_envelope_does_not_identify_speaker(self):
        context = self.classify([{
            "visible": True, "identity_state": "recognized",
            "person_id": "primary_user", "display_name": "Sketch",
        }])
        envelope = context.envelope(7211.0)
        self.assertEqual(envelope["status"], "expired")
        self.assertIsNone(envelope["person_id"])
        self.assertFalse(envelope["exact_arrival_known"])


class WakeIdentityCoordinatorTests(unittest.TestCase):
    def make_coordinator(self, inspector, clock=None):
        clock = clock or Clock()
        coordinator = WakeIdentityCoordinator(
            inspector,
            idle_seconds=7200,
            ttl_seconds=7200,
            inspection_duration_seconds=3,
            join_timeout_seconds=5,
            clock=clock,
            wall_clock=lambda: datetime(2026, 9, 2, 22, 14, tzinfo=timezone.utc),
        )
        return coordinator, clock

    def test_first_wake_inspects_and_followup_envelope_reuses_context(self):
        calls = []
        coordinator, _ = self.make_coordinator(
            lambda duration: calls.append(duration) or metadata([{
                "visible": True, "identity_state": "recognized",
                "person_id": "primary_user", "display_name": "Sketch",
                "identity_confidence": 0.91,
            }])
        )
        epoch, started = coordinator.begin_explicit_wake()
        envelope = coordinator.current_envelope(wait_for_preflight=True)
        followup = coordinator.current_envelope()
        self.assertTrue(started)
        self.assertEqual(calls, [3])
        self.assertEqual(envelope["conversation_epoch_id"], epoch)
        self.assertEqual(coordinator.diagnostics()["speaker_context_display_name"], "Sketch")
        self.assertEqual(followup["context_id"], envelope["context_id"])
        self.assertEqual(coordinator.diagnostics()["speaker_context_inspection_count"], 1)

    def test_inspection_starts_concurrently_without_blocking_wake_path(self):
        started = threading.Event()
        release = threading.Event()

        def inspector(_duration):
            started.set()
            release.wait(0.5)
            return metadata([])

        coordinator, _ = self.make_coordinator(inspector)
        before = time.monotonic()
        coordinator.begin_explicit_wake()
        elapsed = time.monotonic() - before
        self.assertTrue(started.wait(0.2))
        self.assertLess(elapsed, 0.1)
        self.assertTrue(coordinator.diagnostics()["speaker_context_preflight_active"])
        release.set()
        coordinator.current_envelope(wait_for_preflight=True)

    def test_second_wake_inside_ttl_reuses_context_without_inspection(self):
        calls = []
        coordinator, clock = self.make_coordinator(
            lambda duration: calls.append(duration) or metadata([{
                "visible": True, "identity_state": "recognized",
                "person_id": "primary_user", "display_name": "Sketch",
                "identity_confidence": 0.91,
            }])
        )
        first_epoch, _ = coordinator.begin_explicit_wake()
        coordinator.current_envelope(wait_for_preflight=True)
        coordinator.record_accepted_user_utterance()
        clock.value = 60
        second_epoch, started = coordinator.begin_explicit_wake()
        self.assertFalse(started)
        self.assertEqual(second_epoch, first_epoch)
        self.assertEqual(calls, [3])

    def test_recognized_identity_cache_survives_listener_restart_for_two_hours(self):
        with tempfile.TemporaryDirectory() as directory:
            cache_path = Path(directory) / "speaker-context.json"
            observed_wall = datetime(2026, 9, 2, 22, 14, tzinfo=timezone.utc)
            first_calls = []
            first = WakeIdentityCoordinator(
                lambda duration: first_calls.append(duration) or metadata([{
                    "visible": True,
                    "identity_state": "recognized",
                    "person_id": "primary_user",
                    "display_name": "Sketch",
                    "identity_confidence": 0.91,
                }]),
                idle_seconds=7200,
                ttl_seconds=7200,
                inspection_duration_seconds=3,
                join_timeout_seconds=5,
                cache_path=cache_path,
                clock=Clock(10),
                wall_clock=lambda: observed_wall,
            )
            first.begin_explicit_wake()
            recognized = first.current_envelope(wait_for_preflight=True)
            self.assertEqual(recognized["status"], "recognized")
            self.assertTrue(cache_path.is_file())
            self.assertEqual(cache_path.stat().st_mode & 0o777, 0o600)
            first.clear("shutdown")
            self.assertEqual(first.current_envelope()["status"], "unavailable")
            self.assertTrue(cache_path.is_file(), "clean listener restart must retain the two-hour cache")

            second_calls = []
            second = WakeIdentityCoordinator(
                lambda duration: second_calls.append(duration) or metadata([]),
                idle_seconds=7200,
                ttl_seconds=7200,
                inspection_duration_seconds=3,
                join_timeout_seconds=5,
                cache_path=cache_path,
                clock=Clock(70),
                wall_clock=lambda: observed_wall + timedelta(seconds=60),
            )
            envelope = second.current_envelope()
            self.assertEqual(envelope["status"], "recognized")
            self.assertEqual(envelope["display_name"], "Sketch")
            _epoch, started = second.begin_explicit_wake()
            self.assertFalse(started)
            self.assertEqual(second_calls, [])
            self.assertTrue(second.diagnostics()["speaker_context_cache_loaded"])

            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            self.assertEqual(cached["person_id"], "primary_user")
            for prohibited in ("image", "embedding", "transcript", "audio"):
                self.assertNotIn(prohibited, json.dumps(cached).lower())

    def test_expired_recognized_cache_is_removed_and_rechecked(self):
        with tempfile.TemporaryDirectory() as directory:
            cache_path = Path(directory) / "speaker-context.json"
            observed_wall = datetime(2026, 9, 2, 22, 14, tzinfo=timezone.utc)
            first = WakeIdentityCoordinator(
                lambda _duration: metadata([{
                    "visible": True,
                    "identity_state": "recognized",
                    "person_id": "primary_user",
                    "display_name": "Sketch",
                }]),
                cache_path=cache_path,
                clock=Clock(),
                wall_clock=lambda: observed_wall,
            )
            first.begin_explicit_wake()
            first.current_envelope(wait_for_preflight=True)

            calls = []
            expired = WakeIdentityCoordinator(
                lambda duration: calls.append(duration) or metadata([]),
                cache_path=cache_path,
                clock=Clock(7201),
                wall_clock=lambda: observed_wall + timedelta(seconds=7201),
            )
            self.assertEqual(expired.current_envelope()["status"], "unavailable")
            self.assertFalse(cache_path.exists())
            _epoch, started = expired.begin_explicit_wake()
            self.assertTrue(started)
            expired.current_envelope(wait_for_preflight=True)
            self.assertEqual(calls, [3.0])

    def test_idle_and_absolute_ttl_trigger_refresh_without_turn_extension(self):
        calls = []
        coordinator, clock = self.make_coordinator(lambda duration: calls.append(duration) or metadata([]))
        coordinator.begin_explicit_wake()
        coordinator.current_envelope(wait_for_preflight=True)
        coordinator.record_accepted_user_utterance()
        clock.value = 7199
        coordinator.record_accepted_user_utterance()
        clock.value = 7201
        _, started = coordinator.begin_explicit_wake()
        self.assertTrue(started, "absolute observation TTL is not extended by voice turns")
        coordinator.current_envelope(wait_for_preflight=True)
        clock.value = 8000
        coordinator.record_accepted_user_utterance()
        clock.value = 15200
        _, started = coordinator.begin_explicit_wake()
        self.assertTrue(started, "voice inactivity independently refreshes identity")
        self.assertEqual(len(calls), 3)

    def test_unresolved_result_is_reused_in_conversation_but_rechecked_on_next_wake(self):
        calls = []
        coordinator, clock = self.make_coordinator(
            lambda duration: calls.append(duration) or metadata([{"visible": True, "identity_state": "unresolved"}])
        )
        coordinator.begin_explicit_wake()
        coordinator.current_envelope(wait_for_preflight=True)
        self.assertEqual(coordinator.current_envelope()["status"], "unresolved")
        clock.value = 1
        _, started = coordinator.begin_explicit_wake()
        self.assertTrue(started)
        coordinator.current_envelope(wait_for_preflight=True)
        self.assertEqual(len(calls), 2)

    def test_profile_catalog_change_invalidates_cached_negative_context(self):
        calls = []
        revisions = iter(["profile-v1", "profile-v1", "profile-v2"])
        coordinator = WakeIdentityCoordinator(
            lambda duration: calls.append(duration) or metadata([]),
            idle_seconds=7200,
            ttl_seconds=7200,
            inspection_duration_seconds=3,
            join_timeout_seconds=5,
            profile_revision_provider=lambda: next(revisions),
            clock=Clock(),
            wall_clock=lambda: datetime(2026, 9, 2, 22, 14, tzinfo=timezone.utc),
        )
        coordinator.begin_explicit_wake()
        coordinator.current_envelope(wait_for_preflight=True)
        _, started = coordinator.begin_explicit_wake()
        self.assertTrue(started)
        coordinator.current_envelope(wait_for_preflight=True)
        self.assertEqual(calls, [3, 3])
        diagnostics = coordinator.diagnostics()
        self.assertEqual(diagnostics["speaker_context_refresh_reason"], "profile_catalog_changed")
        self.assertEqual(diagnostics["speaker_context_profile_catalog_change_count"], 1)

    def test_failure_and_timeout_are_unavailable_and_conversation_can_continue(self):
        coordinator, _ = self.make_coordinator(lambda _duration: (_ for _ in ()).throw(RuntimeError("camera failed")))
        coordinator.begin_explicit_wake()
        failed = coordinator.current_envelope(wait_for_preflight=True)
        self.assertEqual(failed["status"], "unavailable")
        self.assertEqual(failed["reason"], "RuntimeError")

        started = threading.Event()
        release = threading.Event()
        slow_clock = Clock()

        def slow(_duration):
            started.set()
            release.wait(0.5)
            return metadata([])

        timeout_coordinator = WakeIdentityCoordinator(
            slow, join_timeout_seconds=0.01, inspection_duration_seconds=0.005,
            clock=slow_clock,
        )
        timeout_coordinator.begin_explicit_wake()
        started.wait(0.2)
        timed_out = timeout_coordinator.current_envelope(wait_for_preflight=True)
        release.set()
        self.assertEqual(timed_out["status"], "unavailable")
        self.assertEqual(timed_out["reason"], "inspection_timeout")

    def test_clear_discards_late_old_epoch_and_removes_ram_context(self):
        started = threading.Event()
        release = threading.Event()

        def slow(_duration):
            started.set()
            release.wait(0.5)
            return metadata([{
                "visible": True, "identity_state": "recognized",
                "person_id": "primary_user", "display_name": "Sketch",
            }])

        coordinator, _ = self.make_coordinator(slow)
        coordinator.begin_explicit_wake()
        started.wait(0.2)
        coordinator.clear("thread_rotation")
        release.set()
        time.sleep(0.02)
        self.assertEqual(coordinator.current_envelope()["status"], "unavailable")
        self.assertGreaterEqual(coordinator.diagnostics()["speaker_context_late_result_count"], 1)

    def test_followup_reads_do_not_refresh_or_extend_context(self):
        calls = []
        coordinator, clock = self.make_coordinator(lambda duration: calls.append(duration) or metadata([]))
        coordinator.begin_explicit_wake()
        first = coordinator.current_envelope(wait_for_preflight=True)
        for value in (100, 1800, 3600, 7199):
            clock.value = value
            self.assertEqual(coordinator.current_envelope()["context_id"], first["context_id"])
            coordinator.record_accepted_user_utterance()
        clock.value = 7201
        self.assertEqual(coordinator.current_envelope()["status"], "expired")
        self.assertEqual(calls, [3])

    def test_diagnostics_are_metadata_only(self):
        coordinator, _ = self.make_coordinator(lambda _duration: metadata([]))
        coordinator.begin_explicit_wake()
        coordinator.current_envelope(wait_for_preflight=True)
        payload = coordinator.diagnostics()
        serialized = str(payload).lower()
        for prohibited in ("jpeg", "embedding", "transcript", "face_crop"):
            self.assertNotIn(prohibited, serialized)


if __name__ == "__main__":
    unittest.main()
