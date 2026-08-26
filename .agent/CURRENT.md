# Current Project State

Last updated: 2026-08-26T12:30:00-04:00

## Current stage
M1 — Local Windows Perception

## Current objective
Determine whether the authorized OpenVINO-backed `person-detection-0202` detector can meet M1 quality through evidence-based confidence calibration.

## Active directive
SENTRY-M1-DETECTOR-CALIBRATION-001 — STOPPED AT CALIBRATION FAILURE; no tested confidence threshold separates the confirmed-empty and confirmed-one-person scenes.

## Current verified state
- Canonical path `\\atlas\\ATLAS\\100_ACTIVE\\Projects\\SENTRY` contains a valid Git checkout restored from GitHub after the damaged path was absent on repeated inventory reads.
- The last committed `main` and `origin/main` state is the calibration diagnostic/evidence commit recorded in the latest outcome; all authorized changes are pushed.
- `git fsck --full` passed with exit code 0 and no reported errors.
- Authority kernel, reusable skills, perception source, configuration, requirements, documentation, and tests are present.
- Existing and calibration-focused automated tests pass 11/11.
- No surviving SENTRY files or directories were present before restoration; no unique uncommitted SENTRY material was found or discarded, and no quarantine was required.
- The parent Atlas project share was reachable and stable across repeated reads. Neighboring visible project directories were not treated as comparable Git checkout evidence.
- Architect accepted the camera-access investigation as valid evidence, but M1 remains unaccepted because human detection quality, multi-person tracking, dropout continuity, and controlled camera recovery remain unproven.
- Human-visible Windows Camera preview confirmed one real seated person in the office scene. A 30-second live run produced person records in 238/271 observations (87.8%), but up to 3 simultaneous tracks and IDs 1–14 in a one-person scene. A 90-second run produced up to 6 tracks and 29 unique IDs, materially failing stable office-presence behavior.
- A synchronized occlusion attempt produced one track with two detector-visible observations followed by bounded predicted misses through miss count 12, but the physical timing/box correspondence was not sufficient to accept controlled dropout continuity.
- The existing service remained online during a 90-second run. An authorized PnP disable attempt returned `Generic failure`, and a restart attempt returned `Access is denied`; controlled offline/reopen recovery was not executed.
- M0 remains complete; M2, identity, persistence, events, and broader embodiment remain unauthorized.
- Architect-authorized FP32 `person-detection-0202` XML/BIN artifacts were downloaded under ignored canonical `perception-data/models/person-detection-0202/FP32/`; both match the Open Model Zoo manifest SHA-384 checksums.
- The pinned generic `opencv-python-headless==4.12.0.88` failed both `cv2.dnn.readNet` and `cv2.dnn.readNetFromModelOptimizer` with `Backend (plugin) is not available: 'openvino'`. The detector experiment was reverted; no alternate runtime was introduced.
- Architect has now authorized exactly one additional runtime. Isolated `.venv` installation passed with `openvino==2026.3.1`, `opencv-python-headless==4.12.0.88`, `psutil==7.0.0`, and transitive `numpy==2.2.6` / `openvino-telemetry==2025.2.0`.
- Host verification: Windows 11 x64, AMD Ryzen 7 5800XT, Python 3.12.10, OpenVINO devices `CPU`, `GPU.0`, and `GPU.1`.
- OpenVINO loaded and compiled the checksummed FP32 model on CPU; bounded zero-array inference returned `(1, 1, 200, 7)`.
- The production detector now uses OpenVINO behind the existing detector contract, with model paths configurable and explicit load/decode failures. The IoU tracker remains unchanged. Focused tests pass 11/11 after the calibration diagnostic additions.
- Confirmed-empty Stage A run: 205 processed online observations over approximately 20.6 seconds, all zero-person, with no false-person detections; 8.095 processed FPS and 0 dropped frames.
- Confirmed-one-person Stage B run: the operator confirmed one person remained continuously visible. The service processed 827 online observations over approximately 83.9 seconds at 9.154 FPS, with 480 zero-detection observations, 318 exactly-one observations, 29 multi-detection observations, and a maximum of 2 simultaneous detections. The unchanged tracker produced 19 unique track IDs, first ID 1, final visible ID 19, 32 visible-ID-set changes, and up to 3 active tracker records. This fails the required one-person quality target.
- Stage C synchronized dropout and Stage E ten-minute soak were not run because the confirmed detector-quality failure reached the directive stop boundary. Multi-person live evidence remains blocked because no second person was available. Camera failure/recovery remains a separate unrun M1 gate.
- Calibration diagnostic capability was added without changing the model, OpenVINO runtime/device, preprocessing, camera path, frame buffer, tracker, or production threshold. It records only raw candidate timestamps, frame sequences, confidences, boxes, and inference timing; raw candidates are never sent to the production tracker.
- Calibration Stage A operator-confirmed empty segment: runner marker `CONFIRMED_EMPTY` at `2026-08-26T16:18:50.151051+00:00`; 303 online observations over 30.639 seconds. At threshold 0.20, false-positive observations were 2/303 (0.660%), maximum 1, with a 0.111-second longest run. Raw confidence percentiles were p50 0.031729, p75 0.040432, p90 0.070170, p95 0.107720, max 0.233231.
- Calibration Stage B operator-confirmed continuous one-person segment: runner marker `CONFIRMED_ONE_PERSON` at `2026-08-26T16:21:28.148642+00:00`, runner end at `2026-08-26T16:22:33.820060+00:00`, and operator confirmation `CONFIRMED_ONE_PERSON — END — CONTINUOUS`; 599 online observations over 60.559 seconds. At threshold 0.40, any detection was 579/599 (96.661%), but 64/599 observations had duplicate/multi-box detections (10.684%) and the longest duplicate run was 0.911 seconds. At 0.45, duplicates fell to 2/599 (0.334%) but recall fell to 534/599 (89.149%). Raw confidence percentiles were p50 0.058726, p75 0.112728, p90 0.323212, p95 0.489522, max 0.943762.
- No tested threshold from 0.10 through 0.50 met both empty false-positive rate <=1% and one-person >=95% recall with rare duplicates. The calibration result is `DETECTOR CALIBRATION FAILED — REPLAN MODEL`.
- Best-candidate bounding-box sanity was not accepted because the installed headless OpenCV build cannot provide `cv2.imshow`; no visual overlay or frame was persisted. This limitation does not weaken the decisive count-based calibration failure.

## Current hypotheses / unknowns
- The original SENTRY disappearance is consistent with a transient Atlas share/filesystem visibility or consistency failure, but deletion versus transient visibility cannot be proven from the surviving evidence.
- The restored checkout is trustworthy for continued project work; the earlier camera result remains preserved in Notion and prior append-only evidence.

## Current blockers
- M1 live acceptance is still open: the current OpenVINO detector/tracker combination has a confirmed one-person quality failure, and camera recovery remains unproven.
- The current detector quality is inadequate for ordinary confirmed office presence sensing; the unchanged tracker cannot be evaluated as a separate bottleneck from this failed detector input.
- A human-confirmed one-person segment was completed; the current OpenVINO detector produced a confirmed quality failure and telemetry-only runs remain non-acceptance evidence.
- Controlled camera failure/recovery remains blocked pending an authorized physical disconnect/reconnect or administrative device-interruption path.
- The original Atlas incident has no proven low-level root cause; no broad storage repair or migration was attempted.
- `person-detection-0202` cannot meet the required empty/one-person separation at any tested confidence threshold in the operator-confirmed office segments. The Architect must decide whether to authorize the already-identified `person-detection-0303` fallback; do not implement it under the completed calibration directive.

## Latest recorded evidence
- `OUTCOME-SENTRY-REPO-RECOVERY-001`: fresh clone at `73b43f3`, `git fsck` passed, Authority/source checks passed, automated tests 5/5 passed, canonical reread stable, and local/remote `main` matched.
- `OUTCOME-SENTRY-M1-LIVE-QUALIFICATION-001`: human-visible single-person scene observed; detector/tracker produced severe track churn and false-positive indicators; performance remained above target; controlled camera recovery was blocked by device-operation access failure.
- `OUTCOME-SENTRY-M1-DETECTOR-REPLAN-001`: official model/license/checksum evidence passed, but generic OpenCV DNN IR loading failed; no production detector change was retained and live Stage A/B/C did not run.
- `OUTCOME-SENTRY-M1-DETECTOR-RUNTIME-001`: OpenVINO implementation target-tested; subsequent confirmed live quality evidence failed the one-person gate.
- `OUTCOME-SENTRY-M1-OPENVINO-LIVE-001`: confirmed-empty baseline passed, confirmed-one-person detector/tracker quality failed decisively, and later stages stopped at the authorized quality boundary.
- `OUTCOME-SENTRY-M1-DETECTOR-CALIBRATION-001`: raw-confidence sweep across operator-confirmed empty and continuous-one-person segments found no acceptable operating threshold; model replan is required.
- `OUTCOME-SENTRY-M0-CODEX-FEASIBILITY-001` and `OUTCOME-SENTRY-M0-CODEX-CONTEXT-OPT-001`: accepted M0 Luna boundary and runtime isolation evidence remain historical and unchanged.

## Current risks
- Treating the recovered checkout or camera path as proof of M1 acceptance would overstate the evidence.
- The Atlas share incident may recur; preserve append-only state and recheck canonical path stability after future writes.
- HOG/tracker telemetry must not be promoted to person-quality acceptance when one known person produces multiple simultaneous tracks and high ID churn.

## Next Architect decision point
Architect must decide whether to authorize the bounded `person-detection-0303` model replan. Preserve the current OpenVINO/runtime and calibration evidence, do not change the tracker from this result, and do not begin M2.

This file is a mutable snapshot. Do not use it to erase historical outcomes or decisions.
