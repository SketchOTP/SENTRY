# Repository Map

Last verified against: `main` and working-tree inspection on 2026-08-24.

## Entry points
- `README.md` — concise project contract, V0.1 boundary, milestones, and current status.
- `docs/PROJECT_SCOPE.md` — formal product scope, architecture guidance, acceptance targets, and handoff rules.

## Major modules / packages
- `perception/sentry_perception.py` — observation-only local webcam service, OpenVINO `person-detection-0303` detector, bounded latest-frame buffer, two-stage IoU tracker, health states, and metrics.
- `perception/calibration.py`, `tools/m1_detector_calibration.py`, and `tools/m1_0303_raw_reconcile.py` — metadata-only raw-candidate/raw-output capture and offline threshold evaluation used by the 0202 and 0303 detector gates; no raw frames are written.
- `perception/calibration.py` and `tools/m1_detector_calibration.py` — metadata-only raw-candidate capture and offline confidence-threshold evaluation for the bounded M1 calibration directive; no frames are persisted and candidates do not enter the tracker.
- `perception/config.example.json` — configurable camera, detector, and tracker settings.
- `tests/test_sentry_perception.py` — deterministic M1 contract tests.
- `tools/sentry_codex_bridge.py` — bounded one-event OAuth Codex/Luna adapter; no background worker or persistence.
- `tools/sentry_codex_response.schema.json` — structured output contract for the bounded bridge.
- `tools/sentry_codex_bridge.py` — one bounded OAuth/Luna event adapter; runtime calls execute from a temporary non-repository cwd and copy the schema to an absolute local path.

## Important interfaces / contracts
- `AGENTS.md` — Authority repository router.
- `.agent/` — project state/history.
- `.agents/skills/authority/` — reusable Authority workflow and contracts.

## Tests
- `python -m unittest discover -s tests -v` — M1 deterministic contracts.
- M0 acceptance runs are recorded in `.agent/tasks/completed/`.

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

The M2 persistence/session/API slice is implemented in `perception/presence_store.py` and `tools/sentry_state_api.py`; restart-aware qualification remains blocked until the Atlas SQLite storage topology is resolved under the active directive. Identity and assistant integration remain later milestones.
