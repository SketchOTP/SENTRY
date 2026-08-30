# Evidence — SENTRY-V0.2-RESIDENT-RUNTIME-001

## Result

**V0.2 RESIDENT RUNTIME QUALIFIED**

Starting SHA: `9a5ae0c341d06541fde43cbbe5fbf32f9945ce28`

## Host and topology

- Ubuntu user: `sketch`.
- Canonical checkout: `/srv/ATLAS/100_ACTIVE/Projects/SENTRY`.
- Atlas mount: `/srv/ATLAS`, `atlas:/srv/ATLAS`, `fuse.sshfs`.
- Live SQLite: `/home/sketch/.local/share/sentry/sentry.db` on local ext4. SQLite never opened the Atlas copy as the live database.
- Atlas mirror: `/srv/ATLAS/100_ACTIVE/Projects/SENTRY/perception-data/runtime/backups/sentry.db`.
- User manager: active; `Linger=no`. Startup is therefore tied to the authenticated user session; no boot-before-login claim is made.

## Resident topology

Enabled native user-systemd units:

- `sentry-perception.service`
- `sentry-state-api.service`
- `sentry-proactive.service`

All use `Restart=on-failure`, `RestartSec=10s`, `StartLimitBurst=5`, and `StartLimitIntervalSec=300s`. Perception publishes a metadata-only heartbeat. Proactive watch mode polls once per second with bounded waiting and exits cleanly on SIGTERM. Reactive voice remains explicit and is not continuous.

Production configuration is `/home/sketch/.config/sentry/config.json`, mode `0600`; it was created once from the checked-in example with proactivity enabled and does not contain secrets.

## Automated validation

- Focused resident-runtime tests: **6/6 passed**.
- Full Ubuntu regression before and after final documentation changes: **102/102 passed**; the only output was a known non-failing multiprocessing deprecation warning.
- `py_compile` passed.
- `git diff --check` passed.
- Service unit command paths, localhost API binding, watch cadence, clean stop, configuration preservation, and privacy boundaries are covered.

## 15-minute supervised live proof

Probe: `tools/sentry_resident_live_probe.py --duration-seconds 900 --interval-seconds 30`

- Duration: `900.0` seconds.
- Samples: `30`.
- Probe failures: `[]`.
- All three units active at the final sample and throughout the probe.
- API: healthy, local DB available, schema 4, Atlas mirror `ok`.
- Final perception telemetry: V4L2/MJPEG, 1280x720, configured 15 FPS, `7.607` processed FPS, `115.696 ms` median latency, `134.015 ms` p95 latency.
- No detector, identity, persistence, mirror, camera-read, or unhandled runtime error.
- No raw frames, audio, embeddings, biometric prototypes, or secrets were persisted.
- Continuous perception Luna calls: `0`.

## Failure/restart isolation

- API restart and SIGKILL recovery returned the localhost health endpoint after bounded systemd restart; perception remained running.
- Proactive restart and SIGKILL recovery produced a new process with no additional proactive action or duplicate delivery.
- Perception restart and SIGKILL recovery returned the camera online, preserved the database, added no room entry/exit transition, and preserved zero open sessions.
- Clean stop left all units inactive with no resident component processes. Starting the enabled units restored the stack.
- Supervisor policy was verified as `Restart=on-failure`, 10-second restart delay, five-minute start-limit interval, and burst five.

## Persistence and truthfulness

- Local and Atlas SQLite copies both passed `PRAGMA integrity_check=ok`.
- Both copies had schema 4 and matching logical content: 43 events, zero open sessions, and one proactive action at the final qualification check.
- No persistence or Atlas mirror error occurred.
- Service restart was not converted into a physical entry or exit.
- The one-open-session invariant remained intact.

## Scope boundary

This result qualifies resident supervision only. YOLOX, identity, M2 storage, M4 grounding, M5 policy, reactive voice, and privacy boundaries were preserved. Routine statistics/learning, continuous listening, new models/sensors, additional rooms, and broader household expansion remain outside this directive.
