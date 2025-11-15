"""Database session management for Dispatch."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from ..core.config import get_settings

Base = declarative_base()
_engine = None
_SessionLocal: sessionmaker[Session] | None = None


def configure_engine() -> None:
    """Initialise the SQLAlchemy engine from configuration."""

    global _engine, _SessionLocal
    if _engine is not None:
        return
    settings = get_settings()
    _engine = create_engine(settings.database_url, future=True)
    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, future=True)


def init_db() -> None:
    """Create database tables if they do not already exist."""

    if _engine is None:
        configure_engine()
    if _engine is None:
        raise RuntimeError("Database engine could not be initialised")
    Base.metadata.create_all(bind=_engine)


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations."""

    if _SessionLocal is None:
        configure_engine()
    if _SessionLocal is None:
        raise RuntimeError("Database session factory is not initialised")
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:  # pragma: no cover - re-raise after rollback
        session.rollback()
        raise
    finally:
        session.close()
