# Current Project State

Last updated: 2026-09-01

## Current stage
V0.3.2 — bounded conversational turn-taking is active on the qualified Vosk →
Whisper → bounded ConversationOrchestrator → Kokoro office path. Schema remains 8.

## Current objective
After an explicit `Sentry` request receives successful local speech, permit at
most two wake-free follow-up turns in a short host-bounded focus window. Reuse
the existing RAM-only conversation context; do not add persistent memory,
barge-in, AEC, a new wake/STT model, or a second conversation runtime.

An operator-authorized read-only public-web extension is now implemented on the
same bounded conversation host. Luna may plan public-source search, direct
public-page reading, and public place/date weather, but it never receives a
browser or generic network access. The host validates public HTTP(S) targets,
redirects, DNS results, content bounds, and the no-write/no-login boundary.
This does not qualify V0.3.2 turn-taking or authorize persistent memory.

## Active directive
`SENTRY-V0.3.2-BOUNDED-TURN-TAKING-001` remains active. The operator override
`SENTRY-OPERATOR-READ-ONLY-WEB-ACCESS-001` is implemented and regression
protected. The initial request still requires
`Sentry`; after a successfully delivered user-initiated answer, the listener
may enter a separate `FOLLOWUP_LISTENING` state for 8 seconds and at most two
wake-free turns. Timeout, hard turn limit, errors, shutdown, proactive/reminder
speech, and explicit PTT must never extend or create focus. Voice remains
opt-in and resident services remain inactive outside bounded qualification.

## V0.3 conversational orchestration — 2026-08-31
- `tools/sentry_ask.py` now sends normal user text through `ConversationOrchestrator`, rather than using reminder/preference/weather/routine selectors as the primary natural-language router. The old selectors remain compatibility helpers only.
- The OAuth `codex exec` surface was inspected: it supports strict output schemas, but not a request-scoped host function catalog. SENTRY therefore uses the authorized bounded two-phase form: one strict Luna planner → host-validated localhost tool calls → one strict Luna synthesis. Hard limits are three local tools, one mutation, and two Luna invocations per request.
- The capability set is current office state, bounded office history, reminders, acknowledgement preference, recent proactive action/feedback, routine snapshots, cached private-home weather, plus host-bounded public-web search/page reading/public place-date weather. Luna exposes no database, filesystem, shell, browser, credentials, audio, private coordinates, enrollment data, or arbitrary tool execution. Public network reads remain host-validated and read-only.
- Planning schema compatibility required a closed nullable argument envelope because the installed strict-schema endpoint rejects array-item `oneOf`; null fields are removed before the normal per-tool validation. The host still independently rejects unsupported tools, arguments, over-budget plans, and more than one mutation.
- Conversation context is process-RAM-only, per caller/session, capped at four prior user/assistant turns, and expires after ten minutes. It is not logged, persisted, embedded, or available after restart.
- Text live proof used the real localhost API without production mutation. Natural queries selected only the relevant reminder, preference, proactive-history, routine, weather, current-state, or two-domain reminder+current-state tools. A follow-up “What was it again?” reused RAM context and selected reminder evidence. Weather and current-state unavailability were stated truthfully rather than replaced with M4 history.
- Five observed Vosk/Whisper spoken requests crossed the same path: reminder, greeting preference, recent proactive explanation, historical first-seen time, and weather. The operator reported each as answered correctly; no unrelated physical-state fallback occurred. A final metadata-only diagnostic sample recorded a 1,580.098 ms speech-end-to-dispatch interval and 10,253.513 ms STT-complete-to-grounded-answer interval, with two Luna calls and successful local speech.
- Temporary API, perception, listener, status window, and capture processes were stopped after testing. The actual temporary perception run preserved normal observed history only; no synthetic physical event or production reminder/preference was created.

## V0.3 M4 current-state truthfulness — 2026-08-31
- `GET /health` now reports database health independently from a bounded `perception` runtime object: `fresh`, `stopped`, `stale`, `missing`, or `malformed`, including heartbeat time/age, process state, camera/room summary, `current_physical_available`, and a reason. Production state API service passes the canonical heartbeat path, a 75-second freshness threshold, and `America/New_York` explicitly.
- Only parsed, alive, fresh heartbeat evidence with an `online` camera permits current room state, people, and open-session facts. Fresh `degraded`/`offline` source remains current-occupancy unavailable. Stopped/missing/stale/malformed perception omits those current facts without changing SQLite database health.
- Clearly current questions return a deterministic unavailable response with zero Luna calls when live physical evidence is absent. Historical sessions/events/first identification/last confirmed empty evidence remains available, so stopped perception does not erase history.
- Source timestamps remain unchanged. M4 fact packets add deterministic `*_local_display` values via `zoneinfo`; normal user-facing clock answers use Eastern 12-hour AM/PM with date/timezone where appropriate. EDT, EST, and both DST transitions are regression-covered.
- Production proof: with perception stopped, `/health` reported healthy schema-8 SQLite and `perception.status=stopped`; “Is anyone in the office?” returned current-state unavailable with zero Luna calls. A historical question remained partially grounded and answered with Eastern 12-hour display. A bounded perception process emitted a fresh heartbeat, then its clean shutdown restored `process_alive=false`.
- Focused M4 tests passed 16/16; affected focused suites passed 96/96; complete Ubuntu regression passed 201/201. Schema remains 8; no prior physical history was rewritten. The bounded fresh-heartbeat proof ran the real production pipeline and therefore persisted its normal `system.started`, camera-state, observed occupied session 8, and `system.stopped` events; no event/session was seeded or manually edited. Continuous perception remains at zero Luna calls. M4 implementation commit: `98fc71ab76c18468745321ee63a706249efeea4`.

## V0.3 always-available voice — 2026-08-31
- The committed V0.3 implementation at `7d605af` contains the Architect-authorized local PipeWire → Vosk single-token wake → Silero VAD/endpointing → bounded in-memory utterance → Whisper `tiny.en` command STT → existing `sentry_ask.py` → Kokoro/PipeWire listener, with an opt-in systemd unit, shared flock-based speech-activity gate, pre-speech buffer, and metadata-only diagnostics. This implementation remains unqualified as an always-available resident interface.
- Focused always-on voice tests pass `13/13`. A visible Zenity indicator initially appeared off the active display under this host's desktop scaling; it was corrected to use active-window X11 placement, and the operator confirmed the repaired indicator works. The listener and API were always temporary and were stopped after the test.
- Live listener metadata observed four wake detections/command dispatches and three rejected non-wake segments. Dispatch-latency samples were `1.516–1.619s`. These counts are not accepted wake-reliability evidence because the required structured 20/20/15-minute protocol was not completed.
- Qualification blocker: with perception intentionally stopped, the actual local DB's last room-state record was `empty` at `2026-08-30T14:24:29.186671+00:00`, while `system.stopped` was also persisted. `/health` reported only SQLite availability. M4 nonetheless presented this stale room record to Luna as current for “Is anyone in the office?” and did not establish a local/Eastern 12-hour time-presentation contract for “What time did I come in?”. This is a truthful current-state/formatting defect outside the V0.3 voice-only directive. No M4 code was changed.
- All SENTRY units are inactive; `sentry-voice.service` is not installed/enabled; no `pw-record`, state API, or always-on listener process remains. No audio or transcript artifact was retained.

## V0.3.1A dedicated wake reliability selection — 2026-08-31
- **Status: BLOCKED / NEEDS ARCHITECT DECISION.** The already-failed `VAD → Whisper full utterance → text starts with hey sentry` wake boundary remains superseded. The preserved uncommitted listener components remain valuable, but no dedicated wake detector has qualified for integration.
- Candidate 1, custom local openWakeWord-compatible inference, has clean input provenance: 40 usable positive and 40 usable negative explicit prompted local clips plus generated Gaussian noise. Model v2's Stage-A result was invalidated because it used only 10 positive clips. After correcting repeated positive-directory handling, full-capture model v3 failed held-out validation at its best threshold: 22 negative false positives and 66.7% positive recall. Candidate 1 is now rejected without an additional live Stage-A run. An earlier apparent 107 detection count was traced to evaluator lifecycle/debounce instrumentation and is not retained as a false-wake result.
- Candidate 2, a custom local microWakeWord-style TensorFlow Lite classifier using the complete explicit capture data, generated noise, and an Apache microfrontend, failed held-out validation with 35 negative false positives at threshold `0.50` despite 1.0 positive recall. It remains rejected before consuming more live operator time.
- Candidate 3, Porcupine, remains unavailable under the directive because no existing authorized Picovoice AccessKey/configuration was found. No account, secret, or network audio service was added.
- No main-listener integration, systemd activation, full regression, or acceptance commit has run. Candidate harness/training files and the pre-existing V0.3 voice implementation remain uncommitted in the working tree. All SENTRY services and temporary audio/evaluator processes are inactive outside the bounded retraining/evaluation step.

## V0.3.1A pretrained KWS selection — 2026-08-31
- Wake-word correction: the owner selected the exact one-word wake token **“Sentry”**; “Hey Sentry” is historical/obsolete for this selection run. The live evaluator visibly displayed `GET READY` then `SPEAK NOW` with the exact required utterance on every prompted attempt.
- PocketSphinx 5.1.1 was built in an isolated evaluator prefix from its source archive (SHA-256 `675778b309a22dfc9b7d37f7621976bba491d2a5f8c59696bd77fd6d07271355`). Its bundled CMUdict maps `sentry` to `S EH N T R IY`. After its one permitted KWS result-delay correction, the valid prompted positive screen achieved 9/10, but PocketSphinx triggered on two ordinary sentences containing “Sentry”. It is rejected for the directive's strict no-false-wake definition.
- Vosk 0.3.45 and the isolated official `vosk-model-small-en-us-0.15` model archive (SHA-256 `30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498`) were installed outside Git. The restricted vocabulary is `["sentry", "[unk]"]`; final-result-only decoding was its one permitted decoder adjustment. Its valid Stage-A screens achieved 10/10 prompted wakes and 0/10 non-wake detections for phrases not containing the owner-selected word.
- Owner clarification: uttering “Sentry” inside ordinary conversation is acceptable as a wake. This relaxes the Architect directive's original difficult-negative examples that contained the same one-word wake token; it must be surfaced to Architect and is not silently counted as the directive's original 20/20 false-wake proof.
- Stage B began but the operator stopped it after five prompts as excessive. The required 20-positive, 20-negative, 15-minute ambient, latency, resource, and queued-command-audio evidence is therefore **not complete**. No detector is formally selected, no listener integration/service enablement occurred, no raw audio/transcript was retained, and all SENTRY/evaluator processes are inactive.

### Superseded current-state note — 2026-08-31
- The preceding selection evidence is historical. The owner subsequently selected Vosk and its integration was committed as part of `7d605af`. The current boundary is not "no listener integration"; it is that the integrated Vosk always-on interface remains implemented/unqualified and opt-in/inactive pending its separate final acceptance decision.

## V0.2 event-triggered reminders — 2026-08-30
- Schema version 8 adds one bounded `event_reminders` table for `primary_user` / `office` / `next_primary_user_office_session`, with a partial unique index enforcing one pending reminder and request provenance for idempotent creation/cancellation.
- Deterministic `sentry_ask.py` intent handling supports create, query, and cancel. Timed, recurring, weather, leave-the-house, and other scheduler-shaped requests fail closed with zero Luna calls. Reminder text is normalized, control-character-free, limited to 120 characters, and only the explicit body is persisted.
- Creation records the currently open session, if any; only a later valid `person.identified` event in a distinct session can trigger delivery. Track changes and same-session re-identification do not qualify.
- Physical/source/session/startup gates run before reminder eligibility. An explicit reminder outranks acknowledgement preference, cooldown/budget, and contextual weather for the same source event, while still respecting global enable and speech-busy behavior. Routine facts remain absent.
- Claiming inserts the durable `proactive_actions` record and transitions `pending` to `claimed` atomically before local speech. Success is `delivered`; confirmed speech failure is `failed`; a claimed row found after restart becomes `failed` with `unknown_delivery_after_restart` and is never replayed.
- Isolated qualification covered current-session exclusion, future-session delivery, preference suppression bypass, weather priority, failure/crash/replay safety, API/CLI behavior, one-pending enforcement, idempotence, and Atlas restore. Focused reminder tests passed 14/14; full Ubuntu regression passed 180/180. The actual production DB migrated to schema 8 with zero reminder rows and was not seeded. Resident services remain stopped by operator request.
- Production reminder implementation commit: `dcd36d35b9542cb161da7dcf37939191c5c79663` (`feat: add next-session event reminders`). Final documentation commit: `38ec6f6c5d7e7e188f1517a24f69c4e47523cf13`.

## V0.2 contextual weather proactivity — 2026-08-30
- The existing `person.identified` / current occupied-session event remains the only candidate. Existing physical, source-health, startup, preference, dedupe, cooldown, budget, and speech-busy gates run before contextual weather evaluation.
- Fresh weather is consumed only from the local schema-7 cache. The deterministic window is the event timestamp through 120 minutes afterward; a usable overlapping forecast probability of at least 60% is required. Missing probability is `weather_insufficient`; no overlap or below-threshold probability is `weather_not_relevant`.
- New persisted suppression reasons are `weather_unconfigured`, `weather_unavailable`, `weather_stale`, `weather_insufficient`, and `weather_not_relevant`. None invokes Luna. Relevant weather adds only bounded `weather-context-health` and `weather-near-term-precipitation` facts; routine facts and alerts remain absent.
- The production weather configuration remains absent, production weather rows remain zero, and the production candidate is therefore expected to suppress as `weather_unconfigured`. No production coordinates or physical history were changed.
- Isolated real-NWS proof fetched a fresh public-coordinate snapshot with 25 forecast periods, zero alerts, no component errors, and a 32% maximum probability in the next 120 minutes; it correctly suppressed as `weather_not_relevant` with zero Luna calls. A separate normalized relevant fixture at 80% produced one bounded speech decision and one delivery; replay returned `duplicate` with zero additional Luna calls.
- Contextual weather tests passed 14/14; the combined contextual/M5/weather suite passed 39/39; the complete Ubuntu regression passed 166/166. Resident services were left stopped by operator request. Implementation commit: `57764c5`.

## V0.2 weather context — 2026-08-30
- Schema version 7 adds `weather_snapshots` as derived external-context records. Local SQLite remains authoritative on ext4; Atlas receives complete snapshots only through the accepted backup mirror.
- `perception/weather.py` implements the bounded NWS adapter with explicit operator coordinates, stable User-Agent, 24-hour point-resource caching, bounded retries, normalized current/near-term forecast/alert fields, source fingerprints, and explicit `fresh`/`stale`/`unavailable` status.
- `GET /v1/weather` is localhost-only and omits precise coordinates and provider resource URLs. Weather intent routing is deterministic; stale/unavailable weather returns a truthful limitation without Luna, while fresh weather uses the existing allow-listed M4 packet and at most one Luna turn.
- `sentry-weather.service` / `sentry-weather.timer` are independent user-systemd units. The installer copies them but enables the timer only when local weather configuration is explicitly enabled with coordinates. `Linger=no` remains the startup boundary.
- Production configuration was inspected without coordinates, so production weather remains disabled and no production weather rows were seeded. Isolated public-coordinate NWS transport/normalization succeeded; it is not a local-weather claim.
- Focused weather tests passed 11/11; the combined weather/runtime/store suite passed 38/38; the complete Ubuntu regression passed 150/150. Perception remains outside the weather path with zero Luna calls; services were left stopped by operator request.
- Implementation commit: `9a528fa` (`feat: add read-only NWS weather context`), pushed to `origin/main`.

## V0.2 preference + proactive feedback memory — 2026-08-30
- Schema version 6 adds append-only `preference_events` and `proactive_feedback` ledgers. The sole supported key is `proactivity.primary_user_session_acknowledgement`, with typed `allow`/`suppress` values and `default` when unset.
- Deterministic `sentry_ask.py` commands support set, allow, clear/forget, recall, and bounded explicit feedback. Unsupported arbitrary “remember X” requests fail closed with zero Luna calls. Mutations are provenance-backed and idempotent by source request ID.
- M5 now checks the preference after fundamental event/session/source-health gates and before dedupe/cooldown/budget/Luna/speech. Explicit suppression persists `user_preference`; allow/default retain the accepted M5 path. Routine facts do not enter M5.
- Localhost API adds metadata-only preference/feedback reads and writes plus bounded recent delivered-action resolution. API enum validation, one-action feedback scope, non-delivered rejection, restart/Atlas preservation, and privacy boundaries are covered.
- Qualification used isolated databases and did not write a personal preference to production. The real production database was inspected read-only before deployment: schema 5, no preference events, no feedback rows, healthy local SQLite, and no production preference mutation.
- Focused preference tests passed `10/10`; full Ubuntu regression passed `139/139` with existing warnings only. M5 deterministic suppression remains zero Luna; continuous perception remains zero Luna. Reactive voice remains compatible through `sentry_ask.py`.
- Preference + feedback memory is qualified. Broader semantic memory, inferred preferences, routine-driven proactivity, and new contextual sources remain gated.
- Implementation commit: `c58f2c7` (`feat: add explicit preference and proactive feedback memory`), pushed to `origin/main`.

## V0.2 routine-grounded conversation — 2026-08-30
- `tools/sentry_routine_intent.py` deterministically routes habitual language to one of four accepted routine types and an explicit all-days/weekday/weekend/named-weekday scope. Non-habitual questions stay on the physical-history path; unsupported habitual activity/causal questions fail closed.
- `tools/sentry_grounding.py` adds an allow-listed, metadata-only routine fact packet with stable IDs such as `routine:office_session_start_time:weekday`. It retains current physical facts so routine patterns cannot override present state; it does not expose raw sessions, biometric data, or M5 context.
- `tools/sentry_ask.py` returns deterministic sparse-history answers with zero Luna calls when selected snapshots are `insufficient`; `observed` and `stable` snapshots may use at most one existing low-effort Luna turn with explicit maturity wording rules. Routine source failure is non-fatal to ordinary physical queries.
- The actual resident API remained healthy at schema 5 with Atlas mirror `ok`. Five live routine questions returned evidence-insufficient answers from the real 40-snapshot production set (all `insufficient`), with no routine claim and zero Luna calls. The accepted M4 voice path reuses `sentry_ask.py`; no fresh microphone run was required.
- Focused routine-conversation tests passed `17/17`; full Ubuntu regression passed `129/129` with the existing multiprocessing fork deprecation warning. M5 routine isolation and continuous perception Luna-call count remain `0`.
- Routine-grounded conversation is qualified. Routine statistics remain derived/rebuildable; routine-driven proactivity remains gated for a future Architect directive.

## V0.2 routine statistics — 2026-08-30
- Schema version 5 adds append-only derived `routine_snapshots`; physical sessions/events remain immutable source truth.
- `perception/routines.py` implements exactly four routine types: observed session start clock time, completed observed session duration, interruption-free absence between sessions, and earliest confirmed `primary_user` time per session.
- Analysis preserves UTC source timestamps and uses configured `America/New_York` IANA timezone, 56-day lookback, circular clock-time statistics, and median/MAD/p25/p75/min/max/relative-MAD duration statistics.
- Maturity requires both sample count and distinct local dates: observed at 5/5, stable at 8/8 plus resultant length >=0.80 for clock routines or relative MAD <=0.35 for positive durations/intervals. Labels are heuristic maturity states, not probabilities.
- Uncertain/restart-reconciled/incomplete sessions and absence intervals crossing system or camera interruption events are excluded with reason counts. First identity time is explicitly not exact personal entry.
- Production refresh against `/home/sketch/.local/share/sentry/sentry.db` wrote 40 latest snapshots (four types × ten scopes), all `insufficient` because natural history is sparse. No production history was seeded or rewritten.
- `GET /v1/routines` returns latest metadata-only snapshots on the existing localhost API. `tools/sentry_routines.py refresh/show` provide bounded CLI operations. Unchanged source/config refresh is idempotent.
- `sentry-routines.service` and `sentry-routines.timer` are installed/enabled as an independent user-systemd oneshot/timer: two-minute initial delay, six-hour cadence. Routine refresh failure does not control resident perception/API/proactivity.
- Focused routine suite passed `17/17`; combined routine/store/mirror/resident checks passed `38/38`; full Ubuntu regression passed `120/120` with one known Python multiprocessing deprecation warning. Local and Atlas schema-v5 databases passed integrity checks; resident services remained healthy at approximately 7.5 FPS after startup.
- Routine statistics are derived/rebuildable and are not yet included in conversational grounding or proactive judgment. A later Architect directive is required for that boundary.

## V0.2 resident runtime — 2026-08-30
- Native systemd user services are installed, enabled, and running for the authenticated `sketch` user session: `sentry-perception.service`, `sentry-state-api.service`, and `sentry-proactive.service`.
- Perception uses the existing accepted production config and publishes a metadata-only heartbeat at `perception-data/runtime/health/perception.json`; it never writes frames or audio.
- Proactivity now has `--watch --poll-seconds 1`, preserving M5 persisted-event dedupe and zero-Luna deterministic suppressions.
- Units use `Restart=on-failure`, `RestartSec=10s`, `StartLimitBurst=5`, and `StartLimitIntervalSec=300s`. The user manager startup condition is the authenticated desktop/user session; `Linger=no` is explicit and boot-before-login is not claimed.
- Production config is local at `~/.config/sentry/config.json`, mode `0600`, created once from the checked-in example with accepted proactivity enabled. Live SQLite remains `~/.local/share/sentry/sentry.db`; Atlas remains the snapshot mirror.
- Fifteen-minute supervised probe passed: 900 seconds, 30 metadata samples, all units active, localhost API healthy, Atlas mirror `ok`, no probe failures. Perception final sample: V4L2/MJPEG/1280x720/15 FPS, `7.607` processed FPS, `115.696 ms` median and `134.015 ms` p95.
- Individual API/proactive/perception restart and SIGKILL recovery passed. Proactive action count remained unchanged; perception recovery added no room entry/exit event and preserved zero open sessions. Clean stop left zero resident component processes; starting enabled units restored the stack.
- Final local and Atlas SQLite copies passed integrity checks with schema 4; logical event/session/action content matched, with no persistence or mirror error. Continuous perception Luna calls remained `0`.
- V0.2 resident runtime is **QUALIFIED**. Routine statistics/learning, additional rooms/sensors, and other post-V0.1 expansion are not active.

## Owner/operator M6 decision — 2026-08-29
- M5 is accepted at `e6b56b0f446bc153ba7f936387fad8ec954cb1f6`.
- The former 72-hour unattended soak is **SUPERSEDED / WAIVED** and must not be resurrected.
- The final M6 requirement is a **30-minute unattended soak**, deliberately shorter and not equivalent reliability evidence to 72 hours.
- Reactive voice is **ACCEPTED**: physical microphone → Whisper `tiny.en` → M4 grounded state → one Luna turn → local Kokoro → PipeWire speaker proof passed at `1ce3e611`.
- M6 30-minute unattended final soak **PASSED**. SENTRY V0.1 is **ACCEPTED** within the office-only capability boundary. The former 72-hour requirement remains **WAIVED / SUPERSEDED**.

## Owner/operator acceptance — 2026-08-28
- Practical Ubuntu camera/human-detection behavior is **ACCEPTED BY OWNER/OPERATOR DIRECTION** for V0.1 progression.
- Detector edge cases, low-light boundaries, individual tracking, and physical camera recovery remain documented operational risks; no further detector qualification is required.
- Detector selection is frozen on corrected YOLOX-S. M2 and M3 are accepted within their recorded evidence boundaries.

## Architect correction — 2026-08-28
- The prior `230dafa` transition claim is preserved as history. The later explicit owner/operator decision now supersedes the temporary correction that reopened detector qualification; do not rewrite `230dafa`.
- Ubuntu/V4L2 platform: **VERIFIED**.
- Original YOLOX Stage A failure: **VERIFIED**.
- Official YOLOX postprocess correction: **IMPLEMENTED_UNVERIFIED live**.
- M1 practical presence: **ACCEPTED BY OWNER/OPERATOR**.
- SQLite persistence, sessions, localhost API, and local-to-Atlas snapshot mirroring: **ACCEPTED**.
- M2 milestone: **ACCEPTED; LOCAL SQLITE + ATLAS MIRROR**.

## Current qualification boundary
- M1 practical presence is accepted by owner/operator direction; detector selection is frozen at corrected YOLOX-S and no fresh detector/camera qualification is required.
- M2 durable memory is accepted with metadata-only local SQLite, Atlas snapshots, restart/session, failure-truthfulness, and localhost API behavior. Do not place the live database on the Atlas mount.
- M3 live enrollment and bounded identity qualification passed; M4 conversational grounding is now qualified within bounded API/Luna evidence.
- M4 bounded grounded conversation is implemented and qualified; M5 restrained proactivity and reactive voice are accepted; M6 final integrated stability evidence passed.

## M5 restrained proactivity — qualified
- Schema migration 4 adds metadata-only `proactive_actions` with durable source-event/candidate keys, eligibility/suppression reason, judge, citation, utterance, and delivery provenance.
- `perception/proactive.py` evaluates only `person.identified` for `primary_user` in the current occupied session. Deterministic failures make zero Luna calls; eligible candidates reserve an action before one bounded `gpt-5.6-luna` judgment.
- `tools/sentry_proactive.py` processes persisted events; `tools/sentry_m5_live.py` runs an isolated local-DB physical proof with Atlas snapshots. `SpeechDispatcher` uses local `spd-say` with cancellation.
- Example defaults: TTL 30s, one action per session, 30-minute person cooldown, two delivered actions/hour, 30-second startup suppression, low-effort judge, 20 words/160 characters.
- Automated M5 policy suite is 12/12 before the harness correction; the corrected harness adds three sequencing tests. Full Ubuntu regression is 92/92. A bounded real Luna candidate proof returned valid `silent` and persisted it. The corrected physical handoff run established a persisted empty baseline, real primary-user entry, occupied session, `person.identified`, and one eligible M5 action with a valid grounded `silent` decision.
- Corrected run: local DB `/home/sketch/.local/share/sentry/m5-qualification/handoff-20260829T215316Z.sentry.db`; Atlas snapshot `/srv/ATLAS/100_ACTIVE/Projects/SENTRY/perception-data/runtime/m5-qualification/handoff-20260829T215316Z.sentry.db`. Empty baseline completed `21:53:39.050306Z`; entry prompt `21:53:57.362266Z`; `room.became_occupied`/`presence.session_started` at `21:54:16.643081Z` (session `1`); `person.identified` at `21:54:17.711178Z` (event `1cb6e1b2-749a-4dfe-8a66-0c7bb3390ef3`, track `1`, confidence `0.6749`); action `d542857b-9bb2-4831-9ec6-85e1071594fc` was eligible, invoked one low-effort `gpt-5.6-luna` turn, and persisted `judge_silent` with valid fact citations.
- Corrected physical performance: 840 captured / 489 processed, 8.618 FPS, 102.746 ms median and 120.063 ms p95, 350 dropped frames, V4L2/MJPEG/1280x720/15 FPS, camera online, mirror status `ok`, persistence error `null`, continuous perception Luna calls `0`.
- Restart/replay dedupe against the exact isolated DB produced `duplicate`, zero additional Luna calls, one action row, and no second delivery. M5 physical handoff is qualified; M6 final integrated stability evidence passed.

## Reactive voice — accepted
- Added `perception/voice.py`, `tools/sentry_voice.py`, and `tools/sentry_kokoro_worker.py` for one explicit push-to-talk request: PipeWire microphone -> in-memory PCM -> local `openai-whisper==20250625` `tiny.en` CPU transcription -> existing `tools/sentry_ask.py` M4 grounding -> installed local Kokoro synthesis -> this host's PipeWire speaker.
- The recorder never writes audio to disk. Whisper weights are cached outside the repository under the user-local cache. No audio, embeddings, or raw frames were sent to Luna.
- The initial implementation proof used Whisper `base.en` with no live perception source, so M4 truthfully reported unavailable current state; that run is not final voice qualification. The corrected path uses Whisper `tiny.en` and local Kokoro directly, defaulting to the lower `am_michael` voice at `0.9x`. Local Kokoro playback succeeded; subsequent microphone attempts captured no intelligible requested question. The CLI now displays a temporary local Zenity window titled `SENTRY Reactive Voice` with a three-second countdown and explicit `SPEAK NOW`/`DONE` markers, plus terminal fallback markers.
- The first attempt exposed a full stdout-pipe recorder bug; concurrent draining corrected it. The failure produced zero Luna calls and no persisted audio and was not counted as voice qualification evidence.
- Focused voice tests passed 5/5; full Ubuntu regression passed 97/97 after correction. The physical spoken-request proof passed and M6 is released.

## M4 grounded conversation — qualified within bounded evidence
- `tools/sentry_grounding.py` retrieves `/health`, current room state, sessions, persons, and events from localhost, then allow-lists them into stable fact IDs with an explicit `as_of` timestamp and deterministic derived session/identity/last-empty facts.
- `tools/sentry_ask.py` performs one health-gated query and at most one OAuth `gpt-5.6-luna` turn. `tools/sentry_grounded_response.schema.json` plus local validation enforce `supported`, `partial`, or `unavailable`, non-empty citations, and rejection of unknown fact IDs.
- `tools/sentry_state_api.py` remains localhost-only and now accepts bounded history `limit` parameters. The live DB remains `/home/sketch/.local/share/sentry/sentry.db` on local ext4; no SQLite access is routed through Atlas.
- Deterministic fixtures cover empty, occupied/recognized, occupied/unknown, occupied/unresolved, degraded, offline, completed sessions, and restart-reconciled uncertainty. Full Ubuntu regression is 77/77.
- Real API/Luna proof completed 13 successful low-effort `gpt-5.6-luna` turns across six core and five adversarial concepts plus two additional current-state checks. The actual DB currently has healthy schema 3/mirror `ok` but no current room observation, sessions, or events, so answers correctly returned partial/unavailable rather than inventing state. A no-server proof invoked Luna 0 times.
- Raw frames, embeddings, biometric prototypes, and unrestricted DB rows were not sent to Luna. Continuous perception Luna calls remain 0. M4, M5, M6, and V0.2 resident runtime are qualified within their recorded boundaries.

## M2 persistence slice — accepted, local SQLite plus Atlas mirror
- `perception.presence_store.PresenceStore` is the metadata-only SQLite store. It applies schema migration 3, records current room state, emits state-derived room/session events, records lifecycle/restart provenance, and closes open sessions on observed or restart-reconciled `occupied->empty`.
- `perception/storage_mirror.py` guards the active DB to a local filesystem, creates SQLite Online Backup snapshots, validates them, publishes complete snapshots atomically to Atlas, and preserves/quarantines local files during restore.
- `tools/sentry_state_api.py` provides localhost-only `/health`, `/v1/rooms/office/state`, `/v1/rooms/office/sessions`, and `/v1/events` reads from the local live DB. The example active DB is `~/.local/share/sentry/sentry.db`; Atlas snapshots are ignored under `perception-data/runtime/backups/`.
- M2 qualification is now testing the resolved topology: `/srv/ATLAS` remains `fuse.sshfs`, but SQLite never opens the Atlas copy as its live database.
- Raw frames, embeddings, and continuous Codex/Luna calls remain outside this slice.

## M3 identity slice — qualified within bounded evidence, local-only biometric profile
- `perception/identity.py` loads exact OpenCV Zoo YuNet/SFace models, verifies SHA-256, performs face quality gating, unique face-to-existing-track association, SFace cosine matching, and three-observation temporal confirmation.
- `tools/sentry_enroll_identity.py` deliberately captures 16 accepted samples by default, discards frames and individual embeddings after in-memory feature extraction, and stores only a normalized prototype through `PresenceStore`. `tools/sentry_identity_admin.py delete` explicitly removes the active profile.
- SQLite schema version 3 adds `persons`, `identity_profiles`, and metadata-only current people. Prototypes are local DB data included only in validated Atlas snapshots; they are not exposed by API/events/logs and are not committed.
- `/v1/persons` returns enrolled metadata only. Current room state may expose track identity annotations, never embeddings. Identity errors do not alter room state.
- Exact model provenance and checksums are documented in `docs/M3_IDENTITY.md`; model artifacts are ignored under canonical `perception-data/models/opencv-zoo/`.
- Enrollment accepted 16 samples for `primary_user` / `Sketch`; two attempts were rejected because no face was detected. Held-out genuine scoring produced 425 quality-qualified opportunities; the consenting non-primary segment produced 210. Threshold `0.55` yielded 377/425 (`88.71%`) genuine acceptance, 0/210 negative accepts, and 100% measured accepted-ID precision.
- Corrected live primary verification processed 495/495 frames at 8.246 FPS, recognized within 2.773 seconds, and used one stable track. Live non-primary verification processed 498/498 frames at 8.291 FPS with zero primary-user assignments. Identity loss remained unresolved and did not affect room state.
- Local DB reopen and Atlas restore preserved the profile, threshold, model provenance, and one-person/one-profile invariant. Simultaneous two-person association was not run because both people were not available together; this is a residual limitation. M3 is **QUALIFIED WITH BOUNDED EVIDENCE**.

## Platform migration status
- Ubuntu 24.04.4 LTS / Linux 7.0.0-30-generic / x86_64 is now authoritative for future V0.1 work. The canonical project remains `/srv/ATLAS/100_ACTIVE/Projects/SENTRY` on the Atlas share; the Ubuntu desktop currently reaches that exact checkout through its authenticated user SFTP mount.
- Windows DirectShow, PnP, numeric-index, and Windows runtime results remain historical evidence. The unfinished Windows Stage B entry run is `INVALID/UNRESOLVED` for acceptance because operator visibility after the marker was not confirmed before migration.
- The exact NexiGo N60 V4L2 device is `/dev/v4l/by-id/usb-webcamvendor_NexiGo_N60_FHD_Webcam_Jan_29_2024-10:32:28-N60-video-index0`; the device ACL permits the SENTRY user. Measured target mode is MJPEG 1280x720 at 15 FPS.
- The pinned Linux environment is Python 3.12.3, `opencv-python-headless==4.12.0.88`, `openvino==2026.3.1`, `psutil==7.0.0`, with OpenVINO devices `CPU`, `GPU.0`, and `GPU.1`. CPU remains the active inference device.
- 0202 FP32 XML/BIN checksums remain `fc218405...72a6a` and `e807fab...ab578`; model load/compile and zero-array output contract pass on Ubuntu. Full Linux tests pass 26/26.
- Linux V4L2 camera/inference smoke passed: 666 captured / 665 processed, 14.760 processed FPS, 16.189 ms median and 17.912 ms p95, 0 dropped frames. A separate 20-second sample measured 13.426 processed FPS, 15.758 ms median, 17.169 ms p95, mean process CPU 92.52%, peak 106.00%, and 0 dropped frames. Smoke telemetry is not occupancy ground truth.
- The bounded OAuth bridge passed a synthetic `person.entered` proof on Linux using `gpt-5.6-luna` at low effort; perception makes zero Codex/Luna calls. PipeWire/PulseAudio and NexiGo microphone/output inventory completed; voice implementation remains out of scope.
- No raw frames were persisted. Runtime/model evidence remains under ignored canonical `perception-data/` paths. RT-DETR and 0202 artifacts remain historical/ignored; YOLOX-S is the frozen practical V0.1 backend by Architect direction.
- The asymmetric-evidence diagnostic path exposes positive 0202 candidates from the same single inference, but production semantics remain unchanged at entry/hold threshold `0.40` because calibration found no qualifying lower support threshold.
- Official YOLOX-S integration is the frozen practical V0.1 backend by owner/operator direction: upstream tag `0.3.0` commit `419778480ab6ec0590e5d3831b3afb3b46ab2aa3`, official model-zoo checkpoint `0.1.1rc0/yolox_s.pth`, official ONNX-to-OpenVINO conversion, 640x640 input, 8400x85 output, COCO person filtering, upstream letterbox/grid decode, and NMS `0.45`. Local model artifacts remain ignored. Historical live edge cases remain an operational risk; no further detector qualification is authorized.
- Ubuntu platform migration commit `e9977aa` (`chore: rebaseline SENTRY on Ubuntu`) is pushed to `origin/main`; the canonical checkout is clean after the push.
- M2 local-SQLite/Atlas-mirror implementation and qualification evidence are pushed as `8c1684014ed91d7317f2f0de060757f7d5e20262` (`feat: qualify local SQLite Atlas mirror persistence`). Full regression was 54/54 in the pinned Ubuntu environment, including concurrent localhost reads during local writes; M2 is accepted.

## Latest YOLOX-S qualification result (historical evidence)
- Metadata-only labeled calibration used the existing YOLOX-S candidate records and selected `0.50` as the highest tested state-qualified threshold. Empty-state simulation qualified at `0.50`; the one-person simulation reached `99.0585%` authoritative occupied correctness with approximately `1.124s` simulated entry latency and no false-empty transition.
- Fresh final Stage A was operator-confirmed empty from `2026-08-28T17:29:00.375268Z` through `2026-08-28T17:30:08.775216Z`. It recorded 566 observations, 565 online usable observations, 53/565 threshold-qualified positive observations (`9.38%`), maximum two simultaneous detections, and authoritative state `occupied` for 186/565 observations (`32.92%`) in a sustained `19.272s` false-occupancy interval. Positive confidences reached `0.824309` (55 threshold-qualified candidates including duplicate boxes).
- Stage A therefore stopped at the prior strict false-human-evidence boundary. Stages B-D, low-light, camera recovery, and soak were not run under that directive. The historical result was `YOLOX-S OFFICE EVIDENCE INSUFFICIENT`; the Architect has since accepted practical camera/human detection and authorized progression.

## YOLOX postprocessing root-cause investigation (historical)
- Official YOLOX 0.3.0 semantics select the winning class across all class probabilities using `objectness × top_class_probability`, then apply class-agnostic NMS; person is accepted only when the final winning class is COCO person (`0`). The prior SENTRY decoder instead evaluated `objectness × person_probability` before NMS, which is a confirmed divergence.
- A deterministic overlapping-box case demonstrated the consequence: the legacy path would retain a person-scored box at `0.72`, while the official winner was non-person at `0.9405` and suppressed it. SENTRY now follows the official winning-class/NMS order and exposes metadata-only parity rows for diagnostics.
- The identical-tensor synthetic OpenVINO check passed: raw shape `[1,8400,85]`, corrected SENTRY final-person count matched the reference count (`0 == 0`). The full automated suite remains `37/37` after the correction.
- A live parity probe could not open the stable NexiGo device because `/dev/video0` was held by unrelated `anima` process PID `219972`. No process was terminated and no live parity claim was made. This historical qualification loop is closed by Architect decision; no further detector-specific Stage A-D run is required before M2.

## Current verified state
- The Architect rejected RT-DETR for V0.1 after confirmed-empty false-human evidence and sub-floor throughput, then authorized this final reuse test of the already-investigated 0202 signal through the room-state layer. RT-DETR-specific working-tree code was removed from active production source after complete diff preservation.
- The restored 0202 implementation and fresh asymmetric calibration remain historical negative evidence; no qualifying support operating band was found. The current active backend is the Architect-approved YOLOX-S integration described above.
- The temporal state layer is implemented behind structured observations. It maintains only `empty`, `occupied`, `degraded`, and `offline`; it uses timestamp-based entry confirmation of 1.0 seconds, a 1.0-second entry evidence-gap tolerance, and a 15.0-second absence grace period. Duplicate detections are binary human evidence and do not count occupants.
- Structured observations include room state, state transitions, strong/support detector evidence, maximum candidate confidence, and metadata-only luminance/contrast measurements. The M2 slice now adds metadata-only persistence, sessions, derived events, and a localhost read API; no image enhancement, identity, or proactive behavior was added.
- State-machine deterministic tests and the restored 0202 perception suite pass 24/24 using the repository `.venv`. The 0202 FP32 XML/BIN remain ignored and match the recorded Open Model Zoo SHA-384 checksums.
- Pre-live scope review passed: no detector/model/runtime/tracker changes, no raw frames persisted, and no Codex/Luna perception calls. The asymmetric calibration now provides fresh operator-labeled raw-candidate evidence for the current directive.
- Canonical path `\\atlas\\ATLAS\\100_ACTIVE\\Projects\\SENTRY` contains a valid Git checkout restored from GitHub after the damaged path was absent on repeated inventory reads.
- The last committed `main` and `origin/main` state was `52c2095` before this authorized transition; the YOLOX-S implementation, calibration tooling, and evidence are being committed together with the M2 persistence slice so GitHub reflects the accepted direction.
- `git fsck --full` passed with exit code 0 and no reported errors.
- Authority kernel, reusable skills, perception source, configuration, requirements, documentation, and tests are present.
- Existing and decoder-focused automated tests pass 15/15.
- No surviving SENTRY files or directories were present before restoration; no unique uncommitted SENTRY material was found or discarded, and no quarantine was required.
- The parent Atlas project share was reachable and stable across repeated reads. Neighboring visible project directories were not treated as comparable Git checkout evidence.
- Practical M1 is accepted by owner/operator direction. Individual tracking quality, low-light boundaries, and controlled camera recovery remain downstream operational risks; they do not block current M2 work.
- Human-visible Windows Camera preview confirmed one real seated person in the office scene. A 30-second live run produced person records in 238/271 observations (87.8%), but up to 3 simultaneous tracks and IDs 1–14 in a one-person scene. A 90-second run produced up to 6 tracks and 29 unique IDs, materially failing stable office-presence behavior.
- A synchronized occlusion attempt produced one track with two detector-visible observations followed by bounded predicted misses through miss count 12, but the physical timing/box correspondence was not sufficient to accept controlled dropout continuity.
- The existing service remained online during a 90-second run. An authorized PnP disable attempt returned `Generic failure`, and a restart attempt returned `Access is denied`; controlled offline/reopen recovery was not executed.
- M0, the Ubuntu platform foundation, practical M1 presence, M2 durable memory, and bounded M3 primary-user identity are accepted. M2 uses local SQLite with Atlas snapshot mirroring. M4 conversational grounding, proactive behavior, and embodiment remain ahead.
- Architect-authorized FP32 `person-detection-0202` XML/BIN artifacts were downloaded under ignored canonical `perception-data/models/person-detection-0202/FP32/`; both match the Open Model Zoo manifest SHA-384 checksums.
- The pinned generic `opencv-python-headless==4.12.0.88` failed both `cv2.dnn.readNet` and `cv2.dnn.readNetFromModelOptimizer` with `Backend (plugin) is not available: 'openvino'`. The detector experiment was reverted; no alternate runtime was introduced.
- Architect has now authorized exactly one additional runtime. Isolated `.venv` installation passed with `openvino==2026.3.1`, `opencv-python-headless==4.12.0.88`, `psutil==7.0.0`, and transitive `numpy==2.2.6` / `openvino-telemetry==2025.2.0`.
- Host verification: Windows 11 x64, AMD Ryzen 7 5800XT, Python 3.12.10, OpenVINO devices `CPU`, `GPU.0`, and `GPU.1`.
- OpenVINO loaded and compiled the checksummed FP32 model on CPU; bounded zero-array inference returned `(1, 1, 200, 7)`.
- The production detector now uses OpenVINO behind the existing detector contract, with model paths configurable and explicit load/decode failures. The IoU tracker remains unchanged. The 0303 decoder now follows the official class-agnostic path: positive box confidence, explicit `[1/1280, 1/720]` reconstruction, clipping, and local class-agnostic NMS at `0.6`; the companion labels tensor is diagnostic only.
- Confirmed-empty Stage A run: 205 processed online observations over approximately 20.6 seconds, all zero-person, with no false-person detections; 8.095 processed FPS and 0 dropped frames.
- Confirmed-one-person Stage B run: the operator confirmed one person remained continuously visible. The service processed 827 online observations over approximately 83.9 seconds at 9.154 FPS, with 480 zero-detection observations, 318 exactly-one observations, 29 multi-detection observations, and a maximum of 2 simultaneous detections. The unchanged tracker produced 19 unique track IDs, first ID 1, final visible ID 19, 32 visible-ID-set changes, and up to 3 active tracker records. This fails the required one-person quality target.
- Stage C synchronized dropout and Stage E ten-minute soak were not run because the confirmed detector-quality failure reached the directive stop boundary. Multi-person live evidence remains blocked because no second person was available. Camera failure/recovery remains a separate unrun M1 gate.
- Calibration diagnostic capability was added without changing the model, OpenVINO runtime/device, preprocessing, camera path, frame buffer, tracker, or production threshold. It records only raw candidate timestamps, frame sequences, confidences, boxes, and inference timing; raw candidates are never sent to the production tracker.
- Calibration Stage A operator-confirmed empty segment: runner marker `CONFIRMED_EMPTY` at `2026-08-26T16:18:50.151051+00:00`; 303 online observations over 30.639 seconds. At threshold 0.20, false-positive observations were 2/303 (0.660%), maximum 1, with a 0.111-second longest run. Raw confidence percentiles were p50 0.031729, p75 0.040432, p90 0.070170, p95 0.107720, max 0.233231.
- Calibration Stage B operator-confirmed continuous one-person segment: runner marker `CONFIRMED_ONE_PERSON` at `2026-08-26T16:21:28.148642+00:00`, runner end at `2026-08-26T16:22:33.820060+00:00`, and operator confirmation `CONFIRMED_ONE_PERSON — END — CONTINUOUS`; 599 online observations over 60.559 seconds. At threshold 0.40, any detection was 579/599 (96.661%), but 64/599 observations had duplicate/multi-box detections (10.684%) and the longest duplicate run was 0.911 seconds. At 0.45, duplicates fell to 2/599 (0.334%) but recall fell to 534/599 (89.149%). Raw confidence percentiles were p50 0.058726, p75 0.112728, p90 0.323212, p95 0.489522, max 0.943762.
- No tested threshold from 0.10 through 0.50 met both empty false-positive rate <=1% and one-person >=95% recall with rare duplicates. The calibration result is `DETECTOR CALIBRATION FAILED — REPLAN MODEL`.
- Best-candidate bounding-box sanity was not accepted because the installed headless OpenCV build cannot provide `cv2.imshow`; no visual overlay or frame was persisted. This limitation does not weaken the decisive count-based calibration failure.
- Architect authorized the bounded `person-detection-0303` replan. Official FP32 XML/BIN downloads match the manifest sizes and SHA-384 checksums, and the OpenVINO model loads with static input `[1,3,720,1280]` and runtime outputs `boxes (N,5)` plus `labels (N,)`.
- 0303 pre-live CPU performance check: native 1280x720 DirectShow camera, 107 captured / 105 processed, 6.852 processed FPS, 79.056 ms median and 114.636 ms p95 processing latency, 1 dropped frame, online throughout, zero Codex/Luna calls.
- Raw 0303 investigation: operator-confirmed one-person marker at `2026-08-26T19:42:57.764666+00:00`; 149 online observations over approximately 20.3 seconds. Raw output contained 1,474 positive-confidence rows, 339 rows at or above `0.10`, maximum confidence `0.458353`, and all companion labels were `0`; the pre-correction SENTRY decoder emitted zero candidates in all observations. **DECODER BUG CONFIRMED**.
- Corrected 0303 Stage A: runner marker `CONFIRMED_EMPTY` at `2026-08-26T20:07:48.797739+00:00`; 181 online observations over 29.969 seconds. At threshold `0.45`, false positives were `0/181`; at `0.40`, false positives were `4/181` (2.21%); lower thresholds produced sustained duplicate false detections.
- Corrected 0303 Stage B: runner marker `CONFIRMED_ONE_PERSON` at `2026-08-26T20:23:10.311140+00:00`; 556 online observations over 56.863 seconds with one person continuously visible. At threshold `0.45`, recall was `134/556` (24.10%); at `0.40`, recall was `270/556` (48.56%) while the matched empty false-positive rate was 2.21%; no tested threshold met both gates. **DECODER BUG CONFIRMED — 0303 STILL FAILS QUALITY**.
- Corrected-decoder short performance: 101 captured / 95 processed, 6.173 processed FPS, 87.893 ms median and 132.416 ms p95 processing latency, 5 dropped frames, CPU path, RSS 162.6 MB to 268.4 MB, zero Codex/Luna calls. No ten-minute soak was reached because detector quality failed.
- Tracker qualification, synchronized dropout, ten-minute soak, and live two-person behavior were not run because corrected detector quality failed. Camera recovery remains a separate M1 gate. No tracker, runtime, device, precision, camera, or production threshold change was made.

## Current hypotheses / unknowns
- The original SENTRY disappearance is consistent with a transient Atlas share/filesystem visibility or consistency failure, but deletion versus transient visibility cannot be proven from the surviving evidence.
- The restored checkout is trustworthy for continued project work; the earlier camera result remains preserved in Notion and prior append-only evidence.

## Current blockers
- Stage A of `SENTRY-CONVERGENCE-RTDETR-PRESENCE-STATE-001` failed decisively: during the fresh operator-confirmed-empty run, the RT-DETR path produced 8 positive candidate observations and the authoritative state transitioned `empty->occupied` for approximately 15.8 seconds. Stop at the false-human-evidence boundary; do not request Stage B-D markers or commit RT-DETR as accepted production capability.
- Fresh Ubuntu room-state qualification has Stage A passed and Stage B stopped after the one authorized retry. The retry produced brief evidence and an occupied transition, then falsely returned to `empty` while the operator remained in frame; classify as `STATE FAILURE — UBUNTU OCCUPIED EVIDENCE INSUFFICIENT`, not an operator-protocol failure. Do not reuse earlier detector-specific markers or per-frame calibration results as this directive's state evidence.
- Low-light health thresholds are unresolved until labeled dim/insufficient-light evidence is collected; the implementation supports explicit degraded quality but does not invent a luminance cutoff.
- Historical M1 strict live-qualification evidence remains incomplete, but practical M1 is accepted by owner/operator direction and no further detector qualification is required.
- Historical detector and tracker-quality limitations remain known operational risks; detector selection is frozen on corrected YOLOX-S for V0.1.
- Controlled camera failure/recovery remains a downstream operational risk and is outside this M2 directive.
- The original Atlas incident has no proven low-level root cause; no broad storage repair or migration was attempted.
- RT-DETR remains rejected for this host. The prior 0202 per-frame and Ubuntu occupied-state failures are preserved as historical evidence; the authorized asymmetric reuse test also found no qualifying support threshold. No detector work is authorized in this M2 directive.
- Fresh asymmetric calibration stopped after Phase 2: confirmed-empty raw candidates were low-confidence, while the continuously confirmed one-person segment had only 63/1791 observations at or above the fixed `0.40` entry threshold. No support threshold from `0.10` through `0.40` achieved simulated occupied correctness of `>=95%` with a valid bounded exit.

## Latest recorded evidence
- `OUTCOME-SENTRY-CONVERGENCE-RTDETR-PRESENCE-STATE-001-STAGE-A`: retained as negative evidence; RT-DETR produced false occupied state and missed the FPS floor.
- `OUTCOME-SENTRY-CONVERGENCE-0202-PRESENCE-STATE-001-PRE-LIVE`: restored historical 0202 detector, retained generic state/luminance work, 24/24 tests passed, checksums passed, and short performance gate passed at 5.962 FPS. Awaiting fresh Stage A.
- `OUTCOME-SENTRY-CONVERGENCE-0202-PRESENCE-STATE-001-STAGE-A`: fresh confirmed-empty run passed with 230/230 usable online observations authoritative `empty`, zero detector positives, zero false occupancy, and no persistent phantom evidence. Awaiting fresh Stage B entry marker.
- `OUTCOME-SENTRY-REPO-RECOVERY-001`: fresh clone at `73b43f3`, `git fsck` passed, Authority/source checks passed, automated tests 5/5 passed, canonical reread stable, and local/remote `main` matched.
- `OUTCOME-SENTRY-M1-LIVE-QUALIFICATION-001`: human-visible single-person scene observed; detector/tracker produced severe track churn and false-positive indicators; performance remained above target; controlled camera recovery was blocked by device-operation access failure.
- `OUTCOME-SENTRY-M1-DETECTOR-REPLAN-001`: official model/license/checksum evidence passed, but generic OpenCV DNN IR loading failed; no production detector change was retained and live Stage A/B/C did not run.
- `OUTCOME-SENTRY-M1-DETECTOR-RUNTIME-001`: OpenVINO implementation target-tested; subsequent confirmed live quality evidence failed the one-person gate.
- `OUTCOME-SENTRY-M1-OPENVINO-LIVE-001`: confirmed-empty baseline passed, confirmed-one-person detector/tracker quality failed decisively, and later stages stopped at the authorized quality boundary.
- `OUTCOME-SENTRY-M1-DETECTOR-CALIBRATION-001`: raw-confidence sweep across operator-confirmed empty and continuous-one-person segments found no acceptable operating threshold; model replan is required.
- `OUTCOME-SENTRY-M1-DETECTOR-0303-001`: official 0303 artifacts/runtime/output semantics passed, short CPU performance stayed above 5 FPS, confirmed-empty passed, but confirmed-one-person produced zero candidates across 0.10-0.90; detector quality failed before tracker qualification.
- `OUTCOME-SENTRY-M1-0303-DECODER-RECONCILE-001`: raw output proved the prior zero-candidate result was caused by the label gate; reference-semantics correction passed 15/15 tests, but corrected live calibration still failed all quality operating points.
- `OUTCOME-SENTRY-M0-CODEX-FEASIBILITY-001` and `OUTCOME-SENTRY-M0-CODEX-CONTEXT-OPT-001`: accepted M0 Luna boundary and runtime isolation evidence remain historical and unchanged.

## Current risks
- Treating the recovered checkout or camera path as proof of M1 acceptance would overstate the evidence.
- The Atlas share incident may recur; preserve append-only state and recheck canonical path stability after future writes.
- HOG/tracker telemetry must not be promoted to person-quality acceptance when one known person produces multiple simultaneous tracks and high ID churn.

## Next Architect decision point
The asymmetric-evidence calibration found no qualifying operating band. Architect decision is required before any Phase 3 production change or further live marker; do not increase the 15-second grace, change the tracker, model-shop, or begin M2.

This file is a mutable snapshot. Do not use it to erase historical outcomes or decisions.

## Superseding current snapshot — V0.3 Vosk wake integration, unqualified

- Date: 2026-08-31
- Active directive: `SENTRY-V0.3-VOSK-WAKE-INTEGRATION-001`.
- Status: **IMPLEMENTED_UNVERIFIED / RETURN TO ARCHITECT**. The dirty V0.3 listener now constructs local Vosk `0.3.45` with official `vosk-model-small-en-us-0.15`, grammar `["sentry", "[unk]"]`, and final-result-only wake handling. Vosk is the only live wake authority; Whisper is downstream command STT only.
- Positive evidence: the live office microphone woke four times on the configured single token `Sentry`; the visual state indicator showed `LISTENING` and the explicit `ARMED` follow-up prompt; Vosk wake-to-dispatch latency samples were 1.676 s, 1.696 s, 1.737 s, and 1.734 s. A bare recovered wake-token defect was fixed so it now arms instead of sending `Sentry` as a question. Focused Vosk/voice tests pass **16/16**.
- Blocking evidence: three ordinary deterministic command attempts (reminder query and two supported preference queries) were dispatched but did not reach their intended deterministic route; responses fell through to unrelated bounded M4/unsupported-memory behavior. No raw audio or transcript was retained, so the exact Whisper substitutions are intentionally unknown. This is a command-STT reliability failure, not a Vosk wake-decision failure.
- Boundary: the directive forbids replacing the existing Whisper `tiny.en` command STT or changing broader conversation semantics. Do not claim V0.3 qualification, commit, or push. Preserve the dirty implementation for Architect review. The local production configuration remains `always_on_enabled=false`; Vosk model remains local and ignored; all SENTRY services, listener, `pw-record`, and visual indicator are inactive.
