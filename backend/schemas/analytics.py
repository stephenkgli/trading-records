"""Analytics schemas (placeholder for Phase 2, expanded later)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class DailySummary(BaseModel):
    """Daily P&L summary from materialized view."""

    date: date
    account_id: str
    gross_pnl: Decimal
    net_pnl: Decimal
    commissions: Decimal
    trade_count: int
    win_count: int
    loss_count: int


class CalendarEntry(BaseModel):
    """Single day entry for the P&L calendar."""

    date: date
    net_pnl: Decimal
    trade_count: int
    closed_count: int
    has_activity: bool


class SymbolBreakdown(BaseModel):
    """P&L breakdown for a single symbol."""

    symbol: str
    net_pnl: Decimal
    trade_count: int
    win_count: int
    loss_count: int


class StrategyBreakdown(BaseModel):
    """P&L breakdown for a single strategy tag."""

    strategy_tag: str
    net_pnl: Decimal
    trade_count: int
    group_count: int


class PerformanceMetrics(BaseModel):
    """Overall performance statistics."""

    total_pnl: Decimal
    total_commissions: Decimal
    net_pnl: Decimal
    total_trades: int
    win_count: int
    loss_count: int
    win_rate: float
    avg_win: Decimal
    avg_loss: Decimal
    win_loss_ratio: float | None = None
    expectancy: Decimal
    trading_days: int
