import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from perception.presence_store import PresenceStore
from perception.proactive import ProactiveProcessor, ProactivePolicyConfig, WeatherContextPolicy
from tools.sentry_grounding import build_proactive_fact_packet


BASE = datetime(2026, 8, 30, 16, 0, tzinfo=timezone.utc)


class FakeSpeech:
    def __init__(self, result=True):
        self.result = result
        self.calls = []
        self.busy = False

    @property
    def is_speaking(self):
        return self.busy

    def speak(self, text):
        self.calls.append(text)
        return self.result


def observed(store, state, timestamp, transition=None, *, person=False):
    store.record_observation({
        "room_state": state,
        "captured_at": timestamp.isoformat(),
        "camera_state": "online" if state in {"empty", "occupied"} else state,
        "room_state_transition": transition,
        "frame_sequence": int(timestamp.timestamp()),
        "people": ([{"track_id": 4, "visible": True, "person_id": "primary_user", "identity_state": "recognized", "identity_confidence": 0.91}] if person else []),
        "detector_evidence": person,
        "max_person_confidence": 0.91 if person else None,
    })


def make_event(store, person_id="primary_user"):
    observed(store, "empty", BASE)
    observed(store, "occupied", BASE + timedelta(seconds=2), "empty->occupied", person=True)
    event = next(item for item in store.events() if item["event_type"] == "person.identified")
    event["payload"] = dict(event["payload"])
    event["payload"]["person_id"] = person_id
    return event


def weather_snapshot(*, label="fixture", fresh_until=None, hourly=None, fingerprint="weather-1"):
    return {
        "provider": "nws",
        "location_label": label,
        "latitude": 38.9,
        "longitude": -77.0,
        "timezone": "America/New_York",
        "fetched_at": BASE.isoformat(),
        "source_updated_at": BASE.isoformat(),
        "fresh_until": (fresh_until or BASE + timedelta(minutes=30)).isoformat(),
        "source_fingerprint": fingerprint,
        "current": {"observed_at": BASE.isoformat(), "temperature": {"value": 20, "unit": "wmoUnit:degC"}},
        "hourly": hourly if hourly is not None else [{
            "start": (BASE + timedelta(minutes=5)).isoformat(),
            "end": (BASE + timedelta(minutes=65)).isoformat(),
            "precipitation_probability": 80,
            "short_forecast": "Rain likely",
        }],
        "alerts": [{"id": "alert-ignored", "event": "Storm Watch"}],
        "source_metadata": {"provider": "nws", "points_cache_status": "cached", "station_id": "KXXX", "component_errors": []},
    }


def config():
    return ProactivePolicyConfig.from_mapping({
        "enabled": True,
        "event_ttl_seconds": 30,
        "same_session_max_actions": 1,
        "person_cooldown_minutes": 30,
        "global_max_spoken_actions_per_hour": 2,
        "startup_suppression_seconds": 0,
    })


def weather_policy(**overrides):
    values = {
        "configured": True,
        "location_label": "fixture",
        "horizon_minutes": 120,
        "precipitation_probability_threshold": 60,
    }
    values.update(overrides)
    return WeatherContextPolicy(**values)


def silent_judge(packet, **kwargs):
    return {"ok": True, "result": {
        "decision": "silent", "message": None,
        "fact_ids": ["weather-near-term-precipitation"], "reason_code": "nothing_useful_to_add",
    }}


def speak_judge(packet, **kwargs):
    return {"ok": True, "result": {
        "decision": "speak", "message": "Rain is likely within the next couple of hours.",
        "fact_ids": ["weather-context-health", "weather-near-term-precipitation"], "reason_code": "useful_weather_heads_up",
    }}


class ContextualWeatherProactivityTests(unittest.TestCase):
    def process(self, snapshot=None, *, policy=None, judge=silent_judge, now=BASE + timedelta(seconds=3), person_id="primary_user"):
        store = PresenceStore(Path(tempfile.mkdtemp()) / "sentry.db")
        event = make_event(store, person_id=person_id)
        if snapshot is not None:
            store.persist_weather_snapshot(snapshot)
        speech = FakeSpeech()
        processor = ProactiveProcessor(store, config(), judge=judge, speech=speech, started_at=BASE, weather_policy=policy or weather_policy())
        result = processor.process_event(event, now=now)
        return store, event, result, speech

    def test_unconfigured_weather_is_explicit_and_does_not_call_luna(self):
        calls = []
        store, _, result, speech = self.process(policy=WeatherContextPolicy(), judge=lambda *a, **k: calls.append(1))
        self.assertEqual(result.suppression_reason, "weather_unconfigured")
        self.assertEqual(calls, [])
        self.assertEqual(speech.calls, [])
        store.close()

    def test_missing_snapshot_is_unavailable(self):
        store, _, result, speech = self.process(judge=lambda *a, **k: self.fail("weather failure must not reach Luna"))
        self.assertEqual(result.suppression_reason, "weather_unavailable")
        self.assertEqual(speech.calls, [])
        store.close()

    def test_stale_snapshot_is_rejected(self):
        stale = weather_snapshot(fresh_until=BASE - timedelta(seconds=1))
        store, _, result, _ = self.process(snapshot=stale, judge=lambda *a, **k: self.fail("stale weather must not reach Luna"))
        self.assertEqual(result.suppression_reason, "weather_stale")
        store.close()

    def test_missing_probability_is_insufficient(self):
        hourly = [{"start": (BASE + timedelta(minutes=5)).isoformat(), "end": (BASE + timedelta(hours=1)).isoformat(), "short_forecast": "Rain possible"}]
        store, _, result, _ = self.process(snapshot=weather_snapshot(hourly=hourly), judge=lambda *a, **k: self.fail("missing probability must not reach Luna"))
        self.assertEqual(result.suppression_reason, "weather_insufficient")
        store.close()

    def test_below_threshold_is_not_relevant(self):
        hourly = [{"start": (BASE + timedelta(minutes=5)).isoformat(), "end": (BASE + timedelta(hours=1)).isoformat(), "precipitation_probability": 59}]
        store, _, result, _ = self.process(snapshot=weather_snapshot(hourly=hourly), judge=lambda *a, **k: self.fail("irrelevant weather must not reach Luna"))
        self.assertEqual(result.suppression_reason, "weather_not_relevant")
        store.close()

    def test_probability_outside_horizon_is_not_relevant(self):
        hourly = [{"start": (BASE + timedelta(minutes=121)).isoformat(), "end": (BASE + timedelta(minutes=181)).isoformat(), "precipitation_probability": 99}]
        store, _, result, _ = self.process(snapshot=weather_snapshot(hourly=hourly), judge=lambda *a, **k: self.fail("out-of-horizon weather must not reach Luna"))
        self.assertEqual(result.suppression_reason, "weather_not_relevant")
        store.close()

    def test_relevant_probability_reaches_one_luna_turn_with_bounded_facts(self):
        calls = []
        def judge(packet, **kwargs):
            calls.append(packet)
            return silent_judge(packet, **kwargs)
        store, _, result, speech = self.process(snapshot=weather_snapshot(), judge=judge)
        self.assertEqual(result.suppression_reason, "judge_silent")
        self.assertEqual(len(calls), 1)
        encoded = json.dumps(calls[0])
        self.assertIn("weather-near-term-precipitation", encoded)
        self.assertNotIn("latitude", encoded)
        self.assertNotIn("longitude", encoded)
        self.assertNotIn("alert-ignored", encoded)
        self.assertEqual(speech.calls, [])
        store.close()

    def test_relevant_weather_can_speak_once_and_persisted_decision_is_grounded(self):
        store, event, result, speech = self.process(snapshot=weather_snapshot(), judge=speak_judge)
        self.assertEqual(result.delivery_status, "delivered")
        self.assertEqual(speech.calls, ["Rain is likely within the next couple of hours."])
        action = store.proactive_action_for_event(event["event_id"])
        self.assertEqual(action["judge_decision"], "speak")
        self.assertEqual(action["cited_fact_ids"], ["weather-context-health", "weather-near-term-precipitation"])
        store.close()

    def test_existing_physical_gates_precede_weather_gate(self):
        store = PresenceStore(Path(tempfile.mkdtemp()) / "sentry.db")
        event = make_event(store, person_id="unknown")
        calls = []
        result = ProactiveProcessor(store, config(), judge=lambda *a, **k: calls.append(1), speech=FakeSpeech(), started_at=BASE, weather_policy=WeatherContextPolicy()).process_event(event, now=BASE + timedelta(seconds=3))
        self.assertEqual(result.suppression_reason, "non_primary")
        self.assertEqual(calls, [])
        store.close()

    def test_preference_gate_precedes_weather_gate(self):
        store = PresenceStore(Path(tempfile.mkdtemp()) / "sentry.db")
        event = make_event(store)
        store.record_preference(person_id="primary_user", operation="set", value="suppress", source_surface="test", source_request_id="request-1")
        result = ProactiveProcessor(store, config(), judge=lambda *a, **k: self.fail("suppressed preference must not reach Luna"), speech=FakeSpeech(), started_at=BASE, weather_policy=WeatherContextPolicy()).process_event(event, now=BASE + timedelta(seconds=3))
        self.assertEqual(result.suppression_reason, "user_preference")
        store.close()

    def test_same_session_gate_precedes_weather_gate(self):
        store = PresenceStore(Path(tempfile.mkdtemp()) / "sentry.db")
        event = make_event(store)
        store.persist_weather_snapshot(weather_snapshot())
        processor = ProactiveProcessor(store, config(), judge=silent_judge, speech=FakeSpeech(), started_at=BASE, weather_policy=weather_policy())
        processor.process_event(event, now=BASE + timedelta(seconds=3))
        replay = dict(event, event_id="reacquired-event")
        result = processor.process_event(replay, now=BASE + timedelta(seconds=4))
        self.assertEqual(result.suppression_reason, "already_handled_session")
        store.close()

    def test_existing_m5_packet_has_no_weather_without_context(self):
        store = PresenceStore(Path(tempfile.mkdtemp()) / "sentry.db")
        event = make_event(store)
        packet = build_proactive_fact_packet(store, event, {
            "candidate_key": "primary_user:session:1",
            "hourly_spoken_count": 0,
            "hourly_spoken_limit": 2,
            "same_session_action_count": 0,
            "same_session_action_limit": 1,
        }, as_of=(BASE + timedelta(seconds=3)).isoformat())
        self.assertNotIn("weather-context-health", {fact["fact_id"] for fact in packet["facts"]})
        self.assertNotIn("weather-near-term-precipitation", {fact["fact_id"] for fact in packet["facts"]})
        store.close()

    def test_cache_only_gate_never_calls_nws(self):
        store = PresenceStore(Path(tempfile.mkdtemp()) / "sentry.db")
        event = make_event(store)
        store.persist_weather_snapshot(weather_snapshot())
        with patch("perception.weather.urlopen", side_effect=AssertionError("proactive path must not call NWS")):
            result = ProactiveProcessor(store, config(), judge=silent_judge, speech=FakeSpeech(), started_at=BASE, weather_policy=weather_policy()).process_event(event, now=BASE + timedelta(seconds=3))
        self.assertEqual(result.suppression_reason, "judge_silent")
        store.close()

    def test_restart_replay_does_not_redeliver_contextual_action(self):
        path = Path(tempfile.mkdtemp()) / "sentry.db"
        store = PresenceStore(path)
        event = make_event(store)
        store.persist_weather_snapshot(weather_snapshot())
        calls = []
        processor = ProactiveProcessor(store, config(), judge=lambda *a, **k: (calls.append(1) or speak_judge(*a, **k)), speech=FakeSpeech(), started_at=BASE, weather_policy=weather_policy())
        processor.process_event(event, now=BASE + timedelta(seconds=3))
        store.close()
        reopened = PresenceStore(path)
        result = ProactiveProcessor(reopened, config(), judge=lambda *a, **k: self.fail("replay must not call Luna"), speech=FakeSpeech(), started_at=BASE, weather_policy=weather_policy()).process_event(event, now=BASE + timedelta(seconds=4))
        self.assertEqual(len(calls), 1)
        self.assertEqual(result.suppression_reason, "duplicate")
        reopened.close()

    def test_invalid_weather_citation_fails_silent(self):
        def invalid(packet, **kwargs):
            return {"ok": True, "result": {"decision": "speak", "message": "Bring an umbrella.", "fact_ids": ["weather:not-real"], "reason_code": "weather"}}
        store, _, result, speech = self.process(snapshot=weather_snapshot(), judge=invalid)
        self.assertEqual(result.suppression_reason, "judge_invalid")
        self.assertEqual(speech.calls, [])
        store.close()

    def test_policy_configuration_is_bounded_and_explicit(self):
        policy = WeatherContextPolicy.from_mapping({"enabled": True, "location_label": "fixture", "latitude": 1, "longitude": 2, "contextual_proactivity": {"horizon_minutes": 120, "precipitation_probability_threshold": 60}})
        self.assertTrue(policy.configured)
        self.assertEqual(policy.horizon_minutes, 120)
        self.assertEqual(policy.precipitation_probability_threshold, 60)
        self.assertFalse(WeatherContextPolicy.from_mapping(None).configured)


if __name__ == "__main__":
    unittest.main()
