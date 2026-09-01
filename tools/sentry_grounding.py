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
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from tools.sentry_routine_intent import ROUTINE_TYPES, RoutineIntent, routine_keys
from tools.sentry_weather_intent import WeatherIntent


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


def _local_display(value: Any, display_timezone: str, *, include_date: bool = True) -> str | None:
    """Format an existing authoritative timestamp without changing its source value."""

    timestamp = _parse_time(value)
    if timestamp is None:
        return None
    try:
        local = timestamp.astimezone(ZoneInfo(display_timezone))
    except ZoneInfoNotFoundError as exc:
        raise ValueError("display timezone must be a valid IANA timezone") from exc
    clock = f"{local.strftime('%I').lstrip('0') or '0'}:{local.strftime('%M %p %Z')}"
    if not include_date:
        return clock
    return f"{local.strftime('%B')} {local.day}, {local.year} at {clock}"


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


def _normalize_sessions(sessions: Any, display_timezone: str) -> list[dict[str, Any]]:
    allowed = (
        "session_id", "room_id", "started_at", "ended_at", "status", "start_reason",
        "end_reason", "recovered_after_restart", "end_time_uncertain", "continuity_uncertain",
    )
    output = []
    for session in sessions or []:
        if isinstance(session, dict):
            item = {key: session[key] for key in allowed if key in session}
            for source_key, display_key in (("started_at", "started_at_local_display"), ("ended_at", "ended_at_local_display")):
                display = _local_display(item.get(source_key), display_timezone)
                if display is not None:
                    item[display_key] = display
            output.append(item)
    return output


def _normalize_events(events: Any, display_timezone: str) -> list[dict[str, Any]]:
    allowed = ("event_id", "event_type", "occurred_at", "room_id", "session_id", "source", "confidence", "schema_version")
    output = []
    for event in events or []:
        if not isinstance(event, dict):
            continue
        item = {key: event[key] for key in allowed if key in event}
        display = _local_display(item.get("occurred_at"), display_timezone)
        if display is not None:
            item["occurred_at_local_display"] = display
        payload = event.get("payload")
        if isinstance(payload, dict):
            item["payload"] = {key: payload[key] for key in _ALLOWED_EVENT_PAYLOAD if key in payload}
        output.append(item)
    return output


_ROUTINE_STATISTIC_KEYS = {
    "circular_center_seconds", "circular_center_local_time", "mean_resultant_length",
    "circular_dispersion", "median", "mad", "p25", "p75", "minimum", "maximum",
    "relative_mad",
}
_ROUTINE_SCOPES = {"all_days", "weekday", "weekend", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}


def _normalize_routine(snapshot: Any) -> dict[str, Any] | None:
    if not isinstance(snapshot, dict):
        return None
    required = (
        "routine_key", "routine_type", "scope", "timezone", "algorithm_version",
        "window_start", "window_end", "source_as_of", "generated_at", "sample_count",
        "distinct_date_count", "maturity_status",
    )
    if any(key not in snapshot for key in required):
        return None
    if snapshot["routine_type"] not in ROUTINE_TYPES or snapshot["scope"] not in _ROUTINE_SCOPES:
        return None
    if snapshot["routine_key"] != f"{snapshot['routine_type']}:{snapshot['scope']}":
        return None
    if snapshot["maturity_status"] not in {"insufficient", "observed", "stable"}:
        return None
    if not all(type(snapshot[key]) is int and snapshot[key] >= 0 for key in ("sample_count", "distinct_date_count")):
        return None
    statistics = snapshot.get("statistics")
    exclusions = snapshot.get("exclusions")
    if not isinstance(statistics, dict) or not isinstance(exclusions, dict):
        return None
    return {
        **{key: snapshot[key] for key in required},
        "statistics": {key: statistics[key] for key in _ROUTINE_STATISTIC_KEYS if key in statistics},
        "exclusions": {key: value for key, value in exclusions.items() if isinstance(key, str) and isinstance(value, int)},
    }


_WEATHER_CURRENT_KEYS = {
    "observed_at", "temperature", "apparent_temperature", "wind_chill", "relative_humidity",
    "wind_speed", "wind_direction", "weather_description",
}
_WEATHER_FORECAST_KEYS = {
    "start", "end", "temperature", "temperature_unit", "precipitation_probability",
    "wind_speed", "wind_direction", "short_forecast",
}
_WEATHER_ALERT_KEYS = {
    "id", "event", "severity", "urgency", "certainty", "effective", "onset", "expires", "ends",
    "headline", "description", "instruction",
}


def _normalize_weather(response: Any) -> list[dict[str, Any]]:
    if not isinstance(response, dict):
        return []
    snapshot = response.get("snapshot")
    status = response.get("status") if response.get("status") in {"fresh", "stale", "unavailable"} else "unavailable"
    if not isinstance(snapshot, dict):
        snapshot = {}
    source_data = {
        key: response.get(key, snapshot.get(key))
        for key in ("status", "age_seconds", "fresh_until", "provider", "location_label", "timezone", "fetched_at", "source_updated_at")
        if response.get(key, snapshot.get(key)) is not None
    }
    facts = [{"fact_id": "weather:source-health", "kind": "weather_source_health", "as_of": snapshot.get("fetched_at") or _now_iso(), "data": source_data}]
    if status == "unavailable":
        return facts
    current = snapshot.get("current")
    if isinstance(current, dict) and current:
        facts.append({
            "fact_id": "weather:current", "kind": "weather_current", "as_of": current.get("observed_at") or snapshot.get("fetched_at") or _now_iso(),
            "data": {key: current[key] for key in _WEATHER_CURRENT_KEYS if key in current},
        })
    forecast = snapshot.get("hourly")
    if isinstance(forecast, list):
        normalized_forecast = [
            {key: item[key] for key in _WEATHER_FORECAST_KEYS if key in item}
            for item in forecast[:48] if isinstance(item, dict)
        ]
        if normalized_forecast:
            facts.append({
                "fact_id": "weather:forecast:near-term", "kind": "weather_forecast", "as_of": snapshot.get("fetched_at") or _now_iso(),
                "data": {"periods": normalized_forecast},
            })
    alerts = snapshot.get("alerts")
    if isinstance(alerts, list):
        normalized_alerts = [
            {key: item[key] for key in _WEATHER_ALERT_KEYS if key in item}
            for item in alerts[:10] if isinstance(item, dict)
        ]
        facts.append({
            "fact_id": "weather:alerts", "kind": "weather_alerts", "as_of": snapshot.get("fetched_at") or _now_iso(),
            "data": {"alerts": normalized_alerts},
        })
    return facts


def build_fact_packet(
    responses: dict[str, dict[str, Any]],
    *,
    as_of: str | None = None,
    routine_keys_to_include: set[str] | None = None,
    weather_response: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic, allow-listed packet from API response bodies."""

    evaluated_at = _parse_time(as_of) if as_of else None
    if evaluated_at is None:
        evaluated_at = datetime.now(timezone.utc)
    as_of_value = evaluated_at.isoformat()
    health = responses.get("health", {})
    state = responses.get("state", {})
    display_timezone = health.get("display_timezone", "America/New_York")
    if not isinstance(display_timezone, str):
        raise ValueError("display timezone must be a valid IANA timezone")
    try:
        ZoneInfo(display_timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("display timezone must be a valid IANA timezone") from exc
    perception = health.get("perception") if isinstance(health.get("perception"), dict) else {}
    current_physical_available = bool(perception.get("current_physical_available"))
    perception_as_of = perception.get("heartbeat_updated_at") if isinstance(perception.get("heartbeat_updated_at"), str) else as_of_value
    sessions = _normalize_sessions(responses.get("sessions", {}).get("sessions", []), display_timezone)
    persons = [
        {
            key: item[key]
            for key in ("person_id", "display_name", "enrollment_status", "created_at", "updated_at")
            if key in item
        }
        for item in responses.get("persons", {}).get("persons", [])
        if isinstance(item, dict)
    ]
    events = _normalize_events(responses.get("events", {}).get("events", []), display_timezone)
    primary_user_events = _normalize_events(
        responses.get("primary_user_events", {}).get("events", []), display_timezone
    )
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
            "fact_id": "perception-runtime",
            "kind": "perception_runtime_health",
            "as_of": perception_as_of,
            "data": {
                "status": perception.get("status", "missing"),
                "heartbeat_updated_at": perception.get("heartbeat_updated_at"),
                "age_seconds": perception.get("age_seconds"),
                "process_alive": bool(perception.get("process_alive")),
                "camera_state": perception.get("camera_state"),
                "room_state": perception.get("room_state"),
                "current_physical_available": current_physical_available,
                "reason": perception.get("reason"),
                "display_timezone": display_timezone,
            },
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

    if current_physical_available:
        facts[2:2] = [
            {
                "fact_id": "current-room-state",
                "kind": "room_state",
                "as_of": perception_as_of,
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
                "as_of": perception_as_of,
                "data": {"people": current_people},
            },
        ]

    if routine_keys_to_include is not None:
        routine_items = []
        for raw in responses.get("routines", {}).get("routines", []):
            normalized = _normalize_routine(raw)
            if normalized and normalized["routine_key"] in routine_keys_to_include:
                routine_items.append(normalized)
        facts.append({
            "fact_id": "routine-source",
            "kind": "derived_routine_source",
            "as_of": as_of_value,
            "data": {"snapshot_count": len(routine_items), "requested_keys": sorted(routine_keys_to_include)},
        })
        for item in sorted(routine_items, key=lambda value: value["routine_key"]):
            facts.append({
                "fact_id": f"routine:{item['routine_key']}",
                "kind": "derived_routine",
                "as_of": item["source_as_of"],
                "data": {
                    key: item[key]
                    for key in (
                        "routine_type", "scope", "timezone", "algorithm_version", "window_start", "window_end",
                        "source_as_of", "generated_at", "sample_count", "distinct_date_count", "maturity_status",
                        "statistics", "exclusions",
                    )
                },
            })

    if weather_response is not None:
        facts.extend(_normalize_weather(weather_response))

    open_sessions = [session for session in sessions if session.get("status") == "open"]
    if current_physical_available and open_sessions:
        session = open_sessions[0]
        facts.append(
            {
                "fact_id": "current-open-session",
                "kind": "derived_open_session",
                "as_of": as_of_value,
                "data": {
                    "session_id": session.get("session_id"),
                    "started_at": session.get("started_at"),
                    "started_at_local_display": session.get("started_at_local_display"),
                    "start_reason": session.get("start_reason"),
                    "recovered_after_restart": bool(session.get("recovered_after_restart")),
                    "continuity_uncertain": bool(session.get("continuity_uncertain")),
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
                    "first_identified_at_local_display": _local_display(identified[0].get("occurred_at"), display_timezone),
                    "most_recent_identified_at": identified[-1].get("occurred_at"),
                    "most_recent_identified_at_local_display": _local_display(identified[-1].get("occurred_at"), display_timezone),
                    "person_id": "primary_user",
                    "display_name": next(
                        (item.get("display_name") for item in persons if item.get("person_id") == "primary_user"),
                        None,
                    ),
                },
            }
        )

    if "primary_user_events" in responses:
        primary_today = [
            event for event in primary_user_events
            if event.get("event_type") == "person.identified"
            and (event.get("payload") or {}).get("person_id") == "primary_user"
        ]
        primary_today.sort(key=lambda event: str(event.get("occurred_at", "")))
        local_date = evaluated_at.astimezone(ZoneInfo(display_timezone)).date().isoformat()
        first = primary_today[0] if primary_today else None
        latest = primary_today[-1] if primary_today else None
        facts.append(
            {
                "fact_id": "primary-user-presence-confirmation",
                "kind": "derived_primary_presence_confirmation",
                "as_of": as_of_value,
                "data": {
                    "person_id": "primary_user",
                    "display_name": next(
                        (item.get("display_name") for item in persons if item.get("person_id") == "primary_user"),
                        None,
                    ),
                    "local_date": local_date,
                    "first_confirmed_at": first.get("occurred_at") if first else None,
                    "first_confirmed_at_local_display": first.get("occurred_at_local_display") if first else None,
                    "most_recent_confirmed_at": latest.get("occurred_at") if latest else None,
                    "most_recent_confirmed_at_local_display": latest.get("occurred_at_local_display") if latest else None,
                    "confirmation_count": len(primary_today),
                    "exact_arrival_known": False,
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
                    "occurred_at_local_display": _local_display(latest_empty.get("occurred_at"), display_timezone),
                    "end_time_uncertain": bool((latest_empty.get("payload") or {}).get("end_time_uncertain")),
                    "recovered_after_restart": bool((latest_empty.get("payload") or {}).get("recovered_after_restart")),
                },
            }
        )
    return {"as_of": as_of_value, "facts": facts}


def build_proactive_fact_packet(
    store: Any,
    event: dict[str, Any],
    policy: dict[str, Any],
    *,
    as_of: str | None = None,
) -> dict[str, Any]:
    """Build a bounded M5 packet from the same allow-list as M4.

    This deliberately consumes structured store records rather than exposing
    the SQLite connection or arbitrary event payloads to the reasoning layer.
    """

    evaluated_at = _parse_time(as_of) if as_of else None
    if evaluated_at is None:
        evaluated_at = datetime.now(timezone.utc)
    state_record = store.current_state(event.get("room_id", "office"))
    sessions = store.sessions(event.get("room_id", "office"), limit=20)
    persons = store.persons()
    events = store.events(event.get("room_id", "office"), limit=100)
    responses = {
        "health": {
            "ok": True,
            "db_available": True,
            "schema_version": getattr(store, "health", lambda: {})().get("schema_version"),
            "display_timezone": "America/New_York",
            "perception": {
                "status": "fresh",
                "process_alive": True,
                "current_physical_available": True,
                "camera_state": "online",
                "room_state": state_record.state if state_record else "unknown",
                "heartbeat_updated_at": evaluated_at.isoformat(),
                "age_seconds": 0.0,
                "reason": None,
            },
        },
        "state": state_record.__dict__ if state_record else {"room_id": event.get("room_id", "office"), "state": "unknown"},
        "sessions": {"sessions": sessions},
        "persons": {"persons": persons},
        "events": {"events": events},
    }
    packet = build_fact_packet(responses, as_of=evaluated_at.isoformat())
    event_payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    facts = packet["facts"]
    facts.append(
        {
            "fact_id": "proactive-candidate",
            "kind": "proactive_candidate",
            "as_of": evaluated_at.isoformat(),
            "data": {
                "event_id": event.get("event_id"),
                "event_type": event.get("event_type"),
                "room_id": event.get("room_id", "office"),
                "session_id": event.get("session_id"),
                "person_id": event_payload.get("person_id"),
                "occurred_at": event.get("occurred_at"),
                "event_age_seconds": max(0.0, (evaluated_at - (_parse_time(event.get("occurred_at")) or evaluated_at)).total_seconds()),
            },
        }
    )
    facts.append(
        {
            "fact_id": "proactive-policy",
            "kind": "proactive_policy_context",
            "as_of": evaluated_at.isoformat(),
            "data": {
                "candidate_key": policy.get("candidate_key"),
                "cooldown_active": bool(policy.get("cooldown_active")),
                "hourly_spoken_count": int(policy.get("hourly_spoken_count", 0)),
                "hourly_spoken_limit": int(policy.get("hourly_spoken_limit", 0)),
                "same_session_action_count": int(policy.get("same_session_action_count", 0)),
                "same_session_action_limit": int(policy.get("same_session_action_limit", 0)),
            },
        }
    )
    recent_actions = []
    for action in store.proactive_actions(event.get("room_id", "office"), limit=20):
        recent_actions.append({
            key: action.get(key)
            for key in (
                "action_id", "source_event_id", "candidate_key", "event_type", "person_id", "session_id",
                "event_timestamp", "evaluated_at", "eligibility_result", "suppression_reason", "judge_decision",
                "delivery_status",
            )
            if action.get(key) is not None
        })
    facts.append(
        {
            "fact_id": "recent-proactive-decisions",
            "kind": "recent_proactive_decisions",
            "as_of": evaluated_at.isoformat(),
            "data": {"actions": recent_actions},
        }
    )
    weather_context = policy.get("weather_context")
    if isinstance(weather_context, dict):
        facts.append(
            {
                "fact_id": "weather-context-health",
                "kind": "weather_context_health",
                "as_of": evaluated_at.isoformat(),
                "data": {
                    "status": "fresh",
                    "location_label": weather_context.get("location_label"),
                    "fetched_at": weather_context.get("fetched_at"),
                },
            }
        )
        facts.append(
            {
                "fact_id": "weather-near-term-precipitation",
                "kind": "weather_near_term_precipitation",
                "as_of": evaluated_at.isoformat(),
                "data": {
                    "forecast_period_start": weather_context.get("forecast_period_start"),
                    "forecast_period_end": weather_context.get("forecast_period_end"),
                    "precipitation_probability": weather_context.get("max_precipitation_probability"),
                    "short_forecast": weather_context.get("short_forecast"),
                    "horizon_minutes": weather_context.get("horizon_minutes"),
                },
            }
        )
    return packet


@dataclass(frozen=True)
class Retrieval:
    query_id: str
    packet: dict[str, Any] | None
    error: str | None = None

    @property
    def available(self) -> bool:
        return self.packet is not None and self.error is None


def retrieve_fact_packet(
    base_url: str,
    *,
    room_id: str = "office",
    timeout: float = 5.0,
    routine_intent: RoutineIntent | None = None,
    weather_intent: WeatherIntent | None = None,
) -> Retrieval:
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
        display_timezone = health.get("display_timezone", "America/New_York")
        if not isinstance(display_timezone, str):
            raise ValueError("display timezone must be a valid IANA timezone")
        try:
            local_now = datetime.now(ZoneInfo(display_timezone))
        except ZoneInfoNotFoundError as exc:
            raise ValueError("display timezone must be a valid IANA timezone") from exc
        day_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
        responses["primary_user_events"] = _get_json(
            base_url,
            "/v1/events",
            params={
                "room_id": room_id,
                "limit": "20",
                "event_type": "person.identified",
                "person_id": "primary_user",
                "since": day_start.isoformat(),
            },
            timeout=timeout,
        )
        if routine_intent is not None:
            responses["routines"] = _get_json(
                base_url,
                "/v1/routines",
                params={"room_id": room_id, "limit": "100"},
                timeout=timeout,
            )
            if not isinstance(responses["routines"].get("routines"), list):
                raise ValueError("/v1/routines did not return a routines list")
        if weather_intent is not None:
            responses["weather"] = _get_json(base_url, "/v1/weather", params={"room_id": room_id}, timeout=timeout)
        return Retrieval(
            query_id,
            build_fact_packet(
                responses,
                routine_keys_to_include=set(routine_keys(routine_intent)) if routine_intent is not None else None,
                weather_response=responses.get("weather"),
            ),
            None,
        )
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
