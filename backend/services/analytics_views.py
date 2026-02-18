"""Analytics view registrations.

Each call to ``register_view()`` wires a SQL query function + Pydantic schema
into the analytics route factory.  To add a new standard date-range view,
add one ``register_view()`` call here and one Pydantic model in
``schemas/analytics.py``.
"""

from __future__ import annotations

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
from backend.services.analytics_registry import (
    AnalyticsViewDef,
    ParamStyle,
    register_view,
)


def _calendar_row_converter(row: dict) -> dict:
    """Coerce nullable fields in calendar rows to safe defaults."""
    return {
        "date": row["date"],
        "net_pnl": row["net_pnl"] or 0,
        "trade_count": row["trade_count"] or 0,
    }


register_view(AnalyticsViewDef(
    name="daily",
    query_fn=get_daily_summaries,
    schema=DailySummary,
    summary="Get daily P&L summaries from materialized view",
))

register_view(AnalyticsViewDef(
    name="calendar",
    query_fn=get_calendar_data,
    schema=CalendarEntry,
    param_style=ParamStyle.CALENDAR,
    summary="Get monthly calendar data for P&L heatmap",
    row_converter=_calendar_row_converter,
))

register_view(AnalyticsViewDef(
    name="by-symbol",
    query_fn=get_by_symbol,
    schema=SymbolBreakdown,
    summary="Get per-symbol P&L breakdown",
))

register_view(AnalyticsViewDef(
    name="by-strategy",
    query_fn=get_by_strategy,
    schema=StrategyBreakdown,
    summary="Get per-strategy P&L breakdown",
))

register_view(AnalyticsViewDef(
    name="performance",
    query_fn=get_performance_metrics,
    schema=PerformanceMetrics,
    is_list=False,
    summary="Get overall performance statistics",
))
