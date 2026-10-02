"""Metadata-only call receipts in SENTRY's existing execution audit facility.

An attempted CLI invocation is not proof of a charged provider invocation.
Nothing here is a retry mechanism, a prompt store or an execution permission.
"""

from __future__ import annotations

import json
import subprocess
import uuid
from collections.abc import Callable
from contextvars import ContextVar
from functools import wraps
from typing import Any

from tools.sentry_execution_authority import ExecutionAuthority

PURPOSES = {
    "OPERATIONAL",
    "PRESENTATION",
    "CLASSIFIER",
    "GROUNDED",
    "PLANNER",
    "SYNTHESIS",
    "PROACTIVE",
    "EVENT",
}
_CALLS: ContextVar[list[dict[str, Any]] | None] = ContextVar(
    "model_call_receipts", default=None
)


def account_calls(function: Callable[..., Any]) -> Callable[..., Any]:
    """Attach exact scoped attempts, including nested presentation/classification."""

    @wraps(function)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        parent = _CALLS.get()
        calls: list[dict[str, Any]] = parent if parent is not None else []
        start = len(calls)
        token = _CALLS.set(calls)
        try:
            result = function(*args, **kwargs)
            if isinstance(result, dict):
                selected = calls[start:]
                result = {
                    **result,
                    "model_calls": list(selected),
                    "model_call_count": len(selected),
                    "luna_invocations": len(selected),
                }
            return result
        finally:
            _CALLS.reset(token)

    return wrapped


def accounted_run(
    purpose: str, model: str, runner: Callable[..., Any], *args: Any, **kwargs: Any
) -> Any:
    if purpose not in PURPOSES:
        raise ValueError("unsupported model-call purpose")
    authority = ExecutionAuthority()
    record: dict[str, Any] = {
        "call_id": str(uuid.uuid4()),
        "purpose": purpose,
        "model": model,
        "phase": "ATTEMPTED",
        "status": "UNKNOWN",
        "usage": None,
        "usage_status": "UNKNOWN",
    }
    # Fail closed if an attempt cannot be recorded. No model is invoked first.
    authority.record_model_call(record)
    calls = _CALLS.get()
    if calls is not None:
        calls.append(record)

    def finish(receipt: dict[str, Any]) -> None:
        authority.record_model_call(receipt)
        if calls is not None:
            calls[calls.index(record)] = receipt

    try:
        completed = runner(*args, **kwargs)
    except subprocess.TimeoutExpired:
        finish({**record, "phase": "FINISHED", "status": "TIMEOUT"})
        raise
    except OSError:
        finish({**record, "phase": "FINISHED", "status": "LAUNCH_FAILED"})
        raise
    except Exception:  # record, then propagate unchanged; never retry
        finish({**record, "phase": "FINISHED", "status": "FAILED"})
        raise
    usage: dict[str, int] = {}
    structured = False
    for line in completed.stdout.splitlines():
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if not isinstance(item, dict):
            continue
        if item.get("type") == "turn.completed" and isinstance(item.get("usage"), dict):
            usage = {
                key: value
                for key, value in item["usage"].items()
                if key
                in {
                    "input_tokens",
                    "cached_input_tokens",
                    "output_tokens",
                    "total_tokens",
                    "reasoning_output_tokens",
                }
                and type(value) is int
                and value >= 0
            }
        message = item.get("item", {})
        if isinstance(message, dict) and message.get("type") == "agent_message":
            try:
                structured |= isinstance(json.loads(message.get("text", "")), dict)
            except (ValueError, TypeError):
                pass
    status = (
        "SUCCEEDED"
        if completed.returncode == 0 and structured
        else "INVALID_RESULT"
        if completed.returncode == 0
        else "FAILED"
    )
    finish(
        {
            **record,
            "phase": "FINISHED",
            "status": status,
            "usage": usage or None,
            "usage_status": "REPORTED" if usage else "UNKNOWN",
        }
    )
    return completed
