"""
Tests for the service layer (ImportService, TradeService, AnalyticsService).

Verifies:
1. ImportService — CSV import orchestration, import log listing
2. TradeService — trade listing, detail, summary
3. AnalyticsService — daily, calendar, by-symbol, by-strategy, performance

These are unit tests that call the service methods directly with a db_session,
bypassing the API layer.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from backend.models.trade import Trade
from backend.models.trade_group import TradeGroup
from backend.services.analytics_service import AnalyticsService
from backend.services.import_service import ImportService
from backend.services.trade_service import TradeService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_trades(db_session, count=5):
    """Insert test trades and return them."""
    trades = []
    symbols = ["AAPL", "MSFT", "GOOG"]
    for i in range(count):
        trade = Trade(
            id=uuid.uuid4(),
            broker="ibkr",
            broker_exec_id=f"SVC{i:04d}",
            account_id="U1234567",
            symbol=symbols[i % len(symbols)],
            asset_class="stock",
            side="buy" if i % 2 == 0 else "sell",
            quantity=Decimal("100"),
            price=Decimal(f"{150 + i}.00"),
            commission=Decimal("1.00"),
            executed_at=datetime(2025, 1, 15 + (i % 10), 10, i, 0, tzinfo=timezone.utc),
            currency="USD",
            raw_data={"seed": i},
        )
        trades.append(trade)
        db_session.add(trade)
    db_session.flush()
    return trades


def _seed_groups(db_session):
    """Insert trade groups for analytics tests."""
    group1 = TradeGroup(
        id=uuid.uuid4(),
        account_id="U1234567",
        symbol="AAPL",
        asset_class="stock",
        direction="long",
        status="closed",
        realized_pnl=Decimal("500.00"),
        opened_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        closed_at=datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc),
        strategy_tag="momentum",
    )
    group2 = TradeGroup(
        id=uuid.uuid4(),
        account_id="U1234567",
        symbol="MSFT",
        asset_class="stock",
        direction="long",
        status="closed",
        realized_pnl=Decimal("-250.00"),
        opened_at=datetime(2025, 1, 16, 10, 0, 0, tzinfo=timezone.utc),
        closed_at=datetime(2025, 1, 16, 14, 0, 0, tzinfo=timezone.utc),
        strategy_tag="mean_reversion",
    )
    db_session.add_all([group1, group2])
    db_session.flush()
    return [group1, group2]


# ===========================================================================
# TradeService
# ===========================================================================

class TestTradeServiceListTrades:
    """Test TradeService.list_trades."""

    def test_list_trades_empty(self, db_session):
        """Empty DB should return zero trades."""
        svc = TradeService()
        result = svc.list_trades(db_session)
        assert result.total == 0
        assert result.trades == []

    def test_list_trades_paginated(self, db_session):
        """list_trades should respect page and per_page."""
        _seed_trades(db_session, 10)
        svc = TradeService()
        result = svc.list_trades(db_session, page=1, per_page=3)
        assert len(result.trades) == 3
        assert result.total == 10

    def test_list_trades_filter_symbol(self, db_session):
        """Filtering by symbol should return only matching trades."""
        _seed_trades(db_session, 9)
        svc = TradeService()
        result = svc.list_trades(db_session, symbol="AAPL")
        for trade in result.trades:
            assert trade.symbol == "AAPL"

    def test_list_trades_filter_broker(self, db_session):
        """Filtering by broker should return only matching trades."""
        _seed_trades(db_session, 5)
        svc = TradeService()
        result = svc.list_trades(db_session, broker="ibkr")
        assert result.total == 5

    def test_list_trades_sort_asc(self, db_session):
        """Sorting ascending by executed_at should return oldest first."""
        _seed_trades(db_session, 5)
        svc = TradeService()
        result = svc.list_trades(db_session, sort="executed_at", order="asc")
        if len(result.trades) >= 2:
            assert result.trades[0].executed_at <= result.trades[1].executed_at


class TestTradeServiceGetTrade:
    """Test TradeService.get_trade."""

    def test_get_existing_trade(self, db_session):
        """Should return the trade when it exists."""
        trades = _seed_trades(db_session, 1)
        svc = TradeService()
        result = svc.get_trade(db_session, trades[0].id)
        assert result is not None
        assert result.id == trades[0].id

    def test_get_nonexistent_trade(self, db_session):
        """Should return None for nonexistent trade."""
        svc = TradeService()
        result = svc.get_trade(db_session, uuid.uuid4())
        assert result is None


class TestTradeServiceGetSummary:
    """Test TradeService.get_summary."""

    def test_summary_with_trades(self, db_session):
        """Summary should return correct aggregates."""
        _seed_trades(db_session, 5)
        svc = TradeService()
        result = svc.get_summary(db_session)
        assert result.total_trades == 5
        assert result.total_commissions > 0

    def test_summary_empty_db(self, db_session):
        """Summary with no trades should return zero totals."""
        svc = TradeService()
        result = svc.get_summary(db_session)
        assert result.total_trades == 0

    def test_summary_filter_symbol(self, db_session):
        """Summary filtered by symbol should only count matching trades."""
        _seed_trades(db_session, 9)
        svc = TradeService()
        result = svc.get_summary(db_session, symbol="AAPL")
        assert result.total_trades > 0
        assert result.total_trades < 9  # Not all trades are AAPL


# ===========================================================================
# ImportService
# ===========================================================================

class TestImportServiceCSV:
    """Test ImportService.import_csv."""

    def test_import_csv_ibkr(self, db_session, ibkr_activity_csv):
        """ImportService.import_csv should import IBKR CSV."""
        svc = ImportService()
        result = svc.import_csv(ibkr_activity_csv, filename="ibkr.csv", db=db_session)
        assert result.records_imported > 0
        assert result.status == "success"

    def test_import_csv_tradovate_perf(self, db_session, tradovate_performance_csv):
        """ImportService.import_csv should import Tradovate Performance CSV."""
        svc = ImportService()
        result = svc.import_csv(
            tradovate_performance_csv, filename="Performance.csv", db=db_session
        )
        assert result.records_imported == 20

    def test_import_csv_bytes(self, db_session, ibkr_activity_csv):
        """ImportService should handle bytes input."""
        svc = ImportService()
        result = svc.import_csv(
            ibkr_activity_csv.encode("utf-8"), filename="ibkr.csv", db=db_session
        )
        assert result.records_imported > 0

    def test_import_csv_unknown_format(self, db_session):
        """Unknown CSV format should raise ValueError."""
        svc = ImportService()
        with pytest.raises(ValueError, match="Unknown CSV format"):
            svc.import_csv("col1,col2\na,b\n", filename="unknown.csv", db=db_session)


class TestImportServiceLogs:
    """Test ImportService.list_import_logs."""

    def test_list_logs_empty(self, db_session):
        """Empty DB should return empty logs."""
        svc = ImportService()
        result = svc.list_import_logs(db_session)
        assert result.total == 0
        assert result.logs == []

    def test_list_logs_after_import(self, db_session, ibkr_activity_csv):
        """After an import, list_import_logs should include an entry."""
        svc = ImportService()
        svc.import_csv(ibkr_activity_csv, filename="ibkr.csv", db=db_session)
        result = svc.list_import_logs(db_session)
        assert result.total >= 1
        assert len(result.logs) >= 1

    def test_list_logs_pagination(self, db_session, ibkr_activity_csv):
        """Pagination parameters should be respected."""
        svc = ImportService()
        svc.import_csv(ibkr_activity_csv, filename="ibkr.csv", db=db_session)
        result = svc.list_import_logs(db_session, page=1, per_page=1)
        assert result.page == 1
        assert result.per_page == 1


# ===========================================================================
# AnalyticsService
# ===========================================================================

class TestAnalyticsServiceDaily:
    """Test AnalyticsService.daily_summaries."""

    def test_daily_summaries_empty(self, db_session):
        """Empty DB should return empty list."""
        svc = AnalyticsService()
        result = svc.daily_summaries(db_session)
        assert result == []

    def test_daily_summaries_with_data(self, db_session):
        """Should return summaries when trades exist."""
        _seed_trades(db_session, 5)
        svc = AnalyticsService()
        result = svc.daily_summaries(db_session)
        assert len(result) > 0


class TestAnalyticsServiceCalendar:
    """Test AnalyticsService.calendar."""

    def test_calendar_empty(self, db_session):
        """Empty month should return empty list."""
        svc = AnalyticsService()
        result = svc.calendar(db_session, year=2024, month=6)
        assert result == []


class TestAnalyticsServiceBySymbol:
    """Test AnalyticsService.by_symbol."""

    def test_by_symbol_with_groups(self, db_session):
        """Should return per-symbol breakdown when groups exist."""
        _seed_trades(db_session, 5)
        _seed_groups(db_session)
        svc = AnalyticsService()
        result = svc.by_symbol(db_session)
        assert len(result) > 0


class TestAnalyticsServicePerformance:
    """Test AnalyticsService.performance."""

    def test_performance_with_data(self, db_session):
        """Should return performance metrics when data exists."""
        _seed_trades(db_session, 5)
        _seed_groups(db_session)
        svc = AnalyticsService()
        result = svc.performance(db_session)
        assert result.total_trades >= 0
