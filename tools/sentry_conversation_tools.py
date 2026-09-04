"""Strict, localhost-backed tools for SENTRY's conversational orchestrator.

These adapters deliberately expose a small typed view of existing SENTRY API
surfaces.  They never provide SQLite, filesystem, shell, network, raw audio,
coordinates, or biometric access to the model.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from tools.sentry_grounding import (
    _get_json,
    _normalize_routine,
    _normalize_weather,
    build_fact_packet,
)
from tools.sentry_local_api import post_json
from tools.sentry_routine_intent import ROUTINE_TYPES


READ_TOOLS = {
    "get_current_office_state",
    "get_office_history",
    "get_office_reminders",
    "get_alarms",
    "get_acknowledgement_preference",
    "get_recent_proactive_action",
    "get_routines",
    "get_weather",
    "use_native_web_search",
}
MUTATION_TOOLS = {
    "create_next_office_reminder",
    "cancel_pending_office_reminder",
    "set_acknowledgement_preference",
    "clear_acknowledgement_preference",
    "record_proactive_feedback",
    "create_one_shot_alarm",
    "cancel_alarm",
}
ALL_TOOLS = READ_TOOLS | MUTATION_TOOLS
SCOPES = {
    "all_days", "weekday", "weekend", "monday", "tuesday", "wednesday",
    "thursday", "friday", "saturday", "sunday",
}
FEEDBACK_TYPES = {"helpful", "not_helpful", "too_frequent", "do_not_repeat"}
_CELSIUS_UNITS = {"c", "celsius", "degc", "wmounit:degc"}
_FAHRENHEIT_UNITS = {"f", "fahrenheit", "degf", "wmounit:degf"}


def _as_of() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fahrenheit_temperature(value: Any) -> Any:
    """Normalize known NWS temperature quantities for the operator display contract."""

    if not isinstance(value, dict) or not isinstance(value.get("value"), (int, float)):
        return value
    unit = str(value.get("unit", "")).casefold()
    if unit in _CELSIUS_UNITS:
        return {"value": round(float(value["value"]) * 9 / 5 + 32, 1), "unit": "degrees Fahrenheit"}
    if unit in _FAHRENHEIT_UNITS:
        return {"value": value["value"], "unit": "degrees Fahrenheit"}
    return value


def _normalize_weather_display_units(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep persisted provider values intact while exposing Fahrenheit to SENTRY."""

    normalized: list[dict[str, Any]] = []
    for fact in facts:
        item = {**fact}
        data = fact.get("data")
        if fact.get("fact_id") == "weather:current" and isinstance(data, dict):
            display = {**data}
            for key in ("temperature", "apparent_temperature", "wind_chill"):
                if key in display:
                    display[key] = _fahrenheit_temperature(display[key])
            item["data"] = display
        elif fact.get("fact_id") == "weather:forecast:near-term" and isinstance(data, dict):
            display = {**data}
            periods = []
            for period in data.get("periods", []):
                normalized_period = {**period}
                if str(normalized_period.get("temperature_unit", "")).casefold() in _FAHRENHEIT_UNITS:
                    normalized_period["temperature_unit"] = "degrees Fahrenheit"
                periods.append(normalized_period)
            display["periods"] = periods
            item["data"] = display
        normalized.append(item)
    return normalized


def _read_result(name: str, *, status: str, facts: list[dict[str, Any]] | None = None,
                 limitations: list[str] | None = None, as_of: str | None = None) -> dict[str, Any]:
    return {
        "tool": name,
        "status": status,
        "as_of": as_of or _as_of(),
        "facts": facts or [],
        "limitations": limitations or [],
    }


def _mutation_result(name: str, *, status: str, result: dict[str, Any] | None = None,
                     limitations: list[str] | None = None) -> dict[str, Any]:
    result = result or {}
    facts = []
    if status == "succeeded":
        facts = [{
            "fact_id": f"mutation:{name}",
            "kind": "conversation_mutation_result",
            "as_of": _as_of(),
            "data": {key: value for key, value in result.items() if key != "message"},
        }]
    return {
        "tool": name,
        "status": status,
        "result": result,
        "facts": facts,
        "fact_ids": [],
        "limitations": limitations or [],
    }


def tool_catalog() -> list[dict[str, Any]]:
    """The only capability descriptions supplied to the Luna planning turn."""

    return [
        {"name": "get_current_office_state", "kind": "read", "arguments": {},
         "description": "Fresh current office state only; returns unavailable when live perception cannot support it."},
        {"name": "get_office_history", "kind": "read", "arguments": {"limit": "integer 1..20, optional"},
         "description": "Bounded room-session history plus primary-user presence confirmations. A room session start is not a personal arrival, and a confirmation is not an exact entry time."},
        {"name": "get_office_reminders", "kind": "read", "arguments": {},
         "description": "The bounded next-office-session reminder state."},
        {"name": "create_next_office_reminder", "kind": "mutation", "arguments": {"message": "string, 1..120 characters"},
         "description": "Create the one supported reminder only when the user directly requests it."},
        {"name": "cancel_pending_office_reminder", "kind": "mutation", "arguments": {},
         "description": "Cancel the one pending office reminder only when directly requested."},
        {"name": "get_alarms", "kind": "read", "arguments": {"status": "optional pending, delivered, failed, or cancelled"},
         "description": "Read bounded one-shot alarm state."},
        {"name": "create_one_shot_alarm", "kind": "mutation", "arguments": {"scheduled_for": "offset-aware ISO timestamp", "display_timezone": "IANA timezone", "label": "string, 1..120 characters"},
         "description": "Create one durable one-shot alarm only when the user directly requests it."},
        {"name": "cancel_alarm", "kind": "mutation", "arguments": {"alarm_id": "exact alarm identifier"},
         "description": "Cancel one exact pending alarm only when directly requested."},
        {"name": "get_acknowledgement_preference", "kind": "read", "arguments": {},
         "description": "Read the explicit primary-user session acknowledgement preference."},
        {"name": "set_acknowledgement_preference", "kind": "mutation", "arguments": {"value": "allow or suppress"},
         "description": "Set the one supported acknowledgement preference only when directly requested."},
        {"name": "clear_acknowledgement_preference", "kind": "mutation", "arguments": {},
         "description": "Clear the acknowledgement preference only when directly requested."},
        {"name": "get_recent_proactive_action", "kind": "read", "arguments": {},
         "description": "Read one safely resolved recent delivered proactive action, if one exists."},
        {"name": "record_proactive_feedback", "kind": "mutation", "arguments": {"feedback_type": "helpful, not_helpful, too_frequent, or do_not_repeat"},
         "description": "Record explicit feedback only against a safely resolved delivered proactive action."},
        {"name": "get_routines", "kind": "read", "arguments": {"routine_type": "optional accepted routine type", "scope": "optional accepted scope"},
         "description": "Read bounded accepted derived routine snapshots; insufficient evidence is not a habit claim."},
        {"name": "get_weather", "kind": "read", "arguments": {"topic": "current, forecast, or alerts"},
         "description": "Read only cached normalized local weather, with temperatures spoken as degrees Fahrenheit rather than an abbreviation; never fetch the network."},
        {"name": "use_native_web_search", "kind": "read", "arguments": {},
         "description": "Authorize Luna's native read-only live web search for a user-requested public lookup, current external information, named public place/date weather, or a user-supplied public URL. It cannot write, authenticate, submit forms, or receive SENTRY-private data. Use get_weather for SENTRY's configured private home weather cache."},
    ]


class ConversationToolHost:
    """Validate and execute the approved local capability surface."""

    def __init__(
        self,
        *,
        base_url: str,
        room_id: str = "office",
        source_surface: str = "sentry_ask",
        source_request_id: str | None = None,
        get_json: Callable[..., dict[str, Any]] = _get_json,
        post_json: Callable[..., dict[str, Any]] = post_json,
    ) -> None:
        if not base_url.startswith("http://127.0.0.1"):
            raise ValueError("conversation tools require the localhost state API")
        if room_id != "office":
            raise ValueError("conversation tools support only the office")
        self.base_url = base_url
        self.room_id = room_id
        self.source_surface = source_surface
        self.source_request_id = source_request_id or str(uuid.uuid4())
        self._get_json = get_json
        self._post_json = post_json

    @staticmethod
    def validate_call(name: Any, arguments: Any) -> str | None:
        if not isinstance(name, str) or name not in ALL_TOOLS:
            return "tool name is not approved"
        if not isinstance(arguments, dict):
            return "tool arguments must be an object"
        expected: dict[str, set[str]] = {
            "get_current_office_state": set(), "get_office_reminders": set(),
            "cancel_pending_office_reminder": set(), "get_acknowledgement_preference": set(),
            "clear_acknowledgement_preference": set(), "get_recent_proactive_action": set(),
            "get_office_history": {"limit"}, "create_next_office_reminder": {"message"},
            "set_acknowledgement_preference": {"value"}, "record_proactive_feedback": {"feedback_type"},
            "get_routines": {"routine_type", "scope"}, "get_weather": {"topic"},
            "use_native_web_search": set(),
            "get_alarms": {"status"},
            "create_one_shot_alarm": {"scheduled_for", "display_timezone", "label"},
            "cancel_alarm": {"alarm_id"},
        }
        if set(arguments) - expected[name]:
            return "tool arguments contain unsupported fields"
        if name == "get_office_history" and "limit" in arguments:
            if type(arguments["limit"]) is not int or not 1 <= arguments["limit"] <= 20:
                return "history limit must be an integer from 1 through 20"
        if name == "create_next_office_reminder":
            message = arguments.get("message")
            if not isinstance(message, str) or not message.strip() or len(message) > 120 or re.search(r"[\x00-\x1f\x7f]", message):
                return "reminder message must be a non-empty single-line string of at most 120 characters"
        if name == "set_acknowledgement_preference" and arguments.get("value") not in {"allow", "suppress"}:
            return "acknowledgement preference must be allow or suppress"
        if name == "record_proactive_feedback" and arguments.get("feedback_type") not in FEEDBACK_TYPES:
            return "feedback type is not supported"
        if name == "get_routines":
            if "routine_type" in arguments and arguments["routine_type"] not in ROUTINE_TYPES:
                return "routine type is not supported"
            if "scope" in arguments and arguments["scope"] not in SCOPES:
                return "routine scope is not supported"
        if name == "get_weather" and arguments.get("topic", "current") not in {"current", "forecast", "alerts"}:
            return "weather topic is not supported"
        if name == "get_alarms" and arguments.get("status") not in {None, "pending", "delivered", "failed", "cancelled"}:
            return "alarm status is not supported"
        if name == "create_one_shot_alarm":
            scheduled_for = arguments.get("scheduled_for")
            label = arguments.get("label", "Alarm")
            display_timezone = arguments.get("display_timezone")
            if not isinstance(scheduled_for, str) or not scheduled_for or not isinstance(display_timezone, str) or not display_timezone:
                return "alarm scheduled_for and display_timezone are required strings"
            if not isinstance(label, str) or not label.strip() or len(label) > 120 or re.search(r"[\x00-\x1f\x7f]", label):
                return "alarm label must be a non-empty single-line string of at most 120 characters"
        if name == "cancel_alarm" and (not isinstance(arguments.get("alarm_id"), str) or not arguments["alarm_id"]):
            return "alarm_id is required"
        return None

    def _health(self) -> dict[str, Any]:
        health = self._get_json(self.base_url, "/health", params={"room_id": self.room_id})
        if not health.get("ok") or not health.get("db_available"):
            raise ValueError("SENTRY state API or database is unavailable")
        return health

    def _packet(self, *, include_state: bool, include_history: bool, limit: int = 20) -> dict[str, Any]:
        health = self._health()
        responses: dict[str, dict[str, Any]] = {"health": health}
        responses["state"] = self._get_json(self.base_url, f"/v1/rooms/{self.room_id}/state", params={"room_id": self.room_id})
        if include_history:
            responses["sessions"] = self._get_json(self.base_url, f"/v1/rooms/{self.room_id}/sessions", params={"room_id": self.room_id, "limit": str(limit)})
            responses["persons"] = self._get_json(self.base_url, "/v1/persons", params={"limit": str(limit)})
            responses["events"] = self._get_json(self.base_url, "/v1/events", params={"room_id": self.room_id, "limit": str(limit)})
            display_timezone = health.get("display_timezone", "America/New_York")
            if not isinstance(display_timezone, str):
                raise ValueError("display timezone must be a valid IANA timezone")
            try:
                local_now = datetime.now(ZoneInfo(display_timezone))
            except ZoneInfoNotFoundError as exc:
                raise ValueError("display timezone must be a valid IANA timezone") from exc
            day_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
            responses["primary_user_events"] = self._get_json(
                self.base_url,
                "/v1/events",
                params={
                    "room_id": self.room_id,
                    "limit": "20",
                    "event_type": "person.identified",
                    "person_id": "primary_user",
                    "since": day_start.isoformat(),
                },
            )
        else:
            responses.update({"sessions": {"sessions": []}, "persons": {"persons": []}, "events": {"events": []}})
        return build_fact_packet(responses)

    def _get_current(self) -> dict[str, Any]:
        try:
            packet = self._packet(include_state=True, include_history=True, limit=20)
            allowed = {"source-health", "perception-runtime", "current-room-state", "current-room-people", "current-open-session"}
            facts = [fact for fact in packet["facts"] if fact.get("fact_id") in allowed]
            runtime = next((fact for fact in facts if fact.get("fact_id") == "perception-runtime"), {"data": {}})
            if not runtime.get("data", {}).get("current_physical_available"):
                return _read_result("get_current_office_state", status="unavailable", facts=facts,
                                    limitations=["live perception cannot support current office state"], as_of=packet["as_of"])
            return _read_result("get_current_office_state", status="supported", facts=facts, as_of=packet["as_of"])
        except Exception as exc:  # noqa: BLE001 - localhost failure is bounded
            return _read_result("get_current_office_state", status="unavailable", limitations=[f"current state unavailable: {type(exc).__name__}"])

    def _get_history(self, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            limit = arguments.get("limit", 20)
            packet = self._packet(include_state=True, include_history=True, limit=limit)
            allowed = {"source-health", "room-sessions", "room-events", "enrolled-persons", "primary-user-identification", "primary-user-presence-confirmation", "last-confirmed-empty"}
            facts = [fact for fact in packet["facts"] if fact.get("fact_id") in allowed]
            return _read_result("get_office_history", status="supported", facts=facts, as_of=packet["as_of"])
        except Exception as exc:  # noqa: BLE001
            return _read_result("get_office_history", status="unavailable", limitations=[f"office history unavailable: {type(exc).__name__}"])

    def _get_reminders(self) -> dict[str, Any]:
        try:
            response = self._get_json(self.base_url, "/v1/reminders", params={"person_id": "primary_user", "room_id": self.room_id, "limit": "20"})
            reminders = response.get("reminders")
            if not isinstance(reminders, list):
                raise ValueError("reminder list is invalid")
            allowed = ("reminder_id", "trigger_kind", "message", "created_at", "created_session_id", "status", "claimed_at", "delivered_at", "failed_at", "cancelled_at")
            normalized = [{key: item[key] for key in allowed if key in item} for item in reminders[:20] if isinstance(item, dict)]
            fact = {"fact_id": "office-reminders", "kind": "event_reminders", "as_of": _as_of(), "data": {"reminders": normalized}}
            return _read_result("get_office_reminders", status="supported", facts=[fact])
        except Exception as exc:  # noqa: BLE001
            return _read_result("get_office_reminders", status="unavailable", limitations=[f"reminder state unavailable: {type(exc).__name__}"])

    def _create_reminder(self, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._post_json(self.base_url, "/v1/reminders", {
                "person_id": "primary_user", "room_id": self.room_id,
                "trigger_kind": "next_primary_user_office_session", "message": arguments["message"].strip(),
                "source_surface": self.source_surface, "source_request_id": self.source_request_id,
            })
            reminder = response.get("reminder")
            if not isinstance(reminder, dict):
                raise ValueError("reminder mutation response is invalid")
            return _mutation_result("create_next_office_reminder", status="succeeded", result={
                "reminder_id": reminder.get("reminder_id"), "status": reminder.get("status"), "message": reminder.get("message"),
            })
        except Exception as exc:  # noqa: BLE001
            return _mutation_result("create_next_office_reminder", status="unavailable", limitations=[f"reminder creation unavailable: {type(exc).__name__}"])

    def _cancel_reminder(self) -> dict[str, Any]:
        read = self._get_reminders()
        if read["status"] != "supported":
            return _mutation_result("cancel_pending_office_reminder", status="unavailable", limitations=read["limitations"])
        reminders = read["facts"][0]["data"]["reminders"]
        pending = next((item for item in reminders if item.get("status") == "pending"), None)
        if pending is None:
            return _mutation_result("cancel_pending_office_reminder", status="partial", result={"cancelled": False}, limitations=["no pending office reminder exists"])
        try:
            response = self._post_json(self.base_url, f"/v1/reminders/{pending['reminder_id']}/cancel", {
                "source_surface": self.source_surface, "source_request_id": self.source_request_id,
            })
            reminder = response.get("reminder")
            if not isinstance(reminder, dict):
                raise ValueError("reminder cancellation response is invalid")
            return _mutation_result("cancel_pending_office_reminder", status="succeeded", result={"reminder_id": reminder.get("reminder_id"), "status": reminder.get("status")})
        except Exception as exc:  # noqa: BLE001
            return _mutation_result("cancel_pending_office_reminder", status="unavailable", limitations=[f"reminder cancellation unavailable: {type(exc).__name__}"])

    def _get_alarms(self, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            params = {"person_id": "primary_user", "limit": "32"}
            if arguments.get("status"):
                params["status"] = arguments["status"]
            response = self._get_json(self.base_url, "/v1/alarms", params=params)
            alarms = response.get("alarms")
            if not isinstance(alarms, list):
                raise ValueError("alarm list is invalid")
            allowed = (
                "alarm_id", "label", "scheduled_for", "display_timezone", "created_at", "status",
                "claimed_at", "delivered_at", "failed_at", "cancelled_at", "failure_reason",
            )
            normalized = []
            for item in alarms[:32]:
                if not isinstance(item, dict):
                    continue
                value = {key: item[key] for key in allowed if key in item}
                try:
                    instant = datetime.fromisoformat(str(item["scheduled_for"]).replace("Z", "+00:00"))
                    zone = ZoneInfo(str(item["display_timezone"]))
                    value["scheduled_for_local_display"] = instant.astimezone(zone).strftime(
                        "%B %-d, %Y at %-I:%M %p %Z"
                    )
                except (KeyError, TypeError, ValueError, ZoneInfoNotFoundError):
                    pass
                normalized.append(value)
            fact = {"fact_id": "one-shot-alarms", "kind": "alarms", "as_of": _as_of(), "data": {"alarms": normalized}}
            return _read_result("get_alarms", status="supported", facts=[fact])
        except Exception as exc:  # noqa: BLE001
            return _read_result("get_alarms", status="unavailable", limitations=[f"alarm state unavailable: {type(exc).__name__}"])

    def _create_alarm(self, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._post_json(self.base_url, "/v1/alarms", {
                "person_id": "primary_user",
                "scheduled_for": arguments["scheduled_for"],
                "display_timezone": arguments["display_timezone"],
                "label": arguments.get("label", "Alarm").strip(),
                "source_surface": self.source_surface,
                "source_request_id": self.source_request_id,
            })
            alarm = response.get("alarm")
            if not isinstance(alarm, dict):
                raise ValueError("alarm mutation response is invalid")
            local_display = None
            try:
                instant = datetime.fromisoformat(str(alarm["scheduled_for"]).replace("Z", "+00:00"))
                zone = ZoneInfo(str(alarm["display_timezone"]))
                local_display = instant.astimezone(zone).strftime("%B %-d, %Y at %-I:%M %p %Z")
            except (KeyError, TypeError, ValueError, ZoneInfoNotFoundError):
                pass
            return _mutation_result("create_one_shot_alarm", status="succeeded", result={
                "alarm_id": alarm.get("alarm_id"), "status": alarm.get("status"),
                "label": alarm.get("label"), "scheduled_for": alarm.get("scheduled_for"),
                "display_timezone": alarm.get("display_timezone"),
                "scheduled_for_local_display": local_display,
            })
        except Exception as exc:  # noqa: BLE001
            return _mutation_result("create_one_shot_alarm", status="unavailable", limitations=[f"alarm creation unavailable: {type(exc).__name__}: {exc}"])

    def _cancel_alarm(self, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._post_json(self.base_url, f"/v1/alarms/{arguments['alarm_id']}/cancel", {
                "source_surface": self.source_surface,
                "source_request_id": self.source_request_id,
            })
            alarm = response.get("alarm")
            if not isinstance(alarm, dict):
                raise ValueError("alarm cancellation response is invalid")
            return _mutation_result("cancel_alarm", status="succeeded", result={
                "alarm_id": alarm.get("alarm_id"), "status": alarm.get("status"),
            })
        except Exception as exc:  # noqa: BLE001
            return _mutation_result("cancel_alarm", status="unavailable", limitations=[f"alarm cancellation unavailable: {type(exc).__name__}: {exc}"])

    def _get_preference(self) -> dict[str, Any]:
        try:
            response = self._get_json(self.base_url, "/v1/preferences", params={"person_id": "primary_user"})
            value = response.get("current_value")
            if value not in {"default", "allow", "suppress"}:
                raise ValueError("preference value is invalid")
            fact = {"fact_id": "preference:proactivity.primary_user_session_acknowledgement", "kind": "behavior_preference", "as_of": _as_of(), "data": {"person_id": "primary_user", "preference_key": "proactivity.primary_user_session_acknowledgement", "current_value": value}}
            return _read_result("get_acknowledgement_preference", status="supported", facts=[fact])
        except Exception as exc:  # noqa: BLE001
            return _read_result("get_acknowledgement_preference", status="unavailable", limitations=[f"preference state unavailable: {type(exc).__name__}"])

    def _set_preference(self, value: str | None) -> dict[str, Any]:
        name = "clear_acknowledgement_preference" if value is None else "set_acknowledgement_preference"
        try:
            response = self._post_json(self.base_url, "/v1/preferences", {
                "person_id": "primary_user", "operation": "clear" if value is None else "set", "value": value,
                "source_surface": self.source_surface, "source_request_id": self.source_request_id,
            })
            current = response.get("current_value")
            preference = response.get("preference")
            if current not in {"default", "allow", "suppress"} or not isinstance(preference, dict):
                raise ValueError("preference mutation response is invalid")
            return _mutation_result(name, status="succeeded", result={"current_value": current, "preference_event_id": preference.get("preference_event_id")})
        except Exception as exc:  # noqa: BLE001
            return _mutation_result(name, status="unavailable", limitations=[f"preference update unavailable: {type(exc).__name__}"])

    def _get_recent_action(self) -> dict[str, Any]:
        try:
            response = self._get_json(self.base_url, "/v1/proactive-actions/recent", params={"person_id": "primary_user", "window_seconds": "600"})
            action = response.get("action")
            allowed = ("action_id", "event_type", "session_id", "event_timestamp", "evaluated_at", "suppression_reason", "judge_decision", "delivery_status")
            data = {key: action[key] for key in allowed if key in action} if isinstance(action, dict) else {"action": None}
            fact = {"fact_id": "recent-proactive-action", "kind": "recent_proactive_action", "as_of": _as_of(), "data": data}
            return _read_result("get_recent_proactive_action", status="supported" if isinstance(action, dict) else "partial", facts=[fact], limitations=[] if isinstance(action, dict) else ["no safely resolved delivered proactive action in the last 10 minutes"])
        except Exception as exc:  # noqa: BLE001
            return _read_result("get_recent_proactive_action", status="unavailable", limitations=[f"recent proactive state unavailable: {type(exc).__name__}"])

    def _feedback(self, feedback_type: str) -> dict[str, Any]:
        recent = self._get_recent_action()
        facts = recent.get("facts", [])
        action_id = facts[0]["data"].get("action_id") if facts else None
        if recent["status"] != "supported" or not isinstance(action_id, str):
            return _mutation_result("record_proactive_feedback", status="partial", limitations=recent.get("limitations", ["no safely resolved recent action"]))
        try:
            response = self._post_json(self.base_url, "/v1/proactive-feedback", {
                "action_id": action_id, "person_id": "primary_user", "feedback_type": feedback_type,
                "source_surface": self.source_surface, "source_request_id": self.source_request_id,
            })
            feedback = response.get("feedback")
            if not isinstance(feedback, dict):
                raise ValueError("feedback mutation response is invalid")
            return _mutation_result("record_proactive_feedback", status="succeeded", result={"feedback_id": feedback.get("feedback_id"), "feedback_type": feedback_type, "resulting_preference_event_id": feedback.get("resulting_preference_event_id")})
        except Exception as exc:  # noqa: BLE001
            return _mutation_result("record_proactive_feedback", status="unavailable", limitations=[f"feedback update unavailable: {type(exc).__name__}"])

    def _get_routines(self, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._get_json(self.base_url, "/v1/routines", params={"room_id": self.room_id, "limit": "100"})
            raw_items = response.get("routines")
            if not isinstance(raw_items, list):
                raise ValueError("routine list is invalid")
            filtered = []
            for raw in raw_items:
                item = _normalize_routine(raw)
                if item is None:
                    continue
                if arguments.get("routine_type") and item["routine_type"] != arguments["routine_type"]:
                    continue
                if arguments.get("scope") and item["scope"] != arguments["scope"]:
                    continue
                filtered.append(item)
            filtered.sort(key=lambda item: item["routine_key"])
            facts = [{"fact_id": f"routine:{item['routine_key']}", "kind": "derived_routine", "as_of": item["source_as_of"], "data": {key: item[key] for key in ("routine_type", "scope", "timezone", "algorithm_version", "window_start", "window_end", "source_as_of", "generated_at", "sample_count", "distinct_date_count", "maturity_status", "statistics", "exclusions")}} for item in filtered[:20]]
            status = "supported" if facts else "partial"
            return _read_result("get_routines", status=status, facts=facts, limitations=[] if facts else ["no accepted routine snapshots match the requested type/scope"])
        except Exception as exc:  # noqa: BLE001
            return _read_result("get_routines", status="unavailable", limitations=[f"routine source unavailable: {type(exc).__name__}"])

    def _get_weather(self, arguments: dict[str, Any]) -> dict[str, Any]:
        topic = arguments.get("topic", "current")
        try:
            response = self._get_json(self.base_url, "/v1/weather", params={"room_id": self.room_id})
            facts = _normalize_weather_display_units(_normalize_weather(response))
            wanted = {"weather:source-health", {"current": "weather:current", "forecast": "weather:forecast:near-term", "alerts": "weather:alerts"}[topic]}
            facts = [fact for fact in facts if fact.get("fact_id") in wanted]
            health = next((fact for fact in facts if fact.get("fact_id") == "weather:source-health"), {"data": {}})
            status = health.get("data", {}).get("status", "unavailable")
            if status != "fresh":
                return _read_result("get_weather", status="unavailable", facts=facts, limitations=[f"weather context is {status}"])
            if len(facts) < 2:
                return _read_result("get_weather", status="partial", facts=facts, limitations=[f"fresh weather has no {topic} data"])
            return _read_result("get_weather", status="supported", facts=facts)
        except Exception as exc:  # noqa: BLE001
            return _read_result("get_weather", status="unavailable", limitations=[f"weather context unavailable: {type(exc).__name__}"])

    def _use_native_web_search(self) -> dict[str, Any]:
        """Authorize one synthesis turn to use Luna's own read-only web tool.

        This deliberately performs no network operation in the SENTRY host. The
        synthesis bridge launches the OAuth Codex CLI with ``--search`` only
        when this typed capability is present in the validated plan.
        """

        fact = {
            "fact_id": "web:native-search-authorized",
            "kind": "native_web_search_authorization",
            "as_of": _as_of(),
            "data": {"engine": "codex_native_web_search", "mode": "read_only"},
        }
        return _read_result("use_native_web_search", status="supported", facts=[fact])

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        error = self.validate_call(name, arguments)
        if error:
            return _read_result(str(name), status="unavailable", limitations=[f"invalid tool call: {error}"])
        methods: dict[str, Callable[[], dict[str, Any]]] = {
            "get_current_office_state": self._get_current,
            "get_office_history": lambda: self._get_history(arguments),
            "get_office_reminders": self._get_reminders,
            "create_next_office_reminder": lambda: self._create_reminder(arguments),
            "cancel_pending_office_reminder": self._cancel_reminder,
            "get_alarms": lambda: self._get_alarms(arguments),
            "create_one_shot_alarm": lambda: self._create_alarm(arguments),
            "cancel_alarm": lambda: self._cancel_alarm(arguments),
            "get_acknowledgement_preference": self._get_preference,
            "set_acknowledgement_preference": lambda: self._set_preference(arguments["value"]),
            "clear_acknowledgement_preference": lambda: self._set_preference(None),
            "get_recent_proactive_action": self._get_recent_action,
            "record_proactive_feedback": lambda: self._feedback(arguments["feedback_type"]),
            "get_routines": lambda: self._get_routines(arguments),
            "get_weather": lambda: self._get_weather(arguments),
            "use_native_web_search": self._use_native_web_search,
        }
        return methods[name]()
