"""Run the governed in-memory dual-Vosk long-command acoustic screen."""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from typing import Any

import numpy as np
import torch
from kokoro import KPipeline

SENTRY_SITE = Path("/home/sketch/.venvs/sentry-ubuntu/lib/python3.12/site-packages")
if SENTRY_SITE.is_dir() and str(SENTRY_SITE) not in sys.path:
    sys.path.append(str(SENTRY_SITE))
import psutil  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from perception.always_on_voice import (  # noqa: E402
    AlwaysOnVoiceConfig,
    AlwaysOnVoiceLoop,
    SileroVad,
    VoiceDiagnostics,
    VoiceState,
)
from perception.vosk_kws import (  # noqa: E402
    VoskKwsEvaluator,
    VoskSharedModel,
    VoskStreamingCommandRecognizer,
)
from perception.voice import WhisperTranscriber  # noqa: E402


SAMPLE_RATE = 16_000
CHUNK_SAMPLES = 512


CASES = (
    (
        ("Sentry, prepare the file move", "source voice controlled move dot text", "destination Downloads streaming command cancellation proof dot text, wait for confirmation"),
        ("move", "voice", "control", "download", "streaming", "cancellation", "confirmation"),
    ),
    (
        ("Sentry, inspect the project read me", "find the security policy", "summarize the execution authority section"),
        ("inspect", "project", "security", "execution", "authority"),
    ),
    (
        ("Sentry, create a flat cartoon image", "show a fish with bat wings", "save it as winged fish preview dot P N G"),
        ("create", "fish", "bat", "wings", "preview"),
    ),
    (
        ("Sentry, open a browser", "look for Italian restaurant reservations nearby", "only report choices for two people tomorrow evening"),
        ("browser", "italian", "restaurant", "two", "tomorrow", "evening"),
    ),
    (
        ("Sentry, inspect my Downloads folder", "find image files only", "prepare to move them into Pictures after confirmation"),
        ("downloads", "image", "files", "pictures", "confirmation"),
    ),
    (
        ("Sentry, research tomorrow's weather", "use Mount Washington Kentucky", "report rain risk and the high temperature"),
        ("tomorrow", "weather", "mount", "washington", "rain", "temperature"),
    ),
    (
        ("Sentry, prepare an alarm", "set it for seven A M tomorrow", "call it morning office start and wait for confirmation"),
        ("alarm", "7am", "tomorrow", "morning", "office", "confirmation"),
    ),
    (
        ("Sentry, inspect the controlled workspace", "open testable math dot P Y", "explain the function without changing the file"),
        ("inspect", "controlled", "workspace", "testablemath", "changing"),
    ),
    (
        ("Sentry, check the current office status", "identify who is visible if evidence supports it", "then report the observation time in Eastern time"),
        ("office", "identify", "visible", "observation", "eastern"),
    ),
    (
        ("Sentry, review the recent execution audit", "count cancelled controlled actions", "do not reveal command text or private file contents"),
        ("execution", "audit", "cancelled", "command", "private", "contents"),
    ),
)


class SimulatedClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value


class MemorySpeaker:
    def speak(self, _text: str) -> bool:
        return True


class InactiveSpeechGate:
    def is_active(self) -> bool:
        return False


class RecordingCommandRecognizer:
    """Retain content-free progress coordinates around the real recognizer."""

    def __init__(self, delegate: VoskStreamingCommandRecognizer) -> None:
        self.delegate = delegate
        self.sample_cursor = 0
        self.progress_samples: list[int] = []
        self.processing_ms: list[float] = []
        self.max_finalized_segments = 0
        self.reset_count = 0

    @property
    def endpointer_mode(self) -> str:
        return self.delegate.endpointer_mode

    @property
    def last_result_class(self) -> str:
        return self.delegate.last_result_class

    def feed(self, pcm: np.ndarray):
        update = self.delegate.feed(pcm)
        self.sample_cursor += pcm.size
        self.processing_ms.append(update.processing_ms)
        self.max_finalized_segments = max(
            self.max_finalized_segments, update.finalized_segment_count
        )
        if update.progressed:
            self.progress_samples.append(self.sample_cursor)
        return update

    def reset(self) -> None:
        self.delegate.reset()
        self.sample_cursor = 0
        self.reset_count += 1


class TimedTranscriber:
    def __init__(self, delegate: WhisperTranscriber) -> None:
        self.delegate = delegate
        self.calls = 0
        self.elapsed_ms = 0.0
        self.last_text = ""
        self.last_samples = 0

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        started = time.perf_counter()
        self.calls += 1
        self.last_samples = audio.size
        self.last_text = self.delegate.transcribe(audio, sample_rate)
        self.elapsed_ms = (time.perf_counter() - started) * 1000.0
        return self.last_text


def _resample_24k_to_16k(audio: np.ndarray) -> np.ndarray:
    values = np.asarray(audio, dtype=np.float32)
    target = max(1, round(values.size * 2 / 3))
    positions = np.linspace(0, values.size - 1, target)
    return np.interp(positions, np.arange(values.size), values).astype(np.float32)


def _synthesize(pipeline: KPipeline, text: str) -> np.ndarray:
    chunks = [
        np.asarray(audio, dtype=np.float32)
        for _, _, audio in pipeline(text, voice="bm_george", speed=0.9)
    ]
    if not chunks:
        raise RuntimeError("Kokoro generated no screening audio")
    return _resample_24k_to_16k(np.concatenate(chunks))


def _normalize(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.casefold()))


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    return round(float(np.percentile(np.asarray(values), percentile)), 3)


def run(model_path: Path) -> dict[str, Any]:
    process = psutil.Process(os.getpid())
    rss_before_model = process.memory_info().rss
    shared = VoskSharedModel(model_path)
    rss_after_model = process.memory_info().rss
    probe_command = VoskStreamingCommandRecognizer(shared)
    rss_after_second_recognizer = process.memory_info().rss
    probe_command.close()

    pipeline = KPipeline(lang_code="b", repo_id="hexgrad/Kokoro-82M")
    whisper = WhisperTranscriber(model_name="tiny.en")
    cases: list[dict[str, Any]] = []
    all_processing_ms: list[float] = []
    all_partial_latencies_ms: list[float] = []
    all_whisper_ms: list[float] = []
    cpu_speaking = 0.0
    cpu_silence = 0.0

    for index, (parts, required_terms) in enumerate(CASES, start=1):
        generated = [_synthesize(pipeline, part) for part in parts]
        pause_one = np.zeros(int(2.0 * SAMPLE_RATE), dtype=np.float32)
        pause_two = np.zeros(int(3.0 * SAMPLE_RATE), dtype=np.float32)
        # Vosk may finalize its last acoustic segment after speech has ended.
        # Leave enough source silence for five seconds after that final progress
        # plus the 400 ms host stability recheck.
        final_idle = np.zeros(int(8.0 * SAMPLE_RATE), dtype=np.float32)
        command_audio = np.concatenate(
            [generated[0], pause_one, generated[1], pause_two, generated[2]]
        )
        complete_audio = np.concatenate([command_audio, final_idle])
        padding = (-complete_audio.size) % CHUNK_SAMPLES
        if padding:
            complete_audio = np.pad(complete_audio, (0, padding))

        speech_boundaries = (
            (0, generated[0].size),
            (generated[0].size + pause_one.size, generated[0].size + pause_one.size + generated[1].size),
            (
                generated[0].size + pause_one.size + generated[1].size + pause_two.size,
                command_audio.size,
            ),
        )
        chunks = [
            np.ascontiguousarray(complete_audio[offset : offset + CHUNK_SAMPLES])
            for offset in range(0, complete_audio.size, CHUNK_SAMPLES)
        ]
        clock = SimulatedClock()
        wake = VoskKwsEvaluator(
            model_path,
            detect_partial=True,
            partial_confirmation_frames=1,
            debounce_seconds=1.0,
            shared_model=shared,
        )
        command_delegate = VoskStreamingCommandRecognizer(shared)
        command = RecordingCommandRecognizer(command_delegate)
        transcriber = TimedTranscriber(whisper)
        dispatches: list[str] = []

        def ask(text: str, **_kwargs: Any) -> dict[str, Any]:
            dispatches.append(text)
            return {"answer": "Controlled screening answer.", "luna_invocations": 0}

        with tempfile.TemporaryDirectory(prefix="sentry-stream-screen-") as directory:
            loop = AlwaysOnVoiceLoop(
                AlwaysOnVoiceConfig(
                    minimum_speech_ms=250,
                    command_continuation_idle_ms=5000,
                    command_stability_recheck_ms=400,
                    command_trailing_tail_ms=500,
                    maximum_utterance_seconds=45,
                    timeline_capacity_seconds=50,
                    post_speech_rearm_ms=500,
                ),
                stream=None,
                vad=SileroVad(),
                wake_detector=wake,
                command_recognizer=command,
                transcriber=transcriber,
                speaker=MemorySpeaker(),
                ask_fn=ask,
                diagnostics=VoiceDiagnostics(Path(directory) / "voice.json"),
                speech_activity=InactiveSpeechGate(),
                clock=clock,
            )
            loop._set_state(VoiceState.LISTENING)
            no_early_dispatch = True
            cpu_start = time.process_time()
            for chunk_number, chunk in enumerate(chunks):
                clock.value += CHUNK_SAMPLES / SAMPLE_RATE
                loop.process_chunk(chunk)
                audio_end = (chunk_number + 1) * CHUNK_SAMPLES
                if audio_end < command_audio.size + int(4.95 * SAMPLE_RATE):
                    no_early_dispatch = no_early_dispatch and not dispatches
                if dispatches:
                    break
            cpu_total = time.process_time() - cpu_start
            speech_ratio = command_audio.size / max(1, complete_audio.size)
            cpu_speaking += cpu_total * speech_ratio
            cpu_silence += cpu_total * (1.0 - speech_ratio)

            progress = command.progress_samples
            resumed_progress = []
            for start, end in speech_boundaries[1:]:
                resumed_progress.append(
                    any(start <= sample <= end + SAMPLE_RATE for sample in progress)
                )
                if progress:
                    candidates = [sample for sample in progress if sample >= end]
                    if candidates:
                        all_partial_latencies_ms.append(
                            max(0.0, (min(candidates) - end) * 1000.0 / SAMPLE_RATE)
                        )
            normalized = _normalize(transcriber.last_text)
            core_ok = all(term in normalized for term in required_terms)
            captured_ms = float(loop.diagnostics.payload.get("capture_source_duration_ms", 0.0))
            whisper_ms = transcriber.last_samples * 1000.0 / SAMPLE_RATE
            case = {
                "case": index,
                "audio_duration_ms": round(complete_audio.size * 1000 / SAMPLE_RATE, 3),
                "spoken_command_duration_ms": round(command_audio.size * 1000 / SAMPLE_RATE, 3),
                "wake_count": int(loop.diagnostics.payload.get("wake_detections", 0)),
                "progress_count": len(progress),
                "resumed_regions_with_progress": sum(resumed_progress),
                "resumed_region_count": len(resumed_progress),
                "finalized_segments": command.max_finalized_segments,
                "no_early_dispatch": no_early_dispatch,
                "captured_source_duration_ms": captured_ms,
                "whisper_input_duration_ms": whisper_ms,
                "whisper_calls": transcriber.calls,
                "core_semantics": core_ok,
                "missing_terms": sorted(set(required_terms) - normalized),
                "dispatches": len(dispatches),
                "sample_gaps": int(loop.diagnostics.payload.get("capture_gap_count", 0)),
                "trailing_idle_trimmed_ms": loop.diagnostics.payload.get("trailing_idle_trimmed_ms"),
                "whisper_processing_ms": round(transcriber.elapsed_ms, 3),
            }
            cases.append(case)
            all_processing_ms.extend(command.processing_ms)
            all_whisper_ms.append(transcriber.elapsed_ms)
        wake.close()
        command_delegate.close()

    progress_passes = sum(item["progress_count"] > 0 for item in cases)
    resumed_passes = sum(
        item["resumed_regions_with_progress"] == item["resumed_region_count"]
        for item in cases
    )
    no_early_passes = sum(item["no_early_dispatch"] for item in cases)
    duration_passes = sum(
        item["captured_source_duration_ms"]
        >= item["spoken_command_duration_ms"] + 5000
        for item in cases
    )
    core_passes = sum(item["core_semantics"] for item in cases)
    one_dispatch_passes = sum(
        item["dispatches"] == 1 and item["whisper_calls"] == 1
        for item in cases
    )
    return {
        "model_path": str(model_path),
        "runtime_version": shared.runtime_version,
        "shared_model_rss_bytes": rss_after_model - rss_before_model,
        "second_recognizer_rss_bytes": rss_after_second_recognizer - rss_after_model,
        "process_rss_bytes": process.memory_info().rss,
        "screen": {
            "nonempty_progress": f"{progress_passes}/10",
            "progress_after_resumed_regions": f"{resumed_passes}/10",
            "no_early_close": f"{no_early_passes}/10",
            "complete_source_duration": f"{duration_passes}/10",
            "core_semantics": f"{core_passes}/10",
            "single_whisper_and_dispatch": f"{one_dispatch_passes}/10",
            "passed": (
                progress_passes >= 9
                and resumed_passes >= 9
                and no_early_passes == 10
                and duration_passes == 10
                and core_passes >= 8
                and one_dispatch_passes == 10
            ),
        },
        "performance": {
            "command_processing_median_ms": _percentile(all_processing_ms, 50),
            "command_processing_p95_ms": _percentile(all_processing_ms, 95),
            "partial_update_latency_median_ms": _percentile(all_partial_latencies_ms, 50),
            "partial_update_latency_p95_ms": _percentile(all_partial_latencies_ms, 95),
            "batch_whisper_median_ms": _percentile(all_whisper_ms, 50),
            "batch_whisper_p95_ms": _percentile(all_whisper_ms, 95),
            "estimated_speaking_cpu_seconds": round(cpu_speaking, 3),
            "estimated_silence_cpu_seconds": round(cpu_silence, 3),
        },
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.model.expanduser().resolve())
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["screen"]["passed"] else 1


if __name__ == "__main__":
    torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
    raise SystemExit(main())
