"""Wspólne fixture'y: SQLite in-memory (StaticPool), override get_db i TestClient."""

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
        # Jawnie None: klucz ze zmiennej środowiskowej nie może włączyć sieci w testach.
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
    # Domyślnie testy nie widzą żadnego rozkładu (nigdy lokalnego gtfs.db). Testy GTFS
    # podmieniają tę zależność na bazę zbudowaną z syntetycznego ZIP-a.
    app.dependency_overrides[get_gtfs_db] = lambda: None
    # Pogoda domyślnie wyłączona; testy pogody podmieniają klienta na mock bez sieci.
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
    """Plikowa baza rozkładu zaimportowana z syntetycznego ZIP-a."""
    engine = build_gtfs_engine(f"sqlite:///{tmp_path / 'gtfs.db'}")
    import_zip(gtfs_zip, engine)
    yield engine
    engine.dispose()


@pytest.fixture
def gtfs_client(app: FastAPI, gtfs_engine: Engine) -> Iterator[TestClient]:
    """Klient API z podpiętym zaimportowanym rozkładem."""
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
