"""Analytics API endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.api.dependencies import get_analytics_service
from backend.database import get_db
from backend.schemas.analytics import (
    CalendarEntry,
    DailySummary,
    PerformanceMetrics,
    StrategyBreakdown,
    SymbolBreakdown,
)
from backend.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/daily", response_model=list[DailySummary])
def daily_summaries(
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    account_id: str | None = Query(None),
    db: Session = Depends(get_db),
    service: AnalyticsService = Depends(get_analytics_service),
):
    """Get daily P&L summaries from materialized view."""
    return service.daily_summaries(
        db, from_date=from_date, to_date=to_date, account_id=account_id
    )


@router.get("/calendar", response_model=list[CalendarEntry])
def calendar(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    account_id: str | None = Query(None),
    db: Session = Depends(get_db),
    service: AnalyticsService = Depends(get_analytics_service),
):
    """Get monthly calendar data for P&L heatmap."""
    return service.calendar(
        db, year=year, month=month, account_id=account_id
    )


@router.get("/by-symbol", response_model=list[SymbolBreakdown])
def by_symbol(
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    account_id: str | None = Query(None),
    db: Session = Depends(get_db),
    service: AnalyticsService = Depends(get_analytics_service),
):
    """Get per-symbol P&L breakdown."""
    return service.by_symbol(
        db, from_date=from_date, to_date=to_date, account_id=account_id
    )


@router.get("/by-strategy", response_model=list[StrategyBreakdown])
def by_strategy(
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    account_id: str | None = Query(None),
    db: Session = Depends(get_db),
    service: AnalyticsService = Depends(get_analytics_service),
):
    """Get per-strategy P&L breakdown."""
    return service.by_strategy(
        db, from_date=from_date, to_date=to_date, account_id=account_id
    )


@router.get("/performance", response_model=PerformanceMetrics)
def performance(
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    account_id: str | None = Query(None),
    db: Session = Depends(get_db),
    service: AnalyticsService = Depends(get_analytics_service),
):
    """Get overall performance statistics."""
    return service.performance(
        db, from_date=from_date, to_date=to_date, account_id=account_id
    )
