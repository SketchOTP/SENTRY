"""Bounded National Weather Service context for SENTRY.

The provider returns normalized metadata only.  It never supplies physical
presence evidence and it never invokes Codex/Luna.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


NWS_BASE_URL = "https://api.weather.gov"
DEFAULT_USER_AGENT = "SENTRY/0.2 (https://github.com/SketchOTP/SENTRY)"


class WeatherError(RuntimeError):
    """Base class for bounded weather failures."""


class WeatherLocationRequired(WeatherError):
    """Raised when production weather coordinates are not configured."""


class WeatherProviderError(WeatherError):
    """Raised when the provider cannot produce a structurally valid result."""


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _bounded_text(value: Any, limit: int = 800) -> str | None:
    if not isinstance(value, str):
        return None
    value = " ".join(value.split())
    return value[:limit] if value else None


def _alert_identifier(value: Any) -> str | None:
    """Keep an alert identifier without retaining a provider URL."""

    text = _bounded_text(value, 240)
    if text is None:
        return None
    parsed = urlparse(text)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        tail = parsed.path.rstrip("/").rsplit("/", 1)[-1]
        return _bounded_text(tail, 240)
    return text


def _property(properties: dict[str, Any], key: str) -> Any:
    return properties.get(key)


@dataclass(frozen=True)
class WeatherConfig:
    enabled: bool = False
    provider: str = "nws"
    location_label: str = "home"
    latitude: float | None = None
    longitude: float | None = None
    timezone: str = "America/New_York"
    refresh_interval_seconds: int = 600
    freshness_limit_seconds: int = 1800
    point_cache_seconds: int = 86400
    retry_count: int = 2

    @classmethod
    def from_mapping(cls, value: Any) -> "WeatherConfig":
        if value is None:
            return cls()
        if not isinstance(value, dict):
            raise ValueError("weather configuration must be an object")
        raw_lat = value.get("latitude")
        raw_lon = value.get("longitude")
        latitude = float(raw_lat) if raw_lat is not None else None
        longitude = float(raw_lon) if raw_lon is not None else None
        if latitude is not None and not -90 <= latitude <= 90:
            raise ValueError("weather latitude must be between -90 and 90")
        if longitude is not None and not -180 <= longitude <= 180:
            raise ValueError("weather longitude must be between -180 and 180")
        result = cls(
            enabled=bool(value.get("enabled", False)),
            provider=str(value.get("provider", "nws")),
            location_label=str(value.get("location_label", "home")),
            latitude=latitude,
            longitude=longitude,
            timezone=str(value.get("timezone", "America/New_York")),
            refresh_interval_seconds=int(value.get("refresh_interval_seconds", 600)),
            freshness_limit_seconds=int(value.get("freshness_limit_seconds", 1800)),
            point_cache_seconds=int(value.get("point_cache_seconds", 86400)),
            retry_count=int(value.get("retry_count", 2)),
        )
        if result.provider != "nws":
            raise ValueError("only the nws weather provider is supported")
        if not result.location_label:
            raise ValueError("weather location_label must not be empty")
        try:
            ZoneInfo(result.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("weather timezone must be a valid IANA timezone") from exc
        if result.refresh_interval_seconds <= 0 or result.freshness_limit_seconds <= 0:
            raise ValueError("weather refresh and freshness values must be positive")
        if result.point_cache_seconds <= 0 or result.retry_count < 0 or result.retry_count > 4:
            raise ValueError("weather cache/retry values are invalid")
        return result

    def require_location(self) -> tuple[float, float]:
        if self.latitude is None or self.longitude is None:
            raise WeatherLocationRequired("WEATHER LOCATION CONFIG REQUIRED")
        return self.latitude, self.longitude


class WeatherProvider:
    def refresh(self, config: WeatherConfig, *, previous: dict[str, Any] | None = None) -> dict[str, Any]:
        raise NotImplementedError


class NWSWeatherProvider(WeatherProvider):
    """Small NWS adapter with bounded retry and point-resource caching."""

    def __init__(
        self,
        *,
        user_agent: str = DEFAULT_USER_AGENT,
        fetch_json: Callable[[str], dict[str, Any]] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], datetime] | None = None,
        base_url: str = NWS_BASE_URL,
    ) -> None:
        self.user_agent = user_agent
        self._fetch_json_override = fetch_json
        self._sleep = sleep
        self._now = now or (lambda: datetime.now(timezone.utc))
        self.base_url = base_url.rstrip("/")

    def _fetch_json(self, url: str, *, retry_count: int) -> dict[str, Any]:
        if self._fetch_json_override is not None:
            value = self._fetch_json_override(url)
            if not isinstance(value, dict):
                raise WeatherProviderError(f"NWS response was not an object: {url}")
            return value
        last_error: Exception | None = None
        for attempt in range(retry_count + 1):
            try:
                request = Request(
                    url,
                    headers={
                        "Accept": "application/geo+json, application/json",
                        "User-Agent": self.user_agent,
                    },
                )
                with urlopen(request, timeout=15) as response:  # noqa: S310 - fixed NWS endpoint
                    value = json.loads(response.read().decode("utf-8"))
                if not isinstance(value, dict):
                    raise WeatherProviderError(f"NWS response was not an object: {url}")
                return value
            except HTTPError as exc:
                last_error = exc
                retryable = exc.code == 429 or 500 <= exc.code <= 599
                if not retryable or attempt >= retry_count:
                    raise WeatherProviderError(f"NWS HTTP {exc.code} for {url}") from exc
            except (OSError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt >= retry_count:
                    raise WeatherProviderError(f"NWS request failed for {url}: {type(exc).__name__}") from exc
            self._sleep(min(2.0, 0.25 * (2**attempt)))
        raise WeatherProviderError(f"NWS request failed for {url}: {type(last_error).__name__ if last_error else 'unknown'}")

    def _url(self, path: str) -> str:
        return path if path.startswith("http") else f"{self.base_url}/{path.lstrip('/') }"

    def _cached_points(self, previous: dict[str, Any] | None, now: datetime, config: WeatherConfig) -> dict[str, Any] | None:
        if not previous:
            return None
        metadata = previous.get("source_metadata")
        if not isinstance(metadata, dict):
            return None
        points = metadata.get("points")
        cached_at = _parse_time(points.get("points_fetched_at")) if isinstance(points, dict) else None
        if cached_at is None or not isinstance(points, dict):
            return None
        if now - cached_at > timedelta(seconds=config.point_cache_seconds):
            return None
        return points

    def _points(self, latitude: float, longitude: float, config: WeatherConfig, previous: dict[str, Any] | None, now: datetime) -> tuple[dict[str, Any], str]:
        cached = self._cached_points(previous, now, config)
        if cached is not None:
            return cached, "cached"
        url = self._url(f"points/{latitude:.5f},{longitude:.5f}")
        payload = self._fetch_json(url, retry_count=config.retry_count)
        properties = payload.get("properties")
        if not isinstance(properties, dict):
            raise WeatherProviderError("NWS points response omitted properties")
        required = ("forecastHourly", "observationStations")
        if not all(isinstance(properties.get(key), str) and properties.get(key) for key in required):
            raise WeatherProviderError("NWS points response omitted required resources")
        points = {
            "grid_id": properties.get("gridId"),
            "grid_x": properties.get("gridX"),
            "grid_y": properties.get("gridY"),
            "forecast": properties.get("forecast"),
            "forecast_hourly": properties.get("forecastHourly"),
            "observation_stations": properties.get("observationStations"),
            "points_url": url,
            "points_fetched_at": _iso(now),
        }
        return points, "fresh"

    @staticmethod
    def _normalize_observation(payload: dict[str, Any]) -> tuple[dict[str, Any], str | None, str | None]:
        properties = payload.get("properties")
        if not isinstance(properties, dict):
            raise WeatherProviderError("NWS observation response omitted properties")
        observed_at = properties.get("timestamp")
        current = {
            "observed_at": observed_at,
            "temperature": {"value": properties.get("temperature", {}).get("value"), "unit": properties.get("temperature", {}).get("unitCode")} if isinstance(properties.get("temperature"), dict) else None,
            "apparent_temperature": {"value": properties.get("heatIndex", {}).get("value"), "unit": properties.get("heatIndex", {}).get("unitCode")} if isinstance(properties.get("heatIndex"), dict) and properties.get("heatIndex", {}).get("value") is not None else None,
            "wind_chill": {"value": properties.get("windChill", {}).get("value"), "unit": properties.get("windChill", {}).get("unitCode")} if isinstance(properties.get("windChill"), dict) and properties.get("windChill", {}).get("value") is not None else None,
            "relative_humidity": properties.get("relativeHumidity", {}).get("value") if isinstance(properties.get("relativeHumidity"), dict) else None,
            "wind_speed": properties.get("windSpeed", {}).get("value") if isinstance(properties.get("windSpeed"), dict) else None,
            "wind_direction": properties.get("windDirection", {}).get("value") if isinstance(properties.get("windDirection"), dict) else None,
            "weather_description": _bounded_text(properties.get("textDescription"), 240),
        }
        return current, observed_at if isinstance(observed_at, str) else None, properties.get("stationIdentifier")

    @staticmethod
    def _normalize_forecast(payload: dict[str, Any], now: datetime) -> tuple[list[dict[str, Any]], str | None]:
        properties = payload.get("properties")
        periods = properties.get("periods") if isinstance(properties, dict) else None
        if not isinstance(periods, list):
            raise WeatherProviderError("NWS hourly forecast response omitted periods")
        # Keep enough bounded hourly evidence to answer a normal local-day
        # "tomorrow" request even late in the evening, without exposing the
        # full multi-day NWS feed to the conversation layer.
        end = now + timedelta(hours=48)
        normalized = []
        for period in periods:
            if not isinstance(period, dict):
                continue
            start = _parse_time(period.get("startTime"))
            if start is None or start > end:
                continue
            normalized.append({
                "start": period.get("startTime"),
                "end": period.get("endTime"),
                "temperature": period.get("temperature"),
                "temperature_unit": period.get("temperatureUnit"),
                "precipitation_probability": (period.get("probabilityOfPrecipitation") or {}).get("value") if isinstance(period.get("probabilityOfPrecipitation"), dict) else None,
                "wind_speed": _bounded_text(period.get("windSpeed"), 80),
                "wind_direction": _bounded_text(period.get("windDirection"), 30),
                "short_forecast": _bounded_text(period.get("shortForecast"), 240),
            })
        return normalized, properties.get("generatedAt") if isinstance(properties, dict) else None

    @staticmethod
    def _normalize_alerts(payload: dict[str, Any]) -> list[dict[str, Any]]:
        features = payload.get("features")
        if not isinstance(features, list):
            raise WeatherProviderError("NWS alerts response omitted features")
        alerts = []
        for feature in features:
            properties = feature.get("properties") if isinstance(feature, dict) else None
            if not isinstance(properties, dict):
                continue
            alerts.append({
                "id": _alert_identifier(feature.get("id") or properties.get("id")),
                "event": _bounded_text(properties.get("event"), 120),
                "severity": properties.get("severity"),
                "urgency": properties.get("urgency"),
                "certainty": properties.get("certainty"),
                "effective": properties.get("effective"),
                "onset": properties.get("onset"),
                "expires": properties.get("expires"),
                "ends": properties.get("ends"),
                "headline": _bounded_text(properties.get("headline"), 240),
                "description": _bounded_text(properties.get("description")),
                "instruction": _bounded_text(properties.get("instruction")),
            })
        return alerts

    def refresh(self, config: WeatherConfig, *, previous: dict[str, Any] | None = None) -> dict[str, Any]:
        if not config.enabled:
            raise WeatherProviderError("weather is disabled")
        latitude, longitude = config.require_location()
        now = self._now().astimezone(timezone.utc)
        points, points_status = self._points(latitude, longitude, config, previous, now)
        hourly_url = points.get("forecast_hourly")
        stations_url = points.get("observation_stations")
        if not isinstance(hourly_url, str) or not isinstance(stations_url, str):
            raise WeatherProviderError("NWS point resources are invalid")
        hourly_payload = self._fetch_json(hourly_url, retry_count=config.retry_count)
        hourly, generated_at = self._normalize_forecast(hourly_payload, now)
        source_errors: list[str] = []
        current: dict[str, Any] = {}
        station_id: str | None = None
        try:
            stations = self._fetch_json(stations_url, retry_count=config.retry_count)
            station_features = stations.get("features")
            station_url = station_features[0].get("id") if isinstance(station_features, list) and station_features and isinstance(station_features[0], dict) else None
            if not isinstance(station_url, str):
                raise WeatherProviderError("NWS station list contained no station")
            observation = self._fetch_json(f"{station_url.rstrip('/')}/observations/latest", retry_count=config.retry_count)
            current, _observed_at, station_id = self._normalize_observation(observation)
        except WeatherError as exc:
            source_errors.append(f"observation:{exc}")
        alerts: list[dict[str, Any]] = []
        alerts_url = self._url(f"alerts/active?point={latitude:.5f},{longitude:.5f}")
        try:
            alerts = self._normalize_alerts(self._fetch_json(alerts_url, retry_count=config.retry_count))
        except WeatherError as exc:
            source_errors.append(f"alerts:{exc}")
        source_metadata = {
            "provider": "nws",
            "points": points,
            "points_cache_status": points_status,
            "station_id": station_id,
            "alerts_url": alerts_url,
            "component_errors": source_errors,
        }
        source_updated = next((value for value in (current.get("observed_at"), generated_at) if isinstance(value, str)), None)
        fingerprint_payload = {"current": current, "hourly": hourly, "alerts": alerts, "source_metadata": source_metadata}
        fingerprint = hashlib.sha256(json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return {
            "provider": "nws",
            "location_label": config.location_label,
            "latitude": latitude,
            "longitude": longitude,
            "timezone": config.timezone,
            "fetched_at": _iso(now),
            "source_updated_at": source_updated,
            "fresh_until": _iso(now + timedelta(seconds=config.freshness_limit_seconds)),
            "current": current,
            "hourly": hourly,
            "alerts": alerts,
            "source_metadata": source_metadata,
            "source_fingerprint": fingerprint,
        }
