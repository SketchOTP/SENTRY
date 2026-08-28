"""Timestamp-based authoritative room-state aggregation for SENTRY.

This module consumes bounded human evidence and source health only.  It does
not persist history, emit semantic events, or count/identify individuals.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class RoomState(str, Enum):
    EMPTY = "empty"
    OCCUPIED = "occupied"
    DEGRADED = "degraded"
    OFFLINE = "offline"


@dataclass(frozen=True)
class PresenceStateConfig:
    """Boundaries for temporal room-state hysteresis, expressed in seconds."""

    entry_confirmation_seconds: float = 1.0
    entry_evidence_gap_seconds: float = 1.0
    absence_grace_seconds: float = 15.0

    def __post_init__(self) -> None:
        if self.entry_confirmation_seconds <= 0:
            raise ValueError("entry_confirmation_seconds must be positive")
        if self.entry_evidence_gap_seconds <= 0:
            raise ValueError("entry_evidence_gap_seconds must be positive")
        if self.absence_grace_seconds <= 0:
            raise ValueError("absence_grace_seconds must be positive")

    @classmethod
    def from_mapping(cls, values: dict[str, Any] | None) -> "PresenceStateConfig":
        values = values or {}
        return cls(
            entry_confirmation_seconds=float(values.get("entry_confirmation_seconds", 1.0)),
            entry_evidence_gap_seconds=float(values.get("entry_evidence_gap_seconds", 1.0)),
            absence_grace_seconds=float(values.get("absence_grace_seconds", 15.0)),
        )


@dataclass(frozen=True)
class PresenceStateSnapshot:
    state: RoomState
    evaluated_at: datetime
    last_human_evidence_at: datetime | None
    pending_occupied_since: datetime | None
    transition: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "evaluated_at": self.evaluated_at.isoformat(),
            "last_human_evidence_at": (
                self.last_human_evidence_at.isoformat() if self.last_human_evidence_at else None
            ),
            "pending_occupied_since": (
                self.pending_occupied_since.isoformat() if self.pending_occupied_since else None
            ),
            "transition": self.transition,
        }


class PresenceStateMachine:
    """Maintain binary room presence while preserving source uncertainty.

    A detector-positive observation is credible human evidence for the binary
    room metric; duplicate boxes do not increase occupancy.  Camera, detector,
    or visual-quality failure takes precedence over occupancy inference.
    """

    def __init__(self, config: PresenceStateConfig | None = None) -> None:
        self.config = config or PresenceStateConfig()
        self.state = RoomState.EMPTY
        self._last_update: datetime | None = None
        self._last_human_evidence_at: datetime | None = None
        self._pending_occupied_since: datetime | None = None
        self._occupancy_was_confirmed = False

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("presence timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    @staticmethod
    def _source_value(value: Any) -> str:
        return str(getattr(value, "value", value)).lower()

    def _set_state(self, state: RoomState) -> str | None:
        if state == self.state:
            return None
        previous = self.state
        self.state = state
        if state == RoomState.OCCUPIED:
            self._occupancy_was_confirmed = True
        elif state == RoomState.EMPTY:
            self._occupancy_was_confirmed = False
        return f"{previous.value}->{state.value}"

    def update(
        self,
        evaluated_at: datetime,
        *,
        camera_state: Any,
        human_evidence: bool = False,
        entry_evidence: bool | None = None,
        support_evidence: bool | None = None,
        detector_usable: bool = True,
        visual_quality_usable: bool = True,
    ) -> PresenceStateSnapshot:
        now = self._utc(evaluated_at)
        if self._last_update is not None and now < self._last_update:
            raise ValueError("presence timestamps must be non-decreasing")
        self._last_update = now

        source = self._source_value(camera_state)
        if source == "offline":
            self._pending_occupied_since = None
            transition = self._set_state(RoomState.OFFLINE)
            return self._snapshot(now, transition)
        if source != "online" or not detector_usable or not visual_quality_usable:
            # A source outage is not evidence of departure.  Discard only a
            # not-yet-confirmed entry candidate so stale positives cannot
            # become occupancy after recovery without fresh evidence.
            self._pending_occupied_since = None
            transition = self._set_state(RoomState.DEGRADED)
            return self._snapshot(now, transition)

        strong_evidence = human_evidence if entry_evidence is None else bool(entry_evidence)
        hold_evidence = strong_evidence if support_evidence is None else bool(support_evidence)
        last_evidence_before_update = self._last_human_evidence_at
        if self.state == RoomState.OCCUPIED:
            if hold_evidence:
                self._last_human_evidence_at = now
        elif strong_evidence:
            self._last_human_evidence_at = now
            recently_confirmed = (
                self._occupancy_was_confirmed
                and last_evidence_before_update is not None
                and (now - last_evidence_before_update).total_seconds() <= self.config.absence_grace_seconds
            )
            if recently_confirmed:
                self._pending_occupied_since = None
                transition = self._set_state(RoomState.OCCUPIED)
                return self._snapshot(now, transition)
            if self._pending_occupied_since is None:
                self._pending_occupied_since = now
        elif self._pending_occupied_since is not None:
            gap = (now - self._last_human_evidence_at).total_seconds() if self._last_human_evidence_at else None
            if gap is None or gap > self.config.entry_evidence_gap_seconds:
                self._pending_occupied_since = None

        transition: str | None = None
        if self.state == RoomState.EMPTY or self.state in {RoomState.DEGRADED, RoomState.OFFLINE}:
            if not strong_evidence and self._occupancy_was_confirmed:
                if (
                    self._last_human_evidence_at is not None
                    and (now - self._last_human_evidence_at).total_seconds() < self.config.absence_grace_seconds
                ):
                    transition = self._set_state(RoomState.OCCUPIED)
                    return self._snapshot(now, transition)
                self._pending_occupied_since = None
            confirmed = (
                self._pending_occupied_since is not None
                and (now - self._pending_occupied_since).total_seconds() >= self.config.entry_confirmation_seconds
            )
            if confirmed:
                transition = self._set_state(RoomState.OCCUPIED)
            else:
                transition = self._set_state(RoomState.EMPTY)
        elif self.state == RoomState.OCCUPIED:
            if self._last_human_evidence_at is None:
                transition = self._set_state(RoomState.EMPTY)
            elif (now - self._last_human_evidence_at).total_seconds() >= self.config.absence_grace_seconds:
                self._pending_occupied_since = None
                transition = self._set_state(RoomState.EMPTY)

        return self._snapshot(now, transition)

    def _snapshot(self, now: datetime, transition: str | None) -> PresenceStateSnapshot:
        return PresenceStateSnapshot(
            state=self.state,
            evaluated_at=now,
            last_human_evidence_at=self._last_human_evidence_at,
            pending_occupied_since=self._pending_occupied_since,
            transition=transition,
        )


@dataclass(frozen=True)
class ImageQualityMetrics:
    """Metadata-only RGB/BGR luminance measurements; no image is retained."""

    mean_luminance: float
    p10_luminance: float
    p90_luminance: float
    dynamic_range: float
    contrast_stddev: float

    def as_dict(self) -> dict[str, float]:
        return {
            "mean_luminance": round(self.mean_luminance, 3),
            "p10_luminance": round(self.p10_luminance, 3),
            "p90_luminance": round(self.p90_luminance, 3),
            "dynamic_range": round(self.dynamic_range, 3),
            "contrast_stddev": round(self.contrast_stddev, 3),
        }


def measure_image_quality(image: Any) -> ImageQualityMetrics:
    """Return luminance metrics for a frame without writing or returning pixels."""

    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover - project runtime dependency
        raise RuntimeError("numpy is required for image-quality measurement") from exc
    pixels = np.asarray(image)
    if pixels.ndim == 2:
        luminance = pixels.astype(np.float32)
    elif pixels.ndim == 3 and pixels.shape[2] == 3:
        bgr = pixels.astype(np.float32)
        luminance = 0.114 * bgr[:, :, 0] + 0.587 * bgr[:, :, 1] + 0.299 * bgr[:, :, 2]
    else:
        raise ValueError("image-quality measurement expects a grayscale or three-channel image")
    if luminance.size == 0:
        raise ValueError("image-quality measurement expects a non-empty image")
    p10, p90 = np.percentile(luminance, (10, 90))
    return ImageQualityMetrics(
        mean_luminance=float(np.mean(luminance)),
        p10_luminance=float(p10),
        p90_luminance=float(p90),
        dynamic_range=float(p90 - p10),
        contrast_stddev=float(np.std(luminance)),
    )
