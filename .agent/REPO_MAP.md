# Repository Map

Last verified against: `main` and working-tree inspection on 2026-08-24.

## Entry points
- `README.md` — concise project contract, V0.1 boundary, milestones, and current status.
- `docs/PROJECT_SCOPE.md` — formal product scope, architecture guidance, acceptance targets, and handoff rules.

## Major modules / packages
- None. No application source exists at bootstrap.
- `tools/sentry_codex_bridge.py` — bounded one-event OAuth Codex/Luna adapter; no background worker or persistence.
- `tools/sentry_codex_response.schema.json` — structured output contract for the bounded bridge.
- `tools/sentry_codex_bridge.py` — one bounded OAuth/Luna event adapter; runtime calls execute from a temporary non-repository cwd and copy the schema to an absolute local path.

## Important interfaces / contracts
- `AGENTS.md` — Authority repository router.
- `.agent/` — project state/history.
- `.agents/skills/authority/` — reusable Authority workflow and contracts.

## Tests
- No general runtime suite. M0 acceptance runs are recorded in `.agent/tasks/completed/SENTRY-M0-CODEX-FEASIBILITY-001/EVIDENCE.md` and `.agent/tasks/active/SENTRY-M0-CODEX-CONTEXT-OPT-001/EVIDENCE.md`.

## Generated / cache / build areas
- None in the tracked repository at bootstrap. Future local runtime data, recordings, enrollment data, databases, caches, and model weights must remain outside Git.

## Governance / agent files
- `AGENTS.md`
- `.agents/`
- `.agent/`

## Known sensitive/high-risk areas
- Future biometric enrollment and camera data — must remain local, excluded from Git, and governed by explicit privacy boundaries.
- Future DAWN integration — upstream behavior and GPLv3 licensing must be verified before dependency, derivation, or fork decisions.
- Codex OAuth credentials and per-turn usage — keep credentials private; treat local OAuth proof as trusted-host evidence only.

This map is intentionally not an application inventory; implementation has not begun.
