"""
Tests for the chart endpoint: GET /api/v1/groups/{group_id}/chart.

Tests:
- Auth required (401)
- Group not found (404)
- Successful chart data response with mocked market data
- Marker generation for long/short groups
- Custom interval and padding params
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

from backend.models.trade import Trade
from backend.models.trade_group import TradeGroup, TradeGroupLeg
from backend.services.market_data import OHLCVBar


# Use recent dates so choose_interval age-based promotion doesn't interfere
_BASE_TIME = datetime.now(timezone.utc) - timedelta(hours=3)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_closed_long_group(db_session) -> uuid.UUID:
    """Seed a closed long group with entry and exit trades. Return group id."""
    opened_at = _BASE_TIME
    closed_at = _BASE_TIME + timedelta(hours=1, minutes=20)

    entry_trade = Trade(
        id=uuid.uuid4(),
        broker="ibkr",
        broker_exec_id=f"CHART-ENTRY-{uuid.uuid4().hex[:8]}",
        account_id="U1234567",
        symbol="AAPL",
        asset_class="stock",
        side="buy",
        quantity=Decimal("100"),
        price=Decimal("182.55"),
        commission=Decimal("1.00"),
        executed_at=opened_at,
        currency="USD",
        raw_data={},
    )
    exit_trade = Trade(
        id=uuid.uuid4(),
        broker="ibkr",
        broker_exec_id=f"CHART-EXIT-{uuid.uuid4().hex[:8]}",
        account_id="U1234567",
        symbol="AAPL",
        asset_class="stock",
        side="sell",
        quantity=Decimal("100"),
        price=Decimal("183.10"),
        commission=Decimal("1.00"),
        executed_at=closed_at,
        currency="USD",
        raw_data={},
    )
    db_session.add_all([entry_trade, exit_trade])
    db_session.flush()

    group = TradeGroup(
        id=uuid.uuid4(),
        account_id="U1234567",
        symbol="AAPL",
        asset_class="stock",
        direction="long",
        status="closed",
        realized_pnl=Decimal("55.00"),
        opened_at=opened_at,
        closed_at=closed_at,
    )
    db_session.add(group)
    db_session.flush()

    entry_leg = TradeGroupLeg(
        id=uuid.uuid4(),
        trade_group_id=group.id,
        trade_id=entry_trade.id,
        role="entry",
    )
    exit_leg = TradeGroupLeg(
        id=uuid.uuid4(),
        trade_group_id=group.id,
        trade_id=exit_trade.id,
        role="exit",
    )
    db_session.add_all([entry_leg, exit_leg])
    db_session.flush()

    return group.id


def _seed_closed_short_group(db_session) -> uuid.UUID:
    """Seed a closed short group with entry (sell) and exit (buy) trades."""
    opened_at = _BASE_TIME
    closed_at = _BASE_TIME + timedelta(hours=4)

    entry_trade = Trade(
        id=uuid.uuid4(),
        broker="ibkr",
        broker_exec_id=f"CHART-SHORT-ENTRY-{uuid.uuid4().hex[:8]}",
        account_id="U1234567",
        symbol="TSLA",
        asset_class="stock",
        side="sell",
        quantity=Decimal("50"),
        price=Decimal("200.00"),
        commission=Decimal("1.00"),
        executed_at=opened_at,
        currency="USD",
        raw_data={},
    )
    exit_trade = Trade(
        id=uuid.uuid4(),
        broker="ibkr",
        broker_exec_id=f"CHART-SHORT-EXIT-{uuid.uuid4().hex[:8]}",
        account_id="U1234567",
        symbol="TSLA",
        asset_class="stock",
        side="buy",
        quantity=Decimal("50"),
        price=Decimal("190.00"),
        commission=Decimal("1.00"),
        executed_at=closed_at,
        currency="USD",
        raw_data={},
    )
    db_session.add_all([entry_trade, exit_trade])
    db_session.flush()

    group = TradeGroup(
        id=uuid.uuid4(),
        account_id="U1234567",
        symbol="TSLA",
        asset_class="stock",
        direction="short",
        status="closed",
        realized_pnl=Decimal("500.00"),
        opened_at=opened_at,
        closed_at=closed_at,
    )
    db_session.add(group)
    db_session.flush()

    entry_leg = TradeGroupLeg(
        id=uuid.uuid4(),
        trade_group_id=group.id,
        trade_id=entry_trade.id,
        role="entry",
    )
    exit_leg = TradeGroupLeg(
        id=uuid.uuid4(),
        trade_group_id=group.id,
        trade_id=exit_trade.id,
        role="exit",
    )
    db_session.add_all([entry_leg, exit_leg])
    db_session.flush()

    return group.id


def _mock_candles() -> list[OHLCVBar]:
    """Return a small list of mock OHLCV bars."""
    return [
        OHLCVBar(
            time=1736931600,
            open=Decimal("182.50"),
            high=Decimal("183.20"),
            low=Decimal("182.30"),
            close=Decimal("183.00"),
            volume=12345,
        ),
        OHLCVBar(
            time=1736931900,
            open=Decimal("183.00"),
            high=Decimal("183.50"),
            low=Decimal("182.80"),
            close=Decimal("183.40"),
            volume=23456,
        ),
    ]


def _patch_yfinance_provider():
    """Return a combined patch context manager that mocks the cache and provider.

    The endpoint now uses OHLCVCacheService + _get_provider instead of
    YFinanceProvider directly. We mock the cache to return None (cache miss)
    and the provider to return ``_mock_candles()``.
    """
    mock_provider_instance = MagicMock()
    mock_provider_instance.fetch_ohlcv.return_value = _mock_candles()
    mock_provider_instance.__class__.__name__ = "TiingoProvider"

    class _PatchContext:
        def __enter__(self):
            self._cache_patcher = patch("backend.api.groups.OHLCVCacheService")
            self._provider_patcher = patch("backend.api.groups._get_provider")
            mock_cache_cls = self._cache_patcher.start()
            mock_get_provider = self._provider_patcher.start()
            mock_cache_instance = MagicMock()
            mock_cache_instance.get.return_value = None  # cache miss
            mock_cache_cls.return_value = mock_cache_instance
            mock_get_provider.return_value = mock_provider_instance
            return self

        def __exit__(self, *args):
            self._provider_patcher.stop()
            self._cache_patcher.stop()

    return _PatchContext()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGroupChartAuth:
    """Test authentication requirements for the chart endpoint."""

    def test_chart_endpoint_requires_auth(self, client, db_session):
        """Request without auth header should return 401."""
        group_id = _seed_closed_long_group(db_session)
        resp = client.get(f"/api/v1/groups/{group_id}/chart")
        assert resp.status_code == 401


class TestGroupChartNotFound:
    """Test 404 handling for non-existent groups."""

    def test_chart_endpoint_group_not_found(self, client, auth_headers):
        """Request with non-existent group_id should return 404."""
        fake_id = uuid.uuid4()
        resp = client.get(f"/api/v1/groups/{fake_id}/chart", headers=auth_headers)
        assert resp.status_code == 404


class TestGroupChartSuccess:
    """Test successful chart data retrieval."""

    def test_chart_endpoint_returns_data(self, client, auth_headers, db_session):
        """Seeded closed group with mocked market data should return full chart response."""
        group_id = _seed_closed_long_group(db_session)

        with _patch_yfinance_provider():
            resp = client.get(
                f"/api/v1/groups/{group_id}/chart", headers=auth_headers
            )

        assert resp.status_code == 200
        data = resp.json()

        # Verify top-level structure
        assert "symbol" in data
        assert "interval" in data
        assert "candles" in data
        assert "markers" in data
        assert "group" in data

        # Verify candles
        assert len(data["candles"]) == 2
        candle = data["candles"][0]
        assert "time" in candle
        assert "open" in candle
        assert "high" in candle
        assert "low" in candle
        assert "close" in candle
        assert "volume" in candle

        # Verify group info
        assert data["group"]["direction"] == "long"
        assert data["symbol"] == "AAPL"

    def test_chart_markers_long_direction(self, client, auth_headers, db_session):
        """Long group should have entry (belowBar/arrowUp) and exit (aboveBar/arrowDown) markers."""
        group_id = _seed_closed_long_group(db_session)

        with _patch_yfinance_provider():
            resp = client.get(
                f"/api/v1/groups/{group_id}/chart", headers=auth_headers
            )

        assert resp.status_code == 200
        markers = resp.json()["markers"]
        assert len(markers) == 2

        entry_marker = next(m for m in markers if m["role"] == "entry")
        exit_marker = next(m for m in markers if m["role"] == "exit")

        assert entry_marker["position"] == "belowBar"
        assert entry_marker["shape"] == "arrowUp"
        assert exit_marker["position"] == "aboveBar"
        assert exit_marker["shape"] == "arrowDown"

    def test_chart_markers_short_direction(self, client, auth_headers, db_session):
        """Short group should have reversed marker positions."""
        group_id = _seed_closed_short_group(db_session)

        with _patch_yfinance_provider():
            resp = client.get(
                f"/api/v1/groups/{group_id}/chart", headers=auth_headers
            )

        assert resp.status_code == 200
        markers = resp.json()["markers"]
        assert len(markers) == 2

        entry_marker = next(m for m in markers if m["role"] == "entry")
        exit_marker = next(m for m in markers if m["role"] == "exit")

        # Short: entry (sell) -> belowBar/arrowDown, exit (buy) -> aboveBar/arrowUp
        assert entry_marker["position"] == "belowBar"
        assert entry_marker["shape"] == "arrowDown"
        assert exit_marker["position"] == "aboveBar"
        assert exit_marker["shape"] == "arrowUp"


class TestGroupChartParams:
    """Test custom interval and padding query parameters."""

    def test_chart_with_custom_interval(self, client, auth_headers, db_session):
        """Explicit interval param should be used instead of auto-detection."""
        group_id = _seed_closed_long_group(db_session)

        with _patch_yfinance_provider():
            resp = client.get(
                f"/api/v1/groups/{group_id}/chart?interval=15m",
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["interval"] == "15m"

    def test_chart_with_custom_padding(self, client, auth_headers, db_session):
        """Custom padding param should be accepted without error."""
        group_id = _seed_closed_long_group(db_session)

        with _patch_yfinance_provider():
            resp = client.get(
                f"/api/v1/groups/{group_id}/chart?padding=50",
                headers=auth_headers,
            )

        assert resp.status_code == 200

    def test_chart_auto_interval_selection(self, client, auth_headers, db_session):
        """Without explicit interval, stock groups should auto-select '1d'."""
        group_id = _seed_closed_long_group(db_session)

        with _patch_yfinance_provider():
            resp = client.get(
                f"/api/v1/groups/{group_id}/chart", headers=auth_headers
            )

        assert resp.status_code == 200
        data = resp.json()
        # Stock asset_class -> default interval "1d"
        assert data["interval"] == "1d"
