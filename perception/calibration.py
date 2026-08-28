"""Offline threshold evaluation for raw, metadata-only detector observations."""

from __future__ import annotations

import math
import statistics
from datetime import datetime, timedelta
from typing import Any, Iterable


DEFAULT_THRESHOLDS = tuple(round(value / 100, 2) for value in range(10, 91, 5))
ASYMMETRIC_SUPPORT_THRESHOLDS = tuple(round(value / 100, 2) for value in range(10, 41, 5))


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


def _false_runs(values: list[bool], timestamps: list[datetime]) -> list[float]:
    intervals = [
        (timestamps[index + 1] - timestamps[index]).total_seconds()
        for index in range(len(timestamps) - 1)
        if timestamps[index + 1] > timestamps[index]
    ]
    interval = statistics.median(intervals) if intervals else 0.0
    runs: list[float] = []
    start: int | None = None
    for index, value in enumerate(values + [False]):
        if value and start is None:
            start = index
        if not value and start is not None:
            end = index - 1
            runs.append((timestamps[end] - timestamps[start]).total_seconds() + interval)
            start = None
    return [round(value, 3) for value in runs]


def _raw_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    confidences = [
        float(candidate["confidence"])
        for record in records
        for candidate in record.get("candidates", [])
    ]
    return {
        "total_observations": len(records),
        "observations_with_candidates": sum(bool(record.get("candidates")) for record in records),
        "candidate_count": len(confidences),
        "confidence_percentiles": {
            "p50": _percentile(confidences, 0.50),
            "p75": _percentile(confidences, 0.75),
            "p90": _percentile(confidences, 0.90),
            "p95": _percentile(confidences, 0.95),
            "max": max(confidences, default=None),
        },
    }


def _simulate_occupied_segment(
    records: list[dict[str, Any]],
    entry_threshold: float,
    support_threshold: float,
) -> dict[str, Any]:
    """Simulate state policy for a continuously occupied labeled segment."""

    from .presence_state import PresenceStateConfig, PresenceStateMachine, RoomState

    ordered = sorted(records, key=lambda record: record["captured_at"])
    machine = PresenceStateMachine(PresenceStateConfig())
    states: list[str] = []
    transitions: list[str] = []
    support: list[bool] = []
    strong: list[bool] = []
    timestamps: list[datetime] = []
    for record in ordered:
        now = _parse_timestamp(record["captured_at"])
        timestamps.append(now)
        confidences = [float(candidate["confidence"]) for candidate in record.get("candidates", [])]
        is_strong = any(value >= entry_threshold for value in confidences)
        is_support = any(value >= support_threshold for value in confidences)
        snapshot = machine.update(
            now,
            camera_state="online",
            entry_evidence=is_strong,
            support_evidence=is_support,
        )
        strong.append(is_strong)
        support.append(is_support)
        states.append(snapshot.state.value)
        if snapshot.transition:
            transitions.append(snapshot.transition)
    gaps = _false_runs([not value for value in support], timestamps)
    return {
        "total_observations": len(states),
        "support_evidence_observations": sum(support),
        "support_evidence_rate": round(sum(support) / len(support), 6) if support else 0.0,
        "strong_evidence_observations": sum(strong),
        "longest_support_evidence_gap_seconds": max(gaps, default=0.0),
        "support_gaps_over_1s": sum(gap > 1.0 for gap in gaps),
        "support_gaps_over_5s": sum(gap > 5.0 for gap in gaps),
        "support_gaps_over_15s": sum(gap >= 15.0 for gap in gaps),
        "authoritative_occupied_observations": sum(state == RoomState.OCCUPIED.value for state in states),
        "authoritative_occupied_correctness": round(
            sum(state == RoomState.OCCUPIED.value for state in states) / len(states), 6
        ) if states else 0.0,
        "false_empty_transition": "occupied->empty" in transitions,
        "transitions": transitions,
    }


def _simulate_post_exit(
    records: list[dict[str, Any]],
    entry_threshold: float,
    support_threshold: float,
) -> dict[str, Any]:
    """Simulate departure at the first labeled empty observation."""

    from .presence_state import PresenceStateConfig, PresenceStateMachine, RoomState

    ordered = sorted(records, key=lambda record: record["captured_at"])
    if not ordered:
        return {
            "total_observations": 0,
            "support_false_positive_observations": 0,
            "longest_false_support_run_seconds": 0.0,
            "maximum_interval_between_false_support_candidates_seconds": None,
            "simulated_empty_seconds": None,
            "reaches_empty_within_25s": False,
        }
    config = PresenceStateConfig()
    first_time = _parse_timestamp(ordered[0]["captured_at"])
    machine = PresenceStateMachine(config)
    # Seed an already-authoritative occupied state immediately before the
    # labeled post-departure interval, then measure when it reaches empty.
    seed_time = first_time - timedelta(seconds=config.entry_confirmation_seconds + 1.0)
    machine.update(seed_time, camera_state="online", entry_evidence=True, support_evidence=True)
    machine.update(first_time - timedelta(seconds=0.5), camera_state="online", entry_evidence=True, support_evidence=True)
    support: list[bool] = []
    timestamps: list[datetime] = []
    empty_at: datetime | None = None
    for index, record in enumerate(ordered):
        now = _parse_timestamp(record["captured_at"])
        confidences = [float(candidate["confidence"]) for candidate in record.get("candidates", [])]
        is_strong = any(value >= entry_threshold for value in confidences)
        is_support = any(value >= support_threshold for value in confidences)
        snapshot = machine.update(
            now,
            camera_state="online",
            entry_evidence=is_strong,
            support_evidence=is_support,
        )
        support.append(is_support)
        timestamps.append(now)
        if empty_at is None and snapshot.state == RoomState.EMPTY:
            empty_at = now
    gaps = _false_runs(support, timestamps)
    support_times = [timestamp for timestamp, has_support in zip(timestamps, support) if has_support]
    intervals = [
        (support_times[index + 1] - support_times[index]).total_seconds()
        for index in range(len(support_times) - 1)
        if support_times[index + 1] > support_times[index]
    ]
    simulated_empty_seconds = (
        round((empty_at - first_time).total_seconds(), 3) if empty_at is not None else None
    )
    return {
        "total_observations": len(ordered),
        "support_false_positive_observations": sum(support),
        "longest_false_support_run_seconds": max(gaps, default=0.0),
        "maximum_interval_between_false_support_candidates_seconds": round(max(intervals), 3) if intervals else None,
        "simulated_empty_seconds": simulated_empty_seconds,
        "reaches_empty_within_25s": simulated_empty_seconds is not None and simulated_empty_seconds <= 25.0,
    }


def evaluate_asymmetric_thresholds(
    records: Iterable[dict[str, Any]],
    *,
    entry_threshold: float = 0.40,
    support_thresholds: Iterable[float] = ASYMMETRIC_SUPPORT_THRESHOLDS,
) -> dict[str, Any]:
    """Sweep hold thresholds using one captured empty/person evidence set."""

    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(str(record["segment"]), []).append(record)
    empty = grouped.get("empty", [])
    occupied = grouped.get("one_person", grouped.get("occupied", []))
    threshold_results: dict[str, Any] = {}
    for threshold in support_thresholds:
        value = round(float(threshold), 2)
        key = f"{value:.2f}"
        occupied_result = _simulate_occupied_segment(occupied, entry_threshold, value)
        exit_result = _simulate_post_exit(empty, entry_threshold, value)
        threshold_results[key] = {
            "occupied": occupied_result,
            "post_exit_empty": exit_result,
            "qualifies": (
                occupied_result["authoritative_occupied_correctness"] >= 0.95
                and not occupied_result["false_empty_transition"]
                and exit_result["reaches_empty_within_25s"]
            ),
        }
    return {
        "entry_threshold": round(float(entry_threshold), 2),
        "empty_raw": _raw_summary(empty),
        "occupied_raw": _raw_summary(occupied),
        "thresholds": threshold_results,
        "qualifying_support_thresholds": [
            threshold for threshold, result in threshold_results.items() if result["qualifies"]
        ],
    }


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
