# SENTRY resident runtime

The accepted V0.1 stack can run continuously as three native systemd user
services:

- `sentry-perception.service` — local camera, presence, identity, and SQLite writes.
- `sentry-state-api.service` — localhost-only state/history API.
- `sentry-proactive.service` — bounded persisted-event polling with accepted M5 dedupe and policy.

Perception publishes a small metadata-only heartbeat at
`perception-data/runtime/health/perception.json`; it contains process/camera
and performance counters, never frames or audio.

Install from the canonical checkout with the accepted Ubuntu Python environment:

```bash
/home/sketch/.venvs/sentry-ubuntu/bin/python tools/sentry_install_user_services.py
```

The installer creates `~/.config/sentry/config.json` once from the checked-in
example, enables proactivity for the resident deployment, installs the units
under `~/.config/systemd/user/`, and starts them. An existing production config
is never overwritten; it must already have proactivity enabled.

The user-manager startup condition is the authenticated `sketch` desktop/user
session. The units are enabled for `default.target`; they are not a system
service and do not require root. `loginctl show-user "$USER" -p Linger` should
be checked separately if boot-before-login persistence is required.

Useful status checks:

```bash
systemctl --user is-enabled sentry-perception.service sentry-state-api.service sentry-proactive.service
systemctl --user --no-pager --full status sentry-perception.service sentry-state-api.service sentry-proactive.service
curl --fail http://127.0.0.1:48174/health
journalctl --user -u sentry-perception.service -u sentry-state-api.service -u sentry-proactive.service --since today
```

Stopping the resident stack without leaving orphan processes:

```bash
systemctl --user stop sentry-proactive.service sentry-state-api.service sentry-perception.service
```

Disable autostart only when intentionally changing the deployment:

```bash
systemctl --user disable sentry-proactive.service sentry-state-api.service sentry-perception.service
```

The live database remains local at `~/.local/share/sentry/sentry.db`; complete
SQLite snapshots continue to mirror to the canonical Atlas runtime backup path.
No raw frames, audio, embeddings, or secrets are written by these units.
