# Task Packet — SENTRY-M0-CODEX-FEASIBILITY-001

## Objective

Prove whether an OAuth-authenticated Codex CLI turn using GPT-5.6 Luna only can consume a synthetic SENTRY `person.entered` event and return grounded structured reasoning on demand.

## Scope

- Inspect current official Codex/OpenAI documentation and installed Codex behavior.
- Verify ChatGPT OAuth authentication without an API-key environment variable.
- Implement one bounded local event-to-Codex adapter with explicit Luna model and effort.
- Capture the returned structured response and usage metadata.

## Exclusions

No webcam, perception, face recognition, SQLite, presence sessions, voice stack, OpenClaw, DAWN, Home Assistant, hardware, routine learning, TV/avatar, continuous Codex loop, model escalation, or M1 work.

## Stop condition

Return to the Architect if OAuth cannot support the bounded local invocation, Luna or effort cannot be selected, event provenance cannot remain explicit, or safe bounded failure handling cannot be established.
