"""Tabele rozkładu GTFS Static w osobnej bazie SQLite (``GTFS_DATABASE_URL``).

Mają własne ``GtfsBase``, więc ``create_all`` bazy podróży ich nie tworzy. Tworzy je
i wypełnia wyłącznie importer (``python -m app.gtfs import``).

Uproszczenia względem specyfikacji GTFS:
- kalendarz jest zmaterializowany do par (service_id, data) z calendar.txt i calendar_dates.txt,
- czasy są zapisane jako sekundy od „południa minus 12 h” dnia kursowania (mogą być >= 24 h),
- kurs ma techniczny klucz całkowity ``trip_pk`` (oszczędność miejsca w stop_times).
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class GtfsBase(DeclarativeBase):
    """Bazowa klasa modeli rozkładu (osobne metadata od modeli aplikacji)."""


class GtfsFeed(GtfsBase):
    """Metadane ostatniego udanego importu (zawsze jeden wiersz, id=1)."""

    __tablename__ = "gtfs_feed"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(1000))
    sha256: Mapped[str] = mapped_column(String(64))
    imported_at: Mapped[datetime] = mapped_column(DateTime)  # UTC, bez strefy
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
    # Nazwa bez wielkości liter i polskich znaków — do wyszukiwania ("Główny" ~ "glowny").
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
    """Dzień, w którym kursuje dana usługa (service_id)."""

    __tablename__ = "gtfs_service_dates"
    __table_args__ = {"sqlite_with_rowid": False}

    service_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    date: Mapped[int] = mapped_column(Integer, primary_key=True)  # YYYYMMDD


class GtfsStopTime(GtfsBase):
    __tablename__ = "gtfs_stop_times"
    __table_args__ = (
        # Wyszukiwanie odjazdów z przystanku w oknie czasowym.
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
