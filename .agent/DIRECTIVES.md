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
