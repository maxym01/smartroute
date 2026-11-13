"""Engine and sessions for the GTFS timetable database (a separate SQLite file).

The application only reads this database; the importer creates and overwrites it. If the
database file does not exist, ``get_gtfs_db`` returns ``None`` (timetable not imported)
instead of creating an empty file.
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
    """Engine with explicit transaction control.

    The default ``sqlite3`` driver does not open a transaction before DDL, so the importer's
    ``DROP/CREATE TABLE`` would not be rolled back. Recipe from the SQLAlchemy docs
    ("Serializable isolation / Savepoints / Transactional DDL"): disable the driver's
    autobegin and emit BEGIN ourselves.
    """
    engine = build_engine(database_url)

    @event.listens_for(engine, "connect")
    def _disable_driver_autobegin(dbapi_connection: Any, _: Any) -> None:
        dbapi_connection.isolation_level = None
        # WAL: the API can read the old timetable while the importer writes a new one.
        dbapi_connection.execute("PRAGMA journal_mode=WAL")
        # In WAL mode synchronous=NORMAL keeps the database consistent and speeds up writes.
        dbapi_connection.execute("PRAGMA synchronous=NORMAL")

    @event.listens_for(engine, "begin")
    def _begin(conn: Any) -> None:
        conn.exec_driver_sql("BEGIN")

    return engine


def sqlite_file_exists(database_url: str) -> bool:
    """For file-based SQLite, check that the file exists. Other databases (and in-memory) → True."""
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
