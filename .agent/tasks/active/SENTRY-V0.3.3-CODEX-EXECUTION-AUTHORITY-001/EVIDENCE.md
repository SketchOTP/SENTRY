# Evidence

## Baseline and containment

- Starting HEAD and `origin/main`: `325cc24ae8745f0eeb4d506012943da85dedbebd`.
- Working tree was clean before implementation.
- Schema baseline: 9. Accepted regression baseline: 255/255.
- Production `sentry-voice.service` and `sentry-voice-status.service` were stopped before security work.
- No `pw-record`, Whisper, or Vosk orphan remained.
- Existing persistent Codex session pointer and unrestricted development profile were not changed during containment.

## Installed Codex discovery

- Installed CLI: `codex-cli 0.150.0-alpha.8`.
- Permission profiles are supported by the installed CLI.
- A temporary resident-style profile enforced workspace write, denied direct `$HOME/.ssh` reads, and denied command network access.
- Official Codex documentation confirms permission profiles are independent of browser/computer/MCP/app capability controls and must not be mixed with legacy `sandbox_mode` flags.

Further qualification evidence will be appended before handoff.

## Audio timeline redesign and deterministic gate — 2026-09-02

- Recovery snapshot created before restructuring at
  `/home/sketch/.local/state/sentry/recovery/audio-timeline-20260902-KIrWBF`
  with mode-0700 directory/mode-0600 files and no audio, transcript, credential,
  private-config, database, biometric, or coordinate content.
- Added a bounded sample-indexed PCM timeline and append-only active utterance
  capture. Vosk now emits wake/sample metadata only; one frozen capture supplies
  exact full/post-wake Whisper views. Missing sample ranges fail closed.
- Targeted suites passed 86/86. Python compilation and `git diff --check` passed.
- Tests covered a 12-second command with four internal VAD dips, wake after five
  seconds, duplicate wake, ring wrap, gap rejection, max duration, wake-only,
  post-wake local second pass, non-wake zero dispatch, PTT, resident runtime,
  persistent Codex, and execution authority.

## Sole authorized live attempt — BLOCKED

- Production service reached `LISTENING` under the restricted `sentry-resident`
  profile and persistent Codex thread. Exactly one `pw-record` owned the stream.
- Spoken controlled request asked SENTRY to prepare moving
  `authority-live-proof/voice-controlled-move.txt` to Downloads as
  `cancelled-long-command-proof.txt`, requiring explicit confirmation.
- Vosk wake count: 1. Capture gaps: 0. Capture: 50,304 samples / 3.144 seconds;
  post-wake STT view: 2.356 seconds; endpoint reason: silence; transcription
  attempts: 2; command dispatches: 1.
- The semantic request was truncated. Codex replied: “Could you clarify what you
  mean by Sentry”. No Tier-2 proposal or pending authorization was created.
- Source fixture remained present and unchanged at SHA-256
  `1caaefc907ad50c24cf8ed1e7e428ae11d01e99f1d31b83b71772edaeb38d9d7`.
  Destination remained absent. No executor ran and no mutation occurred.
- Directive stop boundary applied. Voice/status were stopped; no second live
  attempt, additional tuning, short/no-wake checks, matrix, full regression,
  implementation commit, or push occurred.

## Smart Turn v3.2 pre-live screen — BLOCKED — 2026-09-02

- Created source-only recovery snapshot
  `/home/sketch/.local/state/sentry/recovery/semantic-turn-20260902-dky5i3`
  before semantic endpoint edits. Directory/files are mode 0700/0600 and contain
  no runtime audio, transcripts, credentials, private config, database, biometric
  data, or coordinates.
- Verified exact local CPU artifact `smart-turn-v3.2-cpu.onnx`, 8,679,182 bytes,
  SHA-256 `2bb026316b14a660486a75b1733cd3fbab8c2fd0314dc9af7be49f8cca967e4f`,
  from `pipecat-ai/smart-turn-v3`, BSD-2-Clause.
- Added only the standalone ONNX adapter, not Pipecat. Runtime dependencies are
  `onnxruntime==1.29.0` and `transformers==5.16.1`; provider is CPU only.
- Deterministic adapter/audio-timeline/always-on-voice suites passed 56/56. The
  long fixture retained one 13.184-second immutable capture through a 1.792-
  second internal pause, three incomplete decisions, and two stable complete
  decisions. Non-wake speech invoked neither endpoint inference nor Whisper.
- The actual model was screened using 10 incomplete and 10 completed controlled
  local British-male Kokoro utterances. Audio stayed in process memory; zero
  WAV/PCM fixtures were written. Result: incomplete 0/10, complete 10/10.
- Incomplete probabilities: 0.970843, 0.568494, 0.944584, 0.961939, 0.938064,
  0.904224, 0.960470, 0.978554, 0.957368, 0.977712. Complete probabilities:
  0.984260, 0.868822, 0.944584, 0.643550, 0.568494, 0.957368, 0.897182,
  0.968528, 0.944584, 0.792352.
- No threshold can hold at least 8/10 incomplete samples while closing at least
  8/10 complete samples. Median/p95 inference was 51.806/57.552 ms, model load
  63.147 ms, and measured model-load RSS increase 45,892 KiB.
- The mandatory screen failed before operator speech. No live request, Whisper,
  Codex invocation, authorization, mutation, full regression, commit, or push
  followed. Required result: `BLOCKED — STREAMING STT REQUIRED`.

## Dual-Vosk streaming command capture — pre-live checkpoint — 2026-09-02

- Created source-only recovery snapshot
  `/home/sketch/.local/state/sentry/recovery/streaming-command-20260902-wuNfvA`
  before editing. Directory/files are mode 0700/0600 and checksummed; no audio,
  transcript, credential, private config, database, biometric, or coordinate
  content is included.
- One local Vosk model object now creates two independent recognizers: restricted
  wake grammar and full-vocabulary command progress. The installed Python 0.3.45
  binding does not expose endpointer mode configuration, so Vosk segment finals
  remain non-terminal and the host's five-second dual-idle boundary is explicit.
- Smart Turn production imports, configuration, tests, license payload, and
  dependency pins were selectively removed. Historical failure records and the
  optional local model artifact remain intact.
- Initial exact-code Vosk, PCM timeline, and always-on listener tests pass 60/60;
  Python compilation, JSON configuration validation, and `git diff --check`
  pass. Controlled acoustic screening remains pending; no operator attempt,
  authorization, mutation, commit, or push has occurred.

## Trusted-operator natural action handoff — final local evidence — 2026-09-02

- The later long-command proof retained the complete Vosk-authorized request,
  reached Whisper and the restricted persistent Codex thread, and created the
  intended exact deferred file-move proposal without early execution. This
  supersedes the earlier endpoint blocker; Vosk remains sole wake authority.
- Direct live proof: `Sentry, move move-test.txt to Downloads` moved one
  controlled 55-byte file from the private agent workspace to the operator's
  Downloads directory. No redundant confirmation was requested. Source became
  absent, destination became present with mode 0600, and pre/post SHA-256 was
  `b7f1d73d3dabf5b5b99abb8e450d8754a954366fdbae24b973a80d3389910b0c`.
- Audit request `59ba73b2-50a0-44c9-8814-529b979efc2e`, action
  `6faaa3eb-1db3-4b91-b4f2-c4d3c77c50b8`, records
  `authority_source=direct_current_turn`, `EXECUTING`, then
  `EXECUTED/completed`. No actionable pending authorization remains.
- The operator explicitly waived synthetic live proofs B-D after the direct
  proof, explaining that ordinary commands should execute because issuing the
  command already expresses intent. Deferred approval/cancellation/revision
  remains available only for explicit delay wording or unresolved detail. Its
  lifecycle and natural responses are automated-test evidence, not claimed live
  evidence.
- Consolidated automated authority matrix passes: direct current request;
  explicit deferral; presentation-relative 120-second deadline; natural
  approval/cancel/question/revision/unrelated/unusable handling; request,
  thread, restart, argument, destination, active-window and replay binding;
  no-overwrite; traversal/symlink/protected-path denial; audit-write failure;
  credential-like typed-input denial; and untrusted webpage/repository/
  screenshot/MCP/stale-thread/source-document non-authority.
- Installed-profile matrix passes: mode-0600 profile; one managed MCP server;
  workspace-only writes; command network disabled; login shell disabled;
  apps/plugins/Browser/CDP/computer use/Codex memories disabled; original Codex
  auth and resident-home alias denied; future Obsidian path denied; private
  authority root denied; child environment allow-listed.
- Final affected suites: 198/198. Security/profile/Codex subset: 45/45. Complete
  exact-code Ubuntu regression: 334/334 in 47.628 seconds. The only output was
  the known localhost socket `ResourceWarning` and multiprocessing-fork
  `DeprecationWarning`; neither failed a test.
- Python compilation, public/private JSON parsing, `git diff --check`, changed-
  file credential-pattern scan, mode-0700 authority root, mode-0600 append-only
  audit, audit-content privacy scan, and current V0.3.3 no-new-WAV/PCM scan pass.
  Historical explicitly captured wake-training WAVs remain outside Git and are
  not V0.3.3 runtime artifacts.
