# Project Profile

## Repository
- Name: SENTRY
- Root: `/srv/ATLAS/100_ACTIVE/Projects/SENTRY` on the canonical Atlas share
- GitHub: https://github.com/SketchOTP/SENTRY
- Default branch: `main`
- Baseline commit at bootstrap: `63376fe` (`docs: add AI coder operating contract`)

## Strategic documentation
- Notion: https://app.notion.com/p/3c5833cb27ff8065aa88eff1089970a8
- Canonical Authority package: https://app.notion.com/p/3bf833cb27ff811aae15def88959797e
- Formal scope: `docs/PROJECT_SCOPE.md`

## Technical profile
- Language: Python 3.12 runtime for the local M1 slice.
- Frameworks: no application framework; OpenCV provides local V4L2 capture/frame handling and OpenVINO provides local 0202 inference.
- Major dependencies: `opencv-python-headless==4.12.0.88`, `openvino==2026.3.1`, `psutil==7.0.0`, `mcp==2.1.1`; the committed V0.3 implementation additionally uses local `vosk==0.3.45` for the operator-selected wake token `Sentry` and local Kokoro `0.9.4`. The repository default is British-male `bm_george`; the active V0.4 native UI candidate allows a validated English Kokoro voice and bounded speech-speed preference.
- Test command: `python -m unittest discover -s tests -v`.
- Runtime environment: Ubuntu Linux x86_64 host on the canonical Atlas share. The Linux NexiGo N60 V4L2 path and pinned local runtime are established; M1 practical presence, M2/M3, M4, M5, M6, and the V0.2 resident runtime are accepted within recorded boundaries.

## Important integrations
- Direct OAuth-authenticated Codex invocation is the operator-selected agent
  layer. Unattended voice uses the dedicated `sentry-resident` profile, which
  loads only the repository-owned SENTRY Office MCP/skill/instructions, native
  hosted web search, image generation, view-image, workspace dependencies, and
  workspace-bounded shell/file execution. Apps, plugins, Browser/CDP, generic
  computer use, command networking, broad host writes, sensitive reads, and
  Codex-generated memories are disabled. The historical `sentry` development
  profile is preserved for deliberate manual work and is not reachable from
  the voice service.
- Codex CLI `0.150.0-alpha.8`, authenticated with ChatGPT OAuth on the current host, is the current on-demand runtime. SENTRY resumes one dedicated local Codex thread and requests native compaction at 217,600 tokens, 80% of Luna's 272,000-token context window. Continuous perception never invokes it.
- Xiaomi Miloco, https://github.com/XiaoMi/xiaomi-miloco, is an architectural reference only and is not a dependency.
- Notion is the strategic project record; GitHub is the committed repository record.

## Compatibility commitments
- Preserve the owner-locked one-office-room product boundary. Historical
  whole-home, multi-room, distributed sensing, and TV embodiment directions
  are superseded unless the owner explicitly reauthorizes them.
- Preserve explicit degraded/offline states, conservative `unknown` identity behavior, local physical-event history, and restrained proactive speech as the implementation evolves.
- M5 keeps its accepted post-persistence bounded proactive processor. User-initiated PTT and optional V0.3 Vosk voice now converge on one resumed Codex thread; Codex can call typed local SENTRY/desktop tools and its native capabilities. Local Whisper `tiny.en` remains STT and Kokoro remains local PipeWire playback. Physical truth, reminders, preference, weather, and identity contracts remain host-owned. Codex history is working context, not authoritative sensor evidence or durable personal memory.
- V0.2 resident runtime uses separate native systemd user services. In the
  current operator deployment, the localhost state API, Vosk listener, coupled
  visible SENTRY status window, weather timer, and schema-9 one-shot alarm timer
  are enabled; continuous perception and proactive processing remain inactive
  and independently controlled. The listener retains bounded
  `Restart=on-failure`, `Linger=no`, RAM-only audio, and local-only STT/TTS.
- Clear current-turn operator requests authorize the exact supported host
  action after validation and audit; SENTRY does not add a redundant generic
  confirmation. An action is deferred only when the operator explicitly asks
  it to wait/prepare/show/ask first or a material target is unresolved. Deferred
  records are one-use and request/thread/restart/argument bound.
- Do not treat the suggested repository shape in the project scope as permission to create unneeded empty runtime modules.

## Safety / operational constraints
- M1 practical presence is accepted by explicit owner/operator direction; detector edge cases, low-light boundaries, and physical camera recovery remain known operational risks. M2 durable presence memory is accepted, using a local metadata-only SQLite database, integrity-checked Atlas snapshots, and a localhost read API. The Atlas mount is `fuse.sshfs`; SQLite never opens the Atlas copy as the live database. M3 primary-user identity and M4 grounded conversation are qualified within bounded evidence; simultaneous-person association remains a residual limitation. Windows/DirectShow evidence is historical.
- Preserve private recordings, enrollment images, biometric profiles, secrets, generated databases, caches, and large model weights outside Git.
- Do not expose local state beyond localhost without deliberate authorization and appropriate authentication.
- Do not silently derive from or fork DAWN, upload continuous video, add hardware, or expand to whole-home scope.
- Keep camera observations, captures, logs, local model artifacts, and observation exports outside Git by default.

## M0 upstream verification snapshot
- DAWN inspected at `a0c0b13c65f1b02a3416d846f6a0d331244eee9d` on `main`.
- DAWN's documented server path is x86_64 Linux/Docker; current host has Docker and WSL commands installed, but no DAWN runtime was started after the supported-ingress stop condition.
- Current DAWN surfaces do not provide a supported external trusted `person.entered` event ingress that autonomously starts reasoning without user-message masquerading or DAWN source/build changes.

## M0 Codex/Luna verification snapshot
- Official Codex docs document `codex exec`, `--ephemeral`, JSONL output, and `--output-schema`; official auth docs document ChatGPT sign-in for Codex CLI and saved credential reuse.
- Installed host: Codex CLI `0.145.0`; `codex login status` reports ChatGPT; bundled Python runtime is available under the Codex primary runtime dependencies.
- The bridge forces `gpt-5.6-luna`, controls `none|low|medium|high|xhigh|max`, removes API-key environment variables from the child, and performs no work without an explicit event file.
- Low and high synthetic `person.entered` turns passed with structured output and per-turn usage. The proof does not claim subscription quota remaining or optional speech.

## Source-of-truth boundaries
- Notion: strategic/project understanding and Architect state.
- GitHub: committed implementation and governance evidence.
- Codex working tree/runtime: live technical state, including uncommitted work and validation.
