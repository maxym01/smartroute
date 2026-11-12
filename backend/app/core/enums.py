"""Enumy domenowe współdzielone przez modele, schematy i serwisy (bez zależności od ORM/API)."""

from enum import StrEnum


class TripPriority(StrEnum):
    FASTEST = "fastest"
    CHEAPEST = "cheapest"
    GREENEST = "greenest"
    BALANCED = "balanced"


class TransportMode(StrEnum):
    CAR = "car"
    PUBLIC_TRANSPORT = "public_transport"
    BIKE = "bike"


class DataSource(StrEnum):
    """Skąd pochodzi szacunek czasu przejazdu danego wariantu."""

    # Prosty model parametryczny: dystans / średnia prędkość + stałe narzuty z konfiguracji.
    PARAMETRIC_ESTIMATE = "parametric_estimate"
    # Zarezerwowane dla kolejnego etapu: czas wyznaczony z rozkładu GTFS.
    GTFS_SCHEDULE = "gtfs_schedule"


class ComfortLevel(StrEnum):
    """Komfort podróży danym środkiem przy bieżącej pogodzie (obecnie oceniany tylko rower)."""

    GOOD = "good"
    REDUCED = "reduced"
    POOR = "poor"


class WeatherStatus(StrEnum):
    """Wynik próby użycia bieżącej pogody w porównaniu."""

    APPLIED = "applied"  # pobrano pogodę i oceniono rower
    DISABLED = "disabled"  # brak WEATHERBIT_API_KEY — integracja wyłączona
    NO_LOCATION = "no_location"  # brak wiarygodnych współrzędnych (przystanku GTFS)
    OUT_OF_TIME_WINDOW = "out_of_time_window"  # podróż nie odbywa się teraz / wkrótce
    UNAVAILABLE = "unavailable"  # błąd API, limit, timeout, brak internetu
    NOT_APPLICABLE = "not_applicable"  # rower niedostępny — korekta nie miałaby czego dotyczyć
