from collections.abc import Sequence
from dataclasses import dataclass

from app.core.enums import TransportMode, TripPriority, WeatherStatus
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
from app.services.weather import (
    BikeWeatherAdjustment,
    WeatherAdjustmentService,
    WeatherContext,
    WeatherService,
)


@dataclass(frozen=True, slots=True)
class WeatherOutcome:
    """Co porównanie zrobiło z pogodą: kontekst (skąd, kiedy, dlaczego) i ewentualna korekta."""

    context: WeatherContext
    bike_adjustment: BikeWeatherAdjustment | None = None

    @property
    def adjustment_applied(self) -> bool:
        return self.bike_adjustment is not None


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    trip: TripInput
    priority: TripPriority
    estimates: tuple[ModeEstimate, ...]
    recommendation: Recommendation
    weather: WeatherOutcome | None = None  # None = porównanie bez serwisu pogody


class ComparisonService:
    """Liczy szacunki dla wszystkich środków transportu i wybiera rekomendację."""

    def __init__(
        self,
        calculators: Sequence[TransportCalculator],
        recommender: RecommendationService | None = None,
        weather: WeatherService | None = None,
        adjuster: WeatherAdjustmentService | None = None,
    ) -> None:
        modes = [c.mode for c in calculators]
        if len(set(modes)) != len(modes):
            raise ValueError("Każdy środek transportu może mieć tylko jeden kalkulator")
        self.calculators = tuple(calculators)
        self.recommender = recommender or RecommendationService()
        self.weather = weather
        self.adjuster = adjuster or WeatherAdjustmentService()

    @classmethod
    def from_settings(
        cls,
        params: TransportSettings,
        transit_time_provider: TransitTimeProvider | None = None,
        weather: WeatherService | None = None,
    ) -> "ComparisonService":
        """Domyślny zestaw kalkulatorów. ``transit_time_provider`` to punkt wpięcia GTFS."""
        return cls(
            [
                CarCalculator(params.car),
                PublicTransportCalculator(params.public_transport, transit_time_provider),
                BikeCalculator(params.bike),
            ],
            weather=weather,
        )

    def compare(self, trip: TripInput, priority: TripPriority) -> ComparisonResult:
        estimates = tuple(calculator.estimate(trip) for calculator in self.calculators)
        weather = self._weather(trip, estimates)
        if weather and weather.bike_adjustment:
            estimates = tuple(self.adjuster.apply(e, weather.bike_adjustment) for e in estimates)
        return ComparisonResult(
            trip=trip,
            priority=priority,
            estimates=estimates,
            recommendation=self.recommender.recommend(estimates, priority),
            weather=weather,
        )

    def _weather(self, trip: TripInput, estimates: Sequence[ModeEstimate]) -> WeatherOutcome | None:
        if self.weather is None:
            return None
        bike_available = any(e.mode is TransportMode.BIKE and e.available for e in estimates)
        if not bike_available:
            # Pogoda wpływa tylko na rower — bez niego nie zużywamy limitu zapytań API.
            return WeatherOutcome(
                WeatherContext(
                    WeatherStatus.NOT_APPLICABLE,
                    "Rower jest niedostępny dla tej podróży — korekta pogodowa nie dotyczy "
                    "żadnego wariantu.",
                )
            )
        context = self.weather.assess(trip)
        if context.status is not WeatherStatus.APPLIED or context.observation is None:
            return WeatherOutcome(context)
        return WeatherOutcome(context, self.adjuster.assess_bike(context.observation))
