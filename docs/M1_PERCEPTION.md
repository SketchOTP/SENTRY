# M1 local perception

M1 is an observation-only Ubuntu Linux service:

```text
webcam -> bounded latest-frame buffer -> local person detector -> temporary IoU tracks -> temporal room state -> structured observations
```

It makes zero SENTRY Codex/Luna calls. It does not perform identity recognition, persistence, sessions/history, semantic event emission, raw-frame storage, or a local API.

The bounded state layer maintains only `empty`, `occupied`, `degraded`, or `offline`. It uses timestamp-based hysteresis: one second of bounded positive evidence for entry, a one-second evidence-gap tolerance, and a 15-second absence grace period for exit. Duplicate detections remain binary human evidence and do not become multiple authoritative occupants. These values are configuration, not frame-count rules.

Each frame may also be reduced to metadata-only luminance/contrast measurements through `perception.presence_state.measure_image_quality`. No threshold is assumed for insufficient light until operator-labeled evidence establishes one; an explicit unusable-quality signal maps to `degraded`, never `empty`.

## Selected stack

The current working-tree candidate restores the previously verified Open Model Zoo `person-detection-0202` model through the official OpenVINO Python Runtime and a small SENTRY-owned two-stage IoU tracker. This candidate is `IMPLEMENTED_UNVERIFIED` until room-state qualification completes. The tracker is unchanged from the HOG, 0202, 0303, and RT-DETR investigations.

- `openvino==2026.3.1`, Apache-2.0, used for local CPU inference of the externally downloaded IR model.
- `opencv-python-headless==4.12.0.88`, used for camera and image handling.
- `psutil==7.0.0`, BSD-3-Clause, used only for process metrics.
- `person-detection-0202` is stored as ignored local Open Model Zoo FP32 XML/BIN under `perception-data/models/person-detection-0202/FP32/`; its recorded manifest checksums remain the authoritative provenance. It uses 512x512 BGR input and emits `[1,1,200,7]` detections. SENTRY uses confidence `0.40` and converts valid person rows to binary human evidence for the temporal room-state layer.
- The tracker is original SENTRY code. It keeps a bounded track table, associates high-confidence detections before lower-confidence detections, and retains unmatched tracks for a configured short dropout window.

YOLOX plus ByteTrack was evaluated first because YOLOX is Apache-2.0 and ByteTrack is MIT, and both are viable future options. It was not adopted for this first live attempt because the host had no Python/CV runtime, the YOLOX deployment path requires a separately sourced model artifact, and adding a PyTorch/ONNX stack before proving camera access would increase the installation and provenance surface. The detector interface is replaceable so a later benchmark can compare YOLOX-Nano or another permissive model on the same observation contract.

The selected runtime device is CPU. The host exposes other devices, but CPU keeps this first qualification deterministic and does not add a GPU-specific runtime.

## Configuration and operation

Install the pinned requirements into an isolated Linux Python environment, configure the stable V4L2 `device_path` discovered under `/dev/v4l/by-id/`, then run:

```text
python -m perception.sentry_perception --config perception-data/runtime/ubuntu-config.json --duration-seconds 600 --observation-file perception-data/runtime/perception-observations.jsonl
```

The observation file contains structured metadata only, including the current room state, binary detector-evidence flag, transition marker, and optional luminance/contrast measurements. It is not a video or image archive. Local observation files, logs, model weights, captures, and runtime data must stay outside Git.

The service requests the configured resolution/FPS and FOURCC through V4L2, records the actual backend/camera values, uses a size-one latest-frame buffer, drops stale frames, releases the camera on shutdown, and emits `offline` or `degraded` health rather than treating camera failure as an empty room. Prefer a stable `/dev/v4l/by-id/` path because numeric `/dev/videoX` assignments can change.

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
