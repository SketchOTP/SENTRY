# Current Project State

Last updated: 2026-08-24T13:35:00-04:00

## Current stage
M1 — Local Windows Perception

## Current objective
Implement and validate the first local observation-only Windows perception layer: bounded webcam capture, local person detection, temporary multi-person tracking, explicit camera health, and structured observations.

## Active directive
SENTRY-M1-PERCEPTION-001 — implementation target-tested; live camera acceptance blocked.

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
- Repo-root baseline measured 19,308 input tokens for a low-effort event. An isolated temporary runtime measured 18,266 input tokens for the same event, and the final bridge measured 18,223 input tokens for a second event.
- Isolation is now adopted only for the runtime reasoning subprocess: a fresh temporary cwd, `--skip-git-repo-check`, and an absolute copied schema path. Development Codex sessions remain governed by the SENTRY repository `AGENTS.md`.
- M0 Codex/Luna architecture and context optimization are accepted. Codex/Luna remains on-demand only; continuous perception makes zero runtime calls.
- M1 now has a bounded local implementation using OpenCV HOG, a SENTRY-owned two-stage IoU tracker, and a size-one latest-frame buffer. No identity, persistence, sessions, semantic entry/exit events, or raw-frame storage were added.
- Host evidence: NexiGo N60 FHD Webcam enumerates, but OpenCV 4.12.0 could not open camera index 0 through Any, Media Foundation, or DirectShow. The service reports `degraded` startup and `offline / camera_open_failed`, never observed empty.

## Current hypotheses / unknowns
- A clean SENTRY-to-DAWN environmental-event boundary remains unavailable in the inspected upstream.
- A future DAWN upstream change, a maintained fork, or a different assistant foundation would be a strategic choice, not an implicit M0 workaround.
- No live camera capture, person detection, tracking, recovery, FPS, or 10-minute soak evidence is established. Identity, persistence, assistant grounding, and proactive speech remain unimplemented.

## Current blockers
- The actual office webcam cannot currently be opened by the Windows OpenCV capture stack. M1 live acceptance is blocked until device access is restored.
- DAWN WebSocket and satellite inputs represent user/conversational text.
- DAWN MQTT device relay converts returned device data into a `[DEVICE DATA]` user-role turn.
- DAWN SAGE attention consumes a fixed compiled telemetry catalog; its context injection is optional context for an existing session and is not an external event-trigger API.
- DAWN tool extension requires source/build registration, which violates the no-fork/no-substantial-modification boundary for this spike.
- ChatGPT OAuth is usable for this trusted local run, but Codex documentation cautions that general unattended automation commonly uses API keys; future deployment must keep credentials private and must not expose the bridge to untrusted inputs.

## Latest recorded evidence
- `OUTCOME-SENTRY-AUTHORITY-BOOTSTRAP-001`: Authority tree and SENTRY state initialized; structural validation target-tested.
- `OUTCOME-SENTRY-M0-DAWN-FEASIBILITY-001`: Supported synthetic physical-event path decisively blocked by upstream boundary inspection; evidence is E1_OBSERVED.
- `OUTCOME-SENTRY-M0-CODEX-FEASIBILITY-001`: OAuth-only Luna bounded event-to-reasoning proof passed at low and high effort; evidence is E3_TARGET_TESTED; accepted by Architect.
- `OUTCOME-SENTRY-M0-CODEX-CONTEXT-OPT-001`: isolated runtime context reduced measured input by 5.4% to 5.6% and preserved grounding/schema behavior; evidence is E3_TARGET_TESTED; Architect acceptance is pending.
- `OUTCOME-SENTRY-M1-PERCEPTION-001`: automated local perception contracts passed; actual webcam open failed across Any, Media Foundation, and DirectShow; evidence is E2_TARGET_TESTED with live criteria BLOCKED/NOT RUN.

## Current risks
- Treating documentation or governance presence as runtime capability would overstate the project state.
- DAWN integration and licensing details may alter the M0 implementation choice after investigation.
- OpenCV HOG has not been live-qualified on this camera, and no detector/tracker performance claim is made until physical access is restored.

## Next Architect decision point
Restore or authorize replacement access for the office webcam, then rerun the live M1 gate. Do not accept M1 or begin M2 until visible-person detection, stable/multiple tracking, dropout/recovery, useful FPS, and the 10-minute run are evidenced on the actual host.

This file is a mutable snapshot. Do not use it to erase historical outcomes or decisions.
