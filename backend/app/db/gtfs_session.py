"""Silnik i sesje bazy rozkładu GTFS (osobny plik SQLite).

Aplikacja tylko czyta tę bazę; tworzy ją i nadpisuje importer. Jeśli plik bazy nie istnieje,
``get_gtfs_db`` zwraca ``None`` (rozkład nie został zaimportowany), zamiast tworzyć pusty plik.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import build_engine, build_session_factory


def build_gtfs_engine(database_url: str) -> Engine:
    """Silnik z jawnym sterowaniem transakcjami.

    Domyślny sterownik ``sqlite3`` nie otwiera transakcji przed DDL, więc ``DROP/CREATE TABLE``
    importera nie byłyby wycofywane. Przepis z dokumentacji SQLAlchemy („Serializable isolation /
    Savepoints / Transactional DDL”): wyłączamy autobegin sterownika i sami wysyłamy BEGIN.
    """
    engine = build_engine(database_url)

    @event.listens_for(engine, "connect")
    def _disable_driver_autobegin(dbapi_connection: Any, _: Any) -> None:
        dbapi_connection.isolation_level = None
        # WAL: API może czytać stary rozkład, gdy importer w transakcji zapisuje nowy.
        dbapi_connection.execute("PRAGMA journal_mode=WAL")
        # W trybie WAL synchronous=NORMAL zachowuje spójność bazy, a przyspiesza zapis.
        dbapi_connection.execute("PRAGMA synchronous=NORMAL")

    @event.listens_for(engine, "begin")
    def _begin(conn: Any) -> None:
        conn.exec_driver_sql("BEGIN")

    return engine


def sqlite_file_exists(database_url: str) -> bool:
    """Dla SQLite w pliku sprawdza, czy plik istnieje. Inne bazy (i in-memory) → True."""
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite" or url.database in (None, "", ":memory:"):
        return True
    return Path(url.database).exists()


_settings = get_settings()
gtfs_engine = build_gtfs_engine(_settings.gtfs_database_url)
GtfsSessionLocal = build_session_factory(gtfs_engine)


def get_gtfs_db() -> Iterator[Session | None]:
    if not sqlite_file_exists(_settings.gtfs_database_url):
        yield None
        return
    db = GtfsSessionLocal()
    try:
        yield db
    finally:
        db.close()
