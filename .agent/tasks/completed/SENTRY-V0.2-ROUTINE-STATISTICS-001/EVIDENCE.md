# Evidence

- Starting baseline: `49662bc5ff314cc2c5d28a09cb704ad5267c33a3`, clean `main`
  matching `origin/main`.
- Runtime timezone: `America/New_York`; UTC remains the storage timestamp
  basis. Analysis window is 56 days.
- Active database: `/home/sketch/.local/share/sentry/sentry.db` on local ext4.
  Atlas mirror remains on `fuse.sshfs` and is never opened as the live DB.
- Schema migration: version 5; local and Atlas `PRAGMA integrity_check` both
  returned `ok`.
- Production refresh: 40 latest snapshots (four routine types × ten scopes),
  all `insufficient`, with no seeded history. Observed source evidence remains
  sparse: three observed starts, two trustworthy completed durations, two
  primary-user confirmations, and no interruption-free absence interval.
- Refresh idempotence: corrected unchanged-source refresh returned `skipped`
  with zero writes.
- Resident integration: `sentry-routines.timer` enabled/active; oneshot
  completed successfully; perception, state API, and proactive services were
  enabled/active during verification.
- API: `/v1/routines` returned 40 latest privacy-safe snapshots; `/health`
  reported schema 5, database available, and Atlas mirror `ok`.
- Tests: focused routine tests 17/17; combined routine/store/mirror/resident
  tests 38/38; full Ubuntu regression 120/120 with one known fork deprecation
  warning.
- No raw frames, audio, embeddings, biometric prototypes, or Luna calls were
  introduced by the routine layer.
