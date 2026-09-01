# SENTRY

SENTRY is a persistent, one-room AI resident for the office. Its product goal is
to become deeply useful, natural, private, and reliable in that one room:
trusted physical awareness, grounded conversation, explicit memory and
preferences, relevant context, and restrained assistance.

**Owner scope lock:** whole-home/multi-room expansion, second cameras,
cross-camera Re-ID, distributed sensing, ESP32/mmWave/BLE/Wi-Fi CSI, Home
Assistant expansion, and TV embodiment are **SUPERSEDED BY OWNER DIRECTION**.
They are not expected future phases unless the owner explicitly reopens them.

## Current status

**SENTRY V0.1 is accepted within the office-only boundary:** M0, practical M1 presence, M2 durable presence memory, M3 primary-user identity, M4 grounded conversation, M5 restrained proactivity, reactive voice, and the 30-minute unattended M6 integration soak passed within their recorded evidence boundaries. Historical detector edge cases and the M3 simultaneous-person limitation remain documented operational risks. The live SQLite database is local to the Ubuntu host; Atlas receives integrity-checked SQLite snapshots and remains the shared durable mirror. The owner/operator permanently waived the former 72-hour soak in favor of the passed 30-minute final soak.

**V0.2 resident runtime, routine statistics, routine-grounded conversation, preference/feedback memory, weather context, contextual weather proactivity, and event-triggered reminders are qualified. V0.3.1 always-available voice is qualified:** the accepted one-room stack includes Vosk wake, Whisper command STT, grounded conversation, and local Kokoro speech. Schema 8 remains current. Production NWS weather uses private local coordinates and a cache-refresh timer. Reminders remain explicit, durable, at-most-once local speech.

**Current implementation work:** the production conversation entry point now
uses Codex directly as SENTRY's agent. A dedicated write-capable profile exposes
local SENTRY/desktop MCP tools while retaining native web search, installed
skills/plugins, image generation, and shell/file workflows. See
[`docs/V0.3_CODEX_NATIVE_AGENT.md`](docs/V0.3_CODEX_NATIVE_AGENT.md).

## Project links

- Product/spec authority: [SENTRY Notion page](https://app.notion.com/p/3c5833cb27ff8065aa88eff1089970a8)
- Repository: https://github.com/SketchOTP/SENTRY
- SSH clone: `git@github.com:SketchOTP/SENTRY.git`
- Full repository scope: [`docs/PROJECT_SCOPE.md`](docs/PROJECT_SCOPE.md)
- AI-coder operating rules: [`AGENTS.md`](AGENTS.md)

## V0.1 goal

Prove this end-to-end loop on the main office PC:

```text
Office webcam
  -> local person detection/tracking
  -> conservative identity resolution
  -> stable presence state machine
  -> semantic entry/exit events
  -> persistent SQLite history
  -> assistant bridge
  -> conversational grounding
  -> optional proactive spoken response
```

The LLM is **not** the continuous vision processor. Computer vision converts webcam frames into structured state and events; the assistant consumes those facts.

## V0.1 required behavior

SENTRY must be able to:

- run persistently on the Ubuntu host;
- detect whether the office is empty or occupied;
- track one or more visible people;
- recognize the enrolled primary user when evidence is sufficient;
- use `unknown` instead of guessing an identity;
- generate stable entry/exit/session events without flickering on brief occlusions;
- persist sessions and events locally;
- recover cleanly after restart;
- answer questions such as “Who is in the office?”, “When did I come in?”, and “How long have I been here?” from actual SENTRY data;
- allow a physical event to become a proactive assistant candidate;
- suppress duplicate/repetitive speech with cooldowns and an interruption budget;
- remember one explicit primary-user acknowledgement preference and auditable feedback;
- accept one explicitly invoked microphone question through local Whisper STT, grounded M4 answering, and local speaker delivery;
- report camera/assistant failures explicitly rather than inventing state.

## M1 implementation

The current local perception slice is documented in [`docs/M1_PERCEPTION.md`](docs/M1_PERCEPTION.md). It uses a bounded latest-frame buffer, the current locally hosted YOLOX-S detector through OpenVINO, a replaceable two-stage IoU tracker, and a timestamp-based `empty`/`occupied`/`degraded`/`offline` state aggregator. Structured metadata is recorded by the M2 SQLite history slice; M3 adds conservative YuNet/SFace identity annotations. Raw frames and biometric prototypes remain local-only and are never source-controlled.

## Explicitly out of V0.1

Do not expand the product with ESP32s, mmWave, BLE room positioning, Wi-Fi CSI,
Home Assistant, Frigate, multiple rooms/cameras, or TV embodiment. Those
directions are superseded, not deferred milestones.

## V0.2 Resident Runtime

The resident deployment is documented in [`docs/V0.2_RESIDENT_RUNTIME.md`](docs/V0.2_RESIDENT_RUNTIME.md). Install the supervised stack with:

```bash
/home/sketch/.venvs/sentry-ubuntu/bin/python tools/sentry_install_user_services.py
```

The live SQLite database remains local to the Ubuntu host and Atlas continues to receive complete integrity-checked snapshots. The continuous proactive processor polls persisted events at a bounded cadence; perception remains local and makes zero Codex/Luna calls. Routine statistics are available through the separate scheduled refresh described below; learned routine facts remain gated from conversation and proactivity.

## V0.2 Routine Statistics

The transparent routine-statistics foundation is documented in [`docs/V0.2_ROUTINE_STATISTICS.md`](docs/V0.2_ROUTINE_STATISTICS.md). Refresh or inspect derived snapshots with:

```bash
/home/sketch/.venvs/sentry-ubuntu/bin/python tools/sentry_routines.py refresh --config ~/.config/sentry/config.json
/home/sketch/.venvs/sentry-ubuntu/bin/python tools/sentry_routines.py show --config ~/.config/sentry/config.json
```

The production result is currently `insufficient` because natural history is sparse. Routine snapshots never override physical state or feed M5. Their bounded conversational use is documented in [`docs/V0.2_ROUTINE_GROUNDED_CONVERSATION.md`](docs/V0.2_ROUTINE_GROUNDED_CONVERSATION.md). Preference and feedback memory is documented in [`docs/V0.2_PREFERENCE_FEEDBACK_MEMORY.md`](docs/V0.2_PREFERENCE_FEEDBACK_MEMORY.md).

## V0.2 Weather Context

The read-only NWS weather foundation is documented in [`docs/V0.2_WEATHER_CONTEXT.md`](docs/V0.2_WEATHER_CONTEXT.md). It uses schema-v7 snapshots, explicit operator coordinates, bounded retries, 24-hour point-resource caching, freshness states, and the localhost-only `/v1/weather` endpoint. Production weather is not enabled until explicit coordinates are supplied in the local configuration.

The historical read-only public-web extension is documented in [`docs/V0.3_READ_ONLY_WEB.md`](docs/V0.3_READ_ONLY_WEB.md). It has been superseded for the production conversation path by the operator-authorized Codex-native agent described in [`docs/V0.3_CODEX_NATIVE_AGENT.md`](docs/V0.3_CODEX_NATIVE_AGENT.md). Native public web search remains available, while local code/file and desktop actions are now also permitted when naturally requested.

## V0.2 Event Reminders

The one-shot reminder capability is documented in [`docs/V0.2_EVENT_REMINDERS.md`](docs/V0.2_EVENT_REMINDERS.md). It supports one explicit `next_primary_user_office_session` reminder for the primary user, excludes the creation session, claims before speech, survives restart without replay, and keeps unsupported scheduler shapes out of scope.

## V0.3 Always-Available Voice

The qualified, opt-in local listener is documented in [`docs/V0.3_ALWAYS_ON_VOICE.md`](docs/V0.3_ALWAYS_ON_VOICE.md). It provides `PipeWire → local Vosk “Sentry” wake detection → VAD/Whisper tiny.en command capture → bounded conversational orchestration → Kokoro/PipeWire`, while keeping ambient audio ephemeral and never enabling continuous listening without explicit local configuration. `Sentry` is the owner-selected wake token; ordinary conversational uses of that word are accepted activations.

## Reuse strategy

### Accepted V0.1 reasoning layer

Direct OAuth-authenticated Codex/Luna invocation through the bounded SENTRY bridge is the accepted V0.1 reasoning layer. Perception remains local and never invokes Codex/Luna continuously.

DAWN feasibility work is preserved as historical evidence and architectural reference only. DAWN-derived code and the DAWN runtime are not part of the accepted V0.1 foundation. Any future change requires an explicit Architect decision.

### Miloco

[Xiaomi Miloco](https://github.com/XiaoMi/xiaomi-miloco) is architectural inspiration for the long-term perception -> identity -> memory -> routine -> proactive-decision loop. It is not a V0.1 dependency.

## Milestones

1. **M0 — Bootstrap + DAWN feasibility**: reproduce assistant environment; prove a synthetic `person.entered` event can reach the assistant and optionally produce speech.
2. **M1 — Camera + human presence**: stable Ubuntu V4L2 capture, person detection, tracking, diagnostics (accepted foundation).
3. **M2 — Presence sessions + persistence**: temporal hysteresis, entry/exit events, local SQLite history/API, and Atlas snapshot mirroring (accepted).
4. **M3 — Primary-user identity**: local enrollment, conservative recognition, unknown/unresolved fallback (accepted within bounded evidence).
5. **M4 — Conversational grounding**: assistant queries current and historical office state.
6. **M5 — Restrained proactive behavior**: persisted-event eligibility, dedupe/cooldowns/budget, bounded Luna judgment, local speech audit trail (qualified within bounded physical-event evidence).
7. **M6 — Soak + acceptance**: 30 minutes unattended with documented results (owner/operator waiver of the former 72-hour requirement).
8. **V0.2 — Resident runtime**: supervised auto-starting perception, API, and proactive services with bounded restart/recovery (qualified).
9. **V0.2 — Routine statistics foundation**: deterministic, timezone-aware, interruption-filtered derived summaries with schema-v5 persistence, localhost API, and scheduled refresh (qualified; production data currently insufficient).
10. **V0.2 — Routine-grounded conversation**: deterministic routine intent/scope routing, maturity-aware bounded fact packets, and truthful sparse-history answers through M4 (qualified).
11. **V0.2 — Preference + feedback memory**: one explicit reversible acknowledgement preference, auditable proactive feedback, and deterministic M5 suppression (qualified).
12. **V0.2 — Read-only weather context**: explicit-location NWS snapshots, freshness-gated localhost weather facts, and an independent refresh timer (qualified; production location not configured).
13. **V0.2 — Event-triggered reminders**: one explicit next-office-session reminder with deterministic intent/API handling, same-session exclusion, durable claim-before-speech delivery, and restart-safe dedupe (qualified).
14. **V0.3.1 — Always-available voice foundation**: optional local Vosk `Sentry` wake detection, VAD/Whisper command capture, bounded conversational orchestration, and shared TTS capture suppression (qualified; opt-in).
15. **V0.3 — Codex-native agent surface**: direct natural-language Codex turns with local SENTRY/desktop MCP tools, native web, installed skills/plugins, image generation, and explicit local write capability (active qualification).

M6 and V0.2 are accepted. Routine facts entering proactive judgment and general scheduling require a new Architect directive. Multi-room and whole-home hardware are superseded by the permanent one-room product scope.

## Key acceptance targets

- >=95% correct occupied/empty state over labeled representative intervals.
- Fewer than 1 false entry/exit transition per 8 hours of representative use.
- Entry generally confirmed within 3 seconds of clear visibility.
- Empty transition within the configured grace period, target <=25 seconds after actual departure.
- Target >=98% precision for accepted primary-user identifications; uncertain observations become `unknown`.
- 30-minute unattended run without manual process restart.
- No lost completed sessions across normal restart.
- One semantic event creates at most one proactive spoken action unless a genuinely new event occurs.

## Development principle

Build the smallest vertical slice first. Do not create a large framework before proving the event-to-assistant path.

```text
synthetic office event
  -> stable SENTRY event contract
  -> assistant bridge
  -> assistant understands grounded event
  -> optional spoken response
```

Then place real webcam perception behind the same contract.

Read [`docs/PROJECT_SCOPE.md`](docs/PROJECT_SCOPE.md) before implementing anything.
