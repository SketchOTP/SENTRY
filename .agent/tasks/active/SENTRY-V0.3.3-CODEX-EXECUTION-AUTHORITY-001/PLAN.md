# Plan

1. Verify baseline, services, dirty state, installed Codex enforcement surface, and preserve the production thread and developer profile.
2. Install a dedicated resident permission profile and workspace; remove legacy unrestricted launch flags and inherited environment authority.
3. Add a host-side risk classifier, private audit ledger, exact pending-authorization broker, confirmation/cancellation handling, and thread controls.
4. Gate MCP mutations through the authority layer and add truthful status tools.
5. Add focused tests, CI coverage, and security/architecture/operator documentation.
6. Run automated, adversarial, and bounded live qualification; restore the required service state.
7. Synchronize Authority and Notion, commit/push, and verify `main == origin/main` with a clean tree.

Current checkpoint: steps 1-5 are implemented in the preserved working tree.
The superseding `SENTRY-V0.3.3-NATURAL-ACTION-HANDOFF-001` trusted-operator
policy is implemented. A real spoken direct move completed once without a
redundant confirmation, preserved the file hash, and recorded
`direct_current_turn`. The operator then explicitly waived synthetic live
approval/cancellation/revision drills as unrepresentative of normal use; those
paths remain covered by host-side tests. Final security matrices, exact-code
regression, release, CI, records synchronization, and service restoration are
in progress.
