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

---

## RECORD-SENTRY-008 — First detector replan candidate blocked by runtime capability
- Date: 2026-08-25
- Type: MILESTONE / RUNTIME COMPATIBILITY BLOCKER
- Related directive/outcome: `SENTRY-M1-DETECTOR-REPLAN-001` / `OUTCOME-SENTRY-M1-DETECTOR-REPLAN-001`

### Context
The Architect authorized a detector-only replan using Open Model Zoo `person-detection-0202` through the existing OpenCV dependency, with the SENTRY IoU tracker unchanged.

### Decision / event
The official FP32 XML/BIN artifacts were downloaded to ignored canonical local storage and matched the upstream manifest SHA-384 checksums. The pinned generic OpenCV wheel could not load either artifact pair because its OpenVINO backend plugin was unavailable. The production experiment was reverted rather than adding an unapproved runtime.

### Evidence
Both `cv2.dnn.readNetFromModelOptimizer(xml, bin)` and `cv2.dnn.readNet(bin, xml)` failed with the same OpenCV 4.12.0 plugin error. The restored HOG implementation passed the existing 5/5 tests. No live candidate inference or M1 requalification was performed.

### Consequence
`person-detection-0202` is provenance-verified but not executable in the current authorized environment. M1 remains unaccepted. The Architect must decide whether to authorize a compatible OpenCV build, OpenVINO Runtime, or another detector path. M2 remains unauthorized.

---

## RECORD-SENTRY-009 — OpenVINO runtime authorized and integrated behind existing detector contract
- Date: 2026-08-26
- Type: MILESTONE / RUNTIME INTEGRATION / LIVE GATE PENDING
- Related directive/outcome: `SENTRY-M1-DETECTOR-RUNTIME-001` / `OUTCOME-SENTRY-M1-DETECTOR-RUNTIME-001`

### Decision / event
The Architect authorized exactly one new inference runtime, the official OpenVINO Python Runtime. Version `2026.3.1` installed in an isolated ignored environment, the existing FP32 model loaded and compiled on CPU, and bounded inference returned the documented `(1, 1, 200, 7)` output. The detector now sits behind the existing SENTRY interface while the IoU tracker remains unchanged.

### Evidence
Host devices were `CPU`, `GPU.0`, and `GPU.1`; CPU was selected. The model XML/BIN checksums remained valid. Nine automated tests passed, including decoding and explicit missing/corrupt/unavailable runtime failure paths. Two camera runs exceeded 5 processed FPS but lacked operator-confirmed subject presence and therefore do not establish Stage A.

### Consequence
The runtime blocker is resolved, but M1 remains unaccepted. A human-confirmed one-person segment is required before deciding whether the detector is adequate and whether the unchanged tracker is the next bottleneck. No alternate runtime, tracker change, or M2 work is authorized.

---

## RECORD-SENTRY-010 — Confirmed OpenVINO live detector-quality failure
- Date: 2026-08-26
- Type: MILESTONE / M1 QUALITY FAILURE / ARCHITECT DECISION REQUIRED
- Related directive/outcome: `SENTRY-M1-OPENVINO-LIVE-001` / `OUTCOME-SENTRY-M1-OPENVINO-LIVE-001`

### Decision / event
The operator confirmed an empty baseline, then confirmed one real person remained continuously visible for the live segment. The committed OpenVINO detector and unchanged IoU tracker were evaluated without tuning or architecture changes.

### Evidence
The empty baseline passed with 205/205 zero-person observations. The continuous-one-person run processed 827 online observations: 480 zero detections, 318 exactly one, and 29 multiple detections. The tracker produced 19 unique IDs, first ID 1, final visible ID 19, 32 visible-ID-set changes, and up to 3 active records. Throughput was 9.154 FPS with 9.518 ms median and 15.753 ms p95 latency.

### Consequence
The current detector is materially inadequate for M1 office presence sensing. Dropout and soak stages were stopped at the authorized quality boundary. The Architect must decide whether to authorize another detector/calibration path; do not change the tracker or begin M2 from this evidence.

---

## RECORD-SENTRY-011 — Confidence calibration failed for person-detection-0202
- Date: 2026-08-26
- Type: MILESTONE / DETECTOR CALIBRATION FAILURE / ARCHITECT DECISION REQUIRED
- Related directive/outcome: `SENTRY-M1-DETECTOR-CALIBRATION-001` / `OUTCOME-SENTRY-M1-DETECTOR-CALIBRATION-001`

### Context
The Architect authorized a narrow calibration experiment before changing detector families. The goal was to determine whether the current OpenVINO model's poor `0.50` live recall was caused by over-filtering rather than model quality.

### Decision / event
Raw candidates were captured from the unchanged OpenVINO inference path during operator-confirmed empty and continuously confirmed one-person segments. The same raw files were swept offline at thresholds `0.10` through `0.50`.

### Evidence
The empty segment had 303 observations over 30.639 seconds. The one-person segment had 599 observations over 60.559 seconds. At `0.40`, recall was 96.661% but duplicates occurred in 10.684% of observations. At `0.45`, duplicate rate was 0.334% but recall fell to 89.149%. No threshold met both gates. The raw confidence distributions were empty p95 `0.107720` / max `0.233231` and one-person p95 `0.489522` / max `0.943762`.

### Consequence
Calibration failed with `DETECTOR CALIBRATION FAILED — REPLAN MODEL`. No production threshold, tracker, model, runtime, camera, or preprocessing change was made. Tracker evaluation, dropout, soak, and camera recovery were not run. The next Architect candidate is `person-detection-0303`; it is not implemented by this record.

---

## RECORD-SENTRY-012 — Person-detection-0303 failed confirmed live quality gate
- Date: 2026-08-26
- Type: MILESTONE / DETECTOR QUALITY FAILURE / ARCHITECT DECISION REQUIRED
- Related directive/outcome: `SENTRY-M1-DETECTOR-0303-001` / `OUTCOME-SENTRY-M1-DETECTOR-0303-001`

### Decision / event
The Architect authorized a bounded replacement of failed `person-detection-0202` with official Open Model Zoo `person-detection-0303`, preserving OpenVINO CPU execution, native 1280x720 capture, the detector contract, and the unchanged IoU tracker.

### Evidence
0303 provenance, Apache-2.0 license linkage, FP32 XML/BIN checksums, OpenVINO load/compile, output semantics, and a short CPU performance check passed. A confirmed-empty segment produced zero candidates for 279 observations over 30.863 seconds. A confirmed continuous-one-person segment produced zero candidates for 588 observations over 60.91 seconds, across every threshold from 0.10 through 0.90.

### Consequence
0303 is not adequate for the tested office scene. Tracker qualification, dropout, soak, and camera recovery were stopped at the detector-quality boundary. The Architect must decide the next detector direction; do not change the tracker, runtime/device, or begin M2 from this evidence.

---

## RECORD-SENTRY-013 — 0303 rejection reclassified after decoder reconciliation
- Date: 2026-08-26
- Type: MILESTONE / DECODER BUG CONFIRMED / DETECTOR QUALITY FAILURE / ARCHITECT DECISION REQUIRED
- Related directive/outcome: `SENTRY-M1-0303-DECODER-RECONCILE-001` / `OUTCOME-SENTRY-M1-0303-DECODER-RECONCILE-001`

### Decision / event
The prior 0303 zero-candidate live result was not sufficient to reject the model because SENTRY required companion `labels == 1`, while the official class-agnostic adapter uses positive box confidence and assigns the person label itself. The decoder was corrected without changing the model, runtime, tracker, camera, or threshold.

### Evidence
The raw confirmed-one-person run contained 1,474 positive-confidence rows, including 339 at or above `0.10`, with all companion labels equal to `0`; the old decoder emitted zero candidates. After correction and NMS `0.6`, empty threshold `0.45` was false-positive clean in 181 observations, but one-person recall was only 134/556. No tested threshold met the required empty/person quality gates.

### Consequence
The decoder bug is confirmed, but 0303 remains unsuitable for the tested office scene. Tracker qualification, dropout, soak, and camera recovery remain gated. The next detector decision must come from the Architect.

## RECORD-SENTRY-014 — M3 primary-user identity implementation activated
- Date: 2026-08-29
- Type: MILESTONE / IMPLEMENTATION-UNVERIFIED / M3 ACTIVE
- Related directive/outcome: `SENTRY-M3-PRIMARY-IDENTITY-001` / `OUTCOME-SENTRY-M3-PRIMARY-IDENTITY-001`

### Decision / event
M2 durable presence memory is accepted. M3 is active with OpenCV Zoo YuNet plus SFace as the authorized local identity backend. M1 presence and the YOLOX-S detector remain frozen; no detector requalification was reopened.

### Evidence
The exact MIT YuNet and Apache-2.0 SFace artifacts were verified and loaded through OpenCV 4.12. Schema version 3 stores one active local identity prototype, `/v1/persons` exposes metadata only, and identity annotations are bounded, track-associated, and conservative. The deterministic/full regression suite passes 65/65.

### Boundary
M3 remains `IMPLEMENTED_UNVERIFIED` until deliberate enrollment, held-out primary-user evaluation, consenting non-primary negative evidence, threshold calibration, and live restart/Atlas identity recovery are completed. Identity uncertainty cannot change authoritative room presence.

## RECORD-SENTRY-015 — M3 primary identity qualified within bounded evidence
- Date: 2026-08-29
- Type: MILESTONE / M3 QUALIFIED / RESIDUAL LIMITATION
- Related directive: `SENTRY-M3-PRIMARY-IDENTITY-001`

### Decision / event
M3 primary-user identity is qualified for the one-enrolled-user V0.1 boundary. The calibrated profile is `primary_user` / `Sketch` at cosine threshold `0.55`; simultaneous two-person association was not run because both consenting people were unavailable together.

### Evidence
Sixteen enrollment samples were accepted, with two no-face retries rejected. Held-out metadata-only scoring yielded 377/425 (`88.71%`) genuine acceptance and 0/210 non-primary accepts, for 100% measured accepted-ID precision. Live primary recognition occurred within 2.773 seconds at 8.246 FPS; the live non-primary segment produced zero primary-user assignments at 8.291 FPS. Local reopen and Atlas restore preserved the single profile and threshold.

### Boundary
Identity remains an annotation on presence. Face loss remains `unresolved`, non-match remains `unknown`, and neither can create departure or alter room state. No raw frames or query embeddings were persisted; continuous perception Luna/Codex calls remained zero.
## RECORD-SENTRY-016 — M4 grounded conversation qualified within bounded evidence
- Date: 2026-08-29
- Type: MILESTONE / GROUNDED-CONVERSATION QUALIFICATION
- Related directive/outcome: `SENTRY-M4-GROUNDED-CONVERSATION-001` / `OUTCOME-SENTRY-M4-GROUNDED-CONVERSATION-001`

### Decision / event
The bounded text conversation path is qualified for M4. SENTRY retrieves authoritative metadata from its localhost API, converts it to an allow-listed fact packet, and permits one OAuth-authenticated `gpt-5.6-luna` turn to phrase only those facts. M5 remains gated.

### Evidence
The implementation passed 77/77 Ubuntu regression tests and deterministic API fixtures for all required room/identity/availability states plus restart uncertainty. Thirteen real API queries used one low-effort Luna turn each; the actual healthy database had no current room observation, sessions, or events, and Luna returned explicit partial/unavailable answers without inventing physical facts. An unavailable API proof made zero Luna calls.

### Boundary
Room occupancy is not conflated with primary-user arrival. Restart-reconciled uncertainty remains explicit. The fact packet contains no raw frames, embeddings, biometric prototype, or unrestricted DB payload. Continuous perception remains at zero Luna calls.
