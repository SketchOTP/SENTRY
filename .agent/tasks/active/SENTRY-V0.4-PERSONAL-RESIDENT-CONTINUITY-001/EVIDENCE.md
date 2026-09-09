# Evidence

## Linux-PC ANIMA household event consumer — 2026-09-07

The owner-authorized resident event path is enabled in the private Linux-PC
configuration for the commissioned ANIMA `Home` household. `sentry-voice.service`
was restarted after the listener/diagnostics correction and returned to
`LISTENING` with `wake_enabled=true` and `vad_healthy=true`. The event consumer
polls only the bounded fresh autonomous queue through the ANIMA client; its
verification window observed `EMPTY`, meaning no eligible fresh event was
available at that time. This is a live readiness observation, not physical
SenseGuard event-to-TTS evidence.

The voice onboarding prompt is explicitly voice-only and preserves the existing
typed Core workflow: bounded ZHA pairing, spoken operator instruction, spoken
follow-up, discovery refresh, semantic inspection, room commissioning, and
typed alert-policy creation. The listener diagnostics now expose only bounded
metadata for event result and delivery status, including recorded response and
TTS delivery outcomes; response text is not persisted.

Focused SENTRY validation after this correction: 135 unittest cases passed
across always-on voice, resident ANIMA events, bridge, and Codex agent prompt
coverage. No commit or hosted CI is claimed for this local dirty-tree change.

## Phase 0 — 2026-09-03

- Repository root: `/srv/ATLAS/100_ACTIVE/Projects/SENTRY`
- Applicable instructions: root `AGENTS.md` and Authority skill.
- Starting `HEAD == origin/main`:
  `970d1cf5f4df749d5d0844a19d5d392012ced910`
- Accepted GitHub Actions run `33700343412`: `success` on the starting SHA.
- Dirty-tree inventory matched the Architect handoff exactly: 21 modified tracked
  files and 8 intended untracked source files; `git diff --check` passed.
- Classification: identity/speaker context, enrollment/native UI, turn-taking and
  tests, plus previously preserved Fahrenheit and exact artifact-context fixes.
  No unrelated work found.
- Recovery snapshot:
  `/home/sketch/.local/state/sentry/recovery/v0.4-personal-continuity-ZaDoFI`
  with mode-0600 tracked patch and untracked-source archive under a mode-0700
  directory. It excludes audio, images, biometrics, transcripts, credentials,
  private config, databases, and coordinates.
- Snapshot SHA-256:
  - tracked patch: `df27d8aa114d875d36fcf98d437c6b9827f80e5a4138586e491c68e68522564f`
  - untracked source: `fb950d70ea87e2d45fd04a9ac53fb44516c3a59d74caf7920af5b2a6862a27ee`
- Feature branch created with dirty tree intact:
  `feature/v0.4-personal-continuity`.
- Retrieval confidence: `ADEQUATE`.

## Checkpoint A native interface — 2026-09-03

- Consolidated the former voice-status and identity-enrollment surfaces into one
  native GTK application launched by canonical `sentry-ui.service`; legacy UI
  units and desktop launcher are deliberately migrated away.
- Main canvas now contains only one centered orb and one runtime status label.
  An inward-pointing chevron opens a full-height settings drawer over the main
  canvas without moving the orb or resizing the native window; the reversed
  chevron collapses it. Enrolled people, bounded recognition testing, and full
  add/update enrollment controls remain inside that in-window drawer.
- Added a centralized `OrbStateController` with explicit standby, wake,
  listening, processing, speaking, follow-up-listening, and offline semantics.
  Glass shell, internal energy, and external field render independently while
  preserving one continuously morphed object.
- Microphone PCM and actual Kokoro playback PCM publish separate bounded
  amplitude metadata. Semantic state selects the animation system; amplitude
  only modulates its intensity. No transcript or audio content is persisted.
- Wake acknowledgement uses one cached local bubble-pop plus structural
  contraction/rebound and an outward ignition ring. The resident listener is
  the only audio owner; the UI cannot add a second delayed chime. The interim
  `audio-volume-change.oga` cue was rejected as dunk-like and the accepted
  source was restored to freedesktop `message.oga`. Follow-up listening does
  not replay that transition.
- Reduced-motion mode preserves structural state differences with lower motion
  amplitude. The reference-driven production renderer now uses a GPU fragment
  shader at a 60 FPS target with 36-sample ray-marched internal volumes,
  refractive studio-light response, volumetric absorption, filmic tone mapping,
  an anti-aliased deforming silhouette, organic state-specific energy fields,
  and restrained external pressure effects. Literal processing loops, speaking
  spokes, loading-wheel geometry, and stacked waveform lines were removed.
- Listening was subsequently isolated at a fixed high microphone level and
  refined into one translucent, depth-folded cyan/violet energy membrane. Mic
  amplitude now drives the membrane's flow and brilliance while glass-shell
  deformation is deliberately constrained to subtle fine surface motion, so
  the silhouette remains spherical instead of becoming a rounded square.
  Operator review then found the membrane motion too fast; autonomous travel,
  folding, and shell drift were reduced substantially while instantaneous
  amplitude-driven height and brightness response were preserved.
- Speaking was isolated and corrected after operator captures showed a pulsing
  octagonal shell and overexposed central burst. The speaking shell is now
  hard-locked to a constant spherical scale in both controller and shader;
  concentric burst geometry was removed, and TTS amplitude modulates only a
  compact turbulent plasma knot, irregular corona, interwoven internal energy
  filaments, and a fixed-radius outer aura. The internal field retains a bright
  center without expanding or deforming the glass shell. A subsequent live
  comparison found too much visually dormant interior around that nucleus, so
  three slow curved plasma currents and a softly breathing vocal aurora now
  circulate through the middle volume; they brighten outward from actual TTS
  amplitude while remaining detached from shell geometry. Operator approval of
  the resulting contained-lifeforce direction led to one further material
  refinement: a translucent domain-warped spirit-vapor layer now drifts and
  folds independently around the core, remains denser near the central energy,
  and dissipates before the glass boundary.
- The spirit vapor was then made a single persistent material across the full
  interaction lifecycle. Standby retains its existing glass, ribbon, breathing,
  and floating animation while adding visibly free-roaming violet/cyan vapor.
  Wake contracts that same field toward the center and seeds the listening
  membrane; the following 0.82-second eased material morph visibly gathers the
  loose vapor into the established listening waveform. Processing and speaking
  reuse the same base flow coordinates rather than introducing unrelated fog.
- Every active state now inherits Standby's slow vertical float and a shared
  low-amplitude material/light breath. Non-speaking active shells receive only
  a very small geometric breath; Speaking retains its explicitly fixed glass
  radius while its internal vapor and halo breathe instead.
- Listening/follow-up → Processing and Processing → Speaking now use deliberate
  1.55-second material reformations. Full-video review rejected the prior
  advected-particle design: its thresholded 3D grain and 32-by-32 screen-space
  mote grid remained visibly square, quantized, and effect-like in motion even
  after the individual dots were reduced. Both particle paths were removed.
  The final candidate uses one continuous domain-warped volumetric field with no
  particle cells, sprite pass, midpoint takeover, or hard material branch. The
  source structure progressively releases density into broad slow-moving vapor;
  source, mist, and target coexist throughout the morph; and the destination
  density field increasingly attracts the same vapor into the processing helix
  or speaking plasma core. A replacement 930-frame, 60 FPS, 15.5-second GPU
  lifecycle capture plus 10 FPS detailed transition sheets showed uninterrupted
  wave-to-mist-to-helix and helix-to-mist-to-core motion without square breakup,
  a filled-orb flash, or a midpoint cut.
- Normal state changes now use eased 0.62–1.55 second visual morphs while wake
  acknowledgement remains deliberately sharp at 0.18 seconds. The renderer
  carries the previous state's independently sourced audio energy through the
  crossfade and interpolates internal volume, halo width/strength, and speaking
  aura instead of switching those layers abruptly.
- Ubuntu native renderer dependency `python3-opengl` was installed alongside
  GTK 4 and is documented. NVIDIA/X11 required `GSK_RENDERER=gl` plus
  `GDK_DEBUG=gl-prefer-gl:gl-glx`; these service-local settings corrected GTK's
  `Unable to read GL content` / context-creation failure and survive restart.
- Added a native Voice card to the existing in-window settings drawer. Its
  catalog contains 28 validated Kokoro English profiles spanning British and
  American accents and male and female voices. The operator can preview a
  selection without changing runtime state, choose a bounded 0.75x-1.30x
  speech speed, and explicitly save and apply it. Persistence atomically edits
  only the two canonical voice fields, restores config mode 0600, fsyncs the
  replacement, and reloads the resident listener only when it was active.
  Alarms and proactive delivery already consume those same fields. Local
  synthesis checks passed for British-male `bm_george` at 0.75x and
  American-female `af_bella` at 1.30x without writing audio artifacts.
- The first live Save and apply appeared to crash because the canonical UI unit
  still declared `PartOf=sentry-voice.service`; reloading voice therefore
  stopped and recreated the native window. Journal timestamps and PID changes
  established that lifecycle coupling as the exact cause. The UI no longer
  participates in the voice service's stop/restart lifecycle. Voice still
  `Wants=sentry-ui.service` at startup, but preference reloads now preserve the
  UI process, window ID, drawer, and operator interaction state.
- Runtime tracing found that wake audio was downstream of two avoidable
  boundaries: the voice process first performed session/identity and
  diagnostics work, then the native UI discovered `last_wake_at` on its 40 ms
  status poll and cold-launched `canberra-gtk-play`. The cue is now predecoded
  once into the local PipeWire Pulse-compatible sample cache during listener
  startup and requested directly as the first accepted-Vosk-wake side effect.
  The UI remains responsible only for visual wake acknowledgement, eliminating
  duplicate or late audio. The installed listener reached `LISTENING` with
  cached sample `sentry-wake-2221600`; the UI PID remained `2211873` through
  listener restart. Automated ordering/one-shot/cache lifecycle coverage and
  the affected UI/voice/service suites pass 88/88. Perceptual wake alignment is
  still operator-observed evidence and has not been claimed from automation.
- Added a persistent Sleep switch at the top of the settings drawer. Its default
  is off. Enabling it writes `voice.sleep_enabled=true` through the same atomic,
  fsynced mode-0600 config boundary and stops `sentry-voice.service`; disabling
  it writes `false` and starts the listener. The listener independently checks
  the setting before loading Vosk, Silero, Whisper, the microphone stream, the
  wake cue, or identity inspection. Direct loop tests prove Sleep opens no
  stream, accepts no wake, requests no cue, invokes no Whisper/Codex, and
  publishes `SLEEPING` with `wake_enabled=false`.
- Production restart proof persisted Sleep on, attempted a normal service
  start, and observed `sentry-voice.service=inactive`, status `SLEEPING`, and no
  listener or `pw-record` process. Persisting Sleep off restarted the same unit
  and restored `LISTENING`. The production config remained mode 0600 and the
  final setting is `sleep_enabled=false`.
- Exact affected UI/voice/identity/service suites: `109/109` passed before the
  GPU refinement; the latest post-material UI/service/voice sanity set passed
  `31/31`; the latest Sleep/wake/voice/UI/service set passes `93/93`. Python
  compilation and `git diff --check` passed. Window-specific
  captures verified the live GL orb, the in-window settings overlay, unchanged
  `1120x760` geometry, and clean collapse after an installed-service restart.
- A recognized wake identity now survives listener/settings restarts and Codex
  thread rotation for the remainder of its absolute 7200-second observation
  TTL. Production stores only recognized metadata in the mode-0600 runtime file
  `$XDG_RUNTIME_DIR/sentry/speaker-context.json`; it stores no image, biometric
  feature, transcript, or audio and does not survive logout/reboot. Expiry and
  profile-catalog changes invalidate the cache. Negative/unresolved checks are
  not cached and continue to trigger a new bounded camera check on the next
  explicit wake. Exact focused voice/identity/UI/service suites pass `110/110`.
- The operator then disabled Sleep and reported that the UI still said
  `Sleeping`. Runtime evidence showed the setting had correctly persisted
  false and the service had started, but the stale sleeping status survived
  for the approximately 20-second voice-model initialization. The launcher now
  publishes `STARTING` before that work, while the UI latches `Waking SENTRY…`
  until a coherent ready record arrives. Installed-runtime restart evidence was
  `DISABLED → STARTING → LISTENING`; the first state was the prior process's
  shutdown record, and the explicit starting state covered model load. Both UI
  and voice are now active with Sleep false and wake enabled. Exact focused
  validation passes `111/111`; compilation and `git diff --check` pass.
- The native application launcher now owns one idempotent configured-runtime
  entry path. The installer places the application-menu entry and a mode-0755,
  GNOME-trusted `SENTRY.desktop` shortcut in the operator's XDG desktop
  directory. Clicking it starts only configured resident support/timer/UI/
  voice/perception/proactivity units, then activates the existing
  `local.sentry.Control` GTK instance. Explicit Sleep and opt-in continuous
  services remain authoritative. Installed proof retained the existing PID on
  one click and relaunched a deliberately stopped UI as one systemd-owned GTK
  process on another; current Sleep-on voice state remained inactive. Exact
  focused validation now passes `116/116`; desktop-entry validation, affected
  compilation, and `git diff --check` pass.
- The launcher now has an original SENTRY-specific 512x512 RGBA application
  icon rather than the generic microphone symbol. The transparent asset uses
  the same dark glass shell and contained cyan/violet spirit-vapor identity as
  the native orb. The installer deploys it to the local hicolor application
  theme and both desktop/menu entries reference `Icon=sentry`.
- Application activation now explicitly closes the settings revealer and
  restores the inward chevron before presenting the native window. This makes
  both fresh and already-running launch paths default to the clean centered
  orb/status surface. A window-specific installed capture after service restart
  confirmed the drawer was absent. Exact focused validation now passes
  `117/117`.
- GNOME's running-app icon fallback was traced to identity mismatch: GTK
  advertised `local.sentry.Control`, the installed desktop file was named
  `sentry-ui.desktop`, and `_NET_WM_ICON` was absent. The installer now writes
  `local.sentry.Control.desktop`, removes the obsolete alias, and declares the
  observed `sentry_ui.py` startup class; the GTK window explicitly publishes
  the `sentry` icon. Installed inspection now resolves the local orb asset and
  reports a populated `_NET_WM_ICON`. Exact focused validation passes
  `118/118`.
- Desktop/application quick actions now expose `Launch on Main Displays` and
  `Launch on RTX Display`. Named launches validate and persist `:1.0` or
  `:1.1`, restart only `sentry-ui.service`, and select the sole non-HDMI or
  HDMI playback sink respectively. Live RTX-to-main proof observed the GTK
  process and default output on each requested target while the default USB
  microphone source remained unchanged. SENTRY was returned to main. Exact
  affected suites pass `124/124`; desktop-file validation passes.
- Operator testing showed Desktop Icons NG did not render those standard
  actions on the desktop shortcut. Installed-source inspection confirmed DING
  hardcodes `Open` and `Launch using Dedicated Graphics Card`; it does not
  enumerate desktop-file actions. The canonical SENTRY app is now pinned to
  the Ubuntu dock, which does enumerate the exact Main/RTX actions. The desktop
  shortcut's generic dedicated-GPU launch environment is now mapped to the RTX
  display/HDMI route. Exact live environment reproduction reached `:1.1` plus
  HDMI and then restored `:1.0` plus analog; USB input was unchanged. Exact
  affected suites pass `125/125`.

## Unattended ANIMA event wake/TTS target evidence — 2026-09-07

- The existing dirty SENTRY source connects `AttentionQueueSource` to the
  existing same-process resident voice loop at idle. It uses the filtered Core
  eligibility route, exact claim, existing persistent Codex thread, recorded
  Core result receipt, and existing Kokoro speaker. There is no embedded
  cognition fallback or second model/speaker process.
- The production path is opt-in only: absent, disabled, malformed, or
  context-unready private ANIMA config leaves the callback disconnected. No
  production configuration, service state, deployment, or ANIMA repository was
  changed in this slice.
- Added resident integration checks for exact wake/result/TTS ordering and
  provider-start outage. Existing focused checks cover no-action, required
  notification without forced speech, Core receipt disposition, and source
  latching after uncertainty.
- Validation: focused ANIMA event/runtime/voice suites **117/117 PASSED**;
  full unittest discovery **494/494 PASSED**; Python compilation **PASSED**;
  tracked `git diff --check` **PASSED**; Ruff **NOT RUN** because unavailable.
  Live Core/real-model/production TTS delivery **NOT RUN**.

## Push-first immediate household-alert latency evidence — 2026-09-09

- The event worker now blocks on Core's authenticated request-ready wait rather
  than a 15-second loop. Empty push waits were target-tested to produce no
  provider-start and no model call; the live voice PID has an established Unix
  connection to ANIMA Core while idle.
- A strict canonical `ALWAYS_NOTIFY` envelope starts warm speech immediately
  after durable provider-start. A deterministic model barrier proves speech
  begins before the low-effort model can complete. Post-alert follow-up
  listening is preserved even when the contextual model chooses silence.
- Exact request health/context/catalogue snapshots are written mode 0600 and
  consumed locally by the prebound MCP adapter. Direct voice turns with no
  preload siblings continue to read Core normally.
- The Pi projection endpoint returns its playback-process start timestamp; the
  local speaker records the local playback-process start. Trial records contain
  timing/status only, not announcement text, prompt, result or household data.
- Validation: focused suites 132 passed plus 57 subtests; complete unittest
  discovery 531 passed; Python compilation and `git diff --check` passed. The
  live PC voice, Pi projection and ANIMA Core services are active. A fresh
  physical alert timing sample remains NOT RUN.
- Installed Codex CLI 0.153.4 app-server compatibility was reproduced through
  `initialize` and `thread/start`. It cannot safely rotate the per-event
  `ANIMA_PREBOUND_FILE` or frozen MCP catalogue on `turn/start`, and interrupt
  does not promise MCP-child teardown. The existing process-group boundary is
  retained to preserve stale-binding revocation and no-replay.

### Owner clarification — two independent wake sources

The operator clarified that an ANIMA event must not depend on SENTRY being in
microphone `LISTENING` or waiting for the wake word. The explicit off switch is
SENTRY sleep mode. While awake, the resident ANIMA event worker polls Core
independently of microphone chunks and may deliver an authorized SenseGuard or
other household-event alert through the existing speaker.

There are two separate wake sources:

1. an operator-intonated wake word; and
2. a Core-authorized autonomous ANIMA event.

The event source is intentionally provider- and sensor-neutral. SenseGuard is
one possible producer, alongside presence changes, HA device state, routines,
weather, provider observations, and future typed integrations. Core creates the
same `AUTONOMOUS_ATTENTION` request for any eligible event; the resident worker
does not special-case SenseGuard.

There are two permitted paths to unsolicited delivery: an explicit
`ALWAYS_NOTIFY` policy, or a current `LEARNED_PROACTIVE` disposition after
ANIMA's learning and initiative rules permit proactive delivery. SENTRY may
reason about whether an eligible event deserves attention using the supplied
preferences, routines, memory, presence, freshness, urgency, and prior
delivery, but it cannot override a denied or still-learning Core disposition.

After either source produces a successfully delivered spoken response, the
listener opens the same bounded follow-up-listening window so the operator can
ask a question without another wake word. Active capture, an approval dialogue,
current speech, or SENTRY sleep still defers/disables event handling safely;
none of those conditions is required for the alert to be generated.
