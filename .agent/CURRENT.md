# Current Project State

Last updated: 2026-08-26T05:59:11-04:00

## Current stage
M1 — Local Windows Perception

## Current objective
Qualify the authorized OpenVINO-backed person detector and unchanged IoU tracker on the actual office camera.

## Active directive
SENTRY-M1-DETECTOR-RUNTIME-001 — IN PROGRESS; OpenVINO runtime and model smoke path pass, live human-confirmed qualification remains pending.

## Current verified state
- Canonical path `\\atlas\\ATLAS\\100_ACTIVE\\Projects\\SENTRY` contains a valid Git checkout restored from GitHub after the damaged path was absent on repeated inventory reads.
- The last committed `main` and `origin/main` state is `12722a08a062225c8832d9ddbb31b63c12b51aee`; runtime integration edits are currently uncommitted pending live qualification.
- `git fsck --full` passed with exit code 0 and no reported errors.
- Authority kernel, reusable skills, perception source, configuration, requirements, documentation, and tests are present.
- Existing automated tests pass 5/5.
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
- The production detector now uses OpenVINO behind the existing detector contract, with model paths configurable and explicit load/decode failures. The IoU tracker remains unchanged. Focused tests pass 9/9.
- Two 30-second camera runs stayed online at 1280x720/15 FPS and approximately 8.2/8.4 processed FPS. They are not human-confirmed acceptance evidence: one run showed 206/254 visible rows and 9 visible IDs; the later run showed 65/259 visible rows and 5 visible IDs. A confirmed one-person segment is still required.

## Current hypotheses / unknowns
- The original SENTRY disappearance is consistent with a transient Atlas share/filesystem visibility or consistency failure, but deletion versus transient visibility cannot be proven from the surviving evidence.
- The restored checkout is trustworthy for continued project work; the earlier camera result remains preserved in Notion and prior append-only evidence.

## Current blockers
- M1 live acceptance is still open pending human-confirmed detection/tracking/dropout/recovery evidence.
- Current HOG plus IoU tracking evidence is materially inadequate for the observed office scene.
- A human-confirmed one-person Stage A segment is still required before judging detector adequacy; telemetry-only runs cannot establish subject presence or false-positive ground truth.
- Controlled camera failure/recovery remains blocked pending an authorized physical disconnect/reconnect or administrative device-interruption path.
- The original Atlas incident has no proven low-level root cause; no broad storage repair or migration was attempted.

## Latest recorded evidence
- `OUTCOME-SENTRY-REPO-RECOVERY-001`: fresh clone at `73b43f3`, `git fsck` passed, Authority/source checks passed, automated tests 5/5 passed, canonical reread stable, and local/remote `main` matched.
- `OUTCOME-SENTRY-M1-LIVE-QUALIFICATION-001`: human-visible single-person scene observed; detector/tracker produced severe track churn and false-positive indicators; performance remained above target; controlled camera recovery was blocked by device-operation access failure.
- `OUTCOME-SENTRY-M1-DETECTOR-REPLAN-001`: official model/license/checksum evidence passed, but generic OpenCV DNN IR loading failed; no production detector change was retained and live Stage A/B/C did not run.
- `OUTCOME-SENTRY-M1-PERCEPTION-001`: implementation target-tested; live camera gate was later restored but M1 acceptance remains open.
- `OUTCOME-SENTRY-M0-CODEX-FEASIBILITY-001` and `OUTCOME-SENTRY-M0-CODEX-CONTEXT-OPT-001`: accepted M0 Luna boundary and runtime isolation evidence remain historical and unchanged.

## Current risks
- Treating the recovered checkout or camera path as proof of M1 acceptance would overstate the evidence.
- The Atlas share incident may recur; preserve append-only state and recheck canonical path stability after future writes.
- HOG/tracker telemetry must not be promoted to person-quality acceptance when one known person produces multiple simultaneous tracks and high ID churn.

## Next Architect decision point
Architect must decide whether to authorize a compatible OpenCV build, OpenVINO Runtime, or another detector path. Do not accept M1 or begin M2 from the current evidence.

This file is a mutable snapshot. Do not use it to erase historical outcomes or decisions.
