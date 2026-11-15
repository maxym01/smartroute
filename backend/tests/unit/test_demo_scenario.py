"""Regression test: the scenario shown in the demo recording (demo/SmartRoute_demo.mp4).

Dworzec Główny 01 (stop 2001) → Zaspa 01 (stop 2089), priority ``balanced``, 1 passenger.
The recording recommended the bike.

Inputs taken from the trips saved while the demo was recorded (Docker volume, 2026-11-15):
distance 5.9 km, car and bike allowed, departures 18:30 and 20:29. The public transport
times are the direct GTFS trips found for those departures in the ZTM Gdańsk feed used for
the recording (23.0 and 27.0 min); a stub provider pins them so the test stays offline.

Not recorded anywhere: the current weather at the time of the recording. Weather could only
lengthen the bike time (×1.1 at ``reduced`` comfort; ``poor`` comfort would have moved the bike
to the end of the ranking, which contradicts the recording), so the test covers both factors.

The assertions check the outcome shown in the demo (mode and ranking), not the exact
``balanced_score`` values, which depend on the normalisation method.
"""

from dataclasses import replace

import pytest

from app.core.enums import ComfortLevel, DataSource, TransportMode, TripPriority
from app.core.transport_params import TransportSettings
from app.services.comparison_service import ComparisonService
from app.services.recommendation_service import RecommendationService
from app.services.transport import TripInput
from app.services.transport.public_transport import TransitTimeEstimate

CAR, PT, BIKE = TransportMode.CAR, TransportMode.PUBLIC_TRANSPORT, TransportMode.BIKE

DEMO_TRIP = TripInput(
    distance_km=5.9,
    passengers=1,
    has_car=True,
    allow_bike=True,
    origin="Dworzec Główny 01",
    destination="Zaspa 01",
    origin_stop_id="2001",
    destination_stop_id="2089",
)


class _PinnedGtfsTime:
    """Stands in for the GTFS provider: returns the scheduled time found for the demo."""

    def __init__(self, duration_min: float) -> None:
        self.duration_min = duration_min

    def estimate(self, trip: TripInput) -> TransitTimeEstimate:
        return TransitTimeEstimate(self.duration_min, DataSource.GTFS_SCHEDULE)


def demo_estimates(gtfs_duration_min: float):
    service = ComparisonService.from_settings(
        TransportSettings(), _PinnedGtfsTime(gtfs_duration_min)
    )
    return service.compare(DEMO_TRIP, TripPriority.BALANCED).estimates


@pytest.mark.parametrize("gtfs_duration_min", [23.0, 27.0])
def test_demo_scenario_recommends_bike(gtfs_duration_min: float) -> None:
    estimates = demo_estimates(gtfs_duration_min)

    by_mode = {e.mode: e for e in estimates}
    assert all(e.available for e in estimates)
    assert by_mode[PT].data_source is DataSource.GTFS_SCHEDULE
    assert by_mode[PT].duration_min == gtfs_duration_min

    rec = RecommendationService().recommend(estimates, TripPriority.BALANCED)

    assert rec.mode is BIKE
    assert [s.mode for s in rec.scores] == [BIKE, CAR, PT]
    assert rec.tie_break_applied is False


@pytest.mark.parametrize("gtfs_duration_min", [23.0, 27.0])
def test_demo_scenario_recommends_bike_with_moderate_wind(gtfs_duration_min: float) -> None:
    estimates = [
        replace(
            e,
            duration_min=round(e.duration_min * 1.1, 1),
            comfort_level=ComfortLevel.REDUCED,
        )
        if e.mode is BIKE
        else e
        for e in demo_estimates(gtfs_duration_min)
    ]

    rec = RecommendationService().recommend(estimates, TripPriority.BALANCED)

    assert rec.mode is BIKE
    assert [s.mode for s in rec.scores] == [BIKE, CAR, PT]
