# SENTRY-M1-PERCEPTION-001

## Objective

Implement and prove the first local perception layer: Windows webcam capture, local person detection, multi-person temporary tracking, explicit camera health, and structured observations.

## Hard boundaries

- Zero Codex/Luna calls from the continuous perception loop.
- No identity recognition, persistence, sessions, entry/exit semantics, local API, voice, DAWN, or M2 behavior.
- No raw frame persistence by default.
- No new hardware and no cloud video processing.

## Evidence target

E3_TARGET_TESTED requires automated contract tests plus live Windows evidence from the real office webcam. If the webcam cannot be opened, the live portion must remain BLOCKED/NOT RUN and M1 cannot be accepted.
