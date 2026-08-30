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
- Major dependencies: `opencv-python-headless==4.12.0.88`, `openvino==2026.3.1`, `psutil==7.0.0`.
- Test command: `python -m unittest discover -s tests -v`.
- Runtime environment: Ubuntu Linux x86_64 host on the canonical Atlas share. The Linux NexiGo N60 V4L2 path and pinned local runtime are established; M1 practical presence, M2/M3, M4, M5, M6, and the V0.2 resident runtime are accepted within recorded boundaries.

## Important integrations
- Direct OAuth-authenticated Codex/Luna invocation through the bounded SENTRY bridge is the accepted V0.1 reasoning layer. DAWN feasibility work is historical evidence/reference only; integration is not implemented.
- Codex CLI `0.145.0`, authenticated with ChatGPT OAuth on the current host, is the accepted on-demand reasoning layer from M0. Integration remains limited to the bounded bridge in `tools/`; continuous perception never invokes it.
- Xiaomi Miloco, https://github.com/XiaoMi/xiaomi-miloco, is an architectural reference only and is not a dependency.
- Notion is the strategic project record; GitHub is the committed repository record.

## Compatibility commitments
- Preserve the office-only V0.1 boundary and milestone order beginning at M0.
- Preserve explicit degraded/offline states, conservative `unknown` identity behavior, local physical-event history, and restrained proactive speech as the implementation evolves.
- M5 uses a post-persistence proactive processor with one allowed event class (`person.identified` for `primary_user`), deterministic suppression, one bounded low-effort Luna judgment for survivors, and local Speech Dispatcher delivery. Reactive voice is accepted through explicit PipeWire capture, local Whisper `tiny.en` STT, the existing M4 grounded query path, and an installed local Kokoro runtime for local PipeWire playback. M6 passed the owner/operator-approved 30-minute final soak; V0.1 is accepted within the office-only boundary.
- V0.2 resident runtime uses separate native systemd user services for perception, the localhost state API, and continuous bounded proactive polling. Units are enabled for the authenticated user session and use bounded `Restart=on-failure` recovery; routine learning is not implemented.
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
