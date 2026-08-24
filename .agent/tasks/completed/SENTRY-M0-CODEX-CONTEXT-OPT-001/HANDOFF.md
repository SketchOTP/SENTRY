# Handoff — SENTRY-M0-CODEX-CONTEXT-OPT-001

## Recommendation

Adopt the isolated temporary runtime for SENTRY event reasoning. It removes the repository's Authority instruction chain from the runtime subprocess and reduces measured input by 5.4% to 5.6%, while preserving the accepted OAuth/Luna/schema/grounding boundary.

Do not release M1 automatically. M1 remains gated on Architect acceptance of this hardening result and a separate M1 authorization.

## Remaining limitation

The measured floor is approximately 18.2k input tokens on this Codex CLI host. The installed skills context remains present, and the CLI exposes no supported smaller runtime-context switch that was justified within the four-call budget. Subscription quota and plan-wide billing remain outside local CLI measurement.

## Closure

- Commit: `fd363e6` — `perf: isolate Codex runtime context`
- Push: successful to `origin/main`
- Notion: SENTRY page updated with before/after measurements and runtime-context architecture.
- M1: not released; remains gated on Architect acceptance and separate authorization.
