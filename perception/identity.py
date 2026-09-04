"""Conservative local primary-user identity using OpenCV Zoo YuNet and SFace.

The module deliberately keeps identity separate from room presence.  Face
images are accepted only in memory, and the only durable identity material is
the normalized prototype supplied to ``PresenceStore``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable


IDENTITY_STATES = {"recognized", "unknown", "unresolved"}


@dataclass(frozen=True)
class FaceQualityConfig:
    detector_score_threshold: float = 0.90
    detector_nms_threshold: float = 0.30
    detector_top_k: int = 5000
    min_face_size: float = 60.0
    min_sharpness: float = 20.0
    reject_clipped_faces: bool = True

    @classmethod
    def from_mapping(cls, values: dict[str, Any] | None) -> "FaceQualityConfig":
        values = values or {}
        result = cls(
            detector_score_threshold=float(values.get("detector_score_threshold", 0.90)),
            detector_nms_threshold=float(values.get("detector_nms_threshold", 0.30)),
            detector_top_k=int(values.get("detector_top_k", 5000)),
            min_face_size=float(values.get("min_face_size", 60.0)),
            min_sharpness=float(values.get("min_sharpness", 20.0)),
            reject_clipped_faces=bool(values.get("reject_clipped_faces", True)),
        )
        if not 0 <= result.detector_score_threshold <= 1:
            raise ValueError("identity.detector_score_threshold must be between 0 and 1")
        if not 0 <= result.detector_nms_threshold <= 1:
            raise ValueError("identity.detector_nms_threshold must be between 0 and 1")
        if result.detector_top_k <= 0 or result.min_face_size <= 0 or result.min_sharpness < 0:
            raise ValueError("identity face quality limits must be positive")
        return result


@dataclass(frozen=True)
class FaceDetection:
    bbox: tuple[float, float, float, float]
    confidence: float
    landmarks: tuple[float, ...]

    @property
    def center(self) -> tuple[float, float]:
        return (self.bbox[0] + self.bbox[2] / 2.0, self.bbox[1] + self.bbox[3] / 2.0)


def normalize_embedding(embedding: Any) -> Any:
    """Return a finite unit-normalized float32 vector."""

    import numpy as np

    values = np.asarray(embedding, dtype=np.float32).reshape(-1)
    if values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("identity embedding must be a finite non-empty vector")
    norm = float(np.linalg.norm(values))
    if norm <= 0:
        raise ValueError("identity embedding must not be zero")
    return (values / norm).astype(np.float32)


def build_prototype(embeddings: Iterable[Any]) -> Any:
    """Create one normalized mean prototype from accepted in-memory samples."""

    import numpy as np

    normalized = [normalize_embedding(value) for value in embeddings]
    if not normalized:
        raise ValueError("at least one accepted enrollment embedding is required")
    dimensions = {value.shape for value in normalized}
    if len(dimensions) != 1:
        raise ValueError("enrollment embeddings must have one consistent dimension")
    return normalize_embedding(np.mean(np.stack(normalized, axis=0), axis=0))


class OpenCVFaceBackend:
    """YuNet detector plus SFace recognizer through OpenCV's native API."""

    def __init__(self, config: dict[str, Any]) -> None:
        try:
            import cv2
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError("opencv is required for YuNet/SFace identity") from exc
        self._cv2 = cv2
        self.quality = FaceQualityConfig.from_mapping(config.get("quality"))
        self.yunet_model = Path(config.get("yunet_model", "")).expanduser()
        self.sface_model = Path(config.get("sface_model", "")).expanduser()
        self.yunet_sha256 = config.get("yunet_sha256")
        self.sface_sha256 = config.get("sface_sha256")
        if not self.yunet_model.is_file():
            raise RuntimeError(f"YuNet model file not found: {self.yunet_model}")
        if not self.sface_model.is_file():
            raise RuntimeError(f"SFace model file not found: {self.sface_model}")
        self._verify_checksum(self.yunet_model, self.yunet_sha256, "YuNet")
        self._verify_checksum(self.sface_model, self.sface_sha256, "SFace")
        try:
            self.detector = cv2.FaceDetectorYN_create(
                str(self.yunet_model),
                "",
                (320, 320),
                self.quality.detector_score_threshold,
                self.quality.detector_nms_threshold,
                self.quality.detector_top_k,
            )
            self.recognizer = cv2.FaceRecognizerSF_create(str(self.sface_model), "")
        except Exception as exc:
            raise RuntimeError(f"unable to load YuNet/SFace models: {exc}") from exc

    @staticmethod
    def _verify_checksum(path: Path, expected: str | None, label: str) -> None:
        if not expected:
            return
        import hashlib

        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        actual = digest.hexdigest()
        if actual.lower() != str(expected).lower():
            raise RuntimeError(f"{label} model SHA-256 mismatch: expected {expected}, got {actual}")

    def detect_faces(self, image: Any) -> list[FaceDetection]:
        height, width = image.shape[:2]
        if height <= 0 or width <= 0:
            return []
        self.detector.setInputSize((int(width), int(height)))
        result = self.detector.detect(image)
        rows = result[1] if isinstance(result, tuple) else result
        if rows is None:
            return []
        detections: list[FaceDetection] = []
        for row in rows:
            values = [float(value) for value in row]
            if len(values) < 15:
                raise RuntimeError(f"unexpected YuNet output row length: {len(values)}")
            detections.append(
                FaceDetection(
                    (values[0], values[1], values[2], values[3]),
                    values[14],
                    tuple(values[4:14]),
                )
            )
        return detections

    def quality_metrics(self, image: Any, face: FaceDetection) -> dict[str, float | bool]:
        import cv2

        height, width = image.shape[:2]
        x, y, face_width, face_height = face.bbox
        x1, y1 = max(0, int(x)), max(0, int(y))
        x2, y2 = min(width, int(x + face_width)), min(height, int(y + face_height))
        clipped = x < 0 or y < 0 or x + face_width > width or y + face_height > height
        sharpness = 0.0
        if x2 > x1 and y2 > y1:
            crop = image[y1:y2, x1:x2]
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
            sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        accepted = (
            face.confidence >= self.quality.detector_score_threshold
            and face_width >= self.quality.min_face_size
            and face_height >= self.quality.min_face_size
            and sharpness >= self.quality.min_sharpness
            and (not clipped or not self.quality.reject_clipped_faces)
        )
        return {
            "detector_confidence": face.confidence,
            "face_width": face_width,
            "face_height": face_height,
            "sharpness": sharpness,
            "clipped": clipped,
            "accepted": accepted,
        }

    def accepted_embedding(self, image: Any, face: FaceDetection) -> tuple[Any, dict[str, Any]] | None:
        metrics = self.quality_metrics(image, face)
        if not metrics["accepted"]:
            return None
        try:
            import numpy as np

            face_row = np.asarray(face.bbox + face.landmarks, dtype=np.float32)
            aligned = self.recognizer.alignCrop(image, face_row)
            feature = self.recognizer.feature(aligned)
            return normalize_embedding(feature), metrics
        except Exception as exc:
            raise RuntimeError(f"SFace feature extraction failed: {exc}") from exc


@dataclass
class _PendingMatch:
    first_at: datetime
    last_at: datetime
    count: int


class IdentityResolver:
    """Associate face evidence with existing person tracks conservatively."""

    def __init__(
        self,
        backend: OpenCVFaceBackend,
        *,
        match_threshold: float = 0.45,
        confirmation_count: int = 3,
        confirmation_window_seconds: float = 2.0,
        profile_provider: Callable[[], dict[str, Any] | None] | None = None,
    ) -> None:
        if not 0 <= match_threshold <= 1:
            raise ValueError("identity.match_threshold must be between 0 and 1")
        if confirmation_count <= 0 or confirmation_window_seconds <= 0:
            raise ValueError("identity confirmation settings must be positive")
        self.backend = backend
        self.match_threshold = match_threshold
        self.confirmation_count = confirmation_count
        self.confirmation_window_seconds = confirmation_window_seconds
        self.profile_provider = profile_provider
        self._pending: dict[int, _PendingMatch] = {}

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("identity timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    @staticmethod
    def _inside(face: FaceDetection, person: dict[str, Any]) -> bool:
        bbox = person.get("bbox")
        if not bbox or len(bbox) != 4:
            return False
        cx, cy = face.center
        return float(bbox[0]) <= cx <= float(bbox[2]) and float(bbox[1]) <= cy <= float(bbox[3])

    def _unresolved(self, people: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                **person,
                "person_id": None,
                "identity_state": "unresolved",
                "identity_confidence": None,
            }
            for person in people
        ]

    def _profile(self) -> dict[str, Any] | None:
        return self.profile_provider() if self.profile_provider else None

    def resolve(self, image: Any, people: list[dict[str, Any]], evaluated_at: datetime) -> list[dict[str, Any]]:
        now = self._utc(evaluated_at)
        result = self._unresolved(people)
        profile = self._profile()
        if not people or profile is None:
            return result
        match_threshold = float(profile.get("calibrated_threshold", self.match_threshold))
        if not 0 <= match_threshold <= 1:
            raise RuntimeError("stored identity threshold is invalid")
        faces = self.backend.detect_faces(image)
        for index, person in enumerate(people):
            if not person.get("visible", True):
                continue
            matches = [face for face in faces if self._inside(face, person)]
            if len(matches) != 1:
                continue
            extracted = self.backend.accepted_embedding(image, matches[0])
            if extracted is None:
                continue
            query, quality = extracted
            try:
                score = float(self.backend.recognizer.match(query, profile["prototype"], self.backend._cv2.FaceRecognizerSF_FR_COSINE))
            except Exception as exc:
                raise RuntimeError(f"SFace similarity comparison failed: {exc}") from exc
            track_id = int(person.get("track_id", -1))
            if score < match_threshold:
                self._pending.pop(track_id, None)
                result[index].update(
                    {"identity_state": "unknown", "identity_confidence": round(max(0.0, min(1.0, score)), 4), "face_quality": quality}
                )
                continue
            pending = self._pending.get(track_id)
            if pending is None or (now - pending.last_at).total_seconds() > self.confirmation_window_seconds:
                pending = _PendingMatch(now, now, 1)
            else:
                pending.last_at = now
                pending.count += 1
            self._pending[track_id] = pending
            if pending.count >= self.confirmation_count:
                result[index].update(
                    {
                        "person_id": profile["person_id"],
                        "identity_state": "recognized",
                        "identity_confidence": round(max(0.0, min(1.0, score)), 4),
                        "face_quality": quality,
                    }
                )
            else:
                result[index].update(
                    {"identity_state": "unresolved", "identity_confidence": round(max(0.0, min(1.0, score)), 4), "face_quality": quality}
                )
        return result


class MultiProfileIdentityResolver(IdentityResolver):
    """Conservatively resolve visible tracks against several enrolled profiles."""

    def __init__(
        self,
        backend: OpenCVFaceBackend,
        *,
        confirmation_count: int = 3,
        confirmation_window_seconds: float = 2.0,
        profile_provider: Callable[[], list[dict[str, Any]]] | None = None,
        minimum_separation: float = 0.05,
    ) -> None:
        super().__init__(
            backend,
            confirmation_count=confirmation_count,
            confirmation_window_seconds=confirmation_window_seconds,
        )
        if not 0 <= minimum_separation <= 1:
            raise ValueError("identity minimum profile separation must be between 0 and 1")
        self.profiles_provider = profile_provider
        self.minimum_separation = minimum_separation
        self._profile_pending: dict[tuple[int, str], _PendingMatch] = {}

    def _profiles(self) -> list[dict[str, Any]]:
        values = self.profiles_provider() if self.profiles_provider else []
        if not isinstance(values, list):
            raise RuntimeError("identity profile provider must return a list")
        return [value for value in values if isinstance(value, dict)]

    def resolve(self, image: Any, people: list[dict[str, Any]], evaluated_at: datetime) -> list[dict[str, Any]]:
        now = self._utc(evaluated_at)
        result = self._unresolved(people)
        profiles = self._profiles()
        if not people or not profiles:
            return result
        faces = self.backend.detect_faces(image)
        for index, person in enumerate(people):
            if not person.get("visible", True):
                continue
            matches = [face for face in faces if self._inside(face, person)]
            if len(matches) != 1:
                continue
            extracted = self.backend.accepted_embedding(image, matches[0])
            if extracted is None:
                continue
            query, quality = extracted
            scores: list[tuple[float, float, dict[str, Any]]] = []
            try:
                for profile in profiles:
                    threshold = float(profile.get("calibrated_threshold", self.match_threshold))
                    if not 0 <= threshold <= 1:
                        raise RuntimeError("stored identity threshold is invalid")
                    score = float(self.backend.recognizer.match(
                        query, profile["prototype"], self.backend._cv2.FaceRecognizerSF_FR_COSINE,
                    ))
                    scores.append((score, threshold, profile))
            except Exception as exc:
                raise RuntimeError(f"SFace similarity comparison failed: {exc}") from exc
            scores.sort(key=lambda item: item[0], reverse=True)
            top_score, threshold, top_profile = scores[0]
            second_score, second_threshold, _second_profile = (
                scores[1] if len(scores) > 1 else (-1.0, 1.0, {})
            )
            track_id = int(person.get("track_id", -1))
            if top_score < threshold:
                self._profile_pending = {
                    key: pending for key, pending in self._profile_pending.items() if key[0] != track_id
                }
                result[index].update({
                    "identity_state": "unknown",
                    "identity_confidence": round(max(0.0, min(1.0, top_score)), 4),
                    "face_quality": quality,
                })
                continue
            if second_score >= second_threshold and top_score - second_score < self.minimum_separation:
                self._profile_pending = {
                    key: pending for key, pending in self._profile_pending.items() if key[0] != track_id
                }
                result[index].update({
                    "identity_state": "unresolved",
                    "identity_confidence": round(max(0.0, min(1.0, top_score)), 4),
                    "face_quality": quality,
                })
                continue
            person_id = str(top_profile.get("person_id") or "")
            if not person_id:
                raise RuntimeError("stored identity profile is missing person_id")
            key = (track_id, person_id)
            pending = self._profile_pending.get(key)
            if pending is None or (now - pending.last_at).total_seconds() > self.confirmation_window_seconds:
                pending = _PendingMatch(now, now, 1)
            else:
                pending.last_at = now
                pending.count += 1
            self._profile_pending = {
                other_key: other_pending
                for other_key, other_pending in self._profile_pending.items()
                if other_key[0] != track_id or other_key == key
            }
            self._profile_pending[key] = pending
            if pending.count >= self.confirmation_count:
                result[index].update({
                    "person_id": person_id,
                    "display_name": str(top_profile.get("display_name") or person_id),
                    "identity_state": "recognized",
                    "identity_confidence": round(max(0.0, min(1.0, top_score)), 4),
                    "face_quality": quality,
                })
            else:
                result[index].update({
                    "identity_state": "unresolved",
                    "identity_confidence": round(max(0.0, min(1.0, top_score)), 4),
                    "face_quality": quality,
                })
        return result


def identity_config_from_mapping(values: dict[str, Any] | None) -> dict[str, Any]:
    values = values or {}
    if not isinstance(values, dict):
        raise ValueError("identity must be an object")
    result = dict(values)
    result["enabled"] = bool(values.get("enabled", False))
    result["cadence_seconds"] = float(values.get("cadence_seconds", 0.5))
    result["match_threshold"] = float(values.get("match_threshold", 0.45))
    result["minimum_profile_separation"] = float(values.get("minimum_profile_separation", 0.05))
    result["confirmation_count"] = int(values.get("confirmation_count", 3))
    result["confirmation_window_seconds"] = float(values.get("confirmation_window_seconds", 2.0))
    if result["cadence_seconds"] <= 0 or result["confirmation_count"] <= 0 or result["confirmation_window_seconds"] <= 0:
        raise ValueError("identity cadence and confirmation settings must be positive")
    if not 0 <= result["match_threshold"] <= 1:
        raise ValueError("identity.match_threshold must be between 0 and 1")
    if not 0 <= result["minimum_profile_separation"] <= 1:
        raise ValueError("identity.minimum_profile_separation must be between 0 and 1")
    FaceQualityConfig.from_mapping(values.get("quality"))
    if result["enabled"] and (not values.get("yunet_model") or not values.get("sface_model")):
        raise ValueError("enabled identity requires identity.yunet_model and identity.sface_model")
    return result
