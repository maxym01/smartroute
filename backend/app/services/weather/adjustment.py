"""Deterministyczna korekta wariantu „Rower” na podstawie bieżącej pogody.

Reguły (progi są przyjętymi założeniami MVP, nie normą):

- opad [mm/h]: ≥ 0,2 → komfort obniżony (``reduced``), ≥ 2,5 → niski (``poor``),
- burza, śnieg, marznący deszcz (kody Weatherbit 2xx, 511, 6xx) lub opad śniegu > 0 → ``poor``,
- wiatr [km/h]: ≥ 25 → ``reduced``, ≥ 40 (ok. 6° Beauforta) → ``poor``,
- temperatura [°C]: ≤ 3 lub ≥ 28 → ``reduced``, ≤ -5 lub ≥ 33 → ``poor``.

Wynikowy komfort to najgorszy z czynników. Wiatr dodatkowo wydłuża szacowany czas jazdy
rowerem: +10% od 25 km/h, +20% od 40 km/h (umiarkowanie — nie znamy kierunku jazdy względem
wiatru). Pozostałe metryki (koszt, CO₂) ani inne środki transportu nie są zmieniane: nie
symulujemy korków ani opóźnień komunikacji.
"""

from dataclasses import dataclass, replace

from app.core.enums import ComfortLevel, TransportMode
from app.services.transport.base import DURATION_DECIMALS, ModeEstimate, fmt_number
from app.services.weather.client import WeatherObservation

RAIN_REDUCED_MM_H = 0.2
RAIN_POOR_MM_H = 2.5
WIND_REDUCED_KMH = 25.0
WIND_POOR_KMH = 40.0
COLD_REDUCED_C = 3.0
COLD_POOR_C = -5.0
HOT_REDUCED_C = 28.0
HOT_POOR_C = 33.0
WIND_DURATION_FACTOR = {ComfortLevel.REDUCED: 1.1, ComfortLevel.POOR: 1.2}

_ORDER = (ComfortLevel.GOOD, ComfortLevel.REDUCED, ComfortLevel.POOR)
COMFORT_LABELS = {
    ComfortLevel.GOOD: "dobry",
    ComfortLevel.REDUCED: "obniżony",
    ComfortLevel.POOR: "niski",
}


@dataclass(frozen=True, slots=True)
class BikeWeatherAdjustment:
    comfort_level: ComfortLevel
    duration_factor: float
    reasons: tuple[str, ...]  # puste przy dobrej pogodzie


def _worse(a: ComfortLevel, b: ComfortLevel) -> ComfortLevel:
    return max(a, b, key=_ORDER.index)


def _is_severe_code(code: int | None) -> bool:
    # 2xx burza, 511 marznący deszcz, 6xx śnieg / deszcz ze śniegiem (kody Weatherbit).
    return code is not None and (200 <= code < 300 or code == 511 or 600 <= code < 700)


class WeatherAdjustmentService:
    def assess_bike(self, weather: WeatherObservation) -> BikeWeatherAdjustment:
        level = ComfortLevel.GOOD
        reasons: list[str] = []

        if _is_severe_code(weather.weather_code) or weather.snowfall_mm_h > 0:
            level = ComfortLevel.POOR
            reasons.append(
                f"niebezpieczne warunki ({weather.description or 'burza, śnieg lub gołoledź'})"
            )

        rain = weather.precipitation_mm_h
        if rain >= RAIN_POOR_MM_H:
            level = _worse(level, ComfortLevel.POOR)
            reasons.append(f"intensywny opad {fmt_number(rain, 1)} mm/h")
        elif rain >= RAIN_REDUCED_MM_H:
            level = _worse(level, ComfortLevel.REDUCED)
            reasons.append(f"opad {fmt_number(rain, 1)} mm/h")

        wind = weather.wind_speed_kmh
        wind_level = ComfortLevel.GOOD
        if wind >= WIND_POOR_KMH:
            wind_level = ComfortLevel.POOR
            reasons.append(f"silny wiatr {fmt_number(wind, 0)} km/h")
        elif wind >= WIND_REDUCED_KMH:
            wind_level = ComfortLevel.REDUCED
            reasons.append(f"wiatr {fmt_number(wind, 0)} km/h")
        level = _worse(level, wind_level)

        temp = weather.temperature_c
        if temp <= COLD_POOR_C or temp >= HOT_POOR_C:
            level = _worse(level, ComfortLevel.POOR)
            reasons.append(f"skrajna temperatura {fmt_number(temp, 0)} °C")
        elif temp <= COLD_REDUCED_C or temp >= HOT_REDUCED_C:
            level = _worse(level, ComfortLevel.REDUCED)
            reasons.append(f"temperatura {fmt_number(temp, 0)} °C")

        return BikeWeatherAdjustment(
            comfort_level=level,
            duration_factor=WIND_DURATION_FACTOR.get(wind_level, 1.0),
            reasons=tuple(reasons),
        )

    @staticmethod
    def apply(estimate: ModeEstimate, adjustment: BikeWeatherAdjustment) -> ModeEstimate:
        """Zwraca skorygowany szacunek roweru; inne środki i rower niedostępny — bez zmian."""
        if estimate.mode is not TransportMode.BIKE or not estimate.available:
            return estimate
        label = COMFORT_LABELS[adjustment.comfort_level]
        notes = [
            f"Komfort przy bieżącej pogodzie: {label}"
            + (f" ({', '.join(adjustment.reasons)})." if adjustment.reasons else ".")
        ]
        duration = estimate.duration_min
        if adjustment.duration_factor != 1.0:
            duration = round(duration * adjustment.duration_factor, DURATION_DECIMALS)
            percent = round((adjustment.duration_factor - 1) * 100)
            notes.append(f"Czas jazdy wydłużony o {percent}% z powodu wiatru (pogoda bieżąca).")
        return replace(
            estimate,
            duration_min=duration,
            comfort_level=adjustment.comfort_level,
            assumptions=(*estimate.assumptions, *notes),
        )
