# Directive Ledger

Append new directives at the bottom. Never rewrite an accepted historical directive. Use stable IDs.

---

## SENTRY-AUTHORITY-BOOTSTRAP-001 — Install Authority 3.0 governance
- Issued: 2026-08-24
- Status: COMPLETE
- Project stage: M0 — Bootstrap + DAWN Integration Feasibility
- Goal link: Establish the persistent Architect → Codex → evidence → Architect workflow before product implementation.
- Objective: Install the canonical Authority 3.0 root router, `.agent/` project state/history, `.agents/` reusable workflow/supporting references, and SENTRY-specific initialization.
- Scope: Governance and project-state documentation only, plus authorized commit/push and Notion evidence update.
- Exclusions: No DAWN integration, perception, webcam, dependencies, runtime architecture, hardware expansion, or product implementation.
- Acceptance: Canonical Authority structure exists, SENTRY records reflect Notion/repository reality, validation is recorded, and GitHub/Notion are updated.
- Required validation: Authority tree and reference paths, state/index integrity, placeholder scan, scoped diff, commit/push, and final working-tree report.
- External discovery: NOT REQUIRED.
- Stop/escalation conditions: Ambiguous/inaccessible canonical package, material repository conflict, unfamiliar uncommitted work, destructive documentation loss, or scope expansion into M0 implementation.
- Source: Architect directive supplied as `SENTRY-AUTHORITY-BOOTSTRAP-001`; canonical package retrieved from Notion.

---

## SENTRY-M0-DAWN-FEASIBILITY-001 — Prove or decisively block the synthetic SENTRY event bridge
- Issued: 2026-08-24
- Status: BLOCKED — returned to Architect before implementation
- Project stage: M0 — Bootstrap + DAWN Integration Feasibility
- Goal link: Establish the assistant foundation and event boundary before webcam/perception work.
- Objective: Prove the least invasive supported path for `synthetic person.entered event → SENTRY event contract → DAWN grounded environmental context → assistant response → optional speech`.
- Scope: Inspect current DAWN upstream source/docs and relevant deployment/licensing boundaries; implement only the smallest bridge if a supported path exists.
- Exclusions: No webcam, detection, tracking, face recognition, SQLite history, presence sessions, Home Assistant, Frigate, ESP32, BLE/mmWave/CSI, TV/avatar, DAWN fork/vendor, or strategic workaround that presents an event as user speech.
- Acceptance: DAWN runs reproducibly; a versioned SENTRY event reaches DAWN as environmental context; DAWN reasons from it; optional speech is tested; evidence, records, Notion, and GitHub are updated.
- External discovery: REQUIRED; current upstream inspected at commit `a0c0b13c65f1b02a3416d846f6a0d331244eee9d`.
- Stop condition reached: No supported external inbound environmental-event interface was found that both preserves event provenance and initiates reasoning without DAWN modification or user-message masquerading.
- Source: Architect directive supplied as `SENTRY-M0-DAWN-FEASIBILITY-001`; SENTRY Notion scope and GitHub upstream were rechecked.

---

## SENTRY-M0-CODEX-FEASIBILITY-001 — Prove OAuth-authenticated Luna reasoning on demand
- Issued: 2026-08-24
- Status: COMPLETE — target-tested; returned to Architect for acceptance
- Project stage: M0 — Codex/Luna Feasibility
- Goal link: Establish SENTRY's owned event/world-state boundary and on-demand reasoning layer before webcam/perception work.
- Objective: Prove `synthetic person.entered → local SENTRY event → OAuth Codex/GPT-5.6 Luna → grounded structured response` without continuous idle reasoning.
- Scope: Inspect current official OpenAI/Codex documentation and installed Codex behavior; implement only the smallest bounded local event adapter; force Luna; control reasoning effort; capture parseable output and usage metadata; demonstrate failure detection.
- Exclusions: No Terra, Sol, other model, webcam, perception, face recognition, SQLite, presence sessions, voice stack, OpenClaw, DAWN, Home Assistant, hardware, routine learning, TV/avatar, continuous Codex loop, or full governor.
- Acceptance: OAuth local invocation without API key, explicit Luna verification/selection, grounded synthetic event response, reliable structured output, independent second event, two Luna effort levels, observed usage, no idle calls, bounded unavailable/quota failure handling, no M1 scope, records/Notion/GitHub updated.
- External discovery: REQUIRED; current official Codex authentication, CLI noninteractive, structured-output, and GPT-5.6 Luna documentation inspected through `/browse`.
- Stop conditions: OAuth unavailable for local invocation, API key required, Luna/effort cannot be selected, event provenance is lost, idle consumption is substantial, or major custom infrastructure is required.
- Source: Architect directive supplied as `SENTRY-M0-CODEX-FEASIBILITY-001`, accepted Luna-only Notion decision, current official OpenAI documentation, and installed Codex CLI behavior.

---

## SENTRY-M0-CODEX-CONTEXT-OPT-001 — Reduce and characterize runtime context overhead
- Issued: 2026-08-24
- Status: COMPLETE — target-tested; returned to Architect for acceptance
- Project stage: M0 — Codex/Luna Feasibility
- Goal link: Preserve the accepted on-demand OAuth/Luna event-reasoning boundary while controlling per-event context cost before M1.
- Objective: Compare repo-root and isolated Codex execution, identify unnecessary SENTRY Authority context, measure the practical input-token floor, and adopt isolation only if supported and behavior-preserving.
- Scope: Four successful Luna turns maximum; low effort by default; isolated temporary runtime; `--skip-git-repo-check`; absolute schema path; direct usage measurement; final bridge hardening.
- Exclusions: No Authority weakening, model change, Terra, Sol, webcam, perception, M1, voice, DAWN, OpenClaw, persistence, hardware, unsupported Codex modifications, or open-ended optimization.
- Acceptance: Baseline retained; isolated event passes with OAuth, explicit Luna, schema-valid grounded provenance; context source characterized; before/after usage measured; final bridge, failure handling, idle behavior, records, Notion, and GitHub updated.
- External discovery: REQUIRED; official Codex noninteractive, AGENTS.md, and authentication documentation inspected through `/browse`.
- Stop conditions: Authority weakening, OAuth/model/provenance/schema breakage, four successful calls consumed, or unsupported configuration required.
- Source: Architect directive supplied as `SENTRY-M0-CODEX-CONTEXT-OPT-001`, following accepted M0 result.

---

## SENTRY-M1-PERCEPTION-001 — Implement and prove local Windows webcam perception
- Issued: 2026-08-24
- Status: BLOCKED — implementation target-tested; actual-camera live gate could not run
- Project stage: M1 — Local Windows Perception
- Goal link: Establish reliable local observation before identity, persistence, assistant grounding, or proactive behavior.
- Objective: Implement `webcam → local person detection → temporary multi-person tracking → explicit camera health → structured observations`.
- Scope: One Windows webcam, configurable capture, local person-only detection, bounded latest-frame behavior, temporary tracking, health states, structured observations, automated tests, and actual-host live validation.
- Exclusions: No identity recognition, persistence, sessions, semantic entry/exit events, local API, voice, DAWN integration, Codex/Luna calls from perception, raw-frame persistence, additional hardware, or M2 behavior.
- External discovery: REQUIRED; YOLOX, ByteTrack, ONNX Runtime, and OpenCV documentation/licenses reviewed through `/browse`.
- Stop condition reached: NexiGo N60 enumerates but OpenCV 4.12.0 could not open index 0 through Any, Media Foundation, or DirectShow. Live criteria are BLOCKED/NOT RUN.
- Source: Architect directive supplied as `SENTRY-M1-PERCEPTION-001`, accepted M0 Notion state, SENTRY scope, and host evidence.

---

## SENTRY-REPO-RECOVERY-001 — Restore a trustworthy canonical SENTRY checkout
- Issued: 2026-08-24; resumed: 2026-08-25
- Status: COMPLETE — canonical checkout restored and verified; M1 remains open
- Project stage: M1 — Local Windows Perception
- Objective: Diagnose the damaged Atlas checkout, preserve any surviving material, recover from GitHub without rewriting history, restore the canonical checkout, and verify Authority/Git/test integrity.
- Scope: Read-only Atlas/share diagnosis, surviving-material inventory, isolated recovery clone, canonical restoration only after verification, append-only incident records, and authorized recovery commit/push.
- Exclusions: No storage repair or migration, legacy pool paths, mergerfs, perception architecture changes, dependency changes, M2, full M1 live qualification, or deletion of quarantine/remnant data.
- Acceptance: Remote HEAD `73b43f3` reconfirmed; no unique remnants silently destroyed; fresh clone and canonical checkout valid; `git fsck`, Authority checks, tests, stable reread, clean status, and local/remote match verified; records updated.
- External discovery: NOT REQUIRED.
- Stop conditions: Share instability, neighboring checkout corruption, unique uncommitted remnants, remote divergence, failed clean clone, or recovery requiring destructive storage repair/data loss.
- Source: Architect directive `SENTRY-REPO-RECOVERY-001`, SENTRY Notion, and GitHub `SketchOTP/SENTRY`.

---

## SENTRY-M1-LIVE-QUALIFICATION-001 — Complete live M1 acceptance evidence
- Issued: 2026-08-25
- Status: PARTIAL — returned to Architect; current detector/tracker is not acceptable for the observed office scene and camera recovery is blocked
- Project stage: M1 — Local Windows Perception
- Objective: Demonstrate human-confirmed detection, stable tracking, short dropout continuity, multi-person behavior, controlled camera failure/recovery, and performance on the actual office setup using the existing implementation first.
- Scope: Local live observation, transient human-visible preview, structured diagnostics, and minimal fixes only if live evidence proves them necessary.
- Exclusions: No silent HOG/tracker replacement, identity, persistence, events, state machine, API, voice, Codex/Luna integration, M2, additional hardware, or unrelated system changes.
- Acceptance boundary reached: Human-visible single-person operation was observed, but the known one-person scene produced severe track churn and multiple simultaneous track records. The required controlled camera interruption could not be performed because device disable/restart required unavailable administrative access.
- External discovery: NOT REQUIRED.
- Stop condition reached: Current HOG/tracker quality is materially inadequate; Architect must separately decide whether to replan the detector. Camera recovery remains unproven.
- Source: Architect directive `SENTRY-M1-LIVE-QUALIFICATION-001`, accepted camera-access evidence, and actual-host live runs.

---

## SENTRY-M1-DETECTOR-REPLAN-001 — Evaluate Open Model Zoo person-detection-0202 behind the existing detector contract
- Issued: 2026-08-25
- Status: BLOCKED — model provenance passed; pinned generic OpenCV DNN cannot load the OpenVINO IR
- Project stage: M1 — Local Windows Perception
- Objective: Replace only HOG with the first authorized modern local candidate and evaluate the unchanged SENTRY IoU tracker if the runtime is compatible.
- Scope: Official FP32 artifact verification, local checksum verification, bounded OpenCV DNN smoke test, detector-contract implementation only if executable, and live Stage A/B/C only after compatibility.
- Exclusions: No tracker replacement, OpenVINO Runtime, YOLOX, Ultralytics, identity, persistence, events, API, voice, Codex/Luna calls, M2, or camera-recovery detour.
- Acceptance boundary reached: Open Model Zoo FP32 artifacts and Apache-2.0 provenance matched, but both OpenCV DNN IR loading entry points failed on `opencv-python-headless==4.12.0.88` because the `openvino` backend plugin is unavailable.
- External discovery: REQUIRED; official Open Model Zoo manifest/readme/license and OpenCV DNN upstream API source inspected through `/browse`.
- Stop condition reached: Generic OpenCV cannot execute the candidate. The production experiment was reverted and no alternate runtime was added.
- Source: Architect directive `SENTRY-M1-DETECTOR-REPLAN-001`, SENTRY Notion, official Open Model Zoo metadata, OpenCV DNN upstream source, and host runtime evidence.

---

## SENTRY-M1-DETECTOR-RUNTIME-001 — Prove person-detection-0202 through OpenVINO and evaluate the unchanged tracker
- Issued: 2026-08-26
- Status: IN PROGRESS — OpenVINO installation, model loading, smoke inference, integration, and automated tests passed; human-confirmed live qualification pending
- Project stage: M1 — Local Windows Perception
- Objective: Use the official OpenVINO Python Runtime with the already-qualified FP32 `person-detection-0202` model, preserve the existing capture/buffer and IoU tracker, and run the authorized live stages if runtime checks pass.
- Scope: Host/runtime verification, exact package pin, checksum recheck, direct model load/compile/inference, detector-contract integration, focused failure/decoding tests, and human-confirmed live Stage A/B/C plus performance if prerequisites pass.
- Exclusions: No OpenCV rebuild, alternate inference runtime, detector-family change, tracker change, identity, persistence, events, API, voice, Codex/Luna calls, M2, or camera-recovery detour.
- External discovery: REQUIRED; official OpenVINO installation/API/repository/license pages reviewed through `/browse`.
- Current result: OpenVINO `2026.3.1` installed in ignored `.venv`; CPU/GPU devices enumerated; the checksummed model loaded, compiled, and produced `(1, 1, 200, 7)` on bounded zero-array inference. Production integration and 9/9 tests pass. Two telemetry-only camera runs are not acceptance evidence because operator confirmation was not recorded.
- Stop/pending boundary: Obtain an operator-confirmed one-person office segment before accepting or rejecting Stage A. Do not infer human presence from model output alone.
- Source: Architect directive `SENTRY-M1-DETECTOR-RUNTIME-001`, SENTRY Notion, prior detector-replan evidence, official OpenVINO documentation, and host runtime evidence.

---

## SENTRY-M1-OPENVINO-LIVE-001 — Operator-confirmed live quality qualification
- Issued: 2026-08-26
- Status: STOPPED AT ACCEPTED QUALITY-FAILURE BOUNDARY — current OpenVINO detector/tracker combination failed confirmed one-person quality
- Project stage: M1 — Local Windows Perception
- Objective: Run an operator-marked empty baseline and continuously confirmed one-person segment using the committed OpenVINO detector and unchanged IoU tracker; continue to dropout/soak only if quality gates pass.
- Scope: Existing NexiGo N60, DirectShow index 0, 1280x720/15 FPS, OpenVINO CPU, configured threshold, size-one latest-frame buffer, structured metadata-only telemetry.
- Exclusions: No detector/tracker/dependency/threshold changes, camera recovery detour, identity, persistence, events, API, voice, Codex/Luna calls, or M2.
- Acceptance boundary reached: Stage A confirmed-empty passed. Stage B confirmed-one-person failed: 827 processed online observations included 480 zero-detection, 318 exactly-one, and 29 multi-detection observations; the unchanged tracker produced 19 unique IDs and 32 visible-ID-set changes for one continuously visible person.
- Stop condition reached: Current detector quality is materially inadequate; Stage C synchronized dropout and Stage E soak were not run. Multi-person live evidence is blocked without a second person. Camera recovery remains a separate M1 gate.
- External discovery: NOT REQUIRED.
- Source: Architect directive `SENTRY-M1-OPENVINO-LIVE-001`, operator-confirmed ground-truth markers, metadata-only live telemetry, and current committed runtime.

---

## SENTRY-M1-DETECTOR-CALIBRATION-001 — Calibrate person-detection-0202 confidence from raw live candidates
- Issued: 2026-08-26
- Status: COMPLETE — calibration failed; returned to Architect for bounded model-replan decision
- Project stage: M1 — Local Windows Perception
- Objective: Determine whether the committed OpenVINO `person-detection-0202` detector can satisfy M1 through confidence calibration without changing model, runtime, tracker, capture, or production threshold.
- Scope: Metadata-only raw candidate diagnostics, operator-confirmed empty and one-person segments, offline threshold sweep at `0.10` through `0.50`, and no tracker evaluation unless detector calibration passed.
- Exclusions: No model/runtime/tracker/capture/preprocessing changes, no production threshold change, no new model, no tracker tuning, no identity, persistence, events, API, voice, M2, or Codex/Luna perception calls.
- Acceptance boundary reached: 303 empty observations over 30.639 seconds and 599 continuously confirmed one-person observations over 60.559 seconds were captured from the same raw inference path. No tested threshold met both empty false-positive rate <=1% and one-person >=95% recall with rare duplicate detections.
- Stop condition reached: `DETECTOR CALIBRATION FAILED — REPLAN MODEL`. Tracker diagnostics, dropout, soak, and camera recovery were not run because detector calibration failed.
- Evidence level: E5_OPERATIONALLY_OBSERVED for the operator-confirmed segments; bounding-box visual sanity was NOT ACCEPTED because headless OpenCV lacks GUI support.
- Source: Architect directive `SENTRY-M1-DETECTOR-CALIBRATION-001`, current OpenVINO implementation, metadata-only live captures, and offline threshold evaluation.

---

## SENTRY-M1-DETECTOR-0303-001 — Replace the failed detector with Open Model Zoo person-detection-0303
- Issued: 2026-08-26
- Status: STOPPED AT CONFIRMED QUALITY FAILURE — returned to Architect for detector decision
- Project stage: M1 — Local Windows Perception
- Objective: Replace only the failed `person-detection-0202` model with the official Open Model Zoo `person-detection-0303` FP32 model through the existing OpenVINO runtime, then calibrate it before evaluating the unchanged IoU tracker.
- Scope: Official provenance/checksum verification, native 1280x720 model integration, metadata-only operator-confirmed empty/one-person calibration, and short CPU performance check.
- Exclusions: No tracker tuning/replacement, alternate detector/runtime, GPU/FP16 switch, identity, persistence, events, API, voice, M2, or Codex/Luna perception calls.
- Acceptance boundary reached: 0303 loaded/compiled and produced documented `boxes`/`labels` outputs. Stage A passed with 279 empty observations over 30.863 seconds and zero candidates. Stage B failed with 588 observations over 60.91 seconds of continuously confirmed one-person visibility and zero candidates at every threshold from 0.10 through 0.90.
- Stop condition reached: `STOP — 0303 DETECTOR QUALITY FAILURE`. Tracker, dropout, soak, and camera recovery were not run under this directive.
- External discovery: REQUIRED and completed narrowly against the official Open Model Zoo manifest, README, license, and artifact sources.
- Source: Architect directive `SENTRY-M1-DETECTOR-0303-001`, official Open Model Zoo records, current OpenVINO implementation, and operator-confirmed metadata-only live runs.

---

## SENTRY-M1-0303-DECODER-RECONCILE-001 — Reconcile person-detection-0303 decoding with the official class-agnostic adapter
- Issued: 2026-08-26
- Status: COMPLETE — decoder bug confirmed; corrected 0303 still fails quality; returned to Architect for detector decision
- Project stage: M1 — Local Windows Perception
- Objective: Determine whether the prior 0303 zero-candidate result was caused by SENTRY decoding, correct only the decoder if justified, and rerun the detector quality gate.
- Scope: Metadata-only raw-output investigation, official adapter reconciliation, positive-confidence class-agnostic decoding, `[1/1280, 1/720]` coordinate reconstruction, clipping, NMS `0.6`, focused tests, and operator-confirmed empty/one-person calibration.
- Exclusions: No model, runtime, device, precision, camera, tracker, threshold, identity, persistence, events, API, voice, M2, or Codex/Luna perception changes.
- Acceptance boundary reached: Raw output contained 1,474 positive-confidence rows during 149 confirmed one-person observations while the old label gate produced zero candidates. After correction, empty-safe threshold `0.45` had 0/181 false-positive observations, but one-person recall was only 134/556 (24.10%); no tested threshold met empty FP <=1% and one-person recall >=95%.
- Stop condition reached: `DECODER BUG CONFIRMED — 0303 STILL FAILS QUALITY`. Tracker, dropout, soak, and camera recovery were not run.
- Evidence level: E5_OPERATIONALLY_OBSERVED for the operator-confirmed raw and corrected calibration segments; no raw frames were persisted.
- Source: Architect directive `SENTRY-M1-0303-DECODER-RECONCILE-001`, official Open Model Zoo adapter/configuration, current SENTRY implementation, and metadata-only operator-confirmed live runs.

---

## SENTRY-CONVERGENCE-RTDETR-PRESENCE-STATE-001 — Qualify temporal authoritative room state using the retained RT-DETR candidate
- Issued: 2026-08-27
- Status: STOPPED AT STAGE A FALSE-HUMAN-EVIDENCE FAILURE — returned to Architect; RT-DETR remains implemented-unverified and uncommitted
- Project stage: M1 — Local Windows Perception
- Objective: Measure `empty`, `occupied`, `degraded`, and `offline` room-state correctness over time using the existing RT-DETRv2 R18 path, without restarting isolated per-frame detector qualification.
- Scope: Retained uncommitted RT-DETR integration, existing OpenVINO CPU/camera/buffer/tracker path, minimum timestamp-based state machine, metadata-only image-quality metrics, deterministic tests, and sequential operator-labeled room-state stages.
- Exclusions: No detector/model/runtime/precision/device/tracker/camera changes, threshold optimization, identity, persistence, sessions, semantic events, API, voice, proactive behavior, M2, image enhancement, or raw-frame persistence.
- Initial configuration: entry confirmation `1.0s`; entry evidence-gap tolerance `1.0s`; absence grace `15.0s`. Source/detector/visual-quality failure maps to `degraded` or `offline`, never inferred `empty`.
- Pre-live gate: PASSED. RT-DETR checkpoint hash and ignored IR artifacts remain present; prior equivalence evidence is preserved; full automated suite passes 33/33; diff scope reviewed; no runtime Codex/Luna calls or raw frames.
- Stage A result: fresh `CONFIRMED_EMPTY — START` run completed from `2026-08-27T15:35:50.088767+00:00` to `2026-08-27T15:36:50.236329+00:00`. After startup, 118 online observations were recorded; room state was `empty` for 40, `occupied` for 78, and 5 observations were degraded during startup. Eight positive candidate observations (confidence range `0.5315-0.8581`) caused `empty->occupied` at `2026-08-27T15:36:27.653707+00:00`; the false occupied interval ended at `2026-08-27T15:36:43.447774+00:00`. **STATE FAILURE — FALSE HUMAN EVIDENCE**.
- Stop boundary: Stages B-F were not run. Do not reuse this failed run as evidence for later stages, and do not commit RT-DETR as accepted production capability.
- Source: Architect directive `SENTRY-CONVERGENCE-RTDETR-PRESENCE-STATE-001`, current formal project scope, Authority state, retained RT-DETR working tree, and existing local runtime evidence.

---

## SENTRY-CONVERGENCE-0202-PRESENCE-STATE-001 — Qualify temporal authoritative room state using the restored 0202 signal
- Issued: 2026-08-27
- Status: PRE-LIVE GATE PASSED — waiting for fresh operator-labeled Stage A marker
- Project stage: M1 — Local Windows Perception
- Objective: Determine whether the previously verified Open Model Zoo `person-detection-0202` signal at confidence `0.40` can satisfy the room-state requirement through the existing timestamp-based state machine.
- Scope: Restore 0202 from historical commit `ec4a2f3`, preserve generic state/luminance work, retain OpenVINO CPU/camera/buffer/tracker, and run sequential operator-confirmed room-state stages.
- Exclusions: No new detector, RT-DETR requalification, 0303, threshold sweep before a narrow failure, tracker change, runtime/device/precision/camera change, image enhancement, identity, persistence, sessions, semantic events, API, voice, M2, or Codex/Luna perception calls.
- Working-tree recovery: Complete pre-existing diff and untracked state files preserved under ignored canonical `perception-data/runtime/recovery-20260827/`. RT-DETR-specific active production source/config/tests/tooling were removed; ignored RT-DETR artifacts remain local and outside Git.
- Current implementation: 0202 FP32 XML/BIN from the previously verified Open Model Zoo path; `openvino==2026.3.1`, CPU; threshold `0.40`; presence entry confirmation `1.0s`, evidence-gap tolerance `1.0s`, absence grace `15.0s`.
- Automated pre-live validation: **PASSED — 24/24 tests**. 0202 XML/BIN SHA-384 checksums match Authority records; config loads; `git diff --check` passed.
- Short performance gate: **PASSED** — DirectShow 1280x720/15 FPS, 126 captured / 121 processed, 5.962 processed FPS, 24.776 ms median, 29.117 ms p95, 4 dropped frames, online throughout, zero Codex/Luna calls.
- Live status: Stage A passed with fresh operator-labeled evidence. Next gate is `CONFIRMED_ENTRY — START` after the operator begins outside the camera view; do not reuse prior detector-specific markers.
- Source: Architect disposition `SENTRY-CONVERGENCE-0202-PRESENCE-STATE-001`, historical 0202 implementation, current generic state layer, local artifacts, and pre-live checks.

### Stage A result — 2026-08-27
- Status: **PASSED — confirmed-empty room-state gate**.
- Fresh marker: `CONFIRMED_EMPTY — START` at `2026-08-27T16:40:26.042108+00:00`; runner ended at `2026-08-27T16:41:12.519343+00:00`.
- Usable interval: 230 online observations; 7 startup observations were degraded. Authoritative state was `empty` for 230/230 usable observations (`100%`).
- Detector evidence: 0 positive observations, 0 multi-candidate observations, maximum candidate count 0. No false `occupied` transition, sustained phantom occupancy, or false re-entry occurred.
- Performance: 233 captured / 230 processed online, 7.592 processed FPS, 28.307 ms median, 48.788 ms p95, 2 dropped frames, DirectShow 1280x720/15 FPS, camera online at completion.
- Safety: raw frames `NONE`; runtime Codex/Luna calls `0`.
- Next gate: request fresh `CONFIRMED_ENTRY — START` only after the operator begins outside the camera view. Do not reuse prior detector-specific markers.

---

## SENTRY-UBUNTU-PLATFORM-MIGRATION-001 — Re-baseline SENTRY on Ubuntu/Linux
- Issued: 2026-08-28
- Status: **BASELINE QUALIFIED — fresh Ubuntu M1 ground truth not run**
- Current platform: Ubuntu 24.04.4 LTS, V4L2, canonical Atlas `/srv/ATLAS`, OpenVINO CPU, direct OAuth Codex/Luna bridge.
- Historical boundary: Windows/DirectShow evidence is preserved as historical. The unfinished Windows Stage B entry result is `INVALID/UNRESOLVED` and is not reused.
- Repository boundary: exact Atlas checkout retained at `f5ca399dab2b53d90792de1039b519d129bf89dd`; pre-existing dirty tracked/untracked work was preserved in ignored `perception-data/runtime/recovery-ubuntu-20260828/` before edits.
- Camera evidence: stable NexiGo N60 `/dev/v4l/by-id/usb-webcamvendor_NexiGo_N60_FHD_Webcam_Jan_29_2024-10:32:28-N60-video-index0`, V4L2, MJPEG, 1280x720, 15 FPS; user ACL permits access.
- Runtime evidence: Python 3.12.3, OpenCV 4.12.0.88 with V4L2 support, OpenVINO 2026.3.1, psutil 7.0.0; 0202 checksums/load/CPU compile/synthetic inference passed; Linux tests 26/26 passed.
- Smoke evidence: 666 captured / 665 processed, 14.760 processed FPS, 16.189 ms median, 17.912 ms p95, 0 drops, online throughout; no raw frames persisted and perception Codex/Luna calls `0`.
- Codex/Luna parity: `codex-cli 0.150.0-alpha.8`, ChatGPT OAuth authenticated, bounded synthetic event proof passed with immutable `gpt-5.6-luna` and low effort. Audio stack inventory completed only.
- Scope boundary: no fresh empty/entry/occupied/exit markers, threshold tuning, detector research, tracker changes, identity, persistence, sessions, API, voice implementation, deployment, or M2 work.
- Next gate: fresh Ubuntu operator-labeled M1 room-state qualification from `CONFIRMED_EMPTY — START`; do not reuse Windows markers.

## SENTRY-UBUNTU-M1-PRESENCE-QUALIFICATION-001 — Fresh Ubuntu room-state qualification
- Issued: 2026-08-28
- Status: **STOPPED AT STAGE B — OCCUPIED EVIDENCE INSUFFICIENT; returned to Architect**
- Platform: Ubuntu 24.04.4 LTS, V4L2, stable NexiGo by-id path, OpenVINO CPU, 0202 threshold `0.40`, timestamp state timing unchanged.
- Stage A passed: 441/441 usable online observations were authoritative `empty`; zero detector positives, zero false occupied transitions, zero drops; 14.667 FPS, 15.576 ms median, 17.989 ms p95.
- Initial Stage B attempt was invalid because marker-to-occupied timing included camera startup and clear visibility was not separately timestamped.
- The one authorized retry established detector evidence and an `empty->occupied` transition, then lost detector evidence while the operator remained in frame. The service falsely transitioned `occupied->empty` at `16:07:39.546311+00:00` after the configured 15-second grace. Entry from first credible evidence to `occupied` was approximately 0.996 seconds, but sustained occupied state failed.
- Primary disposition: **STATE FAILURE — UBUNTU OCCUPIED EVIDENCE INSUFFICIENT**. This is not an operator-protocol failure and does not authorize Stage C-F, detector changes, tracker changes, or M2.
- Raw frames: none persisted. Perception Codex/Luna calls: `0`. Tracker/model/runtime/camera configuration unchanged.
- Source: Architect directive `SENTRY-UBUNTU-M1-PRESENCE-QUALIFICATION-001`, fresh operator markers, operator correction confirming continued visibility, and metadata-only canonical runtime records.
## SENTRY-UBUNTU-M1-ASYMMETRIC-EVIDENCE-001 — Test strong entry plus lower support hold evidence
- Issued: 2026-08-28
- Status: **STOPPED AT PHASE 2 — NO QUALIFYING OPERATING BAND; returned to Architect**
- Project stage: Ubuntu M1 asymmetric-evidence calibration
- Objective: Expose positive 0202 candidates from one inference, evaluate a fixed `0.40` entry threshold with lower support thresholds, and change production hold semantics only if the same metadata proves a valid operating band.
- Scope: Metadata-only raw candidate capture, operator-confirmed 60-second empty and 120-second continuous-one-person segments, offline support thresholds `0.10` through `0.40`, and deterministic state-policy simulation.
- Exclusions: No new detector/model/runtime, tracker change, grace increase, entry-threshold relaxation, GPU/FP16, image enhancement, identity, persistence, events, API, voice, M2, or Codex/Luna perception calls.
- Pre-live implementation: Added one-inference `detect_raw()` exposure, explicit strong/support evidence state inputs, production telemetry fields, and calibration simulation. Production hold remains `0.40`; no Phase 3 behavior was activated.
- Phase 2 evidence: Empty segment had 889 observations and 40,815 positive raw candidates, max confidence `0.285640`, and zero candidates at `0.40`. Continuous-one-person segment had 1,791 observations and 55,051 positive raw candidates, max confidence `0.547175`, but only 63 observations at `0.40`; the simulated fixed-entry state achieved only 62.9257% occupied correctness for support thresholds `0.10` through `0.35` and 40.0893% at `0.40`.
- Stop condition reached: `ASYMMETRIC EVIDENCE FAILED — 0202 SOURCE INSUFFICIENT`. No support threshold met the `>=95%` occupied-state requirement with bounded exit. Fresh live Phase 4 A-D stages, Phase 3 production activation, and any threshold change were not run.
- Automated tests: **32/32 PASSED**; raw frames `NONE`; perception Codex/Luna calls `0`.
- Source: Architect directive `SENTRY-UBUNTU-M1-ASYMMETRIC-EVIDENCE-001`, current Ubuntu 0202 implementation, fresh operator-confirmed metadata-only segments, and the corrected offline state simulator.

## SENTRY-UBUNTU-M1-YOLOX-S-001 — Official YOLOX-S room-state qualification
- Issued: 2026-08-28
- Status: **STOPPED AT FINAL STAGE A — OFFICE EVIDENCE INSUFFICIENT; returned to Architect**
- Scope executed: official YOLOX-S source/export/runtime integration, metadata-only state calibration, and one fresh operator-confirmed empty-room Stage A. Tracker, camera stack, OpenVINO CPU path, state timing, and privacy boundary remained unchanged.
- Calibration: selected `0.50` as the highest tested state-qualified threshold from the same labeled metadata records; simulated empty state qualified and one-person occupied correctness was `99.0585%` with approximately `1.124s` entry latency.
- Final Stage A: 566 observations, 565 online usable; 53/565 threshold-qualified positive observations (`9.38%`), maximum two simultaneous detections, and authoritative `occupied` for 186/565 observations (`32.92%`) including a sustained `19.272s` false-occupancy interval. Positive confidence reached `0.824309`.
- Stop boundary: `YOLOX-S OFFICE EVIDENCE INSUFFICIENT`. Stages B-D, low-light, camera recovery, and soak were not run. No accepted production-detector commit or push was made.
- Automated suite after calibration correction and threshold selection: **37/37 PASSED**; compilation and `git diff --check` passed. Raw frames: `NONE`; perception Codex/Luna calls: `0`.
## Architect authorization — proceed from M1 to M2 presence persistence — 2026-08-28
- Status: **AUTHORIZED / M2 ACTIVE**
- Decision: Practical Ubuntu camera/human detection is good enough for the project goal. Freeze detector selection and stop reopening per-frame detector qualification.
- Objective: Carry the existing `empty/occupied/degraded/offline` state into durable, restart-safe metadata-only presence sessions and queryable local history.
- Scope: Versioned SQLite store, state-derived room/session events, current-state readback, and localhost-only query API. No identity, raw-frame persistence, proactive behavior, new detector, tracker replacement, or broad M2 framework.
- Source: Architect/user authorization in the active Codex task, reconciled with the SENTRY Notion goal and `docs/PROJECT_SCOPE.md` M2 deliverables.

## SENTRY-UBUNTU-M1-YOLOX-CORRECTED-LIVE-001 — Corrected YOLOX fresh live qualification
- Issued: 2026-08-28
- Status: **ACTIVE / M1 OPEN**
- Architect correction: the prior `230dafa` M1→M2 transition claim is superseded. Preserve that commit and its useful implementation, but do not treat M1 or M2 as accepted.
- Required path: corrected official YOLOX winning-class postprocess, threshold `0.50`, NMS `0.45`, unchanged state timings, fresh operator-confirmed Ubuntu Stage A-D.
- Persistence boundary: disable durable persistence or use an isolated ignored qualification database. Qualification runs must not enter household history.
- Stop boundaries: camera ownership blocker; Stage A false occupancy/source rejection; precise Stage B/C state-evidence failure; no detector/tracker/timing changes; no M2 expansion.
- Required status classification: Ubuntu platform **VERIFIED**; original YOLOX Stage A failure **VERIFIED**; postprocess correction **IMPLEMENTED_UNVERIFIED live**; M1 **OPEN / NOT ACCEPTED**; SQLite/session/API **IMPLEMENTED_UNVERIFIED / OUT-OF-SEQUENCE**; M2 **NOT ACCEPTED**.

## SENTRY-M2-DURABLE-PRESENCE-MEMORY-001 — Durable presence memory and localhost history
- Status: **ACTIVE; TOPOLOGY CHECK BLOCKED**
- Owner/operator has accepted practical M1 camera/human detection for V0.1 progression and frozen detector selection. No further detector qualification is authorized.
- Objective: qualify durable metadata-only presence sessions, restart reconciliation, failure truthfulness, SQLite invariants, and the localhost query API using the existing persistence slice.
- Storage boundary: first measure the actual DB filesystem. If the DB operates on the Atlas SFTP/FUSE/network mount, return `M2 STORAGE TOPOLOGY BLOCKER`; do not relocate storage, use old pool paths, use mergerfs, or introduce another database service.
- Exclusions: no detector, tracker, camera, low-light, identity, voice, M3, systemd, Home Assistant, Redis/Postgres, or whole-home work.
- Source: owner/operator directive `SENTRY-M2-DURABLE-PRESENCE-MEMORY-001` and current SENTRY Notion/Authority records.
