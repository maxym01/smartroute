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
