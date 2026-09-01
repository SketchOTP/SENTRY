"""Local stdio MCP server exposing SENTRY office and Linux desktop tools."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from mcp.server import MCPServer
from mcp.types import ImageContent, TextContent, ToolAnnotations

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.sentry_conversation_tools import ConversationToolHost
from tools.sentry_desktop import (
    active_window as _active_window,
    adjust_volume as _adjust_volume,
    capture_desktop_png,
    click_pointer as _click_pointer,
    find_applications as _find_applications,
    get_volume as _get_volume,
    launch_application as _launch_application,
    media_control as _media_control,
    open_web_page as _open_web_page,
    send_key_combo as _send_key_combo,
    set_muted as _set_muted,
    set_volume as _set_volume,
    type_text as _type_text,
)
from tools.sentry_office_vision import inspect_office_camera as _inspect_office_camera


BASE_URL = os.environ.get("SENTRY_BASE_URL", "http://127.0.0.1:48174")
CONFIG_PATH = Path(os.environ.get("SENTRY_CONFIG_PATH", "~/.config/sentry/config.json")).expanduser()
DISPLAY_TIMEZONE = os.environ.get("SENTRY_DISPLAY_TIMEZONE", "America/New_York")

mcp = MCPServer(
    "SENTRY Office",
    version="0.1.0",
    instructions=(
        "Use these tools for authoritative SENTRY office facts and local Linux desktop actions. "
        "A room-session time is not a personal arrival. Identity is authoritative only when the local "
        "tool reports recognized; never infer identity from appearance alone."
    ),
)


def _host() -> ConversationToolHost:
    return ConversationToolHost(base_url=BASE_URL, room_id="office", source_surface="codex_mcp")


def _read(name: str, arguments: dict | None = None) -> dict:
    return _host().execute(name, arguments or {})


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))
def get_current_office_state() -> dict:
    """Read fresh current office occupancy and locally recognized people."""
    return _read("get_current_office_state")


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))
def get_office_history(limit: int = 20) -> dict:
    """Read bounded room sessions, events, and person-confirmation history."""
    return _read("get_office_history", {"limit": limit})


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))
def get_office_reminders() -> dict:
    """Read the operator's bounded next-office-session reminder state."""
    return _read("get_office_reminders")


@mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False))
def create_next_office_reminder(message: str) -> dict:
    """Create the one supported reminder for the operator's next distinct office session."""
    return _read("create_next_office_reminder", {"message": message})


@mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=True, idempotent_hint=True, open_world_hint=False))
def cancel_pending_office_reminder() -> dict:
    """Cancel the currently pending next-office-session reminder, if one exists."""
    return _read("cancel_pending_office_reminder")


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))
def get_acknowledgement_preference() -> dict:
    """Read the operator's proactive office acknowledgement preference."""
    return _read("get_acknowledgement_preference")


@mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False))
def set_acknowledgement_preference(value: Literal["allow", "suppress"]) -> dict:
    """Allow or suppress proactive primary-user session acknowledgements."""
    return _read("set_acknowledgement_preference", {"value": value})


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))
def get_recent_proactive_action() -> dict:
    """Read the most recent safely resolved proactive office action."""
    return _read("get_recent_proactive_action")


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))
def get_routines() -> dict:
    """Read bounded accepted routine snapshots without inventing a habit."""
    return _read("get_routines")


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))
def get_home_weather(topic: Literal["current", "forecast", "alerts"] = "current") -> dict:
    """Read SENTRY's normalized private-home weather cache when fresh."""
    return _read("get_weather", {"topic": topic})


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))
def get_local_time() -> dict:
    """Read the current configured local date and 12-hour Eastern time."""
    now = datetime.now(ZoneInfo(DISPLAY_TIMEZONE))
    return {"timezone": DISPLAY_TIMEZONE, "iso": now.isoformat(), "display": now.strftime("%B %-d, %Y at %-I:%M:%S %p %Z")}


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))
def inspect_office_camera(duration_seconds: float = 3.0) -> list[TextContent | ImageContent]:
    """Inspect the office camera now, match enrolled identity locally, and return one ephemeral still."""
    metadata, jpeg = _inspect_office_camera(CONFIG_PATH, duration_seconds=duration_seconds)
    content: list[TextContent | ImageContent] = [TextContent(type="text", text=json.dumps(metadata, sort_keys=True))]
    if jpeg:
        import base64
        content.append(ImageContent(type="image", data=base64.b64encode(jpeg).decode("ascii"), mime_type="image/jpeg"))
    return content


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))
def find_applications(query: str, limit: int = 10) -> dict:
    """Find installed Linux applications by natural name or description."""
    return _find_applications(query, limit)


@mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False))
def launch_application(app_id: str) -> dict:
    """Launch one exact installed Linux desktop application id."""
    return _launch_application(app_id)


@mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=True))
def open_web_page(url: str) -> dict:
    """Open one explicit HTTP(S) page in the operator's configured browser."""
    return _open_web_page(url)


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))
def get_system_volume() -> dict:
    """Read the default PipeWire output volume and mute state."""
    return _get_volume()


@mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False))
def set_system_volume(percent: float) -> dict:
    """Set the default PipeWire output volume from 0 through 150 percent."""
    return _set_volume(percent)


@mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False))
def adjust_system_volume(delta_percent: float) -> dict:
    """Raise or lower the default PipeWire output volume by a bounded percentage."""
    return _adjust_volume(delta_percent)


@mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False))
def set_system_muted(muted: bool) -> dict:
    """Mute or unmute the default PipeWire output."""
    return _set_muted(muted)


@mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False))
def control_media(action: Literal["play_pause", "play", "pause", "next", "previous", "stop"], player: str | None = None) -> dict:
    """Control an active local MPRIS media player."""
    return _media_control(action, player)


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))
def get_active_window() -> dict:
    """Read the active X11 window title and identifier."""
    return _active_window()


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))
def capture_desktop() -> ImageContent:
    """Capture one current desktop screenshot for visual inspection."""
    import base64
    return ImageContent(type="image", data=base64.b64encode(capture_desktop_png()).decode("ascii"), mime_type="image/png")


@mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False))
def press_keys(keys: str) -> dict:
    """Send one explicit key or key combination to the active X11 window."""
    return _send_key_combo(keys)


@mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False))
def type_into_active_window(text: str) -> dict:
    """Type bounded text into the active X11 window."""
    return _type_text(text)


@mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False))
def click_desktop(x: int, y: int, button: int = 1) -> dict:
    """Move the pointer and click the requested button at exact X11 coordinates."""
    return _click_pointer(x, y, button)


if __name__ == "__main__":
    mcp.run()
