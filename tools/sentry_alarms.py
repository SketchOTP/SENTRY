"""Deliver due one-shot SENTRY alarms through local Kokoro/PipeWire speech."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from perception.alarms import AlarmDispatcher  # noqa: E402
from perception.presence_store import PresenceStore  # noqa: E402


def _load_config(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("SENTRY config must be an object")
    return payload


class _NullSpeaker:
    def speak(self, text: str) -> bool:
        del text
        return False


class _LazyKokoroSpeaker:
    """Avoid loading/probing Kokoro during idle timer activations."""

    def __init__(self, *, python_executable: str | None, voice: str, speed: float) -> None:
        self.python_executable = python_executable
        self.voice = voice
        self.speed = speed
        self._speaker = None

    def speak(self, text: str) -> bool:
        if self._speaker is None:
            from perception.voice import KokoroSpeaker

            self._speaker = KokoroSpeaker(
                python_executable=self.python_executable,
                voice=self.voice,
                speed=self.speed,
            )
        return self._speaker.speak(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("~/.config/sentry/config.json"))
    parser.add_argument("--no-speech", action="store_true", help="claim due alarms and record delivery failure")
    args = parser.parse_args(argv)
    try:
        config = _load_config(args.config.expanduser())
        storage = config.get("storage", {})
        alarms = config.get("alarms", {})
        if not isinstance(alarms, dict) or not bool(alarms.get("enabled", True)):
            print(json.dumps({"ok": True, "status": "disabled", "outcomes": []}, sort_keys=True))
            return 0
        voice = config.get("voice", {}) if isinstance(config.get("voice"), dict) else {}
        speaker = _NullSpeaker() if args.no_speech else _LazyKokoroSpeaker(
            python_executable=alarms.get("kokoro_python"),
            voice=str(voice.get("kokoro_voice", "bm_george")),
            speed=float(voice.get("kokoro_speed", 0.9)),
        )
        with PresenceStore(
            Path(storage["database_path"]).expanduser(),
            atlas_mirror_path=storage.get("atlas_mirror_path"),
            mirror_interval_seconds=float(storage.get("mirror_interval_seconds", 60.0)),
        ) as store:
            outcomes = AlarmDispatcher(store, speaker=speaker).process_due()
        print(json.dumps({"ok": True, "status": "completed", "outcomes": [item.__dict__ for item in outcomes]}, sort_keys=True))
        return 0
    except (KeyError, OSError, RuntimeError, ValueError) as exc:
        print(json.dumps({"ok": False, "status": "failed", "error": f"{type(exc).__name__}: {exc}"}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
