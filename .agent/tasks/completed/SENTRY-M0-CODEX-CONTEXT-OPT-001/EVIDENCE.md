# Evidence — SENTRY-M0-CODEX-CONTEXT-OPT-001

## Result

`E3_TARGET_TESTED` — PASS for context characterization and bounded runtime hardening; awaiting Architect acceptance of this directive result.

## Successful Luna calls

Exactly four successful model turns were consumed:

| Call | Purpose | Model | Effort | Input | Output | Reasoning |
|---|---|---|---:|---:|---:|---:|
| 1 | Existing bridge, repo-root event `...0101` | `gpt-5.6-luna` | low | 19,308 | 76 | 0 |
| 2 | Direct isolated event `...0101` | `gpt-5.6-luna` | low | 18,266 | 103 | 21 |
| 3 | Repo-root instruction-source audit | `gpt-5.6-luna` | low | 18,845 | 132 | 86 |
| 4 | Updated bridge, isolated event `...0102` | `gpt-5.6-luna` | low | 18,223 | 80 | 0 |

No fifth model call was made.

## Exact invocations

Existing bridge baseline, with the bridge's original repo-root execution:

```text
node C:\Users\sketc\AppData\Roaming\npm\node_modules\@openai\codex\bin\codex.js exec --ephemeral --json --ignore-user-config --model gpt-5.6-luna --output-schema tools/sentry_codex_response.schema.json -c model_reasoning_effort="low" -s read-only -C . -
```

The process cwd was `\\atlas\ATLAS\100_ACTIVE\Projects\SENTRY`, and the event was supplied on stdin by the bridge.

Direct isolated probe:

```text
node C:\Users\sketc\AppData\Roaming\npm\node_modules\@openai\codex\bin\codex.js exec --ephemeral --json --ignore-user-config --skip-git-repo-check --model gpt-5.6-luna --output-schema C:\Users\sketc\AppData\Local\Temp\sentry-codex-isolated-f92587796e9f432e98191b04e9c2006a\sentry_codex_response.schema.json -c model_reasoning_effort="low" -s read-only -
```

The process cwd was the isolated temporary directory, with the same event supplied on stdin. The schema path was absolute and local.

Final bridge invocation has the same isolated shape, with a fresh temporary directory and a copied absolute schema path on every event.

## Context finding

The repository contains one applicable project instruction file, `AGENTS.md`, at the SENTRY root. The repo-root audit turn returned that exact path and the SENTRY project root. Official Codex guidance says project instructions are discovered from the project root down to the current directory, while a non-repository isolated directory has no project root and therefore no SENTRY `AGENTS.md` chain. The isolated directory contained zero `AGENTS*` files. `--ignore-user-config` was retained, so user Codex configuration and MCP startup were not added to either runtime turn.

The isolated turn still reported the installed skills-context warning, so the observed 18.2k input is a practical floor for this CLI environment, not a claim that all Codex startup context is removable.

## Reduction

The same-event baseline fell from 19,308 to 18,266 input tokens, a 5.4% reduction. The final bridge event measured 18,223 input tokens, 5.6% below baseline. This is below the 50% target, but it confirms that repository guidance contributes measurable overhead and that isolation is a safer runtime boundary. No unsupported configuration or model change was attempted.

## Equivalence and safety

- ChatGPT OAuth remained active; API-key variables were removed from child environments.
- The model remained exactly `gpt-5.6-luna`.
- Both semantic events returned schema-valid JSON with `event_type=person.entered`, `room_id=office`, `person_id=primary_user`, `understood=true`, and explicit physical-event/not-user-speech grounding.
- The bridge now uses `TemporaryDirectory`, copies the schema to an absolute local path, runs with `--skip-git-repo-check`, and has no worker, timer, retry, or resume path.
- Missing event input and a forced unavailable executable remain bounded structured errors and do not invoke Luna.

