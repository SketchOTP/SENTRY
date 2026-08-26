"""Offline threshold evaluation for raw, metadata-only detector observations."""

from __future__ import annotations

import math
import statistics
from datetime import datetime
from typing import Any, Iterable


DEFAULT_THRESHOLDS = tuple(round(value / 100, 2) for value in range(10, 91, 5))


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return round(ordered[lower], 6)
    fraction = position - lower
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction, 6)


def _longest_run(values: list[bool], timestamps: list[datetime]) -> tuple[int, float]:
    best_count = 0
    best_seconds = 0.0
    current_start: int | None = None
    intervals = [
        (timestamps[index + 1] - timestamps[index]).total_seconds()
        for index in range(len(timestamps) - 1)
        if timestamps[index + 1] > timestamps[index]
    ]
    interval = statistics.median(intervals) if intervals else 0.0
    for index, value in enumerate(values + [False]):
        if value and current_start is None:
            current_start = index
        if not value and current_start is not None:
            end = index - 1
            count = end - current_start + 1
            seconds = (timestamps[end] - timestamps[current_start]).total_seconds() + interval
            if count > best_count or (count == best_count and seconds > best_seconds):
                best_count = count
                best_seconds = seconds
            current_start = None
    return best_count, round(best_seconds, 3)


def evaluate_thresholds(
    records: Iterable[dict[str, Any]],
    thresholds: Iterable[float] = DEFAULT_THRESHOLDS,
) -> dict[str, dict[str, dict[str, Any]]]:
    """Evaluate all thresholds from the same raw candidate records.

    Records must contain ``segment``, ``captured_at``, and a ``candidates``
    list with ``confidence`` values. The function never accesses image data.
    """

    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(str(record["segment"]), []).append(record)
    results: dict[str, dict[str, dict[str, Any]]] = {}
    for segment, segment_records in grouped.items():
        segment_records.sort(key=lambda record: record["captured_at"])
        timestamps = [_parse_timestamp(record["captured_at"]) for record in segment_records]
        raw_confidences = [
            float(candidate["confidence"])
            for record in segment_records
            for candidate in record.get("candidates", [])
        ]
        segment_result: dict[str, dict[str, Any]] = {}
        for threshold in thresholds:
            threshold_value = round(float(threshold), 2)
            counts = [
                sum(float(candidate["confidence"]) >= threshold_value for candidate in record.get("candidates", []))
                for record in segment_records
            ]
            misses = [count == 0 for count in counts]
            # In the confirmed-empty segment any detection is false-positive
            # evidence. In the confirmed-one-person segment, a multi-box
            # observation is the corresponding duplicate/phantom evidence.
            false_positive = [count > 0 for count in counts] if segment == "empty" else [count > 1 for count in counts]
            miss_count, miss_seconds = _longest_run(misses, timestamps)
            false_count, false_seconds = _longest_run(false_positive, timestamps)
            key = f"{threshold_value:.2f}"
            segment_result[key] = {
                "total_observations": len(counts),
                "zero_detections": sum(count == 0 for count in counts),
                "exactly_one_detection": sum(count == 1 for count in counts),
                "more_than_one_detection": sum(count > 1 for count in counts),
                "any_detection_rate": round(sum(count > 0 for count in counts) / len(counts), 6) if counts else 0.0,
                "duplicate_detection_rate": round(sum(count > 1 for count in counts) / len(counts), 6) if counts else 0.0,
                "maximum_simultaneous_detections": max(counts, default=0),
                "longest_consecutive_miss_observations": miss_count,
                "longest_consecutive_miss_seconds": miss_seconds,
                "longest_consecutive_false_positive_observations": false_count,
                "longest_consecutive_false_positive_seconds": false_seconds,
                "raw_confidence_percentiles": {
                    "p50": _percentile(raw_confidences, 0.50),
                    "p75": _percentile(raw_confidences, 0.75),
                    "p90": _percentile(raw_confidences, 0.90),
                    "p95": _percentile(raw_confidences, 0.95),
                    "max": max(raw_confidences, default=None),
                },
            }
        results[segment] = segment_result
    return results
