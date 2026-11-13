"""Weatherbit Current Weather API client (``GET /v2.0/current``) with a TTL cache.

Rules:

- the API key comes only from the settings (``WEATHERBIT_API_KEY``) and never reaches logs
  or error messages (HTTP exceptions are suppressed with ``from None`` because their URL
  contains the key);
- requests always use ``units=M`` (metric): temperature in °C, wind in m/s, precipitation
  in mm/h; wind is converted to km/h;
- a reading for a grid cell (~0.1°, i.e. a few km) is cached for ``cache_ttl_s`` seconds,
  and after an error (timeout, 429, no network, rejected key) the client sends no further
  requests for ``error_cooldown_s`` seconds, which protects the free plan's daily quota;
- every problem ends in ``WeatherUnavailableError`` with a safe, Polish-language message.

The standard library's ``urllib`` is used to avoid adding a runtime dependency.
"""

import json
import logging
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

# Cache key resolution [degrees]. Current weather does not differ much within a few
# kilometres, and a coarser grid means fewer API requests.
GRID_DECIMALS = 1
MS_TO_KMH = 3.6

# (url, timeout_s) -> response body. urllib by default; replaced in tests.
Fetcher = Callable[[str, float], bytes]


class WeatherUnavailableError(Exception):
    """Weather unavailable. ``reason`` is safe to show to the user."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class WeatherObservation:
    """Current observation in normalized units."""

    temperature_c: float
    precipitation_mm_h: float  # precipitation (water equivalent), mm/h
    snowfall_mm_h: float  # snowfall, mm/h
    wind_speed_kmh: float
    weather_code: int | None
    description: str | None
    observed_at: datetime | None  # UTC
    lat: float  # request coordinates (centre of the grid cell)
    lon: float


def grid_cell(lat: float, lon: float) -> tuple[float, float]:
    return round(lat, GRID_DECIMALS), round(lon, GRID_DECIMALS)


def _urllib_fetch(url: str, timeout_s: float) -> bytes:
    request = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": "SmartRoute/0.1"}
    )
    with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310
        if response.status == 204:  # Weatherbit: no data for the location
            return b""
        return response.read()


def _number(record: dict[str, object], key: str, *, required: bool) -> float:
    value = record.get(key)
    if value is None and not required:
        return 0.0
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise WeatherUnavailableError(f"Odpowiedź Weatherbit bez poprawnego pola „{key}”.")
    return float(value)


def parse_current(payload: object, lat: float, lon: float) -> WeatherObservation:
    """Parse a ``/current`` response (``{"data": [{...}], "count": 1}``) with ``units=M``."""
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        raise WeatherUnavailableError("Weatherbit nie zwrócił danych dla tej lokalizacji.")
    record: dict[str, object] = data[0]

    weather = record.get("weather")
    code = description = None
    if isinstance(weather, dict):
        raw_code = str(weather.get("code", ""))
        code = int(raw_code) if raw_code.isdigit() else None
        raw_description = weather.get("description")
        description = raw_description if isinstance(raw_description, str) else None

    observed_at = None
    ts = record.get("ts")
    if isinstance(ts, int | float) and not isinstance(ts, bool):
        observed_at = datetime.fromtimestamp(ts, tz=UTC)

    return WeatherObservation(
        temperature_c=_number(record, "temp", required=True),
        precipitation_mm_h=max(_number(record, "precip", required=False), 0.0),
        snowfall_mm_h=max(_number(record, "snow", required=False), 0.0),
        wind_speed_kmh=round(_number(record, "wind_spd", required=True) * MS_TO_KMH, 1),
        weather_code=code,
        description=description,
        observed_at=observed_at,
        lat=lat,
        lon=lon,
    )


class WeatherbitClient:
    def __init__(
        self,
        api_key: str | None,
        *,
        base_url: str = "https://api.weatherbit.io/v2.0",
        timeout_s: float = 5.0,
        cache_ttl_s: float = 1800,
        error_cooldown_s: float = 300,
        fetch: Fetcher | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._api_key = api_key or None
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s
        self._cache_ttl_s = cache_ttl_s
        self._error_cooldown_s = error_cooldown_s
        self._fetch = fetch or _urllib_fetch
        self._clock = clock
        self._cache: dict[tuple[float, float], tuple[float, WeatherObservation]] = {}
        self._cooldown_until = 0.0
        self._cooldown_reason = ""
        # A single lock: parallel comparisons for the same location will not send two requests.
        self._lock = threading.Lock()
        self.requests_sent = 0  # counter for diagnostics and tests

    @property
    def enabled(self) -> bool:
        return self._api_key is not None

    def current(self, lat: float, lon: float) -> WeatherObservation:
        if self._api_key is None:
            raise WeatherUnavailableError("Brak klucza WEATHERBIT_API_KEY.")
        cell = grid_cell(lat, lon)
        with self._lock:
            now = self._clock()
            cached = self._cache.get(cell)
            if cached and cached[0] > now:
                return cached[1]
            if self._cooldown_until > now:
                raise WeatherUnavailableError(self._cooldown_reason)
            try:
                observation = self._request(cell)
            except WeatherUnavailableError as exc:
                self._cooldown_until = now + self._error_cooldown_s
                self._cooldown_reason = (
                    f"{exc.reason} Kolejna próba za ok. {round(self._error_cooldown_s / 60)} min."
                )
                logger.warning("Pogoda Weatherbit niedostępna: %s", exc.reason)
                raise
            self._cache[cell] = (now + self._cache_ttl_s, observation)
            return observation

    def _request(self, cell: tuple[float, float]) -> WeatherObservation:
        lat, lon = cell
        query = urllib.parse.urlencode({"lat": lat, "lon": lon, "units": "M", "key": self._api_key})
        url = f"{self._base_url}/current?{query}"
        self.requests_sent += 1
        try:
            body = self._fetch(url, self._timeout_s)
        except urllib.error.HTTPError as exc:
            # ``from None``: the exception holds the URL with the key — keep it out of tracebacks.
            raise WeatherUnavailableError(_http_reason(exc.code)) from None
        except (urllib.error.URLError, OSError) as exc:
            # urllib wraps a connect timeout in URLError(reason=TimeoutError).
            reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
            if isinstance(reason, TimeoutError):
                message = f"Weatherbit nie odpowiedział w ciągu {self._timeout_s:g} s."
            else:
                message = "Brak połączenia z Weatherbit."
            raise WeatherUnavailableError(message) from None
        try:
            payload = json.loads(body) if body else None
        except ValueError:
            raise WeatherUnavailableError("Weatherbit zwrócił nieprawidłowy JSON.") from None
        return parse_current(payload, lat, lon)


def _http_reason(status: int) -> str:
    if status == 429:
        return "Przekroczono limit zapytań Weatherbit (HTTP 429)."
    if status in (401, 403):
        return f"Weatherbit odrzucił klucz API (HTTP {status}) — sprawdź WEATHERBIT_API_KEY."
    return f"Weatherbit zwrócił błąd HTTP {status}."
