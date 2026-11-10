from app.core.enums import DataSource, TransportMode
from app.core.transport_params import BikeParams
from app.services.transport.base import (
    DURATION_DECIMALS,
    ModeEstimate,
    TripInput,
    fmt_number,
    travel_time_min,
)


class BikeCalculator:
    mode = TransportMode.BIKE

    def __init__(self, params: BikeParams) -> None:
        self.params = params

    def _unavailable_reason(self, trip: TripInput) -> str | None:
        if not trip.allow_bike:
            return "Rower wykluczony w preferencjach podróży (allow_bike=false)."
        if trip.distance_km > self.params.max_distance_km:
            return (
                f"Dystans {fmt_number(trip.distance_km, 1)} km przekracza przyjęty limit "
                f"{fmt_number(self.params.max_distance_km, 0)} km dla roweru."
            )
        return None

    def estimate(self, trip: TripInput) -> ModeEstimate:
        p = self.params
        reason = self._unavailable_reason(trip)
        return ModeEstimate(
            mode=self.mode,
            available=reason is None,
            unavailable_reason=reason,
            duration_min=round(
                travel_time_min(trip.distance_km, p.avg_speed_kmh), DURATION_DECIMALS
            ),
            cost_pln=0.0,
            cost_per_passenger_pln=0.0,
            co2_kg=0.0,
            co2_per_passenger_kg=0.0,
            data_source=DataSource.PARAMETRIC_ESTIMATE,
            assumptions=(
                f"Średnia prędkość {fmt_number(p.avg_speed_kmh, 0)} km/h, bez postojów.",
                "Każdy pasażer jedzie własnym rowerem; koszt eksploatacji pominięty (0 zł).",
                "Emisja w trakcie jazdy przyjęta jako 0 kg CO₂.",
                f"Rower uznajemy za realny do {fmt_number(p.max_distance_km, 0)} km.",
            ),
        )
