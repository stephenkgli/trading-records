"""Analytics API endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas.analytics import (
    CalendarEntry,
    DailySummary,
    PerformanceMetrics,
    StrategyBreakdown,
    SymbolBreakdown,
)
from backend.services.analytics import (
    get_by_strategy,
    get_by_symbol,
    get_calendar_data,
    get_daily_summaries,
    get_performance_metrics,
)

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/daily", response_model=list[DailySummary])
def daily_summaries(
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    account_id: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Get daily P&L summaries from materialized view."""
    data = get_daily_summaries(db, from_date=from_date, to_date=to_date, account_id=account_id)
    return [DailySummary(**row) for row in data]


@router.get("/calendar", response_model=list[CalendarEntry])
def calendar(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    account_id: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Get monthly calendar data for P&L heatmap."""
    data = get_calendar_data(db, year=year, month=month, account_id=account_id)
    return [
        CalendarEntry(
            date=row["date"],
            net_pnl=row["net_pnl"] or 0,
            trade_count=row["trade_count"] or 0,
        )
        for row in data
    ]


@router.get("/by-symbol", response_model=list[SymbolBreakdown])
def by_symbol(
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    account_id: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Get per-symbol P&L breakdown."""
    data = get_by_symbol(db, from_date=from_date, to_date=to_date, account_id=account_id)
    return [SymbolBreakdown(**row) for row in data]


@router.get("/by-strategy", response_model=list[StrategyBreakdown])
def by_strategy(
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    account_id: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Get per-strategy P&L breakdown."""
    data = get_by_strategy(db, from_date=from_date, to_date=to_date, account_id=account_id)
    return [StrategyBreakdown(**row) for row in data]


@router.get("/performance", response_model=PerformanceMetrics)
def performance(
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    account_id: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Get overall performance statistics."""
    data = get_performance_metrics(
        db, from_date=from_date, to_date=to_date, account_id=account_id
    )
    return PerformanceMetrics(**data)
