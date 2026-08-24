# Evidence — SENTRY-M0-DAWN-FEASIBILITY-001

## Retrieval

- SENTRY Notion: current project scope and accepted bootstrap review fetched 2026-08-24.
- SENTRY GitHub: clean `main` before this record at `c15704ef82198814bac9d7071f75efa3602d45df`.
- DAWN upstream: `a0c0b13c65f1b02a3416d846f6a0d331244eee9d`.

## Static upstream evidence

- `docs/WEBSOCKET_PROTOCOL.md`: `text` and `satellite_query` carry conversational text; `attention_alert`, `silent_observation`, and `context_injection` are server-to-WebUI primitives.
- `src/webui/webui_message_dispatch.c`: WebSocket `text` routes to `handle_text_message`; `satellite_query` routes to the satellite text handler; the debug silent-observation path only broadcasts a UI event.
- `src/mosquitto_comms.c`: generic device results are formatted as `[DEVICE DATA] Speak this information naturally to the user: ...` and pushed as `INPUT_SOURCE_MQTT`.
- `src/core/attention/attention_catalog.c`: SAGE catalog contains STAT/suit/component metrics and no person/presence event.
- `src/core/attention/attention_core.c`: SAGE can optionally add `[proactive alert] ...` to an existing session and can deliver speech, but it is downstream of DAWN-owned watch evaluation.
- `include/core/pending_system_msg.h` and `src/dawn.c`: deferred system context is applied by the main loop for a later turn; it is not an external reasoning trigger.
- `docs/TOOL_DEVELOPMENT_GUIDE.md`: custom tools require DAWN source files, CMake integration, registration, and rebuild.

## Decision

BLOCKED. A supported external path satisfying both trusted physical-event provenance and autonomous assistant reasoning was not found. Evidence level is `E1_OBSERVED`; no runtime claim is made.
