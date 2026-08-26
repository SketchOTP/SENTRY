# M1 local perception

M1 is an observation-only Windows service:

```text
webcam -> bounded latest-frame buffer -> local person detector -> temporary IoU tracks -> structured observations
```

It makes zero SENTRY Codex/Luna calls. It does not perform identity recognition, persistence, sessions, entry/exit semantics, raw-frame storage, or a local API.

## Selected stack

The current implementation uses Intel Open Model Zoo `person-detection-0202` through the official OpenVINO Python Runtime and a small SENTRY-owned two-stage IoU tracker. The tracker is unchanged from the HOG qualification.

- `openvino==2026.3.1`, Apache-2.0, used for local CPU inference of the externally downloaded IR model.
- `opencv-python-headless==4.12.0.88`, used for camera and image handling.
- `psutil==7.0.0`, BSD-3-Clause, used only for process metrics.
- `person-detection-0202` is the official Open Model Zoo FP32 XML/BIN artifact. Its manifest-provided SHA-384 checksums are recorded in Authority and the files remain outside Git under `perception-data/models/person-detection-0202/FP32/`.
- The tracker is original SENTRY code. It keeps a bounded track table, associates high-confidence detections before lower-confidence detections, and retains unmatched tracks for a configured short dropout window.

YOLOX plus ByteTrack was evaluated first because YOLOX is Apache-2.0 and ByteTrack is MIT, and both are viable future options. It was not adopted for this first live attempt because the host had no Python/CV runtime, the YOLOX deployment path requires a separately sourced model artifact, and adding a PyTorch/ONNX stack before proving camera access would increase the installation and provenance surface. The detector interface is replaceable so a later benchmark can compare YOLOX-Nano or another permissive model on the same observation contract.

The selected runtime device is CPU. The host exposes other devices, but CPU keeps this first qualification deterministic and does not add a GPU-specific runtime.

## Configuration and operation

Install the pinned requirements into a local Python environment, then run:

```text
python -m perception.sentry_perception --config perception/config.example.json --duration-seconds 600 --observation-file perception-observations.jsonl
```

The observation file contains structured metadata only. It is not a video or image archive. Local observation files, logs, model weights, captures, and runtime data must stay outside Git.

The service requests the configured resolution/FPS, records the actual camera values, uses a size-one latest-frame buffer, drops stale frames, releases the camera on shutdown, and emits `offline` or `degraded` health rather than treating camera failure as an empty room.

## Evidence boundary

Automated tracker/configuration/contract tests can establish deterministic behavior. M1 acceptance additionally requires live Windows evidence from the actual office webcam, including visible-person detection, multiple people, short dropout, recovery, useful processed FPS, latency, resource measurements, and a ten-minute run. If the device cannot be opened, the live portion is `BLOCKED/NOT RUN`; synthetic frames must not be substituted for that claim.

## External sources reviewed

- [YOLOX repository and Apache-2.0 license](https://github.com/Megvii-BaseDetection/YOLOX)
- [ByteTrack repository and MIT license](https://github.com/FoundationVision/ByteTrack)
- [ONNX Runtime execution providers](https://onnxruntime.ai/docs/execution-providers/)
- [OpenVINO Python installation](https://docs.openvino.ai/2025/get-started/install-openvino/install-openvino-pip.html)
- [OpenVINO repository and Apache-2.0 license](https://github.com/openvinotoolkit/openvino)
- [Open Model Zoo person-detection-0202 README](https://github.com/openvinotoolkit/open_model_zoo/blob/master/models/intel/person-detection-0202/README.md)
