"""Deterministic adjustment of the "Bike" option based on current weather.

Rules (the thresholds are MVP assumptions, not a standard):

- precipitation [mm/h]: ≥ 0.2 → reduced comfort (``reduced``), ≥ 2.5 → low (``poor``),
- thunderstorm, snow, freezing rain (Weatherbit codes 2xx, 511, 6xx) or snowfall > 0 → ``poor``,
- wind [km/h]: ≥ 25 → ``reduced``, ≥ 40 (about 6 on the Beaufort scale) → ``poor``,
- temperature [°C]: ≤ 3 or ≥ 28 → ``reduced``, ≤ -5 or ≥ 33 → ``poor``.

The resulting comfort is the worst factor. Wind also lengthens the estimated bike travel
time: +10% from 25 km/h, +20% from 40 km/h (moderate, since the riding direction relative
to the wind is unknown). The other metrics (cost, CO₂) and the other transport modes are
not changed: traffic jams and public transport delays are not simulated.
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
    reasons: tuple[str, ...]  # empty in good weather


def _worse(a: ComfortLevel, b: ComfortLevel) -> ComfortLevel:
    return max(a, b, key=_ORDER.index)


def _is_severe_code(code: int | None) -> bool:
    # 2xx thunderstorm, 511 freezing rain, 6xx snow / sleet (Weatherbit codes).
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
        """Return the adjusted bike estimate; other modes and an unavailable bike are unchanged."""
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
