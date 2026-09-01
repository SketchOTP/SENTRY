# SENTRY resident runtime

The accepted V0.1 stack can run continuously as three native systemd user
services:

- `sentry-perception.service` — local camera, presence, identity, and SQLite writes.
- `sentry-state-api.service` — localhost-only state/history API.
- `sentry-proactive.service` — bounded persisted-event polling with accepted M5 dedupe and policy.
- `sentry-routines.timer` — derived routine-statistics refresh every six hours,
  with an initial two-minute delay after the user manager starts.
- `sentry-weather.timer` — independent NWS weather-context refresh every ten
  minutes, with an initial five-minute delay after the user manager starts.
- `sentry-voice.service` — optional always-available local microphone listener.
  It is installed but remains disabled unless the local mode-0600 config sets
  `voice.always_on_enabled` to `true`.

Perception publishes a small metadata-only heartbeat at
`perception-data/runtime/health/perception.json`; it contains process/camera
and performance counters, never frames or audio.

Install from the canonical checkout with the accepted Ubuntu Python environment:

```bash
/home/sketch/.venvs/sentry-ubuntu/bin/python tools/sentry_install_user_services.py
```

Install or refresh the dedicated Codex-native SENTRY profile before enabling
always-on voice:

```bash
/home/sketch/.venvs/sentry-ubuntu/bin/python tools/sentry_codex_profile.py install
/home/sketch/.venvs/sentry-ubuntu/bin/python tools/sentry_codex_profile.py status
codex --profile sentry mcp list
```

The generated profile is mode `0600` and points to the local SENTRY MCP server.
It is required by both push-to-talk and always-on natural-language requests.

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
systemctl --user is-enabled sentry-routines.timer
systemctl --user --no-pager --full status sentry-routines.timer sentry-routines.service
systemctl --user is-enabled sentry-weather.timer
systemctl --user --no-pager --full status sentry-weather.timer sentry-weather.service
systemctl --user is-enabled sentry-voice.service
systemctl --user --no-pager --full status sentry-voice.service
python tools/sentry_voice_status.py
curl --fail http://127.0.0.1:48174/health
journalctl --user -u sentry-perception.service -u sentry-state-api.service -u sentry-proactive.service --since today
```

Stopping the resident stack without leaving orphan processes:

```bash
systemctl --user stop sentry-proactive.service sentry-state-api.service sentry-perception.service
systemctl --user stop sentry-voice.service
```

Disable autostart only when intentionally changing the deployment:

```bash
systemctl --user disable sentry-proactive.service sentry-state-api.service sentry-perception.service
```

The live database remains local at `~/.local/share/sentry/sentry.db`; complete
SQLite snapshots continue to mirror to the canonical Atlas runtime backup path.
No raw frames, audio, embeddings, or secrets are written by these units.

Routine statistics are refreshed by `sentry-routines.service` through
`sentry-routines.timer`; derived snapshots are stored in the same local SQLite
database and mirrored through the existing M2 backup path. Routine refresh is
independent of perception and the API, and its sparse-data result may
legitimately remain `insufficient`.

Weather refresh is independent of all resident services. It is enabled only when the
local mode-0600 production config explicitly sets `weather.enabled` and supplies latitude
and longitude. Without those coordinates, `sentry_weather.py refresh` reports
`WEATHER LOCATION CONFIG REQUIRED`; it does not infer a location or use a public test
coordinate. Weather snapshots are stored in local SQLite and mirrored to Atlas as complete
snapshots, never opened live on the SSHFS mount.
