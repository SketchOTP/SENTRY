# Task Packet — SENTRY-M0-DAWN-FEASIBILITY-001

## Objective

Prove or decisively block the least invasive supported path for:

`synthetic person.entered → SENTRY event contract → DAWN grounded environmental context → assistant response → optional speech`

## Scope

- Inspect current DAWN upstream source/docs and server-mode deployment.
- Inspect WebSocket, MQTT, tool, proactive-attention, context-injection, and TTS surfaces.
- Implement only a minimal bridge if the supported boundary exists.

## Exclusions

No webcam, perception, identity, tracking, SQLite history, presence sessions, hardware, DAWN fork/vendor, or user-message masquerade.

## Stop condition

Return to the Architect if no supported path preserves physical-event provenance and initiates reasoning without DAWN modification.
