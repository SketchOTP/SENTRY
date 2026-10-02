import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from tools.sentry_execution_authority import ExecutionAuthority
from tools.sentry_model_calls import PURPOSES, account_calls, accounted_run


def completed(usage=None, code=0):
    lines = [
        {
            "type": "item.completed",
            "item": {
                "type": "agent_message",
                "text": '{"answer":"private fixture content"}',
            },
        }
    ]
    if usage is not None:
        lines.append({"type": "turn.completed", "usage": usage})
    return subprocess.CompletedProcess(
        [], code, "\n".join(json.dumps(row) for row in lines), "private error content"
    )


class ModelCallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        env = patch.dict(
            os.environ,
            {
                "SENTRY_AUTHORITY_ROOT": str(self.root),
                "SENTRY_AGENT_WORKSPACE": str(self.root / "workspace"),
            },
        )
        env.start()
        self.addCleanup(env.stop)

    def test_all_purposes_and_unknown_usage_without_payloads(self):
        for purpose in PURPOSES:
            accounted_run(purpose, "fixture-model", lambda: completed())
        value = ExecutionAuthority().model_call_summary()
        self.assertEqual(value["counts"]["ATTEMPTED"], len(PURPOSES))
        self.assertEqual(value["counts"]["SUCCEEDED"], len(PURPOSES))
        self.assertTrue(
            all(
                row["usage"] is None and row["usage_status"] == "UNKNOWN"
                for row in value["calls"]
            )
        )
        data = (self.root / "execution-audit.jsonl").read_text()
        self.assertNotIn("private", data)
        self.assertNotIn("thread_id", data)
        self.assertNotIn("request_id", data)
        self.assertEqual(
            (self.root / "execution-audit.jsonl").stat().st_mode & 0o777, 0o600
        )

    def test_failure_timeout_launch_and_usage_are_distinct(self):
        for exception, expected in [
            (subprocess.TimeoutExpired("private", 1), "TIMEOUT"),
            (OSError("private"), "LAUNCH_FAILED"),
            (RuntimeError("private"), "FAILED"),
        ]:
            with self.assertRaises(type(exception)):
                accounted_run("OPERATIONAL", "fixture", Mock(side_effect=exception))
            self.assertEqual(
                ExecutionAuthority().model_call_summary()["calls"][-1]["status"],
                expected,
            )
        accounted_run(
            "OPERATIONAL",
            "fixture",
            lambda: completed(
                {"input_tokens": 7, "output_tokens": 0, "private_prompt": "secret"},
                code=1,
            ),
        )
        row = ExecutionAuthority().model_call_summary()["calls"][-1]
        self.assertEqual(row["status"], "FAILED")
        self.assertEqual(row["usage"], {"input_tokens": 7, "output_tokens": 0})
        self.assertEqual(row["usage_status"], "REPORTED")

    def test_actual_bridge_callers_record_their_own_purposes_and_failures(self):
        from tools import sentry_codex_bridge as bridge

        callers = [
            ("EVENT", lambda: bridge.invoke({"event_id": "fixture"}, "low", 1)),
            ("GROUNDED", lambda: bridge.invoke_grounded_query("fixture", {})),
            ("PLANNER", lambda: bridge.invoke_conversation_planner("fixture", [], [])),
            ("SYNTHESIS", lambda: bridge.invoke_conversation_synthesis("fixture", [], [])),
            ("PROACTIVE", lambda: bridge.invoke_proactive_judgment({})),
        ]
        with patch.object(bridge, "_launcher_args", return_value=["fixture-cli"]):
            for purpose, invoke in callers:
                with self.subTest(purpose=purpose), patch.object(
                    bridge.subprocess, "run", return_value=completed({"input_tokens": 3})
                ) as runner:
                    result = invoke()
                    runner.assert_called_once()
                    self.assertEqual(result["model_call_count"], 1)
                    self.assertEqual(result["model_calls"][0]["purpose"], purpose)
                    self.assertEqual(result["model_calls"][0]["usage"], {"input_tokens": 3})
            with patch.object(
                bridge.subprocess, "run", side_effect=subprocess.TimeoutExpired("fixture", 1)
            ) as runner:
                result = bridge.invoke_grounded_query("fixture", {})
                runner.assert_called_once()
                self.assertFalse(result["ok"])
                self.assertEqual(result["model_calls"][0]["status"], "TIMEOUT")
                self.assertEqual(result["model_calls"][0]["usage_status"], "UNKNOWN")

    def test_attempt_survives_lost_receipt_without_retry(self):
        authority = ExecutionAuthority()
        authority.record_model_call(
            {
                "call_id": "fixture",
                "purpose": "OPERATIONAL",
                "phase": "ATTEMPTED",
                "status": "UNKNOWN",
                "model": "fixture",
                "usage": None,
                "usage_status": "UNKNOWN",
            }
        )
        self.assertEqual(
            ExecutionAuthority().model_call_summary()["counts"]["UNKNOWN"], 1
        )
        runner = Mock()
        with (
            patch.object(
                ExecutionAuthority, "record_model_call", side_effect=PermissionError
            ),
            self.assertRaises(PermissionError),
        ):
            accounted_run("PROACTIVE", "fixture", runner)
        runner.assert_not_called()

    def test_scoped_nested_counts_include_optional_presentation_and_classifier(self):
        @account_calls
        def renderer():
            accounted_run("PRESENTATION", "fixture", lambda: completed())
            return "fixture"

        @account_calls
        def turn():
            accounted_run("OPERATIONAL", "fixture", lambda: completed())
            renderer()
            accounted_run("CLASSIFIER", "fixture", lambda: completed())
            return {"ok": True}

        value = turn()
        self.assertEqual(value["luna_invocations"], 3)
        self.assertEqual(
            [row["purpose"] for row in value["model_calls"]],
            ["OPERATIONAL", "PRESENTATION", "CLASSIFIER"],
        )

        @account_calls
        def immediate():
            return {"status": "DELIVERED"}

        self.assertEqual(immediate()["luna_invocations"], 0)

    def test_recent_counts_have_truthful_bound_and_no_symlink_follow(self):
        target = self.root / "target"
        target.write_text("unchanged")
        (self.root / "execution-audit.jsonl").symlink_to(target)
        with self.assertRaises(OSError):
            accounted_run("EVENT", "fixture", Mock())
        self.assertEqual(target.read_text(), "unchanged")

    def test_offline_exact_test_classification_is_append_only_and_excluded(self):
        accounted_run("EVENT", "fixture", lambda: completed())
        authority = ExecutionAuthority()
        original = authority.audit_path.read_bytes()
        identifier = authority.model_call_summary()["calls"][0]["call_id"]
        plan = authority.classify_model_test_receipts({identifier: ""})
        self.assertEqual(plan["disposition"], "READ_ONLY_PLAN")
        self.assertEqual(authority.audit_path.read_bytes(), original)
        digest = plan["receipts"][0]["receipt_digest"]
        with self.assertRaises(ValueError):
            authority.classify_model_test_receipts({identifier: "a" * 64}, apply=True)
        self.assertEqual(authority.audit_path.read_bytes(), original)
        applied = authority.classify_model_test_receipts(
            {identifier: digest}, apply=True
        )
        self.assertEqual(applied["disposition"], "APPENDED")
        corrected = authority.audit_path.read_bytes()
        self.assertTrue(corrected.startswith(original))
        self.assertEqual(
            authority.classify_model_test_receipts({identifier: digest}, apply=True)[
                "disposition"
            ],
            "ALREADY_CLASSIFIED",
        )
        self.assertEqual(authority.audit_path.read_bytes(), corrected)
        value = authority.model_call_summary()
        self.assertEqual(value["excluded_synthetic_test_calls"], 1)
        self.assertEqual(value["counts"]["ATTEMPTED"], 0)
        accounted_run("OPERATIONAL", "fixture", lambda: completed())
        value = authority.model_call_summary()
        self.assertEqual(value["counts"]["ATTEMPTED"], 1)
        self.assertEqual(value["excluded_synthetic_test_calls"], 1)
        self.assertEqual(value["calls"][0]["purpose"], "OPERATIONAL")
        self.assertEqual(authority.recent_audit()["records"], [])

    def test_public_summary_rejects_unqualified_usage_and_does_not_forward_private_fields(
        self,
    ):
        accounted_run("EVENT", "fixture", lambda: completed())
        authority = ExecutionAuthority()
        records = [
            json.loads(line) for line in authority.audit_path.read_text().splitlines()
        ]
        records[-1]["prompt"] = "private sentinel"
        records[-1]["credential"] = "secret sentinel"
        with authority.audit_path.open("a") as handle:
            handle.write(json.dumps(records[-1]) + "\n")
        public = json.dumps(authority.model_call_summary())
        self.assertNotIn("sentinel", public)
        self.assertNotIn("credential", public)
        with self.assertRaises(ValueError):
            authority.record_model_call(
                {
                    key: value
                    for key, value in records[-1].items()
                    if key not in {"record_type", "timestamp", "prompt", "credential"}
                }
                | {"usage": {"prompt": "private"}}
            )
