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

---

## EXTERNAL-SENTRY-003 — Codex instruction discovery and isolated execution context
- Date: 2026-08-24
- Freshness: Official OpenAI Codex documentation retrieved through `/browse` on 2026-08-24; Codex CLI `0.145.0` behavior tested on the same host
- Sources: [Codex non-interactive mode](https://developers.openai.com/codex/noninteractive/), [Codex AGENTS.md guidance](https://learn.chatgpt.com/docs/agent-configuration/agents-md), [Codex authentication](https://developers.openai.com/codex/auth/), and local `codex exec --help`
- Overlap: Codex project instruction discovery explains the 19k baseline; supported noninteractive flags provide ephemeral JSONL, schema output, `--ignore-user-config`, and `--skip-git-repo-check`.
- Disposition: ADOPT the isolated cwd for SENTRY runtime reasoning; REFERENCE the discovery rules for development sessions.
- Rationale: Repo-root audit reported `\\atlas\ATLAS\100_ACTIVE\Projects\SENTRY\AGENTS.md`; the isolated cwd had zero `AGENTS*` files. The same-event input reduction was 5.4%, and the final bridge retained schema/grounding equivalence. A 50% reduction was not achieved, so no further unsupported optimization was attempted.
- Limitations: The isolated run retained installed skills context and measured approximately 18.2k input tokens. OAuth/local behavior is trusted-host evidence only; subscription quota and plan-wide idle billing remain unavailable from the CLI.
- Recheck trigger: Codex CLI release, AGENTS discovery/config changes, model/auth policy changes, or a move to service/scheduler deployment.

---

## EXTERNAL-SENTRY-004 — M1 detector/tracker/runtime/license comparison
- Date: 2026-08-24
- Freshness: Official upstream pages retrieved through `/browse` on 2026-08-24.
- Sources: [YOLOX](https://github.com/Megvii-BaseDetection/YOLOX), [ByteTrack](https://github.com/FoundationVision/ByteTrack), [ONNX Runtime execution providers](https://onnxruntime.ai/docs/execution-providers/), [OpenCV license](https://opencv.org/license/), and [OpenCV HOGDescriptor API](https://docs.opencv.org/4.x/d5/d33/structcv_1_1HOGDescriptor.html).
- Overlap: Local person detection, permissive licensing, model provenance, tracking, and Windows execution-provider selection.
- Disposition: ADOPT OpenCV HOG plus SENTRY-owned IoU tracking for the first narrow implementation; REFERENCE YOLOX plus ByteTrack and ONNX Runtime for a future benchmark.
- Rationale: OpenCV 4.5+ is Apache-2.0 and its HOG people detector coefficients are bundled, avoiding a separate model-weight provenance step for this slice. YOLOX is Apache-2.0 and ByteTrack is MIT, but the usual stack adds separately sourced artifacts and a larger runtime before camera access is proven. Host GPUs were observed but not required by the selected CPU path.
- Limitation: No live detector quality or performance claim is made because the actual webcam could not be opened.
- Recheck trigger: Webcam access restored, a detector performance shortfall, a qualified model artifact becoming available, or authorization for a YOLOX/ONNX benchmark.
