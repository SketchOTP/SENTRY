"""Structured Linux desktop controls for the Codex-native SENTRY agent.

The adapter deliberately favors stable local interfaces over pixel automation:
desktop entries for application discovery/launch, PipeWire for volume, MPRIS
for media, and xdotool/scrot only when a request genuinely needs GUI control.
"""

from __future__ import annotations

import configparser
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse


APPLICATION_DIRS = (
    Path("~/.local/share/applications").expanduser(),
    Path("/usr/local/share/applications"),
    Path("/usr/share/applications"),
)
_KEYS = re.compile(r"^[A-Za-z0-9_+ -]{1,100}$")


def _run(args: list[str], *, timeout: float = 15.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)


def _desktop_entry(path: Path) -> dict[str, str] | None:
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        parser.read(path, encoding="utf-8")
        section = parser["Desktop Entry"]
    except (OSError, KeyError, configparser.Error):
        return None
    if section.get("Type", "Application") != "Application":
        return None
    if section.getboolean("NoDisplay", fallback=False) or section.getboolean("Hidden", fallback=False):
        return None
    name = section.get("Name", "").strip()
    if not name:
        return None
    return {
        "app_id": path.stem,
        "name": name,
        "comment": section.get("Comment", "").strip(),
        "desktop_file": str(path),
    }


def find_applications(query: str, limit: int = 10) -> dict[str, Any]:
    """Find launchable Linux desktop applications by name or description."""

    query = " ".join(query.split()).casefold()
    if not query:
        raise ValueError("application query must not be empty")
    if not 1 <= limit <= 25:
        raise ValueError("application result limit must be from 1 through 25")
    matches: dict[str, dict[str, str]] = {}
    for directory in APPLICATION_DIRS:
        if not directory.is_dir():
            continue
        for path in directory.glob("*.desktop"):
            item = _desktop_entry(path)
            if item is None or item["app_id"] in matches:
                continue
            haystack = f"{item['name']} {item['comment']} {item['app_id']}".casefold()
            if query in haystack:
                matches[item["app_id"]] = item
    ordered = sorted(matches.values(), key=lambda item: (query not in item["name"].casefold(), item["name"].casefold()))
    return {"query": query, "applications": ordered[:limit], "count": min(len(ordered), limit)}


def launch_application(app_id: str) -> dict[str, Any]:
    """Launch one exact desktop-entry id with the current user session."""

    known = {item["app_id"] for directory in APPLICATION_DIRS if directory.is_dir() for path in directory.glob("*.desktop") if (item := _desktop_entry(path))}
    if app_id not in known:
        raise ValueError("application id is not installed or is not launchable")
    process = subprocess.Popen(
        ["gtk-launch", app_id],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return {"launched": True, "app_id": app_id, "launcher_pid": process.pid}


def open_web_page(url: str) -> dict[str, Any]:
    """Open one explicit HTTP(S) URL in the user's configured browser."""

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or len(url) > 2048:
        raise ValueError("web URL must be an explicit HTTP or HTTPS address")
    process = subprocess.Popen(
        ["xdg-open", url],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return {"opened": True, "url": url, "launcher_pid": process.pid}


def get_volume() -> dict[str, Any]:
    """Read the current default PipeWire sink volume and mute state."""

    result = _run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"])
    if result.returncode != 0:
        raise RuntimeError("unable to read the default audio sink")
    match = re.search(r"Volume:\s*([0-9.]+)(?:\s*\[(MUTED)\])?", result.stdout)
    if not match:
        raise RuntimeError("unexpected PipeWire volume response")
    return {"percent": round(float(match.group(1)) * 100, 1), "muted": bool(match.group(2))}


def set_volume(percent: float) -> dict[str, Any]:
    """Set the default PipeWire sink to an exact 0-150 percent volume."""

    if not 0 <= percent <= 150:
        raise ValueError("volume percent must be from 0 through 150")
    result = _run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{percent / 100:.4f}"])
    if result.returncode != 0:
        raise RuntimeError("unable to set the default audio sink volume")
    return get_volume()


def adjust_volume(delta_percent: float) -> dict[str, Any]:
    """Raise or lower the default sink volume by a bounded percentage."""

    if not -100 <= delta_percent <= 100 or delta_percent == 0:
        raise ValueError("volume adjustment must be non-zero and between -100 and 100")
    current = get_volume()["percent"]
    return set_volume(max(0.0, min(150.0, current + delta_percent)))


def set_muted(muted: bool) -> dict[str, Any]:
    """Mute or unmute the default PipeWire sink."""

    result = _run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "1" if muted else "0"])
    if result.returncode != 0:
        raise RuntimeError("unable to change the default audio sink mute state")
    return get_volume()


def _mpris_players() -> list[str]:
    result = _run(["gdbus", "call", "--session", "--dest", "org.freedesktop.DBus", "--object-path", "/org/freedesktop/DBus", "--method", "org.freedesktop.DBus.ListNames"])
    if result.returncode != 0:
        return []
    return sorted(set(re.findall(r"org\.mpris\.MediaPlayer2\.[A-Za-z0-9_.-]+", result.stdout)))


def media_control(action: Literal["play_pause", "play", "pause", "next", "previous", "stop"], player: str | None = None) -> dict[str, Any]:
    """Control an active MPRIS media player without changing the audio default."""

    players = _mpris_players()
    if not players:
        return {"status": "unavailable", "reason": "no MPRIS media player is active", "players": []}
    destination = player if player in players else players[0]
    methods = {"play_pause": "PlayPause", "play": "Play", "pause": "Pause", "next": "Next", "previous": "Previous", "stop": "Stop"}
    result = _run(["gdbus", "call", "--session", "--dest", destination, "--object-path", "/org/mpris/MediaPlayer2", "--method", f"org.mpris.MediaPlayer2.Player.{methods[action]}"])
    if result.returncode != 0:
        raise RuntimeError("the selected media player rejected the command")
    return {"status": "completed", "player": destination, "action": action}


def send_key_combo(keys: str) -> dict[str, Any]:
    """Send one explicit X11 key or key combination to the active window."""

    if not _KEYS.fullmatch(keys):
        raise ValueError("key combination contains unsupported characters")
    result = _run(["xdotool", "key", "--clearmodifiers", keys])
    if result.returncode != 0:
        raise RuntimeError("unable to send the requested key combination")
    return {"sent": True, "keys": keys}


def type_text(text: str) -> dict[str, Any]:
    """Type bounded UTF-8 text into the active X11 window."""

    if not text or len(text) > 1000 or "\x00" in text:
        raise ValueError("text must contain 1 through 1000 non-NUL characters")
    result = _run(["xdotool", "type", "--clearmodifiers", "--delay", "12", "--", text])
    if result.returncode != 0:
        raise RuntimeError("unable to type into the active window")
    return {"typed": True, "character_count": len(text)}


def click_pointer(x: int, y: int, button: int = 1) -> dict[str, Any]:
    """Move the X11 pointer and click one mouse button at exact coordinates."""

    if not 0 <= x <= 16384 or not 0 <= y <= 16384 or button not in {1, 2, 3}:
        raise ValueError("pointer coordinates or button are invalid")
    result = _run(["xdotool", "mousemove", str(x), str(y), "click", str(button)])
    if result.returncode != 0:
        raise RuntimeError("unable to move or click the pointer")
    return {"clicked": True, "x": x, "y": y, "button": button}


def active_window() -> dict[str, Any]:
    """Read the current X11 active-window identifier and title."""

    window = _run(["xdotool", "getactivewindow"])
    if window.returncode != 0 or not window.stdout.strip().isdigit():
        return {"status": "unavailable", "reason": "no active X11 window"}
    window_id = window.stdout.strip()
    title = _run(["xdotool", "getwindowname", window_id])
    return {"status": "available", "window_id": window_id, "title": title.stdout.strip() if title.returncode == 0 else None}


def capture_desktop_png() -> bytes:
    """Capture the current X11 desktop to transient memory-backed result bytes."""

    descriptor, filename = tempfile.mkstemp(prefix="sentry-desktop-", suffix=".png", dir=os.environ.get("XDG_RUNTIME_DIR") or "/tmp")
    os.close(descriptor)
    path = Path(filename)
    try:
        result = _run(["scrot", "--overwrite", str(path)], timeout=20)
        if result.returncode != 0 or not path.is_file():
            raise RuntimeError("unable to capture the current desktop")
        return path.read_bytes()
    finally:
        path.unlink(missing_ok=True)
