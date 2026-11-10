"""Komunikacja miejska.

Czas przejazdu pochodzi z wymiennego ``TransitTimeProvider``. Dziś domyślnym dostawcą jest
``ParametricTransitTimeProvider`` (dystans / średnia prędkość + dojście i oczekiwanie).
W kolejnym etapie można wstrzyknąć dostawcę opartego o rozkład GTFS — jeśli nie znajdzie
połączenia (zwróci ``None``), kalkulator automatycznie wraca do szacunku parametrycznego.
Koszt biletów i emisja zawsze pochodzą z parametrów konfiguracji.
"""

from dataclasses import dataclass, field
from typing import Protocol

from app.core.enums import DataSource, TransportMode
from app.core.transport_params import PublicTransportParams
from app.services.transport.base import (
    CO2_DECIMALS,
    COST_DECIMALS,
    DURATION_DECIMALS,
    ModeEstimate,
    TripInput,
    fmt_number,
    travel_time_min,
)


@dataclass(frozen=True, slots=True)
class TransitTimeEstimate:
    duration_min: float
    data_source: DataSource
    assumptions: tuple[str, ...] = field(default_factory=tuple)


class TransitTimeProvider(Protocol):
    def estimate(self, trip: TripInput) -> TransitTimeEstimate | None:
        """Zwraca czas przejazdu „od drzwi do drzwi” albo ``None``, gdy brak danych."""
        ...


class ParametricTransitTimeProvider:
    def __init__(self, params: PublicTransportParams) -> None:
        self.params = params

    def estimate(self, trip: TripInput) -> TransitTimeEstimate:
        p = self.params
        duration = travel_time_min(trip.distance_km, p.avg_speed_kmh) + p.access_wait_time_min
        return TransitTimeEstimate(
            duration_min=duration,
            data_source=DataSource.PARAMETRIC_ESTIMATE,
            assumptions=(
                f"Czas szacowany ze średniej prędkości {fmt_number(p.avg_speed_kmh, 0)} km/h, "
                "nie z rzeczywistego rozkładu jazdy.",
                f"Doliczono {fmt_number(p.access_wait_time_min, 0)} min na dojście do przystanku "
                "i oczekiwanie.",
            ),
        )


class PublicTransportCalculator:
    mode = TransportMode.PUBLIC_TRANSPORT

    def __init__(
        self,
        params: PublicTransportParams,
        time_provider: TransitTimeProvider | None = None,
    ) -> None:
        self.params = params
        self.fallback_provider = ParametricTransitTimeProvider(params)
        self.time_provider: TransitTimeProvider = time_provider or self.fallback_provider

    def ticket_price_per_person(self, distance_km: float) -> float:
        p = self.params
        extra_km = max(0.0, distance_km - p.base_ticket_max_km)
        return p.base_ticket_pln + extra_km * p.extra_pln_per_km

    def estimate(self, trip: TripInput) -> ModeEstimate:
        p = self.params
        time = self.time_provider.estimate(trip)
        fallback_note: tuple[str, ...] = ()
        if time is None:
            time = self.fallback_provider.estimate(trip)
            fallback_note = (
                "Brak danych z rozkładu dla tej trasy — użyto szacunku parametrycznego.",
            )

        ticket = self.ticket_price_per_person(trip.distance_km)
        co2_per_person = trip.distance_km * p.co2_kg_per_passenger_km

        return ModeEstimate(
            mode=self.mode,
            available=True,
            unavailable_reason=None,
            duration_min=round(time.duration_min, DURATION_DECIMALS),
            cost_pln=round(ticket * trip.passengers, COST_DECIMALS),
            cost_per_passenger_pln=round(ticket, COST_DECIMALS),
            co2_kg=round(co2_per_person * trip.passengers, CO2_DECIMALS),
            co2_per_passenger_kg=round(co2_per_person, CO2_DECIMALS),
            data_source=time.data_source,
            assumptions=(
                *fallback_note,
                *time.assumptions,
                f"Bilet {fmt_number(p.base_ticket_pln)} zł/os. do "
                f"{fmt_number(p.base_ticket_max_km, 0)} km, powyżej "
                f"+{fmt_number(p.extra_pln_per_km)} zł/km — taryfa przykładowa, nie oficjalna.",
                f"Każdy z {trip.passengers} pasażerów kupuje osobny bilet (bez ulg i biletów "
                "okresowych).",
                f"Emisja {fmt_number(p.co2_kg_per_passenger_km)} kg CO₂ na pasażerokilometr "
                "(średnia dla floty, przyjęta).",
            ),
        )
