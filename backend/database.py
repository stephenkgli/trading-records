"""SQLAlchemy 2.0 database engine and session management (synchronous)."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


def get_db() -> Session:  # type: ignore[misc]
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db  # type: ignore[misc]
    finally:
        db.close()
