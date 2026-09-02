"""Small localhost-only read API for SENTRY state, history, and identity metadata."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from perception.presence_store import PresenceStore


PERCEPTION_RUNTIME_STATUSES = {"fresh", "stopped", "stale", "missing", "malformed"}


def _public_alert_id(value: object) -> str | None:
    """Expose a stable alert identifier, never the source URL."""

    if not isinstance(value, str) or not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        value = parsed.path.rstrip("/").rsplit("/", 1)[-1]
    value = " ".join(value.split())
    return value[:240] if value else None


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def perception_runtime_health(
    heartbeat_path: Path | None,
    *,
    freshness_seconds: float,
    now: datetime | None = None,
) -> dict[str, object]:
    """Report perception-runtime freshness independently from SQLite health."""

    evaluated_at = now or datetime.now(timezone.utc)
    base: dict[str, object] = {
        "status": "missing",
        "heartbeat_updated_at": None,
        "age_seconds": None,
        "process_alive": False,
        "camera_state": None,
        "room_state": None,
        "current_physical_available": False,
        "reason": "perception heartbeat is missing",
    }
    if heartbeat_path is None or not heartbeat_path.is_file():
        return base
    try:
        raw = json.loads(heartbeat_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {**base, "status": "malformed", "reason": "perception heartbeat is malformed"}
    if not isinstance(raw, dict):
        return {**base, "status": "malformed", "reason": "perception heartbeat is malformed"}
    updated_at = _parse_timestamp(raw.get("updated_at"))
    process_alive = raw.get("process_alive")
    summary = raw.get("summary")
    if updated_at is None or type(process_alive) is not bool or not isinstance(summary, dict):
        return {**base, "status": "malformed", "reason": "perception heartbeat fields are invalid"}
    camera_state = summary.get("camera_state")
    room_state = summary.get("room_state")
    if not isinstance(camera_state, str) or not isinstance(room_state, str):
        return {**base, "status": "malformed", "reason": "perception heartbeat state is invalid"}
    age_seconds = max(0.0, (evaluated_at - updated_at).total_seconds())
    common = {
        "heartbeat_updated_at": updated_at.isoformat(),
        "age_seconds": age_seconds,
        "process_alive": process_alive,
        "camera_state": camera_state,
        "room_state": room_state,
    }
    if not process_alive:
        return {**base, **common, "status": "stopped", "reason": "perception process is stopped"}
    if age_seconds > freshness_seconds:
        return {**base, **common, "status": "stale", "reason": "perception heartbeat is stale"}
    if camera_state in {"offline", "degraded"}:
        return {
            **base,
            **common,
            "status": "fresh",
            "reason": f"camera state is {camera_state}",
        }
    if camera_state != "online":
        return {**base, **common, "status": "fresh", "reason": "camera state cannot establish current occupancy"}
    return {
        **base,
        **common,
        "status": "fresh",
        "current_physical_available": True,
        "reason": None,
    }


class _Handler(BaseHTTPRequestHandler):
    server_version = "SENTRYState/1"

    def _send(self, status: int, payload: object) -> None:
        data = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 16_384:
                raise ValueError("request body must be between 1 and 16384 bytes")
            value = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("request body must be valid JSON") from exc
        if not isinstance(value, dict):
            raise ValueError("request body must be a JSON object")
        return value

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        room_id = query.get("room_id", ["office"])[0]
        history = query.get("history", ["0"])[0].lower() in {"1", "true", "yes"}
        try:
            limit = min(100, max(1, int(query.get("limit", ["100"])[0])))
        except (TypeError, ValueError):
            self._send(400, {"error": "limit must be a positive integer"})
            return
        store: PresenceStore = self.server.store  # type: ignore[attr-defined]
        if parsed.path == "/health":
            health = store.health()
            perception = perception_runtime_health(
                getattr(self.server, "perception_heartbeat", None),
                freshness_seconds=float(getattr(self.server, "perception_freshness_seconds", 75.0)),
            )
            self._send(
                200,
                {
                    "ok": bool(health["db_available"]),
                    "service": "sentry-state",
                    "room_id": room_id,
                    "perception": perception,
                    "display_timezone": getattr(self.server, "display_timezone", "America/New_York"),
                    **health,
                },
            )
        elif parsed.path == "/v1/rooms/office/state":
            state = store.current_state(room_id)
            self._send(200, state.__dict__ if state else {"state": "unknown", "room_id": room_id})
        elif parsed.path == "/v1/rooms/office/sessions":
            self._send(200, {"sessions": store.sessions(room_id, limit=limit)})
        elif parsed.path == "/v1/persons":
            self._send(200, {"persons": store.persons()})
        elif parsed.path == "/v1/events":
            event_type = query.get("event_type", [None])[0]
            person_id = query.get("person_id", [None])[0]
            since = query.get("since", [None])[0]
            try:
                self._send(200, {"events": store.events(
                    room_id,
                    limit=limit,
                    event_type=event_type,
                    person_id=person_id,
                    since=since,
                )})
            except ValueError as exc:
                self._send(400, {"error": str(exc)})
        elif parsed.path == "/v1/routines":
            self._send(200, {"routines": store.routine_snapshots(latest_only=not history, limit=limit)})
        elif parsed.path == "/v1/preferences":
            person_id = query.get("person_id", ["primary_user"])[0]
            self._send(200, {
                "person_id": person_id,
                "preference_key": "proactivity.primary_user_session_acknowledgement",
                "current_value": store.preference_value(person_id),
                "events": store.preference_events(person_id, limit=limit) if history else [],
            })
        elif parsed.path == "/v1/reminders":
            person_id = query.get("person_id", ["primary_user"])[0]
            self._send(200, {"reminders": store.event_reminders(person_id=person_id, room_id=room_id, limit=limit)})
        elif parsed.path == "/v1/alarms":
            person_id = query.get("person_id", ["primary_user"])[0]
            status = query.get("status", [None])[0]
            try:
                self._send(200, {"alarms": store.alarms(person_id=person_id, status=status, limit=limit)})
            except ValueError as exc:
                self._send(400, {"error": str(exc)})
        elif parsed.path == "/v1/proactive-actions/recent":
            person_id = query.get("person_id", ["primary_user"])[0]
            window = float(query.get("window_seconds", ["600"])[0])
            action = store.recent_delivered_proactive_action(person_id, window_seconds=window)
            self._send(200, {"action": action})
        elif parsed.path == "/v1/weather":
            location_label = query.get("location_label", ["home"])[0]
            weather = store.weather_status(location_label)
            snapshot = weather.get("snapshot")
            if snapshot is None:
                self._send(200, {"status": "unavailable", "age_seconds": None, "snapshot": None, "location_label": location_label})
                return
            metadata = snapshot.get("source_metadata") if isinstance(snapshot.get("source_metadata"), dict) else {}
            public_snapshot = {
                key: snapshot[key]
                for key in (
                    "provider", "location_label", "timezone", "fetched_at", "source_updated_at",
                    "fresh_until", "current", "hourly", "alerts",
                )
                if key in snapshot
            }
            if isinstance(public_snapshot.get("alerts"), list):
                public_snapshot["alerts"] = [
                    {
                        **alert,
                        "id": _public_alert_id(alert.get("id")),
                    }
                    for alert in public_snapshot["alerts"]
                    if isinstance(alert, dict)
                ]
            public_snapshot["source_metadata"] = {
                key: metadata[key]
                for key in ("provider", "points_cache_status", "station_id", "component_errors")
                if key in metadata
            }
            self._send(200, {
                "status": weather["status"], "age_seconds": weather["age_seconds"],
                "fresh_until": snapshot.get("fresh_until"), "snapshot": public_snapshot,
                **{key: public_snapshot.get(key) for key in ("provider", "location_label", "timezone", "fetched_at")},
            })
        else:
            self._send(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        store: PresenceStore = self.server.store  # type: ignore[attr-defined]
        try:
            body = self._read_json()
            if self.path.split("?", 1)[0] == "/v1/preferences":
                person_id = body.get("person_id", "primary_user")
                operation = body.get("operation")
                value = body.get("value")
                source_surface = body.get("source_surface", "api")
                source_request_id = body.get("source_request_id")
                if not all(isinstance(item, str) and item for item in (person_id, operation, source_surface, source_request_id)):
                    raise ValueError("person_id, operation, source_surface, and source_request_id are required strings")
                if operation == "clear":
                    value = None
                elif operation != "set" or value not in {"allow", "suppress"}:
                    raise ValueError("preference operation/value is invalid")
                result = store.record_preference(
                    person_id=person_id, operation=operation, value=value,
                    source_surface=source_surface, source_request_id=source_request_id,
                )
                self._send(200, {"ok": True, "preference": result, "current_value": store.preference_value(person_id)})
                return
            if self.path.split("?", 1)[0] == "/v1/reminders":
                person_id = body.get("person_id", "primary_user")
                room_id = body.get("room_id", "office")
                trigger_kind = body.get("trigger_kind", "next_primary_user_office_session")
                message = body.get("message")
                source_surface = body.get("source_surface", "api")
                source_request_id = body.get("source_request_id")
                if not all(isinstance(item, str) and item for item in (person_id, room_id, trigger_kind, message, source_surface, source_request_id)):
                    raise ValueError("person_id, room_id, trigger_kind, message, source_surface, and source_request_id are required strings")
                result = store.create_event_reminder(
                    message=message, person_id=person_id, room_id=room_id, trigger_kind=trigger_kind,
                    source_surface=source_surface, source_request_id=source_request_id,
                )
                self._send(200, {"ok": True, "reminder": result})
                return
            if self.path.split("?", 1)[0] == "/v1/alarms":
                person_id = body.get("person_id", "primary_user")
                label = body.get("label", "Alarm")
                scheduled_for = body.get("scheduled_for")
                display_timezone = body.get("display_timezone", getattr(self.server, "display_timezone", "America/New_York"))
                source_surface = body.get("source_surface", "api")
                source_request_id = body.get("source_request_id")
                if not all(isinstance(item, str) and item for item in (
                    person_id, label, scheduled_for, display_timezone, source_surface, source_request_id,
                )):
                    raise ValueError("person_id, label, scheduled_for, display_timezone, source_surface, and source_request_id are required strings")
                result = store.create_alarm(
                    scheduled_for=scheduled_for,
                    display_timezone=display_timezone,
                    label=label,
                    person_id=person_id,
                    source_surface=source_surface,
                    source_request_id=source_request_id,
                )
                self._send(200, {"ok": True, "alarm": result})
                return
            path = self.path.split("?", 1)[0]
            if path.startswith("/v1/reminders/") and path.endswith("/cancel"):
                reminder_id = path[len("/v1/reminders/"):-len("/cancel")]
                source_surface = body.get("source_surface", "api")
                source_request_id = body.get("source_request_id")
                if not reminder_id or not isinstance(source_surface, str) or not source_surface or not isinstance(source_request_id, str) or not source_request_id:
                    raise ValueError("reminder id, source_surface, and source_request_id are required")
                result = store.cancel_event_reminder(
                    reminder_id, source_surface=source_surface, source_request_id=source_request_id,
                )
                self._send(200, {"ok": True, "reminder": result})
                return
            if path.startswith("/v1/alarms/") and path.endswith("/cancel"):
                alarm_id = path[len("/v1/alarms/"):-len("/cancel")]
                source_surface = body.get("source_surface", "api")
                source_request_id = body.get("source_request_id")
                if not alarm_id or not isinstance(source_surface, str) or not source_surface or not isinstance(source_request_id, str) or not source_request_id:
                    raise ValueError("alarm id, source_surface, and source_request_id are required")
                result = store.cancel_alarm(
                    alarm_id, source_surface=source_surface, source_request_id=source_request_id,
                )
                self._send(200, {"ok": True, "alarm": result})
                return
            if self.path.split("?", 1)[0] == "/v1/proactive-feedback":
                fields = (body.get("action_id"), body.get("person_id", "primary_user"), body.get("feedback_type"), body.get("source_surface", "api"), body.get("source_request_id"))
                if not all(isinstance(item, str) and item for item in fields):
                    raise ValueError("action_id, person_id, feedback_type, source_surface, and source_request_id are required strings")
                result = store.record_proactive_feedback(
                    action_id=fields[0], person_id=fields[1], feedback_type=fields[2],
                    source_surface=fields[3], source_request_id=fields[4],
                )
                self._send(200, {"ok": True, "feedback": result})
                return
            self._send(404, {"error": "not_found"})
        except ValueError as exc:
            self._send(400, {"error": str(exc)})
        except KeyError as exc:
            self._send(404, {"error": str(exc)})

    def log_message(self, format: str, *args: object) -> None:
        return


def serve(
    database_path: Path,
    host: str = "127.0.0.1",
    port: int = 48174,
    *,
    atlas_mirror_path: Path | None = None,
    perception_heartbeat: Path | None = None,
    perception_freshness_seconds: float = 75.0,
    display_timezone: str = "America/New_York",
) -> None:
    if perception_freshness_seconds <= 0:
        raise ValueError("perception freshness seconds must be positive")
    try:
        ZoneInfo(display_timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("display timezone must be a valid IANA timezone") from exc
    with PresenceStore(database_path, atlas_mirror_path=atlas_mirror_path) as store:
        server = ThreadingHTTPServer((host, port), _Handler)
        server.store = store  # type: ignore[attr-defined]
        server.perception_heartbeat = perception_heartbeat  # type: ignore[attr-defined]
        server.perception_freshness_seconds = perception_freshness_seconds  # type: ignore[attr-defined]
        server.display_timezone = display_timezone  # type: ignore[attr-defined]
        try:
            server.serve_forever()
        finally:
            server.server_close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("~/.local/share/sentry/sentry.db"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=48174)
    parser.add_argument("--atlas-mirror", type=Path, default=Path("perception-data/runtime/backups/sentry.db"))
    parser.add_argument("--perception-heartbeat", type=Path)
    parser.add_argument("--perception-freshness-seconds", type=float, default=75.0)
    parser.add_argument("--display-timezone", default="America/New_York")
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        parser.error("the state API must remain localhost-only")
    try:
        serve(
            args.database,
            args.host,
            args.port,
            atlas_mirror_path=args.atlas_mirror,
            perception_heartbeat=args.perception_heartbeat,
            perception_freshness_seconds=args.perception_freshness_seconds,
            display_timezone=args.display_timezone,
        )
    except ValueError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
