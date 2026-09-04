import json
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp import Client

from tools.sentry_codex_profile import constrain_generated_images, install, profile_text
from tools.sentry_execution_authority import ExecutionAuthority
from tools.sentry_execution_authority import RISK_TIERS
from tools.sentry_mcp_server import mcp
from tools.sentry_office_vision import inspect_wake_speaker_context


class SentryMCPTests(unittest.IsolatedAsyncioTestCase):
    def test_automatic_wake_identity_path_requests_metadata_only(self):
        metadata = {
            "observed_at": "2026-09-02T22:14:00+00:00",
            "people": [],
            "frames_persisted": False,
        }
        with patch("tools.sentry_office_vision.inspect_office_camera", return_value=(metadata, None)) as inspect:
            result = inspect_wake_speaker_context(Path("config.json"), duration_seconds=3.0, completion_timeout_seconds=5.0)
        inspect.assert_called_once_with(
            Path("config.json"), duration_seconds=3.0,
            include_image=False, completion_timeout_seconds=5.0,
        )
        self.assertFalse(result["image_shared_with_codex"])
        self.assertFalse(result["frames_persisted"])

    def test_automatic_wake_identity_rejects_unexpected_image_bytes(self):
        with patch("tools.sentry_office_vision.inspect_office_camera", return_value=({}, b"jpeg")):
            with self.assertRaises(RuntimeError):
                inspect_wake_speaker_context(Path("config.json"))

    def test_profile_install_reads_private_memory_vault_from_local_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            python = root / "python"
            python.write_text("", encoding="utf-8")
            vault = root / "private-memory-vault"
            config = root / "config.json"
            config.write_text(json.dumps({"agent": {"memory_vault_path": str(vault)}}), encoding="utf-8")
            result = install(
                codex_home=root / "codex-home",
                python_executable=python,
                config_path=config,
                workspace_path=root / "workspace",
                authority_root=root / "authority",
            )
            profile = (root / "codex-home" / "sentry-resident.config.toml").read_text(encoding="utf-8")

        self.assertEqual(result["memory_vault_denied"], str(vault.resolve()))
        self.assertIn(f'"{vault.resolve()}" = "deny"', profile)

    async def test_server_exposes_office_vision_and_desktop_tools(self):
        async with Client(mcp) as client:
            result = await client.list_tools()
        names = {tool.name for tool in result.tools}
        self.assertEqual(len(names), 33)
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
            "propose_file_move",
            "get_execution_authority_status",
            "get_recent_execution_audit",
            "get_pending_authorization",
        }.issubset(names))
        self.assertEqual(names, set(RISK_TIERS))
        by_name = {tool.name: tool for tool in result.tools}
        # These cancellations are host-governed Tier-1 mutations. Marking them
        # destructive would make Codex's approval layer reject them before the
        # SENTRY authority broker can enforce and audit the direct request.
        self.assertFalse(by_name["cancel_alarm"].annotations.destructive_hint)
        self.assertFalse(by_name["cancel_pending_office_reminder"].annotations.destructive_hint)
        self.assertFalse(by_name["open_web_page"].annotations.open_world_hint)

    async def test_camera_tool_returns_metadata_and_ephemeral_image(self):
        metadata = {"status": "observed", "people": [{"person_id": "primary_user"}], "frames_persisted": False}
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {
            "SENTRY_REQUEST_ID": "request-1", "SENTRY_THREAD_ID": "thread-1",
            "SENTRY_OPERATOR_REQUEST": "Sentry, inspect the office camera", "SENTRY_AUTHORITY_EPOCH": "epoch-1",
        }, clear=False), patch("tools.sentry_mcp_server.AUTHORITY", ExecutionAuthority(Path(tmp) / "authority", workspace=Path(tmp) / "workspace")), patch(
            "tools.sentry_mcp_server._inspect_office_camera", return_value=(metadata, b"jpeg-bytes")
        ):
            async with Client(mcp) as client:
                result = await client.call_tool("inspect_office_camera", {"duration_seconds": 1.0})
        self.assertFalse(result.is_error)
        self.assertEqual(json.loads(result.content[0].text), metadata)
        self.assertEqual(result.content[1].mime_type, "image/jpeg")

    async def test_file_move_executes_direct_current_request_without_confirmation(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            source = workspace / "fixture.txt"
            source.write_text("fixture", encoding="utf-8")
            destination = root / "Downloads" / "direct dash result"
            authority = ExecutionAuthority(root / "authority", workspace=workspace)
            with patch.dict("os.environ", {
                "SENTRY_REQUEST_ID": "request-1", "SENTRY_THREAD_ID": "thread-1",
                "SENTRY_OPERATOR_REQUEST": "Move the fixture file into Downloads as direct dash result",
                "SENTRY_AUTHORITY_EPOCH": "epoch-1",
            }, clear=False), patch("tools.sentry_mcp_server.AUTHORITY", authority):
                async with Client(mcp) as client:
                    response = await client.call_tool(
                        "propose_file_move",
                        {"source": str(source), "destination": str(destination)},
                    )
            result = json.loads(response.content[0].text)
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["authority_source"], "direct_current_turn")
            self.assertFalse(source.exists())
            self.assertEqual((root / "Downloads" / "direct-result.txt").read_text(encoding="utf-8"), "fixture")

    async def test_file_move_defers_only_when_operator_explicitly_requests_it(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            source = workspace / "fixture.txt"
            source.write_text("fixture", encoding="utf-8")
            destination = root / "Downloads" / "deferred result.txt"
            authority = ExecutionAuthority(root / "authority", workspace=workspace)
            with patch.dict("os.environ", {
                "SENTRY_REQUEST_ID": "request-1", "SENTRY_THREAD_ID": "thread-1",
                "SENTRY_OPERATOR_REQUEST": "Move the fixture file, but do not make the move until I explicitly confirm it",
                "SENTRY_AUTHORITY_EPOCH": "epoch-1",
            }, clear=False), patch("tools.sentry_mcp_server.AUTHORITY", authority):
                async with Client(mcp) as client:
                    response = await client.call_tool(
                        "propose_file_move",
                        {"source": str(source), "destination": str(destination)},
                    )
            result = json.loads(response.content[0].text)
            self.assertEqual(result["status"], "DRAFTED")
            self.assertTrue(source.exists())
            self.assertFalse(destination.exists())

    def test_profile_enables_restricted_codex_surface_and_local_mcp(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_vault = Path(tmp, "private-memory-vault")
            text = profile_text(
                python_executable=Path(tmp, "python"), config_path=Path(tmp, "config.json"),
                memory_vault_path=memory_vault, resident_codex_home=Path(tmp, "codex-home"),
            )
        self.assertNotIn("sandbox_mode", text)
        self.assertIn('approval_policy = "never"', text)
        self.assertIn('default_permissions = "sentry-resident"', text)
        self.assertIn('extends = ":workspace"', text)
        self.assertIn('"." = "write"', text)
        self.assertIn('":minimal" = "read"', text)
        self.assertIn("enabled = false", text)
        self.assertIn("model_auto_compact_token_limit = 217600", text)
        self.assertIn("browser_use = false", text)
        self.assertIn("computer_use = false", text)
        self.assertIn("plugins = false", text)
        self.assertIn("memories = false", text)
        self.assertIn("image_generation = true", text)
        self.assertIn("[mcp_servers.sentry_office]", text)
        self.assertIn('env_vars = ["SENTRY_REQUEST_ID", "SENTRY_THREAD_ID", "SENTRY_OPERATOR_REQUEST", "SENTRY_AUTHORITY_EPOCH"]', text)
        self.assertIn(f'{json.dumps(str(memory_vault.resolve()))} = "deny"', text)
        self.assertIn(f'{json.dumps(str(Path(tmp, "codex-home").resolve()))} = "deny"', text)
        parsed = tomllib.loads(text)
        self.assertEqual(set(parsed["mcp_servers"]), {"sentry_office"})

    def test_profile_denies_sensitive_host_aliases_and_native_bypass_surfaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = Path.home().resolve()
            resident = root / "codex-home"
            authority = root / "authority"
            vault = root / "obsidian-vault"
            text = profile_text(
                python_executable=root / "python", config_path=root / "config.json",
                workspace_path=root / "workspace", authority_root=authority,
                memory_vault_path=vault, resident_codex_home=resident,
            )
            parsed = tomllib.loads(text)
        profile = parsed["permissions"]["sentry-resident"]
        filesystem = profile["filesystem"]
        for denied in (
            home / ".ssh", home / ".gnupg", home / ".config/gh",
            home / ".config/chromium", home / ".mozilla",
            home / ".config/sentry", home / ".codex/auth.json",
            authority.resolve(), resident.resolve(), vault.resolve(),
        ):
            with self.subTest(path=str(denied)):
                self.assertEqual(filesystem[str(denied)], "deny")
        self.assertFalse(profile["network"]["enabled"])
        self.assertFalse(parsed["features"]["apps"])
        self.assertFalse(parsed["features"]["plugins"])
        self.assertFalse(parsed["features"]["browser_use"])
        self.assertFalse(parsed["features"]["browser_use_external"])
        self.assertFalse(parsed["features"]["browser_use_full_cdp_access"])
        self.assertFalse(parsed["features"]["computer_use"])
        self.assertFalse(parsed["features"]["memories"])
        self.assertFalse(parsed["memories"]["generate_memories"])
        self.assertFalse(parsed["memories"]["use_memories"])

    def test_profile_install_is_private_and_parseable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            python = root / "python"
            config = root / "config.json"
            python.write_text("", encoding="utf-8")
            config.write_text("{}", encoding="utf-8")
            development = root / "codex" / "sentry.config.toml"
            development.parent.mkdir(parents=True)
            development.write_text("sandbox_mode='danger-full-access'\n", encoding="utf-8")
            result = install(
                codex_home=root / "codex", python_executable=python, config_path=config,
                workspace_path=root / "workspace", authority_root=root / "authority",
            )
            installed = Path(result["path"])
            self.assertEqual(installed.stat().st_mode & 0o777, 0o600)
            self.assertNotIn("{}", installed.read_text(encoding="utf-8"))
            self.assertIn(str(python.absolute()), installed.read_text(encoding="utf-8"))
            self.assertTrue(result["development_profile_preserved"])
            self.assertIn("danger-full-access", development.read_text(encoding="utf-8"))

    def test_generated_image_staging_is_migrated_into_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resident = root / "codex-home"
            source = resident / "generated_images" / "thread"
            source.mkdir(parents=True)
            (source / "image.png").write_bytes(b"png")
            workspace = root / "workspace"
            result = constrain_generated_images(resident_codex_home=resident, workspace_path=workspace)
            self.assertTrue(result["image_output_constrained"])
            self.assertTrue((workspace / ".codex-generated-images" / "thread" / "image.png").is_file())
            self.assertTrue((resident / "generated_images").is_symlink())
            self.assertEqual((resident / "generated_images").resolve(), (workspace / ".codex-generated-images").resolve())


if __name__ == "__main__":
    unittest.main()
