# Pre-M6 — Reactive Voice

SENTRY's bounded reactive voice path is an explicitly invoked, push-to-talk
request. It is not an always-listening, wake-word, barge-in, or background
worker system.

```text
PipeWire microphone
  -> in-memory 16 kHz PCM
  -> local OpenAI Whisper (CPU, tiny.en)
  -> existing M4 localhost fact retrieval and grounded Luna turn
  -> local Kokoro synthesis (am_michael, 0.9x) -> explicit 24 kHz mono PipeWire speaker playback
```

## Runtime

The isolated Ubuntu environment pins `openai-whisper==20250625` alongside the
existing OpenCV/OpenVINO runtime. Whisper model weights are cached under the
user-local `~/.cache/whisper` directory and are not part of Atlas project
storage or Git. The microphone stream is never written to a WAV or other
recording file; PCM is discarded after transcription.

Kokoro is used through an already-installed local Python runtime, not through a
remote service. SENTRY invokes its one-shot local worker, keeps the generated
WAV in memory, and sends it directly to this host's `pw-play` without creating
an audio file. Set `SENTRY_KOKORO_PYTHON` (or pass `--kokoro-python`) to the
local Python interpreter containing the Kokoro package. Run one request after
starting the localhost state API:

```bash
/home/sketch/.venvs/sentry-ubuntu/bin/python tools/sentry_state_api.py \
  --database /home/sketch/.local/share/sentry/sentry.db \
  --atlas-mirror /srv/ATLAS/100_ACTIVE/Projects/SENTRY/perception-data/runtime/backups/sentry.db \
  --host 127.0.0.1 --port 48174

/home/sketch/.venvs/sentry-ubuntu/bin/python tools/sentry_voice.py \
  --base-url http://127.0.0.1:48174 --duration-seconds 5 \
  --kokoro-python /path/to/local/kokoro/python
```

Press Enter, watch the visible countdown, and speak only after `START SPEAKING
NOW`. SENTRY returns structured metadata for the transcript, M4 grounding
classification, Luna invocation count, and local delivery result. Audio,
Whisper tensors, and embeddings are not included in that result.

When a graphical Ubuntu session is available, a temporary Zenity window titled
`SENTRY Reactive Voice` is shown locally. It displays `GET READY`, the countdown,
`SPEAK NOW`, and `DONE`; it is closed after the request and stores no media.
Use `--no-indicator` only for headless runs.

## Qualification evidence

The physical proof used the default PipeWire source, which was the NexiGo
microphone, at 16 kHz mono. One bounded five-second request was captured in
memory and transcribed semantically as `in the office. Is anyone`; the existing
M4 path made exactly one low-effort OAuth `gpt-5.6-luna` call and returned a
truthful `partial` answer because the live database had no current room state.
The corrected proof must use `tiny.en` and the local Kokoro runtime. No audio
file is persisted, and a no-speech/failure path makes zero M4/Luna calls.

The first physical attempt exposed and corrected a pipe-drain bug in the
PipeWire recorder. It was not treated as STT or grounding evidence. Focused
voice tests and the full Ubuntu regression passed after the correction.

Reactive voice is accepted at commit `1ce3e611`. M6 is the active final
acceptance gate with a 30-minute unattended soak; the earlier 72-hour
requirement is waived and must not be resurrected.
