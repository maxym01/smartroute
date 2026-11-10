"""Silnik SQLAlchemy, fabryka sesji i zależność FastAPI ``get_db``."""

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings


def build_engine(database_url: str, *, echo: bool = False) -> Engine:
    """Tworzy silnik; dla SQLite wyłącza check_same_thread, a in-memory dzieli jedno połączenie."""
    url = make_url(database_url)
    kwargs: dict = {"echo": echo}
    if url.get_backend_name() == "sqlite":
        kwargs["connect_args"] = {"check_same_thread": False}
        if url.database in (None, "", ":memory:"):
            kwargs["poolclass"] = StaticPool
    return create_engine(url, **kwargs)


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


_settings = get_settings()
engine = build_engine(_settings.database_url, echo=_settings.debug)
SessionLocal = build_session_factory(engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
