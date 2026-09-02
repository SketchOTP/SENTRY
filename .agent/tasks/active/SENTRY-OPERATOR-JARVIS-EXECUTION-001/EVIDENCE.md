# Evidence — SENTRY-OPERATOR-JARVIS-EXECUTION-001

## Starting state

- Repository: `/srv/ATLAS/100_ACTIVE/Projects/SENTRY`
- Starting HEAD/origin: `1fbf1170535ca43c91fffcfb4c006652ac0b8b43`
- Working tree: clean
- Schema: 8
- Full regression: 243/243
- Existing agent: one direct ephemeral Codex turn with native web, image
  generation, shell/files, installed skills/plugins, and 25 SENTRY MCP tools.
- Existing voice: Vosk `Sentry` -> Whisper `tiny.en` -> SENTRY ask -> Kokoro.

## Implementation

- One direct ephemeral Codex turn remains the production natural-language
  authority. The prompt now presents SENTRY as the visible persona, executes
  compound requests strictly in spoken order, and returns a schema-validated
  ordered result for every requested step.
- SENTRY Office MCP expanded from 25 to 29 tools: durable alarm list/create/
  cancel plus safe display of an operator-home artifact.
- Schema 9 adds bounded primary-user one-shot alarms with offset-aware UTC
  storage, IANA display timezone, maximum 32 pending, provenance idempotence,
  claim-before-speech, durable success/failure/cancellation, and conservative
  claimed-restart failure rather than replay.
- `sentry-alarms.timer` performs a 15-second lightweight check. Kokoro is loaded
  lazily only when an alarm is due; observed idle command time was 0.20-0.27 s.
- All normal SENTRY speech defaults to Kokoro 0.9.4 `bm_george` at 0.9x.
- Always-on voice accepts one bounded 45-second compound utterance and permits
  a bounded 900-second Codex turn. Starting `sentry-voice.service` now also
  starts the coupled visible Zenity SENTRY state window.
- Explicit resident flags keep continuous perception and proactivity disabled;
  Codex may invoke the existing bounded ephemeral camera inspection when a
  current visual request needs it.

## Automated evidence

- Focused final voice/Codex/MCP/desktop/service/alarm suites: 48/48.
- Schema/persistence/weather/routine/preference/reminder/proactivity affected
  suite: 88/88 before the final installer-policy assertion.
- Full Ubuntu regression on the final runtime implementation: 253/253.
- Schema-9 migration, Atlas restore, API, local display time, alarm
  idempotence/cancellation, speech success/failure, and uncertain-restart
  no-replay are covered.

## Live evidence

- Production SQLite was backed up to
  `/home/sketch/.local/share/sentry/backups/sentry-pre-schema9-20260901.db`,
  migrated normally to schema 9, and remained healthy through the localhost
  API. Existing history was not rewritten.
- One 5-step direct-agent turn completed in exact order in 127.482 s:
  opened a public Italian restaurant reservation page without submitting;
  generated, verified, displayed, and visually inspected a flat-cartoon fish
  with bat wings; moved only the named 691-byte Downloads fixture without a
  collision; researched tomorrow's Mount Washington weather; and created,
  verified, then cancelled the exact 10-minute qualification alarm.
- Generated artifact:
  `/home/sketch/Pictures/SENTRY/generated/fish-with-bat-wings-20260901.png`.
- On-demand office question used stale-safe current-state lookup followed by
  `inspect_office_camera`; it observed an empty room, returned no identity, and
  persisted no frame.
- British-male Kokoro conversational speech and an isolated real alarm delivery
  both succeeded. Listener dispatch count remained 0 before/after each spoken
  output, proving shared speech-lock self-trigger suppression.
- The production qualification alarm is durably `cancelled`; no pending test
  alarm remains.

## Runtime and privacy

- Local configuration and dedicated Codex profile remain mode 0600.
- Enabled/active: `sentry-state-api.service`, `sentry-voice.service`, coupled
  `sentry-voice-status.service`, `sentry-weather.timer`, and
  `sentry-alarms.timer`.
- Disabled/inactive: `sentry-perception.service` and
  `sentry-proactive.service`; camera work is request-scoped through MCP.
- `Linger=no` remains unchanged.
- Current listener status is `LISTENING`; one `pw-record` is the intentional
  single microphone owner.
- Inspection found no runtime WAV, PCM dump, microphone recording, ambient
  transcript, transcript archive, or audio-derived embedding. The camera frame
  and voice audio remained ephemeral.
