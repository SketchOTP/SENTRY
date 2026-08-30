import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.sentry_install_user_services import ROUTINE_UNIT_NAMES, UNIT_NAMES, install, production_config
from tools.sentry_proactive import watch_loop
from tools.sentry_resident_live_probe import _unit_states


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
            self.assertEqual(sorted(path.name for path in units.iterdir()), sorted((*UNIT_NAMES, *ROUTINE_UNIT_NAMES)))

    def test_units_use_accepted_paths_and_isolated_services(self):
        unit_root = Path("deploy/systemd/user")
        perception = (unit_root / "sentry-perception.service").read_text(encoding="utf-8")
        api = (unit_root / "sentry-state-api.service").read_text(encoding="utf-8")
        proactive = (unit_root / "sentry-proactive.service").read_text(encoding="utf-8")
        routines = (unit_root / "sentry-routines.timer").read_text(encoding="utf-8")
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

    def test_live_probe_uses_user_systemd_and_localhost_api(self):
        self.assertEqual(_unit_states.__module__, "tools.sentry_resident_live_probe")
        source = Path("tools/sentry_resident_live_probe.py").read_text(encoding="utf-8")
        self.assertIn("systemctl", source)
        self.assertIn("--user", source)
        self.assertIn('urlopen(f"{base_url}/health"', source)


if __name__ == "__main__":
    unittest.main()
