"""Market data admin endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.cache.ohlcv_cache import OHLCVCacheService

router = APIRouter(prefix="/api/v1/market-data", tags=["market-data"])


@router.delete("/cache")
def invalidate_cache(
    symbol: str | None = Query(None),
    interval: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Admin endpoint to invalidate OHLCV cache."""
    cache = OHLCVCacheService(db)
    deleted = cache.invalidate(symbol=symbol, interval=interval)
    return {"deleted": deleted}
