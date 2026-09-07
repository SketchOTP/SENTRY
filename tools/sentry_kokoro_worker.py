"""Local Kokoro synthesis worker.

This file is executed by an interpreter that already has the Kokoro package
installed. The default mode reads one JSON request and writes one
base64-encoded WAV response. ``--persistent`` keeps the Kokoro pipeline loaded
and serves newline-delimited requests so the caller keeps both source text and
audio transient without paying model startup for every response.
"""

from __future__ import annotations

import base64
import io
import json
import sys

import numpy as np
import soundfile as sf
from kokoro import KPipeline


def _load_pipeline(voice: str) -> KPipeline:
    language = "b" if voice.startswith("b") else "a"
    return KPipeline(lang_code=language, repo_id="hexgrad/Kokoro-82M")


def _synthesize(pipeline: KPipeline, request: dict[str, object]) -> str:
    text = str(request.get("text", "")).strip()
    if not text:
        raise ValueError("text is required")
    voice = str(request.get("voice", "bm_george"))
    speed = float(request.get("speed", 0.9))
    chunks = [
        np.asarray(audio, dtype=np.float32)
        for _, _, audio in pipeline(text, voice=voice, speed=speed, split_pattern=r"\n+")
    ]
    if not chunks:
        raise RuntimeError("Kokoro produced no audio")
    output = io.BytesIO()
    sf.write(output, np.concatenate(chunks), 24_000, format="WAV", subtype="PCM_16")
    return base64.b64encode(output.getvalue()).decode("ascii")


def _persistent_main(default_voice: str) -> int:
    pipeline = _load_pipeline(default_voice)
    pipeline_language = "b" if default_voice.startswith("b") else "a"
    print(json.dumps({"ready": True}), flush=True)
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError("request must be an object")
            voice = str(request.get("voice", default_voice))
            language = "b" if voice.startswith("b") else "a"
            if language != pipeline_language:
                pipeline = _load_pipeline(voice)
                pipeline_language = language
            print(
                json.dumps({"ok": True, "audioBase64": _synthesize(pipeline, request)}),
                flush=True,
            )
        except Exception as exc:  # keep request errors inside the line protocol
            print(json.dumps({"ok": False, "error": type(exc).__name__}), flush=True)
    return 0


def main() -> int:
    arguments = sys.argv[1:]
    persistent = "--persistent" in arguments
    voice = "bm_george"
    if "--voice" in arguments:
        voice_index = arguments.index("--voice") + 1
        if voice_index >= len(arguments):
            raise ValueError("--voice requires a value")
        voice = arguments[voice_index]
    if persistent:
        return _persistent_main(voice)

    request = json.loads(sys.stdin.readline())
    if not isinstance(request, dict):
        raise ValueError("request must be an object")
    print(json.dumps({"audioBase64": _synthesize(_load_pipeline(str(request.get("voice", voice))), request)}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # keep protocol errors off stdout
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
