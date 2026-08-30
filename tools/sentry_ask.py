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
from tools.sentry_routine_intent import routine_keys, select_routine_intent


def _insufficient_routine_response(fact_ids: list[str], facts: list[dict[str, Any]]) -> dict[str, Any]:
    details = "; ".join(
        (
            f"{fact['data'].get('sample_count', 0)} qualifying observation"
            f"{'s' if fact['data'].get('sample_count', 0) != 1 else ''} across "
            f"{fact['data'].get('distinct_date_count', 0)} date"
            f"{'s' if fact['data'].get('distinct_date_count', 0) != 1 else ''}"
        )
        for fact in facts
    ) or "no qualifying routine observations"
    return {
        "answer": f"I don't have enough qualifying history to describe a reliable routine yet ({details}).",
        "grounding": "unavailable",
        "fact_ids": fact_ids,
        "limitations": ["routine evidence is insufficient; this is a sparse-history result, not a source outage"],
    }


def _unsupported_routine_response() -> dict[str, Any]:
    return {
        "answer": "I don't have a supported routine statistic for that yet, so I can't answer it reliably.",
        "grounding": "unavailable",
        "fact_ids": [],
        "limitations": ["SENTRY has no activity or causal routine evidence for that question"],
    }


def _routine_source_unavailable_response(reason: str) -> dict[str, Any]:
    return {
        "answer": "SENTRY's routine history is currently unavailable, so I can't answer that reliably.",
        "grounding": "unavailable",
        "fact_ids": [],
        "limitations": [reason],
    }


def ask(
    question: str,
    *,
    base_url: str = "http://127.0.0.1:48174",
    room_id: str = "office",
    effort: str = "low",
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    routine_intent = select_routine_intent(question)
    if routine_intent is not None and routine_intent.unsupported:
        return {
            "query_id": None,
            "as_of": None,
            **_unsupported_routine_response(),
            "luna_invocations": 0,
        }
    retrieval = retrieve_fact_packet(base_url, room_id=room_id, routine_intent=routine_intent)
    if not retrieval.available:
        unavailable = (
            _routine_source_unavailable_response(retrieval.error or "SENTRY routine history is unavailable")
            if routine_intent is not None
            else unavailable_response(retrieval.error or "SENTRY state is unavailable")
        )
        return {
            "query_id": retrieval.query_id,
            "as_of": None,
            **unavailable,
            "luna_invocations": 0,
        }

    assert retrieval.packet is not None
    fact_ids = {fact["fact_id"] for fact in retrieval.packet["facts"]}
    if routine_intent is not None:
        requested_ids = [f"routine:{key}" for key in routine_keys(routine_intent)]
        routine_facts = [fact for fact in retrieval.packet["facts"] if fact.get("fact_id") in requested_ids]
        if not routine_facts or all(fact["data"].get("maturity_status") == "insufficient" for fact in routine_facts):
            return {
                "query_id": retrieval.query_id,
                "as_of": retrieval.packet["as_of"],
                **_insufficient_routine_response([fact["fact_id"] for fact in routine_facts], routine_facts),
                "luna_invocations": 0,
            }
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
