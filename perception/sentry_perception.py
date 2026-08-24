"""Bounded, local Windows webcam perception for SENTRY M1.

The implementation deliberately stops at observations. It does not identify
people, create presence sessions, persist frames, emit semantic entry/exit
events, or call Codex/Luna.
"""

from __future__ import annotations

import argparse
import json
import math
import signal
import statistics
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Protocol


class CameraState(str, Enum):
    ONLINE = "online"
    DEGRADED = "degraded"
    OFFLINE = "offline"


@dataclass(frozen=True)
class Detection:
    """A local person detection in x1, y1, x2, y2 pixel coordinates."""

    bbox: tuple[float, float, float, float]
    confidence: float


@dataclass
class _Track:
    track_id: int
    bbox: tuple[float, float, float, float]
    confidence: float
    hits: int = 1
    age: int = 1
    missed_frames: int = 0
    visible: bool = True
    velocity: tuple[float, float] = (0.0, 0.0)

    def predicted_bbox(self) -> tuple[float, float, float, float]:
        dx, dy = self.velocity
        return tuple(value + (dx if index % 2 == 0 else dy) for index, value in enumerate(self.bbox))  # type: ignore[return-value]


def _iou(left: tuple[float, float, float, float], right: tuple[float, float, float, float]) -> float:
    x1 = max(left[0], right[0])
    y1 = max(left[1], right[1])
    x2 = min(left[2], right[2])
    y2 = min(left[3], right[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    if intersection == 0:
        return 0.0
    left_area = max(0.0, left[2] - left[0]) * max(0.0, left[3] - left[1])
    right_area = max(0.0, right[2] - right[0]) * max(0.0, right[3] - right[1])
    union = left_area + right_area - intersection
    return intersection / union if union else 0.0


class IoUTracker:
    """Small two-stage IoU tracker with bounded dropout retention.

    This is intentionally a narrow SENTRY-owned tracker, not a vendored
    ByteTrack implementation. High-confidence detections associate first,
    lower-confidence detections can recover existing tracks, and unmatched
    tracks remain visible as predicted observations for a bounded gap.
    """

    def __init__(
        self,
        *,
        match_iou_threshold: float = 0.30,
        high_confidence_threshold: float = 0.55,
        new_track_confidence_threshold: float = 0.50,
        max_missing_frames: int = 12,
    ) -> None:
        if not 0 <= match_iou_threshold <= 1:
            raise ValueError("match_iou_threshold must be between 0 and 1")
        if not 0 <= high_confidence_threshold <= 1:
            raise ValueError("high_confidence_threshold must be between 0 and 1")
        if not 0 <= new_track_confidence_threshold <= 1:
            raise ValueError("new_track_confidence_threshold must be between 0 and 1")
        if max_missing_frames < 0:
            raise ValueError("max_missing_frames must be non-negative")
        self.match_iou_threshold = match_iou_threshold
        self.high_confidence_threshold = high_confidence_threshold
        self.new_track_confidence_threshold = new_track_confidence_threshold
        self.max_missing_frames = max_missing_frames
        self._tracks: dict[int, _Track] = {}
        self._next_id = 1

    @staticmethod
    def _associate(
        tracks: list[_Track], detections: list[Detection], threshold: float
    ) -> tuple[list[tuple[_Track, Detection]], list[_Track], list[Detection]]:
        candidates = sorted(
            (
                (score, track, detection)
                for track in tracks
                for detection in detections
                if (score := _iou(track.predicted_bbox(), detection.bbox)) >= threshold
            ),
            key=lambda item: item[0],
            reverse=True,
        )
        matched_tracks: set[int] = set()
        matched_detections: set[int] = set()
        matches: list[tuple[_Track, Detection]] = []
        for _, track, detection in candidates:
            detection_index = detections.index(detection)
            if track.track_id in matched_tracks or detection_index in matched_detections:
                continue
            matched_tracks.add(track.track_id)
            matched_detections.add(detection_index)
            matches.append((track, detection))
        unmatched_tracks = [track for track in tracks if track.track_id not in matched_tracks]
        unmatched_detections = [detection for index, detection in enumerate(detections) if index not in matched_detections]
        return matches, unmatched_tracks, unmatched_detections

    def update(self, detections: list[Detection]) -> list[dict[str, Any]]:
        for track in self._tracks.values():
            track.age += 1

        active_tracks = list(self._tracks.values())
        high = [detection for detection in detections if detection.confidence >= self.high_confidence_threshold]
        low = [detection for detection in detections if detection.confidence < self.high_confidence_threshold]
        matches, unmatched_tracks, unmatched_detections = self._associate(active_tracks, high, self.match_iou_threshold)
        low_matches, unmatched_tracks, unmatched_low = self._associate(unmatched_tracks, low, self.match_iou_threshold)
        matches.extend(low_matches)
        unmatched_detections.extend(unmatched_low)

        for track, detection in matches:
            old_center = ((track.bbox[0] + track.bbox[2]) / 2, (track.bbox[1] + track.bbox[3]) / 2)
            new_center = ((detection.bbox[0] + detection.bbox[2]) / 2, (detection.bbox[1] + detection.bbox[3]) / 2)
            track.velocity = (new_center[0] - old_center[0], new_center[1] - old_center[1])
            track.bbox = detection.bbox
            track.confidence = detection.confidence
            track.hits += 1
            track.missed_frames = 0
            track.visible = True

        for track in unmatched_tracks:
            track.bbox = track.predicted_bbox()
            track.missed_frames += 1
            track.visible = False

        for detection in unmatched_detections:
            if detection.confidence < self.new_track_confidence_threshold:
                continue
            track = _Track(self._next_id, detection.bbox, detection.confidence)
            self._tracks[track.track_id] = track
            self._next_id += 1

        self._tracks = {
            track_id: track
            for track_id, track in self._tracks.items()
            if track.missed_frames <= self.max_missing_frames
        }
        return [
            {
                "track_id": track.track_id,
                "confidence": round(max(0.0, min(1.0, track.confidence)), 4),
                "bbox": [round(value, 2) for value in track.bbox],
                "visible": track.visible,
                "missed_frames": track.missed_frames,
            }
            for track in sorted(self._tracks.values(), key=lambda item: item.track_id)
        ]


@dataclass
class _Frame:
    sequence: int
    captured_at: datetime
    image: Any


class LatestFrameBuffer:
    """Thread-safe size-one buffer that drops stale frames instead of queuing."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latest: _Frame | None = None
        self._sequence = 0
        self.dropped_frames = 0

    def push(self, image: Any, captured_at: datetime | None = None) -> int:
        with self._lock:
            self._sequence += 1
            if self._latest is not None:
                self.dropped_frames += 1
            self._latest = _Frame(self._sequence, captured_at or datetime.now(timezone.utc), image)
            return self._sequence

    def pop_latest(self) -> _Frame | None:
        with self._lock:
            frame = self._latest
            self._latest = None
            return frame


class Detector(Protocol):
    def detect(self, image: Any) -> list[Detection]: ...


class OpenCVHogDetector:
    """Local person-only detector using OpenCV's bundled HOG SVM."""

    def __init__(self, config: dict[str, Any]) -> None:
        try:
            import cv2
        except ImportError as exc:  # pragma: no cover - depends on runtime install
            raise RuntimeError("opencv-python-headless is required for the HOG detector") from exc
        self._cv2 = cv2
        self.frame_scale = float(config.get("frame_scale", 0.5))
        self.confidence_threshold = float(config.get("confidence_threshold", 0.50))
        self.win_stride = tuple(int(value) for value in config.get("win_stride", [8, 8]))
        self.padding = tuple(int(value) for value in config.get("padding", [8, 8]))
        self.scale = float(config.get("scale", 1.05))
        self.group_threshold = int(config.get("group_threshold", 2))
        if not 0 < self.frame_scale <= 1:
            raise ValueError("detector.frame_scale must be greater than 0 and no greater than 1")
        self._hog = cv2.HOGDescriptor()
        self._hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    @staticmethod
    def _confidence(weight: float) -> float:
        return 1.0 / (1.0 + math.exp(-float(weight)))

    def detect(self, image: Any) -> list[Detection]:
        height, width = image.shape[:2]
        if self.frame_scale != 1:
            resized = self._cv2.resize(image, (int(width * self.frame_scale), int(height * self.frame_scale)))
        else:
            resized = image
        boxes, weights = self._hog.detectMultiScale(
            resized,
            hitThreshold=0.0,
            winStride=self.win_stride,
            padding=self.padding,
            scale=self.scale,
            groupThreshold=self.group_threshold,
        )
        detections: list[Detection] = []
        for box, weight in zip(boxes, weights):
            confidence = self._confidence(float(weight))
            if confidence < self.confidence_threshold:
                continue
            x, y, box_width, box_height = (float(value) / self.frame_scale for value in box)
            detections.append(Detection((x, y, x + box_width, y + box_height), confidence))
        return detections


@dataclass
class Observation:
    camera_state: CameraState
    captured_at: str
    frame_sequence: int
    people: list[dict[str, Any]]
    processing_ms: float
    health_reason: str | None = None
    dropped_frames: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "camera_state": self.camera_state.value,
            "captured_at": self.captured_at,
            "frame_sequence": self.frame_sequence,
            "people": self.people,
            "processing_ms": round(self.processing_ms, 3),
            "health_reason": self.health_reason,
            "dropped_frames": self.dropped_frames,
        }


class PerceptionEngine:
    """Converts one local frame into one structured observation."""

    def __init__(self, detector: Detector, tracker: IoUTracker) -> None:
        self.detector = detector
        self.tracker = tracker

    def process(
        self,
        image: Any,
        *,
        frame_sequence: int,
        captured_at: datetime,
        dropped_frames: int = 0,
    ) -> Observation:
        started = time.perf_counter()
        detections = self.detector.detect(image)
        people = self.tracker.update(detections)
        return Observation(
            camera_state=CameraState.ONLINE,
            captured_at=captured_at.astimezone(timezone.utc).isoformat(),
            frame_sequence=frame_sequence,
            people=people,
            processing_ms=(time.perf_counter() - started) * 1000,
            dropped_frames=dropped_frames,
        )


def validate_config(config: dict[str, Any]) -> None:
    camera = config.get("camera")
    detector = config.get("detector")
    tracker = config.get("tracker")
    if not isinstance(camera, dict) or not isinstance(detector, dict) or not isinstance(tracker, dict):
        raise ValueError("config must contain camera, detector, and tracker objects")
    if int(camera.get("index", -1)) < 0:
        raise ValueError("camera.index must be non-negative")
    if camera.get("backend", "auto") not in {"auto", "dshow", "msmf", "any"}:
        raise ValueError("camera.backend must be auto, dshow, msmf, or any")
    for key in ("width", "height", "fps", "buffer_size"):
        if float(camera.get(key, 0)) <= 0:
            raise ValueError(f"camera.{key} must be positive")
    if int(camera.get("buffer_size", 1)) != 1:
        raise ValueError("camera.buffer_size must remain 1 to enforce latest-frame behavior")
    if detector.get("name") != "opencv_hog":
        raise ValueError("only the explicitly selected opencv_hog detector is implemented")
    if not 0 <= float(detector.get("confidence_threshold", 0.5)) <= 1:
        raise ValueError("detector.confidence_threshold must be between 0 and 1")
    if int(tracker.get("max_missing_frames", 0)) < 0:
        raise ValueError("tracker.max_missing_frames must be non-negative")


def load_config(path: Path) -> dict[str, Any]:
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to load config: {exc}") from exc
    if not isinstance(config, dict):
        raise ValueError("config must be a JSON object")
    validate_config(config)
    return config


class _CameraWorker:
    def __init__(self, config: dict[str, Any], buffer: LatestFrameBuffer) -> None:
        self.config = config
        self.buffer = buffer
        self.state = CameraState.DEGRADED
        self.reason = "camera_starting"
        self.backend_name = "unknown"
        self.actual_width = 0.0
        self.actual_height = 0.0
        self.actual_fps = 0.0
        self.frames_captured = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._capture: Any = None

    def _set_state(self, state: CameraState, reason: str) -> None:
        with self._lock:
            self.state = state
            self.reason = reason

    def snapshot(self) -> tuple[CameraState, str, str, float, float, float, int]:
        with self._lock:
            return (self.state, self.reason, self.backend_name, self.actual_width, self.actual_height, self.actual_fps, self.frames_captured)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="sentry-camera", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3)
        if self._capture is not None:
            self._capture.release()

    def _run(self) -> None:  # pragma: no cover - exercised by live/CLI tests
        try:
            import cv2
        except ImportError:
            self._set_state(CameraState.OFFLINE, "opencv_not_installed")
            return
        camera = self.config["camera"]
        backend_names = [camera["backend"]] if camera["backend"] != "auto" else ["dshow", "msmf", "any"]
        backend_values = {"dshow": cv2.CAP_DSHOW, "msmf": cv2.CAP_MSMF, "any": cv2.CAP_ANY}
        capture = None
        for backend_name in backend_names:
            candidate = cv2.VideoCapture(int(camera["index"]), backend_values[backend_name])
            if candidate.isOpened():
                capture = candidate
                self.backend_name = backend_name
                break
            candidate.release()
        if capture is None:
            self._set_state(CameraState.OFFLINE, "camera_open_failed")
            return
        self._capture = capture
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, int(camera["width"]))
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, int(camera["height"]))
        capture.set(cv2.CAP_PROP_FPS, float(camera["fps"]))
        self.actual_width = capture.get(cv2.CAP_PROP_FRAME_WIDTH)
        self.actual_height = capture.get(cv2.CAP_PROP_FRAME_HEIGHT)
        self.actual_fps = capture.get(cv2.CAP_PROP_FPS)
        failures = 0
        failure_limit = int(camera.get("read_failure_limit", 5))
        self._set_state(CameraState.ONLINE, "camera_opened")
        while not self._stop.is_set():
            ok, image = capture.read()
            if not ok or image is None:
                failures += 1
                self._set_state(CameraState.OFFLINE if failures >= failure_limit else CameraState.DEGRADED, "camera_read_failed")
                time.sleep(0.05)
                continue
            failures = 0
            self.frames_captured += 1
            self._set_state(CameraState.ONLINE, "frame_received")
            self.buffer.push(image)


class PerceptionService:
    def __init__(self, config: dict[str, Any], observation_callback: Callable[[Observation], None] | None = None) -> None:
        validate_config(config)
        self.config = config
        self.buffer = LatestFrameBuffer()
        self.engine = PerceptionEngine(
            OpenCVHogDetector(config["detector"]),
            IoUTracker(**{
                "match_iou_threshold": config["tracker"]["match_iou_threshold"],
                "high_confidence_threshold": config["tracker"]["high_confidence_threshold"],
                "new_track_confidence_threshold": config["tracker"]["new_track_confidence_threshold"],
                "max_missing_frames": config["tracker"]["max_missing_frames"],
            }),
        )
        self.observation_callback = observation_callback
        self.worker = _CameraWorker(config, self.buffer)
        self._stop = threading.Event()
        self._last_sequence = 0
        self._processing_ms: list[float] = []
        self._started_at = 0.0

    def stop(self) -> None:
        self._stop.set()
        self.worker.stop()

    def run(self, duration_seconds: float | None = None) -> dict[str, Any]:  # pragma: no cover - exercised by live/CLI tests
        self._started_at = time.perf_counter()
        self.worker.start()
        deadline = self._started_at + duration_seconds if duration_seconds is not None else None
        last_health_emit = 0.0
        try:
            while not self._stop.is_set() and (deadline is None or time.perf_counter() < deadline):
                frame = self.buffer.pop_latest()
                if frame is None:
                    now = time.perf_counter()
                    state, reason, *_ = self.worker.snapshot()
                    if state != CameraState.ONLINE and now - last_health_emit >= 1.0:
                        observation = Observation(state, datetime.now(timezone.utc).isoformat(), self._last_sequence, [], 0.0, reason, self.buffer.dropped_frames)
                        if self.observation_callback:
                            self.observation_callback(observation)
                        last_health_emit = now
                    time.sleep(0.01)
                    continue
                self._last_sequence = frame.sequence
                state, reason, *_ = self.worker.snapshot()
                if state != CameraState.ONLINE:
                    observation = Observation(state, frame.captured_at.isoformat(), frame.sequence, [], 0.0, reason, self.buffer.dropped_frames)
                else:
                    try:
                        observation = self.engine.process(frame.image, frame_sequence=frame.sequence, captured_at=frame.captured_at, dropped_frames=self.buffer.dropped_frames)
                    except Exception as exc:
                        observation = Observation(CameraState.DEGRADED, frame.captured_at.isoformat(), frame.sequence, [], 0.0, f"detector_failed:{type(exc).__name__}", self.buffer.dropped_frames)
                self._processing_ms.append(observation.processing_ms)
                if self.observation_callback:
                    self.observation_callback(observation)
        finally:
            self.stop()
        return self.summary()

    def summary(self) -> dict[str, Any]:
        state, reason, backend, width, height, fps, captured = self.worker.snapshot()
        elapsed = max(0.001, time.perf_counter() - self._started_at) if self._started_at else 0.0
        processed = len(self._processing_ms)
        values = sorted(self._processing_ms)
        p95 = values[min(len(values) - 1, max(0, math.ceil(len(values) * 0.95) - 1))] if values else 0.0
        return {
            "camera_state": state.value,
            "health_reason": reason,
            "backend": backend,
            "actual_resolution": [width, height],
            "actual_camera_fps": fps,
            "frames_captured": captured,
            "frames_processed": processed,
            "processed_fps": round(processed / elapsed, 3) if elapsed else 0.0,
            "median_processing_ms": round(statistics.median(values), 3) if values else 0.0,
            "p95_processing_ms": round(p95, 3),
            "dropped_frames": self.buffer.dropped_frames,
            "codex_luna_calls": 0,
        }


def _system_snapshot() -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    try:
        import psutil

        process = psutil.Process()
        snapshot["process_rss_bytes"] = process.memory_info().rss
        snapshot["cpu_percent"] = process.cpu_percent(interval=0.1)
    except ImportError:
        snapshot["metrics"] = "psutil_not_installed"
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        snapshot["gpu"] = result.stdout.strip().splitlines() if result.returncode == 0 else "unavailable"
    except (OSError, subprocess.TimeoutExpired):
        snapshot["gpu"] = "unavailable"
    return snapshot


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI exercised separately
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.example.json"))
    parser.add_argument("--duration-seconds", type=float, default=None)
    parser.add_argument("--observation-file", type=Path)
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 2
    output = args.observation_file.open("w", encoding="utf-8") if args.observation_file else None
    def emit(observation: Observation) -> None:
        if output:
            output.write(json.dumps(observation.as_dict(), sort_keys=True) + "\n")
            output.flush()
    service = PerceptionService(config, emit)
    signal.signal(signal.SIGINT, lambda *_: service.stop())
    signal.signal(signal.SIGTERM, lambda *_: service.stop())
    before = _system_snapshot()
    try:
        summary = service.run(args.duration_seconds)
    finally:
        if output:
            output.close()
    summary["metrics_start"] = before
    summary["metrics_end"] = _system_snapshot()
    print(json.dumps({"ok": summary["camera_state"] != CameraState.OFFLINE.value, "summary": summary}, sort_keys=True))
    return 0 if summary["camera_state"] != CameraState.OFFLINE.value else 3


if __name__ == "__main__":
    raise SystemExit(main())
