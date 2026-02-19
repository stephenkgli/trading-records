"""Database utility helpers."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy.orm import Session

from backend.database import SessionLocal


@contextmanager
def session_scope(db: Session | None = None) -> Generator[Session, None, None]:
    """Provide a transactional session scope.

    If *db* is ``None`` a new session is created, committed on success,
    rolled back on exception, and closed on exit.  When an existing
    session is supplied it is yielded as-is and the caller remains
    responsible for its lifecycle.

    Usage::

        with session_scope() as session:
            session.execute(...)
        # auto-commit & close

        with session_scope(existing_db) as session:
            session.execute(...)
        # nothing happens on exit — caller owns the session
    """
    own_session = db is None
    session = SessionLocal() if own_session else db
    try:
        yield session
        if own_session:
            session.commit()
    except Exception:
        if own_session:
            session.rollback()
        raise
    finally:
        if own_session:
            session.close()
