"""Ask one natural-language question using current SENTRY API facts and one Luna turn."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.sentry_codex_bridge import invoke_grounded_query  # noqa: E402
from tools.sentry_grounding import (  # noqa: E402
    _get_json,
    retrieve_fact_packet,
    unavailable_response,
    validate_grounded_response,
)
from tools.sentry_routine_intent import routine_keys, select_routine_intent
from tools.sentry_preference_intent import PreferenceIntent, select_preference_intent
from tools.sentry_reminder_intent import ReminderIntent, select_reminder_intent
from tools.sentry_weather_intent import WeatherIntent, select_weather_intent


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


def _weather_unavailable_response(reason: str, *, stale: bool = False) -> dict[str, Any]:
    if stale:
        answer = "SENTRY has weather data, but it is stale, so I won't present it as current."
    else:
        answer = "SENTRY weather context is currently unavailable, so I can't answer that reliably."
    return {
        "answer": answer,
        "grounding": "unavailable",
        "fact_ids": [],
        "limitations": [reason],
    }


def _weather_fact_requirement(intent: WeatherIntent) -> str:
    return {
        "current": "weather:current",
        "forecast": "weather:forecast:near-term",
        "alerts": "weather:alerts",
    }.get(intent.topic, "weather:current")


def _preference_response(value: str, *, fact_id: str = "preference:proactivity.primary_user_session_acknowledgement") -> dict[str, Any]:
    if value == "suppress":
        answer = "Your greeting preference is disabled, so I will not proactively acknowledge you when I first recognize you in a session."
    elif value == "allow":
        answer = "Your greeting preference is enabled; I may consider a brief acknowledgement when I first recognize you in a session."
    else:
        answer = "You have no explicit greeting preference saved, so SENTRY is using its default acknowledgement policy."
    return {"answer": answer, "grounding": "supported", "fact_ids": [fact_id], "limitations": []}


def _post_json(base_url: str, path: str, payload: dict[str, Any], *, timeout: float = 5.0) -> dict[str, Any]:
    request = Request(
        f"{base_url.rstrip('/')}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - URL is operator-configured localhost
            value = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            error_value = json.loads(exc.read().decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            error_value = {}
        raise ValueError(error_value.get("error", f"{path} returned HTTP {exc.code}")) from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path} did not return a JSON object")
    return value


def _reminder_response(intent: ReminderIntent, *, base_url: str, room_id: str, source_surface: str, source_request_id: str) -> dict[str, Any]:
    try:
        if intent.kind == "create":
            response = _post_json(base_url, "/v1/reminders", {
                "person_id": "primary_user", "room_id": room_id,
                "trigger_kind": "next_primary_user_office_session", "message": intent.message,
                "source_surface": source_surface, "source_request_id": source_request_id,
            })
            reminder = response.get("reminder")
            if not isinstance(reminder, dict):
                raise ValueError("reminder response is invalid")
            return {
                "answer": "I saved that reminder for your next distinct office session.",
                "grounding": "supported", "fact_ids": [], "limitations": [],
                "reminder": reminder,
            }
        response = _get_json(base_url, "/v1/reminders", params={"person_id": "primary_user", "room_id": room_id})
        reminders = response.get("reminders")
        if not isinstance(reminders, list):
            raise ValueError("reminder list response is invalid")
        pending = next((item for item in reminders if isinstance(item, dict) and item.get("status") == "pending"), None)
        if intent.kind == "query":
            if pending is None:
                return {"answer": "You do not have a pending office reminder.", "grounding": "supported", "fact_ids": [], "limitations": []}
            return {
                "answer": f"Your next-office reminder is: {pending.get('message', '')}",
                "grounding": "supported", "fact_ids": [], "limitations": [], "reminder": pending,
            }
        if pending is None:
            return {"answer": "You do not have a pending office reminder to cancel.", "grounding": "supported", "fact_ids": [], "limitations": []}
        response = _post_json(base_url, f"/v1/reminders/{pending['reminder_id']}/cancel", {
            "source_surface": source_surface, "source_request_id": source_request_id,
        })
        reminder = response.get("reminder")
        if not isinstance(reminder, dict):
            raise ValueError("reminder cancellation response is invalid")
        return {"answer": "I cancelled your pending office reminder.", "grounding": "supported", "fact_ids": [], "limitations": [], "reminder": reminder}
    except ValueError as exc:
        message = str(exc)
        if "already pending" in message:
            answer = "You already have an office reminder waiting. Cancel it first if you want to replace it."
            return {"answer": answer, "grounding": "supported", "fact_ids": [], "limitations": []}
        return {
            "answer": "SENTRY could not update or read that office reminder reliably right now.",
            "grounding": "unavailable", "fact_ids": [], "limitations": [message],
        }


def _deterministic_preference_result(
    intent: PreferenceIntent, *, base_url: str, person_id: str, source_surface: str, source_request_id: str,
) -> dict[str, Any]:
    try:
        if intent.kind == "query":
            preferences = _get_json(base_url, "/v1/preferences", params={"person_id": person_id})
            value = preferences.get("current_value")
            if value not in {"default", "allow", "suppress"}:
                raise ValueError("preference response is invalid")
            result = _preference_response(value)
            if intent.query_topic == "why":
                if value == "suppress":
                    result["answer"] = "I did not greet you because your saved preference suppresses primary-user session acknowledgements."
                else:
                    result["answer"] = "I don't have an explicit suppression preference saved; I may have chosen silence under the normal proactive policy."
                    result["limitations"] = ["the latest proactive decision was not included in this bounded preference lookup"]
            return result
        if intent.kind == "write":
            payload = {
                "person_id": person_id,
                "operation": intent.operation,
                "value": intent.value,
                "source_surface": source_surface,
                "source_request_id": source_request_id,
            }
            response = _post_json(base_url, "/v1/preferences", payload)
            preference = response.get("preference")
            if not isinstance(preference, dict):
                raise ValueError("preference mutation response is invalid")
            current = response.get("current_value")
            result = _preference_response(current)
            result["answer"] = {
                "set": "I saved your preference: I will suppress primary-user session acknowledgements." if intent.value == "suppress" else "I saved your preference: primary-user session acknowledgements are allowed again.",
                "clear": "I forgot your greeting preference and restored the default policy.",
            }.get(str(intent.operation), "Your preference was saved.")
            result["preference_event_id"] = preference.get("preference_event_id")
            return result
        if intent.kind == "feedback":
            recent = _get_json(base_url, "/v1/proactive-actions/recent", params={"person_id": person_id, "window_seconds": "600"})
            action = recent.get("action")
            if not isinstance(action, dict) or not action.get("action_id"):
                return {
                    "answer": "I couldn't safely match that feedback to one recent delivered acknowledgement, so I did not save it.",
                    "grounding": "partial", "fact_ids": [],
                    "limitations": ["no single unambiguous delivered proactive action within the last 10 minutes"],
                }
            response = _post_json(base_url, "/v1/proactive-feedback", {
                "action_id": action["action_id"], "person_id": person_id,
                "feedback_type": intent.feedback_type, "source_surface": source_surface,
                "source_request_id": source_request_id,
            })
            feedback = response.get("feedback")
            if not isinstance(feedback, dict):
                raise ValueError("feedback response is invalid")
            result = {
                "answer": "I saved that feedback." if intent.feedback_type != "do_not_repeat" else "I saved that feedback and disabled future primary-user session acknowledgements.",
                "grounding": "supported", "fact_ids": ["recent-proactive-action"], "limitations": [],
                "feedback_id": feedback.get("feedback_id"),
            }
            if feedback.get("resulting_preference_event_id"):
                result["preference_event_id"] = feedback["resulting_preference_event_id"]
            return result
    except Exception as exc:  # noqa: BLE001 - deterministic API failure is explicit
        return {
            "answer": "SENTRY could not update or read that preference reliably right now.",
            "grounding": "unavailable", "fact_ids": [],
            "limitations": [f"preference API unavailable: {type(exc).__name__}"],
        }
    return {}


def ask(
    question: str,
    *,
    base_url: str = "http://127.0.0.1:48174",
    room_id: str = "office",
    effort: str = "low",
    timeout_seconds: int = 120,
    source_surface: str = "sentry_ask",
) -> dict[str, Any]:
    reminder_intent = select_reminder_intent(question)
    request_id = str(uuid.uuid4())
    if reminder_intent is not None:
        if reminder_intent.kind == "unsupported":
            result = {
                "answer": "I only support reminders for your next distinct office session right now.",
                "grounding": "unavailable", "fact_ids": [],
                "limitations": ["scheduled, recurring, weather, and leave-the-house reminders are not supported"],
            }
        else:
            result = _reminder_response(
                reminder_intent, base_url=base_url, room_id=room_id,
                source_surface=source_surface, source_request_id=request_id,
            )
        return {"query_id": request_id, "as_of": None, **result, "luna_invocations": 0}
    preference_intent = select_preference_intent(question)
    if preference_intent is not None:
        if preference_intent.kind == "unsupported_memory":
            return {
                "query_id": request_id, "as_of": None,
                "answer": "I don't support storing that kind of preference yet.",
                "grounding": "unavailable", "fact_ids": [],
                "limitations": ["only primary-user session acknowledgement preferences are supported"],
                "luna_invocations": 0,
            }
        result = _deterministic_preference_result(
            preference_intent, base_url=base_url, person_id="primary_user",
            source_surface=source_surface, source_request_id=request_id,
        )
        return {"query_id": request_id, "as_of": None, **result, "luna_invocations": 0}
    weather_intent = select_weather_intent(question)
    routine_intent = select_routine_intent(question)
    if weather_intent is None and routine_intent is not None and routine_intent.unsupported:
        return {
            "query_id": None,
            "as_of": None,
            **_unsupported_routine_response(),
            "luna_invocations": 0,
        }
    retrieval = retrieve_fact_packet(
        base_url, room_id=room_id, routine_intent=routine_intent, weather_intent=weather_intent,
    )
    if not retrieval.available:
        unavailable = (
            _weather_unavailable_response(retrieval.error or "SENTRY weather context is unavailable")
            if weather_intent is not None
            else _routine_source_unavailable_response(retrieval.error or "SENTRY routine history is unavailable")
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
    if weather_intent is not None:
        source_health = next((fact for fact in retrieval.packet["facts"] if fact.get("fact_id") == "weather:source-health"), None)
        source_data = source_health.get("data", {}) if isinstance(source_health, dict) else {}
        status = source_data.get("status")
        if status != "fresh":
            reason = "weather source is unavailable" if status == "unavailable" else f"weather source status is {status or 'unknown'}"
            age = source_data.get("age_seconds")
            if age is not None:
                reason += f"; last snapshot age is {float(age) / 60:.1f} minutes"
            return {
                "query_id": retrieval.query_id,
                "as_of": retrieval.packet["as_of"],
                **_weather_unavailable_response(reason, stale=status == "stale"),
                "luna_invocations": 0,
            }
        required_fact = _weather_fact_requirement(weather_intent)
        if required_fact not in fact_ids:
            return {
                "query_id": retrieval.query_id,
                "as_of": retrieval.packet["as_of"],
                **_weather_unavailable_response(f"fresh weather snapshot has no {weather_intent.topic} data"),
                "luna_invocations": 0,
            }
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
