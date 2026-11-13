"""Domain enums shared by models, schemas and services (no ORM/API dependencies)."""

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

    # Simple parametric model: distance / average speed + fixed overheads from the settings.
    PARAMETRIC_ESTIMATE = "parametric_estimate"
    # Scheduled time from the GTFS timetable.
    GTFS_SCHEDULE = "gtfs_schedule"


class ComfortLevel(StrEnum):
    """Komfort podróży danym środkiem przy bieżącej pogodzie (obecnie oceniany tylko rower)."""

    GOOD = "good"
    REDUCED = "reduced"
    POOR = "poor"


class WeatherStatus(StrEnum):
    """Wynik próby użycia bieżącej pogody w porównaniu."""

    APPLIED = "applied"  # weather fetched and the bike assessed
    DISABLED = "disabled"  # no WEATHERBIT_API_KEY — integration disabled
    NO_LOCATION = "no_location"  # no reliable coordinates (GTFS stop)
    OUT_OF_TIME_WINDOW = "out_of_time_window"  # the trip is not happening now / soon
    UNAVAILABLE = "unavailable"  # API error, rate limit, timeout, no internet
    NOT_APPLICABLE = "not_applicable"  # bike unavailable — there is nothing to adjust
