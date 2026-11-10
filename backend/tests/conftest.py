"""Wspólne fixture'y: SQLite in-memory (StaticPool), override get_db i TestClient."""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.session import build_engine, build_session_factory, get_db
from app.main import create_app

TEST_DATABASE_URL = "sqlite://"
TEST_CORS_ORIGINS = ["http://localhost:5173"]


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        database_url=TEST_DATABASE_URL,
        cors_origins=TEST_CORS_ORIGINS,
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
    return app


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
