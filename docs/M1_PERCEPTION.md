# M1 local perception

M1 is an observation-only Windows service:

```text
webcam -> bounded latest-frame buffer -> local person detector -> temporary IoU tracks -> structured observations
```

It makes zero SENTRY Codex/Luna calls. It does not perform identity recognition, persistence, sessions, entry/exit semantics, raw-frame storage, or a local API.

## Selected stack

The first implementation uses OpenCV's built-in HOG people detector and a small SENTRY-owned two-stage IoU tracker.

- `opencv-python-headless==4.12.0.88`, OpenCV 4.5+ Apache-2.0. The HOG detector's classifier coefficients are bundled with OpenCV, so M1 does not download or commit a separate model-weight file.
- `psutil==7.0.0`, BSD-3-Clause, used only for process metrics.
- The tracker is original SENTRY code. It keeps a bounded track table, associates high-confidence detections before lower-confidence detections, and retains unmatched tracks for a configured short dropout window.

YOLOX plus ByteTrack was evaluated first because YOLOX is Apache-2.0 and ByteTrack is MIT, and both are viable future options. It was not adopted for this first live attempt because the host had no Python/CV runtime, the YOLOX deployment path requires a separately sourced model artifact, and adding a PyTorch/ONNX stack before proving camera access would increase the installation and provenance surface. The detector interface is replaceable so a later benchmark can compare YOLOX-Nano or another permissive model on the same observation contract.

The selected runtime is CPU. The host has NVIDIA GPUs, but the chosen HOG implementation is CPU-only; this avoids an unverified CUDA/TensorRT dependency while retaining an explicit future detector swap point.

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
- [OpenCV license](https://opencv.org/license/)
- [OpenCV HOGDescriptor API](https://docs.opencv.org/4.x/d5/d33/structcv_1_1HOGDescriptor.html)
