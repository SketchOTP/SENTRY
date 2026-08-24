# Repository Map

Last verified against: `63376fe` and working-tree inspection on 2026-08-24.

## Entry points
- `README.md` — concise project contract, V0.1 boundary, milestones, and current status.
- `docs/PROJECT_SCOPE.md` — formal product scope, architecture guidance, acceptance targets, and handoff rules.

## Major modules / packages
- None. No application source exists at bootstrap.

## Important interfaces / contracts
- `AGENTS.md` — Authority repository router.
- `.agent/` — project state/history.
- `.agents/skills/authority/` — reusable Authority workflow and contracts.

## Tests
- None present. No runtime or test suite has been implemented.

## Generated / cache / build areas
- None in the tracked repository at bootstrap. Future local runtime data, recordings, enrollment data, databases, caches, and model weights must remain outside Git.

## Governance / agent files
- `AGENTS.md`
- `.agents/`
- `.agent/`

## Known sensitive/high-risk areas
- Future biometric enrollment and camera data — must remain local, excluded from Git, and governed by explicit privacy boundaries.
- Future DAWN integration — upstream behavior and GPLv3 licensing must be verified before dependency, derivation, or fork decisions.

This map is intentionally not an application inventory; implementation has not begun.
