"""Parametry modelu szacowania czasu, kosztu i emisji CO₂.

UWAGA: to są **przyjęte założenia modelowe** o charakterze poglądowym, dobrane jako rozsądne
rzędy wielkości dla jazdy miejskiej w Polsce. Nie są to bieżące pomiary, aktualne ceny paliwa
ani oficjalne taryfy żadnego przewoźnika. Każdą wartość można nadpisać zmienną środowiskową,
np. ``TRANSPORT__CAR__FUEL_PRICE_PLN_PER_L=6.89``.

Wartości dodatnie w mianownikach (prędkości) są wymuszone walidacją ``gt=0``,
więc obliczenia nie mogą dzielić przez zero.
"""

from pydantic import BaseModel, ConfigDict, Field


class _Params(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CarParams(_Params):
    avg_speed_kmh: float = Field(
        40.0, gt=0, description="Średnia prędkość przejazdu [km/h], uśredniona dla ruchu miejskiego"
    )
    parking_time_min: float = Field(
        5.0, ge=0, description="Stały narzut na szukanie miejsca i parkowanie [min]"
    )
    fuel_consumption_l_per_100km: float = Field(
        7.0, ge=0, description="Średnie spalanie [l/100 km] — przyjęte, nie zmierzone"
    )
    fuel_price_pln_per_l: float = Field(
        6.50, ge=0, description="Cena paliwa [PLN/l] — wartość przykładowa, nie bieżąca cena"
    )
    co2_kg_per_km: float = Field(
        0.17, ge=0, description="Emisja CO₂ całego pojazdu [kg/km] (niezależna od liczby osób)"
    )


class PublicTransportParams(_Params):
    avg_speed_kmh: float = Field(
        22.0, gt=0, description="Średnia prędkość komunikacji z przystankami [km/h]"
    )
    access_wait_time_min: float = Field(
        8.0, ge=0, description="Dojście do przystanku i średnie oczekiwanie na pojazd [min]"
    )
    base_ticket_pln: float = Field(
        4.40, ge=0, description="Cena biletu jednorazowego na osobę [PLN] — przykładowa"
    )
    base_ticket_max_km: float = Field(
        10.0, gt=0, description="Dystans pokryty biletem podstawowym [km]"
    )
    extra_pln_per_km: float = Field(
        0.25, ge=0, description="Dopłata na osobę za każdy km ponad bilet podstawowy [PLN/km]"
    )
    co2_kg_per_passenger_km: float = Field(
        0.05, ge=0, description="Emisja CO₂ na pasażerokilometr [kg/pkm], średnia dla floty"
    )


class BikeParams(_Params):
    avg_speed_kmh: float = Field(15.0, gt=0, description="Średnia prędkość rowerzysty [km/h]")
    max_distance_km: float = Field(
        20.0, gt=0, description="Maksymalny dystans uznawany za realny dla roweru [km]"
    )


class TransportSettings(_Params):
    car: CarParams = Field(default_factory=CarParams)
    public_transport: PublicTransportParams = Field(default_factory=PublicTransportParams)
    bike: BikeParams = Field(default_factory=BikeParams)
