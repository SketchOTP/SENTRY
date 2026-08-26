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

---

## LEARNING-SENTRY-004 — Codex CLI provides a bounded OAuth/Luna reasoning boundary
- Date: 2026-08-24
- Evidence source: SENTRY-M0-CODEX-FEASIBILITY-001; Codex CLI `0.145.0`; official Codex noninteractive/authentication docs; GPT-5.6 Luna docs
- Confidence: VERIFIED TARGET-TESTED

### Learning
On this Windows host, `codex exec --ephemeral --json --output-schema` can be invoked locally with saved ChatGPT OAuth credentials after API-key environment variables are removed. Explicit `--model gpt-5.6-luna` plus `model_reasoning_effort` selects Luna effort without model escalation. Per-turn JSONL usage is available, and a fresh bounded turn is sufficient for independent synthetic events.

### Why it matters
SENTRY can own persistence, event provenance, gating, and idle behavior while treating Codex/Luna as an on-demand reasoning layer. The bridge must be called only after a meaningful semantic event, with bounded context, duplicate suppression, call-rate limits, and failure handling.

### Recheck trigger
Recheck after Codex CLI upgrades, ChatGPT plan/authentication changes, model alias changes, or before deploying the adapter beyond a trusted local process.

---

## LEARNING-SENTRY-005 — Runtime reasoning should execute outside the repository instruction chain
- Date: 2026-08-24
- Evidence source: SENTRY-M0-CODEX-CONTEXT-OPT-001; official Codex AGENTS.md/noninteractive documentation; four successful Luna calls
- Confidence: VERIFIED TARGET-TESTED

### Learning
The SENTRY event bridge can preserve the accepted OAuth/Luna/schema boundary while running each runtime reasoning turn from a fresh non-repository temporary directory. With `--skip-git-repo-check` and an absolute copied schema path, the runtime excludes SENTRY's `AGENTS.md` chain and reduced measured input from 19,308 to 18,266 tokens for the same event, with a final 18,223-token measurement.

### Why it matters
Development Codex sessions must retain repository Authority. Runtime event reasoning does not need that development context and should use the isolated boundary. The observed reduction is modest, so usage metrics remain required and further optimization must stop unless a supported lower-context configuration is identified.

### Recheck trigger
Recheck after Codex CLI upgrades, instruction-discovery changes, auth/model changes, or before moving the bridge beyond a trusted local process.

---

## LEARNING-SENTRY-006 — Camera enumeration is not capture readiness
- Date: 2026-08-24
- Evidence source: SENTRY-M1-PERCEPTION-001 host inspection and OpenCV 4.12.0 Any/Media Foundation/DirectShow attempts
- Confidence: VERIFIED HOST-OBSERVED

### Learning
The NexiGo N60 FHD Webcam appears in Windows PnP enumeration, but that does not prove an application can open it. On this host, OpenCV reported camera index 0 unavailable through all three tested backends.

### Why it matters
SENTRY must qualify actual capture before claiming detection, tracking, FPS, or soak behavior. The runtime must report degraded/offline explicitly and must not convert device failure into an empty-room observation.

### Recheck trigger
Recheck after Windows camera privacy/driver/device changes or when a replacement webcam is connected.

---

## LEARNING-SENTRY-007 — Apparent checkout loss requires share-stability verification
- Date: 2026-08-25
- Evidence source: `SENTRY-REPO-RECOVERY-001`; repeated Atlas inventories and verified GitHub recovery clone
- Confidence: VERIFIED RECOVERY OBSERVATION; low-level cause uncertain

### Learning
When a canonical checkout appears to lose `.git` metadata and committed files, first repeat the parent/share and directory inventory, preserve any visible remnants, and verify an isolated clone before restoring the canonical path. In this incident the SENTRY path was absent on repeated reads, no surviving SENTRY material was found, and a fresh clone at the exact verified GitHub HEAD restored a clean checkout without history rewrite.

### Why it matters
A transient visibility or consistency failure can look like deletion. Recovery must not overwrite unknown local work or convert a partial read into proof of data loss. The original low-level cause remains unknown unless independent storage/share evidence becomes available.

### Recheck trigger
Recheck on any future Atlas path disappearance, Git metadata inconsistency, or share instability before replacing a canonical project directory.
