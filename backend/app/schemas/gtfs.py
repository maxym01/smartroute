"""API contract for GTFS timetable stops and connections."""

from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import DataSource
from app.models.gtfs import GtfsFeed
from app.services.gtfs.schedule_service import Connection, ConnectionSearch
from app.services.gtfs.time_utils import int_to_date


class StopRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stop_id: str = Field(description="Identyfikator do origin_stop_id / destination_stop_id")
    stop_name: str
    stop_code: str | None
    stop_lat: float | None
    stop_lon: float | None


class StopList(BaseModel):
    items: list[StopRead]
    count: int


class FeedRead(BaseModel):
    source: str
    imported_at: datetime
    timezone: str
    valid_from: date | None
    valid_to: date | None

    @classmethod
    def from_model(cls, feed: GtfsFeed) -> "FeedRead":
        return cls(
            source=feed.source,
            imported_at=feed.imported_at.replace(tzinfo=UTC),
            timezone=feed.timezone,
            valid_from=int_to_date(feed.valid_from) if feed.valid_from else None,
            valid_to=int_to_date(feed.valid_to) if feed.valid_to else None,
        )


class ConnectionRead(BaseModel):
    trip_id: str
    route_id: str
    line: str = Field(description="Numer linii (route_short_name)")
    route_type: int = Field(description="Typ GTFS, np. 3/700 autobus, 0/900 tramwaj")
    headsign: str | None = Field(description="Kierunek kursu")
    direction_id: int | None
    service_date: date = Field(
        description="Dzień kursowania wg rozkładu (dla kursów po północy — dzień wcześniej)"
    )
    departure_at: datetime
    arrival_at: datetime
    duration_min: float = Field(description="Czas przejazdu z rozkładu [min]")
    origin_stop_sequence: int
    destination_stop_sequence: int

    @classmethod
    def from_domain(cls, connection: Connection) -> "ConnectionRead":
        return cls(
            trip_id=connection.trip_id,
            route_id=connection.route_id,
            line=connection.line,
            route_type=connection.route_type,
            headsign=connection.headsign,
            direction_id=connection.direction_id,
            service_date=connection.service_date,
            departure_at=connection.departure_at,
            arrival_at=connection.arrival_at,
            duration_min=round(connection.duration_min, 1),
            origin_stop_sequence=connection.origin_stop_sequence,
            destination_stop_sequence=connection.destination_stop_sequence,
        )


class ConnectionList(BaseModel):
    origin: StopRead
    destination: StopRead
    departure_at: datetime = Field(description="Szukamy odjazdów od tej chwili (czas lokalny)")
    window_min: int
    data_source: Literal[DataSource.GTFS_SCHEDULE] = DataSource.GTFS_SCHEDULE
    is_realtime: Literal[False] = False
    feed: FeedRead
    connections: list[ConnectionRead]
    notes: list[str]

    @classmethod
    def from_search(cls, search: ConnectionSearch) -> "ConnectionList":
        return cls(
            origin=StopRead.model_validate(search.origin),
            destination=StopRead.model_validate(search.destination),
            departure_at=search.departure_at,
            window_min=search.window_min,
            feed=FeedRead.from_model(search.feed),
            connections=[ConnectionRead.from_domain(c) for c in search.connections],
            notes=list(search.notes),
        )
