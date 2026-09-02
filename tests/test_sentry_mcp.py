import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp import Client

from tools.sentry_codex_profile import install, profile_text
from tools.sentry_mcp_server import mcp


class SentryMCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_server_exposes_office_vision_and_desktop_tools(self):
        async with Client(mcp) as client:
            result = await client.list_tools()
        names = {tool.name for tool in result.tools}
        self.assertEqual(len(names), 29)
        self.assertTrue({
            "get_current_office_state",
            "inspect_office_camera",
            "find_applications",
            "open_web_page",
            "get_system_volume",
            "capture_desktop",
            "open_local_artifact",
            "get_alarms",
            "create_one_shot_alarm",
            "cancel_alarm",
        }.issubset(names))

    async def test_camera_tool_returns_metadata_and_ephemeral_image(self):
        metadata = {"status": "observed", "people": [{"person_id": "primary_user"}], "frames_persisted": False}
        with patch("tools.sentry_mcp_server._inspect_office_camera", return_value=(metadata, b"jpeg-bytes")):
            async with Client(mcp) as client:
                result = await client.call_tool("inspect_office_camera", {"duration_seconds": 1.0})
        self.assertFalse(result.is_error)
        self.assertEqual(json.loads(result.content[0].text), metadata)
        self.assertEqual(result.content[1].mime_type, "image/jpeg")

    def test_profile_enables_full_codex_surface_and_local_mcp(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = profile_text(python_executable=Path(tmp, "python"), config_path=Path(tmp, "config.json"))
        self.assertIn('sandbox_mode = "danger-full-access"', text)
        self.assertIn('approval_policy = "never"', text)
        self.assertIn("model_auto_compact_token_limit = 217600", text)
        self.assertIn("browser_use = true", text)
        self.assertIn("computer_use = true", text)
        self.assertIn("image_generation = true", text)
        self.assertIn("[mcp_servers.sentry_office]", text)

    def test_profile_install_is_private_and_parseable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            python = root / "python"
            config = root / "config.json"
            python.write_text("", encoding="utf-8")
            config.write_text("{}", encoding="utf-8")
            result = install(codex_home=root / "codex", python_executable=python, config_path=config)
            installed = Path(result["path"])
            self.assertEqual(installed.stat().st_mode & 0o777, 0o600)
            self.assertNotIn("{}", installed.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
