"""Run SENTRY's opt-in local always-available voice listener."""

from __future__ import annotations

import argparse
import json
import os
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
    VoiceState,
)
from perception.speaker_context import WakeIdentityCoordinator  # noqa: E402
from perception.sentry_perception import load_config  # noqa: E402
from perception.vosk_kws import (  # noqa: E402
    VoskKwsEvaluator,
    VoskSharedModel,
    VoskStreamingCommandRecognizer,
)
from perception.voice import KokoroSpeaker, PulseCachedWakeChime, WhisperTranscriber  # noqa: E402
from tools.sentry_office_vision import OfficeVisionInspector  # noqa: E402
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
        diagnostics = VoiceDiagnostics()
        if voice.sleep_enabled:
            diagnostics.update(
                state=VoiceState.SLEEPING.value,
                sleep_enabled=True,
                wake_enabled=False,
                vad_healthy=False,
                last_segment_outcome="sleep_enabled",
            )
            print(json.dumps({"ok": True, "status": "sleeping", "diagnostics": str(diagnostics.path)}, sort_keys=True), flush=True)
            return 0
        diagnostics.update(
            state=VoiceState.STARTING.value,
            sleep_enabled=False,
            wake_enabled=False,
            vad_healthy=False,
            last_segment_outcome="listener_starting",
        )
        if args.source:
            voice = AlwaysOnVoiceConfig(**{**voice.__dict__, "microphone_source": args.source})
        stop_event = threading.Event()
        for signum in (signal.SIGTERM, signal.SIGINT):
            signal.signal(signum, lambda *_: stop_event.set())
        invalidate_action_dialogue_for_restart()
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
        vision_inspector = OfficeVisionInspector(args.config.expanduser())

        def inspect_wake_identity(duration: float) -> dict[str, object]:
            metadata, image = vision_inspector.inspect(
                duration_seconds=duration,
                include_image=False,
                completion_timeout_seconds=voice.wake_identity_join_timeout_seconds,
            )
            if image is not None:  # defense in depth for the automatic path
                raise RuntimeError("wake identity inspection unexpectedly produced image bytes")
            return metadata

        identity_coordinator = WakeIdentityCoordinator(
            inspect_wake_identity,
            idle_seconds=voice.wake_identity_refresh_idle_seconds,
            ttl_seconds=voice.wake_identity_context_ttl_seconds,
            inspection_duration_seconds=voice.wake_identity_camera_duration_seconds,
            join_timeout_seconds=voice.wake_identity_join_timeout_seconds,
            profile_revision_provider=vision_inspector.profile_revision,
            cache_path=(Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "sentry" / "speaker-context.json"),
        )
        wake_chime = PulseCachedWakeChime()
        wake_chime.prepare()
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
                level_callback=lambda level: diagnostics.update(output_audio_level=round(level, 4)),
            ),
            ask_fn=ask,
            action_presentation_completed_fn=complete_action_presentation,
            action_presentation_failed_fn=fail_action_presentation,
            action_response_expired_fn=expire_action_response,
            diagnostics=diagnostics,
            identity_coordinator=identity_coordinator,
            wake_chime_fn=wake_chime.play,
        )
    except Exception as exc:  # noqa: BLE001 - service startup must be diagnosable
        print(json.dumps({"ok": False, "status": "failed", "error": f"{type(exc).__name__}: {exc}"}, sort_keys=True))
        return 2
    print(json.dumps({"ok": True, "status": "listening", "diagnostics": str(diagnostics.path)}, sort_keys=True), flush=True)
    try:
        return loop.run(stop_event)
    finally:
        wake_chime.close()


if __name__ == "__main__":
    raise SystemExit(main())
