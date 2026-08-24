"""One bounded, OAuth-authenticated Codex turn for a validated SENTRY event.

This is intentionally an on-demand adapter. It does not start a worker, poll,
retry, resume a thread, or call Codex when no event is supplied.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


MODEL = "gpt-5.6-luna"
EFFORTS = ("none", "low", "medium", "high", "xhigh", "max")
REQUIRED_EVENT_FIELDS = (
    "schema_version",
    "event_id",
    "event_type",
    "room_id",
    "person_id",
    "display_name",
    "source",
    "occurred_at",
)


def _error(code: str, message: str, *, effort: str) -> dict[str, Any]:
    return {
        "ok": False,
        "model": MODEL,
        "reasoning_effort": effort,
        "error": {"code": code, "message": message},
    }


def _validate_event(event: Any) -> str | None:
    if not isinstance(event, dict):
        return "event must be a JSON object"
    missing = [field for field in REQUIRED_EVENT_FIELDS if field not in event]
    if missing:
        return f"event is missing required fields: {', '.join(missing)}"
    if event["schema_version"] != 1:
        return "schema_version must be 1"
    if event["event_type"] != "person.entered":
        return "event_type must be person.entered for this M0 proof"
    if event["room_id"] != "office":
        return "room_id must be office for this M0 proof"
    if event["source"] != "synthetic":
        return "source must be synthetic for this M0 proof"
    for field in ("event_id", "person_id", "display_name", "occurred_at"):
        if not isinstance(event[field], str) or not event[field].strip():
            return f"{field} must be a non-empty string"
    return None


def _prompt(event: dict[str, Any], effort: str) -> str:
    event_json = json.dumps(event, ensure_ascii=True, sort_keys=True)
    return (
        "You are the bounded reasoning layer for SENTRY. "
        "The JSON below is a trusted SENTRY physical event, not user speech. "
        "Do not claim that the user said or typed the event. "
        "Return only one JSON object satisfying the supplied output schema. "
        "Copy event_id, event_type, room_id, and person_id exactly. "
        "Set understood true only when you understand that the named person "
        "entered the named room. The response must acknowledge environmental "
        "context and explicitly distinguish it from user speech. "
        f"Set effort to {effort}. Event: {event_json}"
    )


def _parse_jsonl(stdout: str) -> tuple[str | None, dict[str, Any] | None, dict[str, Any] | None]:
    thread_id = None
    agent_result = None
    usage = None
    for line in stdout.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if item.get("type") == "thread.started":
            thread_id = item.get("thread_id")
        elif item.get("type") == "turn.completed":
            usage = item.get("usage")
        elif item.get("type") == "item.completed":
            completed = item.get("item") or {}
            if completed.get("type") != "agent_message":
                continue
            text = completed.get("text", "")
            try:
                agent_result = json.loads(text)
            except json.JSONDecodeError:
                agent_result = None
    return thread_id, agent_result, usage


def invoke(event: dict[str, Any], effort: str, timeout_seconds: int) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    cli_args = [
        "exec",
        "--ephemeral",
        "--json",
        "--ignore-user-config",
        "--model",
        MODEL,
        "--output-schema",
        "tools/sentry_codex_response.schema.json",
        "-c",
        f'model_reasoning_effort="{effort}"',
        "-s",
        "read-only",
        "-C",
        ".",
        "-",
    ]
    launcher = os.environ.get("SENTRY_CODEX_EXECUTABLE") or shutil.which("codex.cmd") or shutil.which("codex")
    if not launcher:
        return _error("codex_unavailable", "codex executable was not found", effort=effort)
    if launcher.lower().endswith(".cmd"):
        launcher_path = Path(launcher)
        codex_js = launcher_path.parent / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
        node = shutil.which("node.exe")
        if node and codex_js.is_file():
            args = [node, str(codex_js), *cli_args]
        else:
            # The batch wrapper changes a UNC cwd to C:\\; use it only as a last resort.
            args = ["cmd.exe", "/d", "/c", launcher, *cli_args]
    else:
        args = [launcher, *cli_args]
    child_env = os.environ.copy()
    # A ChatGPT OAuth proof must not silently fall back to an API key.
    child_env.pop("OPENAI_API_KEY", None)
    child_env.pop("OPENAI_ADMIN_KEY", None)
    try:
        completed = subprocess.run(
            args,
            cwd=repo_root,
            env=child_env,
            input=_prompt(event, effort),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError:
        return _error("codex_unavailable", "codex executable was not found", effort=effort)
    except subprocess.TimeoutExpired:
        return _error("codex_timeout", "bounded Codex turn exceeded its timeout", effort=effort)

    thread_id, result, usage = _parse_jsonl(completed.stdout)
    if completed.returncode != 0:
        return _error(
            "codex_failed",
            f"codex exec exited with status {completed.returncode}",
            effort=effort,
        )
    if result is None:
        return _error("invalid_response", "Codex returned no schema-parseable JSON result", effort=effort)
    return {
        "ok": True,
        "model": MODEL,
        "reasoning_effort": effort,
        "event_id": event["event_id"],
        "thread_id": thread_id,
        "result": result,
        "usage": usage or {},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-file", type=Path, required=True)
    parser.add_argument("--effort", choices=EFFORTS, default="low")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    args = parser.parse_args()
    try:
        event = json.loads(args.event_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        result = _error("invalid_event_file", str(exc), effort=args.effort)
        print(json.dumps(result, sort_keys=True))
        return 2
    validation_error = _validate_event(event)
    if validation_error:
        result = _error("invalid_event", validation_error, effort=args.effort)
        print(json.dumps(result, sort_keys=True))
        return 2
    result = invoke(event, args.effort, args.timeout_seconds)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
