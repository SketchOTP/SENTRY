"""Poll PC-owned SENTRY status into the Pi's ephemeral runtime file."""

from __future__ import annotations

import argparse
import json
import os
import signal
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from perception.remote_voice import authorization_header, read_private_token


def fetch_status(url: str, token_file: Path, timeout: float = 4.0) -> dict[str, Any]:
    token = read_private_token(token_file)
    request = urllib.request.Request(url, headers={"Authorization": authorization_header(token)}, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        value = json.loads(response.read(16_384).decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("projection status must be an object")
    return value


def write_status(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://192.168.254.5:48220/v1/status")
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--status-path", type=Path, default=Path("/run/user/1000/sentry/voice.json"))
    parser.add_argument("--interval", type=float, default=1.0)
    args = parser.parse_args(argv)
    stop = False

    def request_stop(*_args: object) -> None:
        nonlocal stop
        stop = True

    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, request_stop)
    while not stop:
        try:
            value = fetch_status(args.url, args.token_file)
        except (OSError, ValueError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            value = {"state": "UNAVAILABLE", "reason": f"processing host unavailable: {type(exc).__name__}"}
        write_status(args.status_path, value)
        time.sleep(max(0.25, args.interval))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
