# Current Project State

Last updated: 2026-08-25T21:46:40-04:00

## Current stage
M1 — Local Windows Perception

## Current objective
Complete the remaining M1 live qualification only after the current detector/tracker quality and camera recovery gates are resolved by Architect direction.

## Active directive
SENTRY-M1-LIVE-QUALIFICATION-001 — partial; live evidence returned to Architect.

## Current verified state
- Canonical path `\\atlas\\ATLAS\\100_ACTIVE\\Projects\\SENTRY` contains a valid Git checkout restored from GitHub after the damaged path was absent on repeated inventory reads.
- `main` and `origin/main` are both `73b43f3398c0dc0738d23d389c2a79b48c5af29d`; the final working tree is clean.
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

## Current hypotheses / unknowns
- The original SENTRY disappearance is consistent with a transient Atlas share/filesystem visibility or consistency failure, but deletion versus transient visibility cannot be proven from the surviving evidence.
- The restored checkout is trustworthy for continued project work; the earlier camera result remains preserved in Notion and prior append-only evidence.

## Current blockers
- M1 live acceptance is still open pending human-confirmed detection/tracking/dropout/recovery evidence.
- Current HOG plus IoU tracking evidence is materially inadequate for the observed office scene; Architect decision is required before any detector replan or replacement.
- Controlled camera failure/recovery remains blocked pending an authorized physical disconnect/reconnect or administrative device-interruption path.
- The original Atlas incident has no proven low-level root cause; no broad storage repair or migration was attempted.

## Latest recorded evidence
- `OUTCOME-SENTRY-REPO-RECOVERY-001`: fresh clone at `73b43f3`, `git fsck` passed, Authority/source checks passed, automated tests 5/5 passed, canonical reread stable, and local/remote `main` matched.
- `OUTCOME-SENTRY-M1-LIVE-QUALIFICATION-001`: human-visible single-person scene observed; detector/tracker produced severe track churn and false-positive indicators; performance remained above target; controlled camera recovery was blocked by device-operation access failure.
- `OUTCOME-SENTRY-M1-PERCEPTION-001`: implementation target-tested; live camera gate was later restored but M1 acceptance remains open.
- `OUTCOME-SENTRY-M0-CODEX-FEASIBILITY-001` and `OUTCOME-SENTRY-M0-CODEX-CONTEXT-OPT-001`: accepted M0 Luna boundary and runtime isolation evidence remain historical and unchanged.

## Current risks
- Treating the recovered checkout or camera path as proof of M1 acceptance would overstate the evidence.
- The Atlas share incident may recur; preserve append-only state and recheck canonical path stability after future writes.
- HOG/tracker telemetry must not be promoted to person-quality acceptance when one known person produces multiple simultaneous tracks and high ID churn.

## Next Architect decision point
Architect must choose whether to authorize a detector replan or another bounded M1 investigation. Do not accept M1 or begin M2 from the current evidence.

This file is a mutable snapshot. Do not use it to erase historical outcomes or decisions.
