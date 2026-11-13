"""GTFS Static timetable tables in a separate SQLite database (``GTFS_DATABASE_URL``).

They have their own ``GtfsBase``, so the trips database's ``create_all`` does not create
them. Only the importer creates and fills them (``python -m app.cli.gtfs import``).

Simplifications compared with the GTFS specification:
- the calendar is materialized into (service_id, date) pairs from calendar.txt and
  calendar_dates.txt,
- times are stored as seconds from "noon minus 12 h" of the service day (may be >= 24 h),
- a trip has a technical integer key ``trip_pk`` (saves space in stop_times).
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class GtfsBase(DeclarativeBase):
    """Base class for timetable models (metadata separate from the application models)."""


class GtfsFeed(GtfsBase):
    """Metadata of the last successful import (always a single row, id=1)."""

    __tablename__ = "gtfs_feed"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(1000))
    sha256: Mapped[str] = mapped_column(String(64))
    imported_at: Mapped[datetime] = mapped_column(DateTime)  # UTC, naive
    timezone: Mapped[str] = mapped_column(String(64))
    valid_from: Mapped[int | None] = mapped_column(Integer)  # YYYYMMDD
    valid_to: Mapped[int | None] = mapped_column(Integer)  # YYYYMMDD
    max_time_secs: Mapped[int] = mapped_column(Integer)
    stops_count: Mapped[int] = mapped_column(Integer)
    routes_count: Mapped[int] = mapped_column(Integer)
    trips_count: Mapped[int] = mapped_column(Integer)
    stop_times_count: Mapped[int] = mapped_column(Integer)
    service_dates_count: Mapped[int] = mapped_column(Integer)
    skipped_rows: Mapped[int] = mapped_column(Integer)


class GtfsStop(GtfsBase):
    __tablename__ = "gtfs_stops"

    stop_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    stop_name: Mapped[str] = mapped_column(String(200))
    stop_code: Mapped[str | None] = mapped_column(String(64))
    stop_lat: Mapped[float | None] = mapped_column(Float)
    stop_lon: Mapped[float | None] = mapped_column(Float)
    # Name folded to lowercase without Polish diacritics, for search ("Główny" ~ "glowny").
    search_name: Mapped[str] = mapped_column(String(200))


class GtfsRoute(GtfsBase):
    __tablename__ = "gtfs_routes"

    route_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    short_name: Mapped[str | None] = mapped_column(String(64))
    long_name: Mapped[str | None] = mapped_column(String(300))
    route_type: Mapped[int] = mapped_column(Integer)


class GtfsTrip(GtfsBase):
    __tablename__ = "gtfs_trips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trip_id: Mapped[str] = mapped_column(String(128), unique=True)
    route_id: Mapped[str] = mapped_column(ForeignKey("gtfs_routes.route_id"))
    service_id: Mapped[str] = mapped_column(String(64))
    headsign: Mapped[str | None] = mapped_column(String(200))
    direction_id: Mapped[int | None] = mapped_column(Integer)


class GtfsServiceDate(GtfsBase):
    """A day on which a given service (service_id) runs."""

    __tablename__ = "gtfs_service_dates"
    __table_args__ = {"sqlite_with_rowid": False}

    service_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    date: Mapped[int] = mapped_column(Integer, primary_key=True)  # YYYYMMDD


class GtfsStopTime(GtfsBase):
    __tablename__ = "gtfs_stop_times"
    __table_args__ = (
        # Looking up departures from a stop within a time window.
        Index("ix_gtfs_stop_times_stop_departure", "stop_id", "departure_secs"),
        {"sqlite_with_rowid": False},
    )

    trip_pk: Mapped[int] = mapped_column(ForeignKey("gtfs_trips.id"), primary_key=True)
    stop_sequence: Mapped[int] = mapped_column(Integer, primary_key=True)
    stop_id: Mapped[str] = mapped_column(ForeignKey("gtfs_stops.stop_id"))
    arrival_secs: Mapped[int] = mapped_column(Integer)
    departure_secs: Mapped[int] = mapped_column(Integer)
    pickup_type: Mapped[int] = mapped_column(Integer, default=0)
    drop_off_type: Mapped[int] = mapped_column(Integer, default=0)
