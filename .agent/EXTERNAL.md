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
