"""SQLAlchemy engine, session factory and the ``get_db`` FastAPI dependency."""

from collections.abc import Iterator
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings


def build_engine(database_url: str, *, echo: bool = False) -> Engine:
    """Create the engine; SQLite disables check_same_thread and in-memory shares one connection."""
    url = make_url(database_url)
    kwargs: dict = {"echo": echo}
    if url.get_backend_name() == "sqlite":
        kwargs["connect_args"] = {"check_same_thread": False}
        if url.database in (None, "", ":memory:"):
            kwargs["poolclass"] = StaticPool
        engine = create_engine(url, **kwargs)
        event.listen(engine, "connect", _register_unicode_lower)
        return engine
    return create_engine(url, **kwargs)


def _register_unicode_lower(dbapi_connection: Any, _: Any) -> None:
    # SQLite's built-in lower() handles ASCII only — override it so that "Ł" == "ł".
    dbapi_connection.create_function(
        "lower",
        1,
        lambda value: value.casefold() if isinstance(value, str) else value,
        deterministic=True,
    )


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
