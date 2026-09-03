# V0.3.3 Codex Execution Authority

## Architecture

```text
SENTRY voice/text
  -> persistent Codex thread (context only)
  -> sentry-resident permission profile
       -> native hosted web search
       -> workspace-local shell/files/image output
       -> SENTRY Office MCP
            -> Tier 0 read
            -> Tier 1 current-turn validated local action + audit
            -> Tier 2 current-turn execution or explicit deferred dialogue
            -> Tier 3 supported exact action or blocked
  -> metadata-only audit
  -> spoken result
```

Codex chooses capabilities and plans compound work. The host owns risk classification, direct-request validation, authorization validity, exact execution, and audit.

## Resident profile

`tools/sentry_codex_profile.py install` creates a private Codex runtime home, links only Codex-owned authentication/thread state, installs `sentry-resident.config.toml`, and creates the configured workspace and authority directories. It does not modify the existing manual unrestricted profile.

The installed permission profile extends Codex `:workspace`, grants writes only to workspace roots, denies sensitive paths and credential-like files, and disables command network. It does not contain `sandbox_mode`; mixing legacy `sandbox_mode` with permission profiles would disable the new profile boundary. Apps, plugins, browser/CDP, computer use, and Codex memory generation are disabled. Native web search is explicitly enabled by the launcher and is not command networking.

The child environment is an allow-list. Desktop session variables are given only to the host-owned MCP process, not to the general Codex shell.
The resident Codex runtime home is also denied to shell/file tools, including
its symlinked authentication and thread-state paths; Codex itself may consume
that state internally to authenticate and resume the resident thread.

## Risk tiers

- Tier 0: read/reason. Office state/history, reminder/alarm listing, preference, routines, cached weather, local time, application discovery, volume/window state, and authority/audit summaries.
- Tier 1: direct current-turn, bounded local action. Ephemeral camera/desktop inspection, reminder/preference/alarm mutation, application/URL/artifact open, volume, and media.
- Tier 2: host-brokered current-turn action. Non-overwriting moves outside the
  workspace, keyboard input, typed text, and pointer clicks execute when the
  operator's current request is clear and exact. An explicit request to wait or
  ask first enters the deferred-action dialogue instead.
- Tier 3: destructive, credential-bearing, authenticated, publishing,
  purchasing, sending, deployment, or security changes. A complete direct
  operator instruction is authority only when a separately supported typed
  executor exists; unsupported surfaces remain blocked.
- Tier 4: never confirmable. Credential/private-key access, authority/profile modification, permanent full access, hidden persistence, arbitrary sudo, broad deletion, unrestricted private networking, transcript mining, automatic memory, and direct future Obsidian-vault mutation.

The complete tool-by-tool matrix is in [`CAPABILITY_MATRIX.md`](CAPABILITY_MATRIX.md).

## Natural action handoff

Risk tiers are routing and audit metadata, not automatic conversational
friction. Direct execution and deferred execution share the same broker,
argument validation, executor, and append-only audit.

An explicitly deferred action progresses through `DRAFTED`, `PRESENTING`, and
`AWAITING_RESPONSE`. It cannot execute before presentation completes. The
120-second response window begins after Kokoro delivery and post-speech rearm,
so agent reasoning and TTS consume none of the operator's reply time. Natural
approval, cancellation, questions, and revisions are interpreted in the exact
pending-action context. A no-tool, no-network, read-only classifier is used only
when the high-confidence local parser cannot classify the reply. Outside an
active pending dialogue, agreement words cannot revive or execute an old action.

## Persistent thread

One Codex thread is resumed with the current profile on every turn. The mode-0600 SENTRY pointer stores IDs and utilization metadata, never transcripts. Status reports the model, turn count, configured 272,000-token window, 217,600-token compaction threshold, utilization, and observed compactions. Explicit rotation resets only the active pointer; it does not delete the old Codex thread or SENTRY operational data.

## Operating mode

Production physical mode is `agent_on_demand`: continuous perception remains implemented but inactive. Current physical state is unavailable unless perception is active or an explicit ephemeral camera inspection succeeds. Event-driven history and proactivity are correspondingly limited. The authority status surface reports this rather than implying continuous observation.

## External basis

The profile follows the installed Codex permission-profile contract documented in [OpenAI Codex Permissions](https://learn.chatgpt.com/docs/permissions). Permission profiles govern local commands; MCP, hosted search, browser, computer-use, apps, and plugins require separate controls, which is why this design combines the Codex profile with a host MCP broker.
