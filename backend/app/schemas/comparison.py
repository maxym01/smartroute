"""Schematy odpowiedzi porównania. Mapują wyniki domenowe z warstwy services na kontrakt API."""

from typing import Literal

from pydantic import BaseModel, Field

from app.core.enums import DataSource, TransportMode, TripPriority
from app.services.comparison_service import ComparisonResult
from app.services.recommendation_service import (
    BALANCED_WEIGHTS,
    TIE_BREAK_ORDER,
    ModeScore,
    describe_method,
)
from app.services.transport.base import ModeEstimate

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

    @classmethod
    def from_domain(cls, score: ModeScore) -> "ModeScoreRead":
        return cls(
            rank=score.rank,
            normalized_duration=score.normalized_duration,
            normalized_cost=score.normalized_cost,
            normalized_co2=score.normalized_co2,
            balanced_score=score.balanced_score,
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
        )
