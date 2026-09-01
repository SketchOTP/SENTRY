# Project Goal

> **Owner scope supersession — 2026-08-31.** This goal replaces the earlier
> whole-home framing. SENTRY is a **one-room office product** unless the owner
> explicitly reverses that decision. Historical whole-home and TV references
> are retained as history only; they are not future product assumptions.

## Goal
Build SENTRY into an embodied office intelligence that maintains a grounded,
evolving understanding of the physical office and uses that context to provide
useful, appropriately restrained assistance.

## Objective success criteria
- SENTRY maintains reliable local world state for the office and preserves physical-event history.
- The V0.1 office prototype can detect presence, conservatively identify an enrolled primary user, track sessions, and expose grounded state to an assistant.
- The assistant can answer office-state questions and may speak proactively when a deterministic policy finds a useful, non-duplicative reason.
- The system fails explicitly when perception or assistant services are unavailable and does not invent occupancy or identity.
- A documented, unattended acceptance run demonstrates reliable office behavior.

## Non-goals
- SENTRY is not a whole-home deployment, security alarm, medical system,
  emergency monitor, or life-safety system.
- SENTRY does not require ESP32s, Home Assistant, Frigate, mmWave, BLE room
  positioning, Wi-Fi CSI, multiple rooms/cameras, a TV avatar, or autonomous
  smart-home control.

## Hard constraints
- The complete physical scope is one office using the current Ubuntu Linux host,
  one V4L2 webcam, microphone, speakers, canonical Atlas storage, and available
  CPU/GPU resources.
- Raw webcam frames and biometric enrollment data remain local by default and out of source control.
- SENTRY owns grounded physical events and sessions locally; an LLM is not the continuous vision processor or physical-event database.
- Direct OAuth-authenticated Codex CLI invocation is SENTRY's agent layer. The
  operator-authorized V0.3 profile gives Codex native web, installed skills,
  image generation, shell/file work, and typed local SENTRY/desktop MCP tools.
  SENTRY owns physical truth and local persistence; Codex selects and uses
  tools from natural language. DAWN remains historical reference only.
- New dependencies, upstream derivation/forking, cloud video, infrastructure expansion, and scope changes require documented evidence and Architect authorization.
- Vosk with the single wake token `Sentry` is the operator-selected and
  committed V0.3.1 wake authority, qualified at `a3f6d67`. Conversational uses
  of that token are accepted activations. Always-available voice remains
  opt-in and inactive unless the operator explicitly enables it.

## Goal-change rule
The project goal may change only through explicit user/authorized strategic decision. Roadmaps, milestones, and implementation plans may change when evidence changes without rewriting historical records.
