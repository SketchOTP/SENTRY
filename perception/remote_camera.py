"""Authenticated, bounded JPEG capture from a SENTRY projection host."""

from __future__ import annotations

import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from perception.remote_voice import authorization_header, read_private_token


class RemoteJpegCamera:
    """Fetch one ephemeral frame; never writes or forwards image bytes itself."""

    def __init__(self, url: str, token_file: Path, *, timeout: float = 3.0, max_bytes: int = 2_000_000) -> None:
        if not url.startswith(("http://", "https://")):
            raise ValueError("projection camera URL must use HTTP(S)")
        if not 0.2 <= timeout <= 10.0 or not 1_024 <= max_bytes <= 8_000_000:
            raise ValueError("projection camera bounds are invalid")
        self.url = url
        self.token_file = token_file.expanduser()
        self.timeout = timeout
        self.max_bytes = max_bytes

    def read(self) -> Any:
        token = read_private_token(self.token_file)
        request = urllib.request.Request(
            self.url,
            headers={"Authorization": authorization_header(token), "Accept": "image/jpeg"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read(self.max_bytes + 1)
        except (OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            raise RuntimeError("projection camera is unavailable") from exc
        if len(raw) > self.max_bytes:
            raise RuntimeError("projection camera frame exceeds the bounded size")
        image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None or image.size == 0:
            raise RuntimeError("projection camera returned an invalid JPEG")
        return image
