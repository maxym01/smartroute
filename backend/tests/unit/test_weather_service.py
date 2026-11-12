"""WeatherService: kiedy wolno użyć bieżącej pogody i skąd brać lokalizację."""

from dataclasses import dataclass
from datetime import datetime, timedelta

import pytest
from sqlalchemy.exc import OperationalError

from app.core.enums import WeatherStatus
from app.core.timezone import LOCAL_TIMEZONE
from app.services.transport import TripInput
from app.services.weather import WeatherbitClient, WeatherService
from tests.weather_factory import GOOD, TEST_KEY, FakeFetch, http_error

NOW = datetime(2026, 11, 11, 12, 0, tzinfo=LOCAL_TIMEZONE)


@dataclass
class Stop:
    stop_id: str
    stop_name: str
    stop_lat: float | None
    stop_lon: float | None


class Locator:
    def __init__(self, *stops: Stop) -> None:
        self.stops = {s.stop_id: s for s in stops}

    def get_stop(self, stop_id: str) -> Stop | None:
        return self.stops.get(stop_id)


LOCATOR = Locator(Stop("A1", "Dworzec Główny 01", 54.355, 18.645), Stop("X", "Bez GPS", None, None))


def service(fetch: FakeFetch | None = None, locator=LOCATOR, key: str | None = TEST_KEY):
    client = WeatherbitClient(key, fetch=fetch or FakeFetch(GOOD))
    return WeatherService(client, locator, max_lead_min=120, now=lambda: NOW), client


def trip(**fields) -> TripInput:
    return TripInput(distance_km=5, **{"origin_stop_id": "A1", "departure_at": NOW, **fields})


def test_applied_for_trip_now_with_gtfs_stop() -> None:
    svc, client = service()
    ctx = svc.assess(trip(departure_at=NOW + timedelta(minutes=30)))

    assert ctx.status is WeatherStatus.APPLIED
    assert ctx.location is not None and ctx.location.stop_name == "Dworzec Główny 01"
    assert ctx.observation is not None and ctx.observation.temperature_c == 12.0
    assert client.requests_sent == 1


def test_naive_departure_is_interpreted_as_local_time() -> None:
    svc, _ = service()
    assert svc.assess(trip(departure_at=datetime(2026, 11, 11, 13, 0))).status is (
        WeatherStatus.APPLIED
    )


def test_disabled_without_key() -> None:
    fetch = FakeFetch(GOOD)
    svc, _ = service(fetch, key=None)
    assert svc.assess(trip()).status is WeatherStatus.DISABLED
    assert fetch.urls == []


@pytest.mark.parametrize(
    "departure",
    [NOW + timedelta(hours=2, minutes=1), NOW + timedelta(days=3), NOW - timedelta(hours=2)],
    ids=["beyond-lead", "future-day", "past"],
)
def test_out_of_time_window_skips_without_request(departure: datetime) -> None:
    fetch = FakeFetch(GOOD)
    svc, _ = service(fetch)
    ctx = svc.assess(trip(departure_at=departure))

    assert ctx.status is WeatherStatus.OUT_OF_TIME_WINDOW
    assert "nie" in ctx.message
    assert fetch.urls == []


def test_future_date_message_says_it_is_not_a_forecast() -> None:
    svc, _ = service()
    ctx = svc.assess(trip(departure_at=NOW + timedelta(days=3)))
    assert "nie jest prognozą" in ctx.message
    assert "14.11.2026" in ctx.message


def test_missing_departure_is_skipped() -> None:
    svc, _ = service()
    assert svc.assess(trip(departure_at=None)).status is WeatherStatus.OUT_OF_TIME_WINDOW


@pytest.mark.parametrize(
    ("fields", "locator"),
    [
        ({"origin_stop_id": None, "origin": "Gdańsk"}, LOCATOR),  # nazwa miasta to nie GPS
        ({"origin_stop_id": "NOPE"}, LOCATOR),
        ({"origin_stop_id": "X"}, LOCATOR),  # przystanek bez współrzędnych
        ({}, None),  # rozkład GTFS nie zaimportowany
    ],
    ids=["city-name-only", "unknown-stop", "stop-without-coords", "no-gtfs"],
)
def test_no_reliable_location(fields, locator) -> None:
    fetch = FakeFetch(GOOD)
    svc, _ = service(fetch, locator=locator)
    assert svc.assess(trip(**fields)).status is WeatherStatus.NO_LOCATION
    assert fetch.urls == []


def test_gtfs_db_error_is_treated_as_no_location() -> None:
    class Broken:
        def get_stop(self, stop_id: str):
            raise OperationalError("SELECT", {}, Exception("no such table"))

    svc, _ = service(locator=Broken())
    assert svc.assess(trip()).status is WeatherStatus.NO_LOCATION


def test_api_error_is_reported_not_raised() -> None:
    svc, _ = service(FakeFetch(http_error(429)))
    ctx = svc.assess(trip())
    assert ctx.status is WeatherStatus.UNAVAILABLE
    assert "429" in ctx.message and "bez korekty" in ctx.message


def test_unexpected_error_never_propagates() -> None:
    svc, _ = service(FakeFetch(RuntimeError("boom")))
    assert svc.assess(trip()).status is WeatherStatus.UNAVAILABLE
