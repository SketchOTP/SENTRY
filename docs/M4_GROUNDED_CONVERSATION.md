# M4 — Grounded conversational queries

SENTRY's M4 text surface is `tools/sentry_ask.py`. It accepts one user question,
reads the authoritative localhost API, builds a deterministic metadata-only fact
packet, and makes at most one bounded OAuth-authenticated `gpt-5.6-luna` turn.
Luna phrases supplied facts; it is not given SQLite access and is never the
source of physical truth.

## Runtime

Start the existing localhost API against the local live database:

```bash
/home/sketch/.venvs/sentry-ubuntu/bin/python tools/sentry_state_api.py \
  --database /home/sketch/.local/share/sentry/sentry.db \
  --atlas-mirror /srv/ATLAS/100_ACTIVE/Projects/SENTRY/perception-data/runtime/backups/sentry.db \
  --host 127.0.0.1 --port 48174
```

Ask one question:

```bash
/home/sketch/.venvs/sentry-ubuntu/bin/python tools/sentry_ask.py \
  "Who is in the office?"
```

The query layer requests `/health` first, then `/v1/rooms/office/state`,
`/v1/rooms/office/sessions`, `/v1/persons`, and `/v1/events`. If health or the
database is unavailable, it returns a deterministic unavailable answer without
calling Luna.

## Fact and response contracts

`tools/sentry_grounding.py` allow-lists current state, current people, enrolled
metadata, bounded session fields, selected event provenance, and derived facts
such as current session duration, first primary-user identification, and last
confirmed empty. Each fact has a stable `fact_id` and the packet has an `as_of`
timestamp. Raw frames, embeddings, biometric prototypes, unrestricted rows, and
secrets are excluded.

The structured response in `tools/sentry_grounded_response.schema.json` is:

```json
{
  "answer": "...",
  "grounding": "supported | partial | unavailable",
  "fact_ids": ["current-room-state"],
  "limitations": []
}
```

SENTRY additionally rejects unknown fact IDs, duplicate citations, malformed
fields, and supported/partial responses with no cited facts. Room-session start
and first primary-user identification remain separate facts; the assistant must
not turn one into the other.

## Qualification boundary

M4 was qualified on 2026-08-29 within bounded API/Luna evidence. Deterministic
fixtures covered empty, occupied/recognized, occupied/unknown,
occupied/unresolved, degraded, offline, completed sessions, and
restart-reconciled uncertainty. The full Ubuntu regression passed 77/77.

The real local database was healthy (schema 3, Atlas mirror `ok`) but contained
no current room observation, sessions, or events during the proof. Thirteen
low-effort Luna queries therefore returned truthful partial/unavailable answers
for the six core concepts and adversarial unsupported premises. A no-server
proof returned the deterministic unavailable answer with zero Luna calls.

M5 proactive behavior, voice, and richer activity or causal-history claims are
not included in the original M4 qualification. The later V0.2 routine-grounded
conversation slice extends `sentry_ask.py` for four bounded derived routine
types; see `docs/V0.2_ROUTINE_GROUNDED_CONVERSATION.md`. Routine facts remain
separate from physical-history facts and are never used by M5.
