import json
import inspect
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.sentry_ui import (
    KOKORO_ENGLISH_VOICES,
    ORB_STYLES,
    OrbStateController,
    apply_sleep_preference,
    load_sleep_preference,
    load_voice_preferences,
    read_voice_status,
    resolve_sleep_transition_status,
    save_sleep_preference,
    save_voice_preferences,
    should_acknowledge_wake,
    voice_indicator_model,
    voice_status_summary,
)


class SentryNativeUiTests(unittest.TestCase):
    def test_voice_catalog_has_broad_english_accent_and_gender_coverage(self):
        identifiers = {identifier for identifier, _label in KOKORO_ENGLISH_VOICES}
        self.assertGreaterEqual(len(identifiers), 28)
        for prefix in ("bm_", "bf_", "am_", "af_"):
            self.assertTrue(any(identifier.startswith(prefix) for identifier in identifiers))

    def test_voice_preferences_update_only_voice_fields_atomically(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({
                "voice": {
                    "always_on_enabled": True,
                    "sleep_enabled": True,
                    "kokoro_voice": "bm_george",
                    "kokoro_speed": 0.9,
                },
                "weather": {"enabled": True, "fixture": "preserved"},
            }), encoding="utf-8")
            path.chmod(0o640)
            save_voice_preferences(path, "af_bella", 1.1)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["weather"], {"enabled": True, "fixture": "preserved"})
            self.assertTrue(payload["voice"]["always_on_enabled"])
            self.assertTrue(payload["voice"]["sleep_enabled"])
            self.assertEqual(load_voice_preferences(path), ("af_bella", 1.1))
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(list(path.parent.glob(".*.tmp")), [])

    def test_voice_preferences_reject_unknown_voice_and_out_of_range_speed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({"voice": {}}), encoding="utf-8")
            with self.assertRaises(ValueError):
                save_voice_preferences(path, "unknown_voice", 1.0)
            with self.assertRaises(ValueError):
                save_voice_preferences(path, "bm_george", 1.5)

    def test_sleep_preference_defaults_off_and_persists_across_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({
                "voice": {"kokoro_voice": "bm_george", "kokoro_speed": 0.9},
                "weather": {"enabled": True},
            }), encoding="utf-8")
            self.assertFalse(load_sleep_preference(path))
            save_sleep_preference(path, True)
            self.assertTrue(load_sleep_preference(path))
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["weather"], {"enabled": True})
            self.assertEqual(payload["voice"]["kokoro_voice"], "bm_george")
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_sleep_apply_stops_and_wake_apply_starts_resident_listener(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({"voice": {"sleep_enabled": False}}), encoding="utf-8")
            with patch("tools.sentry_ui.voice_service_is_active", return_value=False), patch(
                "tools.sentry_ui.subprocess.run"
            ) as run:
                self.assertEqual(apply_sleep_preference(path, True), "sleeping")
                self.assertEqual(run.call_args.args[0][2], "stop")
            self.assertTrue(load_sleep_preference(path))

            with patch("tools.sentry_ui.voice_service_is_active", return_value=True), patch(
                "tools.sentry_ui.subprocess.run"
            ) as run:
                self.assertEqual(apply_sleep_preference(path, False), "starting")
                self.assertEqual(run.call_args.args[0][2], "start")
            self.assertFalse(load_sleep_preference(path))

    def test_voice_status_is_rendered_inside_native_ui(self):
        state, guidance, identity = voice_status_summary({
            "state": "LISTENING",
            "speaker_context_active": True,
            "speaker_context_state": "recognized",
            "speaker_context_display_name": "Sketch",
        })
        self.assertEqual(state, "LISTENING")
        self.assertEqual(guidance, "Standby")
        self.assertEqual(identity, "Current speaker: Sketch")

    def test_unresolved_identity_uses_operator_fallback(self):
        _state, _guidance, identity = voice_status_summary({
            "state": "PROCESSING",
            "speaker_context_active": True,
            "speaker_context_state": "unresolved",
        })
        self.assertIn("operator", identity)

    def test_sleeping_state_is_explicit_and_uses_inactive_orb(self):
        state, guidance, identity = voice_status_summary({"state": "SLEEPING"})
        self.assertEqual(state, "SLEEPING")
        self.assertEqual(guidance, "Sleeping")
        self.assertIn("inactive while sleeping", identity)
        self.assertEqual(
            voice_indicator_model({"state": "SLEEPING"})["semantic_state"],
            "OFFLINE",
        )

    def test_disabling_sleep_masks_stale_sleep_status_until_listener_is_ready(self):
        stale, transition = resolve_sleep_transition_status(
            {"state": "SLEEPING", "sleep_enabled": True, "wake_enabled": False},
            sleep_enabled=False,
            transition_state="STARTING",
        )
        self.assertEqual(stale["state"], "STARTING")
        self.assertEqual(transition, "STARTING")
        self.assertEqual(voice_status_summary(stale)[1], "Waking SENTRY…")
        self.assertEqual(voice_indicator_model(stale)["semantic_state"], "PROCESSING")

        ready = {"state": "LISTENING", "sleep_enabled": False, "wake_enabled": True}
        resolved, transition = resolve_sleep_transition_status(
            ready,
            sleep_enabled=False,
            transition_state="STARTING",
        )
        self.assertIs(resolved, ready)
        self.assertIsNone(transition)

    def test_status_reader_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "voice.json"
            self.assertEqual(read_voice_status(path)["state"], "UNAVAILABLE")
            path.write_text("not-json", encoding="utf-8")
            self.assertEqual(read_voice_status(path)["state"], "UNAVAILABLE")
            path.write_text(json.dumps({"state": "CAPTURING"}), encoding="utf-8")
            self.assertEqual(read_voice_status(path)["state"], "CAPTURING")

    def test_single_orb_makes_speaking_and_listening_boundaries_explicit(self):
        standby = voice_indicator_model({"state": "LISTENING"})
        capture = voice_indicator_model({"state": "CAPTURING"})
        working = voice_indicator_model({"state": "PROCESSING"})
        speaking = voice_indicator_model({"state": "SPEAKING"})
        followup = voice_indicator_model({"state": "FOLLOWUP_LISTENING"})
        self.assertEqual(standby["semantic_state"], "STANDBY")
        self.assertEqual(capture["semantic_state"], "LISTENING")
        self.assertEqual(working["semantic_state"], "PROCESSING")
        self.assertEqual(speaking["semantic_state"], "SPEAKING")
        self.assertEqual(followup["semantic_state"], "FOLLOWUP_LISTENING")
        self.assertEqual(ORB_STYLES["STANDBY"]["mode"], "dormant")
        self.assertEqual(ORB_STYLES["LISTENING"]["mode"], "receptive")
        self.assertEqual(ORB_STYLES["PROCESSING"]["mode"], "orbiting")
        self.assertEqual(ORB_STYLES["SPEAKING"]["mode"], "emissive")

    def test_audio_intensity_cannot_choose_semantic_state(self):
        listening = voice_indicator_model({
            "state": "CAPTURING", "microphone_audio_level": 0.8, "output_audio_level": 1.0,
        })
        processing = voice_indicator_model({
            "state": "PROCESSING", "microphone_audio_level": 1.0, "output_audio_level": 1.0,
        })
        speaking = voice_indicator_model({
            "state": "SPEAKING", "microphone_audio_level": 1.0, "output_audio_level": 0.7,
        })
        self.assertEqual(listening["semantic_state"], "LISTENING")
        self.assertEqual(processing["semantic_state"], "PROCESSING")
        self.assertEqual(speaking["semantic_state"], "SPEAKING")

    def test_controller_uses_input_only_for_listening_and_output_only_for_speaking(self):
        controller = OrbStateController(now=0.0)
        controller.update({"state": "CAPTURING", "microphone_audio_level": 0.8, "output_audio_level": 1.0}, now=0.1)
        listening = controller.frame(now=0.6)
        self.assertEqual(listening["state"], "LISTENING")
        self.assertGreater(listening["audio_level"], 0.6)
        self.assertLess(listening["audio_level"], 0.8)

        controller.update({"state": "PROCESSING", "microphone_audio_level": 1.0, "output_audio_level": 1.0}, now=0.7)
        processing = controller.frame(now=1.2)
        self.assertEqual(processing["audio_level"], 0.0)

        controller.update({"state": "SPEAKING", "microphone_audio_level": 1.0, "output_audio_level": 0.65}, now=1.3)
        speaking = controller.frame(now=1.8)
        self.assertGreater(speaking["audio_level"], 0.5)

    def test_wake_acknowledgement_contracts_then_rebounds(self):
        controller = OrbStateController(now=0.0)
        controller.update({"state": "WAKE_DETECTED"}, now=1.0)
        controller.acknowledge_wake(now=1.0)
        contracted = controller.frame(now=1.08)
        rebounding = controller.frame(now=1.21)
        self.assertLess(contracted["shell_scale"], rebounding["shell_scale"])
        self.assertIsNotNone(contracted["wake_progress"])

    def test_reduced_motion_retains_state_structure_with_smaller_float(self):
        full = OrbStateController(now=0.0).frame(now=1.5, reduced_motion=False)
        reduced = OrbStateController(now=0.0).frame(now=1.5, reduced_motion=True)
        self.assertEqual(full["mode"], reduced["mode"])
        self.assertLessEqual(abs(reduced["float_offset"]), abs(full["float_offset"]))

    def test_speaking_audio_never_changes_glass_shell_size(self):
        controller = OrbStateController(now=0.0)
        controller.update({"state": "SPEAKING", "output_audio_level": 1.0}, now=0.1)
        frame = controller.frame(now=0.6)
        self.assertEqual(frame["state"], "SPEAKING")
        self.assertEqual(frame["shell_scale"], 1.0)

    def test_normal_state_changes_use_a_visible_morph(self):
        controller = OrbStateController(now=0.0)
        controller.update({"state": "CAPTURING", "microphone_audio_level": 0.8}, now=0.1)
        frame = controller.frame(now=0.2)
        self.assertLess(frame["transition_progress"], 0.2)
        controller.update({"state": "PROCESSING"}, now=0.3)
        frame = controller.frame(now=0.4)
        self.assertLess(frame["transition_progress"], 0.2)

    def test_transition_retains_previous_states_audio_energy(self):
        controller = OrbStateController(now=0.0)
        controller.update({"state": "CAPTURING", "microphone_audio_level": 0.9}, now=0.1)
        controller.frame(now=0.7)
        controller.update({"state": "PROCESSING"}, now=0.71)
        frame = controller.frame(now=0.72)
        self.assertGreater(frame["previous_audio_level"], 0.7)
        self.assertEqual(frame["audio_level"], 0.0)

    def test_wake_to_listening_leaves_time_for_the_spirit_material_to_gather(self):
        controller = OrbStateController(now=0.0)
        controller.update({"state": "WAKE_DETECTED"}, now=0.1)
        controller.update({"state": "CAPTURING"}, now=0.2)
        frame = controller.frame(now=0.61)
        self.assertEqual(frame["previous_state"], "WAKE_DETECTED")
        self.assertAlmostEqual(frame["transition_progress"], 0.5, places=2)

    def test_all_active_orbs_inherit_the_standby_float_amount(self):
        for state in (
            "WAKE_DETECTED", "LISTENING", "PROCESSING", "SPEAKING", "FOLLOWUP_LISTENING",
        ):
            with self.subTest(state=state):
                self.assertGreaterEqual(ORB_STYLES[state]["float"], 0.7)

    def test_material_reformation_transitions_have_a_slow_vapor_midpoint(self):
        controller = OrbStateController(now=0.0)
        controller.update({"state": "CAPTURING"}, now=0.1)
        controller.frame(now=1.0)
        controller.update({"state": "PROCESSING"}, now=1.1)
        frame = controller.frame(now=1.875)
        self.assertEqual(frame["previous_state"], "LISTENING")
        self.assertAlmostEqual(frame["transition_progress"], 0.5, places=2)

        controller.update({"state": "SPEAKING", "output_audio_level": 0.6}, now=2.3)
        frame = controller.frame(now=3.075)
        self.assertEqual(frame["previous_state"], "PROCESSING")
        self.assertAlmostEqual(frame["transition_progress"], 0.5, places=2)

    def test_wake_visual_acknowledgement_fires_once_per_new_wake_not_on_startup(self):
        self.assertFalse(should_acknowledge_wake(None, "wake-1"))
        self.assertFalse(should_acknowledge_wake("wake-1", "wake-1"))
        self.assertTrue(should_acknowledge_wake("wake-1", "wake-2"))

    def test_settings_use_an_in_window_overlay_not_a_transient_popover(self):
        from tools.sentry_ui import build_application

        source = inspect.getsource(build_application)
        self.assertIn("Gtk.Overlay", source)
        self.assertIn("Gtk.Revealer", source)
        self.assertIn("Gtk.RevealerTransitionType.SLIDE_LEFT", source)
        self.assertIn("root.add_overlay(drawer_host)", source)
        self.assertIn('"go-previous-symbolic"', source)
        self.assertIn('"go-next-symbolic"', source)
        self.assertNotIn("Gtk.Popover", source)
        self.assertNotIn("Gtk.MenuButton", source)

    def test_application_launch_always_restores_collapsed_settings(self):
        from tools.sentry_ui import build_application

        source = inspect.getsource(build_application)
        self.assertIn("drawer.set_reveal_child(False)", source)
        self.assertIn("def close_settings(self)", source)
        self.assertIn("window.close_settings()", source)
        self.assertIn('self.settings_toggle.set_icon_name("go-previous-symbolic")', source)

    def test_native_window_uses_the_sentry_icon_theme_name(self):
        from tools.sentry_ui import build_application

        source = inspect.getsource(build_application)
        self.assertIn('self.set_icon_name("sentry")', source)
        self.assertIn('application_id="local.sentry.Control"', source)

    def test_settings_include_voice_selection_speed_preview_and_apply(self):
        from tools.sentry_ui import build_application

        source = inspect.getsource(build_application)
        self.assertIn("Gtk.ComboBoxText", source)
        self.assertIn("Gtk.Scale.new_with_range", source)
        self.assertIn('label="Preview voice"', source)
        self.assertIn('label="Save and apply"', source)

    def test_settings_put_persistent_sleep_toggle_before_voice_controls(self):
        from tools.sentry_ui import build_application

        source = inspect.getsource(build_application)
        self.assertIn("Gtk.Switch", source)
        self.assertLess(source.index('self._card("Sleep")'), source.index('self._card("Voice")'))
        self.assertIn("apply_sleep_preference(config_path, enabled)", source)


if __name__ == "__main__":
    unittest.main()
