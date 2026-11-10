from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.models.trip import TripPriority
from app.schemas.trip import TripCreate, TripRead, TripUpdate

VALID = {"name": "Dom → praca", "origin": "Dom", "destination": "Praca", "distance_km": 10}


def test_trip_create_valid_with_defaults() -> None:
    trip = TripCreate(**VALID)

    assert trip.passengers == 1
    assert trip.priority is TripPriority.BALANCED
    assert trip.has_car is True and trip.allow_bike is True
    assert trip.notes is None


def test_trip_create_rejects_same_places() -> None:
    with pytest.raises(ValidationError, match="muszą się różnić"):
        TripCreate(**{**VALID, "destination": "  dOM "})


def test_trip_create_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        TripCreate(**VALID, id=5)


def test_trip_update_all_fields_optional() -> None:
    update = TripUpdate()

    assert update.model_dump(exclude_unset=True) == {}


def test_trip_update_keeps_only_set_fields() -> None:
    update = TripUpdate(name="  Nowa  ", notes=None)

    assert update.model_dump(exclude_unset=True) == {"name": "Nowa", "notes": None}


@pytest.mark.parametrize("field", ["name", "destination", "passengers", "allow_bike"])
def test_trip_update_rejects_null_in_required_fields(field: str) -> None:
    with pytest.raises(ValidationError, match="null"):
        TripUpdate(**{field: None})


def test_trip_update_rejects_same_places_when_both_given() -> None:
    with pytest.raises(ValidationError):
        TripUpdate(origin="A", destination="a")


def _read_payload(created_at: datetime) -> dict:
    return {
        **VALID,
        "id": 1,
        "passengers": 1,
        "priority": "balanced",
        "has_car": True,
        "allow_bike": True,
        "notes": None,
        "created_at": created_at,
        "updated_at": created_at,
    }


def test_trip_read_treats_naive_datetimes_as_utc() -> None:
    trip = TripRead(**_read_payload(datetime(2026, 1, 1, 12, 0)))

    assert trip.created_at == datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def test_trip_read_converts_aware_datetimes_to_utc() -> None:
    warsaw = timezone(timedelta(hours=1))
    trip = TripRead(**_read_payload(datetime(2026, 1, 1, 13, 0, tzinfo=warsaw)))

    assert trip.created_at == datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    assert trip.created_at.utcoffset() == timedelta(0)
