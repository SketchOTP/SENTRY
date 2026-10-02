import tempfile
import unittest
from pathlib import Path

from tools.sentry_install_stage1 import deployment_files, install_files


class Stage1DeploymentTests(unittest.TestCase):
    def test_units_render_local_paths_and_optional_core_dependency_without_tooling(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            files = deployment_files(home, anima_core=True)
            self.assertEqual(len(files), 12)
            for content in files.values():
                self.assertNotIn(b"After=default.target", content)
                self.assertNotIn(b"/srv/ATLAS/100_ACTIVE/Projects/SENTRY", content)
                self.assertNotIn(b"graft", content)
            install_files(files)
            self.assertTrue(all(path.read_bytes() == content for path, content in files.items()))
            self.assertFalse(any("20-anima-core" in str(path) for path in deployment_files(home)))

    def test_existing_dropin_and_config_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            dropin = home / ".config/systemd/user/sentry-voice.service.d/10-atlas-storage.conf"
            dropin.parent.mkdir(parents=True)
            dropin.write_text("preserve-owner-dropin")
            config = home / ".config/sentry/config.json"
            config.parent.mkdir(parents=True)
            config.write_text("preserve-owner-config")
            install_files(deployment_files(home, anima_core=True))
            self.assertEqual(dropin.read_text(), "preserve-owner-dropin")
            self.assertEqual(config.read_text(), "preserve-owner-config")

    def test_symlink_preflight_refuses_redirect(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target"
            target.write_text("preserved")
            link = root / "link"
            link.symlink_to(target)
            with self.assertRaises(ValueError):
                install_files({root / "first": b"new", link: b"bad"})
            self.assertFalse((root / "first").exists())
            self.assertEqual(target.read_text(), "preserved")
