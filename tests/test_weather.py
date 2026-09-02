import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from unittest.mock import patch
from urllib.error import HTTPError

from perception.presence_store import PresenceStore
from perception.weather import NWSWeatherProvider, WeatherConfig, WeatherLocationRequired, WeatherProviderError
from tools.sentry_ask import ask
from tools.sentry_grounding import build_fact_packet
from tools.sentry_state_api import _Handler
from tools.sentry_weather_intent import WeatherIntent, select_weather_intent


NOW = datetime(2026, 8, 30, 16, 0, tzinfo=timezone.utc)


def snapshot(*, fetched_at: datetime = NOW, fresh=True, fingerprint="weather-source-1"):
    return {
        "provider": "nws", "location_label": "fixture", "latitude": 38.9, "longitude": -77.0,
        "timezone": "America/New_York", "fetched_at": fetched_at.isoformat(),
        "source_updated_at": fetched_at.isoformat(),
        "fresh_until": (fetched_at + timedelta(minutes=30 if fresh else -1)).isoformat(),
        "source_fingerprint": fingerprint,
        "current": {"observed_at": fetched_at.isoformat(), "temperature": {"value": 72, "unit": "wmoUnit:degC"}, "weather_description": "Clear"},
        "hourly": [{"start": fetched_at.isoformat(), "end": (fetched_at + timedelta(hours=1)).isoformat(), "temperature": 72, "temperature_unit": "F", "precipitation_probability": 10, "short_forecast": "Sunny"}],
        "alerts": [],
        "source_metadata": {"provider": "nws", "points_cache_status": "fresh", "station_id": "KXXX", "component_errors": []},
    }


def _nws_payloads():
    point = {
        "properties": {
            "gridId": "LWX", "gridX": 97, "gridY": 70,
            "forecast": "https://api.test/grid/forecast",
            "forecastHourly": "https://api.test/grid/hourly",
            "observationStations": "https://api.test/stations",
        }
    }
    hourly = {"properties": {"generatedAt": NOW.isoformat(), "periods": [{
        "startTime": NOW.isoformat(), "endTime": (NOW + timedelta(hours=1)).isoformat(),
        "temperature": 75, "temperatureUnit": "F", "probabilityOfPrecipitation": {"value": 20},
        "windSpeed": "5 mph", "windDirection": "NW", "shortForecast": "Mostly sunny", "raw_secret": "drop",
    }]}}
    stations = {"features": [{"id": "https://api.test/stations/KXXX"}]}
    observation = {"properties": {"timestamp": NOW.isoformat(), "stationIdentifier": "KXXX",
        "temperature": {"value": 23, "unitCode": "wmoUnit:degC"}, "relativeHumidity": {"value": 40},
        "windSpeed": {"value": 10}, "windDirection": {"value": 270}, "textDescription": "Clear",
        "unknown": "drop"}}
    alerts = {"features": [{"id": "urn:test-alert", "properties": {
        "event": "Heat Advisory", "severity": "Moderate", "urgency": "Expected", "certainty": "Likely",
        "effective": NOW.isoformat(), "expires": (NOW + timedelta(hours=2)).isoformat(),
        "headline": "Bounded alert", "description": "Drink water", "instruction": "Take care", "raw": "drop",
    }}]}
    return point, hourly, stations, observation, alerts


class WeatherTests(unittest.TestCase):
    def test_location_is_explicit(self):
        with self.assertRaises(WeatherLocationRequired):
            WeatherConfig.from_mapping({"enabled": True}).require_location()

    def test_nws_refresh_discovers_points_and_normalizes_bounded_fields(self):
        point, hourly, stations, observation, alerts = _nws_payloads()
        payloads = {
            "https://api.test/points/38.90000,-77.00000": point,
            "https://api.test/grid/hourly": hourly,
            "https://api.test/stations": stations,
            "https://api.test/stations/KXXX/observations/latest": observation,
            "https://api.test/alerts/active?point=38.90000,-77.00000": alerts,
        }
        provider = NWSWeatherProvider(fetch_json=lambda url: payloads[url], now=lambda: NOW, base_url="https://api.test")
        result = provider.refresh(WeatherConfig(enabled=True, location_label="fixture", latitude=38.9, longitude=-77.0))
        self.assertEqual(result["source_metadata"]["points_cache_status"], "fresh")
        self.assertEqual(result["source_metadata"]["station_id"], "KXXX")
        self.assertEqual(result["current"]["temperature"]["value"], 23)
        self.assertEqual(result["hourly"][0]["short_forecast"], "Mostly sunny")
        self.assertEqual(result["alerts"][0]["event"], "Heat Advisory")
        self.assertNotIn("raw_secret", json.dumps(result))
        self.assertNotIn('"raw"', json.dumps(result))

    def test_hourly_normalization_retains_tomorrow_but_stays_bounded(self):
        point, hourly, stations, observation, alerts = _nws_payloads()
        periods = []
        for offset in range(60):
            periods.append({
                "startTime": (NOW + timedelta(hours=offset)).isoformat(),
                "endTime": (NOW + timedelta(hours=offset + 1)).isoformat(),
                "temperature": 75,
                "temperatureUnit": "F",
                "probabilityOfPrecipitation": {"value": 20},
                "windSpeed": "5 mph",
                "windDirection": "NW",
                "shortForecast": "Mostly sunny",
            })
        hourly = {"properties": {"generatedAt": NOW.isoformat(), "periods": periods}}
        payloads = {
            "https://api.test/points/38.90000,-77.00000": point,
            "https://api.test/grid/hourly": hourly,
            "https://api.test/stations": stations,
            "https://api.test/stations/KXXX/observations/latest": observation,
            "https://api.test/alerts/active?point=38.90000,-77.00000": alerts,
        }
        provider = NWSWeatherProvider(fetch_json=lambda url: payloads[url], now=lambda: NOW, base_url="https://api.test")
        result = provider.refresh(WeatherConfig(enabled=True, location_label="fixture", latitude=38.9, longitude=-77.0))
        self.assertEqual(len(result["hourly"]), 49)
        self.assertEqual(result["hourly"][-1]["start"], (NOW + timedelta(hours=48)).isoformat())

    def test_points_mapping_is_cached_for_configured_interval(self):
        point, hourly, stations, observation, alerts = _nws_payloads()
        payloads = {
            "https://api.test/points/38.90000,-77.00000": point,
            "https://api.test/grid/hourly": hourly,
            "https://api.test/stations": stations,
            "https://api.test/stations/KXXX/observations/latest": observation,
            "https://api.test/alerts/active?point=38.90000,-77.00000": alerts,
        }
        calls = []
        provider = NWSWeatherProvider(fetch_json=lambda url: (calls.append(url) or payloads[url]), now=lambda: NOW, base_url="https://api.test")
        config = WeatherConfig(enabled=True, location_label="fixture", latitude=38.9, longitude=-77.0)
        first = provider.refresh(config)
        provider.refresh(config, previous=first)
        self.assertEqual(calls.count("https://api.test/points/38.90000,-77.00000"), 1)

    def test_provider_retries_429_and_fails_bounded(self):
        provider = NWSWeatherProvider(sleep=lambda _: None)
        error = HTTPError("https://api.weather.gov/test", 429, "rate limited", {}, None)
        with patch("perception.weather.urlopen", side_effect=error) as opener:
            with self.assertRaises(WeatherProviderError):
                provider._fetch_json("https://api.weather.gov/test", retry_count=2)
        self.assertEqual(opener.call_count, 3)

    def test_store_freshness_idempotence_and_atlas_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local, atlas = root / "local" / "sentry.db", root / "atlas" / "sentry.db"
            value = snapshot()
            with PresenceStore(local, atlas_mirror_path=atlas) as store:
                self.assertEqual(store.health()["schema_version"], 9)
                first = store.persist_weather_snapshot(value)
                second = store.persist_weather_snapshot({**value, "fetched_at": (NOW + timedelta(minutes=1)).isoformat(), "fresh_until": (NOW + timedelta(minutes=31)).isoformat()})
                self.assertTrue(first["written"])
                self.assertTrue(second["skipped"])
                self.assertTrue(second["refreshed"])
                self.assertEqual(len(store._connection.execute("SELECT * FROM weather_snapshots").fetchall()), 1)
                self.assertEqual(store.weather_status("fixture", now=NOW)["status"], "fresh")
                self.assertEqual(store.weather_status("fixture", now=NOW + timedelta(hours=1))["status"], "stale")
            local.unlink()
            with PresenceStore(local, atlas_mirror_path=atlas) as restored:
                self.assertEqual(restored.health()["schema_version"], 9)
                self.assertEqual(restored.latest_weather_snapshot("fixture")["provider"], "nws")

    def test_weather_api_is_local_metadata_only(self):
        with tempfile.TemporaryDirectory() as directory, PresenceStore(Path(directory) / "sentry.db") as store:
            value = snapshot(fetched_at=datetime.now(timezone.utc))
            value["alerts"] = [{"id": "https://api.weather.gov/alerts/LEGACY-ALERT", "event": "Fixture"}]
            store.persist_weather_snapshot(value)
            server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
            server.store = store
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
                connection.request("GET", "/v1/weather?location_label=fixture")
                response = connection.getresponse()
                payload = json.loads(response.read())
                self.assertEqual(response.status, 200)
                self.assertEqual(payload["status"], "fresh")
                encoded = json.dumps(payload)
                self.assertNotIn("latitude", encoded)
                self.assertNotIn("longitude", encoded)
                self.assertNotIn("points_url", encoded)
                self.assertNotIn("api.weather.gov", encoded)
                self.assertEqual(payload["snapshot"]["alerts"][0]["id"], "LEGACY-ALERT")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_alert_urls_are_reduced_to_bounded_identifiers(self):
        point, hourly, stations, observation, alerts = _nws_payloads()
        alerts["features"][0]["id"] = "https://api.weather.gov/alerts/TEST-ALERT-123"
        payloads = {
            "https://api.test/points/38.90000,-77.00000": point,
            "https://api.test/grid/hourly": hourly,
            "https://api.test/stations": stations,
            "https://api.test/stations/KXXX/observations/latest": observation,
            "https://api.test/alerts/active?point=38.90000,-77.00000": alerts,
        }
        provider = NWSWeatherProvider(fetch_json=lambda url: payloads[url], now=lambda: NOW, base_url="https://api.test")
        result = provider.refresh(WeatherConfig(enabled=True, location_label="fixture", latitude=38.9, longitude=-77.0))
        self.assertEqual(result["alerts"][0]["id"], "TEST-ALERT-123")
        self.assertNotIn("api.weather.gov", json.dumps(result))

    def test_weather_fact_packet_is_allow_listed(self):
        responses = {
            "health": {"ok": True, "db_available": True, "schema_version": 7},
            "state": {"room_id": "office", "state": "empty", "camera_state": "online", "people": []},
            "sessions": {"sessions": []}, "persons": {"persons": []}, "events": {"events": []},
        }
        packet = build_fact_packet(responses, weather_response={
            "status": "fresh", "age_seconds": 2, "fresh_until": NOW.isoformat(), "provider": "nws",
            "location_label": "fixture", "timezone": "America/New_York", "fetched_at": NOW.isoformat(),
            "snapshot": {**snapshot(), "latitude": 1, "longitude": 2, "source_metadata": {"points_url": "secret", "provider": "nws"}},
        })
        encoded = json.dumps(packet)
        self.assertIn("weather:current", encoded)
        self.assertNotIn("points_url", encoded)
        self.assertNotIn('"latitude"', encoded)

    def test_weather_intent_is_deterministic(self):
        self.assertEqual(select_weather_intent("Any weather alerts?"), WeatherIntent("alerts"))
        self.assertEqual(select_weather_intent("Will it rain tonight?"), WeatherIntent("forecast"))
        self.assertEqual(select_weather_intent("What's it like outside?"), WeatherIntent("current"))
        self.assertIsNone(select_weather_intent("When did I come in today?"))

    def test_weather_tool_arguments_are_bounded_even_with_habitual_wording(self):
        from tools.sentry_conversation_tools import ConversationToolHost
        self.assertIsNone(ConversationToolHost.validate_call("get_weather", {"topic": "forecast"}))
        self.assertEqual(ConversationToolHost.validate_call("get_weather", {"topic": "network"}), "weather topic is not supported")

    @patch("tools.sentry_grounding._get_json")
    def test_weather_unavailable_fact_is_explicit(self, get_json):
        base = {"health": {"ok": True, "db_available": True, "schema_version": 7}, "state": {}, "sessions": {"sessions": []}, "persons": {"persons": []}, "events": {"events": []}}
        weather = {"status": "unavailable", "snapshot": None}
        get_json.side_effect = [base["health"], base["state"], base["sessions"], base["persons"], base["events"], weather]
        packet = build_fact_packet(base, weather_response=weather)
        source = next(fact for fact in packet["facts"] if fact["fact_id"] == "weather:source-health")
        self.assertEqual(source["data"]["status"], "unavailable")

    def test_fresh_weather_fact_packet_is_bounded_for_conversation_tools(self):
        base = {"health": {"ok": True, "db_available": True, "schema_version": 7}, "state": {}, "sessions": {"sessions": []}, "persons": {"persons": []}, "events": {"events": []}}
        weather = {"status": "fresh", "age_seconds": 2, "fresh_until": NOW.isoformat(), "provider": "nws", "location_label": "fixture", "timezone": "America/New_York", "fetched_at": NOW.isoformat(), "snapshot": snapshot()}
        packet = build_fact_packet(base, weather_response=weather)
        ids = {fact["fact_id"] for fact in packet["facts"]}
        self.assertIn("weather:source-health", ids)
        self.assertIn("weather:current", ids)


if __name__ == "__main__":
    unittest.main()
