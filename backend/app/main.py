"""FastAPI application entry point.

Run (from the ``backend`` directory): ``uvicorn app.main:app --reload``
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine

import app.models  # noqa: F401  — registers the models in Base.metadata before create_all
from app.api.v1.router import api_router
from app.core.config import API_V1_PREFIX, Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.db import session as db_session
from app.db.base import Base
from app.db.migrations import upgrade_schema
from app.services.weather import WeatherbitClient

CORS_ALLOWED_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Alembic is out of the MVP scope: tables are created at startup, and new nullable
    # columns are added by an idempotent migration (no data loss).
    Base.metadata.create_all(bind=app.state.engine)
    upgrade_schema(app.state.engine)
    yield


def build_weather_client(settings: Settings) -> WeatherbitClient:
    key = settings.weatherbit_api_key
    return WeatherbitClient(
        key.get_secret_value() if key else None,
        base_url=settings.weatherbit_base_url,
        timeout_s=settings.weather_timeout_s,
        cache_ttl_s=settings.weather_cache_ttl_s,
        error_cooldown_s=settings.weather_error_cooldown_s,
    )


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    settings = settings or get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine or db_session.engine
    # One client per application: a shared TTL cache and error cooldown for all requests.
    app.state.weather_client = build_weather_client(settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=CORS_ALLOWED_METHODS,
        allow_headers=["Content-Type", "Authorization", "Accept"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=API_V1_PREFIX)
    return app


app = create_app()
