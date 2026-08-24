# Major Project Record

Use this ledger for major architecture decisions, strategic reversals, project milestones, important failures, governance migrations, and other events a future Architect/Coder must understand.

---

## RECORD-SENTRY-001 — Authority 3.0 governance bootstrap
- Date: 2026-08-24
- Type: GOVERNANCE
- Related directive/outcome: SENTRY-AUTHORITY-BOOTSTRAP-001 / OUTCOME-SENTRY-AUTHORITY-BOOTSTRAP-001

### Context
The SENTRY repository had product scope and a pre-Authority coder contract but no persistent Authority 3.0 state/history or reusable workflow structure.

### Decision / event
Installed the canonical Authority 3.0 repository governance and initialized it from the actual SENTRY Notion scope, GitHub repository, and clean documentation-first checkout.

### Evidence
Canonical package retrieved from Notion page `Authority 3.0 — Complete Installation Package`; GitHub baseline `63376fe`; SENTRY Notion page and `docs/PROJECT_SCOPE.md` reconciled.

### Consequence
Future Codex work must read the Authority kernel, preserve append-only project evidence, report evidence levels honestly, and stop for Architect review before M0 implementation.

---

## RECORD-SENTRY-002 — M0 DAWN feasibility blocked at supported-boundary gate
- Date: 2026-08-24
- Type: ARCHITECTURE BLOCKER
- Related directive/outcome: SENTRY-M0-DAWN-FEASIBILITY-001 / OUTCOME-SENTRY-M0-DAWN-FEASIBILITY-001

### Context
The accepted M0 directive required a synthetic `person.entered` event to reach DAWN as trusted environmental context and autonomously produce an assistant response, without presenting the event as user speech or modifying/forking DAWN.

### Decision / event
Current DAWN upstream inspection reached the directive's stop condition. The supported external surfaces do not satisfy both event provenance and autonomous reasoning initiation.

### Evidence
DAWN `a0c0b13c65f1b02a3416d846f6a0d331244eee9d`: WebSocket text/satellite query are conversational input; MQTT generic relay is `[DEVICE DATA]` user-role input; SAGE is a fixed telemetry-watch engine; context injection is downstream of a turn; custom tools require DAWN source/build registration.

### Consequence
No SENTRY runtime or perception work may proceed under the current M0 boundary. The Architect must choose an explicit upstream/fork/licensing path, another foundation, or a revised acceptance boundary.
