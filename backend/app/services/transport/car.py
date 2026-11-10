from app.core.enums import DataSource, TransportMode
from app.core.transport_params import CarParams
from app.services.transport.base import (
    CO2_DECIMALS,
    COST_DECIMALS,
    DURATION_DECIMALS,
    ModeEstimate,
    TripInput,
    fmt_number,
    per_passenger,
    travel_time_min,
)


class CarCalculator:
    """Samochód: czas = dystans / prędkość + parkowanie; koszt = tylko paliwo dla całego auta.

    Koszt i emisja dotyczą pojazdu, więc nie rosną z liczbą osób — wartości „na pasażera”
    to równy podział między wszystkich jadących.
    """

    mode = TransportMode.CAR

    def __init__(self, params: CarParams) -> None:
        self.params = params

    def estimate(self, trip: TripInput) -> ModeEstimate:
        p = self.params
        duration = travel_time_min(trip.distance_km, p.avg_speed_kmh) + p.parking_time_min
        fuel_l = trip.distance_km * p.fuel_consumption_l_per_100km / 100
        cost = fuel_l * p.fuel_price_pln_per_l
        co2 = trip.distance_km * p.co2_kg_per_km
        reason = None if trip.has_car else "Brak dostępnego samochodu (has_car=false)."

        return ModeEstimate(
            mode=self.mode,
            available=trip.has_car,
            unavailable_reason=reason,
            duration_min=round(duration, DURATION_DECIMALS),
            cost_pln=round(cost, COST_DECIMALS),
            cost_per_passenger_pln=round(per_passenger(cost, trip.passengers), COST_DECIMALS),
            co2_kg=round(co2, CO2_DECIMALS),
            co2_per_passenger_kg=round(per_passenger(co2, trip.passengers), CO2_DECIMALS),
            data_source=DataSource.PARAMETRIC_ESTIMATE,
            assumptions=(
                f"Średnia prędkość {fmt_number(p.avg_speed_kmh, 0)} km/h, bez danych o bieżącym "
                "natężeniu ruchu.",
                f"Doliczono {fmt_number(p.parking_time_min, 0)} min na parkowanie.",
                f"Spalanie {fmt_number(p.fuel_consumption_l_per_100km, 1)} l/100 km i cena paliwa "
                f"{fmt_number(p.fuel_price_pln_per_l)} zł/l to wartości przyjęte, nie bieżące.",
                "Koszt obejmuje wyłącznie paliwo (bez parkingu, opłat, amortyzacji "
                "i ubezpieczenia).",
                f"Emisja {fmt_number(p.co2_kg_per_km)} kg CO₂/km dotyczy całego pojazdu; "
                f"wartości na osobę to podział na {trip.passengers} os.",
                "Zakładamy, że wszyscy pasażerowie jadą jednym samochodem.",
            ),
        )
