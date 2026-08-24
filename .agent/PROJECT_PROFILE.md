# Project Profile

## Repository
- Name: SENTRY
- Root: `\\atlas\ATLAS\100_ACTIVE\Projects\SENTRY`
- GitHub: https://github.com/SketchOTP/SENTRY
- Default branch: `main`
- Baseline commit at bootstrap: `63376fe` (`docs: add AI coder operating contract`)

## Strategic documentation
- Notion: https://app.notion.com/p/3c5833cb27ff8065aa88eff1089970a8
- Canonical Authority package: https://app.notion.com/p/3bf833cb27ff811aae15def88959797e
- Formal scope: `docs/PROJECT_SCOPE.md`

## Technical profile
- Languages: documentation only at bootstrap; no application implementation exists.
- Frameworks: none installed.
- Major dependencies: none declared.
- Build/test commands: none defined; governance validation is structural and repository-state based.
- Runtime environments: future V0.1 target is the existing Windows/x86 office PC; runtime is not yet implemented or validated.

## Important integrations
- DAWN, https://github.com/The-OASIS-Project/dawn, is the preferred conversational/persistent assistant foundation under evaluation. Integration is not implemented.
- Codex CLI `0.145.0`, authenticated with ChatGPT OAuth on the current host, is the accepted candidate on-demand reasoning layer under M0 feasibility evaluation. Integration is limited to the bounded bridge in `tools/` and is not yet Architect-accepted as M0 complete.
- Xiaomi Miloco, https://github.com/XiaoMi/xiaomi-miloco, is an architectural reference only and is not a dependency.
- Notion is the strategic project record; GitHub is the committed repository record.

## Compatibility commitments
- Preserve the office-only V0.1 boundary and milestone order beginning at M0.
- Preserve explicit degraded/offline states, conservative `unknown` identity behavior, local physical-event history, and restrained proactive speech as the implementation evolves.
- Do not treat the suggested repository shape in the project scope as permission to create unneeded empty runtime modules.

## Safety / operational constraints
- No runtime/product implementation is authorized by the bootstrap directive.
- Preserve private recordings, enrollment images, biometric profiles, secrets, generated databases, caches, and large model weights outside Git.
- Do not expose local state beyond localhost without deliberate authorization and appropriate authentication.
- Do not silently derive from or fork DAWN, upload continuous video, add hardware, or expand to whole-home scope.

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
