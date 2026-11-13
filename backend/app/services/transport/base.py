"""Shared transport calculator types. The module depends on neither FastAPI nor the database."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from app.core.enums import ComfortLevel, DataSource, TransportMode

MODE_LABELS: dict[TransportMode, str] = {
    TransportMode.CAR: "Samochód",
    TransportMode.PUBLIC_TRANSPORT: "Komunikacja miejska",
    TransportMode.BIKE: "Rower",
}

# Rounding precision of the results. The ranking works on rounded values, i.e. the ones
# the user sees, so ties are consistent with what the API shows.
DURATION_DECIMALS = 1
COST_DECIMALS = 2
CO2_DECIMALS = 3


@dataclass(frozen=True, slots=True)
class TripInput:
    """Comparison input, independent of the ORM model."""

    distance_km: float
    passengers: int = 1
    has_car: bool = True
    allow_bike: bool = True
    origin: str | None = None
    destination: str | None = None
    # Optional GTFS timetable data. The stop ID is the feed identifier (stop_id), not the
    # origin/destination text — place names are never converted into stops.
    origin_stop_id: str | None = None
    destination_stop_id: str | None = None
    departure_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.distance_km > 0:
            raise ValueError("distance_km musi być większe od 0")
        if self.passengers < 1:
            raise ValueError("passengers musi wynosić co najmniej 1")


@dataclass(frozen=True, slots=True)
class ModeEstimate:
    """Estimate for one transport mode. Cost and CO₂ apply to the whole group of passengers."""

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
    # Set only by the weather adjustment (currently for the bike); None = not assessed.
    comfort_level: ComfortLevel | None = None

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
    """Format a number the Polish way (decimal comma), e.g. 4.4 → "4,40"."""
    return f"{value:.{decimals}f}".replace(".", ",")
