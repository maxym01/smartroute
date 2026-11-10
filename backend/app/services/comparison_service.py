from collections.abc import Sequence
from dataclasses import dataclass

from app.core.enums import TripPriority
from app.core.transport_params import TransportSettings
from app.services.recommendation_service import Recommendation, RecommendationService
from app.services.transport import (
    BikeCalculator,
    CarCalculator,
    ModeEstimate,
    PublicTransportCalculator,
    TransitTimeProvider,
    TransportCalculator,
    TripInput,
)


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    trip: TripInput
    priority: TripPriority
    estimates: tuple[ModeEstimate, ...]
    recommendation: Recommendation


class ComparisonService:
    """Liczy szacunki dla wszystkich środków transportu i wybiera rekomendację."""

    def __init__(
        self,
        calculators: Sequence[TransportCalculator],
        recommender: RecommendationService | None = None,
    ) -> None:
        modes = [c.mode for c in calculators]
        if len(set(modes)) != len(modes):
            raise ValueError("Każdy środek transportu może mieć tylko jeden kalkulator")
        self.calculators = tuple(calculators)
        self.recommender = recommender or RecommendationService()

    @classmethod
    def from_settings(
        cls,
        params: TransportSettings,
        transit_time_provider: TransitTimeProvider | None = None,
    ) -> "ComparisonService":
        """Domyślny zestaw kalkulatorów. ``transit_time_provider`` to punkt wpięcia GTFS."""
        return cls(
            [
                CarCalculator(params.car),
                PublicTransportCalculator(params.public_transport, transit_time_provider),
                BikeCalculator(params.bike),
            ]
        )

    def compare(self, trip: TripInput, priority: TripPriority) -> ComparisonResult:
        estimates = tuple(calculator.estimate(trip) for calculator in self.calculators)
        return ComparisonResult(
            trip=trip,
            priority=priority,
            estimates=estimates,
            recommendation=self.recommender.recommend(estimates, priority),
        )
