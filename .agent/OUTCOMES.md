# Outcome Ledger

---

## OUTCOME-SENTRY-AUTHORITY-BOOTSTRAP-001 — Directive SENTRY-AUTHORITY-BOOTSTRAP-001
- Completed: 2026-08-24
- Verdict: COMPLETE
- Retrieval confidence: ADEQUATE
- Evidence level: E3_TARGET_TESTED
- Git state / commit: Final governance commit recorded in the GitHub handoff and Notion update.

### Technical state discovered
The restored `main` checkout was clean at baseline `63376fe` and contained only the pre-Authority documentation-first SENTRY repository. GitHub and Notion agree on the project goal, V0.1 office boundary, M0 gate, DAWN evaluation, Miloco reference-only status, and absence of runtime implementation.

### Work performed
Installed the canonical Authority 3.0 root router, project-state/history structure, reusable workflow and references, SENTRY-specific state records, and a completed governance task packet. No product/runtime implementation was added.

### Acceptance results
- Canonical Authority 3.0 structure installed: PASSED
- Root `AGENTS.md` is the Authority router: PASSED
- `.agent/` state is SENTRY-specific and identifies M0: PASSED
- `.agents/` workflow/reference paths resolve: PASSED
- Existing SENTRY documentation preserved: PASSED
- No runtime implementation or dependencies introduced: PASSED
- Commit and push to GitHub: PASSED
- Notion evidence update: PASSED

### Validation
- Expected Authority tree exists: PASSED
- Root router references real mandatory paths: PASSED
- `.agent/INDEX.md` references real mandatory state files: PASSED
- Required workflow/reference files exist: PASSED
- SENTRY-specific goal/scope/current-state content present: PASSED
- Governance-only placeholder scan: PASSED
- Final diff limited to governance/state files: PASSED
- Final working tree clean after commit: PASSED

### Assumptions confirmed
- SENTRY was documentation-first and implementation had not begun.
- M0 — Bootstrap + DAWN Integration Feasibility is the current authorized gate.
- DAWN is the preferred foundation under evaluation; Miloco is architectural reference only.

### Assumptions disproven
- None.

### Risks / blockers
- DAWN integration behavior remains unverified and is intentionally deferred to M0.

### Architect decision required
YES — review and accept this governance result before authorizing M0 implementation.

---

## OUTCOME-SENTRY-M0-DAWN-FEASIBILITY-001 — Directive SENTRY-M0-DAWN-FEASIBILITY-001
- Completed: 2026-08-24
- Verdict: BLOCKED
- Retrieval confidence: ADEQUATE
- Evidence level: E1_OBSERVED
- Upstream inspected: DAWN `a0c0b13c65f1b02a3416d846f6a0d331244eee9d` (`main`)

### Technical state discovered
SENTRY remains documentation-first with no application source, tests, dependency manifest, or runtime implementation. DAWN's current upstream is GPL-3.0-or-later and documents x86_64 Linux/Docker server deployment, but its current supported input and proactive surfaces do not provide the required SENTRY event boundary.

### Work performed
- Reconciled the accepted SENTRY Notion directive and current project scope.
- Inspected DAWN server deployment documentation, WebSocket protocol, tool-development guide, proactive-attention catalog/core, WebSocket message dispatch, satellite query path, MQTT callback path, system-context queue, and speech delivery path.
- Compared alternatives: WebSocket `text`/`satellite_query`, MQTT device relay, SAGE attention/telemetry, WebUI silent-observation test path, existing system-context injection, and custom DAWN tool registration.
- No SENTRY runtime code, dependency, or DAWN source was changed.

### Acceptance results
- Current DAWN upstream inspected: PASSED
- Supported x86/server deployment documented: PASSED (documentation evidence only)
- Minimal versioned SENTRY event implemented: BLOCKED by ingress boundary
- Event reaches DAWN as trusted environmental context: BLOCKED
- Assistant reasons from `person.entered`: BLOCKED
- Optional speech: BLOCKED, no qualifying event-to-reasoning path available
- Event-to-assistant flow reproducible: BLOCKED
- No webcam/perception scope introduced: PASSED
- No DAWN fork/vendor dependency created: PASSED
- Authority state and Notion update: PASSED
- Commit/push: PASSED (`157fb3e`)

### External surface findings
- WebSocket `text` and DAP2 `satellite_query` are documented and implemented as conversational text input. They would make the physical event appear as a user utterance.
- MQTT is subscribed for DAWN/OASIS device commands and selected telemetry/events. The generic device relay formats returned data as `[DEVICE DATA] Speak this information naturally to the user: ...` and pushes it into `INPUT_SOURCE_MQTT`, which becomes a normal user-role turn.
- SAGE attention is a fixed catalog of STAT/suit/component numeric or absence metrics. It can deliver an alert and optionally inject `[proactive alert] ...` into existing sessions, but it does not expose a SENTRY event ingress or an external reasoning trigger. `person.entered` is not in the catalog.
- `silent_observation` and `context_injection` are server-to-WebUI notifications. The test observation path is admin/debug-only and is a UI signal, not assistant grounding.
- `session_broadcast_system_message` and `pending_sysmsg_push` preserve system-role context, but only add context for a later turn and do not initiate an LLM turn.
- DAWN's supported custom-tool process requires source files, CMake registration, and build registration. That is a DAWN modification/fork boundary, explicitly excluded by the directive.

### Assumptions confirmed
- M0 is the current gate and no SENTRY runtime capability exists.
- DAWN is GPL-3.0-or-later; direct derivation or a linked custom tool would require an explicit licensing/architecture decision.
- Existing DAWN speech delivery is reachable from native proactive attention, but that path is downstream of DAWN-owned event generation and does not solve SENTRY event ingress.

### Assumptions disproven
- The current upstream WebSocket/MQTT/SAGE surfaces are sufficient by themselves for a trusted, externally supplied SENTRY physical event that autonomously starts reasoning.

### Risks / blockers
- Proceeding with WebSocket text or MQTT device relay would violate the event-provenance acceptance criterion.
- Modifying or forking DAWN would change the architecture and licensing decision and must be explicitly authorized.
- Docker and WSL are installed on the Windows host, but a live DAWN server was not started because the supported-boundary stop condition was reached first; runtime feasibility remains untested.

### Architect decision required
YES. Choose whether to authorize an explicit DAWN upstream change/maintained fork, evaluate another assistant foundation, or revise the M0 acceptance boundary. Webcam/perception work remains gated.

---

## OUTCOME-SENTRY-M0-CODEX-FEASIBILITY-001 — Directive SENTRY-M0-CODEX-FEASIBILITY-001
- Completed: 2026-08-24
- Verdict: PASS — bounded feasibility proof target-tested; awaiting Architect acceptance
- Retrieval confidence: ADEQUATE
- Evidence level: E3_TARGET_TESTED
- Codex version: `codex-cli 0.145.0`
- Authentication: `codex login status` reported `Logged in using ChatGPT`; the bridge removed `OPENAI_API_KEY` and `OPENAI_ADMIN_KEY` from each child process.
- Model: explicitly forced as `gpt-5.6-luna` for every invocation; no model switching or escalation occurred.

### Technical state discovered
The host has a supported noninteractive Codex CLI surface, OAuth ChatGPT credentials, and a bundled Python runtime at `C:\Users\sketc\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`. Official Codex documentation documents `codex exec` for scripts, `--ephemeral` for non-persisted rollout files, JSONL events for machine-readable processing, `--output-schema` for structured output, and saved CLI authentication reuse. Official GPT-5.6 Luna documentation confirms the model alias and effort levels `none`, `low`, `medium`, `high`, `xhigh`, and `max`.

### Work performed
- Implemented `tools/sentry_codex_bridge.py`, a single-event adapter with schema validation, explicit Luna model, effort selection, OAuth-only child environment, `--ephemeral`, read-only sandbox, schema-constrained JSON output, one timeout, no retry, no thread resume, and structured failure results.
- Implemented `tools/sentry_codex_response.schema.json` for stable downstream parsing.
- Used fresh bounded turns rather than persistent/resumable threads. This keeps event causality explicit and avoids an idle Codex worker.
- No webcam, perception, persistence, voice, DAWN, OpenClaw, hardware, or M1 implementation was added.

### Runtime acceptance results
- OAuth-authenticated local invocation without API key: PASSED. Two successful calls ran after removing the API-key variables from the child environment.
- Luna selection: PASSED. CLI invocation and returned bridge envelope both identify `gpt-5.6-luna`.
- Synthetic event grounding: PASSED. Event IDs `...0101` and `...0102` returned `event_type=person.entered`, `room_id=office`, `person_id=primary_user`, `understood=true`, and responses explicitly described environmental/physical context as not user speech.
- Parseable response: PASSED. Both calls satisfied the JSON Schema through `--output-schema` and were parsed from JSONL `agent_message` plus `turn.completed` usage.
- Independent second event: PASSED. A fresh ephemeral thread handled event `...0102` independently.
- Two Luna effort levels: PASSED. Low and high were selected without changing the model; returned `effort` matched the requested value.
- No repeated/background turns: PASSED. The adapter has no worker, timer, poll, retry, or resume path; after each run no `sentry_codex_bridge.py` Python process remained.
- Failure detection: PASSED. Missing event file returned `invalid_event_file` without a Codex call; a forced missing executable returned `codex_unavailable` without crashing the bridge.
- Idle behavior: PASSED by bounded design and process check. No invocation occurs without an explicit event file, and no bridge process remained during the post-run check. Subscription-wide idle billing cannot be independently measured from the CLI.
- Optional speech: NOT APPLICABLE. This directive tests the reasoning/tool layer only and excludes the voice stack.

### Measured per-turn usage
The JSONL `turn.completed` usage object is the available local measurement, not a claim about remaining ChatGPT plan quota:

| Turn | Model | Effort | Input | Output | Reasoning output |
|---|---|---:|---:|---:|---:|
| event `...0101` | `gpt-5.6-luna` | `low` | 19,100 | 80 | 0 |
| event `...0102` | `gpt-5.6-luna` | `high` | 19,100 | 139 | 55 |

The direct preliminary probes also succeeded at low and high effort, but the packaged bridge measurements above are the representative acceptance evidence. The CLI did not expose a subscription quota-before/after counter; future governance should use these per-turn token metrics plus available account analytics.

### Limitations / risks
- ChatGPT OAuth is proven on this trusted host, not as a general public or unattended service deployment. Codex credentials remain local secrets and the bridge must not be exposed to untrusted input.
- The proof uses the installed bundled Python runtime because the ordinary Windows `python` command is only a Microsoft Store alias. No third-party package was added.
- Codex CLI may initialize configured optional MCP servers unless disabled or absent; the packaged bridge uses `--ignore-user-config` and does not request tools, but it still depends on the installed CLI's local startup behavior.
- The model/provider selection is enforced by the invocation constant and CLI flag. The JSONL stream reports the explicit command's selected model through the bridge envelope, but does not provide a separate server attestation field.

### Architect decision required
YES. Accept or reject the bounded Codex/Luna event-to-reasoning boundary. If accepted, authorize the next SENTRY milestone with the Luna-only rule, default low/medium effort, justified high/xhigh/max effort, no idle calls, bounded context, duplicate suppression, hard call-rate limits, and observable usage metrics. Webcam/perception remains gated until acceptance.
