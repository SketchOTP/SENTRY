"""Scripted, temporary callers only; no model/media or owner state."""
import json
import os
import tempfile
import unittest
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import Mock, patch

from tools.sentry_anima import intended_scope
from tools.sentry_codex_agent import CodexNativeAgent, CodexSessionStore
from tools.sentry_execution_authority import ExecutionAuthority, RequestContext
from tools.sentry_state_api import execute_audio


class ScopeTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="stage9-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        env = patch.dict(os.environ, {
            "HOME": str(self.root), "SENTRY_AUTHORITY_ROOT": str(self.root / "authority"),
            "SENTRY_AGENT_WORKSPACE": str(self.workspace), "XDG_STATE_HOME": str(self.root / "state"),
            "CODEX_HOME": str(self.root / "codex"), "SENTRY_ANIMA_CONFIG": str(self.root / "anima.json"),
        }, clear=True)
        env.start()
        self.addCleanup(env.stop)
        self.authority = ExecutionAuthority(self.root / "authority", workspace=self.workspace)

    def test_explicit_scope_not_absence(self):
        self.assertEqual(intended_scope("always_on_voice"), "HOUSEHOLD")
        path = self.root / "anima.json"
        path.write_text(json.dumps({"enabled": False}))
        path.chmod(0o600)
        self.assertEqual(intended_scope("always_on_voice"), "STANDALONE")
        self.assertEqual(intended_scope("sensor"), "HOUSEHOLD")

    def test_household_does_not_query_office_pending(self):
        invoker = Mock(return_value={"ok": False, "error": {"message": "synthetic"}})
        agent = CodexNativeAgent(session_store=CodexSessionStore(self.root / "session.json"), authority=self.authority, invoker=invoker)
        with patch.object(self.authority, "pending_status", side_effect=AssertionError("Office pending touched")):
            agent.ask("yes", source_surface="always_on_voice")
        self.assertEqual(invoker.call_args.kwargs["host_scope"], "HOUSEHOLD")
        self.assertEqual(agent.session_store.load()["host_scope"], "HOUSEHOLD")

    def test_legacy_history_preserved_and_office_unavailable(self):
        store = CodexSessionStore(self.root / "session.json")
        store.save({"thread_id": "a1111111-1111-4111-8111-111111111111", "turn_count": 7})
        before = store.path.read_bytes()
        invoker = Mock()
        agent = CodexNativeAgent(session_store=store, authority=self.authority, invoker=invoker)
        result = agent.ask("open an application")
        invoker.assert_not_called()
        self.assertEqual(result["security_handler"], "standalone_history_not_eligible")
        self.assertEqual(store.path.read_bytes(), before)

    def test_household_host_executor_denied(self):
        context = RequestContext("request", "thread", "set the volume to 50", "epoch", "HOUSEHOLD")
        executor = Mock()
        with self.assertRaises(PermissionError):
            self.authority.execute_tier1("set_system_volume", {"percent": 50}, "volume", executor, context=context)
        executor.assert_not_called()

    def test_raw_office_read_and_enrollment_denied(self):
        from tools import sentry_mcp_server as m
        with patch.dict(os.environ, {"SENTRY_REQUEST_ID": "req", "SENTRY_THREAD_ID": "thread", "SENTRY_OPERATOR_REQUEST": "volume", "SENTRY_AUTHORITY_EPOCH": "epoch", "SENTRY_HOST_SCOPE": "HOUSEHOLD"}):
            with patch.object(m, "_get_volume") as volume, patch.object(m, "_enrollment_manager") as manager:
                for function, args in ((m.get_system_volume, ()), (m.start_identity_onboarding, ("Person", "uuid"))):
                    with self.assertRaises(PermissionError):
                        function(*args)
                volume.assert_not_called()
                manager.assert_not_called()

    def test_paths_and_document_control(self):
        for relative in (".env", ".codex/report.txt", ".config/systemd/user/test.service", "Projects/product/report.pdf", "policy/main.rego", "scratch/script.py"):
            with self.subTest(path=relative), self.assertRaises(PermissionError):
                self.authority._safe_path(str(self.root / relative), require_workspace=False)
        document = self.root / "Documents/report.pdf"
        document.parent.mkdir()
        document.write_bytes(b"synthetic")
        self.assertEqual(self.authority.validate_home_artifact(str(document)), document)
        alias = self.root / "alias"
        alias.symlink_to(document.parent, target_is_directory=True)
        with self.assertRaises(PermissionError):
            self.authority.validate_home_artifact(str(alias / document.name))

    def test_all_six_fixed_audio_helpers(self):
        value = {"percent": 55.0, "muted": False}
        with patch("tools.sentry_desktop.get_volume", return_value=value) as get, patch("tools.sentry_desktop.set_volume", return_value=value) as setv, patch("tools.sentry_desktop.adjust_volume", return_value=value) as adjust, patch("tools.sentry_desktop.set_muted", return_value=value) as mute, patch("tools.sentry_ui.projection_io_request", return_value={"audio_output": "usb"}) as output:
            for op, args in (("get_system_volume", {}), ("set_system_volume", {"percent": 50}), ("adjust_system_volume", {"delta_percent": 5}), ("set_system_muted", {"muted": True}), ("get_projection_audio_output", {}), ("set_projection_audio_output", {"output": "usb"})):
                self.assertTrue(execute_audio(op, args, self.root / "config.json"))
            for function in (get, setv, adjust, mute):
                self.assertEqual(function.call_count, 1)
            self.assertEqual(output.call_count, 2)
            output.return_value = {"audio_output": "hdmi"}
            self.assertEqual(execute_audio("set_projection_audio_output", {"output": "hdmi"}, self.root / "config.json"), {"audio_output": "hdmi"})

    def test_malformed_audio_executes_nothing(self):
        cases = (("set_system_volume", {"percent": True}), ("set_system_volume", {"percent": float("nan")}), ("set_system_volume", {"percent": 151}), ("adjust_system_volume", {"delta_percent": 0}), ("set_system_muted", {"muted": "true"}), ("set_projection_audio_output", {"output": "shell"}), ("get_system_volume", {"command": "secret"}))
        with patch("tools.sentry_desktop._run") as host, patch("tools.sentry_ui.projection_io_request") as output:
            for op, args in cases:
                with self.subTest(operation=op), self.assertRaises(ValueError):
                    execute_audio(op, args, self.root / "config.json")
            host.assert_not_called()
            output.assert_not_called()

    def test_authenticated_http_audio_bridge_and_no_token_denial(self):
        from tools.sentry_state_api import _Handler
        server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        server.store = None
        server.identity_token = "SYNTHETIC_CORE_TOKEN"
        server.identity_manager = SimpleNamespace(config_path=self.root / "config.json")
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/v1/audio/set_system_volume"
            with patch("tools.sentry_desktop.set_volume", return_value={"percent": 50, "muted": False}) as host:
                for token, expected in ((None, 401), ("wrong", 401), ("SYNTHETIC_CORE_TOKEN", 200)):
                    headers = {"Content-Type": "application/json"}
                    if token:
                        headers["Authorization"] = f"Bearer {token}"
                    req = Request(url, data=b'{"percent":50}', headers=headers, method="POST")
                    try:
                        with urlopen(req, timeout=3) as response:
                            self.assertEqual(response.status, expected)
                            self.assertEqual(json.load(response), {"percent": 50, "muted": False})
                    except HTTPError as exc:
                        self.assertEqual(exc.code, expected)
                host.assert_called_once_with(50)
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=3)
