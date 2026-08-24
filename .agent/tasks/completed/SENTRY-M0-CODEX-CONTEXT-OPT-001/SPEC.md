# SENTRY-M0-CODEX-CONTEXT-OPT-001

## Objective

Reduce and characterize per-event Codex/Luna input overhead without weakening SENTRY Authority or changing the Luna-only reasoning boundary.

## Required boundary

`SENTRY event -> OAuth Codex -> GPT-5.6 Luna -> structured grounded response`

Runtime event reasoning must execute only on demand, in a bounded ephemeral turn, outside the SENTRY repository context.

## Exclusions

- No model change, Terra, Sol, webcam, perception, M1, voice, DAWN, OpenClaw, persistence, hardware, or product expansion.
- Do not move or weaken SENTRY governance.
- Do not exceed four successful Luna model turns for this directive.

## Acceptance

- Retain the repo-root baseline.
- Test an isolated runtime with the same semantic event.
- Preserve ChatGPT OAuth, explicit `gpt-5.6-luna`, physical-event provenance, schema validity, and grounding.
- Measure input/output/reasoning tokens and the practical observed floor.
- Adopt isolation if it reduces context without unsupported hacks.
- Validate failure handling, idle behavior, scoped diff, records, Notion, GitHub, and clean final state.

