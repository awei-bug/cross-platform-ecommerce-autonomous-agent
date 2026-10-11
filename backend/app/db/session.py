from collections.abc import Generator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.models import Base


def _ensure_sqlite_directory(database_url: str) -> None:
    prefix = "sqlite+pysqlite:///"
    if not database_url.startswith(prefix) or database_url.endswith(":memory:"):
        return
    raw_path = database_url.removeprefix(prefix)
    Path(raw_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    database_url = settings.database_url
    _ensure_sqlite_directory(database_url)
    kwargs: dict[str, object] = {
        "echo": settings.database_echo,
        "pool_pre_ping": True,
    }
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if database_url.endswith(":memory:"):
            kwargs["poolclass"] = StaticPool
    return create_engine(database_url, **kwargs)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def initialize_database() -> None:
    settings = get_settings()
    if settings.database_auto_create:
        Base.metadata.create_all(bind=get_engine())


def get_db() -> Generator[Session]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope() -> Generator[Session]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
