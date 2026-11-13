"""WeatherbitClient: unit normalization, TTL cache, errors and key protection (offline)."""

import logging
import urllib.error
import urllib.parse
from datetime import UTC, datetime

import pytest

from app.core.config import Settings
from app.services.weather import WeatherbitClient, WeatherUnavailableError
from app.services.weather.client import parse_current
from tests.weather_factory import (
    GOOD,
    RAIN,
    TEST_KEY,
    FakeClock,
    FakeFetch,
    current_payload,
    http_error,
)


def make_client(fetch: FakeFetch, clock: FakeClock | None = None, **kwargs) -> WeatherbitClient:
    return WeatherbitClient(
        TEST_KEY,
        fetch=fetch,
        clock=clock or FakeClock(),
        timeout_s=kwargs.pop("timeout_s", 2.5),
        cache_ttl_s=kwargs.pop("cache_ttl_s", 1800),
        error_cooldown_s=kwargs.pop("error_cooldown_s", 300),
    )


def test_request_uses_metric_units_coordinates_and_timeout() -> None:
    fetch = FakeFetch(GOOD)
    make_client(fetch).current(54.3551, 18.6449)

    parsed = urllib.parse.urlsplit(fetch.urls[0])
    query = urllib.parse.parse_qs(parsed.query)
    assert parsed.path.endswith("/v2.0/current")
    assert query["units"] == ["M"]
    assert query["lat"] == ["54.4"] and query["lon"] == ["18.6"]  # 0.1° grid cell
    assert query["key"] == [TEST_KEY]
    assert fetch.timeouts == [2.5]


def test_units_are_normalized() -> None:
    obs = parse_current(current_payload(temp=-3.5, precip=1.2, wind_spd=10.0), 54.4, 18.6)

    assert obs.temperature_c == -3.5
    assert obs.precipitation_mm_h == 1.2
    assert obs.wind_speed_kmh == 36.0  # 10 m/s × 3,6
    assert obs.weather_code == 800
    assert obs.observed_at == datetime(2026, 11, 11, 10, 20, tzinfo=UTC)


def test_missing_precipitation_is_zero_but_missing_temperature_is_error() -> None:
    assert parse_current(current_payload(precip=None, snow=None), 0, 0).precipitation_mm_h == 0.0

    payload = current_payload()
    del payload["data"][0]["temp"]
    with pytest.raises(WeatherUnavailableError, match="temp"):
        parse_current(payload, 0, 0)


def test_cache_serves_same_cell_within_ttl_and_refreshes_after() -> None:
    clock = FakeClock()
    fetch = FakeFetch(GOOD, RAIN)
    client = make_client(fetch, clock)

    first = client.current(54.351, 18.641)
    clock.advance(1799)
    second = client.current(54.369, 18.609)  # different coordinate, same cell 54.4/18.6
    assert second is first
    assert client.requests_sent == 1

    clock.advance(2)
    assert client.current(54.351, 18.641).precipitation_mm_h == 4.0
    assert client.requests_sent == 2


def test_different_cells_are_cached_separately() -> None:
    fetch = FakeFetch(GOOD)
    client = make_client(fetch)
    client.current(54.35, 18.64)
    client.current(54.52, 18.53)  # Gdynia
    assert client.requests_sent == 2


def test_without_key_no_request_is_sent() -> None:
    fetch = FakeFetch(GOOD)
    client = WeatherbitClient(None, fetch=fetch)

    assert not client.enabled
    with pytest.raises(WeatherUnavailableError, match="WEATHERBIT_API_KEY"):
        client.current(54.35, 18.64)
    assert fetch.urls == []


@pytest.mark.parametrize(
    "error",
    [TimeoutError("timed out"), urllib.error.URLError(TimeoutError("timed out"))],
    ids=["read-timeout", "connect-timeout"],
)
def test_timeout(error: Exception) -> None:
    with pytest.raises(WeatherUnavailableError, match=r"2,5 s|2.5 s"):
        make_client(FakeFetch(error)).current(54.35, 18.64)


def test_no_internet() -> None:
    error = urllib.error.URLError(OSError("getaddrinfo failed"))
    with pytest.raises(WeatherUnavailableError, match="Brak połączenia"):
        make_client(FakeFetch(error)).current(54.35, 18.64)


def test_rate_limit_429_triggers_cooldown_then_retries() -> None:
    clock = FakeClock()
    fetch = FakeFetch(http_error(429), GOOD)
    client = make_client(fetch, clock)

    with pytest.raises(WeatherUnavailableError, match="429"):
        client.current(54.35, 18.64)
    # During the cooldown — even for another location — the API is not queried.
    with pytest.raises(WeatherUnavailableError, match="429"):
        client.current(54.52, 18.53)
    assert client.requests_sent == 1

    clock.advance(301)
    assert client.current(54.35, 18.64).temperature_c == 12.0
    assert client.requests_sent == 2


def test_rejected_key_403() -> None:
    with pytest.raises(WeatherUnavailableError, match="odrzucił klucz"):
        make_client(FakeFetch(http_error(403))).current(54.35, 18.64)


@pytest.mark.parametrize("body", [b"<html>", b"", b'{"data": []}'], ids=["html", "204", "empty"])
def test_invalid_or_empty_response(body: bytes) -> None:
    with pytest.raises(WeatherUnavailableError):
        make_client(FakeFetch(body)).current(54.35, 18.64)


def test_key_never_appears_in_errors_or_logs(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    client = make_client(FakeFetch(http_error(429)))

    with pytest.raises(WeatherUnavailableError) as info:
        client.current(54.35, 18.64)

    assert TEST_KEY not in str(info.value)
    assert info.value.__cause__ is None and info.value.__suppress_context__
    assert TEST_KEY not in caplog.text
    assert "429" in caplog.text


def test_settings_mask_key_and_treat_empty_as_missing() -> None:
    settings = Settings(_env_file=None, weatherbit_api_key=TEST_KEY)
    assert TEST_KEY not in repr(settings)
    assert settings.weatherbit_api_key is not None
    assert settings.weatherbit_api_key.get_secret_value() == TEST_KEY

    assert Settings(_env_file=None, weatherbit_api_key="  ").weatherbit_api_key is None
