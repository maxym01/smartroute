"""Schematy Pydantic podróży: TripCreate (POST/PUT), TripUpdate (PATCH), TripRead, TripList."""

from datetime import UTC, datetime
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.timezone import LOCAL_TIMEZONE, as_local_aware
from app.models.trip import TripPriority

Name = Annotated[str, Field(min_length=1, max_length=100)]
Place = Annotated[str, Field(min_length=1, max_length=200)]
DistanceKm = Annotated[float, Field(gt=0, le=1000)]
Passengers = Annotated[int, Field(ge=1, le=8)]
Notes = Annotated[str | None, Field(max_length=500)]
StopId = Annotated[
    str | None,
    Field(
        min_length=1,
        max_length=64,
        description="stop_id z rozkładu GTFS (GET /api/v1/stops), nie nazwa miejsca",
    ),
]
DepartureAt = Annotated[
    datetime | None,
    Field(description="Planowany wyjazd; data bez strefy = czas lokalny Europe/Warsaw"),
]

REQUIRED_FIELDS = (
    "name",
    "origin",
    "destination",
    "distance_km",
    "passengers",
    "priority",
    "has_car",
    "allow_bike",
)

_INPUT_CONFIG = ConfigDict(str_strip_whitespace=True, extra="forbid")


def _empty_notes_to_none(value: object) -> object:
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _ensure_different_places(origin: str | None, destination: str | None) -> None:
    if (
        origin is not None
        and destination is not None
        and origin.casefold() == destination.casefold()
    ):
        raise ValueError("Punkt startu i cel muszą się różnić")


def _ensure_different_stops(origin_stop_id: str | None, destination_stop_id: str | None) -> None:
    if origin_stop_id is not None and origin_stop_id == destination_stop_id:
        raise ValueError("Przystanek startowy i docelowy muszą się różnić")


def _empty_to_none(value: object) -> object:
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _departure_with_timezone(value: datetime | None) -> datetime | None:
    return as_local_aware(value) if value is not None else None


GTFS_FIELDS = ("origin_stop_id", "destination_stop_id")


class TripCreate(BaseModel):
    model_config = _INPUT_CONFIG

    name: Name
    origin: Place
    destination: Place
    distance_km: DistanceKm
    passengers: Passengers = 1
    priority: TripPriority = TripPriority.BALANCED
    has_car: bool = True
    allow_bike: bool = True
    notes: Notes = None
    origin_stop_id: StopId = None
    destination_stop_id: StopId = None
    departure_at: DepartureAt = None

    _normalize_notes = field_validator("notes", mode="before")(_empty_notes_to_none)
    _normalize_stops = field_validator(*GTFS_FIELDS, mode="before")(_empty_to_none)
    _normalize_departure = field_validator("departure_at")(_departure_with_timezone)

    @model_validator(mode="after")
    def _check_places(self) -> Self:
        _ensure_different_places(self.origin, self.destination)
        _ensure_different_stops(self.origin_stop_id, self.destination_stop_id)
        return self


class TripUpdate(BaseModel):
    """Częściowa aktualizacja — pola opcjonalne, ale wymaganych nie można ustawić na null."""

    model_config = _INPUT_CONFIG

    name: Name | None = None
    origin: Place | None = None
    destination: Place | None = None
    distance_km: DistanceKm | None = None
    passengers: Passengers | None = None
    priority: TripPriority | None = None
    has_car: bool | None = None
    allow_bike: bool | None = None
    notes: Notes = None
    # Pola GTFS można wyczyścić wartością null.
    origin_stop_id: StopId = None
    destination_stop_id: StopId = None
    departure_at: DepartureAt = None

    _normalize_notes = field_validator("notes", mode="before")(_empty_notes_to_none)
    _normalize_stops = field_validator(*GTFS_FIELDS, mode="before")(_empty_to_none)
    _normalize_departure = field_validator("departure_at")(_departure_with_timezone)

    @field_validator(*REQUIRED_FIELDS, mode="before")
    @classmethod
    def _reject_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("Pole nie może mieć wartości null")
        return value

    @model_validator(mode="after")
    def _check_places(self) -> Self:
        _ensure_different_places(self.origin, self.destination)
        _ensure_different_stops(self.origin_stop_id, self.destination_stop_id)
        return self


class TripRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    origin: str
    destination: str
    distance_km: float
    passengers: int
    priority: TripPriority
    has_car: bool
    allow_bike: bool
    notes: str | None
    origin_stop_id: str | None = None
    destination_stop_id: str | None = None
    departure_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def _assume_utc(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    @field_validator("departure_at")
    @classmethod
    def _as_local_time(cls, value: datetime | None) -> datetime | None:
        # Zwracamy w czasie lokalnym (np. +01:00) — to ta sama chwila co zapisane UTC.
        if value is None:
            return None
        return (value if value.tzinfo else value.replace(tzinfo=UTC)).astimezone(LOCAL_TIMEZONE)


class TripList(BaseModel):
    items: list[TripRead]
    total: int
    skip: int
    limit: int
