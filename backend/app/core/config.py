"""Konfiguracja aplikacji oparta na pydantic-settings.

Wartości można nadpisać zmiennymi środowiskowymi lub plikiem ``.env``.
Parametry modelu transportu (``transport``) są opisane w ``app.core.transport_params``;
zagnieżdżone pola nadpisuje się z separatorem ``__``, np. ``TRANSPORT__BIKE__MAX_DISTANCE_KM=25``.
"""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.core.transport_params import TransportSettings

API_V1_PREFIX = "/api/v1"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
        case_sensitive=False,
    )

    transport: TransportSettings = Field(default_factory=TransportSettings)

    app_name: str = "SmartRoute AI"
    app_version: str = "0.1.0"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False

    database_url: str = "sqlite:///./smartroute.db"

    # NoDecode: pozwala podać listę jako "a,b,c" zamiast JSON-a.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
