"""Trades API endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.api.dependencies import get_trade_service
from backend.database import get_db
from backend.schemas.trade import TradeListResponse, TradeResponse, TradeSummaryResponse
from backend.services.trade_service import TradeService

router = APIRouter(prefix="/api/v1/trades", tags=["trades"])


@router.get("", response_model=TradeListResponse)
def list_trades(
    account_id: str | None = Query(None),
    broker: str | None = Query(None),
    symbol: str | None = Query(None),
    asset_class: str | None = Query(None),
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    sort: str = Query("executed_at"),
    order: str = Query("desc"),
    db: Session = Depends(get_db),
    service: TradeService = Depends(get_trade_service),
):
    """List trades with filtering, pagination, and sorting."""
    return service.list_trades(
        db,
        account_id=account_id,
        broker=broker,
        symbol=symbol,
        asset_class=asset_class,
        from_date=from_date,
        to_date=to_date,
        page=page,
        per_page=per_page,
        sort=sort,
        order=order,
    )


@router.get("/summary", response_model=TradeSummaryResponse)
def trades_summary(
    account_id: str | None = Query(None),
    broker: str | None = Query(None),
    symbol: str | None = Query(None),
    asset_class: str | None = Query(None),
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    db: Session = Depends(get_db),
    service: TradeService = Depends(get_trade_service),
):
    """Get aggregated trade statistics for the filtered scope."""
    return service.get_summary(
        db,
        account_id=account_id,
        broker=broker,
        symbol=symbol,
        asset_class=asset_class,
        from_date=from_date,
        to_date=to_date,
    )


@router.get("/{trade_id}", response_model=TradeResponse)
def get_trade(
    trade_id: uuid.UUID,
    db: Session = Depends(get_db),
    service: TradeService = Depends(get_trade_service),
):
    """Get a single trade by ID."""
    result = service.get_trade(db, trade_id)
    if not result:
        raise HTTPException(status_code=404, detail="Trade not found")
    return result
