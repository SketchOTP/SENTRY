"""Print metadata-only SENTRY always-on voice status."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


def _path() -> Path:
    return Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "sentry" / "voice.json"


def _read(path: Path) -> dict:
    if not path.is_file():
        return {"status": "unavailable", "reason": "voice listener has not published status"}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "unavailable", "reason": type(exc).__name__}


def _label(payload: dict) -> str:
    state = payload.get("state", payload.get("status", "unavailable"))
    error = payload.get("last_error")
    guidance = {
        "LISTENING": "Say “Sentry” to begin.",
        "WAKE_DETECTED": "Wake detected — preparing your request.",
        "CAPTURING": "Listening — finish your request.",
        "TRANSCRIBING": "Understanding your request…",
        "ARMED": "Listening — say your command now.",
        "FOLLOWUP_LISTENING": "Listening for a follow-up…",
        "PROCESSING": "Preparing a grounded answer…",
        "SPEAKING": "SENTRY is speaking — microphone commands are paused.",
        "DISABLED": "Listener is stopped.",
    }.get(str(state), "Voice status is unavailable.")
    return f"SENTRY VOICE — {state}\n{guidance}" + (f"\n{error}" if error else "")


def _active_window_geometry() -> tuple[int, int, int, int] | None:
    """Return the active X11 window geometry so the cue appears where used."""
    if not shutil.which("xdotool"):
        return None
    try:
        window_id = subprocess.check_output(["xdotool", "getactivewindow"], text=True, stderr=subprocess.DEVNULL).strip()
        output = subprocess.check_output(["xdotool", "getwindowgeometry", "--shell", window_id], text=True, stderr=subprocess.DEVNULL)
        values = dict(line.split("=", 1) for line in output.splitlines() if "=" in line)
        return tuple(int(values[key]) for key in ("X", "Y", "WIDTH", "HEIGHT"))
    except (OSError, subprocess.CalledProcessError, KeyError, ValueError):
        return None


def _show_on_active_window(title: str, geometry: tuple[int, int, int, int] | None) -> None:
    """Make the temporary indicator visible on the operator's active display."""
    if geometry is None or not shutil.which("xdotool") or not shutil.which("wmctrl"):
        return
    try:
        window_id = subprocess.check_output(["xdotool", "search", "--name", f"^{title}$"], text=True, stderr=subprocess.DEVNULL).splitlines()[-1]
        x, y, width, _ = geometry
        subprocess.run(["wmctrl", "-i", "-r", window_id, "-b", "add,above"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["xdotool", "windowmove", window_id, str(x + width // 2 - 260), str(y + 160)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["xdotool", "windowactivate", "--sync", window_id], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError, IndexError):
        return


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watch", action="store_true", help="continuously print metadata-only status")
    parser.add_argument("--window", action="store_true", help="show a temporary local Zenity status window")
    args = parser.parse_args(argv)
    path = _path()
    if args.window and not shutil.which("zenity"):
        print("zenity is not available", file=sys.stderr)
        return 2
    process = None
    if args.window:
        title = "SENTRY Voice"
        active_geometry = _active_window_geometry()
        process = subprocess.Popen(
            ["zenity", "--progress", f"--title={title}", "--text=SENTRY VOICE — STARTING", "--percentage=0", "--no-cancel", "--width=520"],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True,
        )
        time.sleep(0.2)
        _show_on_active_window(title, active_geometry)
    while True:
        payload = _read(path)
        if not args.window:
            print(json.dumps(payload, sort_keys=True))
        elif process is not None and process.stdin is not None and process.poll() is None:
            try:
                process.stdin.write(f"# {_label(payload)}\n")
                process.stdin.write("50\n")
                process.stdin.flush()
            except (BrokenPipeError, OSError, ValueError):
                break
        if not args.watch:
            return 0 if payload.get("status") != "unavailable" else 1
        try:
            time.sleep(0.25)
        except KeyboardInterrupt:
            break
    if process is not None and process.poll() is None:
        process.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
