# Evidence

Date: 2026-08-24

## Host

- Windows x64 ASUS desktop, 68,605,759,488 bytes RAM.
- NVIDIA GeForce RTX 3050 and GTX 1660 SUPER, driver `32.0.15.9579`, status OK.
- PnP camera: `NexiGo N60 FHD Webcam`, Microsoft driver `10.0.26100.8972`, PnP status reported `Unknown`.
- System Python was unavailable. A local temporary Python 3.12.13 virtual environment was created outside the repository and installed from the pinned requirements.

## External investigation

- YOLOX upstream reviewed: Apache-2.0, ONNX deployment documented, separate pretrained artifacts required.
- ByteTrack upstream reviewed: MIT, detector-agnostic association method.
- ONNX Runtime execution providers reviewed: CPU, CUDA, DirectML, and others supported through the EP abstraction.
- OpenCV upstream reviewed: OpenCV 4.5+ Apache-2.0; HOG people detector API and bundled default people detector reviewed.
- Disposition: ADOPT OpenCV HOG plus SENTRY-owned IoU tracker for the smallest first live slice; REFERENCE YOLOX plus ByteTrack for a later measured benchmark.

## Automated validation

- Python compilation: PASSED.
- `python -m unittest discover -s tests -v`: PASSED, 5 tests.
- Configuration and camera buffer bound: PASSED.
- Detector output contract: PASSED on a local blank frame.
- Multiple tracks and stable IDs: PASSED.
- Brief detector dropout retention: PASSED.
- Structured observation contract: PASSED.
- Unavailable-camera CLI behavior: PASSED. It returned structured `degraded` startup and `offline / camera_open_failed`, exit code 3, and `codex_luna_calls: 0`.

## Live Windows validation

- OpenCV 4.12.0 attempted camera index 0 with Any, Media Foundation, and DirectShow. All three failed to open; no frame, resolution, FPS, detection, tracking, recovery, or 10-minute soak evidence exists.
- Live M1 criteria: BLOCKED/NOT RUN because the actual office webcam was inaccessible.
- No synthetic frame result is being promoted to live evidence.
