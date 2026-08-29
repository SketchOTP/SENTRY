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

---

## OUTCOME-SENTRY-M1-DETECTOR-0303-001 — Confirmed one-person quality failure
- Date: 2026-08-26
- Directive: `SENTRY-M1-DETECTOR-0303-001`
- Verdict: PARTIAL — **0303 DETECTOR QUALITY FAILURE**
- Retrieval confidence: ADEQUATE for repository, upstream provenance, runtime, model artifacts, decoding, tests, performance, operator markers, and live metadata
- Evidence level: E5_OPERATIONALLY_OBSERVED for the operator-confirmed empty and continuous-one-person segments; bounding-box sanity was NOT ACCEPTED because no candidate box existed in the one-person segment

### Implementation and provenance
- Replaced only the 0202-specific decoder/configuration path with Open Model Zoo `person-detection-0303` through the existing `openvino==2026.3.1` CPU runtime. The NexiGo capture path, native 1280x720/15 FPS request, size-one latest-frame buffer, raw-candidate diagnostic path, detector contract, and unchanged SENTRY IoU tracker were preserved.
- Official FP32 XML source: `https://storage.openvinotoolkit.org/repositories/open_model_zoo/2023.0/models_bin/1/person-detection-0303/FP32/person-detection-0303.xml`; size 1,119,623 bytes; SHA-384 `a3d4b43461bcd5a8d3740a093d069a828d494b23ef4758fb531b9174d5ad0a827da7baf7a46f75d61092563cbab82cde`; verified on host.
- Official FP32 BIN source: `https://storage.openvinotoolkit.org/repositories/open_model_zoo/2023.0/models_bin/1/person-detection-0303/FP32/person-detection-0303.bin`; size 9,279,356 bytes; SHA-384 `0f74ec88ff3667e272a70a245edfff86048fe7de15f2deb7a4a0796f6b8aa870f08f4d1b0867f2d3b175204633f61805`; verified on host.
- The official manifest and README identify Apache-2.0 provenance, MobileNetV2 with ATSS, BGR input `[1,3,720,1280]`, absolute-pixel `boxes (N,5)`, and `labels (N,)` with person label `1`. Runtime inspection matched those semantics: zero-array inference returned `boxes (22,5)` and `labels (22,)`.
- Model files remain outside Git under ignored canonical `perception-data/models/person-detection-0303/FP32/`. No raw frame or video was persisted.

### Pre-live performance
- Short native-camera CPU check: DirectShow, 1280x720, 107 captured / 105 processed, 6.852 processed FPS, 79.056 ms median and 114.636 ms p95 processing latency, 1 dropped frame, camera online, zero Codex/Luna calls. This exceeded the 5 FPS stop boundary; no ten-minute soak was run after quality failure.

### Operator-confirmed live calibration
- Stage A user marker: `CONFIRMED_EMPTY — START`; runner marker `2026-08-26T19:13:21.697481+00:00`; 279 online observations over 30.863 seconds; operator-confirmed empty; zero raw candidates at every threshold from `0.10` through `0.90`; no false-person detections. **PASSED**.
- Stage B user marker: `CONFIRMED_ONE_PERSON — START`; runner marker `2026-08-26T19:15:44.376944+00:00`; 588 online observations over 60.91 seconds; operator confirmed `CONFIRMED_ONE_PERSON — END — CONTINUOUS`; one person was continuously visible; zero raw candidates at every threshold from `0.10` through `0.90`. **FAILED**.
- Metadata-only evidence files: `perception-data/runtime/m1-0303-calibration-empty-20260826.jsonl` and `perception-data/runtime/m1-0303-calibration-one-person-20260826.jsonl`; raw camera frames and video were not written.

### Threshold table from the same raw outputs
All 17 tested thresholds (`0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90`) produced the same result:

| Threshold | Empty FP observations | One-person recall | Exactly one | Multi | Longest false-positive run | Longest miss run | Longest duplicate run |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.10–0.90, each 0.05 | 0/279 (0.000%) | 0/588 (0.000%) | 0/588 (0.000%) | 0/588 (0.000%) | 0.000 s | 60.910 s | 0.000 s |

- Bounding-box sanity: **NOT ACCEPTED**. The one-person segment yielded no candidate boxes to inspect; no visual artifact was retained.
- Tracker stage: **NOT RUN** because detector calibration failed. Synchronized dropout: **NOT RUN**. Ten-minute soak: **NOT RUN**. Live two-person behavior: **BLOCKED** — no second person available. Camera recovery: **NOT RUN** and remains a separate M1 gate.
- Automated tests: **11/11 PASSED**. Py-compile: **PASSED**. Git fsck: **PASSED**. Runtime Codex/Luna calls: `0`.

### Acceptance boundary
- Model provenance/checksums: PASSED.
- OpenVINO load/compile/output semantics: PASSED.
- CPU performance floor: PASSED for short check.
- Confirmed-empty false-positive gate: PASSED.
- Confirmed-one-person detection gate: FAILED decisively.
- Directive stop condition: `STOP — 0303 DETECTOR QUALITY FAILURE`.

### Recommendation
Return to Architect with **DETECTOR REPLAN**. Do not modify the tracker, switch runtime/device/precision, add another detector candidate, or begin M2 from this result.

---

## OUTCOME-SENTRY-M1-0303-DECODER-RECONCILE-001 — Decoder bug confirmed; corrected 0303 still fails quality
- Date: 2026-08-26
- Directive: `SENTRY-M1-0303-DECODER-RECONCILE-001`
- Verdict: PARTIAL — **DECODER BUG CONFIRMED — 0303 STILL FAILS QUALITY**
- Retrieval confidence: ADEQUATE for repository, upstream adapter semantics, runtime, model outputs, decoder, tests, performance, and operator-confirmed live metadata
- Evidence level: E5_OPERATIONALLY_OBSERVED for the operator-confirmed raw and corrected calibration segments

### Upstream discrepancy and raw investigation
- Official `accuracy-check.yml` selects `class_agnostic_detection`, scale `[0.00078125, 0.0013888888]`, `resize_prediction_boxes`, NMS overlap `0.6`, and clipping.
- The official `ClassAgnosticDetectionAdapter` retains rows where `pred[:, -1] > 0.0`, scales the first four values, assigns every retained row label `1`, and does not inspect the companion `labels` tensor.
- Previous SENTRY decoding required `int(label) == 1` and treated the 0303 boxes as final camera pixels. That contradicted the reference selection semantics.
- Operator-confirmed raw run marker: `CONFIRMED_ONE_PERSON` at `2026-08-26T19:42:57.764666+00:00`; 149 online observations over approximately 20.3 seconds. Raw output contained 1,474 positive-confidence rows, 339 rows with confidence >= `0.10`, maximum confidence `0.458353`, coordinate range `0.0` to `1205.41333`, and all companion labels were `0`. The old SENTRY decoder produced zero candidates in every observation.
- Highest-confidence raw box: `[343.841705, 54.877533, 1034.042236, 716.717285, 0.458353]`, label `0`, with similarly shaped high-confidence rows around the confirmed subject. No raw frame or video was retained.

### Correction
- Added metadata-only `infer_raw_outputs()` for the investigation helper; it exposes tensors to diagnostic code without changing the detector contract or sending raw candidates to the tracker.
- Reconciled 0303 decoding to positive box confidence, ignored companion labels for class selection, explicit model-domain normalization and resize reconstruction, clipping, and deterministic class-agnostic NMS at `0.6`.
- Added focused tests for label-agnostic selection, non-positive confidence rejection, coordinate reconstruction, clipping, NMS, and malformed output. The existing tracker, camera, buffer, runtime, device, precision, and production threshold remain unchanged.

### Corrected live calibration
- Confirmed-empty runner marker: `CONFIRMED_EMPTY` at `2026-08-26T20:07:48.797739+00:00`; 181 online observations over a 29.969-second captured timestamp span. At threshold `0.45`, false positives were `0/181`; at `0.40`, false positives were `4/181` (2.21%); lower thresholds had sustained duplicate false detections, including 12 simultaneous boxes at `0.10`.
- Confirmed-one-person runner marker: `CONFIRMED_ONE_PERSON` at `2026-08-26T20:23:10.311140+00:00`; operator later supplied `CONFIRMED_ONE_PERSON — END — CONTINUOUS`; 556 online observations over a 56.863-second captured timestamp span.
- At threshold `0.45`, one-person detection recall was `134/556` (24.10%), with no duplicate observations. At `0.40`, recall was `270/556` (48.56%), with `2/556` multi-detection observations (0.36%), while the matched empty false-positive rate was 2.21%. At `0.35`, recall was 79.32% and duplicate rate 3.96%; the empty segment remained materially false-positive. No threshold met empty FP <=1%, one-person recall >=95%, and duplicate control.
- The corrected result is therefore not a tracker finding. Tracker qualification, synchronized dropout, ten-minute soak, live two-person behavior, and camera recovery were not run.

### Performance and boundaries
- Corrected-decoder short regression: 101 captured / 95 processed, 6.173 processed FPS, 87.893 ms median and 132.416 ms p95 processing latency, 5 dropped frames, CPU path, RSS 162.6 MB to 268.4 MB, camera online, zero Codex/Luna calls. The >=5 FPS floor passed; no ten-minute soak was justified after the quality stop.
- Automated tests: **15/15 PASSED**. Model artifacts remained checksummed and outside Git. Raw-frame persistence: NONE. Live two-person behavior: BLOCKED because no second person was available. Camera recovery: NOT RUN and remains a separate M1 gate.

### Acceptance boundary and recommendation
- Previous 0303 failure was confounded by the decoder label gate, so it is superseded as a final model-quality conclusion.
- The corrected decoder is justified and target-tested, but 0303 still fails the required live empty/person separation in the tested office scene.
- Recommendation: **DETECTOR REPLAN**. Do not modify the tracker, runtime/device/precision, camera path, or begin M2 without a new Architect decision.

---

## OUTCOME-SENTRY-CONVERGENCE-RTDETR-PRESENCE-STATE-001-PRELIVE — Temporal room-state layer ready for labeled qualification
- Date: 2026-08-27
- Directive: `SENTRY-CONVERGENCE-RTDETR-PRESENCE-STATE-001`
- Verdict: PRE-LIVE GATE PASSED; room-state qualification not yet run
- Retrieval confidence: ADEQUATE for current repository, formal scope, retained RT-DETR integration, and state-layer implementation
- Evidence level: E4_REGRESSION_PROTECTED for deterministic state behavior; no E5 live state evidence yet

### Audit-driven correction
- The Architect superseded the planned RT-DETR per-frame detector benchmark. RT-DETRv2 R18 remains an uncommitted `IMPLEMENTED_UNVERIFIED` candidate input to the actual binary room-state metric.
- Current direct OAuth-authenticated Codex/Luna reasoning wording is authoritative; DAWN feasibility material remains historical/reference only.

### Implementation
- Added `perception/presence_state.py` with only `empty`, `occupied`, `degraded`, and `offline` state, timestamp-based hysteresis, binary human evidence, source-failure precedence, and metadata-only luminance/contrast measurement.
- Configured initial policy: one second entry confirmation, one second entry evidence-gap tolerance, and 15 second absence grace. Duplicate detections do not create multiple authoritative occupants.
- Structured observations now include room state, transition, detector-evidence flag, and optional image-quality metrics. Added metadata-only `tools/m1_presence_state_qualification.py` for sequential operator-labeled live segments.
- No detector, model, runtime, precision, device, camera, tracker, dependency, threshold, persistence, event, identity, API, voice, or M2 behavior was changed.

### Pre-live validation
- RT-DETR checkpoint SHA-256 remains `d18309d0d7ea57048138885c4c6ecfcb1e24506fc6153b94ad484f8ab62c7115`; ignored OpenVINO IR files remain present and are not tracked.
- Existing RT-DETR/OpenVINO equivalence evidence remains preserved in prior Authority history.
- Automated suite: **33/33 PASSED**. Git diff check: PASSED. Raw-frame persistence: NONE. Runtime Codex/Luna perception calls: `0`.
- Live room-state stages A-F: NOT RUN. No operator-labeled marker has been reused from an earlier detector-specific directive.

### Next boundary
- Request a fresh `CONFIRMED_EMPTY — START` marker for Stage A. Stop at the first decisive state-level failure and do not model-shop automatically.

---

## OUTCOME-SENTRY-CONVERGENCE-RTDETR-PRESENCE-STATE-001-STAGE-A — Confirmed-empty room-state failure
- Date: 2026-08-27
- Directive: `SENTRY-CONVERGENCE-RTDETR-PRESENCE-STATE-001`
- Verdict: **STATE FAILURE — FALSE HUMAN EVIDENCE**
- Retrieval confidence: ADEQUATE for the current RT-DETR/state implementation and this fresh metadata-only run
- Evidence level: E5_OPERATIONALLY_OBSERVED for the operator-confirmed-empty segment; later live stages not run

### Operator-confirmed segment
- Ground-truth marker: `CONFIRMED_EMPTY — START`; the qualification runner recorded `2026-08-27T15:35:50.088767+00:00`. Runner end marker: `2026-08-27T15:36:50.236329+00:00`.
- The operator-confirmed room was empty for the labeled interval. No raw image or video was retained.
- Camera startup was degraded for 5 observations, then online for 118 observations. The online interval began at `2026-08-27T15:36:25.362821+00:00`, making the usable online interval approximately 24.9 seconds.

### Room-state evidence
- State observations: `empty` 40/118 online; `occupied` 78/118 online; startup `degraded` 5/123 total. Correct empty state was approximately 33.9% of online observations, far below the 95% requirement.
- Transitions: `empty->degraded` at `15:36:19.433188Z`; `degraded->empty` at `15:36:25.362821Z`; false `empty->occupied` at `15:36:27.653707Z`; `occupied->empty` at `15:36:43.447774Z`.
- The false occupied interval lasted approximately 15.8 seconds, consistent with the configured 15-second absence grace after candidate evidence stopped.

### Detector metadata
- Eight online observations contained positive candidate evidence. Candidate count was one on six observations and two on two observations; the two-person output is duplicate/phantom evidence in a confirmed-empty room.
- Reported candidate confidences ranged from `0.5315` to `0.8581`. This was not isolated low-confidence noise: the positives were sufficient to create an authoritative false occupied state.
- Performance summary: 239 captured, 118 processed online (plus 5 startup observations), 120 dropped, 3.869 processed FPS, 175.113 ms median and 302.089 ms p95 processing latency. The 5 FPS runtime floor was not met in this run, but the decisive failure was false human evidence.
- Post-run automated regression: **34/34 PASSED**. The additional test coverage is retained; the pre-live record's earlier 33/33 count reflects the suite at that earlier checkpoint.
- Runtime Codex/Luna calls: `0`. Raw-frame persistence: `NONE`.

### Acceptance boundary
- Stage A failed the `>=95%` empty-state correctness requirement and the no-persistent-phantom-occupancy requirement.
- Stages B-F were not run. No threshold sweep, detector change, tracker change, camera manipulation, or commit/push was authorized from this result.
- Recommendation to Architect: preserve the implemented-unverified RT-DETR/state work and decide the next bounded action. Do not accept or commit RT-DETR as the V0.1 presence backend.

---

## OUTCOME-SENTRY-CONVERGENCE-0202-PRESENCE-STATE-001-PRE-LIVE — Restore 0202 and pass pre-live gate
- Date: 2026-08-27
- Directive: `SENTRY-CONVERGENCE-0202-PRESENCE-STATE-001`
- Verdict: **PRE-LIVE GATE PASSED — awaiting fresh Stage A marker**
- Retrieval confidence: ADEQUATE for the historical 0202 implementation, current generic state layer, artifacts, and host runtime
- Evidence level: E4_REGRESSION_PROTECTED for source/config restoration and automated checks; operator-labeled room-state evidence is NOT RUN

### Working-tree recovery
- The complete pre-existing tracked diff was preserved as `perception-data/runtime/recovery-20260827/working-tree.patch`; status and diff-stat records plus copies of all untracked state files are in the same ignored canonical recovery directory.
- RT-DETR-specific active production source/config/tests/tooling were removed by restoring the detector/test surfaces from historical commit `ec4a2f3`. The generic `presence_state.py`, `test_presence_state.py`, and room-state runner were retained. Ignored RT-DETR model artifacts remain outside Git and were not deleted.

### Restored 0202 and checks
- `OpenVINOPersonDetector` and its contract were restored from `ec4a2f3`; config now selects `openvino_person_detection_0202` with threshold `0.40`, CPU execution, and the existing FP32 paths.
- The 0202 XML SHA-384 is `fc218405d14ca82811a239f841a90eb9f6e1a8d2e8269956471e79bfaba34f3f5ac7070e1d33aa5d2101460854b72a6a`; the BIN SHA-384 is `e807fab165c5327cf726eea6f5d70832dd4bbaec865d929b1ead67061759cf809debf0e43d53b23d612b4c3320eab578`; both match the recorded Authority values.
- Generic timestamp-based `empty`/`occupied`/`degraded`/`offline` state logic and metadata-only luminance/contrast diagnostics remain active. No persistence, sessions, semantic events, API, identity, enhancement, or M2 behavior was added.

### Automated and performance gates
- Full `.venv` suite: **24/24 PASSED**. `git diff --check`: **PASSED**. Config validation: **PASSED**.
- Short local camera gate: **PASSED** — DirectShow, 1280x720/15 FPS, 126 captured / 121 processed, 5.962 processed FPS, 24.776 ms median, 29.117 ms p95, 4 dropped frames, online throughout. Runtime Codex/Luna calls: `0`; raw frames: `NONE`.
- Fresh operator-labeled live room-state evidence: **NOT RUN**. Request only `CONFIRMED_EMPTY — START` next; earlier detector-specific markers are not reusable.

---

## OUTCOME-SENTRY-CONVERGENCE-0202-PRESENCE-STATE-001-STAGE-A — Confirmed-empty room-state pass
- Date: 2026-08-27
- Directive: `SENTRY-CONVERGENCE-0202-PRESENCE-STATE-001`
- Verdict: **PASSED — confirmed-empty room-state gate**
- Retrieval confidence: ADEQUATE for the restored 0202 path, state layer, and fresh labeled segment
- Evidence level: E5_OPERATIONALLY_OBSERVED for the fresh operator-confirmed-empty interval

### Evidence
- Fresh marker: `CONFIRMED_EMPTY — START` at `2026-08-27T16:40:26.042108+00:00`; runner end marker at `2026-08-27T16:41:12.519343+00:00`.
- Total observations: 237. Camera startup produced 7 `degraded` observations; 230 online observations were usable for the labeled empty interval.
- Authoritative room state: `empty` 230/230 usable observations (`100%`); `occupied` 0; no false `empty->occupied` transition; no persistent phantom occupancy.
- Detector evidence: 0 positive observations; 0 multi-candidate observations; maximum candidate count 0.
- Performance: 233 captured / 230 processed online, 7.592 processed FPS, 28.307 ms median and 48.788 ms p95 processing latency, 2 dropped frames, DirectShow 1280x720/15 FPS, camera online at completion.
- Raw frames: none. Runtime Codex/Luna calls: `0`.

### Boundary
- Stage A meets the required >=95% correct-empty criterion and no-phantom criterion. Stages B-F remain NOT RUN. Request a new operator marker `CONFIRMED_ENTRY — START` after the operator begins outside the camera view.

---

## OUTCOME-SENTRY-UBUNTU-PLATFORM-MIGRATION-001 — Ubuntu pre-live baseline
- Date: 2026-08-28
- Directive: `SENTRY-UBUNTU-PLATFORM-MIGRATION-001`
- Verdict: **UBUNTU PLATFORM BASELINE QUALIFIED**
- Retrieval confidence: ADEQUATE for the Atlas checkout, Ubuntu host, V4L2 device, 0202/OpenVINO runtime, state implementation, and Codex/Luna bridge.
- Evidence level: E4_REGRESSION_PROTECTED for source/config/tests/runtime reproduction; E5_OPERATIONALLY_OBSERVED for the bounded Linux camera/inference smoke and OAuth bridge proof. This is not Ubuntu M1 occupancy acceptance.

### Repository and preservation
- The canonical checkout is `/srv/ATLAS/100_ACTIVE/Projects/SENTRY` on the Atlas share, reached from Ubuntu through the authenticated user SFTP mount. Branch `main`, local HEAD, and `origin/main` are all `f5ca399dab2b53d90792de1039b519d129bf89dd`.
- The pre-existing dirty tree was not reset or overwritten. Complete diff/status/untracked state was preserved before edits under ignored canonical `perception-data/runtime/recovery-ubuntu-20260828/`. No unknown material was deleted.

### Ubuntu host/runtime
- Ubuntu 24.04.4 LTS, Linux 7.0.0-30-generic, x86_64, hostname `atlas-desktop`, AMD Ryzen 7 5800XT, 62 GiB RAM. NVIDIA GPUs are inventoried but not used; OpenVINO CPU remains active.
- Python 3.12.3; `opencv-python-headless==4.12.0.88`; `openvino==2026.3.1`; `psutil==7.0.0`; OpenCV reports Linux V4L/V4L2 support; OpenVINO devices are `CPU`, `GPU.0`, `GPU.1`.
- The standard Ubuntu `python3.12-venv` support package was installed because it was absent; no project dependency version was changed.

### Camera and model
- The NexiGo N60 is identified at stable `/dev/v4l/by-id/usb-webcamvendor_NexiGo_N60_FHD_Webcam_Jan_29_2024-10:32:28-N60-video-index0`; the device is `uvcvideo`, user ACL access passed, and V4L2 capability evidence shows MJPEG 1280x720 at 15 FPS.
- The minimal camera adaptation adds explicit `v4l2`, optional stable `device_path`, optional measured `fourcc`, Linux auto-backend selection, read-back of actual FOURCC, and retains numeric-index fallback. The tracker/state/model path is unchanged.
- 0202 FP32 XML/BIN SHA-384 checksums remain `fc218405d14ca82811a239f841a90eb9f6e1a8d2e8269956471e79bfaba34f3f5ac7070e1d33aa5d2101460854b72a6a` and `e807fab165c5327cf726eea6f5d70832dd4bbaec865d929b1ead67061759cf809debf0e43d53b23d612b4c3320eab578`; OpenVINO CPU load/compile and zero-array inference returned the expected detector contract.

### Validation
- Full Linux automated suite: **26/26 PASSED**. Model checksums: **PASSED**. OpenCV V4L2 capability: **PASSED**. Camera open/read/property smoke: **PASSED**.
- 45-second metadata-only camera/inference smoke: **PASSED** — 666 captured / 665 processed, 14.760 FPS, 16.189 ms median, 17.912 ms p95, 0 drops, online, V4L2/MJPEG/1280x720/15 FPS. A separate 20-second sample measured mean process CPU 92.52%, peak 106.00%, 13.426 FPS, 15.758 ms median, 17.169 ms p95, and 0 drops.
- The smoke runner emitted a marker-shaped label only as a runner segment name; no operator ground-truth claim was made or accepted, and the apparent detector positives/state were not used for occupancy qualification.
- Linux Codex parity: **PASSED** — `codex-cli 0.150.0-alpha.8`, ChatGPT OAuth authenticated, one bounded synthetic `person.entered` event returned schema-valid output from `gpt-5.6-luna` at low effort. Perception Codex/Luna calls: `0`.
- Audio inventory: **PASSED** — PipeWire/PulseAudio active, NexiGo microphone enumerated, default source/output available. No STT/TTS implementation or test was run.
- Raw-frame persistence: **NONE**. Physical disconnect/reconnect: **NOT RUN** by directive; deterministic failure-to-degraded/offline behavior remains covered by state tests. Fresh Ubuntu M1 markers: **NOT RUN**.

### Boundary and next step
- The Ubuntu platform baseline is qualified. This does not accept M1 presence behavior and does not reuse Windows Stage B. The next directive may restart M1 from fresh Ubuntu `CONFIRMED_EMPTY — START`; do not begin M2 in this record.
- Commit/push: `e9977aa` (`chore: rebaseline SENTRY on Ubuntu`) pushed to `origin/main`; final checkout clean and local `main` matches `origin/main`.

## OUTCOME-SENTRY-UBUNTU-M1-PRESENCE-QUALIFICATION-001 — Stage A pass; occupied-state evidence insufficient
- Date: 2026-08-28
- Directive: `SENTRY-UBUNTU-M1-PRESENCE-QUALIFICATION-001`
- Verdict: **STATE FAILURE — UBUNTU OCCUPIED EVIDENCE INSUFFICIENT**
- Retrieval confidence: ADEQUATE for the fresh Ubuntu Stage A interval and the two marker-aligned entry attempts; the operator's correction establishes that the retry person remained in frame.
- Evidence level: E5_OPERATIONALLY_OBSERVED for Stage A and the retry telemetry; Stage B entry latency was observable, but the retry also exposed a false-empty transition during continued presence.

### Stage A — confirmed empty
- Fresh marker: `CONFIRMED_EMPTY — START` at `2026-08-28T15:56:25.549453+00:00`; end marker at `2026-08-28T15:56:57.427416+00:00`.
- 442 observations were recorded; 441 online observations were usable and 1 startup observation was `degraded`.
- Authoritative state: `empty` 441/441 usable observations (100%); `occupied` 0; no false occupied transition and no phantom occupancy.
- Detector evidence: 0 positive observations; maximum people 0; 0 dropped frames.
- Performance: 442 captured / 441 processed, 14.667 FPS, 15.576 ms median, 17.989 ms p95, V4L2/MJPEG/1280x720/15 FPS, camera online at completion.
- The startup transition `empty->degraded->empty` recovered without producing false occupancy.

### Stage B — initial attempt and one authorized retry
- Initial attempt marker: `2026-08-28T16:03:41.649451+00:00`; first detector evidence `16:03:44.523761+00:00`; first `occupied` `16:03:45.548744+00:00`; marker-to-occupied 3.899 seconds. Clear-visibility timing was not independently marked, so this attempt was invalid for acceptance.
- Retry marker: `2026-08-28T16:07:18.447065+00:00`; first processed observation `16:07:19.899586+00:00`; first detector evidence `16:07:21.877867+00:00`; first person record `16:07:21.941791+00:00`; first `occupied` `16:07:22.937745+00:00`.
- Retry performance: 293 captured / 292 processed, 14.559 FPS, 15.526 ms median, 17.720 ms p95, 0 dropped frames, camera online at completion.
- Retry detector totals: 16 detector-evidence observations, 34 one-person observations, 0 multi-person observations, maximum 1 person, diagnostic track IDs 1-3. Detector evidence then ceased despite the operator confirming that the person remained in frame.
- State totals: `degraded` 1, `empty` 43, `occupied` 249. The service transitioned `occupied->empty` at `16:07:39.546311+00:00`, approximately 16.609 seconds after entering `occupied`, while the operator remained visible. This is a false-empty occupied-state failure after the configured 15-second absence grace.
- Entry timing from first credible person evidence to authoritative `occupied` was approximately 0.996 seconds; however, the run cannot pass the overall state gate because continued occupied state was not maintained.

### Boundary and safety
- Stages C-F were not run. Low-light and physical camera recovery remain unqualified.
- Raw frames: none persisted. Perception Codex/Luna calls: 0. Tracker was unchanged. No detector, threshold, runtime, camera, or M2 changes were made.
- Primary disposition: **STATE FAILURE — UBUNTU OCCUPIED EVIDENCE INSUFFICIENT**. Architect decision required before another marker or further qualification attempt.
## OUTCOME-SENTRY-UBUNTU-M1-ASYMMETRIC-EVIDENCE-001 — No qualifying support threshold
- Date: 2026-08-28
- Directive: `SENTRY-UBUNTU-M1-ASYMMETRIC-EVIDENCE-001`
- Verdict: **ASYMMETRIC EVIDENCE FAILED — 0202 SOURCE INSUFFICIENT**
- Retrieval confidence: ADEQUATE for current Ubuntu repository, runtime, detector, raw metadata captures, and deterministic simulator
- Evidence level: E5_OPERATIONALLY_OBSERVED for operator-confirmed calibration segments; E4_REGRESSION_PROTECTED for the implementation/tests

### Pre-live correction and implementation
- The first empty marker attempt produced zero observations because the example config still used numeric camera index `0`. It was not counted. The stable NexiGo V4L2 by-id path was verified and configured before the valid run.
- Added a one-inference `detect_raw()` path for positive 0202 candidates; production `detect()` remains the configured strong cutoff. The state contract now distinguishes strong entry evidence from support hold evidence, and telemetry exposes both flags plus maximum raw candidate confidence.
- The checked-in hold threshold remains `0.40`, equal to the entry threshold, so production occupancy behavior was not changed after the failed operating-band selection.

### Operator-confirmed Phase 2 segments
- Confirmed-empty marker: `CONFIRMED_EMPTY — START` at `2026-08-28T16:33:43.349436+00:00`; 889 observations over approximately 60 seconds. Raw candidates appeared in all 889 observations, with 40,815 positive candidates; confidence p50/p75/p90/p95/max was `0.026596 / 0.031280 / 0.041034 / 0.047504 / 0.285640`. The fixed `0.40` strong-entry gate produced no positive candidates. Support false-positive observations were 13 at 0.10, 11 at 0.15, 7 at 0.20, 2 at 0.25, and 0 at 0.30-0.40.
- Confirmed-one-person marker: `CONFIRMED_ONE_PERSON — START` at `2026-08-28T16:35:47.429792+00:00`; operator-confirmed continuous presence; 1,791 observations over approximately 120 seconds. Raw candidates appeared in all observations, with 55,051 positive candidates; confidence p50/p75/p90/p95/max was `0.031744 / 0.042617 / 0.115990 / 0.147000 / 0.547175`. Only 63/1,791 observations reached the fixed `0.40` strong entry gate. The first strong candidate occurred at frame sequence 3, but strong evidence did not remain within the configured 1-second entry evidence-gap policy, so simulated entry was delayed to frame sequence 665.

### Asymmetric offline sweep
- The same raw records were evaluated at support thresholds `0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40`; entry remained fixed at `0.40`. The occupied-state simulation yielded `62.9257%` correctness at 0.10-0.35 and `40.0893%` at 0.40. Support gaps were respectively `0.068, 0.068, 0.068, 1.468, 3.600, 14.000, 43.064` seconds. No threshold reached `>=95%` occupied correctness without a false-empty transition.
- Simulated post-exit empty reached the empty state in `15.990, 15.722, 15.657, 15.590, 14.522, 14.522, 14.522` seconds for thresholds 0.10 through 0.40 respectively, so exit suppression was not the limiting failure. No support threshold qualified because the fixed strong-entry gate could not establish occupancy reliably in the labeled occupied segment.
- Result: no asymmetric operating band was found. No Phase 3 production hold-threshold change and no fresh live A-D state qualification were authorized by the directive after this stop boundary.

### Validation and boundaries
- Automated suite after implementation: **32/32 PASSED**. Python compilation and `git diff --check`: PASSED. 0202 XML/BIN SHA-384 checksums: PASSED. OpenVINO CPU raw/strong smoke contract: PASSED.
- Raw frames persisted: `NONE`; calibration files contain metadata only under ignored canonical `perception-data/runtime/`. Runtime perception Codex/Luna calls: `0`. Tracker/model/runtime/device/camera architecture was not replaced or tuned.
- Recommendation: return to Architect with **ASYMMETRIC EVIDENCE FAILED — 0202 SOURCE INSUFFICIENT**. Preserve the prior Ubuntu occupied-state failure and this stronger raw-candidate evidence; do not increase absence grace, change the tracker, or begin M2.

## OUTCOME-SENTRY-UBUNTU-M1-YOLOX-S-001 — YOLOX-S office state evidence insufficient
- Date: 2026-08-28
- Directive: `SENTRY-UBUNTU-M1-YOLOX-S-001`
- Verdict: **YOLOX-S OFFICE EVIDENCE INSUFFICIENT**
- Retrieval confidence: ADEQUATE for the official source record, ignored local artifacts, OpenVINO integration, metadata calibration, and fresh operator-confirmed Stage A.
- Evidence level: E5_OPERATIONALLY_OBSERVED for the final empty-room Stage A; E4_REGRESSION_PROTECTED for implementation, export, runtime, calibration, and tests.

### Provenance and pre-live result
- Official YOLOX tag `0.3.0` resolves to commit `419778480ab6ec0590e5d3831b3afb3b46ab2aa3`. The official model-zoo checkpoint `0.1.1rc0/yolox_s.pth` SHA-256 is `f55ded7181e1b0c13285c56e7790b8f0e8f8db590fe4edb37f0b7f345c913a30`; official ONNX SHA-256 is `c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063`; official OpenVINO archive SHA-256 is `feeda7f65bdc9e44c4a8732fbfb22cd10787db9df0ef3c0472e5bf6f7b7ef7e3`. Separate checkpoint license terms were not stated in release metadata and remain a documented limitation.
- Official ONNX input/output were `[1,3,640,640]` and `[1,8400,85]`. OpenVINO-converted IR matched official ONNX exactly on seeded CPU comparison (`max_abs=0`, `mean_abs=0`). The active path uses only OpenVINO CPU; model artifacts remain ignored under canonical `perception-data/`.
- The initial smoke was non-ground-truth and passed at approximately `9.233 FPS`, `104.246 ms` median, and `115.274 ms` p95. No occupancy claim was drawn from it.

### Metadata calibration
- The same fresh labeled metadata records were evaluated at thresholds `0.10` through `0.50`. `0.50` was selected as the highest simulated state-qualified point. At `0.50`, the empty simulation had no false state transition; the one-person simulation had `99.0585%` authoritative occupied correctness, approximately `1.124s` entry latency, and no false-empty transition.
- These results did not substitute for final live acceptance and did not alter tracker thresholds or architecture.

### Final live Stage A — confirmed empty
- Marker: `CONFIRMED_EMPTY — START` at `2026-08-28T17:29:00.375268+00:00`; runner end marker at `2026-08-28T17:30:08.775216+00:00`.
- 566 observations were recorded; 565 were online and usable, with one startup `degraded` observation. At selected threshold `0.50`, 53/565 observations had positive candidate evidence (`9.38%`), with maximum two simultaneous detections and 55 qualifying candidate rows. Positive confidence reached `0.824309`; the high-confidence positives were sustained rather than isolated noise.
- Authoritative state counts were `empty=379`, `occupied=186`, `degraded=1`. The state transitioned `empty->occupied` at `17:29:26.997927Z` and returned `occupied->empty` at `17:29:46.402313Z`, a `19.272s` false-occupancy interval while the operator-confirmed room was empty. This fails the required empty-state correctness and no-phantom criteria.
- Performance: 891 captured / 565 processed, `9.403 FPS`, `102.107 ms` median, `109.405 ms` p95, 325 dropped frames; V4L2/MJPEG/1280x720/15 FPS, online at completion. The process snapshot reported RSS `209,350,656` to `573,624,320` bytes; CPU snapshot was not meaningful because the existing snapshot samples before sustained activity.

### Boundary and recommendation
- Primary disposition: **YOLOX-S OFFICE EVIDENCE INSUFFICIENT**. Stages B-D, low-light, camera disconnect/reconnect, and ten-minute soak were not run after the decisive Stage A failure. This is a detector/evidence failure at the room-state boundary, not a tracker qualification result.
- Automated tests: **37/37 PASSED** after the calibration wrapper correction; Python compilation and `git diff --check` passed. Raw frames persisted: `NONE`. Runtime perception Codex/Luna calls: `0`. Working tree remains intentionally uncommitted because the candidate did not pass acceptance.
- Recommendation: return to Architect before reverting, accepting, or replacing YOLOX-S. Do not begin M2, modify the tracker, increase grace, or model-shop automatically.
## OUTCOME-SENTRY-M1-PRACTICAL-ACCEPTANCE-AND-M2-START — 2026-08-28
- **Disposition:** M1 practical camera/human-detection foundation accepted for progression; detector qualification loop closed by Architect direction.
- The decision preserves prior negative detector/edge-case evidence as historical operational risk. It does not claim perfect per-frame recall, perfect individual tracking, or completed camera recovery.
- Project alignment: SENTRY now advances to the formal M2 goal of durable presence sessions, semantic state transitions, and queryable local history.
- Implemented first bounded slice: metadata-only versioned SQLite `PresenceStore`, restart-safe current state and sessions, state-derived room/session events, and a localhost-only read API. No raw frames are stored.
- Tests for migration, restart readback, session open/close, failure semantics, duplicate-track binary occupancy, and config validation pass. Full regression: **43/43 PASSED**. Threaded localhost API smoke: **PASSED** for health, current state, sessions, and events.
- The API smoke initially exposed SQLite's default cross-thread guard; the store now uses a serialized connection lock, matching Python's documented requirement when a connection is shared across handler threads.
- External discovery: Python standard-library `sqlite3` and `http.server` were used; no new dependency was added. The database remains under ignored canonical `perception-data/runtime/` storage.
- Working tree review: `git diff --check` **PASSED**; raw frames and runtime Codex/Luna calls remain **NONE/0**. This outcome is the implementation handoff for M2 continuation, not full V0.1 acceptance.

## OUTCOME-SENTRY-ARCHITECT-CORRECTION-AND-YOLOX-LIVE-REOPEN — 2026-08-28
- **Disposition:** prior practical M1 acceptance and M2 milestone transition claims are superseded; `230dafa` is preserved, M1 is reopened, and M2 persistence/API remains implemented-unverified and out-of-sequence.
- Ubuntu/V4L2 platform is **VERIFIED**. Original YOLOX Stage A failure is **VERIFIED**. Corrected official YOLOX postprocessing is **IMPLEMENTED_UNVERIFIED live**.
- Active next gate: `SENTRY-UBUNTU-M1-YOLOX-CORRECTED-LIVE-001`, fresh operator-confirmed Stage A-D using threshold `0.50`, NMS `0.45`, and unchanged state timings.
- No durable history will be written by qualification runs. No detector, tracker, threshold, timing, or M2 implementation changes are authorized.
## OUTCOME-SENTRY-M2-DURABLE-PRESENCE-MEMORY-001 — 2026-08-28
- **Primary disposition:** **M2 STORAGE TOPOLOGY BLOCKER**.
- Owner/operator direction is recorded and reconciled: practical Ubuntu camera/human detection is accepted for V0.1 progression; detector selection is frozen and no further detector qualification is required. Prior negative detector evidence remains historical operational risk.
- Starting repository: `0d14aa758220daaa5b02c6af585fbd6be82059d9`, clean before this record update; `230dafa` remains preserved history. Existing `PresenceStore`/localhost API implementation was inspected and not replaced.
- Canonical SENTRY path: `/srv/ATLAS/100_ACTIVE/Projects/SENTRY`. The Atlas mount is `TARGET=/srv/ATLAS`, `SOURCE=atlas:/srv/ATLAS`, `FSTYPE=fuse.sshfs`, with read/write options. The configured database location `perception-data/runtime/sentry.db` resolves on that same SFTP/FUSE-backed filesystem; no database file currently exists at that path.
- The active directive explicitly requires returning this blocker when SQLite operates across SFTP/FUSE/network storage. No storage relocation, old pool path, mergerfs, database migration, or alternate database service was attempted.
- Existing code inspection found schema migration 1, metadata-only room state/session/event recording, one-open-session lookup logic, persistence exception capture, and localhost endpoints. Full restart provenance, schema evolution, API health/database truthfulness, and process-level reconciliation evidence remain unqualified; implementation changes were intentionally stopped at the topology boundary.
- Repository integrity: local `HEAD` is `0d14aa758220daaa5b02c6af585fbd6be82059d9`; the checkout reported `main...origin/main` with no working-tree changes before this documentation update. `findmnt` and `git diff --check` were used; full test output was not relied upon as a qualification substitute for the topology blocker.
- Raw frames remain prohibited and absent from the persistence design. Continuous perception Codex/Luna calls remain `0`.
- Recommendation: return to Architect for a storage-topology decision. Do not claim M2 qualified or silently move SQLite off the canonical Atlas path.

## OUTCOME-SENTRY-M2-LOCAL-SQLITE-ATLAS-MIRROR-001 — Local live database and Atlas snapshot mirror
- Date: 2026-08-28
- Directive: `SENTRY-M2-LOCAL-SQLITE-ATLAS-MIRROR-001`
- Verdict: **COMPLETE IMPLEMENTATION / QUALIFICATION EVIDENCE PASSED**
- Retrieval confidence: **ADEQUATE** for the canonical checkout, M2 implementation, local SQLite topology, Atlas mount, deterministic persistence behavior, and process-level recovery scenarios.
- Evidence level: **E4_REGRESSION_PROTECTED** for the implementation and tests; physical unattended deployment was not claimed.

### Storage topology
- Execution host: Ubuntu SENTRY host. Local active database example: `~/.local/share/sentry/sentry.db`; `findmnt`/`df` identify the local root filesystem as `/dev/nvme1n1p2`/`ext4`.
- Atlas mirror: canonical project path `/srv/ATLAS/100_ACTIVE/Projects/SENTRY/perception-data/runtime/backups/sentry.db`, on `atlas:/srv/ATLAS` via `fuse.sshfs`.
- `PresenceStore` rejects network/FUSE filesystems for the active SQLite path. The Atlas copy is never opened as the live database; it is only copied/published and validated as a complete snapshot.
- Generated databases, snapshots, manifests, quarantine files, and runtime artifacts remain under ignored/local paths and are not committed.

### Implementation
- Added `perception/storage_mirror.py` with local-filesystem enforcement, SQLite `Connection.backup()` snapshots, local integrity checks, checksum verification, atomic Atlas temporary-file publication, manifest diagnostics, Atlas outage tolerance, missing-local restore, and corrupt-local quarantine/restore.
- Extended `PresenceStore` to schema version 2 with `start_reason`, `end_reason`, `recovered_after_restart`, `end_time_uncertain`, a unique one-open-session index, lifecycle events, restart reconciliation, mirror health, and truthful uncertainty provenance.
- Updated `PerceptionService` to use the local DB plus Atlas mirror configuration, record lifecycle events, reconcile the first post-start observation, and retain mirror status in bounded summaries.
- Enhanced `/health` to report DB availability, schema version, mirror state, last successful mirror/checksum, and last persistence/mirror error while all other API endpoints read the local live DB.

### Validation
- Schema migration v1->v2 and idempotent reopen: **PASSED**.
- Snapshot integrity/checksum and Atlas publication: **PASSED**.
- Failed publication preserves prior Atlas snapshot while local writes continue: **PASSED**.
- Missing local DB restores from Atlas: **PASSED**.
- Corrupt local DB is preserved under a timestamped quarantine name before Atlas restore: **PASSED**.
- Restart occupied->occupied preserves one session and emits restart provenance without duplicate start: **PASSED**.
- Restart occupied->empty closes the same session with `restart_reconciled`, `recovered_after_restart=1`, and `end_time_uncertain=1`: **PASSED**.
- Restart degraded/offline leaves the open session unresolved and emits no exit: **PASSED**.
- Clean and abrupt process-level restart/restore scenarios: **PASSED**.
- Localhost API state/session/history and health readback: **PASSED**.
- Full regression suite: **PASSED — 52/52** using `/home/sketch/.venvs/sentry-ubuntu/bin/python` with NumPy 2.2.6, OpenCV 4.12.0, and OpenVINO 2026.3.1. System Python was not used for acceptance because it lacks the project runtime dependencies.
- Raw frames persisted: **NONE**. Continuous Codex/Luna perception calls: **0**.

### Boundary
- This outcome qualifies the local-SQLite/Atlas-mirror implementation and deterministic restart/API behavior. It does not claim physical camera recovery, detector improvement, unattended service deployment, or M3 identity.
- Practical M1 remains accepted by explicit owner/operator direction; detector selection remains frozen and no detector qualification was resumed.
- Recommendation: **M2 durable presence memory is ready for Architect acceptance**, subject to review of the pushed implementation and the explicit local-database/Atlas-snapshot topology.
- GitHub: commit `8c1684014ed91d7317f2f0de060757f7d5e20262` (`feat: qualify local SQLite Atlas mirror persistence`) pushed to `origin/main`.

## OUTCOME-SENTRY-M2-LOCAL-SQLITE-ATLAS-MIRROR-001-CORRECTION — 2026-08-28
- The prior M2 outcome's `52/52` count is superseded by the final post-review regression count of **54/54 PASSED** in the pinned Ubuntu environment.
- Added and passed explicit coverage for Atlas mirror catch-up after a transient publication failure and concurrent localhost API reads during local SQLite writes.
- No production behavior, storage topology, detector, or scope changed; this is an evidence/test-record correction.

## OUTCOME-SENTRY-M3-PRIMARY-IDENTITY-001 — Static identity implementation and provenance gate
- Date: 2026-08-29
- Directive: `SENTRY-M3-PRIMARY-IDENTITY-001`
- Verdict: **PARTIAL — IMPLEMENTED / LIVE QUALIFICATION PENDING**
- Retrieval confidence: **ADEQUATE** for the accepted M2 baseline, current repository boundaries, OpenCV APIs, model artifacts, and deterministic implementation tests.
- M2 remains accepted at `0b11695980cea680c5092a34d0049471a541d021`; M3 is now active. M1 practical presence remains accepted by owner/operator direction and detector selection remains frozen.

### Provenance and runtime
- OpenCV Zoo revision `47534e27c9851bb1128ccc0102f1145e27f23f98` was verified through official repository model directories and licenses. YuNet `face_detection_yunet_2023mar.onnx` is MIT; SFace `face_recognition_sface_2021dec.onnx` is Apache-2.0.
- Exact artifacts were downloaded from the official GitHub media paths into ignored canonical `perception-data/models/opencv-zoo/`: YuNet size `232589` bytes, SHA-256 `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`; SFace size `38696353` bytes, SHA-256 `0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79`.
- OpenCV 4.12.0 provides `FaceDetectorYN` and `FaceRecognizerSF`; zero-array model smoke loaded both artifacts and produced no face detections.

### Implementation
- Added `perception/identity.py` for checksum-verified YuNet/SFace loading, face landmarks/quality metadata, unique association to existing tracks, in-memory normalized prototype construction, cosine matching, and three-observation confirmation within two seconds.
- Extended `PresenceStore` to schema version 3 with `persons`, `identity_profiles`, metadata-only current people, profile replacement/deletion, profile snapshot recovery, and deduplicated `person.identified` events. Embeddings are never in API/events/logs.
- Integrated optional bounded identity annotation into `PerceptionEngine` and added `/v1/persons`. Identity failures yield `unresolved` and do not change room presence.
- Added deliberate `tools/sentry_enroll_identity.py` and explicit `tools/sentry_identity_admin.py delete`. Enrollment defaults to 16 accepted samples and never persists frames or individual embeddings.

### Validation and boundary
- Focused identity tests: **13/13 PASSED**. Full Ubuntu regression: **67/67 PASSED**. `py_compile` and `git diff --check`: **PASSED**. OpenCV SFace alignment/feature smoke and identity-enabled service construction also passed.
- Deterministic coverage includes conservative state semantics, unique association, temporal confirmation, prototype normalization, schema/profile persistence, Atlas restore, API metadata-only exposure, deletion, and one-active-profile enforcement. Existing M2 tests were updated for schema v3 and remain passing.
- No live enrollment, genuine holdout, consenting non-primary negative segment, threshold calibration, simultaneous-person test, or unattended performance measurement was run. M3 is not accepted from static evidence.
- Raw frames persisted: **NONE**. Unknown embeddings persisted: **NONE**. Continuous perception Codex/Luna calls: **0**. Model files are ignored and not committed.
- Recommendation: run explicit enrollment and the required primary/negative identity qualification before Architect acceptance; do not begin M4 yet.

## OUTCOME-SENTRY-M3-LIVE-IDENTITY-QUALIFICATION-001 — 2026-08-29
- Directive: `SENTRY-M3-LIVE-IDENTITY-QUALIFICATION-001`
- Verdict: **M3 PRIMARY IDENTITY QUALIFIED — BOUNDED EVIDENCE**
- Retrieval confidence: **ADEQUATE**
- Starting implementation commit: `b0d2d55020a31b858acb8b56e80c3d0bd1c01b45`; final record commit follows after regression and review.

### Enrollment and calibration
- `primary_user` enrolled as `Sketch`: 16 accepted samples; 2 no-face retries rejected. Prototype remains local SQLite/Atlas-mirror data only.
- Held-out primary scoring: 425 quality-qualified opportunities; min `0.336972`, p05 `0.523064`, median `0.647479`, p95 `0.851604`, max `0.892053`.
- Consenting non-primary scoring: 210 quality-qualified opportunities; min `0.112480`, p05 `0.164561`, median `0.243036`, p95 `0.332199`, max `0.383385`.
- Selected threshold: `0.55`, the highest tested value retaining >=80% genuine acceptance. Genuine `377/425` (`88.71%`), negative accepts `0/210`, measured accepted-ID precision `100%`.

### Live evidence
- Corrected primary segment: 495/495 processed, 8.246 FPS, median 114.942 ms, p95 140.233 ms, 0 read failures, 0 detector errors, first recognition 2.773 s, one stable track, room remained occupied after entry. Identity states: recognized 277, unknown 20, unresolved 198; unresolved represented intermittent face evidence loss and did not alter presence.
- Non-primary segment: 498/498 processed, 8.291 FPS, median 114.676 ms, p95 137.871 ms, 0 read failures, 0 detector errors, recognized 0, unknown 316, unresolved 182; room remained occupied.
- RSS during identity-enabled runs was approximately 280 MB start, 452 MB peak, and 442–445 MB end; process CPU was approximately 368–371% of one core. The >=5 FPS floor held.
- Simultaneous two-person association: **NOT RUN — both consenting people unavailable together**.

### Recovery and privacy
- Actual enrolled profile survived local DB reopen and Atlas restore with one active `persons` row, one `identity_profiles` row, threshold `0.55`, 16 samples, and unchanged model provenance. Full regression after final correction: **69/69 PASSED**; `py_compile` and `git diff --check` passed.
- Raw frames persisted: **NONE**. Unknown/query embeddings persisted: **NONE**. Continuous perception Codex/Luna calls: **0**.
- Recommendation: M3 is qualified for bounded one-primary-user V0.1 operation; keep simultaneous-person identity association as a later limitation and do not begin M4 until Architect accepts this record.
## OUTCOME-SENTRY-M4-GROUNDED-CONVERSATION-001 — Bounded grounded conversation qualification
- Completed: 2026-08-29
- Verdict: **M4 GROUNDED CONVERSATION QUALIFIED — BOUNDED API/LUNA EVIDENCE**
- Starting SHA: `f07d278d04f207b3e18518f2807e6a58ce8be488`

### Implementation
- Added `tools/sentry_grounding.py` as the deterministic localhost retrieval and allow-listed fact-packet layer. It queries `/health` first, then current state, sessions, persons, and events, and derives only bounded session/identity/last-empty facts with an explicit `as_of` timestamp.
- Added `tools/sentry_ask.py` for one text question, with at most one OAuth-authenticated `gpt-5.6-luna` turn. Added `tools/sentry_grounded_response.schema.json`; SENTRY rejects malformed responses, unsupported grounding states, empty citations for supported/partial answers, and unknown `fact_id` citations.
- Preserved the M0 synthetic-event bridge contract while factoring its bounded launcher. The state API remains localhost-only and gained bounded session/event `limit` parameters plus direct-entry import-path portability.

### Validation
- Local storage topology: live DB `/home/sketch/.local/share/sentry/sentry.db` on ext4; Atlas `/srv/ATLAS` remains `fuse.sshfs`. The query layer reads only localhost API data and never opens SQLite or Atlas directly.
- Deterministic fixture/API regression: empty, occupied/recognized, occupied/unknown, occupied/unresolved, degraded, offline, completed-session, and restart-reconciled uncertainty cases passed. Sensitive fields such as boxes, raw frames, prototypes, and unrestricted payload keys were excluded.
- Full Ubuntu regression: **77/77 passed**; Python compilation and `git diff --check` passed.
- Real API/Luna proof: 13 successful low-effort `gpt-5.6-luna` turns across the six core concepts, adversarial unsupported-premise queries, and current-state checks. The real DB was healthy (schema 3, Atlas mirror `ok`) but currently had no room observation, sessions, or events; responses consistently returned `partial`/`unavailable` and did not invent occupancy, identity, arrival, activity, causality, or relationship history.
- Unavailable-source proof: API connection failure returned the deterministic unavailable answer with **0 Luna invocations**. All successful query responses cited only supplied fact IDs; each question used one Luna invocation.
- Perception remains separate and makes **0 Codex/Luna calls**. No raw frames, embeddings, biometric prototypes, secrets, or unrestricted DB rows were sent to Luna.

### Boundary
- M4 is qualified for bounded text queries grounded in the current localhost API and persisted metadata. Current real history is empty, so historical answers are correctly unavailable until SENTRY records relevant sessions/events. M5 proactive behavior, voice, and richer activity/memory claims remain out of scope and gated.

## OUTCOME-SENTRY-M5-RESTRAINED-PROACTIVITY-001 — Implementation with physical qualification pending
- Completed: 2026-08-29
- Verdict: **PARTIAL — M5 IMPLEMENTED / PHYSICAL EVENT UNRESOLVED**
- Starting SHA: `a46351b02105fcd4c48ca3965d225b9de4d6fada`

### Implementation
- Schema migration 4 adds `proactive_actions` with source-event uniqueness, semantic candidate/session key, eligibility/suppression reason, Luna decision/citations, utterance, delivery status, and timestamps. Atlas mirroring includes the new metadata-only records through the existing SQLite backup path.
- `perception/proactive.py` processes only persisted `person.identified` events for `primary_user` in the current occupied office session. Defaults are TTL 30s, one action/session, 30-minute person cooldown, two delivered actions/hour, 30-second startup suppression, low-effort `gpt-5.6-luna`, and 20 words/160 characters.
- `tools/sentry_proactive.py` provides the bounded processor CLI. `tools/sentry_m5_live.py` provides an isolated local SQLite physical harness with Atlas snapshot mirroring and in-memory profile seeding. `SpeechDispatcher` uses local `spd-say` and cancellation only.

### Validation
- Focused M5 suite: **12/12 passed**. Full Ubuntu regression: **89/89 passed**. Coverage includes deterministic zero-Luna suppressions, eligible one-call behavior, valid speak/silent decisions, malformed output fail-silent behavior, dedupe, same-session suppression, cooldown, hourly budget, speech busy/failure, restart, Atlas restore, and biometric privacy.
- Real bounded Luna judge proof: one eligible metadata event invoked one low-effort `gpt-5.6-luna` turn; Luna returned a valid grounded `silent` decision, which was persisted. No continuous perception Luna calls occurred.
- Local speech delivery proof: `spd-say --wait` succeeded in 2.30s. Active speech cancellation returned true and the worker stopped.
- Physical harness attempt 1: V4L2/MJPEG/1280x720/15 FPS, 7.935 processed FPS, 392 processed frames, clean mirror; no identity event.
- Physical harness attempt 2: V4L2/MJPEG/1280x720/15 FPS, 7.783 processed FPS, 385 processed frames, clean mirror; no identity event.

### Boundary
- Neither physical attempt produced a session or `person.identified` candidate, so the real event-to-proactive path is **UNRESOLVED**, not passed or failed. No detector, identity, or tracker conclusion is drawn. M5 remains implemented-unverified; M6 is still gated.
