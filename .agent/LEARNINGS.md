# Durable Learnings

Temporary observations do not belong here. Add only findings likely to remain useful across future tasks.

---

## LEARNING-SENTRY-001 — Governance and product boundaries are now persistent
- Date: 2026-08-24
- Evidence source: SENTRY-AUTHORITY-BOOTSTRAP-001, Notion SENTRY page, GitHub baseline `63376fe`
- Confidence: VERIFIED

### Learning
SENTRY is documentation-first, authorized at M0 only, and constrained to a one-office Windows prototype using existing hardware. No runtime capability has been demonstrated.

### Why it matters
Future work must begin by evaluating the DAWN integration path with a synthetic event and must not jump into perception, whole-home hardware, or ungrounded capability claims.

### Recheck trigger
Recheck when the Architect accepts a later milestone result or when the Notion/GitHub project contract changes.

---

## LEARNING-SENTRY-002 — Authority source boundaries
- Date: 2026-08-24
- Evidence source: Authority 3.0 canonical installation package and installed repository records
- Confidence: VERIFIED

### Learning
Notion is the strategic/project source, GitHub is the committed repository source, and the Codex working tree/runtime is the live technical source.

### Why it matters
Future results must distinguish static repository facts, committed evidence, and live runtime evidence instead of treating them as interchangeable.

### Recheck trigger
Recheck if project governance or source-of-truth ownership changes by explicit decision.

---

## LEARNING-SENTRY-003 — Current DAWN upstream lacks the required external event boundary
- Date: 2026-08-24
- Evidence source: SENTRY-M0-DAWN-FEASIBILITY-001; DAWN upstream `a0c0b13c65f1b02a3416d846f6a0d331244eee9d`
- Confidence: VERIFIED STATIC UPSTREAM INSPECTION

### Learning
DAWN's current WebSocket and satellite inputs are conversational text, its generic MQTT device relay becomes a user-role `[DEVICE DATA]` turn, and SAGE attention is limited to DAWN-owned telemetry watches. System-context injection can inform a later turn but does not trigger one. No supported external `person.entered` environmental-event ingress was found.

### Why it matters
SENTRY must not send a physical event through a user-message path and call it grounded environmental context. A clean bridge requires an explicit upstream capability or a separately authorized architecture decision.

### Recheck trigger
Recheck when DAWN adds a documented external event API, a supported generic event/tool ingress, or the Architect authorizes DAWN modification/forking or a foundation change.
