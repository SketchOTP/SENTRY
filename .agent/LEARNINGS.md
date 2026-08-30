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

---

## LEARNING-SENTRY-008 — HOG plus IoU track telemetry can overstate office presence quality
- Date: 2026-08-25
- Evidence source: `SENTRY-M1-LIVE-QUALIFICATION-001`; human-visible NexiGo N60 preview and 30/90-second live runs
- Confidence: VERIFIED HOST-OBSERVED QUALITY FAILURE

### Learning
In the observed one-person office scene, OpenCV HOG produced non-empty person records frequently but the SENTRY IoU tracker emitted multiple simultaneous tracks and high ID churn: up to 3 tracks and IDs 1–14 in 30 seconds, then up to 6 tracks and IDs 1–29 in 90 seconds. Non-empty output and FPS therefore do not establish reliable presence sensing.

### Why it matters
M1 acceptance must prioritize human-correlated detection and track stability over execution, throughput, or detector-row counts. The current evidence supports a detector-quality bottleneck and a separate Architect decision; it does not authorize silent detector/tracker replacement.

### Recheck trigger
Recheck only after an explicitly authorized detector/tracker change or a new bounded calibration/investigation directive.

## LEARNING-SENTRY-009 — Open Model Zoo IR provenance does not establish generic OpenCV executability
- Date: 2026-08-25
- Evidence source: `SENTRY-M1-DETECTOR-REPLAN-001`; official Open Model Zoo manifest/license, verified FP32 artifacts, and host OpenCV 4.12.0 runtime checks
- Confidence: VERIFIED HOST-RUNTIME COMPATIBILITY FAILURE

### Learning
The official `person-detection-0202` FP32 XML/BIN artifacts matched the manifest SHA-384 checksums and Apache-2.0 license provenance, but the pinned generic `opencv-python-headless==4.12.0.88` could not load the OpenVINO IR through either `cv2.dnn.readNetFromModelOptimizer` or `cv2.dnn.readNet`. Both reported that the `openvino` backend plugin was unavailable.

### Why it matters
Model provenance and API surface are separate gates from actual wheel capability. A compatible OpenCV build or OpenVINO Runtime may be required, but adding either is a strategic/runtime decision outside this directive.

### Recheck trigger
Recheck only after explicit Architect authorization for a compatible inference runtime or a different detector candidate.

## LEARNING-SENTRY-010 — Runtime readiness does not establish live detector quality
- Date: 2026-08-26
- Evidence source: `SENTRY-M1-DETECTOR-RUNTIME-001`; OpenVINO host checks, model smoke inference, automated tests, and two unconfirmed camera runs
- Confidence: VERIFIED RUNTIME; LIVE QUALITY UNCONFIRMED

### Learning
The official OpenVINO runtime can load and compile the checksummed `person-detection-0202` FP32 model on the Ryzen host, and the detector runs above the 5 FPS floor. However, model telemetry without an operator-confirmed subject segment cannot establish person detection quality or distinguish missed subjects from an empty scene.

### Why it matters
The live gate must preserve the distinction between executable software, observed camera output, and human-confirmed ground truth. Conflicting telemetry-only runs must remain unresolved rather than being promoted to Stage A evidence.

### Recheck trigger
Recheck with an explicitly operator-confirmed one-person office segment, then evaluate the unchanged tracker before considering any tracker change.

---

## LEARNING-SENTRY-011 — Confirmed continuous visibility exposes OpenVINO detector inadequacy
- Date: 2026-08-26
- Evidence source: `OUTCOME-SENTRY-M1-OPENVINO-LIVE-001`; operator-marked empty and continuous-one-person live runs
- Confidence: VERIFIED LIVE QUALITY FAILURE

### Learning
The committed OpenVINO `person-detection-0202` path stayed above the FPS floor and produced no false-person output during the confirmed-empty baseline, but during approximately 83.9 seconds of continuously confirmed one-person visibility it produced exactly one detector box in only 318/827 observations, no detector box in 480/827, and multiple boxes in 29/827. The unchanged IoU tracker consequently created 19 IDs and 32 visible-ID-set changes.

### Why it matters
The model/runtime integration is technically valid but not adequate for this office scene. Tracker churn cannot be isolated as the primary bottleneck until a detector provides reliable one-person observations.

### Recheck trigger
Recheck only after an explicitly authorized detector replan or calibration directive; preserve this negative live result.

## LEARNING-SENTRY-012 — Confidence calibration cannot rescue person-detection-0202 in the tested office scene
- Date: 2026-08-26
- Evidence source: `OUTCOME-SENTRY-M1-DETECTOR-CALIBRATION-001`; operator-confirmed 30-second empty and 60-second continuous-one-person segments using shared raw OpenVINO inference
- Confidence: VERIFIED LIVE CALIBRATION FAILURE

### Learning
The raw confidence distributions of `person-detection-0202` did not provide a usable operating point in the tested office scene. Threshold `0.20` kept empty false positives at 0.660% but generated duplicate detections in 98.164% of one-person observations. Threshold `0.40` reached 96.661% any-detection recall but still generated duplicate detections in 10.684% of observations. Threshold `0.45` reduced duplicates to 0.334% but lowered recall to 89.149%.

### Why it matters
The model cannot be accepted by threshold calibration alone. A model replan is justified while the tracker remains unchanged and M2 remains gated.

### Recheck trigger
Recheck only after a separately authorized model candidate is integrated and its artifacts/runtime are independently verified.

---

## LEARNING-SENTRY-013 — Native 0303 model failed confirmed seated-office detection
- Date: 2026-08-26
- Evidence source: `OUTCOME-SENTRY-M1-DETECTOR-0303-001`; official Open Model Zoo records; operator-confirmed metadata-only live runs
- Confidence: VERIFIED LIVE QUALITY FAILURE

### Learning
Open Model Zoo `person-detection-0303` loaded and executed through the existing OpenVINO CPU runtime, and a short camera check exceeded 5 processed FPS. However, during 588 observations over 60.91 seconds of continuously confirmed one-person visibility, the model emitted zero person candidates before thresholding. A 30.863-second confirmed-empty segment also emitted zero candidates.

### Why it matters
The native 1280x720 candidate does not satisfy the M1 detector gate in the tested office scene, even at thresholds as low as 0.10. The unchanged IoU tracker remains unjudged because no valid detector input was available.

### Recheck trigger
Recheck only after a separately authorized detector decision. Preserve the 0202 calibration failure, the 0303 failure, and the unchanged tracker boundary.

---

## LEARNING-SENTRY-014 — 0303 raw boxes were discarded by an incorrect label gate, but corrected semantics still failed quality
- Date: 2026-08-26
- Evidence source: `OUTCOME-SENTRY-M1-0303-DECODER-RECONCILE-001`; official Open Model Zoo `accuracy-check.yml` and `ClassAgnosticDetectionAdapter`; operator-confirmed metadata-only live runs
- Confidence: VERIFIED LIVE QUALITY RESULT

### Learning
Open Model Zoo `person-detection-0303` uses class-agnostic detection semantics: positive box confidence is authoritative, companion labels do not select the class, coordinates are scaled by `[1/1280, 1/720]`, retained rows are assigned person label `1`, and reference NMS overlap is `0.6`. The previous SENTRY label gate discarded all raw rows because the live model emitted label `0` for every positive row.

After correcting that decoder, the model produced plausible candidates, but the confirmed-empty and confirmed-one-person calibration still had no acceptable operating point. At empty-safe threshold `0.45`, one-person recall was only 24.10%; at `0.40`, recall was 48.56% with empty false positives above the 1% gate.

### Recheck trigger
Return to Architect for a separately authorized detector decision. Preserve the corrected decoder, raw metadata, negative calibration evidence, and unchanged tracker boundary.

---

## LEARNING-SENTRY-015 — Room-state qualification must aggregate imperfect detector evidence
- Date: 2026-08-27
- Evidence source: `SENTRY-CONVERGENCE-RTDETR-PRESENCE-STATE-001` pre-live implementation and deterministic tests
- Confidence: VERIFIED IMPLEMENTATION; LIVE RESULT PENDING

### Learning
The project acceptance metric is temporal authoritative room state, not per-frame detector recall. A binary detector-positive observation can refresh human evidence, while duplicate boxes remain one occupancy signal. Timestamp-based hysteresis can hold `occupied` through short detector dropouts and expire to `empty` only after a configured usable-camera grace period.

### Safety boundary
Camera, detector, or explicitly unusable visual-quality input maps to `degraded`/`offline`; it must never be converted to inferred `empty`. No low-light cutoff is assumed until operator-labeled evidence establishes one.

### Recheck trigger
Run the sequential operator-labeled room-state stages. If state acceptance fails, classify evidence insufficiency, false human evidence, or state-logic failure before any further detector decision.

---

## LEARNING-SENTRY-016 — Temporal hysteresis cannot rescue sustained false human evidence
- Date: 2026-08-27
- Evidence source: fresh operator-confirmed-empty Stage A run for `SENTRY-CONVERGENCE-RTDETR-PRESENCE-STATE-001`
- Confidence: VERIFIED LIVE QUALITY RESULT

### Learning
The RT-DETR/state path produced eight positive candidate observations in a confirmed-empty office scene, including duplicate two-person output and confidences up to `0.8581`. The timestamp-based state machine consequently reported `occupied` for approximately 15.8 seconds. The 15-second absence grace correctly held the state after evidence disappeared, but it cannot distinguish a sustained phantom candidate from a real occupant.

### Safety boundary
Stage A is a decisive **STATE FAILURE — FALSE HUMAN EVIDENCE**. Do not continue to entry, occupied, exit, low-light, or camera-recovery stages, and do not promote or commit RT-DETR as accepted production capability from this run.

### Recheck trigger
Architect must choose the next bounded action. Preserve the metadata-only capture, current state implementation, and prior negative evidence; do not start a detector carousel or alter the tracker without explicit authorization.

---

## LEARNING-SENTRY-017 — OS migration invalidates platform-specific live evidence, not architecture
- Date: 2026-08-28
- Evidence source: `SENTRY-UBUNTU-PLATFORM-MIGRATION-001`
- Confidence: VERIFIED PLATFORM BASELINE

### Learning
When the host changes from Windows to Ubuntu, DirectShow, PnP, numeric device-index, Windows runtime, and unfinished Windows operator-marker evidence must be reclassified as historical or invalid/unresolved. The accepted detector/state architecture, local OpenVINO boundary, privacy rule, Atlas storage, and OAuth Codex/Luna boundary remain valid and must be reproduced rather than reset.

### Verified Linux boundary
The NexiGo N60 is stable through `/dev/v4l/by-id/`, OpenCV 4.12.0.88 exposes V4L2, OpenVINO 2026.3.1 loads the checksummed 0202 model on CPU, and the metadata-only camera/inference smoke remains above the 5 FPS floor. Stable device identity is preferable to `/dev/videoX` because Linux node numbers are not a durable camera identity.

### Safety boundary
Telemetry-only smoke is not occupancy ground truth. Fresh Ubuntu operator markers are required before M1 acceptance; no Windows marker may be reused. Camera failure/recovery remains a later physical test, and no raw frames, identity, persistence, sessions, API, voice implementation, or M2 behavior were introduced.

## LEARNING-SENTRY-018 — Identity must annotate presence, never replace it
- Date: 2026-08-29
- Evidence source: `SENTRY-M3-PRIMARY-IDENTITY-001`; OpenCV Zoo model loading and 67-test Ubuntu regression
- Confidence: VERIFIED IMPLEMENTATION

### Learning
YuNet/SFace identity is safest as a bounded annotation on an existing person track. No face, poor quality, clipped face, ambiguous association, or model failure produces `unresolved`; a usable non-match produces `unknown`; only a temporally confirmed enrolled match produces `recognized`. None of those outcomes changes the authoritative room state.

### Privacy boundary
Enrollment frames and individual query embeddings are transient. Only one normalized enrolled prototype is stored in local SQLite schema version 3 and included in the existing validated Atlas snapshot path. API responses and semantic event payloads expose identity metadata but never prototype bytes.

### Recheck trigger
Require a fresh deliberate enrollment, high-quality primary-user holdout, consenting non-primary negative segment, threshold calibration, and restart/Atlas recovery proof before calling M3 qualified.

## LEARNING-SENTRY-019 — Carry identity annotations across bounded cadence only for the same visible track
- Date: 2026-08-29
- Evidence source: corrected live primary verification and 69-test regression
- Confidence: VERIFIED IMPLEMENTATION

### Learning
When identity inference runs at a bounded cadence, the last identity annotation must be carried only to the same currently visible track between evaluations. Dropping it on intervening frames creates false unresolved flicker; transferring it to a new or ambiguous track would create false identity continuity. The correction preserved room-state independence and improved the live primary run to first recognition in 2.773 seconds.
## LEARNING-SENTRY-020 — Ground conversational answers in a bounded API fact packet
- A localhost API should be the only M4 retrieval boundary: health first, then a deterministic allow-list of current state, people, sessions, and selected semantic-event metadata.
- Stable fact IDs plus response validation prevent a model from citing data it never received; `partial`/`unavailable` must remain valid outcomes when the live DB lacks an observation or history.
- Room-session start and first primary-user identification are separate facts. A grounded assistant may report a lower bound or limitation rather than inventing personal arrival time.

## LEARNING-SENTRY-021 — Proactivity must consume persisted events outside perception
- M5 is safest when the proactive processor reads committed metadata events through a separate SQLite connection. This preserves zero Luna calls inside continuous perception while still allowing one bounded judge call for an eligible event.
- Reserve an action before Luna/TTS. The durable reservation prevents a process restart after delivery from redelivering the same source event; final judge/delivery fields then record the outcome.
- A clean camera run with no `person.identified` event is unresolved physical integration evidence. It must not be converted into detector failure or proactive-policy success; the live event path remains unqualified until a real candidate reaches the processor.

## LEARNING-SENTRY-022 — Physical proactive qualification requires a live empty baseline before entry
- The physical M5 harness must start perception before operator confirmation. A startup sleep followed by an entry prompt can never establish whether the later event came from a real transition.
- Require both operator ground truth and persisted state evidence: `CONFIRMED_EMPTY`, online camera, authoritative `empty`, no open session, and a bounded stability interval. Startup suppression must elapse while perception is running, then the harness may prompt `PRIMARY_USER_ENTER_NOW`.
- A real event may validly result in persisted `judge_silent`; silence is successful restrained behavior. Replay must return `duplicate` with zero additional Luna calls and no second delivery.

## LEARNING-SENTRY-023 — Resident SENTRY should use independent user-systemd services
- Date: 2026-08-30
- Evidence source: `SENTRY-V0.2-RESIDENT-RUNTIME-001`; 900-second live probe and process-level restart tests
- Confidence: VERIFIED RUNTIME

### Learning
Separate native user-systemd units for perception, the localhost API, and proactive polling preserve component isolation while providing bounded restart/backoff and startup enablement. A metadata-only perception heartbeat is sufficient for operational liveness without persisting frames or audio.

### Safety boundary
The authenticated user session is the startup condition when `Linger=no`; this must not be described as boot-before-login persistence. Local SQLite remains the live database and Atlas remains a complete snapshot mirror. Service restarts must not be interpreted as physical entry/exit events, and proactive dedupe must remain persisted outside perception.
## LEARNING-SENTRY-024 — Routine maturity must require independent dates
Routine statistics can be transparent and useful without an ML model when clock times are treated circularly and positive durations/intervals use robust summaries. Sample count alone is insufficient: requiring distinct local dates prevents one unusually busy day from manufacturing a stable routine. Sparse natural history should remain explicitly `insufficient`.

## LEARNING-SENTRY-025 — Derived routine refresh belongs outside perception
Routine refresh is safely isolated as a user-systemd oneshot/timer over the local SQLite source. The timer can fail or lag without stopping perception, the localhost API, or proactive processing; snapshots are rebuildable and mirrored through the existing Atlas backup path.

## LEARNING-SENTRY-026 — Routine conversation must remain maturity- and source-aware
Routine questions can safely reuse the M4 fact boundary when intent and scope are selected deterministically, only the requested derived snapshots are allow-listed, and current physical facts remain alongside them. Sparse `insufficient` history should return a direct evidence-limited answer with zero Luna calls; routine-source failure should not affect ordinary physical queries. `observed` is tentative and `stable` is the only maturity that supports unqualified habitual wording. Derived room timing is not personal arrival, and routine statistics must remain outside M5.

## LEARNING-SENTRY-027 — Explicit preference memory must be narrow, reversible, and upstream of proactivity
The safest first personalization layer is an append-only typed preference ledger with one supported behavior key, deterministic set/allow/clear commands, explicit provenance, and idempotent request IDs. Feedback should reference a real delivered proactive action; only explicit `do_not_repeat` may create a suppress preference. M5 should evaluate this preference after physical/source validity gates but before cooldown, budget, Luna, or speech, while default/allow preserve existing behavior. Silence, non-response, routines, and repeated behavior are not feedback.

## LEARNING-SENTRY-028 — External weather context must be explicit and freshness-gated
- Date: 2026-08-30
- Evidence source: `SENTRY-V0.2-WEATHER-CONTEXT-001`; schema-v7 migration, isolated NWS refresh, API/privacy tests, and `150/150` Ubuntu regression
- Confidence: VERIFIED IMPLEMENTATION

### Learning
Use one bounded provider adapter with explicit operator coordinates, stable point-resource caching, bounded retry, normalized snapshots, and source freshness. Keep missing/stale weather visibly missing/stale rather than guessing or silently extending the last good value.

### Safety boundary
Weather is external context and must remain outside physical truth and M5 proactive facts. A local SQLite snapshot can safely mirror to Atlas, but the live database must remain on local ext4. No implicit geolocation or weather-driven speech is authorized by this foundation.
