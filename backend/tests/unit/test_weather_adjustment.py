"""WeatherAdjustmentService and the comfort rule in the recommendation."""

from dataclasses import replace

import pytest

from app.core.enums import ComfortLevel, TransportMode, TripPriority
from app.core.transport_params import TransportSettings
from app.services.recommendation_service import RecommendationService
from app.services.transport import BikeCalculator, CarCalculator, TripInput
from app.services.transport.public_transport import PublicTransportCalculator
from app.services.weather import WeatherAdjustmentService
from app.services.weather.client import parse_current
from tests.weather_factory import GOOD, RAIN, STRONG_WIND, current_payload

adjuster = WeatherAdjustmentService()


def obs(payload):
    return parse_current(payload, 54.4, 18.6)


def test_good_weather_keeps_bike_unchanged() -> None:
    adj = adjuster.assess_bike(obs(GOOD))
    assert adj.comfort_level is ComfortLevel.GOOD
    assert adj.duration_factor == 1.0
    assert adj.reasons == ()


@pytest.mark.parametrize(
    ("payload", "level"),
    [
        (current_payload(precip=0.5, code=500), ComfortLevel.REDUCED),
        (RAIN, ComfortLevel.POOR),
        (current_payload(wind_spd=8.0), ComfortLevel.REDUCED),  # 28,8 km/h
        (STRONG_WIND, ComfortLevel.POOR),  # 43,2 km/h
        (current_payload(temp=1.0), ComfortLevel.REDUCED),
        (current_payload(temp=-8.0), ComfortLevel.POOR),
        (current_payload(temp=30.0), ComfortLevel.REDUCED),
        (current_payload(temp=35.0), ComfortLevel.POOR),
        (current_payload(code=201, description="Thunderstorm with rain"), ComfortLevel.POOR),
        (current_payload(code=601, snow=1.0, temp=-1.0), ComfortLevel.POOR),
    ],
    ids=[
        "light-rain",
        "heavy-rain",
        "wind",
        "strong-wind",
        "cold",
        "frost",
        "hot",
        "heat",
        "storm",
        "snow",
    ],
)
def test_comfort_levels(payload, level: ComfortLevel) -> None:
    adj = adjuster.assess_bike(obs(payload))
    assert adj.comfort_level is level
    assert adj.reasons


def test_wind_moderately_increases_duration_rain_does_not() -> None:
    assert adjuster.assess_bike(obs(current_payload(wind_spd=8.0))).duration_factor == 1.1
    assert adjuster.assess_bike(obs(STRONG_WIND)).duration_factor == 1.2
    assert adjuster.assess_bike(obs(RAIN)).duration_factor == 1.0


def test_apply_changes_only_available_bike() -> None:
    params = TransportSettings()
    trip = TripInput(distance_km=6)
    bike = BikeCalculator(params.bike).estimate(trip)
    car = CarCalculator(params.car).estimate(trip)
    adj = adjuster.assess_bike(obs(STRONG_WIND))

    adjusted = adjuster.apply(bike, adj)
    assert adjusted.duration_min == round(bike.duration_min * 1.2, 1)
    assert adjusted.comfort_level is ComfortLevel.POOR
    assert (adjusted.cost_pln, adjusted.co2_kg) == (bike.cost_pln, bike.co2_kg)
    assert any("wiatru" in a for a in adjusted.assumptions)

    assert adjuster.apply(car, adj) is car
    unavailable = BikeCalculator(params.bike).estimate(TripInput(distance_km=6, allow_bike=False))
    assert adjuster.apply(unavailable, adj) is unavailable


# --- comfort rule in RecommendationService ---------------------------------------------------


def estimates(bike_comfort: ComfortLevel | None):
    params = TransportSettings()
    trip = TripInput(distance_km=4)
    bike = BikeCalculator(params.bike).estimate(trip)
    return (
        CarCalculator(params.car).estimate(trip),
        PublicTransportCalculator(params.public_transport).estimate(trip),
        replace(bike, comfort_level=bike_comfort),
    )


@pytest.mark.parametrize("priority", list(TripPriority))
def test_poor_bike_comfort_moves_bike_to_end_for_every_priority(priority: TripPriority) -> None:
    baseline = RecommendationService().recommend(estimates(None), priority)
    rec = RecommendationService().recommend(estimates(ComfortLevel.POOR), priority)

    bike = rec.score_for(TransportMode.BIKE)
    assert bike is not None and bike.weather_demoted and bike.rank == 3
    assert rec.mode is not TransportMode.BIKE
    # Weights and normalization unchanged — only the bike's position changes.
    assert bike.balanced_score == baseline.score_for(TransportMode.BIKE).balanced_score
    others = [s for s in baseline.scores if s.mode is not TransportMode.BIKE]
    assert [s.mode for s in rec.scores[:2]] == [s.mode for s in others]
    assert "przesunięto na koniec rankingu" in rec.explanation


def test_greenest_with_poor_bike_explains_restricted_pool() -> None:
    rec = RecommendationService().recommend(estimates(ComfortLevel.POOR), TripPriority.GREENEST)
    assert rec.mode is TransportMode.PUBLIC_TRANSPORT
    assert "spośród wariantów o akceptowalnym komforcie pogodowym" in rec.explanation


def test_reduced_comfort_only_warns() -> None:
    baseline = RecommendationService().recommend(estimates(None), TripPriority.GREENEST)
    rec = RecommendationService().recommend(estimates(ComfortLevel.REDUCED), TripPriority.GREENEST)

    assert rec.mode is baseline.mode is TransportMode.BIKE
    assert [s.rank for s in rec.scores] == [s.rank for s in baseline.scores]
    assert "komfort wariantu „Rower” obniżony" in rec.explanation


def test_no_demotion_when_bike_is_the_only_option() -> None:
    params = TransportSettings()
    trip = TripInput(distance_km=4, has_car=False)
    bike = replace(BikeCalculator(params.bike).estimate(trip), comfort_level=ComfortLevel.POOR)
    car = CarCalculator(params.car).estimate(trip)  # unavailable (has_car=False)

    rec = RecommendationService().recommend((car, bike), TripPriority.FASTEST)
    assert rec.mode is TransportMode.BIKE
    assert not rec.score_for(TransportMode.BIKE).weather_demoted
    assert "niski komfort wariantu „Rower”" in rec.explanation
