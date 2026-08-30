"""Deterministic routing for the bounded weather conversation vocabulary."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WeatherIntent:
    topic: str = "general"


def select_weather_intent(question: str) -> WeatherIntent | None:
    """Return a weather topic without using an LLM classifier."""

    lowered = " ".join(question.lower().split())
    if any(term in lowered for term in ("weather alert", "weather warning", "active alert", "storm warning", "tornado warning")):
        return WeatherIntent("alerts")
    if any(term in lowered for term in ("rain", "snow", "precipitation", "forecast", "later today", "tonight", "tomorrow", "this afternoon", "this evening")):
        return WeatherIntent("forecast")
    if any(term in lowered for term in ("weather", "outside", "temperature", "how hot", "how cold", "windy", "humidity", "conditions")):
        return WeatherIntent("current")
    return None
