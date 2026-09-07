"""Bounded Hailo face-pipeline contract for the SENTRY projection.

The Pi owns accelerator execution; ANIMA/SENTRY on the processing host owns
identity authority.  This module deliberately does not persist frames or
embeddings and does not allow a model-controlled executable, device, or path.
It validates the official Hailo Apps multi-model contract (SCRFD detector plus
face-recognition model) and provides a safe launch description for the Pi
worker once those externally provisioned assets exist.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID


class HailoFaceUnavailable(RuntimeError):
    """The accelerator or its qualified model assets are not available."""


@dataclass(frozen=True, slots=True)
class HailoFaceConfig:
    device_path: Path = Path("/dev/hailo0")
    detection_hef: Path = Path("/nonexistent/anima-hailo-face-detection.hef")
    recognition_hef: Path = Path("/nonexistent/anima-hailo-face-recognition.hef")
    hailo_apps_root: Path = Path("/nonexistent/hailo-apps")
    input_device: str = "/dev/video0"
    recognition_threshold: float = 0.60

    @classmethod
    def from_mapping(cls, values: dict[str, Any] | None) -> "HailoFaceConfig":
        values = values or {}
        result = cls(
            device_path=Path(str(values.get("device_path", "/dev/hailo0"))).expanduser(),
            detection_hef=Path(str(values.get("detection_hef", ""))).expanduser(),
            recognition_hef=Path(str(values.get("recognition_hef", ""))).expanduser(),
            hailo_apps_root=Path(str(values.get("hailo_apps_root", ""))).expanduser(),
            input_device=str(values.get("input_device", "/dev/video0")),
            recognition_threshold=float(values.get("recognition_threshold", 0.60)),
        )
        if result.input_device != "/dev/video0":
            raise ValueError("Hailo input is fixed to the commissioned camera device")
        if not 0.0 <= result.recognition_threshold <= 1.0:
            raise ValueError("Hailo recognition threshold must be between 0 and 1")
        for path, label in (
            (result.device_path, "device_path"),
            (result.detection_hef, "detection_hef"),
            (result.recognition_hef, "recognition_hef"),
            (result.hailo_apps_root, "hailo_apps_root"),
        ):
            if not path.is_absolute():
                raise ValueError(f"{label} must be an absolute commissioned path")
        return result


@dataclass(frozen=True, slots=True)
class HailoFaceObservation:
    """Privacy-safe identity candidate returned by the Pi worker."""

    observed_at: datetime
    track_id: int
    identity_state: str
    person_id: UUID | None
    confidence: float | None

    def to_payload(self) -> dict[str, Any]:
        return {
            "observed_at": self.observed_at.astimezone(UTC).isoformat(),
            "track_id": self.track_id,
            "identity_state": self.identity_state,
            "person_id": str(self.person_id) if self.person_id else None,
            "confidence": self.confidence,
        }


class HailoFaceRuntime:
    """Validate and describe the official Hailo Apps face pipeline."""

    APP_MODULE = "hailo_apps.python.pipeline_apps.face_recognition.face_recognition"

    def __init__(self, config: HailoFaceConfig) -> None:
        self.config = config

    def status(self) -> dict[str, Any]:
        missing = [
            label
            for label, path in (
                ("hailo_device", self.config.device_path),
                ("detection_hef", self.config.detection_hef),
                ("recognition_hef", self.config.recognition_hef),
                ("hailo_apps_root", self.config.hailo_apps_root),
            )
            if not path.exists()
        ]
        runtime_present = importlib.util.find_spec("hailo_platform") is not None or importlib.util.find_spec("hailo") is not None
        if not runtime_present:
            missing.append("hailo_python_runtime")
        return {
            "provider": "hailo_face",
            "available": not missing,
            "missing": missing,
            "device": str(self.config.device_path),
            "models": {
                "detection": str(self.config.detection_hef),
                "recognition": str(self.config.recognition_hef),
            },
            "official_app_module": self.APP_MODULE,
            "authority_host": "sentry-processing-host",
        }

    def require_available(self) -> None:
        status = self.status()
        if not status["available"]:
            raise HailoFaceUnavailable(
                "HAILO_FACE_MODELS_OR_RUNTIME_UNAVAILABLE:" + ",".join(status["missing"])
            )

    def command(self, *, python_executable: str | None = None) -> list[str]:
        """Return fixed official-app arguments; never accepts user/model input."""
        self.require_available()
        python = python_executable or sys.executable
        if not os.path.isabs(python):
            raise ValueError("Hailo worker Python executable must be absolute")
        return [
            python,
            "-m",
            self.APP_MODULE,
            "--input",
            "usb",
            "--mode",
            "run",
            "--hef-path",
            str(self.config.detection_hef),
            "--hef-path",
            str(self.config.recognition_hef),
        ]


def parse_observation(value: dict[str, Any]) -> HailoFaceObservation:
    """Parse only the worker's bounded result; raw image data is rejected."""
    if set(value) - {"observed_at", "track_id", "identity_state", "person_id", "confidence"}:
        raise ValueError("unexpected Hailo observation fields")
    observed_at = datetime.fromisoformat(str(value["observed_at"]))
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("Hailo observation timestamp must be timezone-aware")
    track_id = int(value["track_id"])
    if track_id < 0:
        raise ValueError("Hailo track_id must be non-negative")
    identity_state = str(value["identity_state"])
    if identity_state not in {"recognized", "unknown", "unresolved"}:
        raise ValueError("unsupported Hailo identity state")
    person_id = UUID(str(value["person_id"])) if value.get("person_id") else None
    confidence = value.get("confidence")
    if confidence is not None and not 0.0 <= float(confidence) <= 1.0:
        raise ValueError("Hailo confidence must be between 0 and 1")
    if identity_state != "recognized" and person_id is not None:
        raise ValueError("only recognized Hailo observations may name a person")
    return HailoFaceObservation(
        observed_at=observed_at.astimezone(UTC),
        track_id=track_id,
        identity_state=identity_state,
        person_id=person_id,
        confidence=float(confidence) if confidence is not None else None,
    )
