"""Synthetic-only resident ANIMA integration: no auth, model, or device calls."""

import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import tomllib

from tools.sentry_anima import (
    AnimaConfig,
    ResidentAnimaTurn,
    binding_root,
    private_json,
    voice_origin,
)
from tools.sentry_codex_agent import invoke_sentry_agent
from tools.sentry_codex_profile import _filesystem_rules, profile_text


class Client:
    def __init__(self):
        self.events = []
        self.fail_open = False
        self.fail_start = False
        self.fail_submit = False

    def open_direct_interaction(self, request, surface, question, identity):
        self.events.append(("open", request, surface, question, identity))
        if self.fail_open:
            raise RuntimeError("PRIVATE CONTENT MUST NOT APPEAR")
        return {
            "status": "CLAIMED",
            "request_id": "cb0f06e3-c10b-40a7-b661-a1a352fe26ec",
            "binding": "private-binding",
        }

    def provider_start(self, request, binding):
        self.events.append(("start",))
        return {"status": "FAILED" if self.fail_start else "PROVIDER_RUNNING"}

    def renew(self, request, binding):
        self.events.append(("renew",))
        return {"status": "RENEWED"}

    def submit_result(self, request, binding, **payload):
        self.events.append(("submit", payload))
        if self.fail_submit:
            raise RuntimeError("PRIVATE CONTENT MUST NOT APPEAR")
        return {"status": "RECORDED"}


class ResidentAnimaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.codex_home = self.root / "codex-home"
        self.codex_home.mkdir()
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.config_path = self.root / "anima.json"
        self.package = self.root / "client"
        self.package.mkdir()
        (self.package / "anima_household_mcp.py").touch()
        self.config_path.write_text(
            json.dumps(
                {
                    "enabled": True,
                    "endpoint": "/private/core.sock",
                    "token_file": str(self.root / "token"),
                    "worker_id": "resident",
                    "client_directory": str(self.package),
                }
            )
        )
        self.config_path.chmod(0o600)
        self.env = patch.dict(
            os.environ,
            {
                "SENTRY_ANIMA_CONFIG": str(self.config_path),
                "XDG_STATE_HOME": str(self.root / "state"),
                "CODEX_HOME": str(self.codex_home),
                "SENTRY_CODEX_HOME": str(self.codex_home),
            },
            clear=False,
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        self.profile = profile_text(
            python_executable=Path("/usr/bin/python3"),
            config_path=self.root / "sentry.json",
            workspace_path=self.workspace,
            anima_config_path=self.config_path,
        )
        (self.codex_home / "sentry-resident.config.toml").write_text(self.profile)
        self.client = Client()
        client_patch = patch.object(AnimaConfig, "client", return_value=self.client)
        client_patch.start()
        self.addCleanup(client_patch.stop)
        launcher = patch(
            "tools.sentry_codex_agent._launcher_args", return_value=["codex"]
        )
        launcher.start()
        self.addCleanup(launcher.stop)
        metrics = patch("tools.sentry_codex_agent._thread_metrics", return_value={})
        metrics.start()
        self.addCleanup(metrics.stop)

    def completed(self, status="completed"):
        return SimpleNamespace(
            returncode=0,
            stderr="",
            stdout=json.dumps(
                {
                    "type": "item.completed",
                    "item": {
                        "type": "agent_message",
                        "text": json.dumps(
                            {"answer": "Actual bounded answer", "status": status}
                        ),
                    },
                }
            ),
        )

    def invoke(self, runner, surface="always_on_voice"):
        with voice_origin(surface):
            return invoke_sentry_agent(
                "Synthetic voice question",
                [],
                working_directory=self.workspace,
                request_id="sentry-request",
                session_id="dedicated-existing-thread",
                runner=runner,
            )

    def test_prebound_before_runner_private_cleanup_final_once_and_thread_preserved(
        self,
    ):
        paths = []

        def runner(args, **kwargs):
            self.assertEqual([x[0] for x in self.client.events], ["open", "start"])
            path = Path(kwargs["env"]["ANIMA_PREBOUND_FILE"])
            paths.append(path)
            data = private_json(path)
            self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
            self.assertEqual(data["workspace_root"], str(self.workspace))
            self.assertTrue(data["persistent_thread"])
            self.assertEqual(data["source_surface"], "always_on_voice")
            self.assertGreater(
                datetime.fromisoformat(data["expires_at"]), datetime.now(timezone.utc)
            )
            self.assertFalse(path.is_relative_to(self.workspace))
            self.assertNotIn("private-binding", kwargs["input"])
            self.assertNotIn("Synthetic voice question", path.read_text())
            self.assertNotIn("ANIMA_SENTRY_CLIENT_TOKEN_FILE", kwargs["env"])
            self.assertIn("dedicated-existing-thread", args)
            self.assertIn("resume", args)
            self.assertNotIn("--ephemeral", args)
            self.assertLessEqual(kwargs["timeout"], 255)
            path.with_name("metadata.json").write_text(
                json.dumps({"version": 1, "status": "SUCCEEDED", "calls": 2})
            )
            return self.completed()

        result = self.invoke(runner)
        self.assertTrue(result["ok"])
        self.assertEqual(result["anima"]["status"], "RECORDED")
        self.assertEqual(self.client.events[-1][1]["status"], "RESPONSE")
        self.assertEqual(self.client.events[-1][1]["response"], "Actual bounded answer")
        self.assertEqual(sum(x[0] == "submit" for x in self.client.events), 1)
        self.assertFalse(paths[0].parent.exists())
        self.assertEqual(list(binding_root().iterdir()), [])

    def test_outage_preserves_ordinary_resident_without_mcp_or_retry(self):
        self.client.fail_open = True

        def runner(args, **kwargs):
            self.assertNotIn("ANIMA_PREBOUND_FILE", kwargs["env"])
            self.assertIn("mcp_servers.anima_household.enabled=false", args)
            self.assertIn("continue independent SENTRY work", kwargs["input"])
            return self.completed()

        result = self.invoke(runner)
        self.assertTrue(result["ok"])
        self.assertEqual([x[0] for x in self.client.events], ["open"])
        self.assertNotIn("PRIVATE CONTENT", json.dumps(result))

    def test_failed_provider_start_never_exposes_binding_to_model(self):
        self.client.fail_start = True

        def runner(args, **kwargs):
            self.assertNotIn("ANIMA_PREBOUND_FILE", kwargs["env"])
            return self.completed()

        self.invoke(runner)
        self.assertEqual(
            [x[0] for x in self.client.events], ["open", "start", "submit"]
        )
        self.assertEqual(self.client.events[-1][1]["status"], "UNKNOWN_RESULT")

    def test_timeout_is_unknown_once_no_replay_and_cleans_binding(self):
        paths = []

        def runner(args, **kwargs):
            paths.append(Path(kwargs["env"]["ANIMA_PREBOUND_FILE"]))
            raise subprocess.TimeoutExpired("synthetic", 1)

        result = self.invoke(runner)
        self.assertFalse(result["ok"])
        self.assertEqual(
            [x[0] for x in self.client.events], ["open", "start", "submit"]
        )
        self.assertTrue(self.client.events[-1][1]["provider_ambiguous"])
        self.assertIsNone(self.client.events[-1][1]["response"])
        self.assertFalse(paths[0].exists())

    def test_sensor_and_default_origins_never_open_direct_interaction(self):
        for surface in ("autonomous", "sensor", "sentry_ask"):
            with self.subTest(surface=surface):
                self.assertTrue(
                    self.invoke(lambda *a, **kw: self.completed(), surface=surface)[
                        "ok"
                    ]
                )
        self.assertEqual(self.client.events, [])

    def test_optin_missing_and_profile_mismatch_do_not_open(self):
        self.config_path.unlink()
        self.invoke(lambda *a, **kw: self.completed())
        self.assertEqual(self.client.events, [])

    def test_profile_retains_native_capabilities_and_denies_binding_token(self):
        data = tomllib.loads(self.profile)
        self.assertEqual(set(data["mcp_servers"]), {"sentry_office", "anima_household"})
        self.assertTrue(data["features"]["shell_tool"])
        self.assertTrue(data["features"]["image_generation"])
        self.assertFalse(data["permissions"]["sentry-resident"]["network"]["enabled"])
        self.assertFalse(data["mcp_servers"]["anima_household"]["enabled"])
        self.assertEqual(
            data["mcp_servers"]["anima_household"]["env_vars"], ["ANIMA_PREBOUND_FILE"]
        )
        for path in (self.config_path, self.root / "token", binding_root()):
            self.assertEqual(
                data["permissions"]["sentry-resident"]["filesystem"][str(path)], "deny"
            )

    def test_profile_approves_only_exact_prebound_tools(self):
        data = tomllib.loads(self.profile)
        server = data["mcp_servers"]["anima_household"]
        expected = [
            "anima_health",
            "anima_get_context",
            "anima_list_tools",
            "anima_invoke",
            "anima_status",
        ]
        self.assertEqual(server["enabled_tools"], expected)
        self.assertEqual(server["default_tools_approval_mode"], "prompt")
        self.assertEqual(
            server["tools"],
            {name: {"approval_mode": "approve"} for name in expected},
        )
        self.assertFalse(server["enabled"])
        self.assertEqual(server["env_vars"], ["ANIMA_PREBOUND_FILE"])
        self.assertEqual(data["approval_policy"], "never")

    def test_anima_approval_settings_preserve_office_and_non_anima_profile(self):
        baseline = tomllib.loads(
            profile_text(
                python_executable=Path("/usr/bin/python3"),
                config_path=self.root / "sentry.json",
                workspace_path=self.workspace,
            )
        )
        integrated = tomllib.loads(self.profile)
        self.assertEqual(set(baseline["mcp_servers"]), {"sentry_office"})
        self.assertEqual(
            integrated["mcp_servers"]["sentry_office"],
            baseline["mcp_servers"]["sentry_office"],
        )
        for key in (
            "approval_policy",
            "default_permissions",
            "features",
            "shell_environment_policy",
            "model",
            "model_reasoning_effort",
            "model_instructions_file",
        ):
            self.assertEqual(integrated[key], baseline[key], key)

    def test_gate_sidecar_is_authoritative_over_model_completed(self):
        for outcome in (
            "WAITING_CONFIRMATION",
            "WAITING_STRONGER_AUTH",
            "UNAVAILABLE",
            "FAILED",
            "UNKNOWN_RESULT",
        ):
            with self.subTest(outcome=outcome):

                def runner(args, expected=outcome, **kwargs):
                    path = Path(kwargs["env"]["ANIMA_PREBOUND_FILE"])
                    path.with_name("metadata.json").write_text(
                        json.dumps({"version": 1, "status": expected, "calls": 1})
                    )
                    return self.completed()

                self.invoke(runner)
                self.assertEqual(self.client.events[-1][1]["status"], outcome)

    def test_submit_failure_not_retried(self):
        self.client.fail_submit = True
        result = self.invoke(lambda *a, **kw: self.completed())
        self.assertEqual(result["anima"]["status"], "UNKNOWN_RESULT")
        self.assertEqual(sum(x[0] == "submit" for x in self.client.events), 1)
        self.assertNotIn("PRIVATE CONTENT", json.dumps(result))

    def test_private_config_symlink_and_world_readable_rejected(self):
        self.config_path.chmod(0o644)
        with self.assertRaises(ValueError):
            AnimaConfig.load(self.config_path)
        self.config_path.chmod(0o600)
        alias = self.root / "alias"
        alias.symlink_to(self.config_path)
        with self.assertRaises(OSError):
            AnimaConfig.load(alias)

    def test_profile_missing_denial_does_not_open_even_when_enabled(self):
        data = tomllib.loads(self.profile)
        data["permissions"]["sentry-resident"]["filesystem"].pop(
            str(self.root / "token")
        )
        turn = ResidentAnimaTurn()
        with voice_origin("always_on_voice"):
            turn.prepare("synthetic", "sentry", self.workspace, profile_data=data)
        self.assertEqual(self.client.events, [])
        self.assertEqual(turn.diagnostics["stage"], "PROFILE_NOT_ENABLED")

    def test_denial_normalization_removes_only_redundant_descendants(self):
        parent = self.root / ".config/sentry"
        token_root = self.root / "client"
        values = [
            str(parent / "anima.json"),
            str(parent),
            str(parent),
            str(token_root / "client.token"),
            str(token_root),
            str(self.root / ".config/sentry-other/private"),
        ]
        rules = tomllib.loads(_filesystem_rules(values))
        self.assertEqual(
            {key for key, mode in rules.items() if mode == "deny"},
            {
                str(parent),
                str(token_root),
                str(self.root / ".config/sentry-other/private"),
            },
        )

    def test_real_configuration_layout_has_parent_deny_without_child_deny(self):
        config = self.root / ".config/sentry/anima.json"
        config.parent.mkdir(parents=True)
        config.write_text(self.config_path.read_text())
        config.chmod(0o600)
        with patch.object(Path, "home", return_value=self.root):
            profile = tomllib.loads(
                profile_text(
                    python_executable=Path("/usr/bin/python3"),
                    config_path=config.parent / "config.json",
                    workspace_path=self.workspace,
                    anima_config_path=config,
                )
            )
        filesystem = profile["permissions"]["sentry-resident"]["filesystem"]
        self.assertEqual(filesystem[str(config.parent)], "deny")
        self.assertNotIn(str(config), filesystem)
        denied = [Path(key) for key, mode in filesystem.items() if mode == "deny"]
        self.assertFalse(
            any(
                child != parent and child.is_relative_to(parent)
                for parent in denied
                for child in denied
            )
        )
        turn = ResidentAnimaTurn()
        self.addCleanup(turn.close)
        with (
            patch.dict(os.environ, {"SENTRY_ANIMA_CONFIG": str(config)}),
            voice_origin("always_on_voice"),
        ):
            turn.prepare("synthetic", "sentry", self.workspace, profile_data=profile)
        self.assertEqual(turn.diagnostics["status"], "BOUND")

    def test_ancestor_denials_allow_host_preparation_without_child_mounts(self):
        data = tomllib.loads(self.profile)
        filesystem = data["permissions"]["sentry-resident"]["filesystem"]
        for path in (self.config_path, self.root / "token", binding_root()):
            filesystem.pop(str(path))
        filesystem[str(self.root)] = "deny"
        turn = ResidentAnimaTurn()
        self.addCleanup(turn.close)
        with voice_origin("always_on_voice"):
            turn.prepare("synthetic", "sentry", self.workspace, profile_data=data)
        self.assertEqual(turn.diagnostics["status"], "BOUND")
        self.assertEqual([event[0] for event in self.client.events], ["open", "start"])

    def test_weak_prefix_and_overridden_parent_never_prove_token_denial(self):
        target = self.root / "token"
        for replacement in (
            {str(self.root): "read"},
            {str(self.root)[:-1]: "deny"},
            {str(self.root) + "-other": "deny"},
            {str(self.root): "deny", str(target): "read"},
            {str(self.root / "*"): "deny"},
        ):
            with self.subTest(replacement=replacement):
                data = tomllib.loads(self.profile)
                filesystem = data["permissions"]["sentry-resident"]["filesystem"]
                filesystem.pop(str(target))
                filesystem.update(replacement)
                turn = ResidentAnimaTurn()
                with voice_origin("always_on_voice"):
                    turn.prepare(
                        "synthetic", "sentry", self.workspace, profile_data=data
                    )
                self.assertEqual(turn.diagnostics["stage"], "PROFILE_NOT_ENABLED")
        self.assertEqual(self.client.events, [])

    def test_denied_symlink_alias_does_not_prove_unrelated_target_path(self):
        private = self.root / "private"
        private.mkdir()
        alias = self.root / "alias"
        alias.symlink_to(private, target_is_directory=True)
        rules = tomllib.loads(_filesystem_rules([str(alias), str(private / "token")]))
        self.assertEqual(rules[str(alias)], "deny")
        self.assertEqual(rules[str(private / "token")], "deny")

    def test_launcher_prefix_is_not_split_by_optional_profile_override(self):
        def runner(args, **kwargs):
            self.assertEqual(args[:2], ["/usr/bin/node", "/fixed/codex.js"])
            self.assertEqual(args[2], "-c")
            return self.completed()

        with patch(
            "tools.sentry_codex_agent._launcher_args",
            return_value=["/usr/bin/node", "/fixed/codex.js"],
        ):
            self.invoke(runner)

    def test_actual_prebound_mcp_consumes_host_file_and_preserves_tool_gate(self):
        package = (
            Path(__file__).resolve().parents[2]
            / "ANIMA Home Automation/integrations/sentry/anima-household"
        )
        if not (package / "anima_household_mcp.py").is_file():
            self.skipTest("sibling ANIMA client checkout unavailable")
        original_modules = set(sys.modules)

        def runner(args, **kwargs):
            path = Path(kwargs["env"]["ANIMA_PREBOUND_FILE"])
            with (
                patch.dict(os.environ, {"ANIMA_PREBOUND_FILE": str(path)}),
                patch.object(sys, "path", [str(package), *sys.path]),
            ):
                spec = importlib.util.spec_from_file_location(
                    "sentry_anima_test_mcp", package / "anima_household_mcp.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            calls = []
            request_id = "cb0f06e3-c10b-40a7-b661-a1a352fe26ec"

            class WireClient:
                def call(self, route):
                    return {"state": "available"}

                def tools(self, request, binding):
                    return {
                        "tools": [
                            {
                                "tool_id": "anima.household-spaces.list_spaces",
                                "availability": True,
                            },
                            {
                                "tool_id": "anima.external.shopping.upcitemdb.search_products",
                                "availability": True,
                                "content_persistence": "EPHEMERAL_RESTRICTED",
                            },
                        ]
                    }

                def invoke(self, request, binding, tool, arguments, ordinal):
                    calls.append(tool)
                    return {"status": "REQUIRE_STRONGER_AUTH"}

            module._CLIENT = WireClient()
            health = module.anima_health()
            self.assertEqual(health["request_id"], request_id)
            self.assertNotIn("binding", health)
            catalogue = module.anima_list_tools(request_id)
            self.assertEqual(len(catalogue["tools"]), 1)
            with self.assertRaises(RuntimeError):
                module.anima_provider_start(request_id)
            result = module.anima_invoke(
                request_id, "anima.household-spaces.list_spaces", {}, 1
            )
            self.assertEqual(result["status"], "REQUIRE_STRONGER_AUTH")
            with self.assertRaises(RuntimeError):
                module.anima_invoke(
                    request_id, "anima.household-spaces.list_spaces", {}, 2
                )
            self.assertEqual(len(calls), 1)
            self.assertEqual(
                private_json(path.with_name("metadata.json"))["status"],
                "WAITING_STRONGER_AUTH",
            )
            return self.completed()

        try:
            result = self.invoke(runner)
            self.assertEqual(result["anima"]["result_status"], "WAITING_STRONGER_AUTH")
        finally:
            # Only test-loaded client modules, never production module state.
            for name in ("anima_household_client", "sentry_anima_test_mcp"):
                if name not in original_modules:
                    sys.modules.pop(name, None)

    def test_lease_loss_revokes_binding_and_final_is_unknown(self):
        turn = ResidentAnimaTurn()
        with voice_origin("always_on_voice"):
            turn.prepare(
                "synthetic",
                "sentry",
                self.workspace,
                profile_data=tomllib.loads(self.profile),
            )
        path = turn.path
        self.addCleanup(turn.close)
        with (
            patch.object(turn._stop, "wait", return_value=False),
            patch.object(self.client, "renew", return_value={"status": "LOST"}),
        ):
            turn._renew()
        self.assertFalse(path.exists())
        turn.finish(
            {"answer": "Not a proven success", "status": "completed"}, success=True
        )
        self.assertEqual(self.client.events[-1][1]["status"], "UNKNOWN_RESULT")


if __name__ == "__main__":
    unittest.main()
