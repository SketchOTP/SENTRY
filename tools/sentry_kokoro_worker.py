"""One-shot local Kokoro synthesis worker.

This file is executed by an interpreter that already has the Kokoro package
installed. It reads one JSON request and writes one base64-encoded WAV response;
the caller keeps both the source text and audio transient.
"""

from __future__ import annotations

import base64
import io
import json
import sys

import numpy as np
import soundfile as sf
from kokoro import KPipeline


def main() -> int:
    request = json.loads(sys.stdin.readline())
    text = str(request.get("text", "")).strip()
    if not text:
        raise ValueError("text is required")
    voice = str(request.get("voice", "am_michael"))
    speed = float(request.get("speed", 0.9))
    language = "b" if voice.startswith("b") else "a"
    pipeline = KPipeline(lang_code=language, repo_id="hexgrad/Kokoro-82M")
    chunks = [np.asarray(audio, dtype=np.float32) for _, _, audio in pipeline(text, voice=voice, speed=speed, split_pattern=r"\n+")]
    if not chunks:
        raise RuntimeError("Kokoro produced no audio")
    output = io.BytesIO()
    sf.write(output, np.concatenate(chunks), 24_000, format="WAV", subtype="PCM_16")
    print(json.dumps({"audioBase64": base64.b64encode(output.getvalue()).decode("ascii")}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # keep protocol errors off stdout
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
