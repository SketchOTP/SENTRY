import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tools import sentry_desktop


class SentryDesktopTests(unittest.TestCase):
    def test_find_applications_returns_exact_desktop_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "ted-editor.desktop")
            path.write_text(
                "[Desktop Entry]\nType=Application\nName=Ted Editor\nComment=Edit text\nExec=ted\n",
                encoding="utf-8",
            )
            with patch.object(sentry_desktop, "APPLICATION_DIRS", (Path(tmp),)):
                result = sentry_desktop.find_applications("ted")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["applications"][0]["app_id"], "ted-editor")

    def test_volume_is_bounded_and_parsed(self):
        calls = []

        def run(args, **_kwargs):
            calls.append(args)
            if args[1] == "get-volume":
                return SimpleNamespace(returncode=0, stdout="Volume: 0.42\n", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with patch("tools.sentry_desktop._run", side_effect=run):
            self.assertEqual(sentry_desktop.set_volume(42), {"percent": 42.0, "muted": False})
        self.assertEqual(calls[0][-1], "0.4200")
        with self.assertRaises(ValueError):
            sentry_desktop.set_volume(151)

    def test_gui_actions_validate_targets(self):
        completed = SimpleNamespace(returncode=0, stdout="", stderr="")
        with patch("tools.sentry_desktop._run", return_value=completed) as run:
            sentry_desktop.send_key_combo("ctrl+alt+t")
            sentry_desktop.type_text("hello")
            sentry_desktop.click_pointer(10, 20)
        self.assertEqual(run.call_count, 3)
        with self.assertRaises(ValueError):
            sentry_desktop.click_pointer(-1, 20)

    def test_open_web_page_accepts_only_explicit_http_urls(self):
        with patch("tools.sentry_desktop.subprocess.Popen", return_value=SimpleNamespace(pid=42)) as popen:
            result = sentry_desktop.open_web_page("https://developers.openai.com/codex/")
        self.assertTrue(result["opened"])
        self.assertEqual(popen.call_args.args[0][0], "xdg-open")
        with self.assertRaises(ValueError):
            sentry_desktop.open_web_page("file:///etc/passwd")

    def test_open_local_artifact_is_existing_operator_home_file(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as tmp:
            artifact = Path(tmp, "result.png")
            artifact.write_bytes(b"png")
            with patch("tools.sentry_desktop.subprocess.Popen", return_value=SimpleNamespace(pid=43)) as popen:
                result = sentry_desktop.open_local_artifact(str(artifact))
            self.assertEqual(result["path"], str(artifact.resolve()))
            self.assertEqual(popen.call_args.args[0][0], "xdg-open")
        with self.assertRaises(ValueError):
            sentry_desktop.open_local_artifact("/etc/passwd")


if __name__ == "__main__":
    unittest.main()
