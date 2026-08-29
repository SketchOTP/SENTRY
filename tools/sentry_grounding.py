"""Retrieve and normalize a bounded SENTRY fact packet from the localhost API."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


GROUNDING_STATES = {"supported", "partial", "unavailable"}
_ALLOWED_EVENT_PAYLOAD = {
    "recovered_after_restart",
    "end_time_uncertain",
    "track_id",
    "person_id",
    "identity_state",
    "identity_confidence",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _elapsed_seconds(started_at: Any, as_of: datetime) -> float | None:
    started = _parse_time(started_at)
    if started is None:
        return None
    return max(0.0, (as_of - started).total_seconds())


def _get_json(base_url: str, path: str, *, params: dict[str, str] | None = None, timeout: float = 5.0) -> dict[str, Any]:
    query = f"?{urlencode(params)}" if params else ""
    request = Request(f"{base_url.rstrip('/')}{path}{query}", headers={"Accept": "application/json"})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - URL is operator-configured localhost
        value = json.loads(response.read().decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} did not return a JSON object")
    return value


def _normalize_people(state: dict[str, Any], persons: list[dict[str, Any]]) -> list[dict[str, Any]]:
    names = {
        item.get("person_id"): item.get("display_name")
        for item in persons
        if isinstance(item, dict) and item.get("person_id")
    }
    output = []
    for person in state.get("people", []) or []:
        if not isinstance(person, dict):
            continue
        item: dict[str, Any] = {}
        for key in ("track_id", "person_id", "identity_state", "identity_confidence", "visible", "missed_frames"):
            if key in person:
                item[key] = person[key]
        person_id = item.get("person_id")
        if person_id in names:
            item["display_name"] = names[person_id]
        output.append(item)
    return output


def _normalize_sessions(sessions: Any) -> list[dict[str, Any]]:
    allowed = (
        "session_id", "room_id", "started_at", "ended_at", "status", "start_reason",
        "end_reason", "recovered_after_restart", "end_time_uncertain",
    )
    output = []
    for session in sessions or []:
        if isinstance(session, dict):
            output.append({key: session[key] for key in allowed if key in session})
    return output


def _normalize_events(events: Any) -> list[dict[str, Any]]:
    allowed = ("event_id", "event_type", "occurred_at", "room_id", "session_id", "source", "confidence", "schema_version")
    output = []
    for event in events or []:
        if not isinstance(event, dict):
            continue
        item = {key: event[key] for key in allowed if key in event}
        payload = event.get("payload")
        if isinstance(payload, dict):
            item["payload"] = {key: payload[key] for key in _ALLOWED_EVENT_PAYLOAD if key in payload}
        output.append(item)
    return output


def build_fact_packet(
    responses: dict[str, dict[str, Any]],
    *,
    as_of: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic, allow-listed packet from API response bodies."""

    evaluated_at = _parse_time(as_of) if as_of else None
    if evaluated_at is None:
        evaluated_at = datetime.now(timezone.utc)
    as_of_value = evaluated_at.isoformat()
    health = responses.get("health", {})
    state = responses.get("state", {})
    sessions = _normalize_sessions(responses.get("sessions", {}).get("sessions", []))
    persons = [
        {
            key: item[key]
            for key in ("person_id", "display_name", "enrollment_status", "created_at", "updated_at")
            if key in item
        }
        for item in responses.get("persons", {}).get("persons", [])
        if isinstance(item, dict)
    ]
    events = _normalize_events(responses.get("events", {}).get("events", []))
    current_people = _normalize_people(state, persons)

    facts: list[dict[str, Any]] = [
        {
            "fact_id": "source-health",
            "kind": "source_health",
            "as_of": as_of_value,
            "data": {
                "api_ok": bool(health.get("ok")),
                "db_available": bool(health.get("db_available")),
                "schema_version": health.get("schema_version"),
                "mirror_status": (health.get("atlas_mirror") or {}).get("status"),
            },
        },
        {
            "fact_id": "current-room-state",
            "kind": "room_state",
            "as_of": state.get("updated_at") or as_of_value,
            "data": {
                "room_id": state.get("room_id", "office"),
                "state": state.get("state", "unknown"),
                "camera_state": state.get("camera_state"),
                "person_count": state.get("person_count", 0),
            },
        },
        {
            "fact_id": "current-room-people",
            "kind": "current_people",
            "as_of": state.get("updated_at") or as_of_value,
            "data": {"people": current_people},
        },
        {
            "fact_id": "enrolled-persons",
            "kind": "enrolled_persons",
            "as_of": as_of_value,
            "data": {"persons": persons},
        },
        {
            "fact_id": "room-sessions",
            "kind": "presence_sessions",
            "as_of": as_of_value,
            "data": {"sessions": sessions},
        },
        {
            "fact_id": "room-events",
            "kind": "semantic_events",
            "as_of": as_of_value,
            "data": {"events": events},
        },
    ]

    open_sessions = [session for session in sessions if session.get("status") == "open"]
    if open_sessions:
        session = open_sessions[0]
        facts.append(
            {
                "fact_id": "current-open-session",
                "kind": "derived_open_session",
                "as_of": as_of_value,
                "data": {
                    "session_id": session.get("session_id"),
                    "started_at": session.get("started_at"),
                    "elapsed_seconds": _elapsed_seconds(session.get("started_at"), evaluated_at),
                },
            }
        )

    identified = [
        event for event in events
        if event.get("event_type") == "person.identified"
        and (event.get("payload") or {}).get("person_id") == "primary_user"
    ]
    if identified:
        identified.sort(key=lambda event: str(event.get("occurred_at", "")))
        facts.append(
            {
                "fact_id": "primary-user-identification",
                "kind": "derived_primary_identification",
                "as_of": as_of_value,
                "data": {
                    "first_identified_at": identified[0].get("occurred_at"),
                    "most_recent_identified_at": identified[-1].get("occurred_at"),
                    "person_id": "primary_user",
                    "display_name": next(
                        (item.get("display_name") for item in persons if item.get("person_id") == "primary_user"),
                        None,
                    ),
                },
            }
        )

    empty_events = [event for event in events if event.get("event_type") == "room.became_empty"]
    if empty_events:
        latest_empty = max(empty_events, key=lambda event: str(event.get("occurred_at", "")))
        facts.append(
            {
                "fact_id": "last-confirmed-empty",
                "kind": "derived_last_empty",
                "as_of": as_of_value,
                "data": {
                    "occurred_at": latest_empty.get("occurred_at"),
                    "end_time_uncertain": bool((latest_empty.get("payload") or {}).get("end_time_uncertain")),
                    "recovered_after_restart": bool((latest_empty.get("payload") or {}).get("recovered_after_restart")),
                },
            }
        )
    return {"as_of": as_of_value, "facts": facts}


@dataclass(frozen=True)
class Retrieval:
    query_id: str
    packet: dict[str, Any] | None
    error: str | None = None

    @property
    def available(self) -> bool:
        return self.packet is not None and self.error is None


def retrieve_fact_packet(base_url: str, *, room_id: str = "office", timeout: float = 5.0) -> Retrieval:
    """Read health first, then the bounded state/history API surface."""

    query_id = str(uuid.uuid4())
    try:
        health = _get_json(base_url, "/health", params={"room_id": room_id}, timeout=timeout)
        if not health.get("ok") or not health.get("db_available"):
            return Retrieval(query_id, None, "SENTRY state API or database is unavailable")
        responses = {"health": health}
        for name, path in (
            ("state", f"/v1/rooms/{room_id}/state"),
            ("sessions", f"/v1/rooms/{room_id}/sessions"),
            ("persons", "/v1/persons"),
            ("events", "/v1/events"),
        ):
            responses[name] = _get_json(base_url, path, params={"room_id": room_id, "limit": "100"}, timeout=timeout)
        return Retrieval(query_id, build_fact_packet(responses), None)
    except (OSError, HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        return Retrieval(query_id, None, f"SENTRY state retrieval failed: {type(exc).__name__}")


def validate_grounded_response(response: Any, supplied_fact_ids: set[str]) -> str | None:
    """Validate the model response against the bounded grounding contract."""

    if not isinstance(response, dict):
        return "response is not an object"
    if set(response) != {"answer", "grounding", "fact_ids", "limitations"}:
        return "response fields do not match the grounded response contract"
    if not isinstance(response["answer"], str) or not response["answer"].strip():
        return "answer must be a non-empty string"
    if response["grounding"] not in GROUNDING_STATES:
        return "grounding must be supported, partial, or unavailable"
    fact_ids = response["fact_ids"]
    if not isinstance(fact_ids, list) or any(not isinstance(value, str) for value in fact_ids):
        return "fact_ids must be a list of strings"
    if len(set(fact_ids)) != len(fact_ids):
        return "fact_ids must be unique"
    if not set(fact_ids).issubset(supplied_fact_ids):
        return "response cites an unknown fact_id"
    if response["grounding"] in {"supported", "partial"} and not fact_ids:
        return "supported or partial response must cite at least one fact"
    if not isinstance(response["limitations"], list) or any(
        not isinstance(value, str) or not value.strip() for value in response["limitations"]
    ):
        return "limitations must be a list of non-empty strings"
    return None


def unavailable_response(reason: str) -> dict[str, Any]:
    return {
        "answer": "SENTRY state is currently unavailable, so I can't answer that reliably.",
        "grounding": "unavailable",
        "fact_ids": [],
        "limitations": [reason],
    }
