import pytest
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings
from app.db.session import build_engine


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("APP_NAME", "ENVIRONMENT", "DEBUG", "DATABASE_URL", "CORS_ORIGINS"):
        monkeypatch.delenv(var, raising=False)


def test_default_settings() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_name == "SmartRoute"
    assert settings.environment == "development"
    assert settings.debug is False
    assert settings.database_url == "sqlite:///./smartroute.db"
    assert settings.cors_origins == ["http://localhost:5173"]


def test_settings_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./other.db")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DEBUG", "true")

    settings = Settings(_env_file=None)

    assert settings.database_url == "sqlite:///./other.db"
    assert settings.environment == "production"
    assert settings.debug is True


def test_cors_origins_parsed_from_comma_separated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", " http://localhost:5173 , https://app.example.com ,")

    settings = Settings(_env_file=None)

    assert settings.cors_origins == ["http://localhost:5173", "https://app.example.com"]


def test_cors_origins_accept_list() -> None:
    settings = Settings(_env_file=None, cors_origins=["http://a.test", "http://b.test"])

    assert settings.cors_origins == ["http://a.test", "http://b.test"]


def test_invalid_environment_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="staging")


def test_transport_params_overridable_with_nested_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSPORT__CAR__FUEL_PRICE_PLN_PER_L", "7.25")
    monkeypatch.setenv("TRANSPORT__BIKE__MAX_DISTANCE_KM", "25")

    settings = Settings(_env_file=None)

    assert settings.transport.car.fuel_price_pln_per_l == 7.25
    assert settings.transport.bike.max_distance_km == 25
    assert settings.transport.car.avg_speed_kmh == 40  # pozostałe bez zmian


def test_transport_params_from_env_are_validated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSPORT__PUBLIC_TRANSPORT__AVG_SPEED_KMH", "0")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()


def test_in_memory_sqlite_engine_uses_static_pool() -> None:
    engine = build_engine("sqlite://")
    try:
        assert isinstance(engine.pool, StaticPool)
        with engine.connect() as conn:
            assert conn.execute(text("SELECT 1")).scalar_one() == 1
    finally:
        engine.dispose()


def test_file_sqlite_engine_does_not_use_static_pool(tmp_path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        assert not isinstance(engine.pool, StaticPool)
        with engine.connect() as conn:
            assert conn.execute(text("SELECT 1")).scalar_one() == 1
    finally:
        engine.dispose()
