"""Analytics service — wraps analytics query functions.

Provides a service-layer interface for analytics operations so API
handlers remain thin.  Delegates to the existing analytics module
functions.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

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


class AnalyticsService:
    """Service for analytics query operations."""

    def daily_summaries(
        self,
        db: Session,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        account_id: str | None = None,
    ) -> list[DailySummary]:
        """Get daily P&L summaries."""
        data = get_daily_summaries(
            db, from_date=from_date, to_date=to_date, account_id=account_id
        )
        return [DailySummary(**row) for row in data]

    def calendar(
        self,
        db: Session,
        *,
        year: int,
        month: int,
        account_id: str | None = None,
    ) -> list[CalendarEntry]:
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

    def by_symbol(
        self,
        db: Session,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        account_id: str | None = None,
    ) -> list[SymbolBreakdown]:
        """Get per-symbol P&L breakdown."""
        data = get_by_symbol(
            db, from_date=from_date, to_date=to_date, account_id=account_id
        )
        return [SymbolBreakdown(**row) for row in data]

    def by_strategy(
        self,
        db: Session,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        account_id: str | None = None,
    ) -> list[StrategyBreakdown]:
        """Get per-strategy P&L breakdown."""
        data = get_by_strategy(
            db, from_date=from_date, to_date=to_date, account_id=account_id
        )
        return [StrategyBreakdown(**row) for row in data]

    def performance(
        self,
        db: Session,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        account_id: str | None = None,
    ) -> PerformanceMetrics:
        """Get overall performance statistics."""
        data = get_performance_metrics(
            db, from_date=from_date, to_date=to_date, account_id=account_id
        )
        return PerformanceMetrics(**data)
