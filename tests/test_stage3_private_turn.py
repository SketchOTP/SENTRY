"""Credential isolation fixtures only: sandbox open/close, never a model/secret read."""

import copy
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import tomllib

from tools.sentry_codex_profile import autonomous_turn_overrides, private_turn_profile


class PrivateTurnTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sentry-stage3-isolation-", dir=os.environ.get("XDG_RUNTIME_DIR"))
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.config_home = self.root / "codex-home"
        self.config_home.mkdir()
        (self.root / "state/sentry/anima-turns").mkdir(parents=True)
        self.private = [self.root / "Projects/ANIMA Home Automation/.env",
                        self.root / ".config/anima/server.env",
                        self.root / ".local/share/anima-owner-boundary/client-token"]
        for path in self.private:
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            path.write_text("ISOLATED_NOT_A_CREDENTIAL")
            path.chmod(0o600)
        self.public = self.root / "public.txt"
        self.public.write_text("ISOLATED_PUBLIC")
        self.alias = self.private[1].with_name("anima-project.env")
        self.alias.symlink_to(self.private[0])
        self.profile = {
            "model": "unchanged-test-model", "approval_policy": "never",
            "default_permissions": "sentry-resident", "features": {"shell_tool": True},
            "permissions": {"sentry-resident": {
                "extends": ":workspace", "network": {"enabled": False},
                "workspace_roots": {str(self.workspace): True},
                "filesystem": {":minimal": "read", "glob_scan_max_depth": 4,
                               ":workspace_roots": {".": "write", "*.env": "deny"}},
            }},
            "mcp_servers": {"anima_household": {"enabled": False, "command": "/usr/bin/true",
                "env_vars": ["ANIMA_PREBOUND_FILE"], "enabled_tools": [
                    "anima_health", "anima_get_context", "anima_list_tools", "anima_invoke", "anima_status",
                ]}},
        }
        environment = patch.dict(os.environ, {
            "SENTRY_ANIMA_CONFIG": str(self.root / "disabled-anima.json"),
            "XDG_STATE_HOME": str(self.root / "state"),
        })
        environment.start()
        self.addCleanup(environment.stop)

    def merge(self):
        with patch("tools.sentry_codex_profile.Path.home", return_value=self.root):
            return private_turn_profile(self.profile, self.workspace)

    def test_minimum_launch_merge_preserves_owner_profile_and_autonomous_restrictions(self):
        before = copy.deepcopy(self.profile)
        merged, arguments = self.merge()
        self.assertEqual(self.profile, before)
        self.assertEqual(merged["model"], before["model"])
        self.assertEqual(merged["features"], before["features"])
        self.assertEqual(merged["mcp_servers"], before["mcp_servers"])
        values = {arguments[1].split("=", 1)[0]: tomllib.loads("value=" + arguments[1].split("=", 1)[1])["value"]}
        filesystem = values["permissions.sentry-resident.filesystem"]
        self.assertEqual(filesystem[str(self.private[0])], "deny")
        self.assertEqual(filesystem[str(self.private[1].parent)], "deny")
        autonomous = autonomous_turn_overrides(merged)
        values = {autonomous[i+1].split("=", 1)[0]: tomllib.loads("value=" + autonomous[i+1].split("=", 1)[1])["value"]
                  for i in range(0, len(autonomous), 2)}
        self.assertIs(values["features.shell_tool"], False)
        self.assertEqual(values["permissions.sentry-resident.filesystem"][str(self.private[0])], "deny")
        self.assertEqual(values["permissions.sentry-resident.filesystem"][":workspace_roots"]["."], "read")

    def test_conflicting_grant_or_unknown_config_fail_closed(self):
        self.profile["permissions"]["sentry-resident"]["filesystem"][str(self.private[1])] = "read"
        with self.assertRaisesRegex(ValueError, "PRIVATE_DENY_UNPROVEN"):
            self.merge()
        self.profile["permissions"]["sentry-resident"]["filesystem"].pop(str(self.private[1]))
        (self.root / "disabled-anima.json").write_text("invalid-test-config")
        with self.assertRaises(ValueError):
            self.merge()

    def test_actual_cli_sandbox_external_private_open_denied_content_never_read(self):
        if os.environ.get("SENTRY_STAGE3_SANDBOX_TEST") != "1":
            self.skipTest("explicit no-model local CLI sandbox qualification required")
        cli = "/usr/lib/chatgpt/resources/codex"
        if not Path(cli).is_file():
            self.fail("qualified installed launcher unavailable")
        from tools.sentry_codex_profile import _inline
        (self.config_home / "config.toml").write_text("\n".join(
            f"{key}={_inline(value)}" for key, value in self.profile.items()))
        (self.config_home / "sentry-resident.config.toml").touch()
        environment = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "CODEX_HOME": str(self.config_home), "HOME": str(self.root)}
        def probe(overrides):
            code = """import errno,os,json,sys
results=[]
for index,path in enumerate(sys.argv[1:]):
 try:
  fd=os.open(path,os.O_RDONLY|(0 if index==3 else os.O_NOFOLLOW));os.close(fd);results.append('OPEN_ALLOWED_CONTENT_NOT_READ')
 except PermissionError: results.append('OPEN_DENIED')
try:
 fd=os.open('isolated-workspace-write',os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW,0o600);os.close(fd);results.append('WORKSPACE_WRITE_ALLOWED')
except OSError as exc:
 if exc.errno not in (errno.EACCES,errno.EPERM,errno.EROFS): raise
 results.append('WORKSPACE_WRITE_DENIED')
print(json.dumps(results))
"""
            result = subprocess.run([cli, "sandbox", *overrides, "--profile", "sentry-resident",
                "--permission-profile", "sentry-resident", "-C", str(self.workspace), "--",
                "/usr/bin/python3", "-c", code, *map(str, [*self.private, self.alias, self.public])],
                env=environment, cwd=self.workspace, capture_output=True, text=True, timeout=60, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        self.assertEqual(probe([]), ["OPEN_ALLOWED_CONTENT_NOT_READ"] * 5 + ["WORKSPACE_WRITE_ALLOWED"])
        merged, overrides = self.merge()
        expected = ["OPEN_DENIED"] * 4 + ["OPEN_ALLOWED_CONTENT_NOT_READ"]
        self.assertEqual(probe(overrides), expected + ["WORKSPACE_WRITE_ALLOWED"])
        # Same final last-wins ordering as invoke_sentry_agent, not an
        # intermediate overlay that could hide a later write reintroduction.
        self.assertEqual(probe(overrides + autonomous_turn_overrides(merged)),
                         expected + ["WORKSPACE_WRITE_DENIED"])

    def test_actual_bridge_host_feature_disable_configuration_without_model(self):
        if os.environ.get("SENTRY_STAGE3_SANDBOX_TEST") != "1":
            self.skipTest("explicit no-model local CLI feature qualification required")
        from tools.sentry_codex_bridge import _tool_free_overrides
        result = subprocess.run([
            "/usr/lib/chatgpt/resources/codex", *_tool_free_overrides(), "features", "list",
        ], env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(self.root),
                "CODEX_HOME": str(self.config_home)}, cwd=self.workspace,
            capture_output=True, text=True, timeout=60, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        states = {line.split()[0]: line.split()[-1] for line in result.stdout.splitlines() if line.split()}
        for name in ("shell_tool", "code_mode_host", "view_image", "apps", "plugins",
                     "browser_use", "computer_use", "workspace_dependencies", "hooks"):
            self.assertEqual(states.get(name), "false", name)
        # This qualified build keeps the execution backend enabled even when
        # --disable unified_exec is requested. It is not the shell-tool gate.
        self.assertEqual(states.get("unified_exec"), "true")
