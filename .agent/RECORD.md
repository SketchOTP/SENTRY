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

---

## RECORD-SENTRY-004 — Isolated runtime context adopted for event reasoning
- Date: 2026-08-24
- Type: MILESTONE / RUNTIME HARDENING
- Related directive/outcome: SENTRY-M0-CODEX-CONTEXT-OPT-001 / OUTCOME-SENTRY-M0-CODEX-CONTEXT-OPT-001

### Context
The accepted Codex/Luna bridge measured 19,308 input tokens for a trivial event while executing from the SENTRY repository root, where Codex discovered the repository `AGENTS.md` Authority instructions.

### Decision / event
Runtime event reasoning now executes from a fresh temporary non-repository directory with `--skip-git-repo-check` and an absolute local copy of the output schema. Development Codex sessions and repository Authority are unchanged.

### Evidence
The same synthetic event measured 19,308 input tokens at repo root and 18,266 in isolation, a 5.4% reduction. The final bridge event measured 18,223 input tokens. All four successful calls used ChatGPT OAuth, explicit `gpt-5.6-luna`, and low effort. Both semantic events remained schema-valid and grounded the physical event as distinct from user speech.

### Consequence
The runtime boundary avoids unnecessary SENTRY development/governance context, but the observed floor remains approximately 18.2k input tokens. M1 webcam/perception remains separately gated and requires explicit Architect authorization.

---

## RECORD-SENTRY-005 — M1 perception implementation stopped at physical-camera gate
- Date: 2026-08-24
- Type: MILESTONE / BLOCKER
- Related directive/outcome: `SENTRY-M1-PERCEPTION-001` / `OUTCOME-SENTRY-M1-PERCEPTION-001`

### Context
M0 was accepted and explicitly authorized the next milestone: local Windows webcam perception with zero Codex/Luna calls in the continuous loop.

### Decision / event
Implemented the observation-only service and deterministic contracts, then stopped live qualification at the actual-device gate. OpenCV 4.12.0 could not open the enumerated NexiGo N60 through Any, Media Foundation, or DirectShow.

### Evidence
Five deterministic tests passed. The unavailable-camera run returned `degraded` startup followed by `offline / camera_open_failed`, exit code 3, and zero Luna calls. No frame, detection, tracking, FPS, recovery, or ten-minute soak claim was made.

### Consequence
M1 remains unaccepted and M2 remains unauthorized. Restore camera access or authorize a replacement device before live validation resumes.

---

## RECORD-SENTRY-006 — Canonical checkout recovered after Atlas visibility incident
- Date: 2026-08-25
- Type: GOVERNANCE / REPOSITORY RECOVERY
- Related directive/outcome: `SENTRY-REPO-RECOVERY-001` / `OUTCOME-SENTRY-REPO-RECOVERY-001`

### Context
The Atlas SENTRY directory had previously lost visible Git metadata and committed files while GitHub `main` remained independently intact at `73b43f3`. The Architect authorized safe recovery and prohibited destructive storage repair, legacy pool paths, mergerfs, and unrelated project changes.

### Decision / event
After repeated read-only inventory confirmed the parent share was reachable and the SENTRY path had no visible remnants, a fresh GitHub clone was verified in isolation and the canonical SENTRY path was restored. The restored checkout passed Git, Authority, test, status, and stability checks.

### Evidence
Remote HEAD and canonical HEAD are `73b43f3398c0dc0738d23d389c2a79b48c5af29d`; `git fsck --full` exited 0; all five existing tests passed; Authority/source files are present; three canonical rereads retained `.git` metadata and perception source; local `main` matches `origin/main`; final status is clean.

### Consequence
Repository integrity is restored and M1 live qualification may safely resume from the canonical checkout. M1 remains unaccepted until its remaining human/tracking/recovery gates are evidenced. No storage migration, architecture change, dependency change, or M2 work was performed.

---

## RECORD-SENTRY-007 — M1 live gate rejected current detector quality
- Date: 2026-08-25
- Type: MILESTONE / DETECTOR QUALITY BLOCKER
- Related directive/outcome: `SENTRY-M1-LIVE-QUALIFICATION-001` / `OUTCOME-SENTRY-M1-LIVE-QUALIFICATION-001`

### Context
The repository, camera path, throughput foundation, and automated contracts were accepted/current. The remaining M1 question was whether the existing HOG detector and SENTRY IoU tracker behaved adequately on a real office scene.

### Decision / event
An operator-visible preview confirmed one real person. Live SENTRY runs produced high track churn and multiple simultaneous track records in that known one-person scene. The current stack is therefore not acceptable for M1 office presence sensing. A controlled camera interruption could not be executed because device disable/restart required unavailable administrative access.

### Evidence
The 30-second run had 238/271 non-empty observation rows, up to 3 reported people, and IDs 1–14. The 90-second run had up to 6 reported people and IDs 1–29, while maintaining 9.435 processed FPS and zero Luna calls. Automated tests remained 5/5. No raw frame was retained.

### Consequence
M1 remains unaccepted. The Architect must separately authorize detector replanning or another bounded investigation. Camera recovery also requires a user/admin or physical-interruption path before it can be accepted. M2 remains unauthorized.
