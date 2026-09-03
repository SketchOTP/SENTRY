# SENTRY Security Policy

SENTRY is an always-listening local interface backed by a persistent Codex thread. Conversation context is not authority. The host, not the model, decides what may execute.

## Resident boundary

- Resident profile: `sentry-resident`; the manual `sentry` development profile is not used by voice.
- Writable root: the private configured SENTRY agent workspace only.
- Command network: disabled. Native hosted web search remains independently available.
- Disabled resident surfaces: apps, plugins, browser/CDP automation, generic computer use, unmanaged MCP, and Codex-generated memories.
- Sensitive reads: SSH/GPG/cloud/browser/Codex-auth/SENTRY-private/biometric/security-state paths are denied.
- Host mutations: classified and audited by `tools/sentry_execution_authority.py`.

## Trusted-operator authority

A clear action requested directly by the operator in the current turn is the
authorization for that exact action. The host still validates the request,
canonicalizes its arguments, enforces workspace and no-overwrite boundaries,
and audits the result, but SENTRY does not add a redundant generic confirmation.

If the operator explicitly asks SENTRY to wait, prepare, show, or ask first,
the host creates one exact pending action. It becomes actionable only after the
prompt has been presented and speech has completed; the full 120-second reply
window starts then. Natural approvals, cancellations, questions, and revisions
are interpreted only in that active context. The record remains one-use and is
bound to its request, thread, restart epoch, and canonical argument hash.
Prior messages, webpages, screenshots, files, and tool output never supply
operator authority.

## Audit and privacy

Non-read attempts append metadata to the private mode-0600 execution ledger. Records include action/request/thread IDs, risk tier, target summary, authorization status, execution surface, outcome, error class, and duration. They exclude prompts, transcripts, raw audio, file/image contents, credentials, biometrics, exact private coordinates, and authentication state.

## Reporting

Report a suspected boundary bypass privately to the repository owner. Do not include secrets, biometric material, private coordinates, or captured ambient content in an issue.
