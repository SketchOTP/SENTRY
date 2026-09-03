# SENTRY Resident Threat Model

## Assets

Operator files, credentials, browser sessions, SENTRY private configuration, biometric enrollment, physical history, Codex authentication/thread state, future Obsidian memory, and control of desktop/external accounts.

## Adversaries and failures

- mistranscribed voice or ambiguous speech;
- hostile webpage, repository file, screenshot, generated artifact, or MCP output;
- stale instructions in the persistent Codex thread;
- model planning/error or tool-argument drift;
- filesystem traversal/symlink escape;
- shell network exfiltration;
- confirmation spoofing/replay;
- audit tampering or unavailable audit storage;
- a resident process restart between proposal and confirmation.

## Controls

- Codex permission profile limits native commands to a dedicated workspace and disables command network.
- Sensitive paths are unreadable; apps/plugins/browser/computer-use and Codex memories are disabled.
- MCP mutations are host classified. A clear current operator request may
  execute through the host broker without a redundant confirmation; web, file,
  screenshot, MCP, and stale-thread content cannot provide that authority.
- Explicitly deferred actions are private, one-use, argument-hashed, and bound
  to request, thread, and process epoch. They are non-actionable while drafted
  or presented; the 120-second response window starts only after presentation.
- Non-read attempts require an appendable private audit ledger. Audit failure blocks mutation.
- File moves reject overwrite, traversal, symlink targets, protected paths, and source roots outside the resident workspace.
- The persistent thread supplies context but cannot mint authorization or change the profile.

## Residual risk

Workspace-local writes can still create bad scratch code or artifacts, so the workspace is not a trusted software-distribution root. Hosted web search and image generation are service-side capabilities outside command-network controls; their outputs are untrusted data. The manual unrestricted development profile remains powerful and must be invoked deliberately outside the resident service. Voice identity is not a cryptographic authenticator. This personal deployment uses the owner's explicit trusted-operator policy; unsupported consequential surfaces remain blocked, and ambiguous targets fail closed.

## Memory boundary

Codex native memory generation is disabled. No Obsidian vault is created here. A future private vault must remain denied to normal shell/file tools and be writable only through a separately governed memory MCP.
