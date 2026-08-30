# SENTRY-V0.2-ROUTINE-STATISTICS-001

## Objective

Implement and qualify a transparent, metadata-only routine-statistics layer
over trusted SENTRY session and event history. Keep derived routine output
rebuildable and gated from physical state, M4 conversation, and M5 policy.

## Acceptance boundary

The routine foundation is accepted when schema-v5 persistence, circular clock
statistics, robust duration/interval statistics, evidence maturity, exclusion
provenance, localhost API exposure, Atlas restore, idempotent refresh, and the
systemd timer are regression-protected. Sparse production history may remain
`insufficient`.
