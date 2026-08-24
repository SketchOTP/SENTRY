# Current Project State

Last updated: 2026-08-24T11:12:06-04:00

## Current stage
M0 — Bootstrap + DAWN Integration Feasibility

## Current objective
Determine whether the least invasive supported DAWN boundary can carry a genuine synthetic SENTRY `person.entered` event into grounded assistant reasoning and optional speech before perception work begins.

## Active directive
SENTRY-M0-DAWN-FEASIBILITY-001 — BLOCKED at the supported-boundary gate; awaiting Architect decision.

## Current verified state
- The repository is documentation-first with no application source, tests, dependency manifest, or runtime implementation.
- The authoritative checkout is clean on `main` at baseline `63376fe` before this bootstrap.
- SENTRY V0.1 is constrained to one office on the existing Windows PC with one webcam, microphone, speakers, local storage, and available CPU/GPU resources.
- DAWN is the preferred assistant foundation under evaluation; Xiaomi Miloco is an architectural reference only.
- The Authority 3.0 root router, project state, reusable workflow, references, and governance task record are installed by this change.
- DAWN upstream was inspected at `a0c0b13c65f1b02a3416d846f6a0d331244eee9d`.
- DAWN documents x86_64 Linux server mode and Docker deployment, but no supported external trusted physical-event ingress was found.

## Current hypotheses / unknowns
- A clean SENTRY-to-DAWN environmental-event boundary remains unavailable in the inspected upstream.
- A future DAWN upstream change, a maintained fork, or a different assistant foundation would be a strategic choice, not an implicit M0 workaround.
- No runtime capability, camera behavior, identity accuracy, persistence behavior, assistant grounding, or proactive speech is established.

## Current blockers
- DAWN WebSocket and satellite inputs represent user/conversational text.
- DAWN MQTT device relay converts returned device data into a `[DEVICE DATA]` user-role turn.
- DAWN SAGE attention consumes a fixed compiled telemetry catalog; its context injection is optional context for an existing session and is not an external event-trigger API.
- DAWN tool extension requires source/build registration, which violates the no-fork/no-substantial-modification boundary for this spike.

## Latest accepted evidence
- `OUTCOME-SENTRY-AUTHORITY-BOOTSTRAP-001`: Authority tree and SENTRY state initialized; structural validation target-tested.
- `OUTCOME-SENTRY-M0-DAWN-FEASIBILITY-001`: Supported synthetic physical-event path decisively blocked by upstream boundary inspection; evidence is E1_OBSERVED.

## Current risks
- Treating documentation or governance presence as runtime capability would overstate the project state.
- DAWN integration and licensing details may alter the M0 implementation choice after investigation.

## Next Architect decision point
Choose whether to pursue an explicit DAWN upstream change/fork or select another assistant foundation. Do not authorize webcam/perception work until a supported event-to-reasoning boundary is accepted.

This file is a mutable snapshot. Do not use it to erase historical outcomes or decisions.
