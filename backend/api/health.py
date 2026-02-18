"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.database import get_db

router = APIRouter()


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Health check — verifies DB connectivity and service readiness.

    Used by Docker healthcheck. Unauthenticated.
    """
    try:
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}
