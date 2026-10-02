import ast
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tools import sentry_ui, sentry_voice_supervisor

from tools.sentry_install_user_services import (
    ALARM_UNIT_NAMES,
    APPLICATION_DESKTOP_NAME,
    LEGACY_UI_UNIT_NAMES,
    ROUTINE_UNIT_NAMES,
    UNIT_NAMES,
    VOICE_UNIT_NAMES,
    WEATHER_UNIT_NAMES,
    _continuous_perception_enabled,
    _continuous_proactivity_enabled,
    install,
    production_config,
)
from tools.sentry_proactive import watch_loop
from tools.sentry_resident_live_probe import _unit_states


def native_window_method(name):
    """Execute the actual nested GTK method headlessly, not a copy of its logic."""
    tree = ast.parse(Path("tools/sentry_ui.py").read_text(encoding="utf-8"))
    window = next(node for node in ast.walk(tree) if isinstance(node, ast.ClassDef) and node.name == "SentryWindow")
    method = next(node for node in window.body if isinstance(node, ast.FunctionDef) and node.name == name)
    module = ast.Module(body=[method], type_ignores=[])
    namespace = dict(vars(sentry_ui))
    return module, namespace


class _FakeProcessor:
    def __init__(self, stop_event: threading.Event):
        self.calls = 0
        self.stop_event = stop_event

    def process_pending(self):
        self.calls += 1
        if self.calls == 2:
            self.stop_event.set()
        return []


class ResidentRuntimeTests(unittest.TestCase):
    def test_watch_loop_is_bounded_and_stops_cleanly(self):
        stop_event = threading.Event()
        processor = _FakeProcessor(stop_event)
        started = time.monotonic()
        self.assertEqual(watch_loop(processor, 0.03, stop_event), 0)
        elapsed = time.monotonic() - started
        self.assertEqual(processor.calls, 2)
        self.assertGreaterEqual(elapsed, 0.02)

    def test_watch_loop_rejects_hot_loop_interval(self):
        with self.assertRaises(ValueError):
            watch_loop(_FakeProcessor(threading.Event()), 0, threading.Event())

    def test_production_config_enables_proactive_runtime_without_model_changes(self):
        source = production_config(Path("perception/config.example.json"))
        self.assertTrue(source["proactivity"]["enabled"])
        self.assertEqual(source["detector"]["name"], "openvino_yolox_s")
        self.assertEqual(source["detector"]["device"], "CPU")
        self.assertFalse(_continuous_perception_enabled(source))
        self.assertFalse(_continuous_proactivity_enabled(source))

    def test_resident_camera_and_proactivity_require_explicit_service_opt_in(self):
        config = production_config(Path("perception/config.example.json"))
        config["resident"]["continuous_perception_enabled"] = True
        config["resident"]["continuous_proactivity_enabled"] = True
        self.assertTrue(_continuous_perception_enabled(config))
        self.assertTrue(_continuous_proactivity_enabled(config))

    def test_install_preserves_existing_production_config(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config.json"
            custom = production_config(Path("perception/config.example.json"))
            custom["proactivity"]["judge_effort"] = "none"
            config.write_text(json.dumps(custom), encoding="utf-8")
            units = root / "units"
            with patch("tools.sentry_install_user_services._run_systemctl"):
                install(config, start=False, systemd_user_dir=units)
            self.assertEqual(json.loads(config.read_text(encoding="utf-8")), custom)
            self.assertEqual(sorted(path.name for path in units.iterdir()), sorted((*UNIT_NAMES, *ROUTINE_UNIT_NAMES, *WEATHER_UNIT_NAMES, *VOICE_UNIT_NAMES, *ALARM_UNIT_NAMES)))
            self.assertTrue((root / "applications" / APPLICATION_DESKTOP_NAME).is_file())
            self.assertFalse((root / "applications" / "sentry-ui.desktop").exists())
            self.assertFalse((root / "applications" / "sentry-identity-ui.desktop").exists())
            installed_icon = root / "icons" / "hicolor" / "512x512" / "apps" / "sentry.png"
            self.assertTrue(installed_icon.is_file())
            self.assertEqual(installed_icon.read_bytes(), Path("deploy/icons/hicolor/512x512/apps/sentry.png").read_bytes())
            desktop_launcher = root / "Desktop" / "SENTRY.desktop"
            self.assertTrue(desktop_launcher.is_file())
            self.assertEqual(desktop_launcher.stat().st_mode & 0o777, 0o755)

    def test_install_removes_legacy_ui_units_and_launcher(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config.json"
            config.write_text(json.dumps(production_config(Path("perception/config.example.json"))), encoding="utf-8")
            units = root / "units"
            units.mkdir()
            applications = root / "applications"
            applications.mkdir()
            for name in LEGACY_UI_UNIT_NAMES:
                (units / name).write_text("legacy", encoding="utf-8")
            (applications / "sentry-identity-ui.desktop").write_text("legacy", encoding="utf-8")
            (applications / "sentry-ui.desktop").write_text("legacy", encoding="utf-8")
            with patch("tools.sentry_install_user_services._run_systemctl") as systemctl:
                install(config, start=False, systemd_user_dir=units)
            for name in LEGACY_UI_UNIT_NAMES:
                self.assertFalse((units / name).exists())
                systemctl.assert_any_call("disable", "--now", name)
            self.assertFalse((applications / "sentry-identity-ui.desktop").exists())
            self.assertFalse((applications / "sentry-ui.desktop").exists())
            self.assertTrue((applications / APPLICATION_DESKTOP_NAME).is_file())

    def test_install_renders_relocated_repo_in_units_and_both_launchers(self):
        source_root = Path(__file__).resolve().parents[1]
        names = (*UNIT_NAMES, *ROUTINE_UNIT_NAMES, *WEATHER_UNIT_NAMES, *VOICE_UNIT_NAMES, *ALARM_UNIT_NAMES)
        templates = {
            name: (source_root / "deploy/systemd/user" / name).read_text(encoding="utf-8")
            for name in names
        }
        desktop = (source_root / "deploy/applications/sentry-ui.desktop").read_text(encoding="utf-8")
        legacy = "/srv/ATLAS/100_ACTIVE/Projects/SENTRY"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            relocated = root / "local-checkout"
            launcher_source = relocated / "deploy/applications/sentry-ui.desktop"
            launcher_source.parent.mkdir(parents=True)
            launcher_source.write_text(desktop, encoding="utf-8")
            config = root / "config.json"
            config_bytes = b'{"voice": {"always_on_enabled": false}, "custom": "preserved"}\n'
            config.write_bytes(config_bytes)
            config.chmod(0o600)
            units = root / "units"
            with (
                patch("tools.sentry_install_user_services.REPO_ROOT", relocated),
                patch("tools.sentry_install_user_services._run_systemctl"),
                patch("tools.sentry_install_user_services.shutil.which", return_value=None),
            ):
                install(config, start=False, systemd_user_dir=units)
            for name, template in templates.items():
                self.assertEqual(
                    (units / name).read_text(encoding="utf-8"),
                    template.replace(legacy, str(relocated)),
                    name,
                )
                self.assertEqual(
                    (source_root / "deploy/systemd/user" / name).read_text(encoding="utf-8"),
                    template,
                )
            for launcher in (
                root / "applications" / APPLICATION_DESKTOP_NAME,
                root / "Desktop/SENTRY.desktop",
            ):
                self.assertEqual(
                    launcher.read_text(encoding="utf-8"), desktop.replace(legacy, str(relocated))
                )
            self.assertEqual(launcher_source.read_text(encoding="utf-8"), desktop)
            self.assertEqual((root / "Desktop/SENTRY.desktop").stat().st_mode & 0o777, 0o755)
            self.assertEqual(config.read_bytes(), config_bytes)
            self.assertEqual(config.stat().st_mode & 0o777, 0o600)

    def test_units_use_accepted_paths_and_isolated_services(self):
        unit_root = Path("deploy/systemd/user")
        perception = (unit_root / "sentry-perception.service").read_text(encoding="utf-8")
        api = (unit_root / "sentry-state-api.service").read_text(encoding="utf-8")
        proactive = (unit_root / "sentry-proactive.service").read_text(encoding="utf-8")
        routines = (unit_root / "sentry-routines.timer").read_text(encoding="utf-8")
        weather = (unit_root / "sentry-weather.timer").read_text(encoding="utf-8")
        voice = (unit_root / "sentry-voice.service").read_text(encoding="utf-8")
        sentry_ui = (unit_root / "sentry-ui.service").read_text(encoding="utf-8")
        self.assertIn("Environment=GSK_RENDERER=gl", sentry_ui)
        self.assertIn("Environment=GDK_DEBUG=gl-prefer-gl:gl-glx", sentry_ui)
        alarms = (unit_root / "sentry-alarms.timer").read_text(encoding="utf-8")
        self.assertIn("WorkingDirectory=/srv/ATLAS/100_ACTIVE/Projects/SENTRY", perception)
        self.assertIn("--config %h/.config/sentry/config.json", perception)
        self.assertIn("--heartbeat-file /srv/ATLAS/100_ACTIVE/Projects/SENTRY/perception-data/runtime/health/perception.json", perception)
        self.assertIn("127.0.0.1", api)
        self.assertIn("%h/.local/share/sentry/sentry.db", api)
        self.assertIn("--watch --poll-seconds 1", proactive)
        for unit in (perception, api, proactive):
            self.assertIn("Restart=on-failure", unit)
            self.assertIn("RestartSec=10s", unit)
        self.assertNotIn("old", perception.lower())
        self.assertIn("OnBootSec=2min", routines)
        self.assertIn("OnUnitActiveSec=6h", routines)
        self.assertIn("OnBootSec=5min", weather)
        self.assertIn("OnUnitActiveSec=10min", weather)
        self.assertIn("tools/sentry_always_on_voice.py", voice)
        self.assertIn("Environment=SENTRY_CODEX_HOME=%h/.local/share/sentry/codex-home", voice)
        self.assertIn("Environment=SENTRY_CODEX_EXECUTABLE=/srv/ATLAS/100_ACTIVE/Projects/SENTRY/tools/sentry_codex_launcher.sh", voice)
        self.assertNotIn("Environment=CODEX_HOME=%h/.codex", voice)
        launcher = Path("tools/sentry_codex_launcher.sh").read_text(encoding="utf-8")
        self.assertIn("/usr/bin/aa-exec -p chatgpt", launcher)
        self.assertIn("/usr/lib/chatgpt/resources/codex", launcher)
        self.assertNotIn("Wants=sentry-ui.service", voice)
        self.assertIn("tools/sentry_ui.py", sentry_ui)
        self.assertNotIn("zenity", sentry_ui.lower())
        self.assertNotIn("PartOf=sentry-voice.service", sentry_ui)
        self.assertIn("After=graphical-session.target", sentry_ui)
        self.assertIn("EnvironmentFile=-%h/.config/sentry/ui-display.env", sentry_ui)
        desktop = Path("deploy/applications/sentry-ui.desktop").read_text(encoding="utf-8")
        self.assertIn("Name=SENTRY", desktop)
        self.assertIn("Icon=sentry", desktop)
        self.assertNotIn("Icon=audio-input-microphone", desktop)
        self.assertIn("StartupWMClass=sentry_ui.py", desktop)
        self.assertIn("Actions=LaunchMain;LaunchRTX;", desktop)
        self.assertIn("Name=Launch on Main Displays", desktop)
        self.assertIn("Name=Launch on RTX Display", desktop)
        self.assertIn("--display main", desktop)
        self.assertIn("--display rtx", desktop)
        self.assertIn("tools/sentry_open_identity_ui.sh", desktop)
        launcher = Path("tools/sentry_open_identity_ui.sh").read_text(encoding="utf-8")
        self.assertIn('"$SENTRY_LAUNCH_DIR/sentry_launch.py"', launcher)
        self.assertIn('"$@"', launcher)
        self.assertIn("Restart=on-failure", voice)
        voice_launcher = Path("tools/sentry_always_on_voice.py").read_text(encoding="utf-8")
        self.assertIn('"sentry" / "speaker-context.json"', voice_launcher)
        self.assertIn("cache_path=", voice_launcher)
        self.assertIn("OnUnitActiveSec=15s", alarms)
        self.assertIn("Persistent=true", alarms)
        native_ui = Path("tools/sentry_ui.py").read_text(encoding="utf-8")
        self.assertIn("Gtk.Application", native_ui)
        self._assert_native_faces_have_no_local_voice_or_identity_controls()
        self.assertIn("orb_stack.set_child(self.status_orb)", native_ui)
        self.assertNotIn("ThreadingHTTPServer", native_ui)

    def _assert_native_faces_have_no_local_voice_or_identity_controls(self):
        for projection_mode in (False, True):
            with self.subTest(projection_mode=projection_mode):
                module, namespace = native_window_method("_build")
                # Only display widgets are available. Reaching legacy local
                # settings/enrollment construction raises AttributeError.
                gtk = SimpleNamespace(**{name: Mock() for name in (
                    "CssProvider", "StyleContext", "Overlay", "Box", "DrawingArea", "Label",
                )}, Orientation=SimpleNamespace(VERTICAL=1),
                    Align=SimpleNamespace(CENTER=1), STYLE_PROVIDER_PRIORITY_APPLICATION=1)
                namespace.update(Gtk=gtk, Gdk=Mock(), StatusOrb=Mock())
                exec(compile(module, "tools/sentry_ui.py", "exec"), namespace)
                window = SimpleNamespace(projection_mode=projection_mode,
                    _draw_projection_fallback=Mock(), _show_projection_fallback=Mock(),
                    _build_sensor_drawer=Mock(), set_child=Mock(), fullscreen=Mock())
                namespace["_build"](window)
                window.set_child.assert_called_once()
                if projection_mode:
                    window.fullscreen.assert_called_once()
                    window._build_sensor_drawer.assert_not_called()
                else:
                    window._build_sensor_drawer.assert_called_once()
                    window.fullscreen.assert_not_called()
                for local_control in ("voice_combo", "speed_scale", "sleep_switch", "manager", "profile_list"):
                    self.assertFalse(hasattr(window, local_control), local_control)

    def test_native_faces_consume_anima_intent_without_local_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            voice_path = Path(directory) / "voice.json"
            config = Mock()
            client = config.client.return_value
            for instance, sleep in (("office", False), ("living_room", True)):
                with self.subTest(instance=instance, sleep=sleep):
                    client.voice_settings.return_value = {
                        "active_instance_id": instance, "sleep_enabled": sleep,
                        "voice_id": "fixture", "speech_speed": 1.0,
                    }
                    with patch.object(sentry_voice_supervisor.AnimaConfig, "load", return_value=config), \
                            patch.object(sentry_voice_supervisor, "voice_is_active", return_value=False), \
                            patch.object(sentry_voice_supervisor, "_systemctl", return_value=SimpleNamespace(returncode=0)), \
                            patch.object(sentry_voice_supervisor, "reconcile_visible_face", return_value="face_ready"):
                        sentry_voice_supervisor.reconcile_once(publish=lambda value:
                            sentry_voice_supervisor.publish_desired_status(value, voice_path.with_name("voice-supervisor.json")))
                    payload = sentry_ui.read_voice_status(voice_path)
                    # Missing observed voice remains unavailable, even when
                    # canonical intent is awake; intent comes from ANIMA only.
                    self.assertEqual(payload["state"], "UNAVAILABLE")
                    self.assertEqual(payload["desired_sleep_enabled"], sleep)
                    self.assertEqual(payload["desired_instance_id"], instance)
                    for projection_mode in (False, True):
                        module, namespace = native_window_method("_refresh_status")
                        namespace["read_voice_status"] = lambda: payload
                        exec(compile(module, "tools/sentry_ui.py", "exec"), namespace)
                        window = SimpleNamespace(projection_mode=projection_mode,
                            sleep_enabled=not sleep, _last_wake_at=None, _status_initialized=False,
                            status_orb=Mock(), projection_fallback_orb=Mock(), state_label=Mock())
                        window.projection_fallback_orb.get_visible.return_value = False
                        self.assertTrue(namespace["_refresh_status"](window))
                        self.assertEqual(window.sleep_enabled, sleep)
                        self.assertEqual(window.status_orb.present.call_args.args[0], payload)
            self.assertEqual(client.voice_settings.call_count, 2)

    def test_live_probe_uses_user_systemd_and_localhost_api(self):
        self.assertEqual(_unit_states.__module__, "tools.sentry_resident_live_probe")
        source = Path("tools/sentry_resident_live_probe.py").read_text(encoding="utf-8")
        self.assertIn("systemctl", source)
        self.assertIn("--user", source)
        self.assertIn('urlopen(f"{base_url}/health"', source)


if __name__ == "__main__":
    unittest.main()
