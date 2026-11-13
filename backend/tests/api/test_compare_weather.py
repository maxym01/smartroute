"""Comparison with current weather — Weatherbit replaced by a mock (no network)."""

from datetime import datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.comparisons import get_weather_client
from app.core.timezone import LOCAL_TIMEZONE
from app.services.weather import WeatherbitClient
from tests.weather_factory import GOOD, RAIN, STRONG_WIND, TEST_KEY, FakeFetch, http_error

TRIPS_URL = "/api/v1/trips"


def soon(minutes: int = 15) -> str:
    return (datetime.now(LOCAL_TIMEZONE) + timedelta(minutes=minutes)).isoformat()


def use_weather(app: FastAPI, fetch: FakeFetch) -> WeatherbitClient:
    client = WeatherbitClient(TEST_KEY, fetch=fetch)
    app.dependency_overrides[get_weather_client] = lambda: client
    return client


def compare(client: TestClient, priority: str = "balanced", **fields: Any) -> dict[str, Any]:
    payload = {
        "name": "Do pracy",
        "origin": "Gdańsk",
        "destination": "Gdańsk Śródmieście",
        "distance_km": 4,
        "priority": priority,
        "origin_stop_id": "A1",
        "destination_stop_id": "C1",
        "departure_at": soon(),
        **fields,
    }
    created = client.post(TRIPS_URL, json=payload)
    assert created.status_code == 201, created.text
    response = client.get(f"{TRIPS_URL}/{created.json()['id']}/compare")
    assert response.status_code == 200, response.text
    return response.json()


def bike(body: dict[str, Any]) -> dict[str, Any]:
    return next(v for v in body["variants"] if v["mode"] == "bike")


def test_without_key_weather_is_disabled_and_result_unchanged(gtfs_client: TestClient) -> None:
    body = compare(gtfs_client, "greenest")

    assert body["weather"]["status"] == "disabled"
    assert body["weather"]["adjustment_applied"] is False
    assert body["weather"]["is_forecast"] is False
    assert body["recommendation"]["mode"] == "bike"
    assert bike(body)["comfort_level"] is None
    assert bike(body)["score"]["weather_demoted"] is False


def test_good_weather(app: FastAPI, gtfs_client: TestClient) -> None:
    use_weather(app, FakeFetch(GOOD))
    body = compare(gtfs_client, "greenest")

    weather = body["weather"]
    assert weather["status"] == "applied" and weather["adjustment_applied"] is True
    assert weather["location"] == {
        "stop_id": "A1",
        "stop_name": "Dworzec Główny 01",
        "lat": 54.355,
        "lon": 18.645,
    }
    assert weather["conditions"]["wind_speed_kmh"] == 10.8
    assert weather["adjustment"]["comfort_level"] == "good"
    assert body["recommendation"]["mode"] == "bike"
    assert bike(body)["comfort_level"] == "good"
    assert bike(body)["estimated_duration_min"] == 16.0  # 4 km / 15 km/h, unchanged


def test_heavy_rain_demotes_bike_even_for_greenest(app: FastAPI, gtfs_client: TestClient) -> None:
    use_weather(app, FakeFetch(RAIN))
    body = compare(gtfs_client, "greenest")

    assert body["weather"]["adjustment"]["comfort_level"] == "poor"
    assert body["recommendation"]["mode"] != "bike"
    assert bike(body)["score"]["weather_demoted"] is True
    assert bike(body)["score"]["rank"] == 3
    assert "przesunięto na koniec rankingu" in body["recommendation"]["explanation"]
    assert bike(body)["estimated_co2_kg"] == 0.0  # metrics unchanged


def test_strong_wind_increases_bike_time(app: FastAPI, gtfs_client: TestClient) -> None:
    use_weather(app, FakeFetch(STRONG_WIND))
    body = compare(gtfs_client, "fastest")

    assert body["weather"]["adjustment"]["duration_factor"] == 1.2
    assert bike(body)["estimated_duration_min"] == 19.2  # 16 min × 1.2
    assert any("wiatru" in a for a in bike(body)["assumptions"])


@pytest.mark.parametrize(
    ("error", "fragment"),
    [(TimeoutError("timed out"), "nie odpowiedział"), (http_error(429), "429")],
    ids=["timeout", "429"],
)
def test_api_failure_falls_back_to_previous_algorithm(
    app: FastAPI, gtfs_client: TestClient, error: Exception, fragment: str
) -> None:
    baseline = compare(gtfs_client, "greenest")
    use_weather(app, FakeFetch(error))
    body = compare(gtfs_client, "greenest")

    assert body["weather"]["status"] == "unavailable"
    assert fragment in body["weather"]["explanation"]
    assert TEST_KEY not in str(body)
    assert body["recommendation"] == baseline["recommendation"]
    assert body["variants"] == baseline["variants"]


def test_cache_limits_external_calls(app: FastAPI, gtfs_client: TestClient) -> None:
    client = use_weather(app, FakeFetch(GOOD))
    for priority in ("fastest", "cheapest", "greenest"):
        assert compare(gtfs_client, priority)["weather"]["status"] == "applied"
    assert client.requests_sent == 1


def test_future_date_skips_weather(app: FastAPI, gtfs_client: TestClient) -> None:
    fetch = FakeFetch(RAIN)
    use_weather(app, fetch)
    body = compare(gtfs_client, "greenest", departure_at=soon(60 * 24 * 3))

    assert body["weather"]["status"] == "out_of_time_window"
    assert "nie jest prognozą" in body["weather"]["explanation"]
    assert body["recommendation"]["mode"] == "bike"
    assert fetch.urls == []


def test_trip_without_stop_has_no_location(app: FastAPI, gtfs_client: TestClient) -> None:
    fetch = FakeFetch(RAIN)
    use_weather(app, fetch)
    body = compare(gtfs_client, origin_stop_id=None, destination_stop_id=None)

    assert body["weather"]["status"] == "no_location"
    assert fetch.urls == []


def test_unavailable_bike_does_not_query_api(app: FastAPI, gtfs_client: TestClient) -> None:
    fetch = FakeFetch(RAIN)
    use_weather(app, fetch)
    body = compare(gtfs_client, allow_bike=False)

    assert body["weather"]["status"] == "not_applicable"
    assert fetch.urls == []
