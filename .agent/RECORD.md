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

---

## RECORD-SENTRY-003 — Codex/Luna direct reasoning boundary target-tested
- Date: 2026-08-24
- Type: MILESTONE / ARCHITECTURE DECISION CANDIDATE
- Related directive/outcome: SENTRY-M0-CODEX-FEASIBILITY-001 / OUTCOME-SENTRY-M0-CODEX-FEASIBILITY-001

### Context
DAWN's supported external boundary could not preserve SENTRY physical-event provenance while initiating reasoning. The Architect accepted a Luna-only policy and redirected M0 to direct OAuth-authenticated Codex invocation.

### Decision / event
The smallest local Codex bridge was implemented and target-tested. It accepts a validated synthetic SENTRY `person.entered` event, performs exactly one OAuth-only `codex exec --ephemeral` turn with `gpt-5.6-luna`, controls Luna reasoning effort, and returns a schema-constrained structured result or a bounded error.

### Evidence
Two independent runs passed: low effort on event `...0101` and high effort on event `...0102`. Both understood the person, room, and physical event and explicitly distinguished environmental context from user speech. JSONL usage reported 19,100 input tokens for each turn; low returned 80 output/0 reasoning-output tokens and high returned 139 output/55 reasoning-output tokens.

### Consequence
SENTRY now has a target-tested on-demand reasoning boundary candidate without a continuous Codex worker or model escalation. The Architect must accept this M0 result before webcam/perception work. The full governor, persistence, and perception system remain unauthorized.
