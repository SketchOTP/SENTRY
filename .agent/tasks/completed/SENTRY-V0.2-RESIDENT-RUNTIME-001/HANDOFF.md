# Handoff — SENTRY-V0.2-RESIDENT-RUNTIME-001

## Verdict

**V0.2 RESIDENT RUNTIME QUALIFIED**

The accepted office-only V0.1 stack now runs under native Ubuntu user-systemd supervision. The qualification passed the 900-second supervised probe, bounded restart/isolation checks, clean stop/start, persistence integrity checks, and the full regression suite.

## Accepted operational commands

Install or refresh units and the local production config:

```bash
/home/sketch/.venvs/sentry-ubuntu/bin/python tools/sentry_install_user_services.py
```

Inspect the resident stack:

```bash
systemctl --user --no-pager --full status sentry-perception.service sentry-state-api.service sentry-proactive.service
curl -fsS http://127.0.0.1:48174/health
```

Stop/start the complete stack:

```bash
systemctl --user stop sentry-proactive.service sentry-state-api.service sentry-perception.service
systemctl --user start sentry-perception.service sentry-state-api.service sentry-proactive.service
```

Disable startup only when deliberately changing the resident configuration:

```bash
systemctl --user disable sentry-proactive.service sentry-state-api.service sentry-perception.service
```

## Important boundary

`Linger=no` means the units start with the authenticated `sketch` user session. This evidence does not claim boot-before-login operation. Local SQLite is authoritative; Atlas is a snapshot mirror and is never opened as the live DB. Reactive voice remains explicit rather than continuously listening.

## Next work

No active implementation directive remains for V0.2 resident runtime. Routine statistics/learning is the next candidate phase, but it requires a new Architect directive. Do not add routines, sensors, rooms, or adaptive behavior as part of this task.
