"""Deterministic, rule-based choice of the recommended transport mode.

Algorithm
---------
1. Only ``available=True`` options are considered. Unavailable ones are never recommended.
2. For each metric m ∈ {time, cost, CO₂}, the values are scaled by the largest value among
   the available options::

       norm_m(x) = x / max_m     (0 = zero value, 1 = the largest, i.e. worst, value)

   The score therefore reflects how large the differences are, not only which option is
   better: an option 10× slower but 0.5% cheaper does not win just by "winning more metrics".
   When max_m = 0 (e.g. zero cost for every option), norm_m = 0. A single available option
   gets 0 for every metric (there is nothing to compare it with). The scale still depends on
   the options being compared, so removing an option can, in rare cases, change the order of
   the remaining ones.
3. Single-criterion priorities (``fastest``, ``cheapest``, ``greenest``) order the options
   lexicographically: the main metric first, then the others as tie-breakers
   (fastest: time → cost → CO₂; cheapest: cost → time → CO₂; greenest: CO₂ → time → cost).
   This way "fastest" always means the shortest time. When two options tie on the main
   metric, the next metric decides, and the explanation says so explicitly.
4. ``balanced`` computes a weighted score::

       score = 1/3 · norm_time + 1/3 · norm_cost + 1/3 · norm_CO₂     (0..1, lower = better)

   rounded to 4 decimal places, and picks the lowest score.
5. A complete tie is resolved by a fixed order: bike → public transport → car
   (preferring lower-emission options). The result is therefore always deterministic.
6. Comfort rule (only when the comparison used current weather): an option with ``poor``
   comfort is moved to the end of the ranking if another available option exists. This is
   a separate, explicit step before the criteria in points 3–4; the weights and the
   time/cost/CO₂ normalization do not change, and the option keeps its ``balanced_score``
   (flagged ``weather_demoted``). ``reduced`` comfort does not change the ranking; it only
   adds a warning to the explanation.

Comparisons work on values rounded the same way the API returns them (see ``base.py``).
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from app.core.enums import ComfortLevel, TransportMode, TripPriority
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
            "Każda metryka dzielona przez największą wartość wśród dostępnych wariantów "
            "(0 = wartość zerowa, 1 = najgorsza), wynik = 1/3·czas + 1/3·koszt + 1/3·CO₂, "
            f"wygrywa najniższy wynik. Remis: {tie}."
        )
    order = " → ".join(_METRIC_NAMES[m] for m in LEXICOGRAPHIC_ORDER[priority])
    return f"Porządek leksykograficzny wśród dostępnych wariantów: {order}. Remis: {tie}."


COMFORT_RULE = (
    "Gdy uwzględniono bieżącą pogodę, wariant o niskim komforcie (poor) przesuwany jest na koniec "
    "rankingu, jeśli istnieje inny dostępny wariant; wagi czasu, kosztu i CO₂ się nie zmieniają."
)


@dataclass(frozen=True, slots=True)
class ModeScore:
    mode: TransportMode
    rank: int
    normalized_duration: float
    normalized_cost: float
    normalized_co2: float
    balanced_score: float
    weather_demoted: bool = False


@dataclass(frozen=True, slots=True)
class Recommendation:
    priority: TripPriority
    mode: TransportMode | None
    explanation: str
    scores: tuple[ModeScore, ...]  # available options only, in ranking order
    tie_break_applied: bool

    def score_for(self, mode: TransportMode) -> ModeScore | None:
        return next((score for score in self.scores if score.mode is mode), None)


def _scale_to_max(values: Sequence[float]) -> list[float]:
    """Divide by the largest value: keeps the ratio between options (all values are ≥ 0)."""
    high = max(values)
    if len(values) == 1 or high == 0:
        return [0.0 for _ in values]
    return [value / high for value in values]


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
        demoted = {e.mode for e in candidates if e.comfort_level is ComfortLevel.POOR}
        if len(demoted) == len(candidates):  # no alternative — the rule does not apply
            demoted = set()

        def sort_key(estimate: ModeEstimate) -> tuple[float | int, ...]:
            return (
                int(estimate.mode in demoted),
                *(c(estimate) for c in criteria),
                TIE_BREAK_ORDER.index(estimate.mode),
            )

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
                weather_demoted=e.mode in demoted,
            )
            for rank, e in enumerate(ranked, start=1)
        )
        explanation = self._explain(
            priority, ranked, unavailable, balanced, tie_break_applied, demoted
        )
        return Recommendation(priority, winner.mode, explanation, scores, tie_break_applied)

    @staticmethod
    def _normalize(candidates: Sequence[ModeEstimate]) -> dict[TransportMode, dict[Metric, float]]:
        result: dict[TransportMode, dict[Metric, float]] = {e.mode: {} for e in candidates}
        for metric in METRICS:
            values = _scale_to_max([metric_value(e, metric) for e in candidates])
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

    # --- explanation (in Polish) -------------------------------------------------------------

    def _explain(
        self,
        priority: TripPriority,
        ranked: Sequence[ModeEstimate],
        unavailable: Sequence[ModeEstimate],
        balanced: dict[TransportMode, float],
        tie_break_applied: bool,
        demoted: set[TransportMode],
    ) -> str:
        winner = ranked[0]
        pool = len(ranked) - len(demoted)
        sentences = [
            self._headline(priority, winner, balanced[winner.mode], pool, comfort=bool(demoted))
        ]
        if not tie_break_applied:
            sentences += self._secondary_tie_sentence(priority, ranked, demoted)
        sentences += [self._versus(winner, other) for other in ranked[1:]]
        if tie_break_applied:
            order = " → ".join(MODE_LABELS[m].lower() for m in TIE_BREAK_ORDER)
            sentences.append(f"Wystąpił remis — rozstrzygnięto stałą kolejnością: {order}.")
        sentences += self._comfort_sentences(ranked, demoted)
        if unavailable:
            sentences.append(self._unavailable_sentence(unavailable))
        sentences.append("Wszystkie wartości są szacunkowe.")
        return " ".join(sentences)

    @staticmethod
    def _headline(
        priority: TripPriority,
        winner: ModeEstimate,
        score: float,
        count: int,
        *,
        comfort: bool = False,
    ) -> str:
        label = winner.label
        # With the comfort rule active, compare only against options with acceptable comfort.
        pool = "wariant o akceptowalnym komforcie pogodowym" if comfort else "dostępny wariant"
        among = " spośród wariantów o akceptowalnym komforcie pogodowym" if comfort else ""
        if count == 1:
            return f"{label} to jedyny {pool}."
        if priority is TripPriority.FASTEST:
            return f"{label} to najszybszy {pool}: ok. {fmt_number(winner.duration_min, 0)} min."
        if priority is TripPriority.CHEAPEST:
            return (
                f"{label} to najtańszy {pool}: ok. "
                f"{fmt_number(winner.cost_pln)} zł za cały przejazd."
            )
        if priority is TripPriority.GREENEST:
            return (
                f"{label} ma najniższą szacowaną emisję{among}: ok. "
                f"{fmt_number(winner.co2_kg, 2)} kg CO₂."
            )
        return (
            f"{label} daje najlepszy kompromis czasu, kosztu i emisji{among} "
            f"(wynik {fmt_number(score, 2)} w skali 0–1, im mniej, tym lepiej)."
        )

    @staticmethod
    def _secondary_tie_sentence(
        priority: TripPriority, ranked: Sequence[ModeEstimate], demoted: set[TransportMode]
    ) -> list[str]:
        """Explicitly describe a tie on the main metric that a secondary criterion resolved."""
        if priority is TripPriority.BALANCED or len(ranked) < 2:
            return []
        winner, runner_up = ranked[0], ranked[1]
        if (runner_up.mode in demoted) != (winner.mode in demoted):
            return []
        primary, *secondary = LEXICOGRAPHIC_ORDER[priority]
        if metric_value(winner, primary) != metric_value(runner_up, primary):
            return []
        decisive = next(
            (m for m in secondary if metric_value(winner, m) != metric_value(runner_up, m)),
            None,
        )
        if decisive is None:  # a complete tie is described by the fixed-order sentence
            return []
        return [
            f"Taką samą wartość kryterium „{_METRIC_NAMES[primary]}” ma wariant "
            f"„{runner_up.label}” — rozstrzygnęło kolejne kryterium: {_METRIC_NAMES[decisive]}."
        ]

    @staticmethod
    def _comfort_sentences(
        ranked: Sequence[ModeEstimate], demoted: set[TransportMode]
    ) -> list[str]:
        sentences = []
        for estimate in ranked:
            if estimate.mode in demoted:
                sentences.append(
                    f"Wariant „{estimate.label}” przesunięto na koniec rankingu: niski komfort "
                    "przy bieżącej pogodzie."
                )
            elif estimate.comfort_level is ComfortLevel.REDUCED:
                sentences.append(
                    f"Uwaga: komfort wariantu „{estimate.label}” obniżony przez bieżącą pogodę."
                )
            elif estimate.comfort_level is ComfortLevel.POOR:  # no alternative
                sentences.append(
                    f"Uwaga: niski komfort wariantu „{estimate.label}” przy bieżącej pogodzie."
                )
        return sentences

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
