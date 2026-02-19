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

import pytest

from backend.services.analytics_service import AnalyticsService
from backend.services.analytics_registry import get_views
from backend.services.import_service import ImportService
from backend.services.trade_service import TradeService


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

    def test_list_trades_paginated(self, db_session, seed_trades):
        """list_trades should respect page and per_page."""
        seed_trades(count=10, exec_prefix="SVC")
        svc = TradeService()
        result = svc.list_trades(db_session, page=1, per_page=3)
        assert len(result.trades) == 3
        assert result.total == 10

    def test_list_trades_filter_symbol(self, db_session, seed_trades):
        """Filtering by symbol should return only matching trades."""
        seed_trades(count=9, exec_prefix="SVC")
        svc = TradeService()
        result = svc.list_trades(db_session, symbol="AAPL")
        for trade in result.trades:
            assert trade.symbol == "AAPL"

    def test_list_trades_filter_broker(self, db_session, seed_trades):
        """Filtering by broker should return only matching trades."""
        seed_trades(count=5, exec_prefix="SVC")
        svc = TradeService()
        result = svc.list_trades(db_session, broker="ibkr")
        assert result.total == 5

    def test_list_trades_sort_asc(self, db_session, seed_trades):
        """Sorting ascending by executed_at should return oldest first."""
        seed_trades(count=5, exec_prefix="SVC")
        svc = TradeService()
        result = svc.list_trades(db_session, sort="executed_at", order="asc")
        if len(result.trades) >= 2:
            assert result.trades[0].executed_at <= result.trades[1].executed_at


class TestTradeServiceGetTrade:
    """Test TradeService.get_trade."""

    def test_get_existing_trade(self, db_session, seed_trades):
        """Should return the trade when it exists."""
        trades = seed_trades(count=1, exec_prefix="SVC")
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

    def test_summary_with_trades(self, db_session, seed_trades):
        """Summary should return correct aggregates."""
        seed_trades(count=5, exec_prefix="SVC")
        svc = TradeService()
        result = svc.get_summary(db_session)
        assert result.total_trades == 5
        assert result.total_commissions > 0

    def test_summary_empty_db(self, db_session):
        """Summary with no trades should return zero totals."""
        svc = TradeService()
        result = svc.get_summary(db_session)
        assert result.total_trades == 0

    def test_summary_filter_symbol(self, db_session, seed_trades):
        """Summary filtered by symbol should only count matching trades."""
        seed_trades(count=9, exec_prefix="SVC")
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
    """Test AnalyticsService.execute for daily view."""

    def test_daily_summaries_empty(self, db_session):
        """Empty DB should return empty list."""
        svc = AnalyticsService()
        views = get_views()
        result = svc.execute(views["daily"], db_session)
        assert result == []

    def test_daily_summaries_with_data(self, db_session, seed_trades):
        """Should return summaries when trades exist."""
        seed_trades(count=5, exec_prefix="SVC")
        svc = AnalyticsService()
        views = get_views()
        result = svc.execute(views["daily"], db_session)
        assert len(result) > 0


class TestAnalyticsServiceCalendar:
    """Test AnalyticsService.execute for calendar view."""

    def test_calendar_empty(self, db_session):
        """Empty month should return empty list."""
        svc = AnalyticsService()
        views = get_views()
        result = svc.execute(views["calendar"], db_session, year=2024, month=6)
        assert result == []


class TestAnalyticsServiceBySymbol:
    """Test AnalyticsService.execute for by-symbol view."""

    def test_by_symbol_with_groups(self, db_session, seed_trades, seed_trade_groups):
        """Should return per-symbol breakdown when groups exist."""
        seed_trades(count=5, exec_prefix="SVC")
        seed_trade_groups()
        svc = AnalyticsService()
        views = get_views()
        result = svc.execute(views["by-symbol"], db_session)
        assert len(result) > 0


class TestAnalyticsServicePerformance:
    """Test AnalyticsService.execute for performance view."""

    def test_performance_with_data(self, db_session, seed_trades, seed_trade_groups):
        """Should return performance metrics when data exists."""
        seed_trades(count=5, exec_prefix="SVC")
        seed_trade_groups()
        svc = AnalyticsService()
        views = get_views()
        result = svc.execute(views["performance"], db_session)
        assert result.total_trades >= 0
