"""Run SENTRY's opt-in local always-available voice listener."""

from __future__ import annotations

import argparse
import json
import signal
import sys
import threading
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from perception.always_on_voice import (  # noqa: E402
    AlwaysOnVoiceConfig,
    AlwaysOnVoiceLoop,
    PipeWirePcmStream,
    SileroVad,
    VoiceDiagnostics,
)
from perception.sentry_perception import load_config  # noqa: E402
from perception.vosk_kws import (  # noqa: E402
    VoskKwsEvaluator,
    VoskSharedModel,
    VoskStreamingCommandRecognizer,
)
from perception.voice import KokoroSpeaker, WhisperTranscriber  # noqa: E402
from tools.sentry_ask import (  # noqa: E402
    ask,
    complete_action_presentation,
    expire_action_response,
    fail_action_presentation,
    invalidate_action_dialogue_for_restart,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("~/.config/sentry/config.json"))
    parser.add_argument("--allow-disabled", action="store_true", help="run an explicitly disabled listener only for bounded qualification")
    parser.add_argument("--source", help="override configured PipeWire source")
    parser.add_argument("--kokoro-python", help="local Python interpreter containing Kokoro")
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config.expanduser())
        voice = AlwaysOnVoiceConfig.from_mapping(config.get("voice"))
        if not voice.always_on_enabled and not args.allow_disabled:
            print(json.dumps({"ok": False, "status": "disabled", "error": "always-on voice is disabled in local config"}, sort_keys=True))
            return 2
        if args.source:
            voice = AlwaysOnVoiceConfig(**{**voice.__dict__, "microphone_source": args.source})
        stop_event = threading.Event()
        for signum in (signal.SIGTERM, signal.SIGINT):
            signal.signal(signum, lambda *_: stop_event.set())
        invalidate_action_dialogue_for_restart()
        diagnostics = VoiceDiagnostics()
        shared_vosk = VoskSharedModel(Path(voice.vosk_model_path or ""))
        wake_detector = VoskKwsEvaluator(
            shared_vosk.model_path,
            # The restricted recognizer may not emit its final result until
            # the whole utterance ends. Accept the exact partial token so the
            # resident loop can preserve everything spoken after "Sentry" in
            # its existing bounded in-memory capture.
            detect_partial=True,
            partial_confirmation_frames=1,
            debounce_seconds=voice.wake_debounce_ms / 1000,
            shared_model=shared_vosk,
        )
        command_recognizer = VoskStreamingCommandRecognizer(
            shared_vosk,
            sample_rate=voice.sample_rate,
        )
        loop = AlwaysOnVoiceLoop(
            voice,
            stream=PipeWirePcmStream(source=voice.microphone_source, sample_rate=voice.sample_rate),
            vad=SileroVad(),
            wake_detector=wake_detector,
            command_recognizer=command_recognizer,
            transcriber=WhisperTranscriber(model_name=voice.whisper_model),
            speaker=KokoroSpeaker(
                python_executable=args.kokoro_python,
                voice=voice.kokoro_voice,
                speed=voice.kokoro_speed,
            ),
            ask_fn=ask,
            action_presentation_completed_fn=complete_action_presentation,
            action_presentation_failed_fn=fail_action_presentation,
            action_response_expired_fn=expire_action_response,
            diagnostics=diagnostics,
        )
    except Exception as exc:  # noqa: BLE001 - service startup must be diagnosable
        print(json.dumps({"ok": False, "status": "failed", "error": f"{type(exc).__name__}: {exc}"}, sort_keys=True))
        return 2
    print(json.dumps({"ok": True, "status": "listening", "diagnostics": str(diagnostics.path)}, sort_keys=True), flush=True)
    return loop.run(stop_event)


if __name__ == "__main__":
    raise SystemExit(main())
