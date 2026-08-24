# Evidence — SENTRY-M0-CODEX-FEASIBILITY-001

## Official and installed-surface evidence

- Official Codex CLI docs: `codex exec` is intended for scripts/CI; `--ephemeral` avoids persisted rollout files; `--json` emits JSONL events; `--output-schema` requests structured final output.
- Official Codex authentication docs: Codex CLI supports ChatGPT sign-in and reuses saved CLI authentication.
- Official GPT-5.6 Luna docs: alias `gpt-5.6-luna`; reasoning effort `none`, `low`, `medium`, `high`, `xhigh`, `max`.
- Installed CLI: `codex-cli 0.145.0`.
- Installed authentication: `codex login status` → `Logged in using ChatGPT`.

## Invocation

```text
C:\Users\sketc\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe tools\sentry_codex_bridge.py --event-file <event.json> --effort <low|high>
```

The bridge invokes:

```text
codex exec --ephemeral --json --ignore-user-config --model gpt-5.6-luna --output-schema tools/sentry_codex_response.schema.json -c model_reasoning_effort="<effort>" -s read-only -C . -
```

The child environment removes `OPENAI_API_KEY` and `OPENAI_ADMIN_KEY`.

## Runtime results

| Event | Effort | Result | Usage |
|---|---|---|---|
| `00000000-0000-4000-8000-000000000101` | low | `understood=true`; `person.entered`; `office`; `primary_user`; physical context explicitly not user speech | input 19,100; output 80; reasoning output 0 |
| `00000000-0000-4000-8000-000000000102` | high | `understood=true`; `person.entered`; `office`; `primary_user`; trusted physical context explicitly not user speech | input 19,100; output 139; reasoning output 55 |

Both runs used fresh ephemeral thread IDs and returned schema-parseable JSON envelopes.

## Failure and idle checks

- Missing event file: structured `invalid_event_file`, exit 2, no Codex call.
- Forced missing executable: structured `codex_unavailable`, exit 1, no crash.
- No bridge Python process remained after successful completion.
- The bridge has no loop, timer, retry, thread resume, or idle path. Subscription-wide idle consumption was not observable from CLI reporting.

## Scope checks

- No webcam, perception, identity, SQLite, presence session, voice, DAWN, OpenClaw, hardware, or M1 files changed.
- No third-party dependency was added.
