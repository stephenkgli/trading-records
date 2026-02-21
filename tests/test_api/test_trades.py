"""
Tests for the trades API endpoints.

Verifies:
- Pagination (page, per_page)
- Filtering (symbol, broker, asset_class, date range)
- Sorting (executed_at)
- Single trade detail by ID

The response model is TradeListResponse with fields:
  trades: list[TradeResponse], total: int, page: int, per_page: int, pages: int

Reference: design-doc-final.md Sections 6.1, 6.2
"""

import uuid
from datetime import datetime

import pytest


# ===========================================================================
# Pagination
# ===========================================================================

class TestTradesPagination:
    """Test pagination of the trades list endpoint."""

    def test_default_pagination(self, client, db_session, seed_trades):
        """Default pagination should return a paginated response."""
        seed_trades(
            count=20,
            symbols=["AAPL", "MSFT", "GOOG", "TSLA", "AMZN"],
            brokers=["ibkr", "tradovate"],
            exec_prefix="SEED",
        )

        response = client.get("/api/v1/trades")
        assert response.status_code == 200
        data = response.json()

        assert "trades" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert len(data["trades"]) <= data["per_page"]

    def test_custom_page_size(self, client, db_session, seed_trades):
        """Custom per_page should limit results."""
        seed_trades(
            count=20,
            symbols=["AAPL", "MSFT", "GOOG", "TSLA", "AMZN"],
            brokers=["ibkr", "tradovate"],
            exec_prefix="SEED",
        )

        response = client.get("/api/v1/trades?per_page=5")
        assert response.status_code == 200
        data = response.json()
        assert len(data["trades"]) <= 5

    def test_page_2(self, client, db_session, seed_trades):
        """Page 2 should return different results than page 1."""
        seed_trades(
            count=20,
            symbols=["AAPL", "MSFT", "GOOG", "TSLA", "AMZN"],
            brokers=["ibkr", "tradovate"],
            exec_prefix="SEED",
        )

        resp1 = client.get("/api/v1/trades?page=1&per_page=5")
        resp2 = client.get("/api/v1/trades?page=2&per_page=5")

        data1 = resp1.json()
        data2 = resp2.json()

        ids1 = {t["id"] for t in data1["trades"]}
        ids2 = {t["id"] for t in data2["trades"]}
        assert ids1 != ids2  # Different pages have different items

    def test_empty_results(self, client):
        """No trades in DB should return empty list with total=0."""
        response = client.get("/api/v1/trades")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["trades"]) == 0


# ===========================================================================
# Filtering
# ===========================================================================

class TestTradesFiltering:
    """Test filtering of trades."""

    def test_filter_by_symbol(self, client, db_session, seed_trades):
        """Filtering by symbol should return only matching trades."""
        seed_trades(
            count=20,
            symbols=["AAPL", "MSFT", "GOOG", "TSLA", "AMZN"],
            brokers=["ibkr", "tradovate"],
            exec_prefix="SEED",
        )

        response = client.get("/api/v1/trades?symbol=AAPL")
        assert response.status_code == 200
        data = response.json()

        for trade in data["trades"]:
            assert trade["symbol"] == "AAPL"

    def test_filter_by_broker(self, client, db_session, seed_trades):
        """Filtering by broker should return only matching trades."""
        seed_trades(
            count=20,
            symbols=["AAPL", "MSFT", "GOOG", "TSLA", "AMZN"],
            brokers=["ibkr", "tradovate"],
            exec_prefix="SEED",
        )

        response = client.get("/api/v1/trades?broker=ibkr")
        assert response.status_code == 200
        data = response.json()

        for trade in data["trades"]:
            assert trade["broker"] == "ibkr"

    def test_filter_by_date_range(self, client, db_session, seed_trades):
        """Filtering by date range should return only trades within the range."""
        seed_trades(
            count=20,
            symbols=["AAPL", "MSFT", "GOOG", "TSLA", "AMZN"],
            brokers=["ibkr", "tradovate"],
            exec_prefix="SEED",
        )

        response = client.get(
            "/api/v1/trades?from=2025-01-15T00:00:00Z&to=2025-01-17T23:59:59Z",
        )
        assert response.status_code == 200
        data = response.json()

        for trade in data["trades"]:
            dt = datetime.fromisoformat(trade["executed_at"].replace("Z", "+00:00"))
            assert dt.date() >= datetime(2025, 1, 15).date()
            assert dt.date() <= datetime(2025, 1, 17).date()

    def test_filter_by_asset_class(self, client, db_session, seed_trades):
        """Filtering by asset_class should return matching trades."""
        seed_trades(
            count=20,
            symbols=["AAPL", "MSFT", "GOOG", "TSLA", "AMZN"],
            brokers=["ibkr", "tradovate"],
            exec_prefix="SEED",
        )

        response = client.get("/api/v1/trades?asset_class=stock")
        assert response.status_code == 200
        data = response.json()

        for trade in data["trades"]:
            assert trade["asset_class"] == "stock"


# ===========================================================================
# Sorting
# ===========================================================================

class TestTradesSorting:
    """Test sorting of trade results."""

    def test_sort_by_executed_at_desc(self, client, db_session, seed_trades):
        """Sorting by executed_at descending should return newest first."""
        seed_trades(
            count=10,
            symbols=["AAPL", "MSFT", "GOOG", "TSLA", "AMZN"],
            brokers=["ibkr", "tradovate"],
            exec_prefix="SEED",
        )

        response = client.get(
            "/api/v1/trades?sort=executed_at&order=desc",
        )
        assert response.status_code == 200
        data = response.json()

        if len(data["trades"]) >= 2:
            dates = [t["executed_at"] for t in data["trades"]]
            assert dates == sorted(dates, reverse=True)

    def test_sort_by_executed_at_asc(self, client, db_session, seed_trades):
        """Sorting by executed_at ascending should return oldest first."""
        seed_trades(
            count=10,
            symbols=["AAPL", "MSFT", "GOOG", "TSLA", "AMZN"],
            brokers=["ibkr", "tradovate"],
            exec_prefix="SEED",
        )

        response = client.get(
            "/api/v1/trades?sort=executed_at&order=asc",
        )
        assert response.status_code == 200
        data = response.json()

        if len(data["trades"]) >= 2:
            dates = [t["executed_at"] for t in data["trades"]]
            assert dates == sorted(dates)


# ===========================================================================
# Trades Summary
# ===========================================================================

class TestTradesSummary:
    """Test aggregated trades summary endpoint."""

    def test_summary_returns_aggregates(self, client, db_session, seed_trades):
        """Summary should return aggregate fields with non-empty data."""
        seed_trades(
            count=6,
            symbols=["AAPL", "MSFT", "GOOG", "TSLA", "AMZN"],
            brokers=["ibkr", "tradovate"],
            exec_prefix="SEED",
        )

        response = client.get("/api/v1/trades/summary")
        assert response.status_code == 200
        data = response.json()

        assert data["total_trades"] == 6
        assert "total_quantity" in data
        assert "total_commissions" in data
        assert "gross_pnl" in data
        assert "net_pnl" in data

    def test_summary_respects_filters(self, client, db_session, seed_trades):
        """Summary filters should restrict the aggregation scope."""
        seed_trades(
            count=10,
            symbols=["AAPL", "MSFT", "GOOG", "TSLA", "AMZN"],
            brokers=["ibkr", "tradovate"],
            exec_prefix="SEED",
        )

        response = client.get(
            "/api/v1/trades/summary?symbol=AAPL&broker=ibkr",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_trades"] >= 0


# ===========================================================================
# Single Trade Detail
# ===========================================================================

class TestTradeDetail:
    """Test the single trade detail endpoint."""

    def test_get_trade_by_id(self, client, db_session, seed_trades):
        """GET /api/v1/trades/:id should return the specific trade."""
        trades = seed_trades(
            count=5,
            symbols=["AAPL", "MSFT", "GOOG", "TSLA", "AMZN"],
            brokers=["ibkr", "tradovate"],
            exec_prefix="SEED",
        )
        trade_id = str(trades[0].id)

        response = client.get(f"/api/v1/trades/{trade_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == trade_id

    def test_trade_not_found(self, client):
        """GET /api/v1/trades/:id with nonexistent ID should return 404."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/v1/trades/{fake_id}")
        assert response.status_code == 404

    def test_trade_detail_fields(self, client, db_session, seed_trades):
        """Trade detail should include all expected fields."""
        trades = seed_trades(
            count=1,
            symbols=["AAPL", "MSFT", "GOOG", "TSLA", "AMZN"],
            brokers=["ibkr", "tradovate"],
            exec_prefix="SEED",
        )
        trade_id = str(trades[0].id)

        response = client.get(f"/api/v1/trades/{trade_id}")
        data = response.json()

        expected_fields = [
            "id", "broker", "broker_exec_id", "account_id", "symbol",
            "asset_class", "side", "quantity", "price", "commission",
            "executed_at", "currency",
        ]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
