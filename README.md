# SENTRY

SENTRY is a persistent, room-aware AI presence. The long-term goal is an embodied household intelligence that understands who is present, learns routines and preferences, maintains memory of physical events, and can decide when useful information should be spoken proactively.

The project intentionally begins much smaller: **one office, one Ubuntu Linux host, one V4L2 webcam, microphone, and speakers**. The office prototype must prove that persistent perception and proactive behavior are reliable before any whole-home expansion.

## Current status

**M0 is accepted. Current authorized milestone: Ubuntu platform re-baseline before fresh M1 live qualification.** Windows/DirectShow results remain historical; the previously verified 0202 detector and temporal room-state layer are being reproduced on Ubuntu through V4L2.

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
- report camera/assistant failures explicitly rather than inventing state.

## M1 implementation

The current local perception slice is documented in [`docs/M1_PERCEPTION.md`](docs/M1_PERCEPTION.md). It uses a bounded latest-frame buffer, the verified Open Model Zoo `person-detection-0202` detector through OpenVINO, a replaceable two-stage IoU tracker, and a timestamp-based `empty`/`occupied`/`degraded`/`offline` state aggregator. It produces metadata-only observations and makes zero Codex/Luna calls. Identity, persistence, semantic entry/exit events, and assistant integration remain later milestones.

## Explicitly out of V0.1

Do not expand the first build with ESP32s, mmWave, BLE room positioning, Wi-Fi CSI, Home Assistant, Frigate, multiple rooms/cameras, a TV avatar, autonomous smart-home control, or full routine learning. Those are later phases.

## Reuse strategy

### Accepted V0.1 reasoning layer

Direct OAuth-authenticated Codex/Luna invocation through the bounded SENTRY bridge is the accepted V0.1 reasoning layer. Perception remains local and never invokes Codex/Luna continuously.

DAWN feasibility work is preserved as historical evidence and architectural reference only. DAWN-derived code and the DAWN runtime are not part of the accepted V0.1 foundation. Any future change requires an explicit Architect decision.

### Miloco

[Xiaomi Miloco](https://github.com/XiaoMi/xiaomi-miloco) is architectural inspiration for the long-term perception -> identity -> memory -> routine -> proactive-decision loop. It is not a V0.1 dependency.

## Milestones

1. **M0 — Bootstrap + DAWN feasibility**: reproduce assistant environment; prove a synthetic `person.entered` event can reach the assistant and optionally produce speech.
2. **M1 — Camera + human presence**: stable Ubuntu V4L2 capture, person detection, tracking, diagnostics.
3. **M2 — Presence sessions + persistence**: temporal hysteresis, entry/exit events, SQLite history/API.
4. **M3 — Primary-user identity**: local enrollment, conservative recognition, unknown fallback.
5. **M4 — Conversational grounding**: assistant queries current and historical office state.
6. **M5 — Proactive arrival behavior**: eligibility gate, dedupe/cooldowns/budget, spoken action audit trail.
7. **M6 — Soak + acceptance**: at least 72 hours unattended with documented results.

Only after M6 passes should routine learning or multi-room hardware work begin.

## Key acceptance targets

- >=95% correct occupied/empty state over labeled representative intervals.
- Fewer than 1 false entry/exit transition per 8 hours of representative use.
- Entry generally confirmed within 3 seconds of clear visibility.
- Empty transition within the configured grace period, target <=25 seconds after actual departure.
- Target >=98% precision for accepted primary-user identifications; uncertain observations become `unknown`.
- 72-hour unattended run without manual process restart.
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
