# Evidence — SENTRY-OPERATOR-CODEX-NATIVE-AGENT-001

## Starting state

- Repository: `/srv/ATLAS/100_ACTIVE/Projects/SENTRY`
- Starting HEAD/origin: `122de1924f4e6f62d68838bdf1f1ccfbf35dea68`
- Working tree: clean
- Schema: 8
- Installed Codex CLI: `0.150.0-alpha.8`
- Existing direct bridge: ephemeral `gpt-5.6-luna`, `--ignore-user-config`,
  read-only sandbox, two-turn planner/host/synthesis orchestration.

## Capability selection

- Installed stable feature flags include shell, plugins, MCP/apps, browser use,
  computer-use family, image generation, image viewing, and workspace
  dependencies.
- Normal user configuration exposes the `node_repl` MCP and installed Browser,
  Codex App Tools, document, PDF, spreadsheet, presentation, Sites, and
  visualization plugins; the current SENTRY invocation intentionally ignores
  all of them.
- Official Codex documentation confirms named profile files, stdio MCP servers,
  `danger-full-access`, noninteractive `approval_policy=never`, and CLI
  `$imagegen` support. Official graphical Computer Use is macOS/Windows only;
  Linux desktop control therefore requires structured local adapters.

## Implementation

- Implementation commit: `cb3e97c` (`feat: make Codex the SENTRY agent runtime`).

- `tools/sentry_ask.py` now sends production conversation directly to one
  `CodexNativeAgent` turn. The old planner/orchestrator modules remain only as
  compatibility and historical regression surfaces.
- Installed mode-0600 profile: `/home/sketch/.codex/sentry.config.toml`;
  `codex --profile sentry mcp list` reports `sentry_office` enabled alongside
  the normal `node_repl` server.
- Repo-local plugin/skill: `integrations/codex/plugins/sentry-office/`.
- MCP SDK: `mcp==2.1.1`; server exposes 25 tools across office state/history,
  reminders/preferences/routines/weather/time, explicit camera inspection,
  applications/URL opening, PipeWire volume, MPRIS media, and X11 desktop.
- Natural-language turns run with `--search`, installed user configuration,
  `danger-full-access`, `approval_policy=never`, model `gpt-5.6-luna`, and no
  inherited API-key environment variables.
- Recent context is process RAM only, four turns, ten-minute TTL.

## Live capability evidence

- SENTRY MCP local time: passed; exact `sentry_office.get_local_time` call.
- Native public web: passed; NWS Mount Washington forecast with source link,
  two native `web_search` calls.
- Image generation: passed; generated and verified
  `/home/sketch/Pictures/SENTRY/sentry-emblem.png`, 1254x1254 PNG, SHA-256
  `d5ba392f0793cff67eb0d3e84448df30427f42c63c183e4593793cefd990ade1`.
- Local write: passed; Codex created and read back the exact requested proof
  file under `/home/sketch`.
- Desktop volume: passed; Codex read 61%, changed to 60%, verified, and the host
  restored the original 61%.
- Application control: passed; Codex resolved `org.gnome.TextEditor` and
  launched it.
- Desktop vision: passed; active-window and transient screenshot tools returned
  a truthful description with no retained screenshot file.
- Explicit office camera: passed; one visible person was observed, local
  enrolled identity remained unresolved, and Codex refused to infer identity
  from appearance. Tool call: `sentry_office.inspect_office_camera`.
- Browser-page opening: passed; exact OpenAI Codex URL was handed to the
  configured desktop browser. Subsequent screenshot truthfully reported the
  visible OpenAI/ChatGPT Learn page rather than inventing a Codex title.
- Interactive Browser skill: connection-dependent/unavailable in the ephemeral
  CLI because no in-app browser or ChatGPT browser-extension surface was
  connected. Native web search and explicit desktop browser control remain
  functional.

## Validation

- New focused Codex/MCP/desktop/profile/voice/resident tests: `43/43`.
- Complete Ubuntu regression after final URL-tool change: `243/243` in
  45.515 seconds.
- `git diff --check` and Python compilation: passed.
- Schema remains 8. No camera frame, screenshot, ambient transcript, API key,
  biometric vector, or private coordinate was added to Git.
- Final process inspection: voice, perception, state API, and proactivity were
  inactive; no `pw-record`, listener, Whisper/Vosk worker, temporary API, or
  transient desktop screenshot remained. `voice.always_on_enabled=false`.
  The independently authorized `sentry-weather.timer` remained enabled/active.
