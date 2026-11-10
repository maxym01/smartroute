"""Deterministyczny wybór rekomendowanego środka transportu.

Algorytm
--------
1. Pod uwagę bierzemy tylko warianty ``available=True``. Niedostępne nigdy nie są rekomendowane.
2. Dla każdej metryki m ∈ {czas, koszt, CO₂} liczymy normalizację min-max wśród dostępnych
   wariantów::

       norm_m(x) = (x - min_m) / (max_m - min_m)     (0 = najlepszy, 1 = najgorszy)

   Gdy wszystkie wartości są równe (max = min, np. jeden dostępny wariant), norm_m = 0.
3. Priorytety jednokryterialne (``fastest``, ``cheapest``, ``greenest``) porządkują warianty
   leksykograficznie: najpierw metryka główna, potem pozostałe jako dogrywka
   (fastest: czas → koszt → CO₂; cheapest: koszt → czas → CO₂; greenest: CO₂ → czas → koszt).
   Dzięki temu „najszybszy” zawsze oznacza faktycznie najkrótszy czas.
4. ``balanced`` liczy wynik ważony::

       score = 1/3 · norm_czas + 1/3 · norm_koszt + 1/3 · norm_CO₂     (0..1, mniej = lepiej)

   zaokrąglony do 4 miejsc, i wybiera najniższy wynik.
5. Pełny remis rozstrzyga stała kolejność: rower → komunikacja miejska → samochód
   (preferencja dla wariantów tańszych w emisji). Wynik jest więc zawsze deterministyczny.

Porównania działają na wartościach zaokrąglonych tak, jak zwraca je API (patrz ``base.py``).
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from app.core.enums import TransportMode, TripPriority
from app.services.transport.base import MODE_LABELS, ModeEstimate, fmt_number

Metric = Literal["duration", "cost", "co2"]
METRICS: tuple[Metric, ...] = ("duration", "cost", "co2")

BALANCED_WEIGHTS: MappingProxyType[Metric, float] = MappingProxyType(
    {"duration": 1 / 3, "cost": 1 / 3, "co2": 1 / 3}
)
TIE_BREAK_ORDER: tuple[TransportMode, ...] = (
    TransportMode.BIKE,
    TransportMode.PUBLIC_TRANSPORT,
    TransportMode.CAR,
)
LEXICOGRAPHIC_ORDER: MappingProxyType[TripPriority, tuple[Metric, ...]] = MappingProxyType(
    {
        TripPriority.FASTEST: ("duration", "cost", "co2"),
        TripPriority.CHEAPEST: ("cost", "duration", "co2"),
        TripPriority.GREENEST: ("co2", "duration", "cost"),
    }
)
SCORE_DECIMALS = 4

_METRIC_NAMES: dict[Metric, str] = {"duration": "czas", "cost": "koszt", "co2": "emisja CO₂"}


def metric_value(estimate: ModeEstimate, metric: Metric) -> float:
    if metric == "duration":
        return estimate.duration_min
    if metric == "cost":
        return estimate.cost_pln
    return estimate.co2_kg


def describe_method(priority: TripPriority) -> str:
    tie = " → ".join(MODE_LABELS[mode].lower() for mode in TIE_BREAK_ORDER)
    if priority is TripPriority.BALANCED:
        return (
            "Normalizacja min-max każdej metryki wśród dostępnych wariantów (0 = najlepszy, "
            "1 = najgorszy), wynik = 1/3·czas + 1/3·koszt + 1/3·CO₂, wygrywa najniższy wynik. "
            f"Remis: {tie}."
        )
    order = " → ".join(_METRIC_NAMES[m] for m in LEXICOGRAPHIC_ORDER[priority])
    return f"Porządek leksykograficzny wśród dostępnych wariantów: {order}. Remis: {tie}."


@dataclass(frozen=True, slots=True)
class ModeScore:
    mode: TransportMode
    rank: int
    normalized_duration: float
    normalized_cost: float
    normalized_co2: float
    balanced_score: float


@dataclass(frozen=True, slots=True)
class Recommendation:
    priority: TripPriority
    mode: TransportMode | None
    explanation: str
    scores: tuple[ModeScore, ...]  # tylko warianty dostępne, w kolejności rankingu
    tie_break_applied: bool

    def score_for(self, mode: TransportMode) -> ModeScore | None:
        return next((score for score in self.scores if score.mode is mode), None)


def _min_max(values: Sequence[float]) -> list[float]:
    low, high = min(values), max(values)
    spread = high - low
    if spread == 0:
        return [0.0 for _ in values]
    return [(value - low) / spread for value in values]


class RecommendationService:
    def recommend(
        self, estimates: Sequence[ModeEstimate], priority: TripPriority
    ) -> Recommendation:
        candidates = [e for e in estimates if e.available]
        unavailable = [e for e in estimates if not e.available]
        if not candidates:
            return Recommendation(
                priority=priority,
                mode=None,
                explanation="Żaden wariant nie jest dostępny dla tej podróży — brak rekomendacji. "
                + self._unavailable_sentence(unavailable),
                scores=(),
                tie_break_applied=False,
            )

        normalized = self._normalize(candidates)
        balanced = {
            mode: round(sum(BALANCED_WEIGHTS[m] * norms[m] for m in METRICS), SCORE_DECIMALS)
            for mode, norms in normalized.items()
        }
        criteria = self._criteria(priority, balanced)

        def sort_key(estimate: ModeEstimate) -> tuple[float | int, ...]:
            return (*(c(estimate) for c in criteria), TIE_BREAK_ORDER.index(estimate.mode))

        ranked = sorted(candidates, key=sort_key)
        winner = ranked[0]
        tie_break_applied = len(ranked) > 1 and sort_key(ranked[0])[:-1] == sort_key(ranked[1])[:-1]

        scores = tuple(
            ModeScore(
                mode=e.mode,
                rank=rank,
                normalized_duration=round(normalized[e.mode]["duration"], SCORE_DECIMALS),
                normalized_cost=round(normalized[e.mode]["cost"], SCORE_DECIMALS),
                normalized_co2=round(normalized[e.mode]["co2"], SCORE_DECIMALS),
                balanced_score=balanced[e.mode],
            )
            for rank, e in enumerate(ranked, start=1)
        )
        explanation = self._explain(priority, ranked, unavailable, balanced, tie_break_applied)
        return Recommendation(priority, winner.mode, explanation, scores, tie_break_applied)

    @staticmethod
    def _normalize(candidates: Sequence[ModeEstimate]) -> dict[TransportMode, dict[Metric, float]]:
        result: dict[TransportMode, dict[Metric, float]] = {e.mode: {} for e in candidates}
        for metric in METRICS:
            values = _min_max([metric_value(e, metric) for e in candidates])
            for estimate, value in zip(candidates, values, strict=True):
                result[estimate.mode][metric] = value
        return result

    @staticmethod
    def _criteria(
        priority: TripPriority, balanced: dict[TransportMode, float]
    ) -> list[Callable[[ModeEstimate], float]]:
        if priority is TripPriority.BALANCED:
            return [lambda e: balanced[e.mode]]
        return [
            (lambda e, m=metric: metric_value(e, m)) for metric in LEXICOGRAPHIC_ORDER[priority]
        ]

    # --- uzasadnienie po polsku ---------------------------------------------------------------

    def _explain(
        self,
        priority: TripPriority,
        ranked: Sequence[ModeEstimate],
        unavailable: Sequence[ModeEstimate],
        balanced: dict[TransportMode, float],
        tie_break_applied: bool,
    ) -> str:
        winner = ranked[0]
        sentences = [self._headline(priority, winner, balanced[winner.mode], len(ranked))]
        sentences += [self._versus(winner, other) for other in ranked[1:]]
        if tie_break_applied:
            order = " → ".join(MODE_LABELS[m].lower() for m in TIE_BREAK_ORDER)
            sentences.append(f"Wystąpił remis — rozstrzygnięto stałą kolejnością: {order}.")
        if unavailable:
            sentences.append(self._unavailable_sentence(unavailable))
        sentences.append("Wszystkie wartości są szacunkowe.")
        return " ".join(sentences)

    @staticmethod
    def _headline(priority: TripPriority, winner: ModeEstimate, score: float, count: int) -> str:
        label = winner.label
        if count == 1:
            return f"{label} to jedyny dostępny wariant."
        if priority is TripPriority.FASTEST:
            return (
                f"{label} to najszybszy dostępny wariant: ok. "
                f"{fmt_number(winner.duration_min, 0)} min."
            )
        if priority is TripPriority.CHEAPEST:
            return (
                f"{label} to najtańszy dostępny wariant: ok. "
                f"{fmt_number(winner.cost_pln)} zł za cały przejazd."
            )
        if priority is TripPriority.GREENEST:
            return (
                f"{label} ma najniższą szacowaną emisję: ok. {fmt_number(winner.co2_kg, 2)} kg CO₂."
            )
        return (
            f"{label} daje najlepszy kompromis czasu, kosztu i emisji "
            f"(wynik {fmt_number(score, 2)} w skali 0–1, im mniej, tym lepiej)."
        )

    @staticmethod
    def _versus(winner: ModeEstimate, other: ModeEstimate) -> str:
        d_time = winner.duration_min - other.duration_min
        if abs(d_time) < 0.5:
            time = "podobny czas"
        else:
            time = f"{fmt_number(abs(d_time), 0)} min {'szybciej' if d_time < 0 else 'dłużej'}"

        d_cost = round(winner.cost_pln - other.cost_pln, 2)
        if d_cost == 0:
            cost = "ten sam koszt"
        else:
            cost = f"{fmt_number(abs(d_cost))} zł {'taniej' if d_cost < 0 else 'drożej'}"

        d_co2 = round(winner.co2_kg - other.co2_kg, 3)
        if d_co2 == 0:
            co2 = "ta sama emisja"
        else:
            decimals = 2 if abs(d_co2) >= 0.01 else 3
            co2 = f"{fmt_number(abs(d_co2), decimals)} kg CO₂ {'mniej' if d_co2 < 0 else 'więcej'}"

        return f"Względem wariantu „{other.label}”: {time}, {cost}, {co2}."

    @staticmethod
    def _unavailable_sentence(unavailable: Sequence[ModeEstimate]) -> str:
        if not unavailable:
            return ""
        parts = "; ".join(
            f"{e.label} — {(e.unavailable_reason or 'niedostępny').rstrip('.')}"
            for e in unavailable
        )
        return f"Pominięto niedostępne: {parts}."
