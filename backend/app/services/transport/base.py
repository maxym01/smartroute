"""Wspólne typy kalkulatorów transportu. Moduł nie zależy od FastAPI ani od bazy danych."""

from dataclasses import dataclass, field
from typing import Protocol

from app.core.enums import DataSource, TransportMode

MODE_LABELS: dict[TransportMode, str] = {
    TransportMode.CAR: "Samochód",
    TransportMode.PUBLIC_TRANSPORT: "Komunikacja miejska",
    TransportMode.BIKE: "Rower",
}

# Precyzja zaokrągleń wyników. Ranking działa na wartościach zaokrąglonych, czyli tych,
# które widzi użytkownik — dzięki temu remisy są spójne z tym, co pokazuje API.
DURATION_DECIMALS = 1
COST_DECIMALS = 2
CO2_DECIMALS = 3


@dataclass(frozen=True, slots=True)
class TripInput:
    """Dane wejściowe porównania, niezależne od modelu ORM."""

    distance_km: float
    passengers: int = 1
    has_car: bool = True
    allow_bike: bool = True
    origin: str | None = None
    destination: str | None = None

    def __post_init__(self) -> None:
        if not self.distance_km > 0:
            raise ValueError("distance_km musi być większe od 0")
        if self.passengers < 1:
            raise ValueError("passengers musi wynosić co najmniej 1")


@dataclass(frozen=True, slots=True)
class ModeEstimate:
    """Szacunek dla jednego środka transportu. Koszt i CO₂ dotyczą całej grupy pasażerów."""

    mode: TransportMode
    available: bool
    unavailable_reason: str | None
    duration_min: float
    cost_pln: float
    cost_per_passenger_pln: float
    co2_kg: float
    co2_per_passenger_kg: float
    data_source: DataSource
    assumptions: tuple[str, ...] = field(default_factory=tuple)

    @property
    def label(self) -> str:
        return MODE_LABELS[self.mode]


class TransportCalculator(Protocol):
    mode: TransportMode

    def estimate(self, trip: TripInput) -> ModeEstimate: ...


def travel_time_min(distance_km: float, speed_kmh: float) -> float:
    if speed_kmh <= 0:
        raise ValueError("Prędkość musi być dodatnia")
    return distance_km / speed_kmh * 60


def per_passenger(total: float, passengers: int) -> float:
    return total / max(passengers, 1)


def fmt_number(value: float, decimals: int = 2) -> str:
    """Formatuje liczbę po polsku (przecinek dziesiętny), np. 4.4 → "4,40"."""
    return f"{value:.{decimals}f}".replace(".", ",")
