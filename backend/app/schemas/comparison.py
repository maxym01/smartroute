"""Schematy odpowiedzi porównania. Mapują wyniki domenowe z warstwy services na kontrakt API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.core.enums import (
    ComfortLevel,
    DataSource,
    TransportMode,
    TripPriority,
    WeatherStatus,
)
from app.services.comparison_service import ComparisonResult, WeatherOutcome
from app.services.recommendation_service import (
    BALANCED_WEIGHTS,
    COMFORT_RULE,
    TIE_BREAK_ORDER,
    ModeScore,
    describe_method,
)
from app.services.transport.base import ModeEstimate
from app.services.weather.adjustment import COMFORT_LABELS

DISCLAIMER = (
    "Wszystkie wartości są szacunkami z uproszczonego modelu i przyjętych parametrów "
    "konfiguracji. Nie są to pomiary, rzeczywiste rozkłady jazdy, bieżące ceny paliwa "
    "ani oficjalne taryfy przewoźników."
)


class ModeScoreRead(BaseModel):
    rank: int = Field(description="Miejsce w rankingu dostępnych wariantów (1 = rekomendowany)")
    normalized_duration: float = Field(description="Czas po normalizacji min-max (0 = najlepszy)")
    normalized_cost: float = Field(description="Koszt po normalizacji min-max (0 = najlepszy)")
    normalized_co2: float = Field(description="Emisja po normalizacji min-max (0 = najlepsza)")
    balanced_score: float = Field(description="Wynik ważony 1/3 każdej metryki (0..1)")
    weather_demoted: bool = Field(
        default=False,
        description="Przesunięty na koniec rankingu z powodu niskiego komfortu przy pogodzie",
    )

    @classmethod
    def from_domain(cls, score: ModeScore) -> "ModeScoreRead":
        return cls(
            rank=score.rank,
            normalized_duration=score.normalized_duration,
            normalized_cost=score.normalized_cost,
            normalized_co2=score.normalized_co2,
            balanced_score=score.balanced_score,
            weather_demoted=score.weather_demoted,
        )


class ModeEstimateRead(BaseModel):
    mode: TransportMode
    label: str
    available: bool
    unavailable_reason: str | None
    estimated_duration_min: float = Field(description="Szacowany czas od drzwi do drzwi [min]")
    estimated_cost_pln: float = Field(description="Szacowany koszt całego przejazdu [PLN]")
    estimated_cost_per_passenger_pln: float = Field(description="Koszt na pasażera [PLN]")
    estimated_co2_kg: float = Field(description="Szacowana emisja całego przejazdu [kg CO₂]")
    estimated_co2_per_passenger_kg: float = Field(description="Emisja na pasażera [kg CO₂]")
    is_estimate: Literal[True] = True
    data_source: DataSource
    assumptions: list[str]
    score: ModeScoreRead | None = Field(
        description="Dane rankingu; null dla wariantu niedostępnego"
    )
    comfort_level: ComfortLevel | None = Field(
        default=None,
        description="Komfort przy bieżącej pogodzie; null, gdy nie oceniano (obecnie tylko rower)",
    )

    @classmethod
    def from_domain(cls, estimate: ModeEstimate, score: ModeScore | None) -> "ModeEstimateRead":
        return cls(
            mode=estimate.mode,
            label=estimate.label,
            available=estimate.available,
            unavailable_reason=estimate.unavailable_reason,
            estimated_duration_min=estimate.duration_min,
            estimated_cost_pln=estimate.cost_pln,
            estimated_cost_per_passenger_pln=estimate.cost_per_passenger_pln,
            estimated_co2_kg=estimate.co2_kg,
            estimated_co2_per_passenger_kg=estimate.co2_per_passenger_kg,
            data_source=estimate.data_source,
            assumptions=list(estimate.assumptions),
            score=ModeScoreRead.from_domain(score) if score else None,
            comfort_level=estimate.comfort_level,
        )


class RecommendationRead(BaseModel):
    mode: TransportMode | None
    label: str | None
    explanation: str
    tie_break_applied: bool


class ScoringMethodRead(BaseModel):
    priority: TripPriority
    description: str
    balanced_weights: dict[str, float]
    tie_break_order: list[TransportMode]
    comfort_rule: str = COMFORT_RULE


class WeatherConditionsRead(BaseModel):
    source: Literal["weatherbit_current"] = "weatherbit_current"
    observed_at: datetime | None = Field(description="Czas obserwacji (UTC)")
    temperature_c: float
    precipitation_mm_h: float = Field(description="Opad (ekwiwalent wody) [mm/h]")
    snowfall_mm_h: float = Field(description="Opad śniegu [mm/h]")
    wind_speed_kmh: float = Field(description="Prędkość wiatru [km/h] (Weatherbit: m/s × 3,6)")
    description: str | None


class WeatherLocationRead(BaseModel):
    stop_id: str
    stop_name: str
    lat: float
    lon: float


class WeatherAdjustmentRead(BaseModel):
    mode: TransportMode = TransportMode.BIKE
    comfort_level: ComfortLevel
    duration_factor: float = Field(description="Mnożnik czasu jazdy (1.0 = bez zmian)")
    reasons: list[str]


def _weather_explanation(outcome: WeatherOutcome) -> str:
    adj = outcome.bike_adjustment
    if adj is None:
        return outcome.context.message
    verdict = f" Komfort roweru: {COMFORT_LABELS[adj.comfort_level]}"
    verdict += f" ({', '.join(adj.reasons)})." if adj.reasons else "."
    return outcome.context.message + verdict


class WeatherRead(BaseModel):
    """Bieżąca pogoda (nie prognoza) i jej wpływ na porównanie."""

    status: WeatherStatus
    adjustment_applied: bool
    explanation: str
    is_forecast: Literal[False] = False
    location: WeatherLocationRead | None = None
    conditions: WeatherConditionsRead | None = None
    adjustment: WeatherAdjustmentRead | None = None

    @classmethod
    def from_domain(cls, outcome: WeatherOutcome) -> "WeatherRead":
        ctx, obs, adj = outcome.context, outcome.context.observation, outcome.bike_adjustment
        loc = ctx.location
        return cls(
            status=ctx.status,
            adjustment_applied=outcome.adjustment_applied,
            explanation=_weather_explanation(outcome),
            location=WeatherLocationRead(
                stop_id=loc.stop_id, stop_name=loc.stop_name, lat=loc.lat, lon=loc.lon
            )
            if loc
            else None,
            conditions=WeatherConditionsRead(
                observed_at=obs.observed_at,
                temperature_c=obs.temperature_c,
                precipitation_mm_h=obs.precipitation_mm_h,
                snowfall_mm_h=obs.snowfall_mm_h,
                wind_speed_kmh=obs.wind_speed_kmh,
                description=obs.description,
            )
            if obs
            else None,
            adjustment=WeatherAdjustmentRead(
                comfort_level=adj.comfort_level,
                duration_factor=adj.duration_factor,
                reasons=list(adj.reasons),
            )
            if adj
            else None,
        )


class ComparisonResponse(BaseModel):
    trip_id: int
    priority: TripPriority
    distance_km: float
    passengers: int
    is_estimate: Literal[True] = True
    disclaimer: str = DISCLAIMER
    variants: list[ModeEstimateRead]
    recommendation: RecommendationRead
    scoring: ScoringMethodRead
    weather: WeatherRead | None = Field(
        default=None, description="Bieżąca pogoda i korekta roweru; null = nie oceniano"
    )

    @classmethod
    def from_result(cls, trip_id: int, result: ComparisonResult) -> "ComparisonResponse":
        rec = result.recommendation
        variants = [
            ModeEstimateRead.from_domain(e, rec.score_for(e.mode)) for e in result.estimates
        ]
        label = next((v.label for v in variants if v.mode is rec.mode), None)
        return cls(
            trip_id=trip_id,
            priority=result.priority,
            distance_km=result.trip.distance_km,
            passengers=result.trip.passengers,
            variants=variants,
            recommendation=RecommendationRead(
                mode=rec.mode,
                label=label,
                explanation=rec.explanation,
                tie_break_applied=rec.tie_break_applied,
            ),
            scoring=ScoringMethodRead(
                priority=result.priority,
                description=describe_method(result.priority),
                balanced_weights={k: round(v, 4) for k, v in BALANCED_WEIGHTS.items()},
                tie_break_order=list(TIE_BREAK_ORDER),
            ),
            weather=WeatherRead.from_domain(result.weather) if result.weather else None,
        )
