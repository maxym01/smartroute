"""Mocked Weatherbit ``/current`` responses (documented format, ``units=M``)."""

import json
import urllib.error
from collections.abc import Callable
from typing import Any

TEST_KEY = "test-secret-key-123"


def current_payload(
    *,
    temp: float = 12.0,
    precip: float | None = 0.0,
    wind_spd: float = 3.0,  # m/s
    code: int = 800,
    description: str = "Clear sky",
    snow: float | None = 0.0,
) -> dict[str, Any]:
    return {
        "count": 1,
        "data": [
            {
                "lat": 54.4,
                "lon": 18.6,
                "city_name": "Gdańsk",
                "ts": 1794392400,  # 2026-11-11 10:20 UTC
                "ob_time": "2026-11-11 10:20",
                "temp": temp,
                "app_temp": temp - 2,
                "precip": precip,
                "snow": snow,
                "wind_spd": wind_spd,
                "wind_cdir": "W",
                "weather": {"icon": "c01d", "code": code, "description": description},
            }
        ],
    }


GOOD = current_payload()
RAIN = current_payload(precip=4.0, code=502, description="Heavy rain")
STRONG_WIND = current_payload(wind_spd=12.0, code=804, description="Overcast clouds")  # 43,2 km/h


class FakeFetch:
    """Replace HTTP: return successive responses (dict → JSON, exception → raise) and store URLs."""

    def __init__(self, *responses: dict[str, Any] | Exception | bytes) -> None:
        self.responses = list(responses)
        self.urls: list[str] = []
        self.timeouts: list[float] = []

    def __call__(self, url: str, timeout_s: float) -> bytes:
        self.urls.append(url)
        self.timeouts.append(timeout_s)
        response = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(response, Exception):
            raise response
        if isinstance(response, bytes):
            return response
        return json.dumps(response).encode()


def http_error(status: int) -> urllib.error.HTTPError:
    url = f"https://api.weatherbit.io/v2.0/current?key={TEST_KEY}"
    return urllib.error.HTTPError(url, status, "error", {}, None)  # type: ignore[arg-type]


class FakeClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


Clock = Callable[[], float]
