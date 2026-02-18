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
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from backend.models.trade import Trade


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_trades(db_session, count=20):
    """Insert test trades into the database and return them."""
    trades = []
    symbols = ["AAPL", "MSFT", "GOOG", "TSLA", "AMZN"]
    brokers = ["ibkr", "tradovate"]

    for i in range(count):
        trade = Trade(
            id=uuid.uuid4(),
            broker=brokers[i % 2],
            broker_exec_id=f"SEED{i:04d}",
            account_id="U1234567",
            symbol=symbols[i % len(symbols)],
            asset_class="stock",
            side="buy" if i % 2 == 0 else "sell",
            quantity=Decimal("100"),
            price=Decimal(f"{150 + i}.00"),
            commission=Decimal("1.00"),
            executed_at=datetime(2025, 1, 15 + (i % 15), 10, i % 60, 0, tzinfo=timezone.utc),
            currency="USD",
            raw_data={"seed": i},
        )
        trades.append(trade)
        db_session.add(trade)

    db_session.flush()
    return trades


# ===========================================================================
# Pagination
# ===========================================================================

class TestTradesPagination:
    """Test pagination of the trades list endpoint."""

    def test_default_pagination(self, client, auth_headers, db_session):
        """Default pagination should return a paginated response."""
        _seed_trades(db_session, 20)

        response = client.get("/api/v1/trades", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        assert "trades" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert len(data["trades"]) <= data["per_page"]

    def test_custom_page_size(self, client, auth_headers, db_session):
        """Custom per_page should limit results."""
        _seed_trades(db_session, 20)

        response = client.get("/api/v1/trades?per_page=5", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["trades"]) <= 5

    def test_page_2(self, client, auth_headers, db_session):
        """Page 2 should return different results than page 1."""
        _seed_trades(db_session, 20)

        resp1 = client.get("/api/v1/trades?page=1&per_page=5", headers=auth_headers)
        resp2 = client.get("/api/v1/trades?page=2&per_page=5", headers=auth_headers)

        data1 = resp1.json()
        data2 = resp2.json()

        ids1 = {t["id"] for t in data1["trades"]}
        ids2 = {t["id"] for t in data2["trades"]}
        assert ids1 != ids2  # Different pages have different items

    def test_empty_results(self, client, auth_headers):
        """No trades in DB should return empty list with total=0."""
        response = client.get("/api/v1/trades", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["trades"]) == 0


# ===========================================================================
# Filtering
# ===========================================================================

class TestTradesFiltering:
    """Test filtering of trades."""

    def test_filter_by_symbol(self, client, auth_headers, db_session):
        """Filtering by symbol should return only matching trades."""
        _seed_trades(db_session, 20)

        response = client.get("/api/v1/trades?symbol=AAPL", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        for trade in data["trades"]:
            assert trade["symbol"] == "AAPL"

    def test_filter_by_broker(self, client, auth_headers, db_session):
        """Filtering by broker should return only matching trades."""
        _seed_trades(db_session, 20)

        response = client.get("/api/v1/trades?broker=ibkr", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        for trade in data["trades"]:
            assert trade["broker"] == "ibkr"

    def test_filter_by_date_range(self, client, auth_headers, db_session):
        """Filtering by date range should return only trades within the range."""
        _seed_trades(db_session, 20)

        response = client.get(
            "/api/v1/trades?from=2025-01-15T00:00:00Z&to=2025-01-17T23:59:59Z",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()

        for trade in data["trades"]:
            dt = datetime.fromisoformat(trade["executed_at"].replace("Z", "+00:00"))
            assert dt.date() >= datetime(2025, 1, 15).date()
            assert dt.date() <= datetime(2025, 1, 17).date()

    def test_filter_by_asset_class(self, client, auth_headers, db_session):
        """Filtering by asset_class should return matching trades."""
        _seed_trades(db_session, 20)

        response = client.get("/api/v1/trades?asset_class=stock", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        for trade in data["trades"]:
            assert trade["asset_class"] == "stock"


# ===========================================================================
# Sorting
# ===========================================================================

class TestTradesSorting:
    """Test sorting of trade results."""

    def test_sort_by_executed_at_desc(self, client, auth_headers, db_session):
        """Sorting by executed_at descending should return newest first."""
        _seed_trades(db_session, 10)

        response = client.get(
            "/api/v1/trades?sort=executed_at&order=desc",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()

        if len(data["trades"]) >= 2:
            dates = [t["executed_at"] for t in data["trades"]]
            assert dates == sorted(dates, reverse=True)

    def test_sort_by_executed_at_asc(self, client, auth_headers, db_session):
        """Sorting by executed_at ascending should return oldest first."""
        _seed_trades(db_session, 10)

        response = client.get(
            "/api/v1/trades?sort=executed_at&order=asc",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()

        if len(data["trades"]) >= 2:
            dates = [t["executed_at"] for t in data["trades"]]
            assert dates == sorted(dates)


# ===========================================================================
# Single Trade Detail
# ===========================================================================

class TestTradeDetail:
    """Test the single trade detail endpoint."""

    def test_get_trade_by_id(self, client, auth_headers, db_session):
        """GET /api/v1/trades/:id should return the specific trade."""
        trades = _seed_trades(db_session, 5)
        trade_id = str(trades[0].id)

        response = client.get(f"/api/v1/trades/{trade_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == trade_id

    def test_trade_not_found(self, client, auth_headers):
        """GET /api/v1/trades/:id with nonexistent ID should return 404."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/v1/trades/{fake_id}", headers=auth_headers)
        assert response.status_code == 404

    def test_trade_detail_fields(self, client, auth_headers, db_session):
        """Trade detail should include all expected fields."""
        trades = _seed_trades(db_session, 1)
        trade_id = str(trades[0].id)

        response = client.get(f"/api/v1/trades/{trade_id}", headers=auth_headers)
        data = response.json()

        expected_fields = [
            "id", "broker", "broker_exec_id", "account_id", "symbol",
            "asset_class", "side", "quantity", "price", "commission",
            "executed_at", "currency",
        ]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
