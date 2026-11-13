"""Application settings based on pydantic-settings.

Values can be overridden with environment variables or a ``.env`` file.
Transport model parameters (``transport``) are described in ``app.core.transport_params``;
nested fields use the ``__`` separator, e.g. ``TRANSPORT__BIKE__MAX_DISTANCE_KM=25``.
"""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.core.transport_params import TransportSettings

API_V1_PREFIX = "/api/v1"

# Official ZTM Gdańsk GTFS Static feed (Otwarte Dane Gdańsk / CKAN portal).
GTFS_ZTM_GDANSK_URL = (
    "https://ckan.multimediagdansk.pl/dataset/c24aa637-3619-4dc2-a171-a23eec8f2172/"
    "resource/30e783e4-2bec-4a7d-bb22-ee3e3b26ca96/download/gtfsgoogle.zip"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
        case_sensitive=False,
    )

    transport: TransportSettings = Field(default_factory=TransportSettings)

    app_name: str = "SmartRoute"
    app_version: str = "0.1.0"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False

    database_url: str = "sqlite:///./smartroute.db"

    # --- GTFS Static (timetable) ---
    # Separate SQLite file: a re-import replaces the timetable in one transaction and never
    # touches the trips table. Only the importer creates it (python -m app.cli.gtfs import).
    gtfs_database_url: str = "sqlite:///./gtfs.db"
    gtfs_feed_url: str = GTFS_ZTM_GDANSK_URL
    # How far ahead of departure_at the trip comparison looks for connections [min].
    gtfs_search_window_min: Annotated[int, Field(ge=1, le=1440)] = 180
    # Download size limit for the ZIP [MB] (protects against an unexpectedly large file).
    gtfs_max_download_mb: Annotated[int, Field(ge=1, le=2048)] = 200

    # --- Current weather (Weatherbit Current Weather API) ---
    # Key only from backend/.env or an environment variable. SecretStr masks it in repr
    # and logs. No key = integration disabled (comparison runs without a weather adjustment).
    weatherbit_api_key: SecretStr | None = None
    weatherbit_base_url: str = "https://api.weatherbit.io/v2.0"
    weather_timeout_s: Annotated[float, Field(gt=0, le=30)] = 5.0
    # How many seconds a reading is cached per location (~0.1° grid).
    weather_cache_ttl_s: Annotated[int, Field(ge=60, le=86400)] = 1800
    # After an error (timeout, 429, no network) the API is not queried again for this many seconds.
    weather_error_cooldown_s: Annotated[int, Field(ge=0, le=86400)] = 300
    # Current weather is applied only to trips departing at most this many minutes from now.
    weather_max_lead_min: Annotated[int, Field(ge=0, le=360)] = 120

    # NoDecode: allows the list to be given as "a,b,c" instead of JSON.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    @field_validator("weatherbit_api_key", mode="before")
    @classmethod
    def _empty_key_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
