# Current Project State

Last updated: 2026-08-24T12:20:27-04:00

## Current stage
M0 — Codex/Luna Feasibility

## Current objective
Determine whether an OAuth-authenticated Codex CLI turn using GPT-5.6 Luna only can consume a genuine synthetic SENTRY `person.entered` event and return bounded grounded structured reasoning on demand before perception work begins.

## Active directive
SENTRY-M0-CODEX-FEASIBILITY-001 — target-tested; awaiting Architect acceptance of the bounded reasoning boundary.

## Current verified state
- The repository is documentation-first with no application source, tests, dependency manifest, or runtime implementation.
- The authoritative checkout is clean on `main` at baseline `63376fe` before this bootstrap.
- SENTRY V0.1 is constrained to one office on the existing Windows PC with one webcam, microphone, speakers, local storage, and available CPU/GPU resources.
- DAWN is the preferred assistant foundation under evaluation; Xiaomi Miloco is an architectural reference only.
- The Authority 3.0 root router, project state, reusable workflow, references, and governance task record are installed by this change.
- DAWN upstream was inspected at `a0c0b13c65f1b02a3416d846f6a0d331244eee9d`.
- DAWN documents x86_64 Linux server mode and Docker deployment, but no supported external trusted physical-event ingress was found.
- The host has Codex CLI `0.145.0`, ChatGPT OAuth login, and an installed bundled Python runtime.
- `codex exec --ephemeral --json --output-schema` is the supported local programmatic surface used by the proof.
- The bridge forces `gpt-5.6-luna`, accepts only explicit effort values, removes API-key environment variables from the child, and returns one bounded JSON result or a structured error.
- Low and high Luna turns independently grounded synthetic `person.entered` events and reported per-turn token usage.

## Current hypotheses / unknowns
- A clean SENTRY-to-DAWN environmental-event boundary remains unavailable in the inspected upstream.
- A future DAWN upstream change, a maintained fork, or a different assistant foundation would be a strategic choice, not an implicit M0 workaround.
- No runtime capability, camera behavior, identity accuracy, persistence behavior, assistant grounding, or proactive speech is established.

## Current blockers
- DAWN WebSocket and satellite inputs represent user/conversational text.
- DAWN MQTT device relay converts returned device data into a `[DEVICE DATA]` user-role turn.
- DAWN SAGE attention consumes a fixed compiled telemetry catalog; its context injection is optional context for an existing session and is not an external event-trigger API.
- DAWN tool extension requires source/build registration, which violates the no-fork/no-substantial-modification boundary for this spike.
- ChatGPT OAuth is usable for this trusted local run, but Codex documentation cautions that general unattended automation commonly uses API keys; future deployment must keep credentials private and must not expose the bridge to untrusted inputs.

## Latest accepted evidence
- `OUTCOME-SENTRY-AUTHORITY-BOOTSTRAP-001`: Authority tree and SENTRY state initialized; structural validation target-tested.
- `OUTCOME-SENTRY-M0-DAWN-FEASIBILITY-001`: Supported synthetic physical-event path decisively blocked by upstream boundary inspection; evidence is E1_OBSERVED.
- `OUTCOME-SENTRY-M0-CODEX-FEASIBILITY-001`: OAuth-only Luna bounded event-to-reasoning proof passed at low and high effort; evidence is E3_TARGET_TESTED.

## Current risks
- Treating documentation or governance presence as runtime capability would overstate the project state.
- DAWN integration and licensing details may alter the M0 implementation choice after investigation.

## Next Architect decision point
Choose whether to accept the bounded Codex/Luna reasoning boundary and authorize the next narrowly scoped SENTRY milestone. Keep Luna-only selection, event gating, duplicate suppression, call-rate limits, bounded context, and usage observability as required architecture rules. Do not begin webcam/perception work until this M0 result is accepted.

This file is a mutable snapshot. Do not use it to erase historical outcomes or decisions.
