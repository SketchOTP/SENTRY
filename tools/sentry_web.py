"""Bounded, read-only public-web retrieval for SENTRY conversations.

The model never receives a socket, browser, credentials, or shell.  It selects
one host-owned research operation; this module rejects local/private targets,
does not submit data, and returns small source-attributed text extracts only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import ipaddress
import json
import socket
import xml.etree.ElementTree as ET
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


MAX_URL_LENGTH = 2_048
MAX_QUERY_LENGTH = 240
MAX_RESULTS = 5
MAX_RESPONSE_BYTES = 750_000
MAX_EXCERPT_CHARS = 4_000
USER_AGENT = "SENTRY/0.3 (+local read-only research)"
ALLOWED_CONTENT_TYPES = {"text/html", "text/plain", "application/json", "application/xml", "text/xml"}


class WebResearchError(RuntimeError):
    """A bounded web operation could not safely retrieve a source."""


@dataclass(frozen=True)
class WebDocument:
    url: str
    title: str
    content_type: str
    text: str
    retrieved_at: str
    retrieval_method: str = "page"


@dataclass(frozen=True)
class PublicWeather:
    """A small, source-attributed public forecast result with no coordinates."""

    location: str
    local_date: str
    timezone: str
    summary: str
    temperature_min_f: float | None
    temperature_max_f: float | None
    precipitation_probability_max: int | None
    retrieved_at: str
    source: str = "Open-Meteo"


class _TextExtractor(HTMLParser):
    _SKIP = {"script", "style", "noscript", "svg", "canvas", "template"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._in_title = False
        self.title_parts: list[str] = []
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        tag = tag.lower()
        if tag in self._SKIP:
            self._skip_depth += 1
        if tag == "title" and not self._skip_depth:
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        value = " ".join(data.split())
        if not value:
            return
        if self._in_title:
            self.title_parts.append(value)
        self.parts.append(value)


def _compact(value: str, limit: int) -> str:
    return " ".join(value.split())[:limit]


def _is_public_ip(value: str) -> bool:
    try:
        return ipaddress.ip_address(value).is_global
    except ValueError:
        return False


def validate_public_url(
    value: str,
    *,
    resolver: Callable[..., list[tuple]] = socket.getaddrinfo,
) -> str:
    """Validate a read-only public HTTP(S) target before every connection."""

    if not isinstance(value, str) or not value or len(value) > MAX_URL_LENGTH:
        raise WebResearchError("URL is invalid or too long")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise WebResearchError("URL must be a public HTTP(S) resource")
    try:
        port = parsed.port
    except ValueError as exc:
        raise WebResearchError("URL port is invalid") from exc
    if port not in {None, 80, 443}:
        raise WebResearchError("URL must use the standard HTTP(S) port")
    host = parsed.hostname
    if _is_public_ip(host):
        return value
    if host.replace(".", "").isdigit() or host.lower() == "localhost":
        raise WebResearchError("URL must not target a private network")
    try:
        records = resolver(host, port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except OSError as exc:
        raise WebResearchError("public web host could not be resolved") from exc
    addresses = {item[4][0] for item in records if len(item) >= 5 and item[4]}
    if not addresses or not all(_is_public_ip(address) for address in addresses):
        raise WebResearchError("URL must not target a private network")
    return value


class _SafeRedirectHandler(HTTPRedirectHandler):
    def __init__(self, validate: Callable[[str], str]) -> None:
        super().__init__()
        self._validate = validate

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        self._validate(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class WebResearchClient:
    """Public, source-attributed reading through one bounded host surface."""

    def __init__(
        self,
        *,
        resolver: Callable[..., list[tuple]] = socket.getaddrinfo,
        opener_factory: Callable[..., object] = build_opener,
    ) -> None:
        self._resolver = resolver
        self._opener = opener_factory(_SafeRedirectHandler(self._validate))

    def _validate(self, url: str) -> str:
        return validate_public_url(url, resolver=self._resolver)

    def _fetch(self, url: str) -> tuple[str, str, bytes]:
        """Fetch a bounded public document after validation, without mutation."""

        checked = self._validate(url)
        request = Request(
            checked,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,text/plain,application/json,application/xml,text/xml;q=0.8",
            },
        )
        try:
            with self._opener.open(request, timeout=15) as response:  # type: ignore[attr-defined]
                final_url = self._validate(response.geturl())
                content_type = response.headers.get_content_type().lower()
                if content_type not in ALLOWED_CONTENT_TYPES:
                    raise WebResearchError("web source content type is not readable")
                length = response.headers.get("Content-Length")
                if length and int(length) > MAX_RESPONSE_BYTES:
                    raise WebResearchError("web source is too large")
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except (HTTPError, URLError, OSError, ValueError) as exc:
            raise WebResearchError(f"web source unavailable: {type(exc).__name__}") from exc
        if len(raw) > MAX_RESPONSE_BYTES:
            raise WebResearchError("web source is too large")
        return final_url, content_type, raw

    def read(self, url: str, *, excerpt_limit: int = MAX_EXCERPT_CHARS) -> WebDocument:
        final_url, content_type, raw = self._fetch(url)
        text = raw.decode("utf-8", errors="replace")
        if content_type == "text/html":
            extractor = _TextExtractor()
            extractor.feed(text)
            title = _compact(" ".join(extractor.title_parts), 300) or "web page"
            body = _compact(" ".join(extractor.parts), excerpt_limit)
        else:
            title = final_url
            body = _compact(text, excerpt_limit)
        if not body:
            raise WebResearchError("web source returned no readable text")
        return WebDocument(
            url=final_url,
            title=title,
            content_type=content_type,
            text=body,
            retrieved_at=datetime.now(timezone.utc).isoformat(),
        )

    def read_json(self, url: str) -> dict:
        """Read one validated public JSON document without exposing transport."""

        _final_url, content_type, raw = self._fetch(url)
        if content_type != "application/json":
            raise WebResearchError("public data source did not return JSON")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WebResearchError("public data source returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise WebResearchError("public data source returned an invalid JSON shape")
        return payload

    def search(self, query: str, *, max_results: int = 3) -> list[WebDocument]:
        if not isinstance(query, str) or not query.strip() or len(query) > MAX_QUERY_LENGTH:
            raise WebResearchError("web search query is invalid or too long")
        if type(max_results) is not int or not 1 <= max_results <= MAX_RESULTS:
            raise WebResearchError("web search result count is invalid")
        # Bing's RSS endpoint is a public, no-credential discovery feed.  The
        # resulting source pages are still independently public-URL checked.
        feed = self.read(
            f"https://www.bing.com/search?format=rss&q={quote_plus(query.strip())}",
            excerpt_limit=64_000,
        )
        try:
            root = ET.fromstring(feed.text)
        except ET.ParseError as exc:
            raise WebResearchError("web search returned invalid results") from exc
        items: list[tuple[str, str, str]] = []
        for item in root.findall("./channel/item"):
            link = item.findtext("link")
            if not isinstance(link, str) or any(link == existing[0] for existing in items):
                continue
            title = _compact(item.findtext("title") or "web search result", 300)
            description = item.findtext("description") or ""
            extractor = _TextExtractor()
            extractor.feed(description)
            snippet = _compact(" ".join(extractor.parts) or description, MAX_EXCERPT_CHARS)
            items.append((link, title, snippet))
            if len(items) >= max_results:
                break
        if not items:
            raise WebResearchError("web search returned no readable sources")
        documents: list[WebDocument] = []
        for link, title, snippet in items:
            try:
                # Validate before attempting the page and before retaining a
                # source URL in a fallback fact.  A hostile search feed must
                # not turn a private target into model-visible source data.
                checked_link = self._validate(link)
            except WebResearchError:
                continue
            try:
                documents.append(self.read(checked_link))
            except WebResearchError:
                # Search snippets are still a bounded, source-attributed public
                # result.  Keep them explicitly marked rather than pretending
                # that a blocked destination page was fetched.
                if snippet:
                    documents.append(WebDocument(
                        url=link,
                        title=title,
                        content_type="application/rss+xml",
                        text=snippet,
                        retrieved_at=feed.retrieved_at,
                        retrieval_method="search_snippet",
                    ))
        if not documents:
            raise WebResearchError("web search sources could not be read")
        return documents


class PublicWeatherClient:
    """Read-only global forecast lookup for a place stated by the user.

    This is deliberately not a generic HTTP capability for Luna.  It uses the
    host's public-web boundary, sends only the requested place name, and
    returns normalized weather without provider coordinates or URLs.
    """

    _CONDITIONS = {
        0: "clear",
        1: "mostly clear",
        2: "partly cloudy",
        3: "overcast",
        45: "foggy",
        48: "foggy with rime",
        51: "light drizzle",
        53: "drizzle",
        55: "heavy drizzle",
        61: "light rain",
        63: "rain",
        65: "heavy rain",
        71: "light snow",
        73: "snow",
        75: "heavy snow",
        80: "rain showers",
        81: "rain showers",
        82: "heavy rain showers",
        95: "thunderstorms",
        96: "thunderstorms with hail",
        99: "thunderstorms with heavy hail",
    }

    def __init__(self, *, web_client: WebResearchClient | None = None) -> None:
        self._web = web_client or WebResearchClient()

    @staticmethod
    def _location_query(location: str) -> str:
        if not isinstance(location, str) or not location.strip() or len(location) > 160:
            raise WebResearchError("weather location is invalid or too long")
        if any(ord(character) < 32 or ord(character) == 127 for character in location):
            raise WebResearchError("weather location must be a single line")
        return location.strip()

    @staticmethod
    def _requested_date(when: str, timezone_name: str) -> str:
        try:
            local_now = datetime.now(ZoneInfo(timezone_name))
        except ZoneInfoNotFoundError as exc:
            raise WebResearchError("public weather source returned an invalid timezone") from exc
        if when == "today":
            return local_now.date().isoformat()
        if when == "tomorrow":
            return (local_now.date() + timedelta(days=1)).isoformat()
        try:
            candidate = datetime.strptime(when, "%Y-%m-%d").date()
        except (TypeError, ValueError) as exc:
            raise WebResearchError("weather date must be today, tomorrow, or YYYY-MM-DD") from exc
        if candidate < local_now.date() or candidate > local_now.date() + timedelta(days=15):
            raise WebResearchError("public forecast is available only for today through the next 15 days")
        return candidate.isoformat()

    def get_weather(self, location: str, *, when: str = "today") -> PublicWeather:
        location = self._location_query(location)
        geocoding = self._web.read_json(
            "https://geocoding-api.open-meteo.com/v1/search?" + urlencode({"name": location, "count": 1, "language": "en", "format": "json"})
        )
        candidates = geocoding.get("results")
        if not isinstance(candidates, list) or not candidates or not isinstance(candidates[0], dict):
            raise WebResearchError("public weather could not resolve that location")
        candidate = candidates[0]
        latitude, longitude, timezone_name = candidate.get("latitude"), candidate.get("longitude"), candidate.get("timezone")
        if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)) or not isinstance(timezone_name, str):
            raise WebResearchError("public weather location result was incomplete")
        local_date = self._requested_date(when, timezone_name)
        forecast = self._web.read_json(
            "https://api.open-meteo.com/v1/forecast?" + urlencode({
                "latitude": latitude,
                "longitude": longitude,
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "timezone": timezone_name,
                "temperature_unit": "fahrenheit",
                "forecast_days": 16,
            })
        )
        daily = forecast.get("daily")
        if not isinstance(daily, dict) or not isinstance(daily.get("time"), list):
            raise WebResearchError("public weather forecast was incomplete")
        try:
            index = daily["time"].index(local_date)
        except ValueError as exc:
            raise WebResearchError("public weather has no forecast for that local date") from exc

        def numeric_value(name: str, *, integer: bool = False):
            values = daily.get(name)
            value = values[index] if isinstance(values, list) and index < len(values) else None
            if not isinstance(value, (int, float)):
                return None
            return int(value) if integer else float(value)

        code = numeric_value("weather_code", integer=True)
        name = candidate.get("name") if isinstance(candidate.get("name"), str) else location
        admin = candidate.get("admin1") if isinstance(candidate.get("admin1"), str) else None
        country = candidate.get("country") if isinstance(candidate.get("country"), str) else None
        label = ", ".join(part for part in (name, admin, country) if part)
        return PublicWeather(
            location=label,
            local_date=local_date,
            timezone=timezone_name,
            summary=self._CONDITIONS.get(code, "weather conditions unavailable"),
            temperature_min_f=numeric_value("temperature_2m_min"),
            temperature_max_f=numeric_value("temperature_2m_max"),
            precipitation_probability_max=numeric_value("precipitation_probability_max", integer=True),
            retrieved_at=datetime.now(timezone.utc).isoformat(),
        )
