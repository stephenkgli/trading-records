"""Trades API endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.trade import Trade
from backend.schemas.trade import TradeListResponse, TradeResponse

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
):
    """List trades with filtering, pagination, and sorting."""
    query = select(Trade)

    # Apply filters
    if account_id:
        query = query.where(Trade.account_id == account_id)
    if broker:
        query = query.where(Trade.broker == broker)
    if symbol:
        query = query.where(Trade.symbol == symbol)
    if asset_class:
        query = query.where(Trade.asset_class == asset_class)
    if from_date:
        query = query.where(Trade.executed_at >= from_date)
    if to_date:
        query = query.where(Trade.executed_at <= to_date)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar_one()

    # Sorting
    sort_column = getattr(Trade, sort, Trade.executed_at)
    if order == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    # Pagination
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    trades = db.execute(query).scalars().all()
    pages = (total + per_page - 1) // per_page if total > 0 else 1

    return TradeListResponse(
        trades=[TradeResponse.model_validate(t) for t in trades],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


@router.get("/{trade_id}", response_model=TradeResponse)
def get_trade(trade_id: uuid.UUID, db: Session = Depends(get_db)):
    """Get a single trade by ID."""
    trade = db.get(Trade, trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    return TradeResponse.model_validate(trade)
