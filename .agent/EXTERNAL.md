# External Discovery Ledger

Record material prior-art investigations when Authority triggers external discovery. Do not log every trivial web search.

No external discovery was required for this governance-only bootstrap. The directive explicitly marked external discovery `NOT REQUIRED`; Notion and GitHub were authoritative project sources, and the canonical Authority package was retrieved from Notion.

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
