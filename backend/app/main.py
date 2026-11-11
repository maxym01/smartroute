"""Punkt wejścia aplikacji FastAPI.

Uruchomienie (z katalogu ``backend``): ``uvicorn app.main:app --reload``
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine

import app.models  # noqa: F401  — rejestruje modele w Base.metadata przed create_all
from app.api.v1.router import api_router
from app.core.config import API_V1_PREFIX, Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.db import session as db_session
from app.db.base import Base
from app.db.migrations import upgrade_schema

CORS_ALLOWED_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Alembic poza zakresem MVP — tabele tworzymy przy starcie, a nowe kolumny nullable
    # dodaje idempotentna migracja (bez utraty danych).
    Base.metadata.create_all(bind=app.state.engine)
    upgrade_schema(app.state.engine)
    yield


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
