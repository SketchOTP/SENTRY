# Outcome Ledger

---

## OUTCOME-SENTRY-AUTHORITY-BOOTSTRAP-001 — Directive SENTRY-AUTHORITY-BOOTSTRAP-001
- Completed: 2026-08-24
- Verdict: COMPLETE
- Retrieval confidence: ADEQUATE
- Evidence level: E3_TARGET_TESTED
- Git state / commit: Final governance commit recorded in the GitHub handoff and Notion update.

### Technical state discovered
The restored `main` checkout was clean at baseline `63376fe` and contained only the pre-Authority documentation-first SENTRY repository. GitHub and Notion agree on the project goal, V0.1 office boundary, M0 gate, DAWN evaluation, Miloco reference-only status, and absence of runtime implementation.

### Work performed
Installed the canonical Authority 3.0 root router, project-state/history structure, reusable workflow and references, SENTRY-specific state records, and a completed governance task packet. No product/runtime implementation was added.

### Acceptance results
- Canonical Authority 3.0 structure installed: PASSED
- Root `AGENTS.md` is the Authority router: PASSED
- `.agent/` state is SENTRY-specific and identifies M0: PASSED
- `.agents/` workflow/reference paths resolve: PASSED
- Existing SENTRY documentation preserved: PASSED
- No runtime implementation or dependencies introduced: PASSED
- Commit and push to GitHub: PASSED
- Notion evidence update: PASSED

### Validation
- Expected Authority tree exists: PASSED
- Root router references real mandatory paths: PASSED
- `.agent/INDEX.md` references real mandatory state files: PASSED
- Required workflow/reference files exist: PASSED
- SENTRY-specific goal/scope/current-state content present: PASSED
- Governance-only placeholder scan: PASSED
- Final diff limited to governance/state files: PASSED
- Final working tree clean after commit: PASSED

### Assumptions confirmed
- SENTRY was documentation-first and implementation had not begun.
- M0 — Bootstrap + DAWN Integration Feasibility is the current authorized gate.
- DAWN is the preferred foundation under evaluation; Miloco is architectural reference only.

### Assumptions disproven
- None.

### Risks / blockers
- DAWN integration behavior remains unverified and is intentionally deferred to M0.

### Architect decision required
YES — review and accept this governance result before authorizing M0 implementation.

---

## OUTCOME-SENTRY-M0-DAWN-FEASIBILITY-001 — Directive SENTRY-M0-DAWN-FEASIBILITY-001
- Completed: 2026-08-24
- Verdict: BLOCKED
- Retrieval confidence: ADEQUATE
- Evidence level: E1_OBSERVED
- Upstream inspected: DAWN `a0c0b13c65f1b02a3416d846f6a0d331244eee9d` (`main`)

### Technical state discovered
SENTRY remains documentation-first with no application source, tests, dependency manifest, or runtime implementation. DAWN's current upstream is GPL-3.0-or-later and documents x86_64 Linux/Docker server deployment, but its current supported input and proactive surfaces do not provide the required SENTRY event boundary.

### Work performed
- Reconciled the accepted SENTRY Notion directive and current project scope.
- Inspected DAWN server deployment documentation, WebSocket protocol, tool-development guide, proactive-attention catalog/core, WebSocket message dispatch, satellite query path, MQTT callback path, system-context queue, and speech delivery path.
- Compared alternatives: WebSocket `text`/`satellite_query`, MQTT device relay, SAGE attention/telemetry, WebUI silent-observation test path, existing system-context injection, and custom DAWN tool registration.
- No SENTRY runtime code, dependency, or DAWN source was changed.

### Acceptance results
- Current DAWN upstream inspected: PASSED
- Supported x86/server deployment documented: PASSED (documentation evidence only)
- Minimal versioned SENTRY event implemented: BLOCKED by ingress boundary
- Event reaches DAWN as trusted environmental context: BLOCKED
- Assistant reasons from `person.entered`: BLOCKED
- Optional speech: BLOCKED, no qualifying event-to-reasoning path available
- Event-to-assistant flow reproducible: BLOCKED
- No webcam/perception scope introduced: PASSED
- No DAWN fork/vendor dependency created: PASSED
- Authority state and Notion update: PASSED
- Commit/push: PASSED (`157fb3e`)

### External surface findings
- WebSocket `text` and DAP2 `satellite_query` are documented and implemented as conversational text input. They would make the physical event appear as a user utterance.
- MQTT is subscribed for DAWN/OASIS device commands and selected telemetry/events. The generic device relay formats returned data as `[DEVICE DATA] Speak this information naturally to the user: ...` and pushes it into `INPUT_SOURCE_MQTT`, which becomes a normal user-role turn.
- SAGE attention is a fixed catalog of STAT/suit/component numeric or absence metrics. It can deliver an alert and optionally inject `[proactive alert] ...` into existing sessions, but it does not expose a SENTRY event ingress or an external reasoning trigger. `person.entered` is not in the catalog.
- `silent_observation` and `context_injection` are server-to-WebUI notifications. The test observation path is admin/debug-only and is a UI signal, not assistant grounding.
- `session_broadcast_system_message` and `pending_sysmsg_push` preserve system-role context, but only add context for a later turn and do not initiate an LLM turn.
- DAWN's supported custom-tool process requires source files, CMake registration, and build registration. That is a DAWN modification/fork boundary, explicitly excluded by the directive.

### Assumptions confirmed
- M0 is the current gate and no SENTRY runtime capability exists.
- DAWN is GPL-3.0-or-later; direct derivation or a linked custom tool would require an explicit licensing/architecture decision.
- Existing DAWN speech delivery is reachable from native proactive attention, but that path is downstream of DAWN-owned event generation and does not solve SENTRY event ingress.

### Assumptions disproven
- The current upstream WebSocket/MQTT/SAGE surfaces are sufficient by themselves for a trusted, externally supplied SENTRY physical event that autonomously starts reasoning.

### Risks / blockers
- Proceeding with WebSocket text or MQTT device relay would violate the event-provenance acceptance criterion.
- Modifying or forking DAWN would change the architecture and licensing decision and must be explicitly authorized.
- Docker and WSL are installed on the Windows host, but a live DAWN server was not started because the supported-boundary stop condition was reached first; runtime feasibility remains untested.

### Architect decision required
YES. Choose whether to authorize an explicit DAWN upstream change/maintained fork, evaluate another assistant foundation, or revise the M0 acceptance boundary. Webcam/perception work remains gated.

---

## OUTCOME-SENTRY-M0-CODEX-FEASIBILITY-001 — Directive SENTRY-M0-CODEX-FEASIBILITY-001
- Completed: 2026-08-24
- Verdict: PASS — bounded feasibility proof target-tested; awaiting Architect acceptance
- Retrieval confidence: ADEQUATE
- Evidence level: E3_TARGET_TESTED
- Codex version: `codex-cli 0.145.0`
- Authentication: `codex login status` reported `Logged in using ChatGPT`; the bridge removed `OPENAI_API_KEY` and `OPENAI_ADMIN_KEY` from each child process.
- Model: explicitly forced as `gpt-5.6-luna` for every invocation; no model switching or escalation occurred.

### Technical state discovered
The host has a supported noninteractive Codex CLI surface, OAuth ChatGPT credentials, and a bundled Python runtime at `C:\Users\sketc\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`. Official Codex documentation documents `codex exec` for scripts, `--ephemeral` for non-persisted rollout files, JSONL events for machine-readable processing, `--output-schema` for structured output, and saved CLI authentication reuse. Official GPT-5.6 Luna documentation confirms the model alias and effort levels `none`, `low`, `medium`, `high`, `xhigh`, and `max`.

### Work performed
- Implemented `tools/sentry_codex_bridge.py`, a single-event adapter with schema validation, explicit Luna model, effort selection, OAuth-only child environment, `--ephemeral`, read-only sandbox, schema-constrained JSON output, one timeout, no retry, no thread resume, and structured failure results.
- Implemented `tools/sentry_codex_response.schema.json` for stable downstream parsing.
- Used fresh bounded turns rather than persistent/resumable threads. This keeps event causality explicit and avoids an idle Codex worker.
- No webcam, perception, persistence, voice, DAWN, OpenClaw, hardware, or M1 implementation was added.

### Runtime acceptance results
- OAuth-authenticated local invocation without API key: PASSED. Two successful calls ran after removing the API-key variables from the child environment.
- Luna selection: PASSED. CLI invocation and returned bridge envelope both identify `gpt-5.6-luna`.
- Synthetic event grounding: PASSED. Event IDs `...0101` and `...0102` returned `event_type=person.entered`, `room_id=office`, `person_id=primary_user`, `understood=true`, and responses explicitly described environmental/physical context as not user speech.
- Parseable response: PASSED. Both calls satisfied the JSON Schema through `--output-schema` and were parsed from JSONL `agent_message` plus `turn.completed` usage.
- Independent second event: PASSED. A fresh ephemeral thread handled event `...0102` independently.
- Two Luna effort levels: PASSED. Low and high were selected without changing the model; returned `effort` matched the requested value.
- No repeated/background turns: PASSED. The adapter has no worker, timer, poll, retry, or resume path; after each run no `sentry_codex_bridge.py` Python process remained.
- Failure detection: PASSED. Missing event file returned `invalid_event_file` without a Codex call; a forced missing executable returned `codex_unavailable` without crashing the bridge.
- Idle behavior: PASSED by bounded design and process check. No invocation occurs without an explicit event file, and no bridge process remained during the post-run check. Subscription-wide idle billing cannot be independently measured from the CLI.
- Optional speech: NOT APPLICABLE. This directive tests the reasoning/tool layer only and excludes the voice stack.

### Measured per-turn usage
The JSONL `turn.completed` usage object is the available local measurement, not a claim about remaining ChatGPT plan quota:

| Turn | Model | Effort | Input | Output | Reasoning output |
|---|---|---:|---:|---:|---:|
| event `...0101` | `gpt-5.6-luna` | `low` | 19,100 | 80 | 0 |
| event `...0102` | `gpt-5.6-luna` | `high` | 19,100 | 139 | 55 |

The direct preliminary probes also succeeded at low and high effort, but the packaged bridge measurements above are the representative acceptance evidence. The CLI did not expose a subscription quota-before/after counter; future governance should use these per-turn token metrics plus available account analytics.

### Limitations / risks
- ChatGPT OAuth is proven on this trusted host, not as a general public or unattended service deployment. Codex credentials remain local secrets and the bridge must not be exposed to untrusted input.
- The proof uses the installed bundled Python runtime because the ordinary Windows `python` command is only a Microsoft Store alias. No third-party package was added.
- Codex CLI may initialize configured optional MCP servers unless disabled or absent; the packaged bridge uses `--ignore-user-config` and does not request tools, but it still depends on the installed CLI's local startup behavior.
- The model/provider selection is enforced by the invocation constant and CLI flag. The JSONL stream reports the explicit command's selected model through the bridge envelope, but does not provide a separate server attestation field.

### Architect decision required
YES. Accept or reject the bounded Codex/Luna event-to-reasoning boundary. If accepted, authorize the next SENTRY milestone with the Luna-only rule, default low/medium effort, justified high/xhigh/max effort, no idle calls, bounded context, duplicate suppression, hard call-rate limits, and observable usage metrics. Webcam/perception remains gated until acceptance.

---

## OUTCOME-SENTRY-M0-CODEX-CONTEXT-OPT-001 — Directive SENTRY-M0-CODEX-CONTEXT-OPT-001
- Completed: 2026-08-24
- Verdict: PASS — isolated runtime hardening target-tested; awaiting Architect acceptance
- Retrieval confidence: ADEQUATE for the bridge and runtime surface; jCodemunch was unavailable and narrow direct inspection was used
- Evidence level: E3_TARGET_TESTED
- Codex version: `codex-cli 0.145.0`
- Authentication: `codex login status` reported `Logged in using ChatGPT`; child processes removed `OPENAI_API_KEY` and `OPENAI_ADMIN_KEY`.
- Model: all four successful calls explicitly selected `gpt-5.6-luna`; all used low effort.

### Technical state discovered
The SENTRY root contains one applicable project instruction file, `AGENTS.md`. A repo-root Codex audit returned that exact path. Official Codex guidance states that project instructions are discovered from the project root down to the current directory. The isolated runtime was a fresh non-repository temporary directory with zero `AGENTS*` files, so it did not load SENTRY Authority instructions. `--ignore-user-config` was retained in both configurations.

### Measurements
| Call | Context | Input | Output | Reasoning |
|---|---|---:|---:|---:|
| 1 | Existing repo-root bridge, event `...0101` | 19,308 | 76 | 0 |
| 2 | Direct isolated runtime, event `...0101` | 18,266 | 103 | 21 |
| 3 | Repo-root instruction-source audit | 18,845 | 132 | 86 |
| 4 | Updated isolated bridge, event `...0102` | 18,223 | 80 | 0 |

The same-event reduction was 5.4%; the final bridge measurement was 5.6% below the original baseline. The observed practical floor is approximately 18.2k input tokens. The 50% reduction target was not reached, and no unsupported further optimization was attempted.

### Work performed
- Updated `tools/sentry_codex_bridge.py` to run each event in a fresh temporary cwd outside the repository.
- Added `--skip-git-repo-check` and copied the schema to an absolute local temporary path.
- Preserved one bounded ephemeral turn, read-only sandbox, OAuth-only child environment, explicit Luna, structured errors, and no worker/timer/retry/resume path.
- No M1/perception/product work was added.

### Acceptance results
- Repo-root baseline retained: PASSED
- Isolated same-event comparison: PASSED
- Authority `AGENTS.md` excluded from runtime reasoning cwd: PASSED
- Absolute schema path and structured output: PASSED
- Physical-event provenance and grounding: PASSED
- OAuth and explicit Luna: PASSED
- Four-call budget: PASSED, exactly four successful calls
- Failure handling and idle behavior: PASSED by bounded design and process checks
- M1 scope: PASSED, not started
- Notion/GitHub/Authority updates: PENDING at ledger-write time; completed before final handoff

### Limitations / risks
- The 5.4% to 5.6% reduction is measurable but modest, below the 50% target.
- The installed skills context warning remained in the isolated run; approximately 18.2k is an observed floor, not a theoretical minimum.
- Local CLI output does not expose subscription-wide quota or plan-wide idle billing.
- OAuth evidence remains trusted-host evidence; the bridge must not accept untrusted public input or expose credentials.
- Repository sync also found that the mandatory `PROJECT_GOAL.md` named by `AGENTS.md` is absent. Existing Authority state and accepted records were readable; the missing kernel file remains an open governance documentation gap and was not fabricated in this task.

### Architect decision required
YES. Accept or reject the isolated runtime hardening result. M1 webcam/perception remains separately gated and unauthorized.

---

## OUTCOME-SENTRY-REPO-RECOVERY-001 — Canonical checkout restored and verified
- Date: 2026-08-25
- Directive: `SENTRY-REPO-RECOVERY-001`
- Verdict: COMPLETE — repository integrity restored; M1 remains open
- Retrieval confidence: ADEQUATE for canonical repository and Authority state; original low-level share failure remains uncertain
- Evidence level: E3_TARGET_TESTED

### Technical state discovered
The Atlas parent share was reachable and stable across three repeated reads. The canonical `SENTRY` directory was absent during the initial inventory, with no visible SENTRY remnants or alternate `SENTRY*` entries to quarantine. Neighboring visible project directories were evidence-only directories rather than comparable Git checkouts, so no neighboring checkout corruption was inferred. The original disappearance mechanism remains unproven; no storage repair, migration, legacy pool path, or mergerfs operation was performed.

### Recovery and validation
- GitHub `refs/heads/main`: reconfirmed as `73b43f3398c0dc0738d23d389c2a79b48c5af29d`.
- Fresh isolated recovery clone: passed at `C:\Users\sketc\AppData\Local\Temp\sentry-recovery-20260824`.
- Canonical Atlas clone: restored at `\\atlas\\ATLAS\\100_ACTIVE\\Projects\\SENTRY`.
- Branch/origin: `main`; origin identifies `SketchOTP/SENTRY`; local `main` and `origin/main` match exactly.
- Authority kernel and project source/tests/docs: present.
- `git fsck --full`: passed, exit code 0, no reported errors.
- Existing automated suite: passed, 5/5 tests.
- Canonical reread/reopen check: passed across three reads with Git metadata and perception source present.
- Final working tree: clean.

### Acceptance boundary
Repository recovery is complete. M1 is not accepted: human-confirmed detection quality, multi-person tracking, dropout continuity, and controlled camera recovery remain outside this directive and must remain separately evidenced. M2 remains unauthorized.

---

## OUTCOME-SENTRY-M1-PERCEPTION-001 — Local perception implementation target-tested; live gate blocked
- Date: 2026-08-24
- Directive: `SENTRY-M1-PERCEPTION-001`
- Evidence level: E2_TARGET_TESTED; live criteria BLOCKED/NOT RUN
- Retrieval confidence: ADEQUATE for repository/host state; INSUFFICIENT for live camera qualification because the device could not be opened.

### Result
Implemented the smallest observation-only local service. It uses OpenCV HOG for person-only detection, a SENTRY-owned two-stage IoU tracker, and a size-one latest-frame buffer. It emits `online`, `degraded`, or `offline` observations and never treats camera failure as an empty room. The perception path contains no Codex/Luna invocation.

### Validation
- Python compilation: PASSED.
- Five deterministic unit tests: PASSED.
- Config validation, detector contract, multi-track stability, dropout retention, latest-frame dropping, and structured observation shape: PASSED.
- Unavailable-camera CLI: PASSED. Any/Media Foundation/DirectShow attempts produced `offline / camera_open_failed`, exit code 3, and `codex_luna_calls: 0`.
- Live visible-person detection, tracking, recovery, FPS/latency, resource measurements, and ten-minute soak: BLOCKED/NOT RUN. The NexiGo N60 FHD Webcam is enumerated but cannot be opened by OpenCV on this host.

### Selected stack and external discovery
OpenCV 4.5+ is Apache-2.0 and bundles the HOG default people detector coefficients. YOLOX is Apache-2.0 and ByteTrack is MIT, but their common deployment path requires separately sourced model artifacts and a larger runtime. The detector interface remains replaceable for a later measured YOLOX/ONNX comparison. CPU was selected because the adopted HOG path is CPU-only; NVIDIA adapters remain available for a future qualified backend.

### Files
`perception/sentry_perception.py`, `perception/config.example.json`, `tests/test_sentry_perception.py`, `requirements.txt`, `docs/M1_PERCEPTION.md`, `README.md`, and M1 task evidence.

### Decision boundary
M1 is not accepted. Restore camera access or authorize a replacement device, then rerun the actual-host gate. Do not begin M2.

### Governance correction
The earlier M0 context-optimization record stated that `.agent/PROJECT_GOAL.md` was absent. The M1 synchronization checked the live repository and confirmed that `.agent/PROJECT_GOAL.md` exists. The historical statement remains preserved; this entry is the superseding current-state correction.

---

## OUTCOME-SENTRY-M1-LIVE-QUALIFICATION-001 — Live quality gate returned to Architect
- Date: 2026-08-25
- Directive: `SENTRY-M1-LIVE-QUALIFICATION-001`
- Verdict: PARTIAL — **M1 NOT ACCEPTABLE — detector quality bottleneck**; camera recovery also remains unproven
- Retrieval confidence: ADEQUATE for canonical repository and live runtime; UNCERTAIN for exact per-frame human ground truth outside the operator-visible previews
- Evidence level: E5_OPERATIONALLY_OBSERVED

### Human-confirmed scene
- Windows Camera preview visibly showed one real seated person in the office scene, centered in the NexiGo N60 view.
- A later preview showed the operator intentionally covering the lens, establishing a real occlusion action, but the subsequent SENTRY timing was not sufficiently synchronized to accept that particular dropout as a controlled gate.
- No raw preview or overlay frame remains: the transient overlay was cleared after inspection and no image/video was added to the repository.

### Single-person detection and tracking
- 30-second SENTRY run: 271 observation rows; 238 rows contained person records (87.8%); maximum reported people was 3; track IDs were `1` through `14`.
- 90-second SENTRY run: 854 observation rows; maximum reported people was 6; track IDs were `1` through `29`; 295 track records were detector-visible and 12 was the maximum retained miss count.
- In the known one-person scene, simultaneous extra track records and rapid ID churn are material false-positive/identity-quality indicators. Exact research-grade per-frame false-positive labeling was not attempted; the evidence is already sufficient to reject stable office-presence adequacy.
- Stable real-person track: FAILED. The 30-second run changed IDs 13 times in a known one-person scene.

### Dropout and multi-person
- Short dropout continuity: NOT ACCEPTED. One synchronized attempt showed track `1` with two visible detections followed by predicted observations through miss count 12, but the physical occlusion timing and predicted box correspondence were not independently sufficient to establish the required detector-miss-versus-track-retention result.
- Live two-person behavior: BLOCKED. A second real person was not available; automated multi-track tests were not substituted.

### Camera failure/recovery
- Existing implementation remained online during a 90-second run; summary: 852 processed, 9.435 processed FPS, 19.391 ms median, 23.164 ms p95, 12 dropped frames, zero Luna calls.
- Controlled device interruption: BLOCKED/NOT RUN. `Disable-PnpDevice` returned `Generic failure`; `pnputil /restart-device` returned `Access is denied`. No physical disconnect/reconnect or administrative workaround was performed.
- Camera offline state, recovery, and no-false-empty-on-controlled-failure: NOT RUN. The service has no demonstrated reopen path from this directive.

### Required validation
- Existing automated tests: PASSED — 5/5.
- Real single-person detection: FAILED for acceptance adequacy due false-positive indicators and unstable outputs despite 87.8% non-empty observation rows.
- Stable real-person track: FAILED.
- Short dropout continuity: NOT RUN / NOT ACCEPTED.
- Live two-person behavior: BLOCKED.
- Camera offline state: BLOCKED.
- Camera recovery: BLOCKED.
- No false `empty` on failure: NOT RUN.
- At least 5 processed FPS: PASSED — 9.435 FPS in the 90-second run.
- Raw-frame persistence: PASSED — none in repository; transient overlay cleared.
- Runtime Codex/Luna calls: PASSED — 0.
- Working tree: PASSED — clean before record update.

### Decision boundary
Do not accept M1. Do not begin M2. The current HOG plus SENTRY IoU tracker is not acceptable for the observed office scene. Return to Architect for a separate detector-replan decision; do not silently add YOLOX, ByteTrack, or another stack.

---

## OUTCOME-SENTRY-M1-DETECTOR-REPLAN-001 — Open Model Zoo candidate blocked by generic OpenCV runtime
- Date: 2026-08-25
- Directive: `SENTRY-M1-DETECTOR-REPLAN-001`
- Verdict: BLOCKED — `person-detection-0202` provenance passed, but the pinned generic OpenCV DNN runtime cannot load the candidate
- Retrieval confidence: ADEQUATE for repository, upstream metadata, artifact checksums, and host runtime; live detector quality remains NOT RUN
- Evidence level: E3_TARGET_TESTED

### Model provenance
- Official Open Model Zoo `model.yml` identifies `person-detection-0202`, MobileNetV2-SSD, 512x512 BGR input, and output shape `1x1x200x7`.
- FP32 XML source: `https://storage.openvinotoolkit.org/repositories/open_model_zoo/2023.0/models_bin/1/person-detection-0202/FP32/person-detection-0202.xml`; 185,467 bytes; manifest SHA-384 `fc218405d14ca82811a239f841a90eb9f6e1a8d2e8269956471e79bfaba34f3f5ac7070e1d33aa5d2101460854b72a6a`; verified on host.
- FP32 BIN source: `https://storage.openvinotoolkit.org/repositories/open_model_zoo/2023.0/models_bin/1/person-detection-0202/FP32/person-detection-0202.bin`; 7,269,196 bytes; manifest SHA-384 `e807fab165c5327cf726eea6f5d70832dd4bbaec865d929b1ead67061759cf809debf0e43d53b23d612b4c3320eab578`; verified on host.
- Manifest license points to the Open Model Zoo Apache-2.0 license; official license text was retrieved.

### Runtime investigation
- Existing `opencv-python-headless==4.12.0.88` was tested without adding dependencies.
- `cv2.dnn.readNetFromModelOptimizer(xml, bin)` failed with `Backend (plugin) is not available: 'openvino'`.
- `cv2.dnn.readNet(bin, xml)` failed with the same error.
- The candidate therefore did not reach single-frame inference, output decoding, or live Stage A/B/C qualification.
- The attempted detector/config/test/docs changes were reverted. No OpenVINO Runtime, alternate OpenCV build, YOLOX, tracker change, or M2 work was introduced.

### Validation and decision boundary
- Existing HOG regression suite after revert: PASSED — 5/5.
- DNN candidate contract tests were exercised during the bounded implementation attempt, but are not retained because the production candidate cannot load in the authorized runtime.
- Model files remain outside Git under ignored canonical `perception-data/models/person-detection-0202/FP32/`.
- Runtime Codex/Luna calls: 0. Raw frames: none.
- Do not claim detector improvement or M1 acceptance. Return to Architect for a runtime decision; do not add a new inference runtime implicitly.

---

## OUTCOME-SENTRY-M1-DETECTOR-RUNTIME-001 — OpenVINO runtime path reproduced; live quality gate pending human confirmation
- Date: 2026-08-26
- Directive: `SENTRY-M1-DETECTOR-RUNTIME-001`
- Verdict: PARTIAL — runtime/model integration and automated checks passed; live Stage A/B/C acceptance is not yet established
- Retrieval confidence: ADEQUATE for repository, host, package, model, and integration state; UNCERTAIN for human presence during telemetry-only camera runs
- Evidence level: E4_REGRESSION_PROTECTED for the implementation; live quality remains NOT ACCEPTED

### Host, package, and model
- Host: Windows 11 x64, AMD Ryzen 7 5800XT, Python 3.12.10.
- Isolated environment: `.venv` with `openvino==2026.3.1`, `opencv-python-headless==4.12.0.88`, `psutil==7.0.0`, transitive `numpy==2.2.6`, and `openvino-telemetry==2025.2.0`.
- OpenVINO `Core().available_devices`: `CPU`, `GPU.0`, `GPU.1`; CPU selected for deterministic first qualification.
- The existing FP32 XML/BIN artifacts remain outside Git and matched the recorded Open Model Zoo SHA-384 checksums.

### Smoke and implementation
- `Core.read_model` and CPU `compile_model` passed for `person-detection-0202`.
- Bounded zero-array inference passed and returned `float32` output shape `(1, 1, 200, 7)`.
- `OpenVINOPersonDetector` now implements the existing `Detector` contract, performs BGR-to-NCHW preprocessing, filters label `0` and configured confidence, converts normalized boxes to image pixels, and fails explicitly for missing, corrupt, incompatible, or unavailable runtime/model paths.
- The existing SENTRY IoU tracker, latest-frame buffer, camera health semantics, and no-Codex/Luna perception boundary were not changed.

### Automated validation
- Focused and existing suite: PASSED — 9/9.
- Python compilation and `git diff --check`: PASSED.
- Artifact checksum recheck: PASSED.
- Raw-frame persistence: NONE.
- Runtime Codex/Luna calls: 0.

### Live telemetry, not acceptance evidence
- First 30-second camera run: online, 1280x720 at 15 FPS, 250 captured / 249 processed, 8.22 processed FPS, 8.558 ms median, 12.201 ms p95, 0 dropped frames. Telemetry showed 206/254 rows with a visible track, 9 visible track IDs, and 9 rows with two visible tracks.
- Second 30-second camera run: online, 1280x720 at 15 FPS, 257 captured / 255 processed, 8.414 processed FPS, 9.275 ms median, 15.493 ms p95, 1 dropped frame. Telemetry showed 65/259 rows with a visible track, 5 visible track IDs, and 1 row with two visible tracks.
- These runs were not operator-confirmed one-person segments. Their conflicting presence statistics cannot establish Stage A detection quality, false positives, or false negatives.
- Stage A human-confirmed detection: BLOCKED pending operator-confirmed subject presence.
- Stage B unchanged-tracker qualification: NOT RUN.
- Stage C synchronized dropout: NOT RUN.
- Ten-minute soak: NOT RUN because live quality stages have not passed.
- Camera failure/recovery: NOT RUN under this directive, as explicitly outside the primary objective.

### Decision boundary
The authorized runtime path is technically usable and the detector replacement is ready for proper live qualification. Do not accept M1 or claim detector adequacy until a human-confirmed one-person segment is completed. Do not change the tracker or add another runtime.

---

## OUTCOME-SENTRY-M1-OPENVINO-LIVE-001 — Confirmed one-person quality failure
- Date: 2026-08-26
- Directive: `SENTRY-M1-OPENVINO-LIVE-001`
- Verdict: PARTIAL — **DETECTOR QUALITY FAILURE**; Architect decision required before further M1 qualification
- Retrieval confidence: ADEQUATE for repository, runtime, telemetry, and operator markers
- Evidence level: E5_OPERATIONALLY_OBSERVED

### Pre-live gates
- Working tree was clean before live operation, local `main` matched `origin/main` at `ec4a2f3af1f8ad245d3d0c0f8d41dc528d97d438`, the FP32 XML/BIN checksums passed, and the existing automated suite passed 9/9.
- Runtime remained the committed `openvino==2026.3.1` CPU path with no production changes. Runtime Codex/Luna calls remained 0.

### Operator-confirmed markers
- Stage A marker: `CONFIRMED_EMPTY — START`, recorded at `2026-08-26T15:07:31.1859602Z`; an extended confirmed-empty run provided approximately 20.6 seconds of online telemetry.
- Stage B marker: `CONFIRMED_ONE_PERSON — START`, recorded at `2026-08-26T15:09:55.9480344Z`.
- Operator end confirmation: `CONFIRMED_ONE_PERSON — END — CONTINUOUS`; the operator confirmed the subject remained continuously visible for the recorded segment.
- The runner captured exact start-marker timestamps; the end confirmation arrived as a chat marker after process completion, and its transport timestamp was not exposed in the telemetry file. The continuous operator confirmation is explicit.
- No raw frames or video were persisted.

### Stage A — confirmed empty
- 205 processed online observations.
- 205 zero-person, 0 one-person, 0 multi-person observations.
- Maximum false-person confidence: none; no sustained false-person period.
- 8.095 processed FPS; 0 dropped frames.
- Result: PASSED.

### Stage B — confirmed one person and unchanged tracker
- Online telemetry span: approximately 83.9 seconds; 827 processed observations; 9.154 processed FPS; median/p95 processing latency 9.518/15.753 ms; 1 dropped frame.
- Detector-visible observations: 480 zero detections, 318 exactly one detection, and 29 more-than-one detections; maximum simultaneous detector boxes 2.
- Detector-visible detection rate while the person was continuously confirmed visible: 347/827 observations, 42.0%.
- Duplicate/multi-detection observations were present in 29/827 observations, 3.5%; no persistent second physical person was confirmed.
- Unchanged tracker: first visible ID `1`, final visible ID `19`, 19 unique IDs, 32 visible-ID-set changes, maximum 3 active tracker records, 265 predicted/missed tracker records, and maximum missed count 12.
- Result: FAILED. The detector missed the continuously visible subject in a large fraction of observations and produced repeated ID churn/extra tracker records. This is a detector-quality failure; tracker rework was not attempted.

### Stop boundary and remaining gates
- Stage C synchronized dropout: NOT RUN because Stage B failed.
- Ten-minute soak: NOT RUN because Stage B failed.
- Live two-person behavior: BLOCKED — no second person available; automated tests were not substituted.
- Camera offline/recovery: NOT RUN under this directive; remains a separate final M1 gate and no privileged device manipulation was attempted.
- Recommendation: **DETECTOR REPLAN**. Do not accept M1, do not modify the tracker in this result, and do not begin M2.

---

## OUTCOME-SENTRY-M1-DETECTOR-CALIBRATION-001 — No acceptable confidence operating point
- Date: 2026-08-26
- Directive: `SENTRY-M1-DETECTOR-CALIBRATION-001`
- Verdict: PARTIAL — **DETECTOR CALIBRATION FAILED — REPLAN MODEL**
- Retrieval confidence: ADEQUATE for repository, runtime, implementation, model artifacts, operator markers, and live metadata; bounding-box visual sanity is NOT ACCEPTED because the installed OpenCV wheel is headless
- Evidence level: E5_OPERATIONALLY_OBSERVED

### Implementation and pre-live gates
- The existing OpenVINO `person-detection-0202` model, `openvino==2026.3.1`, CPU device, preprocessing, camera path, size-one buffer, existing IoU tracker, and production confidence threshold remained unchanged.
- Added only `OpenVINOPersonDetector.detect_raw()` plus metadata-only calibration capture/evaluation. Raw candidates were decoded through the existing inference/box path, stored only as timestamps, frame sequence, candidate confidences/boxes, and inference timing, and never entered the production tracker. No raw image or video was persisted.
- Existing and focused tests passed 11/11. FP32 XML/BIN checksums remained valid. Working tree was clean and local `main` matched `origin/main` before live capture.

### Operator-confirmed markers and segment coverage
- Stage A user marker: `CONFIRMED_EMPTY — START`; runner marker: `CONFIRMED_EMPTY` at `2026-08-26T16:18:50.151051+00:00`; runner end: `CONFIRMED_EMPTY_END` at `2026-08-26T16:19:25.924405+00:00`.
- Stage A: 303 online observations; captured timestamp span 30.639 seconds. Operator confirmed nobody was visible.
- Stage B user marker: `CONFIRMED_ONE_PERSON — START`; runner marker: `CONFIRMED_ONE_PERSON` at `2026-08-26T16:21:28.148642+00:00`; runner end: `CONFIRMED_ONE_PERSON_END` at `2026-08-26T16:22:33.820060+00:00`; operator then confirmed `CONFIRMED_ONE_PERSON — END — CONTINUOUS`.
- Stage B: 599 online observations; captured timestamp span 60.559 seconds. The operator confirmed exactly one person remained continuously visible for the full segment.

### Complete offline threshold sweep
All rows below were computed from the same raw candidate files; no camera rerun was performed for individual thresholds.

| Threshold | Empty any detection | Empty max | Empty longest false-positive run | One-person any detection | Zero | Exactly one | Multi | Duplicate rate | One-person max | Longest miss | Longest duplicate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.10 | 100.000% | 6 | 303 / 30.749 s | 100.000% | 0 | 0 | 599 | 100.000% | 7 | 0.000 s | 60.670 s |
| 0.15 | 26.733% | 2 | 14 / 1.438 s | 100.000% | 0 | 0 | 599 | 100.000% | 5 | 0.000 s | 60.670 s |
| 0.20 | 0.660% | 1 | 1 / 0.111 s | 100.000% | 0 | 11 | 588 | 98.164% | 3 | 0.000 s | 42.798 s |
| 0.25 | 0.000% | 0 | 0 / 0.000 s | 100.000% | 0 | 108 | 491 | 81.970% | 3 | 0.000 s | 37.951 s |
| 0.30 | 0.000% | 0 | 0 / 0.000 s | 99.332% | 4 | 212 | 383 | 63.940% | 2 | 0.320 s | 20.750 s |
| 0.35 | 0.000% | 0 | 0 / 0.000 s | 98.331% | 10 | 346 | 243 | 40.568% | 2 | 0.399 s | 2.960 s |
| 0.40 | 0.000% | 0 | 0 / 0.000 s | 96.661% | 20 | 515 | 64 | 10.684% | 2 | 1.199 s | 0.911 s |
| 0.45 | 0.000% | 0 | 0 / 0.000 s | 89.149% | 65 | 532 | 2 | 0.334% | 2 | 2.239 s | 0.111 s |
| 0.50 | 0.000% | 0 | 0 / 0.000 s | 73.289% | 160 | 439 | 0 | 0.000% | 1 | 6.863 s | 0.000 s |

### Confidence distributions and decision
- Empty raw candidates: p50 `0.031729`, p75 `0.040432`, p90 `0.070170`, p95 `0.107720`, max `0.233231`.
- One-person raw candidates: p50 `0.058726`, p75 `0.112728`, p90 `0.323212`, p95 `0.489522`, max `0.943762`.
- Threshold `0.20` meets the empty false-positive rate criterion but creates persistent duplicate/multi-box evidence in the one-person segment. Threshold `0.40` is the highest-recall candidate near the person gate at 96.661%, but 10.684% of observations are duplicates and the longest duplicate run is 0.911 seconds. Threshold `0.45` reduces duplicates to 0.334% but fails person recall at 89.149%. No tested threshold passes the required separation.
- The transient overlay check was attempted at `0.40` but failed because `opencv-python-headless` does not implement `cv2.imshow`. Bounding-box sanity is therefore NOT ACCEPTED; no image was retained. The count-based failure remains decisive.

### Acceptance boundary
- Detector calibration: FAILED.
- Production threshold adoption: NOT AUTHORIZED and not performed.
- Unchanged tracker diagnostic: NOT RUN because calibration failed.
- Synchronized dropout: NOT RUN.
- Ten-minute soak: NOT RUN.
- Live two-person behavior: BLOCKED — no second person available.
- Camera recovery: NOT RUN under this directive; remains a separate M1 gate.
- Runtime Codex/Luna calls: 0.

### Recommendation
Return to Architect with **REPLAN MODEL**. Preserve `person-detection-0202` and this negative calibration evidence. Do not change the tracker or implement `person-detection-0303` until separately authorized.
