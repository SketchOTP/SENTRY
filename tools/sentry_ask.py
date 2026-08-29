"""Ask one natural-language question using current SENTRY API facts and one Luna turn."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.sentry_codex_bridge import invoke_grounded_query  # noqa: E402
from tools.sentry_grounding import (  # noqa: E402
    retrieve_fact_packet,
    unavailable_response,
    validate_grounded_response,
)


def ask(
    question: str,
    *,
    base_url: str = "http://127.0.0.1:48174",
    room_id: str = "office",
    effort: str = "low",
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    retrieval = retrieve_fact_packet(base_url, room_id=room_id)
    if not retrieval.available:
        return {
            "query_id": retrieval.query_id,
            "as_of": None,
            **unavailable_response(retrieval.error or "SENTRY state is unavailable"),
            "luna_invocations": 0,
        }

    assert retrieval.packet is not None
    fact_ids = {fact["fact_id"] for fact in retrieval.packet["facts"]}
    invocation = invoke_grounded_query(
        question,
        retrieval.packet,
        effort=effort,
        timeout_seconds=timeout_seconds,
    )
    if not invocation.get("ok"):
        return {
            "query_id": retrieval.query_id,
            "as_of": retrieval.packet["as_of"],
            **unavailable_response("bounded Luna invocation failed"),
            "luna_invocations": 1,
            "luna_error": invocation.get("error"),
        }
    result = invocation.get("result")
    validation_error = validate_grounded_response(result, fact_ids)
    if validation_error:
        return {
            "query_id": retrieval.query_id,
            "as_of": retrieval.packet["as_of"],
            **unavailable_response(f"bounded Luna response failed validation: {validation_error}"),
            "luna_invocations": 1,
        }
    return {
        "query_id": retrieval.query_id,
        "as_of": retrieval.packet["as_of"],
        **result,
        "model": invocation.get("model"),
        "reasoning_effort": invocation.get("reasoning_effort"),
        "usage": invocation.get("usage", {}),
        "luna_invocations": 1,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    parser.add_argument("--base-url", default="http://127.0.0.1:48174")
    parser.add_argument("--room-id", default="office")
    parser.add_argument("--effort", choices=("none", "low", "medium", "high", "xhigh", "max"), default="low")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    args = parser.parse_args()
    result = ask(
        args.question,
        base_url=args.base_url,
        room_id=args.room_id,
        effort=args.effort,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0 if result["grounding"] != "unavailable" or result["limitations"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
