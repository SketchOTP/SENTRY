# M5 — Restrained Proactivity

M5 adds one bounded proactive event class: a persisted `person.identified`
event for `primary_user` in the current occupied office session. Proactivity is
processed after the event is committed; the camera/perception loop remains
local and makes zero Luna calls.

## Runtime boundary

```text
persisted person.identified
  -> deterministic eligibility gate
  -> one reserved proactive_actions row
  -> bounded allow-listed fact packet
  -> optional one-turn gpt-5.6-luna judgment
  -> local Speech Dispatcher delivery or silence
  -> finalized action record
```

The live SQLite database remains on the Ubuntu host. Schema migration 4 adds
`proactive_actions`; existing Atlas mirroring covers it through the normal
SQLite backup path. No frames, embeddings, or identity prototypes enter the
fact packet or action log.

## Default policy

The example configuration keeps the master switch disabled until an operator
explicitly enables proactivity. Defaults are:

```text
event_ttl_seconds = 30
same_session_max_actions = 1
person_cooldown_minutes = 30
global_max_spoken_actions_per_hour = 2
startup_suppression_seconds = 30
judge_effort = low
max_utterance_words = 20
max_utterance_chars = 160
```

Deterministic suppressions never call Luna. Reasons are machine-readable,
including `disabled`, `unsupported_event`, `non_primary`, `stale`,
`room_not_occupied`, `source_unhealthy`, `restart_reconciled`, `duplicate`,
`already_handled_session`, `cooldown`, `hourly_budget`,
`startup_suppression`, `speech_busy`, `judge_silent`, `judge_invalid`, and
`delivery_failed`.

## Commands

Process recent persisted identity events using the configured policy:

```bash
/home/sketch/.venvs/sentry-ubuntu/bin/python tools/sentry_proactive.py --process-all
```

Run the isolated physical proof with the active enrolled profile copied in
memory into a local qualification database and mirrored only as an Atlas
snapshot:

```bash
/home/sketch/.venvs/sentry-ubuntu/bin/python tools/sentry_m5_live.py \
  --database /home/sketch/.local/share/sentry/m5-qualification/sentry.db \
  --mirror /srv/ATLAS/100_ACTIVE/Projects/SENTRY/perception-data/runtime/m5-qualification/sentry.db \
  --duration 150
```

Perception starts before any operator prompt. The operator must type
`CONFIRMED_EMPTY`; the harness then requires a persisted online/empty,
session-free baseline for a bounded stable interval, waits out startup
suppression while perception continues, and prints `PRIMARY_USER_ENTER_NOW`.
The physical event must be produced by the real perception/identity path. The
separate processor observes committed events, so continuous perception remains
at zero Luna calls.

## Speech boundary

`perception.proactive.SpeechDispatcher` uses the existing local `spd-say`
binary with notification priority, bounded wait, and cancellation. It does
not add cloud TTS, a voice server, a queue, VAD, or barge-in infrastructure.

## Qualification boundary

Automated policy, privacy, restart, dedupe, cooldown, budget, and fail-silent
tests are required before physical qualification. A physical run must show a
real persisted `person.identified` event reaching the processor. The corrected
handoff run now establishes that chain and the replay dedupe proof; M5 remains
bounded to one primary-user event class. M6 unattended soak remains gated
until Architect review accepts this result.
