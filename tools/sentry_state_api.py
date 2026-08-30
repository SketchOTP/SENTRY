"""Small localhost-only read API for SENTRY state, history, and identity metadata."""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from perception.presence_store import PresenceStore


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
            self._send(
                200,
                {
                    "ok": bool(health["db_available"]),
                    "service": "sentry-state",
                    "room_id": room_id,
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
            self._send(200, {"events": store.events(room_id, limit=limit)})
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
) -> None:
    with PresenceStore(database_path, atlas_mirror_path=atlas_mirror_path) as store:
        server = ThreadingHTTPServer((host, port), _Handler)
        server.store = store  # type: ignore[attr-defined]
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
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        parser.error("the state API must remain localhost-only")
    serve(args.database, args.host, args.port, atlas_mirror_path=args.atlas_mirror)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
