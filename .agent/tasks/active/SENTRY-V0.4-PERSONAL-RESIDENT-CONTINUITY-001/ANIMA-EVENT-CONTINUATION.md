# ANIMA event integration — frozen continuation

Active checkout: `/home/sketch/Projects/SENTRY` on atlas-desktop. Preserve the
dirty worktree; the old laptop/shared checkout is not the active source.

## Implemented and tested, not connected

- `tools/sentry_anima_events.py` contains an **inert**, one-shot queued-event
  lease primitive; `tests/test_sentry_anima_events.py` contains 11 synthetic
  tests. It accepts an already exact-claimed request, checks scope, marks
  provider-start before an injected executor, renews during execution, revokes
  the binding, and attempts one result submission. Ambiguity is not replayed.
- No queue consumer, qualified model executor, resident runtime hook, or speech
  hook exists. **Automatic ANIMA wake/TTS is NOT CONNECTED.** This is not owner
  feature completion. Result recording reports speech as `NOT_ATTEMPTED`.
- Final validation: **11 primitive tests / 178 combined focused tests PASSED**;
  Ruff, compilation, and whitespace checks PASSED. Runtime integration and
  end-to-end event delivery were NOT RUN. Validation used
  `/home/sketch/.venvs/sentry-ubuntu/bin/python` with temporary authority,
  workspace, session, ANIMA-config, and state paths. No real claims, model/TTS
  calls, configuration/service changes, or commits were made for this slice.

## Required decision and follow-up

1. Approve and qualify an autonomous execution mode inside existing SENTRY,
   with the same persona and voice but a separate ephemeral per-event context
   where restricted content requires it. Do not enable the old helper or create
   another daemon/persona. No qualified ANIMA autonomous route currently exists.
2. Add an atomic exact eligible Attention claim. Existing public claiming
   filters household/provider only; post-claim rejection still consumes work.
   Preserve old diagnostic/flood exclusions and never replay ambiguous work.
3. Add the same-process resident hook and acquire the existing turn lock before
   claiming. Do not feed autonomous data through `CodexNativeAgent.ask()`:
   that path handles operator authority and pending-action replies.
4. Enforce origin/principal, frozen catalogue, restricted-data boundaries,
   executor timeout/cancellation, and lease fencing. The primitive alone does
   not enforce executor qualification or terminate a hung injected executor.
   Per-turn tool restrictions do not prevent retained context influencing later
   broad-tool turns; `EPHEMERAL_RESTRICTED` must never enter persistent history.
5. Connect existing SpeechDispatcher/Kokoro with a distinct delivery receipt,
   then qualify claim → model → governed tools → result → speech, including
   concurrency, lease loss, privacy, and failure paths before enabling runtime.

Owner boundary: **voice-only** wake/microphone → SENTRY → existing TTS. No typed
chat or web conversational replacement; ANIMA configuration forms remain valid.
Direct mutation authority is also unfinished: the current host sends no identity
observation. Connector authentication is not owner authentication; mapped SENTRY
recognition cannot mint authenticated/strong-authenticated Core authority.

Source/tests are frozen. Lead owns architecture approval, hooks, deployment,
and end-to-end acceptance. No further implementation is authorized by this note.

## Superseding owner-authorized queue/runtime candidate — 2026-09-07

The historical inert-only state above is superseded by the owner's explicit
authorization to use the SAME persistent SENTRY brain for nonrestricted
household preferences/routines/memory/presence and useful event reasoning.
EPHEMERAL_RESTRICTED products remain excluded by Core/persistent MCP. Voice-only
interaction, no competing model/voice process, and no automatic production
enablement remain hard boundaries.

Source now connects the existing voice launcher to `configured_anima_events()`
and the existing `_AGENT`, then `AttentionQueueSource` at idle, the resident lock,
metadata eligibility, exact claim, provider-start, active lease, the same Codex
thread with per-turn restrictions, Core result, and existing Kokoro speaker.
The model chooses silent/speak/notify. Notification delivery is NOT_VERIFIED
because aggregate MCP success is not a route-specific delivery receipt. Pending
confirmation/auth, ambiguous execution/result, and TTS failure cannot become
invented delivery. No email route/recipient is created.

### Agreed Core/client contract

- POST `/v1/provider/requests/eligible`: origin AUTONOMOUS_ATTENTION,
  aware `not_before`, `max_age_seconds:120`, `limit:1`; returns EMPTY/items:[]
  or AVAILABLE/items:[request_id, household_id, provider_id, origin, created_at
  fields in a metadata object].
- POST `/v1/provider/claims/exact`: same origin/window plus exact request_id,
  worker_id, host UUID sentry_request_id, source_surface anima_attention.
  Returns existing CLAIMED/binding/fencing fields plus created_at and
  provider_started:false, or EMPTY on lost eligibility. No unfiltered fallback.
- Existing client.call is reused; no Core imports or new client method needed.
- Core owner Tesla confirms atomic PENDING/no-attempt/no-fence/never-started
  eligibility for authentic household-scoped SenseGuard/presence triggers.
  Both request and source-event times must satisfy the server/host epochs and
  120-second freshness. Its separate validation: 25 real PG/UnixHTTP target
  passes; 74 broader passes, one pre-existing PG skip (reported by Tesla).
- Source polls at most once per 15 seconds, one candidate per callback, and
  latches on ambiguous transport/execution. Local client/profile/schema/root
  and private-file allocation checks happen before queue contact/claim.

### Staged configuration; NOT applied by this contributor

Lead may add this optional object to the existing private ANIMA host config
after qualification, substituting real commissioned values, never secrets:

```json
{"auto_wake":{"enabled":true,"context_ready":true,"enabled_at":"<aware UTC enable epoch>","household_id":"<commissioned household UUID>"}}
```

Absent/disabled/not-context-ready leaves the callback disconnected. Malformed
configuration disables only this optional source, not ordinary owner voice.
Core independently requires `ANIMA_SENTRY_AUTOWAKE_ENABLED_AT`; missing is
disabled, and the later server/host epoch wins. No epoch is invented at restart.
Neither this source nor this note configures/enables/restarts any live service.

### Qualification boundary and remaining proof

- SENTRY combined focused tests: 213 PASSED with isolated authority/workspace/
  session/config/state. Interpreter: `/home/sketch/.venvs/sentry-ubuntu/bin/python`.
- Three tests execute installed Codex configuration-only commands against
  synthetic temporary profiles, without auth/model/MCP execution. They caught
  and regression-protect quoted dotted-key parsing failure and base-config MCP
  merging. Per-turn tables now serialize correctly; effective unexpected enabled
  MCP servers fail preflight. Relevant shell/web/browser/apps/plugins/image/
  code-mode/skill-install restrictions are configured; filesystem writes are
  downgraded and private denials/network denial preserved. Owner profile stays
  unchanged. The unified_exec backend flag still reports true on this CLI;
  shell_tool is false. Do not present backend selection as an access grant or
  these config checks as a live adversarial tool-execution proof.
- Frozen request-bound MCP still owns exact catalogue, ordinals, policy and
  restricted-content gates. No blanket prohibition on owner-approved persistent
  household context is introduced, and no cross-turn privacy guarantee is made.
- Live real-model autonomous tool isolation and event-to-speaker delivery are
  NOT RUN. Lead owns controlled commissioning/reload and subsequent operational
  proof, without a fabricated household security warning or seeded recipient.
- Earlier hook validation included one unisolated 27-test run that may have
  appended synthetic authority-audit entries. No history was deleted/repaired;
  test isolation was added. This queue slice used isolated state and made no
  production config/service/model/device changes.

Current-state/Notion and final publication remain lead-owned; this append does
not rewrite prior evidence or claim whole-project acceptance.

## Real read-smoke negative evidence and strict-config correction — 2026-09-07

Owner authorized one read-only, no-TTS direct request using the existing agent
and persistent thread, with the autonomous restrictions applied in the bounded
diagnostic runner. The legacy pending record status was exactly lowercase
`expired`; it was preserved unchanged and is not an unfinished owner action.

- Query ID: `b5350876-c125-4838-8d6f-4af8971b8923`.
- Core request: `e594277c-6100-58a9-bbdd-5cb1b074b606`.
- Same resident thread: `01a05f8f-71f3-7f20-bc2a-14781c0f4e58`.
- Origin: DIRECT_SENTRY_INTERACTION; no fabricated Attention/security event.
- Provider-start: PROVIDER_RUNNING; CLI exit 1; zero MCP calls, metadata READY.
- Core receipt: RECORDED; result UNKNOWN_RESULT. No retry or automatic replay.
- Context digest: `7ca434ce51a358fddb6edae2aa554b8d58229d0ec87a35962d02989eb7b982e2`.
- Catalogue digest: `ba2085ff27bb46ad79b76de7de1c73af30953bace625cca5afbf1994b5fc7c43`.
- No memory write, physical command, notification or TTS. No transcript/private
  context was copied into this record; ordinary Core/audit lifecycle occurred.

No-auth/no-existing-session reproduction identified the exact startup cause:
strict Codex execution rejects `tools.view_image`. That unsupported override
was removed; supported `features.view_image=false` remains. MCP config listing
alone had missed this failure because that command does not support strict
configuration validation.

Preflight now also invokes strict exec with a deliberately missing output schema
in a private temporary directory. It must reach that precise missing-schema stop
after parsing configuration and before model/session/MCP execution. Any other
failure blocks before queue contact. Installed actual resident profile/AppArmor
launcher passed this check and effective-MCP isolation after the correction,
without a Core request or model invocation. Focused strict rejection regression
and existing CLI configuration regressions pass (44 focused checks). The first
214-test broader run failed two profile-isolation assertions because the live
preflight command's SENTRY_CODEX_HOME environment was inherited by that test
run. Those invokers were mocked; no new Core/model request occurred. The broader
suite must be rerun without the live runtime environment before a pass claim.

Final isolated rerun, explicitly unsetting SENTRY_CODEX_HOME and
SENTRY_CODEX_EXECUTABLE before setting temporary test-state paths: **214 PASS**
in 4.885 seconds. Scoped Ruff and whitespace checks PASS. This supersedes the
environment-contaminated test result, not the real read-smoke UNKNOWN_RESULT.

Source frozen again. Real-model read success remains NOT RUN after the fix;
the failed request stays ambiguous/terminal rather than being replayed. Lead
requested a deployment hold; no new claims were started. The deployed disabled
EMPTY response is not proof of enabled OwnerBoundary factory wiring; Tesla owns
that separate factory correction and its PG/UnixHTTP qualification.

## Learning/initiative delivery guard candidate — 2026-09-07

Owner's new Ring/multi-signal/review request is scoped here to SENTRY guidance
and autonomous delivery guards. Voice-only, the same persistent SENTRY, existing
manual capabilities, exact Core policy and restricted-content exclusion remain.
No Ring/provider/device action, model invocation, poller activation, private
configuration/service write, restart, commit or deployment occurred in this slice.

Lead-selected wire contract is the host-fetched bound Core context's
`household_context.initiative`: `status` AVAILABLE/UNAVAILABLE and `notification`
containing strict booleans `allowed`, `required`, exact `request_id`, aware ISO
`evaluated_at`, and an enumerated reason. Host accepts a maximum 30-second age
and 5-second future skew. Only allowed ALWAYS_NOTIFY or LEARNED_PROACTIVE can
permit delivery; required is valid only with allowed ALWAYS_NOTIFY. Core, not
host/model elapsed time, decides observed-day learning and explicit event policy.

Implemented in `tools/sentry_anima_events.py`: after model execution, while the
binding is active, refresh disposition directly from Core before result submit.
Missing/malformed/stale/cross-request/denied/error results suppress unsolicited
speech; silent reasoning is not disabled. The model's permission fields are never
consumed. Suppressed speech submits NO_ACTION with no response; denied notify
submits PARTIAL, never claims sent. Existing tool/auth gates remain authoritative.
After recording, recheck disposition freshness before TTS; recorded result and
actual delivery remain distinct. No change to direct owner voice adapter.

Important remaining ANIMA boundary integration: an event model may invoke MCP
notification tools before its final. A host final guard cannot undo that dispatch.
Core/MCP must enforce the same current disposition BEFORE notification invocation.
Also Core rejects context reads after terminal result, so Core must re-evaluate
permission at result submission and provide an explicit delivery decision or
refuse recording of a now-disallowed RESPONSE. The current host pre-submit check
plus freshness check does not alone close that changed-setting race. Automatic
delivery remains unqualified/off until lead wires and tests this contract; no
claim is made that current installed Core or unattended voice enforces it yet.

Guidance in `tools/sentry_codex_agent.py` and
`integrations/codex/SENTRY_AGENT_INSTRUCTIONS.md` now requires silent learning
except explicit ALWAYS_NOTIFY; learned proactivity respects current preferences.
Autonomous daily/endday/multiday reviews are silent recommendations for owner
review. Multi-signal reasoning preserves timestamps, gaps, independent-source
coverage, uncertainty and no invented identity/intent. Inferred routines remain
distinct from owner rules. Reusable workflows are versioned/reviewable proposals,
not auto-created executable code, installed scripts, timers or permissions.
This is guidance and delivery enforcement, not implemented Ring support or a
new review scheduler. Lead-reported guided read/note proof is not an unattended
event/TTS qualification and does not erase prior negative smoke evidence above.

Validation: 223 isolated focused/regression unittest checks PASS in 5.016s using
`/home/sketch/.venvs/sentry-ubuntu/bin/python -B`, temporary authority/session/
workspace/state/config and unset SENTRY_CODEX_HOME/SENTRY_CODEX_EXECUTABLE.
Scopes: resident events, lease primitive, direct ANIMA, Codex agent, execution
authority, proactive, conversation bridge, resident runtime, MCP, always-on
voice, voice and launcher. New guards/guidance add nine tests, including model
permission forgery, learning/review silence, exact binding, stale submission,
malformed/cross-request timestamps, context outage and learned model choice.
The first 222-test run failed five new test assertions due to accumulated mock
call counts; test isolation was corrected, then 222 and final 223 both passed.
Scoped Ruff and git diff whitespace checks PASS. Evidence: E4 for host guards;
live unsolicited notification/TTS and complete cross-boundary enforcement NOT RUN.

Changed this slice: the three source/instruction files above,
`tests/test_sentry_anima_resident_events.py`, and this append-only handoff note.
Other dirty source/history preserved. CURRENT/OUTCOMES/Notion publication remains
lead-owned. Candidate frozen pending final delivery contract from lead.

## Core result-receipt reconciliation — 2026-09-07

Lead implemented Core's pre-notification invocation ceiling and final result
normalization. Read-only source verification confirms service result receipts
now carry `status`, actual `result_status`, and current `notification` disposition.
This supersedes the preceding unresolved wire-contract gate, not the unrun live
autonomous/TTS qualification.

`QueuedEventLease` now uses the actual recognized Core recorded result status.
A legacy receipt missing result_status for submitted RESPONSE, or an invalid
explicit result_status, becomes locally UNKNOWN_RESULT rather than authorizing
speech. Non-response legacy compatibility remains. Result recording and actual
delivery are still distinct, and the one-shot lease never retries ambiguity.

The event host uses only the validated notification returned with the Core
result receipt for final speech permission, never the pre-submit snapshot.
It requires a submitted speech response, actual recorded RESPONSE, strict
request-bound notification validity/freshness, and an available speaker.
Core NO_ACTION normalization cannot be promoted back to the model's response.
Missing/denied/malformed/stale/cross-request receipt permission blocks TTS.

Changed only `tools/sentry_anima_events.py`,
`tests/test_sentry_anima_events.py`, `tests/test_sentry_anima_resident_events.py`,
and this append-only record. Existing dirty work preserved; instructions were
not changed again. Four additional test methods include the requested fake
cross-boundary settings-change-during-submission case: allowed pre-submit
context -> Core RECORDED/NO_ACTION with denied permission -> zero TTS, one model
attempt and one submission. Receipt rejection matrix and legacy/no-retry
regressions also pass.

Validation: **227 isolated focused/regression tests PASS**, 5.452s, same isolated
Python/runtime recipe and scopes as above. Scoped Ruff and git diff whitespace
checks PASS. E4 for host receipt reconciliation. Real Core/PG-to-TTS execution
NOT RUN here; Core integration tests remain lead-owned. No model invocation,
live claim/poll, TTS, private config/service change, restart, deployment or commit.
Source frozen for lead integration/review.

## Required notification without a delivery decision — 2026-09-07

Owner clarified that required ALWAYS_NOTIFY cannot be called handled when the
model chooses silence. The host now fetches current bound Core initiative even
for a valid silent final. If required is true, it submits PARTIAL with fixed
detail `REQUIRED_NOTIFICATION_NOT_PRODUCED`, response None, and records the
session turn as autonomous_partial. The one-shot model/result lifecycle is
unchanged: no forced TTS/greeting, invented recipient, fallback channel or retry.
Optional learned silence and REVIEW_SILENT with required false remain NO_ACTION;
notify choices retain governed channel behavior and unverified delivery status.
Existing policy/auth/ambiguous failures remain authoritative rather than being
overwritten by this check. The only new durable detail permitted by EventResult
is that fixed code with PARTIAL; arbitrary model text is rejected.

Guidance and instructions explicitly distinguish required delivery from proof
of delivery and prohibit calling silence handled. Changed source this follow-up:
tools/sentry_anima_events.py, tools/sentry_codex_agent.py,
integrations/codex/SENTRY_AGENT_INSTRUCTIONS.md; focused tests changed in
tests/test_sentry_anima_events.py and tests/test_sentry_anima_resident_events.py.
Other dirty work preserved. This handoff is the only project-state write here;
shared CURRENT/OUTCOMES/Notion remain lead-owned.

Final validation: **229 isolated focused/regression tests PASS**, 5.614s, using
the same isolated runtime/suite recipe above. Ruff and whitespace checks PASS.
New required-silence and silent-review tests plus strengthened fixed-detail and
guidance checks prove PARTIAL/no TTS/one attempt and preserve quiet notification
choice. E4 host evidence only. No runtime activation, live models/claims, audio,
config/service changes, deployment or commits. Source frozen.

Cross-boundary edge for lead: if policy changes from optional to required only
inside final result submission, Core must normalize a now-required NO_ACTION
to PARTIAL/fixed missing-notification detail as well. The host must not rewrite
Core's already-recorded status or resubmit it; this slice's required check uses
the fresh pre-submit bound disposition. The existing returned-disposition guard
continues to govern all actual TTS delivery independently.

## Independent autonomous wake and post-alert follow-up — 2026-09-07

Owner clarification: microphone/wake-word `LISTENING` is not a prerequisite for
an ANIMA alert. Sleep mode is the explicit autonomous off switch. The listener
now runs the ANIMA event poller in its own worker while awake, so an eligible
SenseGuard event can be evaluated and spoken even when no microphone chunks are
arriving.

The product has two independent wake sources: an operator-intonated wake word
and a Core-authorized autonomous ANIMA event. After either source's spoken
response is successfully delivered, the existing bounded follow-up window is
opened. The operator can therefore ask a follow-up question after an autonomous
alert without saying the wake word again. Active capture, current speech,
approval dialogue, or sleep still defer/disable safely; they do not define the
alert's eligibility.

Focused voice/event validation now covers awake processing without `LISTENING`,
sleep suppression, successful autonomous TTS opening follow-up, failed delivery
not opening follow-up, and worker execution with zero microphone chunks.
