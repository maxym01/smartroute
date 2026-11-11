"""Wyszukiwanie bezpośrednich połączeń w rozkładzie GTFS (bez przesiadek, bez realtime)."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.exceptions import GtfsNotImportedError, UnknownStopError
from app.core.timezone import as_local_aware
from app.models.gtfs import GtfsFeed, GtfsStop
from app.repositories.gtfs_repository import GtfsRepository, ScheduledRide
from app.services.gtfs.time_utils import (
    date_to_int,
    gtfs_time_to_datetime,
    int_to_date,
    service_day_reference,
)

__all__ = [
    "Connection",
    "ConnectionSearch",
    "GtfsNotImportedError",
    "ScheduleService",
    "UnknownStopError",
]


@dataclass(frozen=True, slots=True)
class Connection:
    trip_id: str
    route_id: str
    route_short_name: str | None
    route_long_name: str | None
    route_type: int
    headsign: str | None
    direction_id: int | None
    service_date: date
    departure_at: datetime
    arrival_at: datetime
    origin_stop_sequence: int
    destination_stop_sequence: int

    @property
    def duration_min(self) -> float:
        return (self.arrival_at - self.departure_at).total_seconds() / 60

    @property
    def line(self) -> str:
        return self.route_short_name or self.route_long_name or self.route_id


@dataclass(frozen=True, slots=True)
class ConnectionSearch:
    feed: GtfsFeed
    origin: GtfsStop
    destination: GtfsStop
    departure_at: datetime  # w strefie feedu
    window_min: int
    connections: tuple[Connection, ...]
    notes: tuple[str, ...]


class ScheduleService:
    def __init__(self, repository: GtfsRepository) -> None:
        self.repository = repository

    def require_feed(self) -> GtfsFeed:
        feed = self.repository.feed()
        if feed is None:
            raise GtfsNotImportedError()
        return feed

    def get_stop(self, stop_id: str) -> GtfsStop:
        stop = self.repository.get_stop(stop_id)
        if stop is None:
            raise UnknownStopError(stop_id)
        return stop

    def find_direct_connections(
        self,
        origin_stop_id: str,
        destination_stop_id: str,
        departure_at: datetime,
        *,
        window_min: int = 120,
        limit: int = 5,
    ) -> ConnectionSearch:
        feed = self.require_feed()
        origin = self.get_stop(origin_stop_id)
        destination = self.get_stop(destination_stop_id)
        tz = ZoneInfo(feed.timezone)
        start = as_local_aware(departure_at).astimezone(tz)
        end = start + timedelta(minutes=window_min)

        # Kurs z dnia D może odjeżdżać po północy (czas >= 24:00), więc sprawdzamy też
        # odpowiednią liczbę dni wstecz (np. ZTM Gdańsk: do ~29:30 → 1 dzień). Margines ±1 dnia
        # pokrywa dni zmiany czasu, gdy „południe minus 12 h” nie wypada o północy.
        days_back = feed.max_time_secs // 86400
        day = start.date() - timedelta(days=days_back + 1)
        last_day = end.date() + timedelta(days=1)
        candidates: list[Connection] = []
        while day <= last_day:
            candidates.extend(
                self._rides_for_day(day, tz, origin.stop_id, destination.stop_id, start, end, limit)
            )
            day += timedelta(days=1)

        connections = _dedupe_by_trip(sorted(candidates, key=_sort_key))[:limit]
        return ConnectionSearch(
            feed=feed,
            origin=origin,
            destination=destination,
            departure_at=start,
            window_min=window_min,
            connections=tuple(connections),
            notes=self._notes(feed, start, end, connections),
        )

    def _rides_for_day(
        self,
        day: date,
        tz: ZoneInfo,
        origin_id: str,
        destination_id: str,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> list[Connection]:
        reference = service_day_reference(day, tz)
        low = int((start.astimezone(UTC) - reference).total_seconds())
        high = int((end.astimezone(UTC) - reference).total_seconds())
        if high < 0:
            return []
        rides = self.repository.direct_rides(
            origin_stop_id=origin_id,
            destination_stop_id=destination_id,
            service_date=date_to_int(day),
            min_departure_secs=max(low, 0),
            max_departure_secs=high,
            limit=limit * 2,  # zapas na duplikaty z pętli
        )
        return [_to_connection(ride, day, tz) for ride in rides]

    @staticmethod
    def _notes(
        feed: GtfsFeed, start: datetime, end: datetime, connections: list[Connection]
    ) -> tuple[str, ...]:
        notes = [
            "Rozkład planowy GTFS Static — bez opóźnień i danych w czasie rzeczywistym.",
            "Tylko połączenia bezpośrednie (bez przesiadek).",
        ]
        if feed.valid_from and feed.valid_to:
            valid_from, valid_to = int_to_date(feed.valid_from), int_to_date(feed.valid_to)
            if end.date() < valid_from or start.date() > valid_to:
                notes.append(
                    f"Wybrana data jest poza okresem ważności rozkładu "
                    f"({valid_from:%d.%m.%Y}–{valid_to:%d.%m.%Y})."
                )
        if not connections:
            notes.append("Brak bezpośredniego połączenia w podanym oknie czasowym.")
        return tuple(notes)


def _to_connection(ride: ScheduledRide, day: date, tz: ZoneInfo) -> Connection:
    return Connection(
        trip_id=ride.trip_id,
        route_id=ride.route_id,
        route_short_name=ride.route_short_name,
        route_long_name=ride.route_long_name,
        route_type=ride.route_type,
        headsign=ride.headsign,
        direction_id=ride.direction_id,
        service_date=day,
        departure_at=gtfs_time_to_datetime(day, ride.departure_secs, tz),
        arrival_at=gtfs_time_to_datetime(day, ride.arrival_secs, tz),
        origin_stop_sequence=ride.origin_sequence,
        destination_stop_sequence=ride.destination_sequence,
    )


def _sort_key(connection: Connection) -> tuple[datetime, datetime, str]:
    return connection.departure_at, connection.arrival_at, connection.trip_id


def _dedupe_by_trip(connections: list[Connection]) -> list[Connection]:
    seen: set[tuple[str, date]] = set()
    unique = []
    for connection in connections:
        key = (connection.trip_id, connection.service_date)
        if key not in seen:
            seen.add(key)
            unique.append(connection)
    return unique
