from dataclasses import replace

import pytest

from app.core.enums import DataSource, TransportMode, TripPriority
from app.core.transport_params import TransportSettings
from app.services.comparison_service import ComparisonService
from app.services.recommendation_service import RecommendationService, describe_method
from app.services.transport import CarCalculator, ModeEstimate, TripInput

CAR, PT, BIKE = TransportMode.CAR, TransportMode.PUBLIC_TRANSPORT, TransportMode.BIKE


def estimate(
    mode: TransportMode,
    duration: float,
    cost: float,
    co2: float,
    *,
    available: bool = True,
) -> ModeEstimate:
    return ModeEstimate(
        mode=mode,
        available=available,
        unavailable_reason=None if available else "niedostępny",
        duration_min=duration,
        cost_pln=cost,
        cost_per_passenger_pln=cost,
        co2_kg=co2,
        co2_per_passenger_kg=co2,
        data_source=DataSource.PARAMETRIC_ESTIMATE,
    )


# Scenario from the default parameters for 10 km and 1 person (see test_default_scenario...).
CITY = [estimate(CAR, 20.0, 4.55, 1.7), estimate(PT, 35.3, 4.40, 0.5), estimate(BIKE, 40.0, 0, 0)]

recommender = RecommendationService()


@pytest.mark.parametrize(
    ("priority", "expected"),
    [
        (TripPriority.FASTEST, CAR),
        (TripPriority.CHEAPEST, BIKE),
        (TripPriority.GREENEST, BIKE),
        (TripPriority.BALANCED, BIKE),
    ],
)
def test_each_priority_on_city_scenario(priority: TripPriority, expected: TransportMode) -> None:
    assert recommender.recommend(CITY, priority).mode is expected


def test_balanced_score_scales_each_metric_by_its_maximum_with_equal_weights() -> None:
    rec = recommender.recommend(CITY, TripPriority.BALANCED)
    car, pt, bike = (rec.score_for(m) for m in (CAR, PT, BIKE))

    # max values: time 40 (bike), cost 4.55 (car), CO₂ 1.7 (car)
    # car: time 20/40, cost 1, CO₂ 1
    assert (car.normalized_duration, car.normalized_cost, car.normalized_co2) == (0.5, 1, 1)
    assert car.balanced_score == pytest.approx(2.5 / 3, abs=1e-4)
    # pt: time 35.3/40, cost 4.40/4.55, CO₂ 0.5/1.7
    assert pt.normalized_duration == pytest.approx(35.3 / 40, abs=1e-4)
    assert pt.normalized_cost == pytest.approx(4.40 / 4.55, abs=1e-4)
    assert pt.normalized_co2 == pytest.approx(0.5 / 1.7, abs=1e-4)
    assert pt.balanced_score == pytest.approx((35.3 / 40 + 4.40 / 4.55 + 0.5 / 1.7) / 3, abs=1e-4)
    # bike: time 1, cost and CO₂ 0
    assert (bike.normalized_duration, bike.normalized_cost, bike.normalized_co2) == (1, 0, 0)
    assert bike.balanced_score == pytest.approx(1 / 3, abs=1e-4)
    assert [s.mode for s in rec.scores] == [BIKE, PT, CAR]
    assert [s.rank for s in rec.scores] == [1, 2, 3]


# --- balanced: regression tests for the min-max normalisation issue --------------------------


def test_balanced_respects_magnitude_of_differences() -> None:
    """135 min slower for 0.02 PLN less must not win just by being better on 2 of 3 metrics."""
    options = [estimate(CAR, 15.0, 4.42, 0.51), estimate(PT, 150.0, 4.40, 0.15)]

    rec = recommender.recommend(options, TripPriority.BALANCED)

    assert rec.mode is CAR
    assert not rec.explanation.startswith("Komunikacja miejska daje najlepszy kompromis")
    assert rec.explanation.startswith("Samochód daje najlepszy kompromis")


def test_balanced_two_options_scores_reflect_the_size_of_differences() -> None:
    # Min-max always gave exactly 1/3 and 2/3 for two options, whatever the differences.
    options = [estimate(CAR, 15.0, 4.42, 0.51), estimate(PT, 150.0, 4.40, 0.15)]

    rec = recommender.recommend(options, TripPriority.BALANCED)
    car, pt = rec.score_for(CAR), rec.score_for(PT)

    assert car.balanced_score == pytest.approx((15 / 150 + 1 + 1) / 3, abs=1e-4)
    assert pt.balanced_score == pytest.approx((1 + 4.40 / 4.42 + 0.15 / 0.51) / 3, abs=1e-4)
    assert {car.balanced_score, pt.balanced_score}.isdisjoint({0.3333, 0.6667})


@pytest.mark.parametrize("pt_duration", [None, 40.0, 60.0, 90.0])
def test_balanced_car_vs_public_transport_order_survives_removing_bike(
    pt_duration: float | None,
) -> None:
    """Scenario from the code review: 9.7 km, 1 passenger, real calculators.

    With min-max, removing the bike swapped car and public transport. ``pt_duration`` stands
    for a GTFS time that includes waiting for the departure (None = parametric estimate).
    """
    service = ComparisonService.from_settings(TransportSettings())
    estimates = service.compare(TripInput(distance_km=9.7), TripPriority.BALANCED).estimates
    if pt_duration is not None:
        estimates = tuple(
            replace(e, duration_min=pt_duration, data_source=DataSource.GTFS_SCHEDULE)
            if e.mode is PT
            else e
            for e in estimates
        )

    with_bike = recommender.recommend(estimates, TripPriority.BALANCED)
    without_bike = recommender.recommend(
        [e for e in estimates if e.mode is not BIKE], TripPriority.BALANCED
    )

    order_with_bike = [s.mode for s in with_bike.scores if s.mode is not BIKE]
    assert order_with_bike == [s.mode for s in without_bike.scores]


def test_balanced_handles_metric_that_is_zero_for_every_option() -> None:
    options = [estimate(BIKE, 30.0, 0.0, 0.0), estimate(PT, 25.0, 0.0, 0.0)]

    rec = recommender.recommend(options, TripPriority.BALANCED)

    assert rec.mode is PT
    assert all(s.normalized_cost == 0 and s.normalized_co2 == 0 for s in rec.scores)
    assert rec.score_for(BIKE).normalized_duration == 1
    assert rec.score_for(PT).normalized_duration == pytest.approx(25 / 30, abs=1e-4)


def test_fastest_picks_strictly_fastest_even_if_runner_up_is_much_cheaper() -> None:
    # Weighting could pick the bike here; the lexicographic "fastest" cannot.
    rec = recommender.recommend(
        [estimate(CAR, 20.0, 30, 5), estimate(BIKE, 20.5, 0, 0)], TripPriority.FASTEST
    )
    assert rec.mode is CAR


def test_unavailable_modes_are_never_recommended() -> None:
    variants = [
        estimate(CAR, 10, 1, 1, available=False),
        estimate(PT, 50, 9, 2),
        estimate(BIKE, 5, 0, 0, available=False),
    ]
    for priority in TripPriority:
        rec = recommender.recommend(variants, priority)
        assert rec.mode is PT
        assert [s.mode for s in rec.scores] == [PT]
        assert rec.score_for(CAR) is None


def test_single_available_mode_gets_zero_scores() -> None:
    rec = recommender.recommend([estimate(PT, 30, 4, 1)], TripPriority.BALANCED)

    score = rec.scores[0]
    assert (score.normalized_duration, score.normalized_cost, score.normalized_co2) == (0, 0, 0)
    assert score.balanced_score == 0
    assert "jedyny dostępny" in rec.explanation
    assert rec.tie_break_applied is False


def test_no_available_modes_returns_no_recommendation() -> None:
    rec = recommender.recommend(
        [estimate(CAR, 1, 1, 1, available=False), estimate(BIKE, 1, 0, 0, available=False)],
        TripPriority.FASTEST,
    )

    assert rec.mode is None
    assert rec.scores == ()
    assert "Żaden wariant" in rec.explanation
    assert "niedostępny" in rec.explanation


@pytest.mark.parametrize("priority", list(TripPriority))
def test_full_tie_is_resolved_by_fixed_order(priority: TripPriority) -> None:
    same = [estimate(CAR, 30, 5, 1), estimate(PT, 30, 5, 1), estimate(BIKE, 30, 5, 1)]

    rec = recommender.recommend(same, priority)

    assert rec.mode is BIKE
    assert [s.mode for s in rec.scores] == [BIKE, PT, CAR]
    assert rec.tie_break_applied is True
    assert "remis" in rec.explanation


def test_tie_between_car_and_public_transport_prefers_public_transport() -> None:
    rec = recommender.recommend(
        [estimate(CAR, 30, 5, 1), estimate(PT, 30, 5, 1)], TripPriority.BALANCED
    )
    assert rec.mode is PT


def test_primary_tie_is_resolved_by_secondary_metric_before_fixed_order() -> None:
    # Same time — with "fastest" the lower cost decides, not the fixed order.
    rec = recommender.recommend(
        [estimate(CAR, 30, 3, 2), estimate(BIKE, 30, 4, 0)], TripPriority.FASTEST
    )
    assert rec.mode is CAR
    assert rec.tie_break_applied is False


def test_result_does_not_depend_on_input_order() -> None:
    for priority in TripPriority:
        forward = recommender.recommend(CITY, priority)
        backward = recommender.recommend(list(reversed(CITY)), priority)
        assert forward == backward


def test_explanation_compares_winner_with_other_modes() -> None:
    rec = recommender.recommend(CITY[:2], TripPriority.CHEAPEST)

    assert rec.mode is PT
    assert rec.explanation.startswith(
        "Komunikacja miejska to najtańszy dostępny wariant: ok. 4,40 zł"
    )
    assert "Względem wariantu „Samochód”: 15 min dłużej, 0,15 zł taniej, 1,20 kg CO₂ mniej." in (
        rec.explanation
    )
    assert rec.explanation.endswith("Wszystkie wartości są szacunkowe.")


@pytest.mark.parametrize(
    ("priority", "fragment"),
    [
        (TripPriority.FASTEST, "najszybszy"),
        (TripPriority.GREENEST, "najniższą szacowaną emisję"),
        (TripPriority.BALANCED, "najlepszy kompromis"),
    ],
)
def test_explanation_headline_matches_priority(priority: TripPriority, fragment: str) -> None:
    assert fragment in recommender.recommend(CITY, priority).explanation


def test_explanation_mentions_unavailable_modes_and_similar_values() -> None:
    rec = recommender.recommend(
        [
            estimate(CAR, 30.2, 5, 1),
            estimate(PT, 30.0, 5, 1.001),
            estimate(BIKE, 1, 0, 0, available=False),
        ],
        TripPriority.FASTEST,
    )

    assert rec.mode is PT
    assert "podobny czas, ten sam koszt, 0,001 kg CO₂ więcej" in rec.explanation
    assert "Pominięto niedostępne: Rower — niedostępny. Wszystkie" in rec.explanation


def test_describe_method_documents_each_priority() -> None:
    assert "dzielona przez największą wartość" in describe_method(TripPriority.BALANCED)
    assert "min-max" not in describe_method(TripPriority.BALANCED)
    assert "czas → koszt → emisja CO₂" in describe_method(TripPriority.FASTEST)
    assert "koszt → czas" in describe_method(TripPriority.CHEAPEST)
    assert describe_method(TripPriority.GREENEST).startswith("Porządek leksykograficzny")


# --- ComparisonService ----------------------------------------------------------------------


def test_default_scenario_matches_city_fixture() -> None:
    """Tie the CITY fixture values to the real calculators and the default settings."""
    service = ComparisonService.from_settings(TransportSettings())

    result = service.compare(TripInput(distance_km=10), TripPriority.BALANCED)

    by_mode = {e.mode: e for e in result.estimates}
    for expected in CITY:
        actual = by_mode[expected.mode]
        assert (actual.duration_min, actual.cost_pln, actual.co2_kg) == pytest.approx(
            (expected.duration_min, expected.cost_pln, expected.co2_kg)
        )
    assert [e.mode for e in result.estimates] == [CAR, PT, BIKE]
    assert result.recommendation.mode is BIKE


def test_service_excludes_car_without_car_and_bike_on_long_trip() -> None:
    service = ComparisonService.from_settings(TransportSettings())

    result = service.compare(TripInput(distance_km=50, has_car=False), TripPriority.FASTEST)

    assert result.recommendation.mode is PT
    assert {e.mode for e in result.estimates if not e.available} == {CAR, BIKE}


def test_service_handles_large_groups_without_errors() -> None:
    service = ComparisonService.from_settings(TransportSettings())

    result = service.compare(TripInput(distance_km=1000, passengers=8), TripPriority.CHEAPEST)

    # 8 tickets for 1000 km cost more than one car.
    assert result.recommendation.mode is CAR


def test_service_rejects_duplicate_calculators() -> None:
    params = TransportSettings().car
    with pytest.raises(ValueError, match="jeden kalkulator"):
        ComparisonService([CarCalculator(params), CarCalculator(params)])


def test_primary_tie_is_explained_in_recommendation() -> None:
    # Time tie with "fastest": the winner is chosen by cost, and the explanation says so.
    rec = recommender.recommend(
        [estimate(CAR, 30, 3, 2), estimate(BIKE, 30, 4, 0)], TripPriority.FASTEST
    )
    assert "Taką samą wartość kryterium „czas” ma wariant „Rower”" in rec.explanation
    assert "rozstrzygnęło kolejne kryterium: koszt" in rec.explanation


def test_no_tie_sentence_without_primary_tie() -> None:
    rec = recommender.recommend(CITY, TripPriority.FASTEST)
    assert "Taką samą wartość" not in rec.explanation


@pytest.mark.parametrize(
    ("priority", "metric"),
    [
        (TripPriority.FASTEST, "duration_min"),
        (TripPriority.CHEAPEST, "cost_pln"),
        (TripPriority.GREENEST, "co2_kg"),
    ],
)
def test_single_metric_priority_winner_has_minimum_value(
    priority: TripPriority, metric: str
) -> None:
    for pool in (CITY, CITY[:2], CITY[1:], [CITY[0], CITY[2]]):
        rec = recommender.recommend(pool, priority)
        winner = next(e for e in pool if e.mode is rec.mode)
        assert getattr(winner, metric) == min(getattr(e, metric) for e in pool)
