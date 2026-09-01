"""Small localhost-only JSON mutation helper shared by conversation surfaces."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def post_json(base_url: str, path: str, payload: dict[str, Any], *, timeout: float = 5.0) -> dict[str, Any]:
    if not base_url.startswith("http://127.0.0.1"):
        raise ValueError("SENTRY mutations require the localhost state API")
    request = Request(
        f"{base_url.rstrip('/')}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - caller is constrained above
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
