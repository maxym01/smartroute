from pathlib import Path

from sqlalchemy import inspect, text

from app.db.migrations import upgrade_schema
from app.db.session import build_engine

# Schema of the trips table before the GTFS columns were added.
LEGACY_TRIPS_DDL = """
CREATE TABLE trips (
    id INTEGER NOT NULL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    origin VARCHAR(200) NOT NULL,
    destination VARCHAR(200) NOT NULL,
    distance_km FLOAT NOT NULL,
    passengers INTEGER NOT NULL,
    priority VARCHAR(20) NOT NULL,
    has_car BOOLEAN NOT NULL,
    allow_bike BOOLEAN NOT NULL,
    notes VARCHAR(500),
    created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
    updated_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL
)
"""


def test_upgrade_adds_columns_without_losing_data(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(text(LEGACY_TRIPS_DDL))
        conn.execute(
            text(
                "INSERT INTO trips (name, origin, destination, distance_km, passengers, priority,"
                " has_car, allow_bike) VALUES ('Sopot', 'Gdańsk', 'Sopot', 12, 2, 'fastest', 1, 0)"
            )
        )

    added = upgrade_schema(engine)

    assert added == ["trips.origin_stop_id", "trips.destination_stop_id", "trips.departure_at"]
    columns = {c["name"] for c in inspect(engine).get_columns("trips")}
    assert {"origin_stop_id", "destination_stop_id", "departure_at"} <= columns
    with engine.connect() as conn:
        row = conn.execute(text("SELECT name, origin, passengers, departure_at FROM trips")).one()
    assert tuple(row) == ("Sopot", "Gdańsk", 2, None)
    assert upgrade_schema(engine) == []  # idempotent
    engine.dispose()


def test_upgrade_on_fresh_database_does_nothing(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'new.db'}")

    assert upgrade_schema(engine) == []
    engine.dispose()


def test_app_startup_migrates_legacy_database(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from app.core.config import Settings
    from app.main import create_app

    url = f"sqlite:///{tmp_path / 'legacy.db'}"
    engine = build_engine(url)
    with engine.begin() as conn:
        conn.execute(text(LEGACY_TRIPS_DDL))
    app = create_app(settings=Settings(_env_file=None, database_url=url), engine=engine)

    with TestClient(app):
        pass

    columns = {c["name"] for c in inspect(engine).get_columns("trips")}
    assert "departure_at" in columns
    engine.dispose()
