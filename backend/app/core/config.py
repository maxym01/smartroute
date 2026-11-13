"""Konfiguracja aplikacji oparta na pydantic-settings.

Wartości można nadpisać zmiennymi środowiskowymi lub plikiem ``.env``.
Parametry modelu transportu (``transport``) są opisane w ``app.core.transport_params``;
zagnieżdżone pola nadpisuje się z separatorem ``__``, np. ``TRANSPORT__BIKE__MAX_DISTANCE_KM=25``.
"""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.core.transport_params import TransportSettings

API_V1_PREFIX = "/api/v1"

# Oficjalny feed GTFS Static ZTM Gdańsk (portal Otwarte Dane Gdańsk / CKAN).
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

    # --- GTFS Static (rozkład jazdy) ---
    # Osobny plik SQLite: ponowny import podmienia rozkład w jednej transakcji i nie dotyka
    # tabeli podróży. Plik tworzy wyłącznie importer (python -m app.gtfs import).
    gtfs_database_url: str = "sqlite:///./gtfs.db"
    gtfs_feed_url: str = GTFS_ZTM_GDANSK_URL
    # Jak daleko w przód od departure_at szukamy połączeń przy porównaniu podróży [min].
    gtfs_search_window_min: Annotated[int, Field(ge=1, le=1440)] = 180
    # Limit rozmiaru pobieranego ZIP-a [MB] (ochrona przed nieoczekiwanie dużym plikiem).
    gtfs_max_download_mb: Annotated[int, Field(ge=1, le=2048)] = 200

    # --- Pogoda bieżąca (Weatherbit Current Weather API) ---
    # Klucz wyłącznie z backend/.env lub zmiennej środowiskowej. SecretStr maskuje go w repr
    # i logach. Brak klucza = integracja wyłączona (porównanie działa bez korekty pogodowej).
    weatherbit_api_key: SecretStr | None = None
    weatherbit_base_url: str = "https://api.weatherbit.io/v2.0"
    weather_timeout_s: Annotated[float, Field(gt=0, le=30)] = 5.0
    # Ile sekund pamiętamy odczyt dla danej lokalizacji (siatka ~0,1°).
    weather_cache_ttl_s: Annotated[int, Field(ge=60, le=86400)] = 1800
    # Po błędzie (timeout, 429, brak sieci) przez tyle sekund nie odpytujemy API ponownie.
    weather_error_cooldown_s: Annotated[int, Field(ge=0, le=86400)] = 300
    # Pogodę bieżącą stosujemy tylko do podróży z odjazdem najpóźniej tyle minut od teraz.
    weather_max_lead_min: Annotated[int, Field(ge=0, le=360)] = 120

    # NoDecode: pozwala podać listę jako "a,b,c" zamiast JSON-a.
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
