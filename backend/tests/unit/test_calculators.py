import pytest
from pydantic import ValidationError

from app.core.enums import DataSource, TransportMode
from app.core.transport_params import (
    BikeParams,
    CarParams,
    PublicTransportParams,
    TransportSettings,
)
from app.services.transport import (
    BikeCalculator,
    CarCalculator,
    PublicTransportCalculator,
    TransitTimeEstimate,
    TripInput,
)
from app.services.transport.base import fmt_number, per_passenger, travel_time_min

CAR = CarParams()
PT = PublicTransportParams()
BIKE = BikeParams()


# --- TripInput i funkcje pomocnicze ---------------------------------------------------------


@pytest.mark.parametrize("distance", [0, -1])
def test_trip_input_rejects_non_positive_distance(distance: float) -> None:
    with pytest.raises(ValueError, match="distance_km"):
        TripInput(distance_km=distance)


@pytest.mark.parametrize("passengers", [0, -3])
def test_trip_input_rejects_less_than_one_passenger(passengers: int) -> None:
    with pytest.raises(ValueError, match="passengers"):
        TripInput(distance_km=5, passengers=passengers)


def test_travel_time_rejects_zero_speed() -> None:
    with pytest.raises(ValueError):
        travel_time_min(10, 0)


def test_per_passenger_never_divides_by_zero() -> None:
    assert per_passenger(10.0, 0) == 10.0
    assert per_passenger(10.0, 4) == 2.5


def test_fmt_number_uses_polish_decimal_comma() -> None:
    assert fmt_number(4.4) == "4,40"
    assert fmt_number(12.345, 1) == "12,3"


@pytest.mark.parametrize(
    ("model", "field"),
    [
        (CarParams, "avg_speed_kmh"),
        (PublicTransportParams, "avg_speed_kmh"),
        (PublicTransportParams, "base_ticket_max_km"),
        (BikeParams, "avg_speed_kmh"),
        (BikeParams, "max_distance_km"),
    ],
)
def test_params_reject_zero_in_denominators(model, field: str) -> None:
    with pytest.raises(ValidationError):
        model(**{field: 0})


def test_params_reject_negative_prices() -> None:
    with pytest.raises(ValidationError):
        CarParams(fuel_price_pln_per_l=-1)


def test_params_are_documented_with_units() -> None:
    for model in (CarParams, PublicTransportParams, BikeParams):
        for name, info in model.model_fields.items():
            assert info.description and "[" in info.description, f"{model.__name__}.{name}"


def test_transport_settings_defaults() -> None:
    settings = TransportSettings()
    assert settings.car == CAR and settings.public_transport == PT and settings.bike == BIKE


# --- samochód -------------------------------------------------------------------------------


def test_car_estimate_for_single_passenger() -> None:
    e = CarCalculator(CAR).estimate(TripInput(distance_km=20))

    assert e.mode is TransportMode.CAR
    assert e.available is True and e.unavailable_reason is None
    assert e.duration_min == pytest.approx(20 / 40 * 60 + 5)  # 35 min
    assert e.cost_pln == pytest.approx(9.10)  # 20 km · 7 l/100 km · 6,50 zł/l
    assert e.co2_kg == pytest.approx(3.4)  # 20 km · 0,17 kg/km
    assert e.cost_per_passenger_pln == e.cost_pln
    assert e.data_source is DataSource.PARAMETRIC_ESTIMATE
    assert e.assumptions


def test_car_cost_is_per_vehicle_and_split_between_passengers() -> None:
    solo = CarCalculator(CAR).estimate(TripInput(distance_km=20, passengers=1))
    group = CarCalculator(CAR).estimate(TripInput(distance_km=20, passengers=4))

    assert group.cost_pln == solo.cost_pln
    assert group.co2_kg == solo.co2_kg
    assert group.cost_per_passenger_pln == pytest.approx(9.10 / 4, abs=0.01)
    assert group.co2_per_passenger_kg == pytest.approx(0.85)


def test_car_unavailable_without_car_but_still_estimated() -> None:
    e = CarCalculator(CAR).estimate(TripInput(distance_km=10, has_car=False))

    assert e.available is False
    assert "has_car" in e.unavailable_reason
    assert e.duration_min > 0 and e.cost_pln > 0


def test_car_uses_custom_params() -> None:
    params = CarParams(avg_speed_kmh=60, parking_time_min=0, fuel_price_pln_per_l=10)
    e = CarCalculator(params).estimate(TripInput(distance_km=30))

    assert e.duration_min == pytest.approx(30)
    assert e.cost_pln == pytest.approx(30 * 7 / 100 * 10)


# --- komunikacja miejska --------------------------------------------------------------------


def test_public_transport_within_base_ticket() -> None:
    e = PublicTransportCalculator(PT).estimate(TripInput(distance_km=10))

    assert e.available is True
    assert e.duration_min == pytest.approx(round(10 / 22 * 60 + 8, 1))
    assert e.cost_pln == pytest.approx(4.40)
    assert e.co2_kg == pytest.approx(0.5)


def test_public_transport_ticket_surcharge_above_base_distance() -> None:
    calc = PublicTransportCalculator(PT)

    assert calc.ticket_price_per_person(10) == pytest.approx(4.40)
    assert calc.ticket_price_per_person(20) == pytest.approx(4.40 + 10 * 0.25)
    assert calc.ticket_price_per_person(0.5) == pytest.approx(4.40)


def test_public_transport_cost_and_co2_scale_with_passengers() -> None:
    e = PublicTransportCalculator(PT).estimate(TripInput(distance_km=10, passengers=3))

    assert e.cost_per_passenger_pln == pytest.approx(4.40)
    assert e.cost_pln == pytest.approx(13.20)
    assert e.co2_per_passenger_kg == pytest.approx(0.5)
    assert e.co2_kg == pytest.approx(1.5)


def test_public_transport_is_available_regardless_of_preferences() -> None:
    e = PublicTransportCalculator(PT).estimate(
        TripInput(distance_km=1000, has_car=False, allow_bike=False)
    )

    assert e.available is True


class FakeScheduleProvider:
    """Atrapa przyszłego dostawcy GTFS — bez dostępu do sieci."""

    def __init__(self, result: TransitTimeEstimate | None) -> None:
        self.result = result
        self.calls: list[TripInput] = []

    def estimate(self, trip: TripInput) -> TransitTimeEstimate | None:
        self.calls.append(trip)
        return self.result


def test_public_transport_uses_injected_time_provider() -> None:
    provider = FakeScheduleProvider(
        TransitTimeEstimate(42.0, DataSource.GTFS_SCHEDULE, ("Połączenie z rozkładu.",))
    )
    trip = TripInput(distance_km=10, origin="A", destination="B")

    e = PublicTransportCalculator(PT, provider).estimate(trip)

    assert provider.calls == [trip]
    assert e.duration_min == 42.0
    assert e.data_source is DataSource.GTFS_SCHEDULE
    assert "Połączenie z rozkładu." in e.assumptions
    assert e.cost_pln == pytest.approx(4.40)  # koszt nadal z parametrów


def test_public_transport_falls_back_when_provider_has_no_data() -> None:
    e = PublicTransportCalculator(PT, FakeScheduleProvider(None)).estimate(
        TripInput(distance_km=10)
    )

    assert e.data_source is DataSource.PARAMETRIC_ESTIMATE
    assert e.duration_min == pytest.approx(round(10 / 22 * 60 + 8, 1))
    assert "Brak danych z rozkładu" in e.assumptions[0]


# --- rower ----------------------------------------------------------------------------------


def test_bike_estimate() -> None:
    e = BikeCalculator(BIKE).estimate(TripInput(distance_km=15, passengers=3))

    assert e.available is True
    assert e.duration_min == pytest.approx(60)
    assert (e.cost_pln, e.co2_kg, e.cost_per_passenger_pln, e.co2_per_passenger_kg) == (0, 0, 0, 0)


def test_bike_available_exactly_at_distance_limit() -> None:
    assert BikeCalculator(BIKE).estimate(TripInput(distance_km=20)).available is True


def test_bike_unavailable_above_distance_limit() -> None:
    e = BikeCalculator(BIKE).estimate(TripInput(distance_km=20.1))

    assert e.available is False
    assert "limit" in e.unavailable_reason


def test_bike_unavailable_when_not_allowed() -> None:
    e = BikeCalculator(BIKE).estimate(TripInput(distance_km=5, allow_bike=False))

    assert e.available is False
    assert "allow_bike" in e.unavailable_reason


def test_bike_preference_reason_takes_precedence_over_distance() -> None:
    e = BikeCalculator(BIKE).estimate(TripInput(distance_km=50, allow_bike=False))

    assert "allow_bike" in e.unavailable_reason
