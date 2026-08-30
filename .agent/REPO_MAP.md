# Repository Map

Last verified against: `main` and working-tree inspection on 2026-08-30.

## Entry points
- `README.md` — concise project contract, V0.1 boundary, milestones, and current status.
- `docs/PROJECT_SCOPE.md` — formal product scope, architecture guidance, acceptance targets, and handoff rules.

## Major modules / packages
- `perception/sentry_perception.py` — observation-only local webcam service, OpenVINO YOLOX-S detector, bounded latest-frame buffer, two-stage IoU tracker, health states, metrics, and metadata persistence wiring.
- `perception/storage_mirror.py` — local-filesystem SQLite guard, Atlas snapshot publication, integrity validation, and local recovery/quarantine helpers.
- `perception/identity.py` — OpenCV Zoo YuNet/SFace loading, face quality/track association, conservative temporal matching, and in-memory enrollment prototype construction.
- `perception/calibration.py`, `tools/m1_detector_calibration.py`, and `tools/m1_0303_raw_reconcile.py` — metadata-only raw-candidate/raw-output capture and offline threshold evaluation used by the 0202 and 0303 detector gates; no raw frames are written.
- `perception/calibration.py` and `tools/m1_detector_calibration.py` — metadata-only raw-candidate capture and offline confidence-threshold evaluation for the bounded M1 calibration directive; no frames are persisted and candidates do not enter the tracker.
- `perception/config.example.json` — configurable camera, detector, and tracker settings.
- `tests/test_sentry_perception.py` — deterministic M1 contract tests.
- `tools/sentry_codex_bridge.py` — bounded one-event OAuth Codex/Luna adapter; no background worker or persistence.
- `tools/sentry_identity_evaluate.py` and `tools/sentry_identity_live_verify.py` — metadata-only held-out and live identity qualification runners; no frames or embeddings are written.
- `tools/sentry_codex_response.schema.json` — structured output contract for the bounded bridge.
- `tools/sentry_codex_bridge.py` — bounded OAuth/Luna launcher reused by the event proof and grounded query path; runtime calls execute from a temporary non-repository cwd and copy the selected schema to an absolute local path.
- `perception/voice.py`, `tools/sentry_voice.py`, and `tools/sentry_kokoro_worker.py` — bounded push-to-talk PipeWire/in-memory Whisper `tiny.en` STT adapter reusing M4 `sentry_ask.py` and an installed local Kokoro runtime with local PipeWire playback; no audio persistence or continuous Luna calls.
- `deploy/systemd/user/` — native user-systemd units and resident-runtime operations guide for perception, the localhost API, and continuous proactive polling.
- `tools/sentry_install_user_services.py` — reproducible installer for the local mode-600 production config and enabled user units.
- `tools/sentry_resident_live_probe.py` — bounded metadata-only live probe for service health, API health, Atlas mirror status, and perception heartbeat.
- `perception/routines.py` — standard-library routine feature extraction, circular clock-time/robust duration statistics, evidence exclusions, and maturity gates.
- `tools/sentry_routines.py` — bounded routine snapshot refresh/show CLI over the local SQLite source.
- `deploy/systemd/user/sentry-routines.service` and `sentry-routines.timer` — independent six-hour derived-statistics refresh.
- `tests/test_routines.py` — metadata-only routine statistics, schema-v5, API, Atlas restore, idempotence, DST, and privacy tests.

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

The M2 persistence/session/API slice is implemented in `perception/presence_store.py` and `tools/sentry_state_api.py`; active SQLite operations are local to the Ubuntu host and complete snapshots are mirrored to Atlas by `perception/storage_mirror.py`. M3 identity is implemented in `perception/identity.py` and the enrollment/admin tools. M4 grounded conversation is implemented in `tools/sentry_grounding.py` and `tools/sentry_ask.py`. M5 restrained proactivity is implemented in `perception/proactive.py`, `tools/sentry_proactive.py`, and `tools/sentry_m5_live.py`; its physical event-to-action qualification is accepted. V0.2 resident supervision is implemented in `deploy/systemd/user/` and the resident-runtime tools. V0.2 routine statistics are implemented in `perception/routines.py` with schema-v5 persistence in `perception/presence_store.py`, the `/v1/routines` API, and scheduled refresh units.
