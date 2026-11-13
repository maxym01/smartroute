"""Shared fixtures: in-memory SQLite (StaticPool), get_db override and TestClient."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.api.v1.comparisons import get_weather_client
from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.gtfs_session import build_gtfs_engine, get_gtfs_db
from app.db.session import build_engine, build_session_factory, get_db
from app.main import create_app
from app.services.gtfs.importer import import_zip
from tests.gtfs_factory import build_gtfs_zip

TEST_DATABASE_URL = "sqlite://"
TEST_CORS_ORIGINS = ["http://localhost:5173"]


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        database_url=TEST_DATABASE_URL,
        cors_origins=TEST_CORS_ORIGINS,
        # Explicit None: a key from an environment variable must not enable network calls in tests.
        weatherbit_api_key=None,
    )


@pytest.fixture
def engine() -> Iterator[Engine]:
    engine = build_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db_session(engine: Engine) -> Iterator[Session]:
    session = build_session_factory(engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def app(test_settings: Settings, engine: Engine) -> FastAPI:
    app = create_app(settings=test_settings, engine=engine)
    session_factory = build_session_factory(engine)

    def override_get_db() -> Iterator[Session]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: test_settings
    # By default tests see no timetable (never the local gtfs.db). GTFS tests replace
    # this dependency with a database built from the synthetic ZIP.
    app.dependency_overrides[get_gtfs_db] = lambda: None
    # Weather is disabled by default; weather tests replace the client with an offline mock.
    app.dependency_overrides[get_weather_client] = lambda: None
    return app


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


# --- GTFS ------------------------------------------------------------------------------------


@pytest.fixture
def gtfs_zip(tmp_path: Path) -> Path:
    return build_gtfs_zip(tmp_path / "gtfs.zip")


@pytest.fixture
def gtfs_engine(tmp_path: Path, gtfs_zip: Path) -> Iterator[Engine]:
    """File-based timetable database imported from the synthetic ZIP."""
    engine = build_gtfs_engine(f"sqlite:///{tmp_path / 'gtfs.db'}")
    import_zip(gtfs_zip, engine)
    yield engine
    engine.dispose()


@pytest.fixture
def gtfs_client(app: FastAPI, gtfs_engine: Engine) -> Iterator[TestClient]:
    """API client wired to the imported timetable."""
    session_factory = build_session_factory(gtfs_engine)

    def override_get_gtfs_db() -> Iterator[Session]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_gtfs_db] = override_get_gtfs_db
    with TestClient(app) as test_client:
        yield test_client
