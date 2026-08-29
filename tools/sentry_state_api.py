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

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        room_id = query.get("room_id", ["office"])[0]
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
        else:
            self._send(404, {"error": "not_found"})

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
