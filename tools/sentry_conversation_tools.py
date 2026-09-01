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
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from tools.sentry_grounding import (
    _get_json,
    _normalize_routine,
    _normalize_weather,
    build_fact_packet,
)
from tools.sentry_local_api import post_json
from tools.sentry_routine_intent import ROUTINE_TYPES
from tools.sentry_web import MAX_QUERY_LENGTH, MAX_RESULTS, PublicWeatherClient, WebResearchClient, WebResearchError


READ_TOOLS = {
    "get_current_office_state",
    "get_office_history",
    "get_office_reminders",
    "get_acknowledgement_preference",
    "get_recent_proactive_action",
    "get_routines",
    "get_weather",
    "get_public_weather",
    "search_web",
    "read_web_page",
}
MUTATION_TOOLS = {
    "create_next_office_reminder",
    "cancel_pending_office_reminder",
    "set_acknowledgement_preference",
    "clear_acknowledgement_preference",
    "record_proactive_feedback",
}
ALL_TOOLS = READ_TOOLS | MUTATION_TOOLS
SCOPES = {
    "all_days", "weekday", "weekend", "monday", "tuesday", "wednesday",
    "thursday", "friday", "saturday", "sunday",
}
FEEDBACK_TYPES = {"helpful", "not_helpful", "too_frequent", "do_not_repeat"}


def _as_of() -> str:
    return datetime.now(timezone.utc).isoformat()


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
         "description": "Read only cached normalized local weather; never fetch the network."},
        {"name": "get_public_weather", "kind": "read", "arguments": {"location": "place explicitly supplied by the user", "when": "today, tomorrow, or an ISO YYYY-MM-DD date"},
         "description": "Read-only public forecast for a user-named place. It resolves that public place and fetches normalized data without exposing coordinates or a general network surface. Use get_weather, not this tool, for SENTRY's configured private home weather."},
        {"name": "search_web", "kind": "read", "arguments": {"query": "public-web research query, at most 240 characters", "max_results": "optional integer 1..5"},
         "description": "Read-only public-web research. Use for an explicit lookup or current external information beyond SENTRY's local cache, including another place/date's weather. Never use it to submit data, authenticate, or expose private SENTRY details."},
        {"name": "read_web_page", "kind": "read", "arguments": {"url": "user-supplied public http(s) URL"},
         "description": "Read one public HTTP(S) page when the user directly supplies or explicitly asks about its URL. It cannot log in, submit forms, or access private/local network addresses."},
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
        web_client: WebResearchClient | None = None,
        public_weather_client: PublicWeatherClient | None = None,
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
        self._web_client = web_client or WebResearchClient()
        self._public_weather_client = public_weather_client or PublicWeatherClient(web_client=self._web_client)

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
            "get_public_weather": {"location", "when"},
            "search_web": {"query", "max_results"}, "read_web_page": {"url"},
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
        if name == "get_public_weather":
            location = arguments.get("location")
            if not isinstance(location, str) or not location.strip() or len(location) > 160 or re.search(r"[\x00-\x1f\x7f]", location):
                return "public weather location must be a non-empty single-line string of at most 160 characters"
            when = arguments.get("when") or "today"
            if when not in {"today", "tomorrow"} and (not isinstance(when, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", when)):
                return "public weather date must be today, tomorrow, or YYYY-MM-DD"
        if name == "search_web":
            query = arguments.get("query")
            if not isinstance(query, str) or not query.strip() or len(query) > MAX_QUERY_LENGTH or re.search(r"[\x00-\x1f\x7f]", query):
                return "web search query must be a non-empty single-line string of at most 240 characters"
            if "max_results" in arguments and (type(arguments["max_results"]) is not int or not 1 <= arguments["max_results"] <= MAX_RESULTS):
                return "web search result count must be an integer from 1 through 5"
        if name == "read_web_page":
            url = arguments.get("url")
            if not isinstance(url, str) or not url.strip() or len(url) > 2048 or re.search(r"[\x00-\x1f\x7f]", url):
                return "web page URL must be a non-empty single-line URL of at most 2048 characters"
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
                return "web page URL must be a public HTTP(S) URL"
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
            facts = _normalize_weather(response)
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

    @staticmethod
    def _web_fact(index: int, document: Any, *, source_kind: str) -> dict[str, Any]:
        return {
            "fact_id": f"web:{source_kind}:{index}",
            "kind": "untrusted_public_web_source",
            "as_of": document.retrieved_at,
            "data": {
                "title": document.title,
                "url": document.url,
                "content_type": document.content_type,
                "retrieval_method": document.retrieval_method,
                "excerpt": document.text,
            },
        }

    def _search_web(self, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            documents = self._web_client.search(arguments["query"].strip(), max_results=arguments.get("max_results", 3))
            facts = [self._web_fact(index, document, source_kind="search") for index, document in enumerate(documents, start=1)]
            return _read_result("search_web", status="supported", facts=facts)
        except WebResearchError as exc:
            return _read_result("search_web", status="unavailable", limitations=[str(exc)])
        except Exception as exc:  # noqa: BLE001
            return _read_result("search_web", status="unavailable", limitations=[f"web research unavailable: {type(exc).__name__}"])

    def _get_public_weather(self, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            weather = self._public_weather_client.get_weather(arguments["location"].strip(), when=arguments.get("when") or "today")
            fact = {
                "fact_id": "public-weather:forecast:1",
                "kind": "untrusted_public_weather_source",
                "as_of": weather.retrieved_at,
                "data": {
                    "location": weather.location,
                    "local_date": weather.local_date,
                    "timezone": weather.timezone,
                    "summary": weather.summary,
                    "temperature_min_f": weather.temperature_min_f,
                    "temperature_max_f": weather.temperature_max_f,
                    "precipitation_probability_max": weather.precipitation_probability_max,
                    "source": weather.source,
                },
            }
            return _read_result("get_public_weather", status="supported", facts=[fact])
        except WebResearchError as exc:
            return _read_result("get_public_weather", status="unavailable", limitations=[str(exc)])
        except Exception as exc:  # noqa: BLE001
            return _read_result("get_public_weather", status="unavailable", limitations=[f"public weather unavailable: {type(exc).__name__}"])

    def _read_web_page(self, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            document = self._web_client.read(arguments["url"].strip())
            return _read_result("read_web_page", status="supported", facts=[self._web_fact(1, document, source_kind="page")])
        except WebResearchError as exc:
            return _read_result("read_web_page", status="unavailable", limitations=[str(exc)])
        except Exception as exc:  # noqa: BLE001
            return _read_result("read_web_page", status="unavailable", limitations=[f"web page unavailable: {type(exc).__name__}"])

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
            "get_acknowledgement_preference": self._get_preference,
            "set_acknowledgement_preference": lambda: self._set_preference(arguments["value"]),
            "clear_acknowledgement_preference": lambda: self._set_preference(None),
            "get_recent_proactive_action": self._get_recent_action,
            "record_proactive_feedback": lambda: self._feedback(arguments["feedback_type"]),
            "get_routines": lambda: self._get_routines(arguments),
            "get_weather": lambda: self._get_weather(arguments),
            "get_public_weather": lambda: self._get_public_weather(arguments),
            "search_web": lambda: self._search_web(arguments),
            "read_web_page": lambda: self._read_web_page(arguments),
        }
        return methods[name]()
