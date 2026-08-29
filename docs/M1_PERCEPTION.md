# M1 local perception foundation

M1 is an observation-only Ubuntu Linux service:

```text
webcam -> bounded latest-frame buffer -> local person detector -> temporary IoU tracks -> temporal room state -> structured observations
```

It makes zero SENTRY Codex/Luna calls. The Architect has accepted the practical camera/human-detection foundation as good enough to proceed to M2; this is not a claim of perfect per-frame detector recall. Metadata-only sessions/events are now handled by `perception.presence_store`; raw-frame storage remains prohibited.

The bounded state layer maintains only `empty`, `occupied`, `degraded`, or `offline`. It uses timestamp-based hysteresis: one second of bounded positive evidence for entry, a one-second evidence-gap tolerance, and a 15-second absence grace period for exit. Duplicate detections remain binary human evidence and do not become multiple authoritative occupants. These values are configuration, not frame-count rules.

Each frame may also be reduced to metadata-only luminance/contrast measurements through `perception.presence_state.measure_image_quality`. No threshold is assumed for insufficient light until operator-labeled evidence establishes one; an explicit unusable-quality signal maps to `degraded`, never `empty`. The detector can expose positive raw candidates for metadata-only calibration, but weak support evidence cannot initiate occupancy.

## Selected stack

The current backend is official Megvii YOLOX-S through the already-qualified OpenVINO Python Runtime and a small SENTRY-owned two-stage IoU tracker. It is frozen as the practical V0.1 sensing backend by Architect direction; prior detector experiments remain historical evidence and are not reopened. The tracker remains unchanged from the HOG, 0202, 0303, and RT-DETR investigations.

- YOLOX-S source tag `0.3.0` resolves to commit `419778480ab6ec0590e5d3831b3afb3b46ab2aa3` in the official [Megvii repository](https://github.com/Megvii-BaseDetection/YOLOX), which is Apache-2.0 and documents OpenVINO deployment. The official model-zoo checkpoint URL is `https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_s.pth`; its local SHA-256 is `f55ded7181e1b0c13285c56e7790b8f0e8f8db590fe4edb37f0b7f345c913a30`. Release metadata does not state separate checkpoint terms; that limitation remains explicit.
- The official ONNX release SHA-256 is `c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063`. OpenVINO 2026.3 converted it to ignored IR with `[1,3,640,640]` input and `[1,8400,85]` output. Deterministic CPU output comparison between official ONNX and the converted IR was exact (`max_abs=0`).
- SENTRY follows upstream YOLOX validation semantics: top-left 114 padding with aspect-preserving resize, CHW float32 input, stride 8/16/32 grid decode, objectness × winning-class probability, final winning-class selection, coordinate restoration, clipping, and class-agnostic NMS `0.45`; only final class COCO person (`0`) is passed to the detector contract. Metadata-only room-state calibration selected operating confidence `0.50`, but final live Stage A produced sustained false occupancy in a confirmed-empty room; YOLOX-S office evidence remains insufficient pending this postprocessing investigation.

- `openvino==2026.3.1`, Apache-2.0, used for local CPU inference of the externally downloaded YOLOX-S IR model.
- `opencv-python-headless==4.12.0.88`, used for camera and image handling.
- `psutil==7.0.0`, BSD-3-Clause, used only for process metrics.
- The previously qualified-but-rejected `person-detection-0202` artifacts remain stored as ignored local Open Model Zoo FP32 XML/BIN under `perception-data/models/person-detection-0202/FP32/` for historical evidence only. They are not loaded by the active configuration.
- The tracker is original SENTRY code. It keeps a bounded track table, associates high-confidence detections before lower-confidence detections, and retains unmatched tracks for a configured short dropout window.

YOLOX-S is now the single Architect-authorized detector candidate because its official source, model-zoo artifacts, and OpenVINO deployment path are available under a bounded provenance record. The production path does not add PyTorch or ONNX Runtime; it loads the ignored OpenVINO IR produced from the official ONNX release. No ByteTrack dependency is used.

The selected runtime device is CPU. The host exposes other devices, but CPU keeps this first qualification deterministic and does not add a GPU-specific runtime.

## Configuration and operation

Install the pinned requirements into an isolated Linux Python environment, configure the stable V4L2 `device_path` discovered under `/dev/v4l/by-id/`, then run:

```text
python -m perception.sentry_perception --config perception-data/runtime/ubuntu-config.json --duration-seconds 600 --observation-file perception-data/runtime/perception-observations.jsonl
```

The observation file contains structured metadata only, including the current room state, strong/support detector-evidence flags, maximum candidate confidence, transition marker, and optional luminance/contrast measurements. It is not a video or image archive. Local observation files, logs, model weights, captures, and runtime data must stay outside Git.

The service requests the configured resolution/FPS and FOURCC through V4L2, records the actual backend/camera values, uses a size-one latest-frame buffer, drops stale frames, releases the camera on shutdown, and emits `offline` or `degraded` health rather than treating camera failure as an empty room. Prefer a stable `/dev/v4l/by-id/` path because numeric `/dev/videoX` assignments can change.

## Asymmetric-evidence calibration result

The Ubuntu Phase 2 calibration used a 60-second operator-confirmed empty segment (889 observations) and a 120-second continuously operator-confirmed one-person segment (1,791 observations). The fixed `0.40` entry gate appeared in only 63/1,791 occupied observations. Support thresholds from `0.10` through `0.40` produced simulated occupied correctness from 62.9% (0.10–0.35) to 40.1% (0.40); none met the `>=95%` requirement and bounded post-exit-empty requirement. No production hold threshold was changed.

## YOLOX-S room-state qualification history

Metadata-only calibration of fresh empty and one-person candidate records selected threshold `0.50` as the highest tested point passing the simulated state gates. The prior operator-confirmed-empty Stage A recorded 53/565 positive observations at or above `0.50`, with candidate confidence up to `0.824309`; the authoritative state was falsely `occupied` for 186/565 observations, including a sustained `19.272s` interval. This was recorded as `YOLOX-S OFFICE EVIDENCE INSUFFICIENT` under the prior strict qualification directive. The Architect subsequently accepted the practical camera/human-detection behavior as sufficient to proceed, explicitly ending the detector carousel. The residual risk is carried forward as an operational limitation rather than hidden or re-tested here.

## M2 persistence slice

`perception.presence_store.PresenceStore` records the current office state, state-derived room/session events, and open/completed presence sessions in a versioned SQLite database. The active database is configured at a local per-user path (`~/.local/share/sentry/sentry.db` in the example); the Atlas path is a complete snapshot mirror under ignored `perception-data/runtime/backups/`. The store consumes structured observations only, uses UTC timestamps, supports restart reconciliation, and stores no raw image or video data. `tools/sentry_state_api.py` exposes localhost-only health, current-state, sessions, and event queries from the local live database.

## Evidence boundary

Automated tracker/configuration/contract tests can establish deterministic behavior. M1 acceptance additionally requires fresh live Ubuntu evidence from the actual office webcam, including visible-person detection, multiple people, short dropout, recovery, useful processed FPS, latency, resource measurements, and a ten-minute run. If the device cannot be opened, the live portion is `BLOCKED/NOT RUN`; synthetic frames must not be substituted for that claim. Historical Windows evidence remains labeled as such and is not reused for Ubuntu acceptance.

## External sources reviewed

- [YOLOX repository and Apache-2.0 license](https://github.com/Megvii-BaseDetection/YOLOX)
- [ByteTrack repository and MIT license](https://github.com/FoundationVision/ByteTrack)
- [ONNX Runtime execution providers](https://onnxruntime.ai/docs/execution-providers/)
- [OpenVINO Python installation](https://docs.openvino.ai/2025/get-started/install-openvino/install-openvino-pip.html)
- [OpenVINO repository and Apache-2.0 license](https://github.com/openvinotoolkit/openvino)
- [Open Model Zoo person-detection-0303 README](https://github.com/openvinotoolkit/open_model_zoo/blob/master/models/intel/person-detection-0303/README.md)
- [Open Model Zoo person-detection-0303 manifest](https://github.com/openvinotoolkit/open_model_zoo/blob/master/models/intel/person-detection-0303/model.yml)
- [Open Model Zoo Apache-2.0 license](https://github.com/openvinotoolkit/open_model_zoo/blob/master/LICENSE)
- [Open Model Zoo class-agnostic adapter source](https://raw.githubusercontent.com/openvinotoolkit/open_model_zoo/master/tools/accuracy_checker/accuracy_checker/adapters/detection.py)
