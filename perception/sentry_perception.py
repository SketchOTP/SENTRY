"""Bounded, local webcam perception and metadata persistence for SENTRY.

The continuous path remains local and metadata-only. It does not identify
people, persist frames, or call Codex/Luna. When configured, structured room
state transitions are recorded by the separate M2 presence store.
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

from .presence_state import (
    PresenceStateConfig,
    PresenceStateMachine,
    PresenceStateSnapshot,
    RoomState,
    measure_image_quality,
)
from .presence_store import PresenceStore


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


class OpenVINOPersonDetector:
    """Local person detector backed by the Open Model Zoo IR model."""

    def __init__(self, config: dict[str, Any]) -> None:
        try:
            import numpy as np
            from openvino import Core
        except ImportError as exc:  # pragma: no cover - depends on runtime install
            raise RuntimeError("openvino is required for the person-detection-0202 detector") from exc
        self._np = np
        self.confidence_threshold = float(config.get("confidence_threshold", 0.50))
        self.model_xml = Path(config.get("model_xml", ""))
        self.model_bin = Path(config.get("model_bin", ""))
        self.device = str(config.get("device", "CPU"))
        if not self.model_xml.is_file():
            raise RuntimeError(f"model XML file not found: {self.model_xml}")
        if not self.model_bin.is_file():
            raise RuntimeError(f"model BIN file not found: {self.model_bin}")
        try:
            core = Core()
            model = core.read_model(str(self.model_xml), str(self.model_bin))
            outputs = list(model.outputs)
            if len(outputs) != 1 or list(outputs[0].shape) != [1, 1, 200, 7]:
                raise ValueError(f"expected one output shaped [1, 1, N, 7], got {[list(output.shape) for output in outputs]}")
            input_shape = list(model.inputs[0].shape)
            if input_shape != [1, 3, 512, 512]:
                raise ValueError(f"expected input shape [1, 3, 512, 512], got {input_shape}")
            self._compiled_model = core.compile_model(model, self.device)
            self._input_name = model.inputs[0].any_name
            self._request = self._compiled_model.create_infer_request()
        except Exception as exc:
            raise RuntimeError(f"unable to load or compile OpenVINO model: {exc}") from exc

    @staticmethod
    def _decode_detections(output: Any, width: int, height: int, confidence_threshold: float) -> list[Detection]:
        detections: list[Detection] = []
        for image_id, label, confidence, x_min, y_min, x_max, y_max in output[0, 0]:
            if image_id < 0 or int(label) != 0 or float(confidence) < confidence_threshold:
                continue
            left = max(0.0, min(float(width), float(x_min) * width))
            top = max(0.0, min(float(height), float(y_min) * height))
            right = max(0.0, min(float(width), float(x_max) * width))
            bottom = max(0.0, min(float(height), float(y_max) * height))
            if right <= left or bottom <= top:
                continue
            detections.append(Detection((left, top, right, bottom), float(confidence)))
        return detections

    def _infer(self, image: Any) -> tuple[Any, int, int]:
        height, width = image.shape[:2]
        if len(image.shape) != 3 or image.shape[2] != 3:
            raise ValueError("detector expects a BGR image with three channels")
        import cv2

        resized = cv2.resize(image, (512, 512))
        tensor = self._np.asarray(resized, dtype=self._np.float32).transpose(2, 0, 1)[self._np.newaxis, ...]
        result = self._request.infer({self._input_name: tensor})
        output = next(iter(result.values()))
        if tuple(output.shape) != (1, 1, 200, 7):
            raise RuntimeError(f"unexpected detector output shape: {tuple(output.shape)}")
        return output, width, height

    def detect_raw(self, image: Any) -> list[Detection]:
        """Decode positive person candidates before the production cutoff.

        This is metadata-only and performs exactly one inference. The returned
        candidates are intended for threshold calibration or evidence policy;
        callers must choose the production subset explicitly.
        """

        output, width, height = self._infer(image)
        return self._decode_detections(output, width, height, 1e-12)

    def detect(self, image: Any) -> list[Detection]:
        output, width, height = self._infer(image)
        return self._decode_detections(output, width, height, self.confidence_threshold)


def yolox_preprocess(image: Any, input_size: tuple[int, int] = (640, 640)) -> tuple[Any, float]:
    """Apply the official YOLOX validation preprocessing.

    YOLOX uses aspect-preserving resize into a top-left anchored 114-padded
    canvas, then CHW float32 conversion.  The ratio is retained for restoring
    predictions to the original camera coordinate system.
    """

    import cv2
    import numpy as np

    if len(image.shape) != 3 or image.shape[2] != 3:
        raise ValueError("YOLOX detector expects a BGR image with three channels")
    height, width = image.shape[:2]
    if height <= 0 or width <= 0:
        raise ValueError("YOLOX detector expects a non-empty image")
    target_height, target_width = input_size
    ratio = min(target_height / height, target_width / width)
    resized = cv2.resize(
        image,
        (int(width * ratio), int(height * ratio)),
        interpolation=cv2.INTER_LINEAR,
    ).astype(np.uint8)
    padded = np.ones((target_height, target_width, 3), dtype=np.uint8) * 114
    padded[: resized.shape[0], : resized.shape[1]] = resized
    tensor = np.ascontiguousarray(padded.transpose(2, 0, 1), dtype=np.float32)
    return tensor, ratio


def _yolox_decode_arrays(
    output: Any,
    *,
    width: int,
    height: int,
    ratio: float,
    input_size: tuple[int, int] = (640, 640),
) -> tuple[Any, Any]:
    """Decode YOLOX grid coordinates and restore boxes to image pixels."""

    import numpy as np

    values = np.asarray(output)
    expected_rows = sum((input_size[0] // stride) * (input_size[1] // stride) for stride in (8, 16, 32))
    if values.shape != (1, expected_rows, 85):
        raise ValueError(f"expected YOLOX output shape (1, {expected_rows}, 85), got {tuple(values.shape)}")
    if ratio <= 0:
        raise ValueError("YOLOX preprocessing ratio must be positive")

    decoded = values[0].astype(np.float32, copy=True)
    grids: list[Any] = []
    strides: list[Any] = []
    for stride in (8, 16, 32):
        grid_y, grid_x = np.meshgrid(
            np.arange(input_size[0] // stride),
            np.arange(input_size[1] // stride),
            indexing="ij",
        )
        grids.append(np.stack((grid_x, grid_y), axis=-1).reshape(-1, 2))
        strides.append(np.full((grid_x.size, 1), stride, dtype=np.float32))
    grid = np.concatenate(grids, axis=0)
    expanded_stride = np.concatenate(strides, axis=0)
    decoded[:, :2] = (decoded[:, :2] + grid) * expanded_stride
    decoded[:, 2:4] = np.exp(decoded[:, 2:4]) * expanded_stride

    boxes = np.empty_like(decoded[:, :4])
    boxes[:, 0] = decoded[:, 0] - decoded[:, 2] / 2
    boxes[:, 1] = decoded[:, 1] - decoded[:, 3] / 2
    boxes[:, 2] = decoded[:, 0] + decoded[:, 2] / 2
    boxes[:, 3] = decoded[:, 1] + decoded[:, 3] / 2
    boxes /= ratio
    boxes[:, 0::2] = np.clip(boxes[:, 0::2], 0, width)
    boxes[:, 1::2] = np.clip(boxes[:, 1::2], 0, height)

    return decoded, boxes


def _yolox_nms_indices(boxes: Any, scores: Any, nms_threshold: float) -> list[int]:
    import numpy as np

    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size:
        index = int(order[0])
        keep.append(index)
        if order.size == 1:
            break
        current = boxes[index]
        remainder = boxes[order[1:]]
        left = np.maximum(current[0], remainder[:, 0])
        top = np.maximum(current[1], remainder[:, 1])
        right = np.minimum(current[2], remainder[:, 2])
        bottom = np.minimum(current[3], remainder[:, 3])
        intersection = np.maximum(0, right - left) * np.maximum(0, bottom - top)
        current_area = max(0.0, current[2] - current[0]) * max(0.0, current[3] - current[1])
        remainder_area = np.maximum(0, remainder[:, 2] - remainder[:, 0]) * np.maximum(0, remainder[:, 3] - remainder[:, 1])
        union = current_area + remainder_area - intersection
        overlap = np.divide(intersection, union, out=np.zeros_like(intersection), where=union > 0)
        order = order[1:][overlap <= nms_threshold]
    return keep


def yolox_decode_reference_output(
    output: Any,
    *,
    width: int,
    height: int,
    ratio: float,
    confidence_threshold: float,
    nms_threshold: float = 0.45,
    input_size: tuple[int, int] = (640, 640),
) -> list[dict[str, Any]]:
    """Return official YOLOX final-class candidates with NMS diagnostics.

    This mirrors the upstream ONNX/PyTorch path: select the winning class
    from all class probabilities, score it with objectness, then apply
    class-agnostic NMS.  Rows suppressed by NMS are retained as metadata for
    parity diagnostics; only rows marked ``nms_kept`` are final detections.
    """

    import numpy as np

    if not 0 <= confidence_threshold <= 1:
        raise ValueError("YOLOX confidence_threshold must be between 0 and 1")
    if not 0 <= nms_threshold <= 1:
        raise ValueError("YOLOX nms_threshold must be between 0 and 1")
    decoded, boxes = _yolox_decode_arrays(
        output, width=width, height=height, ratio=ratio, input_size=input_size
    )
    class_probabilities = decoded[:, 5:]
    top_class_ids = class_probabilities.argmax(axis=1)
    top_class_probabilities = class_probabilities[
        np.arange(len(top_class_ids)), top_class_ids
    ]
    scores = decoded[:, 4] * top_class_probabilities
    valid = (
        np.isfinite(decoded[:, 4])
        & np.isfinite(top_class_probabilities)
        & np.isfinite(scores)
        & (scores > confidence_threshold)
        & (boxes[:, 2] > boxes[:, 0])
        & (boxes[:, 3] > boxes[:, 1])
    )
    candidate_indices = np.flatnonzero(valid)
    if candidate_indices.size == 0:
        return []
    valid_boxes = boxes[candidate_indices]
    valid_scores = scores[candidate_indices]
    keep = set(_yolox_nms_indices(valid_boxes, valid_scores, nms_threshold))
    rows: list[dict[str, Any]] = []
    for local_index, source_index in enumerate(candidate_indices):
        rows.append(
            {
                "source_index": int(source_index),
                "final_class_id": int(top_class_ids[source_index]),
                "objectness": float(decoded[source_index, 4]),
                "person_probability": float(decoded[source_index, 5]),
                "top_class_probability": float(top_class_probabilities[source_index]),
                "top_class_id": int(top_class_ids[source_index]),
                "final_score": float(scores[source_index]),
                "bbox": [float(value) for value in boxes[source_index]],
                "nms_kept": local_index in keep,
            }
        )
    return rows


def yolox_decode_output(
    output: Any,
    *,
    width: int,
    height: int,
    ratio: float,
    confidence_threshold: float,
    nms_threshold: float = 0.45,
    input_size: tuple[int, int] = (640, 640),
) -> list[Detection]:
    """Decode official YOLOX output and retain final-class COCO person detections."""

    rows = yolox_decode_reference_output(
        output,
        width=width,
        height=height,
        ratio=ratio,
        confidence_threshold=confidence_threshold,
        nms_threshold=nms_threshold,
        input_size=input_size,
    )
    return [
        Detection(tuple(row["bbox"]), row["final_score"])
        for row in rows
        if row["nms_kept"] and row["final_class_id"] == 0
    ]


class OpenVINOYOLOXSPersonDetector:
    """YOLOX-S detector using the official OpenVINO IR export."""

    def __init__(self, config: dict[str, Any]) -> None:
        try:
            import numpy as np
            from openvino import Core
        except ImportError as exc:  # pragma: no cover - depends on runtime install
            raise RuntimeError("openvino is required for the YOLOX-S detector") from exc
        self._np = np
        self.confidence_threshold = float(config.get("confidence_threshold", 0.25))
        self.nms_threshold = float(config.get("nms_threshold", 0.45))
        self.model_xml = Path(config.get("model_xml", ""))
        self.model_bin = Path(config.get("model_bin", ""))
        self.device = str(config.get("device", "CPU"))
        if not self.model_xml.is_file():
            raise RuntimeError(f"model XML file not found: {self.model_xml}")
        if not self.model_bin.is_file():
            raise RuntimeError(f"model BIN file not found: {self.model_bin}")
        try:
            core = Core()
            model = core.read_model(str(self.model_xml), str(self.model_bin))
            inputs = list(model.inputs)
            outputs = list(model.outputs)
            if len(inputs) != 1 or list(inputs[0].shape) != [1, 3, 640, 640]:
                raise ValueError(f"expected one input shaped [1, 3, 640, 640], got {[list(item.shape) for item in inputs]}")
            if len(outputs) != 1 or list(outputs[0].shape) != [1, 8400, 85]:
                raise ValueError(f"expected one output shaped [1, 8400, 85], got {[list(item.shape) for item in outputs]}")
            self._compiled_model = core.compile_model(model, self.device)
            self._input_name = inputs[0].any_name
            self._request = self._compiled_model.create_infer_request()
        except Exception as exc:
            raise RuntimeError(f"unable to load or compile YOLOX-S OpenVINO model: {exc}") from exc

    def _infer(self, image: Any) -> tuple[Any, float, int, int]:
        height, width = image.shape[:2]
        tensor, ratio = yolox_preprocess(image)
        result = self._request.infer({self._input_name: tensor[self._np.newaxis, ...]})
        output = next(iter(result.values()))
        if tuple(output.shape) != (1, 8400, 85):
            raise RuntimeError(f"unexpected YOLOX-S output shape: {tuple(output.shape)}")
        return output, ratio, width, height

    def _detect_at(self, image: Any, confidence_threshold: float) -> list[Detection]:
        output, ratio, width, height = self._infer(image)
        return yolox_decode_output(
            output,
            width=width,
            height=height,
            ratio=ratio,
            confidence_threshold=confidence_threshold,
            nms_threshold=self.nms_threshold,
        )

    def detect_raw(self, image: Any) -> list[Detection]:
        return self._detect_at(image, 0.0)

    def detect(self, image: Any) -> list[Detection]:
        return self._detect_at(image, self.confidence_threshold)


@dataclass
class Observation:
    camera_state: CameraState
    captured_at: str
    frame_sequence: int
    people: list[dict[str, Any]]
    processing_ms: float
    health_reason: str | None = None
    dropped_frames: int = 0
    room_state: RoomState = RoomState.EMPTY
    image_quality: dict[str, float] | None = None
    room_state_transition: str | None = None
    detector_evidence: bool = False
    strong_detector_evidence: bool = False
    support_detector_evidence: bool = False
    max_person_confidence: float | None = None
    candidates: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "camera_state": self.camera_state.value,
            "captured_at": self.captured_at,
            "frame_sequence": self.frame_sequence,
            "people": self.people,
            "processing_ms": round(self.processing_ms, 3),
            "health_reason": self.health_reason,
            "dropped_frames": self.dropped_frames,
            "room_state": self.room_state.value,
            "image_quality": self.image_quality,
            "room_state_transition": self.room_state_transition,
            "detector_evidence": self.detector_evidence,
            "strong_detector_evidence": self.strong_detector_evidence,
            "support_detector_evidence": self.support_detector_evidence,
            "max_person_confidence": self.max_person_confidence,
            "candidates": self.candidates,
        }


class PerceptionEngine:
    """Converts one local frame into one structured observation."""

    def __init__(
        self,
        detector: Detector,
        tracker: IoUTracker,
        presence_state: PresenceStateMachine | None = None,
        *,
        entry_confidence_threshold: float | None = None,
        hold_confidence_threshold: float | None = None,
    ) -> None:
        self.detector = detector
        self.tracker = tracker
        self.presence_state = presence_state or PresenceStateMachine()
        configured_threshold = float(getattr(detector, "confidence_threshold", 0.40))
        self.entry_confidence_threshold = (
            configured_threshold if entry_confidence_threshold is None else float(entry_confidence_threshold)
        )
        self.hold_confidence_threshold = (
            self.entry_confidence_threshold if hold_confidence_threshold is None else float(hold_confidence_threshold)
        )
        if not 0 <= self.hold_confidence_threshold <= self.entry_confidence_threshold <= 1:
            raise ValueError("hold_confidence_threshold must be <= entry_confidence_threshold, both between 0 and 1")

    def update_room_state(
        self,
        evaluated_at: datetime,
        *,
        camera_state: CameraState,
        human_evidence: bool = False,
        entry_evidence: bool | None = None,
        support_evidence: bool | None = None,
        detector_usable: bool = True,
        visual_quality_usable: bool = True,
    ) -> PresenceStateSnapshot:
        return self.presence_state.update(
            evaluated_at,
            camera_state=camera_state,
            human_evidence=human_evidence,
            entry_evidence=entry_evidence,
            support_evidence=support_evidence,
            detector_usable=detector_usable,
            visual_quality_usable=visual_quality_usable,
        )

    def process(
        self,
        image: Any,
        *,
        frame_sequence: int,
        captured_at: datetime,
        dropped_frames: int = 0,
    ) -> Observation:
        started = time.perf_counter()
        image_quality = None
        shape = getattr(image, "shape", None)
        if shape is not None and len(shape) in {2, 3}:
            image_quality = measure_image_quality(image).as_dict()
        raw_detector = getattr(self.detector, "detect_raw", None)
        if callable(raw_detector):
            raw_candidates = raw_detector(image)
            entry_detections = [
                detection for detection in raw_candidates if detection.confidence >= self.entry_confidence_threshold
            ]
            support_detections = [
                detection for detection in raw_candidates if detection.confidence >= self.hold_confidence_threshold
            ]
        else:
            entry_detections = self.detector.detect(image)
            support_detections = entry_detections
            raw_candidates = entry_detections
        people = self.tracker.update(entry_detections)
        strong_evidence = bool(entry_detections)
        support_evidence = bool(support_detections)
        room_state = self.update_room_state(
            captured_at,
            camera_state=CameraState.ONLINE,
            entry_evidence=strong_evidence,
            support_evidence=support_evidence,
        )
        return Observation(
            camera_state=CameraState.ONLINE,
            captured_at=captured_at.astimezone(timezone.utc).isoformat(),
            frame_sequence=frame_sequence,
            people=people,
            processing_ms=(time.perf_counter() - started) * 1000,
            dropped_frames=dropped_frames,
            room_state=room_state.state,
            image_quality=image_quality,
            room_state_transition=room_state.transition,
            detector_evidence=strong_evidence,
            strong_detector_evidence=strong_evidence,
            support_detector_evidence=support_evidence,
            max_person_confidence=max((candidate.confidence for candidate in raw_candidates), default=None),
            candidates=[
                {"bbox": [round(value, 2) for value in candidate.bbox], "confidence": candidate.confidence}
                for candidate in raw_candidates
            ],
        )


def validate_config(config: dict[str, Any]) -> None:
    camera = config.get("camera")
    detector = config.get("detector")
    tracker = config.get("tracker")
    if not isinstance(camera, dict) or not isinstance(detector, dict) or not isinstance(tracker, dict):
        raise ValueError("config must contain camera, detector, and tracker objects")
    if not camera.get("device_path") and int(camera.get("index", -1)) < 0:
        raise ValueError("camera.device_path or non-negative camera.index is required")
    if camera.get("backend", "auto") not in {"auto", "v4l2", "dshow", "msmf", "any"}:
        raise ValueError("camera.backend must be auto, v4l2, dshow, msmf, or any")
    fourcc = camera.get("fourcc")
    if fourcc is not None and (not isinstance(fourcc, str) or len(fourcc) != 4):
        raise ValueError("camera.fourcc must be exactly four characters when provided")
    for key in ("width", "height", "fps", "buffer_size"):
        if float(camera.get(key, 0)) <= 0:
            raise ValueError(f"camera.{key} must be positive")
    if int(camera.get("buffer_size", 1)) != 1:
        raise ValueError("camera.buffer_size must remain 1 to enforce latest-frame behavior")
    if detector.get("name") not in {"openvino_person_detection_0202", "openvino_yolox_s"}:
        raise ValueError("detector.name must be openvino_person_detection_0202 or openvino_yolox_s")
    if not 0 <= float(detector.get("confidence_threshold", 0.5)) <= 1:
        raise ValueError("detector.confidence_threshold must be between 0 and 1")
    hold_threshold = float(detector.get("hold_confidence_threshold", detector.get("confidence_threshold", 0.5)))
    if not 0 <= hold_threshold <= float(detector.get("confidence_threshold", 0.5)):
        raise ValueError("detector.hold_confidence_threshold must be between 0 and confidence_threshold")
    if not detector.get("model_xml") or not detector.get("model_bin"):
        raise ValueError("detector.model_xml and detector.model_bin are required")
    if not detector.get("device", "CPU"):
        raise ValueError("detector.device must be non-empty")
    if detector.get("name") == "openvino_yolox_s":
        if not 0 <= float(detector.get("nms_threshold", 0.45)) <= 1:
            raise ValueError("detector.nms_threshold must be between 0 and 1")
    storage = config.get("storage", {})
    if not isinstance(storage, dict):
        raise ValueError("storage must be an object")
    if storage.get("database_path") is not None and not isinstance(storage.get("database_path"), str):
        raise ValueError("storage.database_path must be a string when provided")
    if int(tracker.get("max_missing_frames", 0)) < 0:
        raise ValueError("tracker.max_missing_frames must be non-negative")
    presence = config.get("presence", {})
    if not isinstance(presence, dict):
        raise ValueError("presence must be an object")
    PresenceStateConfig.from_mapping(presence)


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
        self.actual_fourcc = ""
        self.frames_captured = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._capture: Any = None

    def _set_state(self, state: CameraState, reason: str) -> None:
        with self._lock:
            self.state = state
            self.reason = reason

    def snapshot(self) -> tuple[CameraState, str, str, float, float, float, str, int]:
        with self._lock:
            return (self.state, self.reason, self.backend_name, self.actual_width, self.actual_height, self.actual_fps, self.actual_fourcc, self.frames_captured)

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
        if camera.get("backend") == "auto":
            backend_names = ["v4l2", "any"] if not sys.platform.startswith("win") else ["dshow", "msmf", "any"]
        else:
            backend_names = [camera["backend"]]
        backend_values = {
            "v4l2": getattr(cv2, "CAP_V4L2", cv2.CAP_ANY),
            "dshow": cv2.CAP_DSHOW,
            "msmf": cv2.CAP_MSMF,
            "any": cv2.CAP_ANY,
        }
        source: Any = camera.get("device_path") or int(camera.get("index", 0))
        capture = None
        for backend_name in backend_names:
            candidate = cv2.VideoCapture(source, backend_values[backend_name])
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
        if camera.get("fourcc"):
            capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*camera["fourcc"]))
        self.actual_width = capture.get(cv2.CAP_PROP_FRAME_WIDTH)
        self.actual_height = capture.get(cv2.CAP_PROP_FRAME_HEIGHT)
        self.actual_fps = capture.get(cv2.CAP_PROP_FPS)
        fourcc_value = int(capture.get(cv2.CAP_PROP_FOURCC) or 0)
        self.actual_fourcc = "".join(chr((fourcc_value >> (8 * index)) & 0xFF) for index in range(4)).rstrip("\x00")
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
        detector_name = config["detector"]["name"]
        detector_class = (
            OpenVINOYOLOXSPersonDetector
            if detector_name == "openvino_yolox_s"
            else OpenVINOPersonDetector
        )
        self.engine = PerceptionEngine(
            detector_class(config["detector"]),
            IoUTracker(**{
                "match_iou_threshold": config["tracker"]["match_iou_threshold"],
                "high_confidence_threshold": config["tracker"]["high_confidence_threshold"],
                "new_track_confidence_threshold": config["tracker"]["new_track_confidence_threshold"],
                "max_missing_frames": config["tracker"]["max_missing_frames"],
            }),
            PresenceStateMachine(PresenceStateConfig.from_mapping(config.get("presence"))),
            entry_confidence_threshold=float(config["detector"].get("confidence_threshold", 0.40)),
            hold_confidence_threshold=float(
                config["detector"].get("hold_confidence_threshold", config["detector"].get("confidence_threshold", 0.40))
            ),
        )
        self.observation_callback = observation_callback
        storage = config.get("storage", {})
        database_path = storage.get("database_path") if isinstance(storage, dict) else None
        self.presence_store = PresenceStore(database_path) if database_path else None
        self.last_persistence_error: str | None = None
        self.worker = _CameraWorker(config, self.buffer)
        self._stop = threading.Event()
        self._last_sequence = 0
        self._processing_ms: list[float] = []
        self._started_at = 0.0

    def stop(self) -> None:
        self._stop.set()
        self.worker.stop()
        if self.presence_store is not None:
            self.presence_store.close()
            self.presence_store = None

    def _record_observation(self, observation: Observation) -> None:
        if self.presence_store is None:
            return
        try:
            self.presence_store.record_observation(observation)
        except Exception as exc:  # pragma: no cover - exercised by filesystem faults
            # A history outage is explicit diagnostic state. It must never
            # turn a missing observation into authoritative empty-room truth.
            self.last_persistence_error = f"{type(exc).__name__}: {exc}"

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
                        evaluated_at = datetime.now(timezone.utc)
                        room_state = self.engine.update_room_state(
                            evaluated_at,
                            camera_state=state,
                            detector_usable=False,
                        )
                        observation = Observation(
                            state,
                            evaluated_at.isoformat(),
                            self._last_sequence,
                            [],
                            0.0,
                            reason,
                            self.buffer.dropped_frames,
                            room_state.state,
                            None,
                            room_state.transition,
                            False,
                        )
                        self._record_observation(observation)
                        if self.observation_callback:
                            self.observation_callback(observation)
                        last_health_emit = now
                    time.sleep(0.01)
                    continue
                self._last_sequence = frame.sequence
                state, reason, *_ = self.worker.snapshot()
                if state != CameraState.ONLINE:
                    room_state = self.engine.update_room_state(
                        frame.captured_at,
                        camera_state=state,
                        detector_usable=False,
                    )
                    observation = Observation(
                        state,
                        frame.captured_at.isoformat(),
                        frame.sequence,
                        [],
                        0.0,
                        reason,
                        self.buffer.dropped_frames,
                        room_state.state,
                        None,
                        room_state.transition,
                        False,
                    )
                else:
                    try:
                        observation = self.engine.process(frame.image, frame_sequence=frame.sequence, captured_at=frame.captured_at, dropped_frames=self.buffer.dropped_frames)
                    except Exception as exc:
                        room_state = self.engine.update_room_state(
                            frame.captured_at,
                            camera_state=CameraState.DEGRADED,
                            detector_usable=False,
                        )
                        observation = Observation(
                            CameraState.DEGRADED,
                            frame.captured_at.isoformat(),
                            frame.sequence,
                            [],
                            0.0,
                            f"detector_failed:{type(exc).__name__}",
                            self.buffer.dropped_frames,
                            room_state.state,
                            None,
                            room_state.transition,
                            False,
                        )
                self._processing_ms.append(observation.processing_ms)
                self._record_observation(observation)
                if self.observation_callback:
                    self.observation_callback(observation)
        finally:
            self.stop()
        return self.summary()

    def summary(self) -> dict[str, Any]:
        state, reason, backend, width, height, fps, fourcc, captured = self.worker.snapshot()
        elapsed = max(0.001, time.perf_counter() - self._started_at) if self._started_at else 0.0
        processed = len(self._processing_ms)
        values = sorted(self._processing_ms)
        p95 = values[min(len(values) - 1, max(0, math.ceil(len(values) * 0.95) - 1))] if values else 0.0
        return {
            "camera_state": state.value,
            "room_state": self.engine.presence_state.state.value,
            "health_reason": reason,
            "backend": backend,
            "actual_resolution": [width, height],
            "actual_camera_fps": fps,
            "actual_fourcc": fourcc,
            "frames_captured": captured,
            "frames_processed": processed,
            "processed_fps": round(processed / elapsed, 3) if elapsed else 0.0,
            "median_processing_ms": round(statistics.median(values), 3) if values else 0.0,
            "p95_processing_ms": round(p95, 3),
            "dropped_frames": self.buffer.dropped_frames,
            "codex_luna_calls": 0,
            "persistence_error": self.last_persistence_error,
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
