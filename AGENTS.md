# AGENTS.md — SENTRY AI Coder Contract

## Mission

Build SENTRY from the formal scope in [`docs/PROJECT_SCOPE.md`](docs/PROJECT_SCOPE.md). SENTRY is a persistent room-aware AI presence. The current authorized implementation is **V0.1: one office, one Windows PC, one webcam, microphone, and speakers**.

Do not assume any prior conversation context. Everything required to understand the project should be derivable from this repository plus the linked Notion scope.

## Authority

1. Product intent and scope: SENTRY Notion page and `docs/PROJECT_SCOPE.md`.
2. Implementation reality: repository code, tests, logs, and measured runtime evidence.
3. Upstream behavior: current upstream documentation/source, verified before depending on it.

If scope and implementation evidence conflict, do not silently reinterpret either. Record the conflict and make the smallest justified change.

## Current authorized milestone

**M0 — Bootstrap and DAWN feasibility spike.**

Do not jump ahead into a full perception stack until the assistant integration path has been demonstrated with a synthetic event.

Required first vertical slice:

```text
synthetic person.entered event
-> SENTRY event contract
-> assistant bridge
-> assistant receives grounded context
-> optional spoken response
```

Then place real webcam perception behind the same contract.

## Core implementation rules

- Do not use an LLM as the continuous camera processor.
- Webcam frames remain local by default.
- Convert perception into structured state/events before involving an LLM.
- Prefer `unknown` to a wrong human identity.
- Camera unavailable means `degraded`/`offline`, never fabricated `empty`.
- Keep physical event/session history in SENTRY storage, not only assistant memory.
- Use SQLite for V0.1 unless measured evidence demonstrates a real need for more infrastructure.
- Keep detector, tracker, identity model, and assistant integrations behind replaceable interfaces.
- Use bounded queues/backoff; do not accumulate stale frames or hot-retry failures.
- All meaningful state transitions and proactive decisions must be diagnosable from logs/data.
- Do not commit private recordings, enrollment photos, face embeddings, generated databases, secrets, model caches, or large model weights.

## Reuse before rebuild

D.A.W.N. is the preferred assistant foundation under evaluation:
https://github.com/The-OASIS-Project/dawn

Before implementing duplicate voice, memory, weather, scheduling, or proactive-assistant infrastructure, inspect current DAWN capabilities and determine whether they can be reused.

Treat DAWN as external upstream initially. DAWN is GPLv3. Do not copy/fork substantial DAWN code without documenting the integration need and license consequences.

Xiaomi Miloco is architectural reference only:
https://github.com/XiaoMi/xiaomi-miloco

Do not add Xiaomi hardware/service dependencies to V0.1.

## Scope guardrails

Do not add the following to make the office prototype pass:

- ESP32 hardware
- mmWave sensors
- BLE room tracking
- Wi-Fi CSI
- Home Assistant
- Frigate
- multiple rooms
- multiple cameras unless the single-camera requirement is objectively impossible and documented
- TV/avatar embodiment
- smart-home actuation
- full routine learning
- cloud continuous-video analysis

Those are later phases.

## Preferred implementation shape

Use a small Python service on Windows unless measurement or upstream integration requires otherwise.

Expected logical modules:

```text
camera -> detector/tracker -> identity -> presence state machine
                                      -> semantic events
                                      -> SQLite sessions/history
                                      -> local API/event stream
                                      -> assistant bridge
                                      -> proactive policy
```

Do not create empty abstraction layers solely to match a diagram. Build only what the current vertical slice needs.

## Engineering requirements

- Type public/domain interfaces.
- Pin dependencies reproducibly.
- Use schema migrations from database version 1.
- Store timezone-aware timestamps.
- Add unit tests for hysteresis/state transitions before relying on live testing alone.
- Add integration tests for persistence/restart and API contracts.
- Verify code **and model-weight licenses** for any vision/identity dependency.
- Provide `.env.example`/example configuration, never real secrets.
- Keep local APIs on loopback by default.
- Use structured logging.
- Document commands required to reproduce each milestone on Windows.

## Required domain states

Room state:
- `empty`
- `occupied`
- `degraded`
- `offline`

Identity state should distinguish at least:
- recognized enrolled person
- unknown person
- unresolved/not evaluated

Presence and identity are separate. A face disappearing does not mean a person left.

## Minimum semantic events

- `room.camera_online`
- `room.camera_offline`
- `room.became_occupied`
- `room.became_empty`
- `person.entered`
- `person.identified`
- `person.identity_changed`
- `person.left`
- `person.unknown_entered`
- `presence.session_started`
- `presence.session_ended`
- `system.started`
- `system.stopped`
- `system.error`

Events are append-oriented and versioned.

## Proactivity rule

Physical event does **not** automatically mean speech.

Use:

```text
stable event
-> enrich context
-> deterministic eligibility/dedupe/cooldown gate
-> optional LLM judgment
-> speak or remain silent
-> persist decision + suppression reason
```

Silence is a successful outcome when there is nothing useful to say.

## Milestone order

- M0 Bootstrap + DAWN integration feasibility
- M1 Camera + human presence
- M2 Presence sessions + persistence
- M3 Primary-user identity
- M4 Conversational grounding
- M5 Proactive arrival behavior
- M6 72-hour soak + acceptance

Routine learning begins only after M6 passes.

## Completion discipline

At the end of each milestone:

1. Run the defined acceptance tests.
2. Record actual evidence/results.
3. Update README/project documentation to match reality.
4. State known failures and limitations.
5. Identify the next bounded milestone.
6. Do not describe future capabilities as implemented.

Read `docs/PROJECT_SCOPE.md` in full before coding.