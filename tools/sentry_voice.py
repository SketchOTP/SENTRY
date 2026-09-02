"""Run one explicit local reactive SENTRY voice request.

This is push-to-talk: press Enter, speak for the bounded recording window, and
receive the existing grounded M4 answer through the existing local speaker.
Audio is held in memory only and is discarded after transcription.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from perception.voice import (  # noqa: E402
    KokoroSpeaker,
    LocalVoiceIndicator,
    NullSpeaker,
    PipeWireRecorder,
    ReactiveVoiceConfig,
    ReactiveVoiceLoop,
    WhisperTranscriber,
)
from tools.sentry_ask import ask  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:48174")
    parser.add_argument("--room-id", default="office")
    parser.add_argument("--duration-seconds", type=float, default=5.0)
    parser.add_argument("--source", help="PipeWire target name/serial; default uses the system default source")
    parser.add_argument("--model", default="tiny.en", help="local Whisper model name, default: tiny.en")
    parser.add_argument("--whisper-cache", type=Path, default=Path("~/.cache/whisper"))
    parser.add_argument("--kokoro-python", help="local Python interpreter that has the Kokoro package installed")
    parser.add_argument("--kokoro-voice", default="bm_george")
    parser.add_argument("--kokoro-speed", type=float, default=0.9)
    parser.add_argument("--lead-in-seconds", type=float, default=3.0, help="visible countdown before recording starts")
    parser.add_argument("--no-indicator", action="store_true", help="disable the temporary local speech-timing window")
    parser.add_argument("--no-speech", action="store_true", help="transcribe and ground without speaker delivery")
    parser.add_argument("--skip-prompt", action="store_true", help="start recording immediately")
    args = parser.parse_args()
    if args.duration_seconds <= 0:
        parser.error("--duration-seconds must be positive")
    if args.lead_in_seconds < 0:
        parser.error("--lead-in-seconds must not be negative")

    if not args.skip_prompt:
        input("Press Enter to start the microphone, then speak your SENTRY question... ")
    recorder = PipeWireRecorder(source=args.source)
    transcriber = WhisperTranscriber(model_name=args.model, download_root=args.whisper_cache)
    speaker = NullSpeaker() if args.no_speech else KokoroSpeaker(
        python_executable=args.kokoro_python,
        voice=args.kokoro_voice,
        speed=args.kokoro_speed,
    )
    indicator = LocalVoiceIndicator()
    indicator_open = False if args.no_indicator else indicator.open()
    if indicator_open:
        indicator.update("GET READY — speak when the countdown reaches START", 0)
    loop = ReactiveVoiceLoop(
        ReactiveVoiceConfig(base_url=args.base_url, room_id=args.room_id, recording_seconds=args.duration_seconds),
        recorder=recorder,
        transcriber=transcriber,
        speaker=speaker,
        ask_fn=ask,
    )
    print(json.dumps({
        "status": "ready_to_speak",
        "message": "Speak your question when the countdown reaches START.",
        "recording_seconds": args.duration_seconds,
    }, sort_keys=True), flush=True)
    remaining = int(args.lead_in_seconds)
    while remaining > 0:
        if indicator_open:
            indicator.update(f"GET READY — starting in {remaining}", max(0, 100 - remaining * 20))
        print(f"Starting in {remaining}...", flush=True)
        time.sleep(1.0)
        remaining -= 1
    if indicator_open:
        indicator.update(f"SPEAK NOW — {args.duration_seconds:g} seconds", 5)
    print("START SPEAKING NOW", flush=True)
    print(json.dumps({"status": "recording", "seconds": args.duration_seconds}, sort_keys=True), flush=True)
    result = loop.run_once()
    if indicator_open:
        indicator.finish()
    print("RECORDING COMPLETE", flush=True)
    print(json.dumps(result.as_dict(), ensure_ascii=True, sort_keys=True))
    return 0 if result.status == "answered" and (result.delivery == "delivered" or args.no_speech) else 1


if __name__ == "__main__":
    raise SystemExit(main())
