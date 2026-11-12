"""Ustala, czy i jaką bieżącą pogodę można użyć dla podróży. Nigdy nie zgłasza wyjątku.

Kolejność warunków (pierwszy niespełniony kończy ocenę z wyjaśnieniem):

1. integracja włączona (jest ``WEATHERBIT_API_KEY``),
2. podróż odbywa się teraz lub wkrótce: ``departure_at`` w przedziale
   [teraz − 60 min, teraz + ``weather_max_lead_min``] — pogoda bieżąca nie jest prognozą,
3. wiarygodna lokalizacja: współrzędne przystanku startowego GTFS (``origin_stop_id``);
   tekstowych nazw miejsc (``origin``) nie zamieniamy na współrzędne,
4. odpowiedź Weatherbit (z cache lub z API).
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from sqlalchemy.exc import SQLAlchemyError

from app.core.enums import WeatherStatus
from app.core.timezone import LOCAL_TIMEZONE, as_local_aware
from app.services.transport.base import TripInput
from app.services.weather.client import (
    WeatherbitClient,
    WeatherObservation,
    WeatherUnavailableError,
)

logger = logging.getLogger(__name__)

PAST_TOLERANCE = timedelta(minutes=60)


class StopRecord(Protocol):
    stop_id: str
    stop_name: str
    stop_lat: float | None
    stop_lon: float | None


class StopLocator(Protocol):
    def get_stop(self, stop_id: str) -> StopRecord | None: ...


@dataclass(frozen=True, slots=True)
class WeatherLocation:
    stop_id: str
    stop_name: str
    lat: float
    lon: float


@dataclass(frozen=True, slots=True)
class WeatherContext:
    status: WeatherStatus
    message: str
    observation: WeatherObservation | None = None
    location: WeatherLocation | None = None


def _now_local() -> datetime:
    return datetime.now(LOCAL_TIMEZONE)


class WeatherService:
    def __init__(
        self,
        client: WeatherbitClient | None,
        locator: StopLocator | None,
        *,
        max_lead_min: int,
        now: Callable[[], datetime] = _now_local,
    ) -> None:
        self.client = client
        self.locator = locator
        self.max_lead = timedelta(minutes=max_lead_min)
        self.now = now

    def assess(self, trip: TripInput) -> WeatherContext:
        try:
            return self._assess(trip)
        except Exception:  # noqa: BLE001 — pogoda nigdy nie może zepsuć porównania
            logger.exception("Nieoczekiwany błąd oceny pogody")
            return WeatherContext(
                WeatherStatus.UNAVAILABLE, "Nieoczekiwany błąd pobierania pogody."
            )

    def _assess(self, trip: TripInput) -> WeatherContext:
        if self.client is None or not self.client.enabled:
            return WeatherContext(
                WeatherStatus.DISABLED,
                "Integracja pogodowa wyłączona (brak WEATHERBIT_API_KEY).",
            )

        if trip.departure_at is None:
            return WeatherContext(
                WeatherStatus.OUT_OF_TIME_WINDOW,
                "Brak departure_at — nie wiadomo, czy podróż odbywa się teraz, a bieżącej "
                "pogody nie stosujemy do innych terminów.",
            )
        departure = as_local_aware(trip.departure_at)
        now = self.now()
        if departure > now + self.max_lead:
            hours = self.max_lead.total_seconds() / 3600
            return WeatherContext(
                WeatherStatus.OUT_OF_TIME_WINDOW,
                f"Odjazd {departure.astimezone(LOCAL_TIMEZONE):%d.%m.%Y %H:%M} jest później niż "
                f"{hours:g} h od teraz — bieżąca pogoda nie jest prognozą, "
                "korekty nie zastosowano.",
            )
        if departure < now - PAST_TOLERANCE:
            return WeatherContext(
                WeatherStatus.OUT_OF_TIME_WINDOW,
                "Odjazd jest w przeszłości — bieżąca pogoda go nie opisuje, korekty nie "
                "zastosowano.",
            )

        location = self._locate(trip)
        if location is None:
            return WeatherContext(
                WeatherStatus.NO_LOCATION,
                "Brak wiarygodnej lokalizacji: pogodę ustalamy tylko ze współrzędnych przystanku "
                "startowego GTFS (origin_stop_id), nie z nazwy miejsca.",
            )

        try:
            observation = self.client.current(location.lat, location.lon)
        except WeatherUnavailableError as exc:
            return WeatherContext(
                WeatherStatus.UNAVAILABLE,
                f"{exc.reason} Porównanie bez korekty pogodowej.",
                location=location,
            )
        return WeatherContext(
            WeatherStatus.APPLIED,
            "Uwzględniono bieżącą pogodę Weatherbit w okolicy przystanku "
            f"{location.stop_name} (tylko komfort i czas roweru).",
            observation=observation,
            location=location,
        )

    def _locate(self, trip: TripInput) -> WeatherLocation | None:
        if self.locator is None or not trip.origin_stop_id:
            return None
        try:
            stop = self.locator.get_stop(trip.origin_stop_id)
        except SQLAlchemyError:  # np. baza rozkładu bez tabel
            return None
        if stop is None or stop.stop_lat is None or stop.stop_lon is None:
            return None
        lat, lon = stop.stop_lat, stop.stop_lon
        if not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0):
            return None
        return WeatherLocation(stop.stop_id, stop.stop_name, lat, lon)
