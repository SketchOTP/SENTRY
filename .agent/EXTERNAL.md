# External Discovery Ledger

Record material prior-art investigations when Authority triggers external discovery. Do not log every trivial web search.

No external discovery was required for this governance-only bootstrap. The directive explicitly marked external discovery `NOT REQUIRED`; Notion and GitHub were authoritative project sources, and the canonical Authority package was retrieved from Notion.

---

## EXTERNAL-SENTRY-014 — Codex-native agent, MCP, image, and computer surfaces
- Date: 2026-09-01
- Freshness: official OpenAI Codex configuration, MCP, plugin, Computer Use, and image-generation documentation reviewed against installed Codex CLI `0.150.0-alpha.8`; MCP Python SDK `2.1.1` reproduced locally.
- Sources: [Codex configuration reference](https://developers.openai.com/codex/config-file/config-reference), [MCP](https://learn.chatgpt.com/docs/extend/mcp), [Plugins](https://learn.chatgpt.com/docs/plugins), [Computer Use](https://learn.chatgpt.com/docs/computer-use), [Image generation](https://learn.chatgpt.com/docs/image-generation), and [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk).
- Finding: Codex named profiles can select write-capable sandboxing, inherit installed skills/plugins, and launch local stdio MCP servers. CLI image generation is available through `$imagegen`; native web search is available with `--search`. Official graphical Computer Use is not a Linux-host runtime, and interactive Browser control requires a connected in-app browser or ChatGPT browser extension.
- Disposition: ADOPT a dedicated Codex profile plus local SENTRY MCP/skill; COMPOSE Linux desktop actions from structured desktop entries, PipeWire, MPRIS, and X11 tools; RETAIN Browser as connection-dependent rather than claiming an unavailable surface.
- Recheck trigger: Codex CLI/profile/MCP schema changes, Linux graphical Computer Use support, or a connected browser surface becoming part of the unattended runtime.

---

## EXTERNAL-SENTRY-013 — OpenAI constrained response schema and tool-orchestration boundary
- Date: 2026-08-31
- Freshness: Official OpenAI Responses API reference and GPT-5.6 model guidance reviewed during `SENTRY-V0.3-CONVERSATIONAL-ORCHESTRATION-001`; installed OAuth Codex CLI behavior reproduced on the same host.
- Sources: [OpenAI Responses API reference](https://developers.openai.com/api/reference/cli/resources/responses/methods/create) and [GPT-5.6 model guidance](https://developers.openai.com/api/docs/guides/latest-model).
- Finding: current OpenAI guidance supports structured outputs and typed tool selection, with the application retaining autonomy boundaries and validation. The installed OAuth `codex exec` path supports `--output-schema` but does not offer a safe per-invocation host function catalog. Its strict schema endpoint also rejects `oneOf` in array item schemas.
- Disposition: ADOPT the bounded two-phase fallback: strict planner JSON → host-side typed local execution → strict grounded synthesis. All model-selected calls remain allow-listed and revalidated; no credentials, remote tool service, or arbitrary capability is added.
- Recheck trigger: a later installed OAuth CLI safely exposes a request-scoped function-tool catalog, or official strict-schema support changes.

---

## EXTERNAL-SENTRY-001 — DAWN M0 integration surface investigation
- Date: 2026-08-24
- Freshness: DAWN `main` at `a0c0b13c65f1b02a3416d846f6a0d331244eee9d`; current project Notion fetched 2026-08-24
- Source: [DAWN repository](https://github.com/The-OASIS-Project/dawn), [server deployment guide](https://github.com/The-OASIS-Project/dawn/blob/a0c0b13/docs/GETTING_STARTED_SERVER.md), [WebSocket protocol](https://github.com/The-OASIS-Project/dawn/blob/a0c0b13/docs/WEBSOCKET_PROTOCOL.md), [tool development guide](https://github.com/The-OASIS-Project/dawn/blob/a0c0b13/docs/TOOL_DEVELOPMENT_GUIDE.md), and inspected source at the same commit
- Overlap: DAWN provides server mode, WebSocket conversations, MQTT device/telemetry paths, SAGE proactive attention, system-context injection, and TTS delivery.
- Disposition: REJECT for the current M0 proof as a complete supported path; REFERENCE for future architecture decisions.
- Rationale: WebSocket/satellite inputs are user text; MQTT generic relay becomes a user-role `[DEVICE DATA]` turn; SAGE watches only a fixed DAWN telemetry catalog and does not expose SENTRY event ingress; context injection does not initiate reasoning; custom tools require DAWN source/build registration.
- Licensing/deployment: DAWN is GPL-3.0-or-later. Server deployment is documented for x86_64 Linux/Docker, not natively Windows. Docker and WSL are installed on the host, but runtime was not started after the supported-boundary stop condition.
- Recheck trigger: DAWN documents a generic trusted event ingress/proactive trigger, or Architect explicitly authorizes an upstream change/fork, licensing review, or foundation comparison.

---

## EXTERNAL-SENTRY-002 — Official Codex OAuth, noninteractive, structured output, and Luna capability
- Date: 2026-08-24
- Freshness: Official OpenAI documentation retrieved through `/browse` on 2026-08-24; installed Codex behavior tested on the same host
- Sources: [Codex CLI](https://developers.openai.com/codex/cli/), [Codex non-interactive mode](https://developers.openai.com/codex/noninteractive/), [Codex authentication](https://developers.openai.com/codex/auth/), [GPT-5.6 Luna model](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
- Overlap: Codex CLI supports local script/CI invocation, ChatGPT sign-in, ephemeral runs, JSONL events, JSON Schema output, and explicit model/effort configuration; Luna supports the required effort levels.
- Disposition: ADOPT for the bounded M0 proof; REFERENCE for future governor/deployment design.
- Rationale: The supported CLI surface matches SENTRY's required on-demand shape without adding an assistant framework. Two OAuth-only local turns passed with independent synthetic event IDs and measurable per-turn usage.
- Limitations: The current proof is trusted-local, not public unattended service deployment. Official docs state ChatGPT-managed auth is supported locally but general automation often uses API keys; SENTRY's architecture must preserve credential privacy. Subscription quota remaining and plan-wide idle billing were not exposed by the CLI; only per-turn JSONL token usage and process behavior were observed.
- Recheck trigger: Codex CLI/model/auth changes, ChatGPT plan policy changes, or any move from a trusted local process to a scheduler/service.

---

## EXTERNAL-SENTRY-003 — Codex instruction discovery and isolated execution context
- Date: 2026-08-24
- Freshness: Official OpenAI Codex documentation retrieved through `/browse` on 2026-08-24; Codex CLI `0.145.0` behavior tested on the same host
- Sources: [Codex non-interactive mode](https://developers.openai.com/codex/noninteractive/), [Codex AGENTS.md guidance](https://learn.chatgpt.com/docs/agent-configuration/agents-md), [Codex authentication](https://developers.openai.com/codex/auth/), and local `codex exec --help`
- Overlap: Codex project instruction discovery explains the 19k baseline; supported noninteractive flags provide ephemeral JSONL, schema output, `--ignore-user-config`, and `--skip-git-repo-check`.
- Disposition: ADOPT the isolated cwd for SENTRY runtime reasoning; REFERENCE the discovery rules for development sessions.
- Rationale: Repo-root audit reported `\\atlas\ATLAS\100_ACTIVE\Projects\SENTRY\AGENTS.md`; the isolated cwd had zero `AGENTS*` files. The same-event input reduction was 5.4%, and the final bridge retained schema/grounding equivalence. A 50% reduction was not achieved, so no further unsupported optimization was attempted.
- Limitations: The isolated run retained installed skills context and measured approximately 18.2k input tokens. OAuth/local behavior is trusted-host evidence only; subscription quota and plan-wide idle billing remain unavailable from the CLI.
- Recheck trigger: Codex CLI release, AGENTS discovery/config changes, model/auth policy changes, or a move to service/scheduler deployment.

---

## EXTERNAL-SENTRY-004 — M1 detector/tracker/runtime/license comparison
- Date: 2026-08-24
- Freshness: Official upstream pages retrieved through `/browse` on 2026-08-24.
- Sources: [YOLOX](https://github.com/Megvii-BaseDetection/YOLOX), [ByteTrack](https://github.com/FoundationVision/ByteTrack), [ONNX Runtime execution providers](https://onnxruntime.ai/docs/execution-providers/), [OpenCV license](https://opencv.org/license/), and [OpenCV HOGDescriptor API](https://docs.opencv.org/4.x/d5/d33/structcv_1_1HOGDescriptor.html).
- Overlap: Local person detection, permissive licensing, model provenance, tracking, and Windows execution-provider selection.
- Disposition: ADOPT OpenCV HOG plus SENTRY-owned IoU tracking for the first narrow implementation; REFERENCE YOLOX plus ByteTrack and ONNX Runtime for a future benchmark.
- Rationale: OpenCV 4.5+ is Apache-2.0 and its HOG people detector coefficients are bundled, avoiding a separate model-weight provenance step for this slice. YOLOX is Apache-2.0 and ByteTrack is MIT, but the usual stack adds separately sourced artifacts and a larger runtime before camera access is proven. Host GPUs were observed but not required by the selected CPU path.
- Limitation: No live detector quality or performance claim is made because the actual webcam could not be opened.
- Recheck trigger: Webcam access restored, a detector performance shortfall, a qualified model artifact becoming available, or authorization for a YOLOX/ONNX benchmark.

---

## EXTERNAL-SENTRY-005 — Open Model Zoo person-detection-0202 and OpenCV DNN compatibility
- Date: 2026-08-25
- Freshness: Official upstream pages retrieved through `/browse` on 2026-08-25; artifact checksums and host runtime behavior reproduced on the same date.
- Sources: [person-detection-0202 manifest](https://raw.githubusercontent.com/openvinotoolkit/open_model_zoo/master/models/intel/person-detection-0202/model.yml), [person-detection-0202 documentation](https://raw.githubusercontent.com/openvinotoolkit/open_model_zoo/master/models/intel/person-detection-0202/README.md), [Open Model Zoo Apache-2.0 license](https://raw.githubusercontent.com/openvinotoolkit/open_model_zoo/master/LICENSE), and [OpenCV DNN upstream API](https://github.com/opencv/opencv/blob/4.x/modules/dnn/include/opencv2/dnn/dnn.hpp).
- Overlap: Dedicated local person detection, explicit model provenance/license, OpenVINO IR loading, and preservation of SENTRY's detector contract.
- Disposition: REFERENCE the model candidate and provenance; REJECT adoption through the current generic OpenCV wheel because the required backend plugin is unavailable.
- Rationale: The FP32 XML/BIN artifacts matched the manifest SHA-384 checksums and the manifest linked the candidate to Apache-2.0. However, both OpenCV IR-loading entry points failed under `opencv-python-headless==4.12.0.88` with `Backend (plugin) is not available: 'openvino'`. No OpenVINO Runtime or alternate inference stack was added.
- Limitation: No candidate single-frame or live quality evidence exists. The existing HOG plus IoU result remains the only live detector evidence and is not M1-acceptable.
- Recheck trigger: Explicit Architect authorization for a compatible OpenCV build/OpenVINO Runtime or a new detector candidate.

---

## EXTERNAL-SENTRY-006 — Official OpenVINO Python Runtime installation and IR execution
- Date: 2026-08-26
- Freshness: Official OpenVINO installation/repository pages retrieved through `/browse` on 2026-08-26; package installation and model execution reproduced on the host the same day.
- Sources: [OpenVINO Python installation](https://docs.openvino.ai/2025/get-started/install-openvino/install-openvino-pip.html), [OpenVINO repository](https://github.com/openvinotoolkit/openvino), and [Open Model Zoo person-detection-0202 README](https://github.com/openvinotoolkit/open_model_zoo/blob/master/models/intel/person-detection-0202/README.md).
- Overlap: Supported Windows Python runtime, OpenVINO IR loading/compilation, CPU device execution, and the already-qualified person detector.
- Disposition: ADOPT the official `openvino` Python runtime at the tested pin `2026.3.1`; WRAP it behind SENTRY's existing detector interface.
- Rationale: The official package installed cleanly in the isolated Python 3.12 environment, exposed `CPU`, `GPU.0`, and `GPU.1`, and directly loaded/compiled the existing FP32 XML/BIN model. Bounded inference produced the documented `1x1x200x7` output. No OpenCV replacement or second inference framework was needed.
- Limitations: Runtime compatibility is reproduced, but live detector adequacy remains unproven pending operator-confirmed ground truth. The 2025 documentation page was used for the installation workflow because it was the reachable official page; the current official repository README also documents `pip install -U openvino` and version verification.
- Recheck trigger: OpenVINO package/model format changes, Python or Windows support changes, or a future Architect-authorized runtime replacement.

---

## EXTERNAL-SENTRY-007 — Open Model Zoo person-detection-0303 provenance and output semantics
- Date: 2026-08-26
- Freshness: Official Open Model Zoo manifest, README, license, and artifact sources retrieved through `/browse` on 2026-08-26; model download, checksum, OpenVINO load/compile, and output inspection reproduced on the same date.
- Sources: [person-detection-0303 manifest](https://github.com/openvinotoolkit/open_model_zoo/blob/master/models/intel/person-detection-0303/model.yml), [person-detection-0303 README](https://github.com/openvinotoolkit/open_model_zoo/blob/master/models/intel/person-detection-0303/README.md), [Open Model Zoo Apache-2.0 license](https://github.com/openvinotoolkit/open_model_zoo/blob/master/LICENSE), and the manifest's [FP32 XML](https://storage.openvinotoolkit.org/repositories/open_model_zoo/2023.0/models_bin/1/person-detection-0303/FP32/person-detection-0303.xml) / [FP32 BIN](https://storage.openvinotoolkit.org/repositories/open_model_zoo/2023.0/models_bin/1/person-detection-0303/FP32/person-detection-0303.bin) sources.
- Overlap: Local person detection through the existing OpenVINO runtime, native 1280x720 BGR input, absolute-coordinate box decoding, and preservation of SENTRY's detector/tracker boundary.
- Disposition: REFERENCE provenance and output semantics; REJECT 0303 for the tested office scene after operator-confirmed live quality failure.
- Rationale: The candidate met artifact/runtime/performance prerequisites, but emitted zero person candidates during 588 observations of continuously confirmed one-person visibility, including at threshold 0.10. No tracker change or alternate runtime was introduced.
- Limitation: Bounding-box visual sanity and tracker qualification were not reached because no one-person candidate was produced. Camera recovery remains untested.
- Recheck trigger: A separately authorized detector decision; do not switch model, runtime/device, precision, or tracker under this completed directive.

---

## EXTERNAL-SENTRY-008 — Open Model Zoo class-agnostic 0303 adapter semantics
- Date: 2026-08-26
- Freshness: Official Open Model Zoo `accuracy-check.yml` and adapter source retrieved through the required browse workflow on 2026-08-26; local raw-output and decoder behavior reproduced on the same date.
- Sources: [person-detection-0303 accuracy configuration](https://github.com/openvinotoolkit/open_model_zoo/blob/master/models/intel/person-detection-0303/accuracy-check.yml) and [ClassAgnosticDetectionAdapter source](https://raw.githubusercontent.com/openvinotoolkit/open_model_zoo/master/tools/accuracy_checker/accuracy_checker/adapters/detection.py).
- Overlap: 0303 OpenVINO output decoding, class-agnostic confidence selection, coordinate scaling, and reference postprocessing.
- Disposition: REFERENCE and EXTEND the upstream semantics in the existing SENTRY detector wrapper; do not adopt the full Accuracy Checker runtime.
- Rationale: The official adapter selects positive-confidence box rows, multiplies coordinates by `[1/1280, 1/720]` in its configured representation, assigns person label `1`, and the model config applies resize, NMS overlap `0.6`, and clipping. SENTRY's old `labels == 1` gate was therefore a material decoder discrepancy. Correcting it exposed candidates but did not make 0303 meet the live empty/person quality gate.
- Limitation: This discovery changes the interpretation of the prior 0303 zero-candidate result, not the final live quality outcome. The corrected detector still fails the tested office scene; no alternate model or tracker was authorized.
- Recheck trigger: Any future 0303 model artifact/output change or separately authorized detector decision.
## YOLOX-S official source and deployment discovery — 2026-08-28
- Source: official `Megvii-BaseDetection/YOLOX` repository at tag `0.3.0`, commit `419778480ab6ec0590e5d3831b3afb3b46ab2aa3`; official README, model-zoo, OpenVINO demo, and GitHub release API.
- Findings: upstream repository is Apache-2.0; YOLOX-S is the official 640x640, 9.0M-parameter, 26.8 GFLOPs standard model; the repository documents OpenVINO deployment and links the official `0.1.1rc0/yolox_s.pth`, `yolox_s.onnx`, and `yolox_s_openvino.tar.gz` assets.
- Artifact provenance: official checkpoint URL and SHA-256 `f55ded7181e1b0c13285c56e7790b8f0e8f8db590fe4edb37f0b7f345c913a30`; official ONNX SHA-256 `c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063`; official archive SHA-256 `feeda7f65bdc9e44c4a8732fbfb22cd10787db9df0ef3c0472e5bf6f7b7ef7e3`. The release metadata exposes no separate checkpoint license text; that absence is retained as a provenance limitation, not silently treated as a stronger license grant.
- Runtime/export evidence: official ONNX and official IR both expose `[1,3,640,640]` input and `[1,8400,85]` output. OpenVINO 2026.3 converted the official ONNX into ignored local IR; deterministic CPU output comparison against the official ONNX was exact (`max_abs=0`).
- Disposition: **ADOPT for bounded qualification** behind the existing detector interface; do not add the YOLOX/PyTorch training stack to production. Recheck if upstream changes the linked checkpoint, export semantics, or license terms.

## EXTERNAL-SENTRY-009 — Official YOLOX final-class postprocessing parity
- Date: 2026-08-28
- Freshness: Official YOLOX 0.3.0 source and deployment code were inspected during this investigation; local identical-tensor and deterministic regression checks were reproduced on the same date.
- Sources: [YOLOX 0.3.0 demo inference](https://github.com/Megvii-BaseDetection/YOLOX/blob/0.3.0/demo/ONNXRuntime/onnx_inference.py), [YOLOX 0.3.0 demo utilities](https://github.com/Megvii-BaseDetection/YOLOX/blob/0.3.0/yolox/utils/demo_utils.py), and [YOLOX 0.3.0 postprocess](https://github.com/Megvii-BaseDetection/YOLOX/blob/0.3.0/yolox/utils/boxes.py).
- Finding: upstream computes `objectness × class_probability` for every class, selects the highest-scoring class, then applies class-agnostic NMS at `0.45`. The prior SENTRY path evaluated only the person-class product before NMS, so it could retain a person-scored box whose winning class was non-person.
- Disposition: **DIVERGENCE CONFIRMED — corrected in the existing YOLOX decoder**. The corrected path retains final-class metadata, applies upstream order, and passes only final class `0` to the SENTRY person contract. No new model, runtime, tracker, device, or threshold was introduced.
- Validation: deterministic overlapping-box regression demonstrates legacy-vs-reference divergence; corrected SENTRY tests pass. A live same-tensor probe was blocked because `/dev/video0` was held by unrelated `anima` PID `219972`; no live parity claim is made until the camera is available.
## EXTERNAL-SENTRY-010 — Python standard-library SQLite and localhost HTTP primitives
- Date: 2026-08-28
- Source: [Python sqlite3 documentation](https://docs.python.org/3.12/library/sqlite3.html) and [Python http.server documentation](https://docs.python.org/3.12/library/http.server.html)
- Freshness: official Python 3.12 documentation, checked during the M2 implementation.
- Relevance: SENTRY needed a small versioned local metadata store and read-only localhost query surface without introducing a framework or dependency.
- Disposition: **BUILD using the standard library**. `sqlite3` supplies the local database connection/migrations; `ThreadingHTTPServer` supplies the bounded localhost read surface. SQLite cross-thread access is serialized by the store lock because Python documents that disabling `check_same_thread` requires user serialization for writes.
- Boundary: this does not establish suitability of SQLite locking on every network/shared filesystem. The canonical Atlas path remains authoritative and that mount behavior is a later measured operational concern.

## EXTERNAL-SENTRY-011 — Dedicated wake-engine provenance and clean-route evaluation
- Date: 2026-08-31
- Freshness: upstream project licensing/repositories and package artifacts checked during `SENTRY-V0.3-WAKE-RELIABILITY-SELECTION-001`.
- Sources: [openWakeWord README](https://github.com/dscripka/openWakeWord/blob/main/README.md?plain=1), [micro-wake-word](https://github.com/OHF-Voice/micro-wake-word), [microWakeWord data sources](https://github.com/kahrendt/microWakeWord/blob/main/documentation/data_sources.md), [pymicro-features](https://github.com/rhasspy/pymicro-features), and [Porcupine documentation](https://picovoice.ai/docs/porcupine/).
- Findings: openWakeWord runtime code supports custom models but bundled classifiers are not acceptable for SENTRY's clean route; microWakeWord code/framework is Apache-2.0 but its standard recipes include non-commercial sources such as WHAM!, so published/default artifacts cannot be adopted without per-artifact provenance; Porcupine requires an AccessKey.
- Disposition: **REJECT BOTH CUSTOM CANDIDATES FOR THIS CAPTURE SET; PORCUPINE NOT AVAILABLE.** The local openWakeWord-compatible model had clean input provenance but failed live recall. The local microWakeWord-style model had clean input provenance but failed held-out negative safety. No bundled model, default recipe data, unknown community weight, cloud audio, account, or credential was adopted.
- Recheck trigger: Architect authorizes a materially different, fully licensed and provenance-auditable data/model route or supplies an already-authorized proprietary credential. Any future route must start with a new bounded selection directive and must retain the current negative evidence.

### Superseding implementation correction
- The custom openWakeWord-compatible candidate remains under evaluation rather than rejected for the full available data set: v2 used only 10 positive clips because the local trainer accepted one positive directory. This is a local selection bug, not an external provenance finding. The permitted correction is to train from all approved local-positive directories; no upstream asset or license disposition changes.

### Final local evaluation result
- The corrected v3 custom openWakeWord-compatible model consumed all 40 positive and 40 negative explicit local clips, then failed held-out validation with 22 negative false positives and 66.7% recall. The external provenance conclusion remains unchanged; the rejection now concerns model/data sufficiency rather than licensing or input selection.

## EXTERNAL-SENTRY-012 — Pretrained PocketSphinx and Vosk wake evaluation
- Date: 2026-08-31
- Freshness: official PocketSphinx configuration documentation and the official Vosk model table were checked during `SENTRY-V0.3-WAKE-RELIABILITY-PRETRAINED-KWS-001`.
- Sources: [PocketSphinx 5.1.1 configuration](https://pocketsphinx.readthedocs.io/en/stable/config_params.html), [PocketSphinx source](https://github.com/cmusphinx/pocketsphinx), [CMUSphinx models](https://github.com/cmusphinx/models), [CMUdict](https://github.com/cmusphinx/cmudict), and [Vosk official models](https://alphacephei.com/vosk/models).
- Findings: PocketSphinx exposes dedicated `keyphrase`, `kws`, `kws_delay`, and `kws_threshold` controls for continuous KWS. The source artifact is BSD-style; its bundled CMUdict entry is `sentry S EH N T R IY`. Vosk 0.3.45 was used only in an isolated evaluator, and the official model table identifies `vosk-model-small-en-us-0.15` as Apache-2.0 with dynamic vocabulary support.
- Artifact evidence: PocketSphinx 5.1.1 source SHA-256 `675778b309a22dfc9b7d37f7621976bba491d2a5f8c59696bd77fd6d07271355`; isolated native library SHA-256 `ae6a577b4015b7d1936dac2962df85e0c020075bd71b6e8b535a217cfc661bfd`; Vosk small-en-us model archive SHA-256 `30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498`.
- Disposition: PocketSphinx is rejected because contextual uses of the one-word target caused detections. Vosk is a promising but **not formally selected** isolated candidate: Stage A passed only under the owner's explicitly relaxed single-word policy, and full Stage B/ambient qualification was stopped early. No external model is integrated into SENTRY.
