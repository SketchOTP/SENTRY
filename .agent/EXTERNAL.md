# External Discovery Ledger

Record material prior-art investigations when Authority triggers external discovery. Do not log every trivial web search.

No external discovery was required for this governance-only bootstrap. The directive explicitly marked external discovery `NOT REQUIRED`; Notion and GitHub were authoritative project sources, and the canonical Authority package was retrieved from Notion.

---

## EXTERNAL-SENTRY-001 — DAWN M0 integration surface investigation
- Date: 2026-08-24
- Freshness: DAWN `main` at `a0c0b13c65f1b02a3416d846f6a0d331244eee9d`; current project Notion fetched 2026-08-24
- Source: [DAWN repository](https://github.com/The-OASIS-Project/dawn), [server deployment guide](https://github.com/The-OASIS-Project/dawn/blob/a0c0b13/docs/GETTING_STARTED_SERVER.md), [WebSocket protocol](https://github.com/The-OASIS-Project/dawn/blob/a0c0b13/docs/WEBSOCKET_PROTOCOL.md), [tool development guide](https://github.com/The-OASIS-Project/dawn/blob/a0c0b13/docs/TOOL_DEVELOPMENT_GUIDE.md), and inspected source at the same commit
- Overlap: DAWN provides server mode, WebSocket conversations, MQTT device/telemetry paths, SAGE proactive attention, system-context injection, and TTS delivery.
- Disposition: REJECT for the current M0 proof as a complete supported path; REFERENCE for future architecture decisions.
- Rationale: WebSocket/satellite inputs are user text; MQTT generic relay becomes a user-role `[DEVICE DATA]` turn; SAGE watches only a fixed DAWN telemetry catalog and does not expose SENTRY event ingress; context injection does not initiate reasoning; custom tools require DAWN source/build registration.
- Licensing/deployment: DAWN is GPL-3.0-or-later. Server deployment is documented for x86_64 Linux/Docker, not natively Windows. Docker and WSL are installed on the host, but runtime was not started after the supported-boundary stop condition.
- Recheck trigger: DAWN documents a generic trusted event ingress/proactive trigger, or Architect explicitly authorizes an upstream change/fork, licensing review, or foundation comparison.

---

## EXTERNAL-SENTRY-002 — Official Codex OAuth, noninteractive, structured output, and Luna capability
- Date: 2026-08-24
- Freshness: Official OpenAI documentation retrieved through `/browse` on 2026-08-24; installed Codex behavior tested on the same host
- Sources: [Codex CLI](https://developers.openai.com/codex/cli/), [Codex non-interactive mode](https://developers.openai.com/codex/noninteractive/), [Codex authentication](https://developers.openai.com/codex/auth/), [GPT-5.6 Luna model](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
- Overlap: Codex CLI supports local script/CI invocation, ChatGPT sign-in, ephemeral runs, JSONL events, JSON Schema output, and explicit model/effort configuration; Luna supports the required effort levels.
- Disposition: ADOPT for the bounded M0 proof; REFERENCE for future governor/deployment design.
- Rationale: The supported CLI surface matches SENTRY's required on-demand shape without adding an assistant framework. Two OAuth-only local turns passed with independent synthetic event IDs and measurable per-turn usage.
- Limitations: The current proof is trusted-local, not public unattended service deployment. Official docs state ChatGPT-managed auth is supported locally but general automation often uses API keys; SENTRY's architecture must preserve credential privacy. Subscription quota remaining and plan-wide idle billing were not exposed by the CLI; only per-turn JSONL token usage and process behavior were observed.
- Recheck trigger: Codex CLI/model/auth changes, ChatGPT plan policy changes, or any move from a trusted local process to a scheduler/service.
