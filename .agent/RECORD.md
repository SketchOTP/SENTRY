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

## RECORD-SENTRY-017 — M5 restrained proactivity implemented; physical qualification pending
- Date: 2026-08-29
- Type: MILESTONE / IMPLEMENTED-UNVERIFIED / QUALIFICATION PENDING
- Related directive/outcome: `SENTRY-M5-RESTRAINED-PROACTIVITY-001` / `OUTCOME-SENTRY-M5-RESTRAINED-PROACTIVITY-001`

### Decision / event
The M5 bounded proactive policy is implemented around persisted `person.identified` events for `primary_user`. It is not yet accepted because two bounded physical harness attempts produced no persisted identity event.

### Evidence
Schema-4 action logging, deterministic eligibility, dedupe, cooldown, hourly budget, fail-silent Luna validation, local Speech Dispatcher, cancellation, restart/Atlas restore, and privacy tests pass. Focused M5 coverage is 12/12; full Ubuntu regression is 89/89. One real low-effort Luna judge proof returned and persisted `silent`. Two isolated V4L2 runs were clean at 7.935 and 7.783 FPS with zero perception Luna calls, but no physical candidate reached the processor.

### Boundary
M5 remains `IMPLEMENTED_UNVERIFIED / PHYSICAL EVENT UNRESOLVED`. M6 unattended soak is not active. No detector, identity, tracker, or presence qualification claim is changed.

## RECORD-SENTRY-018 — M5 restrained proactivity qualified through physical handoff
- Date: 2026-08-29
- Type: MILESTONE / M5 QUALIFIED / M6 GATED
- Related directive/outcome: `SENTRY-M5-PHYSICAL-HANDOFF-QUALIFICATION-001` / `OUTCOME-SENTRY-M5-PHYSICAL-HANDOFF-QUALIFICATION-001`

### Decision / event
The corrected operator-gated harness proved one real primary-user physical entry traverses the accepted presence/identity pipeline into the existing restrained proactive processor. The action was grounded and persisted as valid `silent`; M5 is qualified within its one-event bounded scope.

### Evidence
Perception started before the `CONFIRMED_EMPTY` marker. A persisted empty/online/session-free baseline stabilized for 7 seconds, startup suppression elapsed while perception continued, and `PRIMARY_USER_ENTER_NOW` was issued. The run then persisted occupied/session-start events at `21:54:16.643081Z`, `person.identified` event `1cb6e1b2-749a-4dfe-8a66-0c7bb3390ef3` at `21:54:17.711178Z`, and proactive action `d542857b-9bb2-4831-9ec6-85e1071594fc`.

### Boundary
The action invoked one low-effort `gpt-5.6-luna` turn and persisted a valid `judge_silent` outcome with no delivery. Replay returned `duplicate` with zero additional Luna calls and one action row. Full regression passed 92/92. M6 72-hour unattended soak remains gated; no new detector or identity claim is made.

## RECORD-SENTRY-019 — Reactive voice implementation corrected
- Date: 2026-08-29
- Type: IMPLEMENTATION / QUALIFICATION PENDING
- Related directive/outcome: `SENTRY-PRE-M6-REACTIVE-VOICE-001` / `OUTCOME-SENTRY-PRE-M6-REACTIVE-VOICE-001`

### Decision / event
The reactive voice path now uses local Whisper `tiny.en` for STT and an installed local Kokoro runtime for TTS. Kokoro is executed locally through a one-shot worker and streamed to this Ubuntu host's PipeWire speaker; SENTRY does not call a remote/RPi5 service.

### Evidence
`tiny.en` correctly transcribed an in-memory Kokoro-generated question. Local Kokoro playback succeeded. With live perception running, the same question's grounded text path returned a supported occupied-state answer with one low-effort Luna call. Focused voice tests passed 5/5 and full Ubuntu regression passed 97/97.

### Boundary
The microphone produced signal but the two corrected physical attempts captured no intelligible speech, so no spoken-request qualification is claimed and both made zero Luna calls. No raw audio was persisted. M6 remains gated; the owner/operator-approved final soak is 30 minutes unattended and the former 72-hour requirement is waived.

### Follow-up physical attempt
The corrected CLI emitted its recording marker only after Whisper/Kokoro initialization. The captured transcript was `Thank you`, confirming `tiny.en` execution, but not the requested occupancy question. A transient Luna failure yielded a truthful unavailable answer delivered by local Kokoro; an immediate text retry returned supported occupancy facts. Spoken-request qualification remains pending.

### Successful synchronized physical question
The local Ubuntu `SENTRY Reactive Voice` window displayed `GET READY`, a three-second countdown, `SPEAK NOW`, and `DONE`. Whisper `tiny.en` captured `Is anyone in the office?`; the live API supplied current occupancy/identity facts; one low-effort Luna turn returned `grounding=supported`; and local Kokoro delivered the answer. Perception remained at 0 Luna calls and processed 340 frames at 6.980 FPS. No raw audio was persisted.

### Playback-rate correction
The prior Kokoro delivery sounded excessively fast because `pw-play -` ignored the WAV header and assumed 48 kHz stereo while Kokoro supplied 24 kHz mono. The implementation now strips the header in memory and supplies explicit 24 kHz/mono/16-bit playback parameters. The operator confirmed the corrected playback sounded normal.

## RECORD-SENTRY-020 — M6 released after reactive voice acceptance
- Date: 2026-08-29
- Type: MILESTONE / M6 ACTIVE
- Related directive: `SENTRY-M6-30MIN-FINAL-ACCEPTANCE-001`

### Decision
Architect accepted the reactive voice proof at `1ce3e611` and released M6. The final unattended acceptance requirement is exactly 30 minutes; the former 72-hour requirement is waived/superseded by owner/operator decision and must not be resurrected.

### Current boundary
M0 through M5 and reactive voice are accepted within their recorded evidence boundaries. M6 is a stability/integration gate only. No detector, identity, voice, or architecture work is reopened during the soak.

## RECORD-SENTRY-021 — M6 30-minute final acceptance passed
- Date: 2026-08-30
- Type: MILESTONE / V0.1 ACCEPTANCE
- Related directive: `SENTRY-M6-30MIN-FINAL-ACCEPTANCE-001`

### Decision
The actual accepted SENTRY V0.1 stack completed the owner/operator-approved 30-minute unattended soak successfully. M6 is accepted; the former 72-hour soak remains waived/superseded and must not be resurrected.

### Evidence
The run lasted `1811.818` seconds, processed `13,458` frames at `7.475 FPS`, and exited cleanly. V4L2/MJPEG/1280x720/15 FPS remained online. Local ext4 SQLite and the Atlas `fuse.sshfs` snapshot both passed integrity checks; one open session remained valid, no persistence/mirror errors occurred, and the one pre-existing stale proactive candidate was suppressed without Luna or speech. Post-soak API reads and one grounded M4 query were consistent with persisted state. Final Ubuntu regression passed `97/97`.

### Accepted V0.1 boundary
SENTRY V0.1 is accepted for the office-only capability chain: webcam presence, durable local-memory/Atlas-mirror history, bounded primary identity, grounded text and reactive voice, restrained proactivity, and 30-minute unattended integrated stability. Whole-home expansion, longer-duration reliability, simultaneous-person identity, wake-word/continuous listening, and other future capabilities remain outside this acceptance.

## RECORD-SENTRY-022 — V0.2 resident runtime qualified
- Date: 2026-08-30
- Type: MILESTONE / V0.2 QUALIFICATION
- Related directive/outcome: `SENTRY-V0.2-RESIDENT-RUNTIME-001` / `OUTCOME-SENTRY-V0.2-RESIDENT-RUNTIME-001`

### Decision
The accepted SENTRY V0.1 stack now runs as a supervised Ubuntu resident under three enabled native user-systemd services. V0.2 resident runtime is qualified; routine learning is not yet active.

### Evidence
The 900-second metadata-only live probe completed with 30 samples and no failures. Perception remained above the 5 FPS floor, the localhost API and Atlas mirror remained healthy, and process-level API/proactive/perception restart isolation passed. Clean stop/start, session integrity, and proactive dedupe passed without fabricating physical events.

### Accepted boundary
The runtime requires an authenticated user session because `Linger=no`; no boot-before-login claim is made. Local SQLite remains authoritative on local ext4, Atlas remains the snapshot mirror, and continuous perception Luna calls remain zero. Routine statistics/learning and broader household expansion require a later directive.
## RECORD-SENTRY-023 — V0.2 routine statistics foundation qualified
- Date: 2026-08-30
- Type: MILESTONE / V0.2 QUALIFICATION
- Related directive/outcome: `SENTRY-V0.2-ROUTINE-STATISTICS-001` / `OUTCOME-SENTRY-V0.2-ROUTINE-STATISTICS-001`

### Decision
The first V0.2 learning layer is qualified as a deterministic, rebuildable statistical foundation. It does not claim that current natural history contains a mature routine.

### Evidence
Schema 5 routine snapshots, circular clock handling, robust duration/absence summaries, sample/date maturity gates, uncertainty/interruption exclusions, idempotent refresh, localhost API, Atlas restore, and the independent user-systemd timer passed validation. Actual production refresh returned `insufficient` for all 40 latest type/scope snapshots, correctly reflecting sparse history. Focused and full regression suites passed `17/17`, `38/38`, and `120/120` respectively.

### Boundary
Routine snapshots remain derived and cannot override current physical evidence or feed M4/M5. Learned routine conversation/proactivity requires a later Architect directive.

## RECORD-SENTRY-024 — V0.2 routine-grounded conversation qualified
- Date: 2026-08-30
- Type: MILESTONE / V0.2 QUALIFICATION
- Related directive/outcome: `SENTRY-V0.2-ROUTINE-GROUNDED-CONVERSATION-001` / `OUTCOME-SENTRY-V0.2-ROUTINE-GROUNDED-CONVERSATION-001`

### Decision
Routine statistics are now available to a bounded M4 conversation path. The feature is qualified without claiming that the current sparse production history contains a mature routine.

### Evidence
Deterministic intent/scope routing, metadata-only routine facts, maturity-aware wording, physical-state contradiction protection, source-outage isolation, and one-turn Luna behavior passed. The resident production API returned 40 latest snapshots, all `insufficient`; five real routine questions correctly returned sparse-history limitations with zero Luna calls. Focused tests passed `17/17`; full regression passed `129/129`.

### Boundary
Routine facts are derived/rebuildable, cannot override physical truth, are not fed into M5, and do not support unsupported activity or causal claims. The existing reactive voice bridge remains compatible through `sentry_ask.py`.
