# SENTRY Architecture

SENTRY is the visible, local one-room interface. Codex is the persistent reasoning agent underneath it. Local perception and deterministic stores produce authoritative facts; Codex selects bounded native capabilities or typed SENTRY MCP operations; Kokoro provides the British-male spoken surface.

```text
Vosk / PTT
  -> Whisper
  -> persistent Codex thread
       -> hosted public web search
       -> resident workspace tools
       -> SENTRY Office MCP
            -> state/history/weather/time
            -> bounded local actions
            -> host authorization broker
  -> grounded result
  -> Kokoro / PipeWire
```

The persistent thread is conversational context, not authority or durable personal memory. The host-enforced resident boundary is specified in [`EXECUTION_AUTHORITY.md`](EXECUTION_AUTHORITY.md); threats in [`THREAT_MODEL.md`](THREAT_MODEL.md); tool tiers in [`CAPABILITY_MATRIX.md`](CAPABILITY_MATRIX.md); and content-retention boundaries in [`PRIVACY.md`](PRIVACY.md).

Continuous perception remains implemented but the current operator mode is `agent_on_demand`. That means SENTRY can perform an explicit ephemeral office-camera inspection, but it must report current physical state as unavailable when neither fresh perception nor an on-demand inspection supports it. Physical history, reminders, preferences, routines, alarms, and weather remain separate governed subsystems.
