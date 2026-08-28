# Current Project State

Last updated: 2026-08-28T19:05:00-04:00

## Current stage
M2 presence sessions and persistence

## Current objective
Carry the accepted practical Ubuntu camera/human-detection foundation into durable, restart-safe presence sessions and queryable local history.

## Active directive
Architect authorization to proceed past M1 — accept practical camera/human detection for V0.1 and begin the smallest M2 presence-session/persistence slice. Detector selection is frozen; no further detector qualification is authorized in this phase.

## Architect transition — 2026-08-28
- The Architect explicitly accepted the practical camera/human-detection foundation as good enough for the project goal and authorized progression. This supersedes the prior detector-specific qualification loop without rewriting its historical evidence.
- Next work is M2: record timestamped room-state transitions and open/completed presence sessions in SQLite, expose a localhost-only query surface, and verify restart-safe history. No identity or proactive behavior is being added in this slice.
- Residual detector edge cases, individual-track quality, and physical camera recovery remain known operational risks; they are not being used to block the next project-goal milestone.

## M2 persistence slice — current
- `perception.presence_store.PresenceStore` is the metadata-only SQLite store. It applies schema migration 1, records current room state, emits state-derived room/session events, and closes open sessions on `occupied->empty`.
- `tools/sentry_state_api.py` provides localhost-only `/health`, `/v1/rooms/office/state`, `/v1/rooms/office/sessions`, and `/v1/events` reads. The default database is ignored at `perception-data/runtime/sentry.db`.
- Raw frames, embeddings, and continuous Codex/Luna calls remain outside this slice.

## Platform migration status
- Ubuntu 24.04.4 LTS / Linux 7.0.0-30-generic / x86_64 is now authoritative for future V0.1 work. The canonical project remains `/srv/ATLAS/100_ACTIVE/Projects/SENTRY` on the Atlas share; the Ubuntu desktop currently reaches that exact checkout through its authenticated user SFTP mount.
- Windows DirectShow, PnP, numeric-index, and Windows runtime results remain historical evidence. The unfinished Windows Stage B entry run is `INVALID/UNRESOLVED` for acceptance because operator visibility after the marker was not confirmed before migration.
- The exact NexiGo N60 V4L2 device is `/dev/v4l/by-id/usb-webcamvendor_NexiGo_N60_FHD_Webcam_Jan_29_2024-10:32:28-N60-video-index0`; the device ACL permits the SENTRY user. Measured target mode is MJPEG 1280x720 at 15 FPS.
- The pinned Linux environment is Python 3.12.3, `opencv-python-headless==4.12.0.88`, `openvino==2026.3.1`, `psutil==7.0.0`, with OpenVINO devices `CPU`, `GPU.0`, and `GPU.1`. CPU remains the active inference device.
- 0202 FP32 XML/BIN checksums remain `fc218405...72a6a` and `e807fab...ab578`; model load/compile and zero-array output contract pass on Ubuntu. Full Linux tests pass 26/26.
- Linux V4L2 camera/inference smoke passed: 666 captured / 665 processed, 14.760 processed FPS, 16.189 ms median and 17.912 ms p95, 0 dropped frames. A separate 20-second sample measured 13.426 processed FPS, 15.758 ms median, 17.169 ms p95, mean process CPU 92.52%, peak 106.00%, and 0 dropped frames. Smoke telemetry is not occupancy ground truth.
- The bounded OAuth bridge passed a synthetic `person.entered` proof on Linux using `gpt-5.6-luna` at low effort; perception makes zero Codex/Luna calls. PipeWire/PulseAudio and NexiGo microphone/output inventory completed; voice implementation remains out of scope.
- No raw frames were persisted. Runtime/model evidence remains under ignored canonical `perception-data/` paths. RT-DETR and 0202 artifacts remain historical/ignored; YOLOX-S is the frozen practical V0.1 backend by Architect direction.
- The asymmetric-evidence diagnostic path exposes positive 0202 candidates from the same single inference, but production semantics remain unchanged at entry/hold threshold `0.40` because calibration found no qualifying lower support threshold.
- Official YOLOX-S integration remains the active local backend: upstream tag `0.3.0` commit `419778480ab6ec0590e5d3831b3afb3b46ab2aa3`, official model-zoo checkpoint `0.1.1rc0/yolox_s.pth`, official ONNX-to-OpenVINO conversion, 640x640 input, 8400x85 output, COCO person filtering, upstream letterbox/grid decode, and NMS `0.45`. Local model artifacts remain ignored. The Architect accepted practical camera/human detection as sufficient and froze detector selection for V0.1 progression.
- Ubuntu platform migration commit `e9977aa` (`chore: rebaseline SENTRY on Ubuntu`) is pushed to `origin/main`; the canonical checkout is clean after the push.

## Latest YOLOX-S qualification result (historical evidence)
- Metadata-only labeled calibration used the existing YOLOX-S candidate records and selected `0.50` as the highest tested state-qualified threshold. Empty-state simulation qualified at `0.50`; the one-person simulation reached `99.0585%` authoritative occupied correctness with approximately `1.124s` simulated entry latency and no false-empty transition.
- Fresh final Stage A was operator-confirmed empty from `2026-08-28T17:29:00.375268Z` through `2026-08-28T17:30:08.775216Z`. It recorded 566 observations, 565 online usable observations, 53/565 threshold-qualified positive observations (`9.38%`), maximum two simultaneous detections, and authoritative state `occupied` for 186/565 observations (`32.92%`) in a sustained `19.272s` false-occupancy interval. Positive confidences reached `0.824309` (55 threshold-qualified candidates including duplicate boxes).
- Stage A therefore stopped at the prior strict false-human-evidence boundary. Stages B-D, low-light, camera recovery, and soak were not run under that directive. The historical result was `YOLOX-S OFFICE EVIDENCE INSUFFICIENT`; the Architect has since accepted practical camera/human detection and authorized progression.

## YOLOX postprocessing root-cause investigation (historical)
- Official YOLOX 0.3.0 semantics select the winning class across all class probabilities using `objectness × top_class_probability`, then apply class-agnostic NMS; person is accepted only when the final winning class is COCO person (`0`). The prior SENTRY decoder instead evaluated `objectness × person_probability` before NMS, which is a confirmed divergence.
- A deterministic overlapping-box case demonstrated the consequence: the legacy path would retain a person-scored box at `0.72`, while the official winner was non-person at `0.9405` and suppressed it. SENTRY now follows the official winning-class/NMS order and exposes metadata-only parity rows for diagnostics.
- The identical-tensor synthetic OpenVINO check passed: raw shape `[1,8400,85]`, corrected SENTRY final-person count matched the reference count (`0 == 0`). The full automated suite remains `37/37` after the correction.
- A live parity probe could not open the stable NexiGo device because `/dev/video0` was held by unrelated `anima` process PID `219972`. No process was terminated and no live parity claim was made. This historical qualification loop is closed by Architect decision; no further detector-specific Stage A-D run is required before M2.

## Current verified state
- The Architect rejected RT-DETR for V0.1 after confirmed-empty false-human evidence and sub-floor throughput, then authorized this final reuse test of the already-investigated 0202 signal through the room-state layer. RT-DETR-specific working-tree code was removed from active production source after complete diff preservation.
- The restored 0202 implementation and fresh asymmetric calibration remain historical negative evidence; no qualifying support operating band was found. The current active backend is the Architect-approved YOLOX-S integration described above.
- The temporal state layer is implemented behind structured observations. It maintains only `empty`, `occupied`, `degraded`, and `offline`; it uses timestamp-based entry confirmation of 1.0 seconds, a 1.0-second entry evidence-gap tolerance, and a 15.0-second absence grace period. Duplicate detections are binary human evidence and do not count occupants.
- Structured observations include room state, state transitions, strong/support detector evidence, maximum candidate confidence, and metadata-only luminance/contrast measurements. The M2 slice now adds metadata-only persistence, sessions, derived events, and a localhost read API; no image enhancement, identity, or proactive behavior was added.
- State-machine deterministic tests and the restored 0202 perception suite pass 24/24 using the repository `.venv`. The 0202 FP32 XML/BIN remain ignored and match the recorded Open Model Zoo SHA-384 checksums.
- Pre-live scope review passed: no detector/model/runtime/tracker changes, no raw frames persisted, and no Codex/Luna perception calls. The asymmetric calibration now provides fresh operator-labeled raw-candidate evidence for the current directive.
- Canonical path `\\atlas\\ATLAS\\100_ACTIVE\\Projects\\SENTRY` contains a valid Git checkout restored from GitHub after the damaged path was absent on repeated inventory reads.
- The last committed `main` and `origin/main` state was `52c2095` before this authorized transition; the YOLOX-S implementation, calibration tooling, and evidence are being committed together with the M2 persistence slice so GitHub reflects the accepted direction.
- `git fsck --full` passed with exit code 0 and no reported errors.
- Authority kernel, reusable skills, perception source, configuration, requirements, documentation, and tests are present.
- Existing and decoder-focused automated tests pass 15/15.
- No surviving SENTRY files or directories were present before restoration; no unique uncommitted SENTRY material was found or discarded, and no quarantine was required.
- The parent Atlas project share was reachable and stable across repeated reads. Neighboring visible project directories were not treated as comparable Git checkout evidence.
- Architect accepted the practical camera/human-detection foundation as sufficient for progression. Individual tracking quality and controlled camera recovery remain operational risks to validate later; they do not reopen detector selection in the current M2 slice.
- Human-visible Windows Camera preview confirmed one real seated person in the office scene. A 30-second live run produced person records in 238/271 observations (87.8%), but up to 3 simultaneous tracks and IDs 1–14 in a one-person scene. A 90-second run produced up to 6 tracks and 29 unique IDs, materially failing stable office-presence behavior.
- A synchronized occlusion attempt produced one track with two detector-visible observations followed by bounded predicted misses through miss count 12, but the physical timing/box correspondence was not sufficient to accept controlled dropout continuity.
- The existing service remained online during a 90-second run. An authorized PnP disable attempt returned `Generic failure`, and a restart attempt returned `Access is denied`; controlled offline/reopen recovery was not executed.
- M0 and the practical M1 camera foundation are complete for progression. M2 persistence/sessions is active; identity, broader events, conversational grounding, proactive behavior, and embodiment remain ahead.
- Architect-authorized FP32 `person-detection-0202` XML/BIN artifacts were downloaded under ignored canonical `perception-data/models/person-detection-0202/FP32/`; both match the Open Model Zoo manifest SHA-384 checksums.
- The pinned generic `opencv-python-headless==4.12.0.88` failed both `cv2.dnn.readNet` and `cv2.dnn.readNetFromModelOptimizer` with `Backend (plugin) is not available: 'openvino'`. The detector experiment was reverted; no alternate runtime was introduced.
- Architect has now authorized exactly one additional runtime. Isolated `.venv` installation passed with `openvino==2026.3.1`, `opencv-python-headless==4.12.0.88`, `psutil==7.0.0`, and transitive `numpy==2.2.6` / `openvino-telemetry==2025.2.0`.
- Host verification: Windows 11 x64, AMD Ryzen 7 5800XT, Python 3.12.10, OpenVINO devices `CPU`, `GPU.0`, and `GPU.1`.
- OpenVINO loaded and compiled the checksummed FP32 model on CPU; bounded zero-array inference returned `(1, 1, 200, 7)`.
- The production detector now uses OpenVINO behind the existing detector contract, with model paths configurable and explicit load/decode failures. The IoU tracker remains unchanged. The 0303 decoder now follows the official class-agnostic path: positive box confidence, explicit `[1/1280, 1/720]` reconstruction, clipping, and local class-agnostic NMS at `0.6`; the companion labels tensor is diagnostic only.
- Confirmed-empty Stage A run: 205 processed online observations over approximately 20.6 seconds, all zero-person, with no false-person detections; 8.095 processed FPS and 0 dropped frames.
- Confirmed-one-person Stage B run: the operator confirmed one person remained continuously visible. The service processed 827 online observations over approximately 83.9 seconds at 9.154 FPS, with 480 zero-detection observations, 318 exactly-one observations, 29 multi-detection observations, and a maximum of 2 simultaneous detections. The unchanged tracker produced 19 unique track IDs, first ID 1, final visible ID 19, 32 visible-ID-set changes, and up to 3 active tracker records. This fails the required one-person quality target.
- Stage C synchronized dropout and Stage E ten-minute soak were not run because the confirmed detector-quality failure reached the directive stop boundary. Multi-person live evidence remains blocked because no second person was available. Camera failure/recovery remains a separate unrun M1 gate.
- Calibration diagnostic capability was added without changing the model, OpenVINO runtime/device, preprocessing, camera path, frame buffer, tracker, or production threshold. It records only raw candidate timestamps, frame sequences, confidences, boxes, and inference timing; raw candidates are never sent to the production tracker.
- Calibration Stage A operator-confirmed empty segment: runner marker `CONFIRMED_EMPTY` at `2026-08-26T16:18:50.151051+00:00`; 303 online observations over 30.639 seconds. At threshold 0.20, false-positive observations were 2/303 (0.660%), maximum 1, with a 0.111-second longest run. Raw confidence percentiles were p50 0.031729, p75 0.040432, p90 0.070170, p95 0.107720, max 0.233231.
- Calibration Stage B operator-confirmed continuous one-person segment: runner marker `CONFIRMED_ONE_PERSON` at `2026-08-26T16:21:28.148642+00:00`, runner end at `2026-08-26T16:22:33.820060+00:00`, and operator confirmation `CONFIRMED_ONE_PERSON — END — CONTINUOUS`; 599 online observations over 60.559 seconds. At threshold 0.40, any detection was 579/599 (96.661%), but 64/599 observations had duplicate/multi-box detections (10.684%) and the longest duplicate run was 0.911 seconds. At 0.45, duplicates fell to 2/599 (0.334%) but recall fell to 534/599 (89.149%). Raw confidence percentiles were p50 0.058726, p75 0.112728, p90 0.323212, p95 0.489522, max 0.943762.
- No tested threshold from 0.10 through 0.50 met both empty false-positive rate <=1% and one-person >=95% recall with rare duplicates. The calibration result is `DETECTOR CALIBRATION FAILED — REPLAN MODEL`.
- Best-candidate bounding-box sanity was not accepted because the installed headless OpenCV build cannot provide `cv2.imshow`; no visual overlay or frame was persisted. This limitation does not weaken the decisive count-based calibration failure.
- Architect authorized the bounded `person-detection-0303` replan. Official FP32 XML/BIN downloads match the manifest sizes and SHA-384 checksums, and the OpenVINO model loads with static input `[1,3,720,1280]` and runtime outputs `boxes (N,5)` plus `labels (N,)`.
- 0303 pre-live CPU performance check: native 1280x720 DirectShow camera, 107 captured / 105 processed, 6.852 processed FPS, 79.056 ms median and 114.636 ms p95 processing latency, 1 dropped frame, online throughout, zero Codex/Luna calls.
- Raw 0303 investigation: operator-confirmed one-person marker at `2026-08-26T19:42:57.764666+00:00`; 149 online observations over approximately 20.3 seconds. Raw output contained 1,474 positive-confidence rows, 339 rows at or above `0.10`, maximum confidence `0.458353`, and all companion labels were `0`; the pre-correction SENTRY decoder emitted zero candidates in all observations. **DECODER BUG CONFIRMED**.
- Corrected 0303 Stage A: runner marker `CONFIRMED_EMPTY` at `2026-08-26T20:07:48.797739+00:00`; 181 online observations over 29.969 seconds. At threshold `0.45`, false positives were `0/181`; at `0.40`, false positives were `4/181` (2.21%); lower thresholds produced sustained duplicate false detections.
- Corrected 0303 Stage B: runner marker `CONFIRMED_ONE_PERSON` at `2026-08-26T20:23:10.311140+00:00`; 556 online observations over 56.863 seconds with one person continuously visible. At threshold `0.45`, recall was `134/556` (24.10%); at `0.40`, recall was `270/556` (48.56%) while the matched empty false-positive rate was 2.21%; no tested threshold met both gates. **DECODER BUG CONFIRMED — 0303 STILL FAILS QUALITY**.
- Corrected-decoder short performance: 101 captured / 95 processed, 6.173 processed FPS, 87.893 ms median and 132.416 ms p95 processing latency, 5 dropped frames, CPU path, RSS 162.6 MB to 268.4 MB, zero Codex/Luna calls. No ten-minute soak was reached because detector quality failed.
- Tracker qualification, synchronized dropout, ten-minute soak, and live two-person behavior were not run because corrected detector quality failed. Camera recovery remains a separate M1 gate. No tracker, runtime, device, precision, camera, or production threshold change was made.

## Current hypotheses / unknowns
- The original SENTRY disappearance is consistent with a transient Atlas share/filesystem visibility or consistency failure, but deletion versus transient visibility cannot be proven from the surviving evidence.
- The restored checkout is trustworthy for continued project work; the earlier camera result remains preserved in Notion and prior append-only evidence.

## Current blockers
- Stage A of `SENTRY-CONVERGENCE-RTDETR-PRESENCE-STATE-001` failed decisively: during the fresh operator-confirmed-empty run, the RT-DETR path produced 8 positive candidate observations and the authoritative state transitioned `empty->occupied` for approximately 15.8 seconds. Stop at the false-human-evidence boundary; do not request Stage B-D markers or commit RT-DETR as accepted production capability.
- Fresh Ubuntu room-state qualification has Stage A passed and Stage B stopped after the one authorized retry. The retry produced brief evidence and an occupied transition, then falsely returned to `empty` while the operator remained in frame; classify as `STATE FAILURE — UBUNTU OCCUPIED EVIDENCE INSUFFICIENT`, not an operator-protocol failure. Do not reuse earlier detector-specific markers or per-frame calibration results as this directive's state evidence.
- Low-light health thresholds are unresolved until labeled dim/insufficient-light evidence is collected; the implementation supports explicit degraded quality but does not invent a luminance cutoff.
- M1 strict live qualification evidence remains historical and incomplete, but the Architect has authorized the practical foundation as good enough. M2 persistence/sessions is the active milestone; camera recovery remains a later operational gate.
- The current detector quality is inadequate for ordinary confirmed office presence sensing; the unchanged tracker cannot be evaluated as a separate bottleneck from this failed detector input.
- A human-confirmed one-person segment was completed; the current OpenVINO detector produced a confirmed quality failure and telemetry-only runs remain non-acceptance evidence.
- Controlled camera failure/recovery remains blocked pending an authorized physical disconnect/reconnect or administrative device-interruption path.
- The original Atlas incident has no proven low-level root cause; no broad storage repair or migration was attempted.
- RT-DETR remains rejected for this host. The prior 0202 per-frame and Ubuntu occupied-state failures are preserved as historical evidence; the authorized asymmetric reuse test also found no qualifying support threshold. Do not change the tracker, increase absence grace, model-shop, or begin M2.
- Fresh asymmetric calibration stopped after Phase 2: confirmed-empty raw candidates were low-confidence, while the continuously confirmed one-person segment had only 63/1791 observations at or above the fixed `0.40` entry threshold. No support threshold from `0.10` through `0.40` achieved simulated occupied correctness of `>=95%` with a valid bounded exit.

## Latest recorded evidence
- `OUTCOME-SENTRY-CONVERGENCE-RTDETR-PRESENCE-STATE-001-STAGE-A`: retained as negative evidence; RT-DETR produced false occupied state and missed the FPS floor.
- `OUTCOME-SENTRY-CONVERGENCE-0202-PRESENCE-STATE-001-PRE-LIVE`: restored historical 0202 detector, retained generic state/luminance work, 24/24 tests passed, checksums passed, and short performance gate passed at 5.962 FPS. Awaiting fresh Stage A.
- `OUTCOME-SENTRY-CONVERGENCE-0202-PRESENCE-STATE-001-STAGE-A`: fresh confirmed-empty run passed with 230/230 usable online observations authoritative `empty`, zero detector positives, zero false occupancy, and no persistent phantom evidence. Awaiting fresh Stage B entry marker.
- `OUTCOME-SENTRY-REPO-RECOVERY-001`: fresh clone at `73b43f3`, `git fsck` passed, Authority/source checks passed, automated tests 5/5 passed, canonical reread stable, and local/remote `main` matched.
- `OUTCOME-SENTRY-M1-LIVE-QUALIFICATION-001`: human-visible single-person scene observed; detector/tracker produced severe track churn and false-positive indicators; performance remained above target; controlled camera recovery was blocked by device-operation access failure.
- `OUTCOME-SENTRY-M1-DETECTOR-REPLAN-001`: official model/license/checksum evidence passed, but generic OpenCV DNN IR loading failed; no production detector change was retained and live Stage A/B/C did not run.
- `OUTCOME-SENTRY-M1-DETECTOR-RUNTIME-001`: OpenVINO implementation target-tested; subsequent confirmed live quality evidence failed the one-person gate.
- `OUTCOME-SENTRY-M1-OPENVINO-LIVE-001`: confirmed-empty baseline passed, confirmed-one-person detector/tracker quality failed decisively, and later stages stopped at the authorized quality boundary.
- `OUTCOME-SENTRY-M1-DETECTOR-CALIBRATION-001`: raw-confidence sweep across operator-confirmed empty and continuous-one-person segments found no acceptable operating threshold; model replan is required.
- `OUTCOME-SENTRY-M1-DETECTOR-0303-001`: official 0303 artifacts/runtime/output semantics passed, short CPU performance stayed above 5 FPS, confirmed-empty passed, but confirmed-one-person produced zero candidates across 0.10-0.90; detector quality failed before tracker qualification.
- `OUTCOME-SENTRY-M1-0303-DECODER-RECONCILE-001`: raw output proved the prior zero-candidate result was caused by the label gate; reference-semantics correction passed 15/15 tests, but corrected live calibration still failed all quality operating points.
- `OUTCOME-SENTRY-M0-CODEX-FEASIBILITY-001` and `OUTCOME-SENTRY-M0-CODEX-CONTEXT-OPT-001`: accepted M0 Luna boundary and runtime isolation evidence remain historical and unchanged.

## Current risks
- Treating the recovered checkout or camera path as proof of M1 acceptance would overstate the evidence.
- The Atlas share incident may recur; preserve append-only state and recheck canonical path stability after future writes.
- HOG/tracker telemetry must not be promoted to person-quality acceptance when one known person produces multiple simultaneous tracks and high ID churn.

## Next Architect decision point
The asymmetric-evidence calibration found no qualifying operating band. Architect decision is required before any Phase 3 production change or further live marker; do not increase the 15-second grace, change the tracker, model-shop, or begin M2.

This file is a mutable snapshot. Do not use it to erase historical outcomes or decisions.
