"""Transparent, metadata-only routine statistics for trusted SENTRY history."""

from __future__ import annotations

import hashlib
import json
import math
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from statistics import median
from zoneinfo import ZoneInfo


ALGORITHM_VERSION = "routine-statistics-v1"
ROUTINE_TYPES = (
    "office_session_start_time",
    "office_session_duration",
    "office_absence_between_sessions",
    "primary_user_session_first_confirmed_time",
)
SCOPES = ("all_days", "weekday", "weekend", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
INTERRUPTION_EVENTS = {
    "system.started",
    "system.stopped",
    "room.camera_degraded",
    "room.camera_offline",
}


@dataclass(frozen=True)
class RoutineConfig:
    timezone: str = "America/New_York"
    lookback_days: int = 56
    minimum_observed_samples: int = 5
    minimum_stable_samples: int = 8
    minimum_observed_distinct_dates: int = 5
    minimum_stable_distinct_dates: int = 8
    clock_stable_resultant_length: float = 0.80
    duration_stable_relative_mad: float = 0.35

    @classmethod
    def from_mapping(cls, mapping: dict | None) -> "RoutineConfig":
        values = mapping or {}
        result = cls(
            timezone=str(values.get("timezone", cls.timezone)),
            lookback_days=int(values.get("lookback_days", cls.lookback_days)),
            minimum_observed_samples=int(values.get("minimum_observed_samples", cls.minimum_observed_samples)),
            minimum_stable_samples=int(values.get("minimum_stable_samples", cls.minimum_stable_samples)),
            minimum_observed_distinct_dates=int(values.get("minimum_observed_distinct_dates", cls.minimum_observed_distinct_dates)),
            minimum_stable_distinct_dates=int(values.get("minimum_stable_distinct_dates", cls.minimum_stable_distinct_dates)),
            clock_stable_resultant_length=float(values.get("clock_stable_resultant_length", cls.clock_stable_resultant_length)),
            duration_stable_relative_mad=float(values.get("duration_stable_relative_mad", cls.duration_stable_relative_mad)),
        )
        try:
            ZoneInfo(result.timezone)
        except Exception as exc:
            raise ValueError(f"invalid IANA routine timezone: {result.timezone}") from exc
        if result.lookback_days <= 0:
            raise ValueError("routine lookback_days must be positive")
        if result.minimum_observed_samples <= 0 or result.minimum_stable_samples < result.minimum_observed_samples:
            raise ValueError("routine sample thresholds are invalid")
        if result.minimum_observed_distinct_dates <= 0 or result.minimum_stable_distinct_dates < result.minimum_observed_distinct_dates:
            raise ValueError("routine distinct-date thresholds are invalid")
        if not 0 <= result.clock_stable_resultant_length <= 1 or result.duration_stable_relative_mad < 0:
            raise ValueError("routine consistency thresholds are invalid")
        return result


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"timestamp must include timezone: {value}")
    return parsed.astimezone(timezone.utc)


def _scope_for(local_time: datetime) -> tuple[str, ...]:
    day = local_time.strftime("%A").lower()
    return ("all_days", "weekday" if local_time.weekday() < 5 else "weekend", day)


def _quantile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("quantile requires values")
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    return float(ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower))


def robust_statistics(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {}
    med = float(median(values))
    mad = float(median([abs(value - med) for value in values]))
    return {
        "median": med,
        "mad": mad,
        "p25": _quantile(values, 0.25),
        "p75": _quantile(values, 0.75),
        "minimum": float(min(values)),
        "maximum": float(max(values)),
        "relative_mad": mad / med if med > 0 else None,
    }


def circular_statistics(seconds: list[float]) -> dict[str, float | str]:
    if not seconds:
        return {}
    angles = [value / 86400.0 * 2.0 * math.pi for value in seconds]
    mean_sin = sum(math.sin(angle) for angle in angles) / len(angles)
    mean_cos = sum(math.cos(angle) for angle in angles) / len(angles)
    resultant = min(1.0, math.sqrt(mean_sin * mean_sin + mean_cos * mean_cos))
    center_angle = math.atan2(mean_sin, mean_cos) % (2.0 * math.pi)
    center_seconds = (center_angle / (2.0 * math.pi) * 86400.0) % 86400.0
    whole_seconds = int(round(center_seconds)) % 86400
    hours, remainder = divmod(whole_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return {
        "circular_center_seconds": center_seconds,
        "circular_center_local_time": f"{hours:02d}:{minutes:02d}:{secs:02d}",
        "mean_resultant_length": resultant,
        "circular_dispersion": 1.0 - resultant,
    }


def maturity(sample_count: int, distinct_date_count: int, stats: dict, routine_type: str, config: RoutineConfig) -> str:
    if sample_count < config.minimum_observed_samples or distinct_date_count < config.minimum_observed_distinct_dates:
        return "insufficient"
    if sample_count < config.minimum_stable_samples or distinct_date_count < config.minimum_stable_distinct_dates:
        return "observed"
    if routine_type in {"office_session_start_time", "primary_user_session_first_confirmed_time"}:
        return "stable" if stats.get("mean_resultant_length", 0.0) >= config.clock_stable_resultant_length else "observed"
    relative_mad = stats.get("relative_mad")
    return "stable" if relative_mad is not None and relative_mad <= config.duration_stable_relative_mad else "observed"


def _event_payload(event: dict) -> dict:
    payload = event.get("payload", {})
    return payload if isinstance(payload, dict) else {}


def _source_fingerprint(source: dict, config: RoutineConfig, window_start: datetime, window_end: datetime) -> str:
    canonical = {
        "algorithm_version": ALGORITHM_VERSION,
        "config": asdict(config),
        "sessions": source["sessions"],
        "events": source["events"],
    }
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _source_as_of(source: dict, window_start: datetime) -> str:
    timestamps: list[datetime] = []
    for session in source["sessions"]:
        for key in ("started_at", "ended_at"):
            if session.get(key):
                timestamps.append(_parse_utc(session[key]))
    for event in source["events"]:
        if event.get("occurred_at"):
            timestamps.append(_parse_utc(event["occurred_at"]))
    return max(timestamps, default=window_start).isoformat()


def _exclusion_counts(sessions: list[dict], events: list[dict], window_start: datetime, window_end: datetime) -> dict[str, int]:
    result = {"uncertain_end": 0, "restart_reconciled": 0, "camera_interruption": 0, "system_interruption": 0, "missing_session": 0, "outside_window": 0}
    for session in sessions:
        if session.get("status") != "completed" or not session.get("ended_at"):
            result["missing_session"] += 1
        if session.get("end_time_uncertain") or session.get("end_reason") == "restart_reconciled":
            result["uncertain_end"] += 1
        if session.get("end_reason") == "restart_reconciled" or session.get("recovered_after_restart"):
            result["restart_reconciled"] += 1
        try:
            started = _parse_utc(session["started_at"])
            if started < window_start or started > window_end:
                result["outside_window"] += 1
        except (KeyError, ValueError):
            result["outside_window"] += 1
    for event in events:
        if event.get("event_type") in INTERRUPTION_EVENTS:
            bucket = "camera_interruption" if str(event["event_type"]).startswith("room.camera_") else "system_interruption"
            result[bucket] += 1
    return result


def _interval_has_interruption(events: list[dict], end: datetime, start: datetime) -> bool:
    return any(
        event.get("event_type") in INTERRUPTION_EVENTS
        and end < _parse_utc(event["occurred_at"]) < start
        for event in events
    )


def _samples(source: dict, config: RoutineConfig, window_start: datetime, window_end: datetime) -> tuple[dict[str, list[dict]], dict[str, dict[str, int]]]:
    local_zone = ZoneInfo(config.timezone)
    sessions = source["sessions"]
    events = source["events"]
    samples: dict[str, list[dict]] = {routine: [] for routine in ROUTINE_TYPES}
    exclusions: dict[str, dict[str, int]] = {routine: _exclusion_counts(sessions, events, window_start, window_end) for routine in ROUTINE_TYPES}

    for session in sessions:
        try:
            started = _parse_utc(session["started_at"])
        except (KeyError, ValueError):
            continue
        if not window_start <= started <= window_end or session.get("start_reason", "observed") != "observed":
            continue
        local = started.astimezone(local_zone)
        samples["office_session_start_time"].append({"value": local.hour * 3600 + local.minute * 60 + local.second + local.microsecond / 1e6, "local_date": local.date().isoformat()})
        if session.get("status") == "completed" and session.get("ended_at"):
            try:
                ended = _parse_utc(session["ended_at"])
            except ValueError:
                continue
            if session.get("end_reason", "observed") == "observed" and not session.get("end_time_uncertain") and ended >= started:
                samples["office_session_duration"].append({"value": (ended - started).total_seconds(), "local_date": local.date().isoformat()})

    trustworthy_sessions = []
    for session in sessions:
        if session.get("status") != "completed" or session.get("start_reason", "observed") != "observed" or session.get("end_reason") != "observed" or session.get("end_time_uncertain"):
            continue
        try:
            started, ended = _parse_utc(session["started_at"]), _parse_utc(session["ended_at"])
        except (KeyError, TypeError, ValueError):
            continue
        if window_start <= started <= window_end and window_start <= ended <= window_end:
            trustworthy_sessions.append((started, ended, session))
    trustworthy_sessions.sort(key=lambda item: (item[1], item[0], item[2]["session_id"]))
    for previous, current in zip(trustworthy_sessions, trustworthy_sessions[1:]):
        previous_end, current_start = previous[1], current[0]
        if current_start <= previous_end or _interval_has_interruption(events, previous_end, current_start):
            continue
        local = current_start.astimezone(local_zone)
        samples["office_absence_between_sessions"].append({"value": (current_start - previous_end).total_seconds(), "local_date": local.date().isoformat()})

    identity_by_session: dict[int, datetime] = {}
    for event in events:
        if event.get("event_type") != "person.identified" or event.get("session_id") is None:
            continue
        payload = _event_payload(event)
        if payload.get("person_id") != "primary_user":
            continue
        try:
            occurred = _parse_utc(event["occurred_at"])
        except (KeyError, ValueError):
            continue
        session_id = int(event["session_id"])
        if window_start <= occurred <= window_end and (session_id not in identity_by_session or occurred < identity_by_session[session_id]):
            identity_by_session[session_id] = occurred
    session_lookup = {int(session["session_id"]): session for session in sessions}
    for session_id, occurred in identity_by_session.items():
        session = session_lookup.get(session_id)
        if not session:
            continue
        started = _parse_utc(session["started_at"])
        if not window_start <= started <= window_end:
            continue
        local = occurred.astimezone(local_zone)
        samples["primary_user_session_first_confirmed_time"].append({"value": local.hour * 3600 + local.minute * 60 + local.second + local.microsecond / 1e6, "local_date": local.date().isoformat()})
    return samples, exclusions


def _statistic_for(routine_type: str, values: list[float]) -> dict:
    if routine_type in {"office_session_start_time", "primary_user_session_first_confirmed_time"}:
        return circular_statistics(values)
    return robust_statistics(values)


def build_snapshots(source: dict, *, as_of: datetime, config: RoutineConfig, room_id: str = "office") -> list[dict]:
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("routine as_of must be timezone-aware")
    as_of = as_of.astimezone(timezone.utc)
    window_start = as_of - timedelta(days=config.lookback_days)
    samples, exclusions = _samples(source, config, window_start, as_of)
    fingerprint = _source_fingerprint(source, config, window_start, as_of)
    source_as_of = _source_as_of(source, window_start)
    generated_at = datetime.now(timezone.utc).isoformat()
    snapshots = []
    for routine_type in ROUTINE_TYPES:
        for scope in SCOPES:
            scoped = [sample for sample in samples[routine_type] if scope in _scope_for(datetime.fromisoformat(sample["local_date"] + "T12:00:00" ).replace(tzinfo=ZoneInfo(config.timezone)))]
            values = [float(sample["value"]) for sample in scoped]
            stats = _statistic_for(routine_type, values)
            sample_count = len(scoped)
            distinct_dates = len({sample["local_date"] for sample in scoped})
            snapshots.append({
                "snapshot_id": str(uuid.uuid4()),
                "routine_key": f"{routine_type}:{scope}",
                "routine_type": routine_type,
                "scope": scope,
                "room_id": room_id,
                "person_id": "primary_user" if routine_type.startswith("primary_user") else None,
                "timezone": config.timezone,
                "algorithm_version": ALGORITHM_VERSION,
                "window_start": window_start.isoformat(),
                "window_end": as_of.isoformat(),
                "source_as_of": source_as_of,
                "source_fingerprint": fingerprint,
                "generated_at": generated_at,
                "sample_count": sample_count,
                "distinct_date_count": distinct_dates,
                "maturity_status": maturity(sample_count, distinct_dates, stats, routine_type, config),
                "statistics": stats,
                "exclusions": exclusions[routine_type],
            })
    return snapshots
