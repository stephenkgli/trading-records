"""Tests for the chart endpoint with new market data providers."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from backend.models.trade import Trade
from backend.models.trade_group import TradeGroup, TradeGroupLeg
from backend.services.market_data import OHLCVBar
from backend.services.providers.errors import ProviderError
from backend.services.providers.rate_limit import RateLimitError


def _seed_group_with_legs(db_session):
    """Create a trade group with legs and trades for chart testing."""
    trade_id = uuid.uuid4()
    group_id = uuid.uuid4()

    trade = Trade(
        id=trade_id,
        broker="ibkr",
        broker_exec_id="CHART0001",
        account_id="U1234567",
        symbol="AAPL",
        asset_class="stock",
        side="buy",
        quantity=Decimal("100"),
        price=Decimal("150.00"),
        commission=Decimal("1.00"),
        executed_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        currency="USD",
        raw_data={},
    )
    db_session.add(trade)

    group = TradeGroup(
        id=group_id,
        account_id="U1234567",
        symbol="AAPL",
        asset_class="stock",
        direction="long",
        status="closed",
        realized_pnl=Decimal("500.00"),
        opened_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        closed_at=datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc),
    )
    db_session.add(group)

    leg = TradeGroupLeg(
        id=uuid.uuid4(),
        trade_group_id=group_id,
        trade_id=trade_id,
        role="entry",
    )
    db_session.add(leg)
    db_session.flush()

    return group_id


def _make_bars(count: int = 5) -> list[OHLCVBar]:
    """Create a list of mock OHLCVBar objects."""
    bars = []
    for i in range(count):
        bars.append(
            OHLCVBar(
                time=int(
                    datetime(2025, 1, 15, 10 + i, 0, 0, tzinfo=timezone.utc).timestamp()
                ),
                open=Decimal("100.00") + i,
                high=Decimal("110.00") + i,
                low=Decimal("90.00") + i,
                close=Decimal("105.00") + i,
                volume=1000 + i * 100,
            )
        )
    return bars


class TestChartEndpoint:
    """Integration tests for the chart endpoint."""

    def test_cache_hit_skips_provider(self, client, auth_headers, db_session):
        """When cache has data, provider should not be called."""
        group_id = _seed_group_with_legs(db_session)

        mock_bars = _make_bars()

        with patch(
            "backend.api.groups.OHLCVCacheService"
        ) as MockCacheService:
            mock_cache_instance = MagicMock()
            mock_cache_instance.get.return_value = mock_bars
            MockCacheService.return_value = mock_cache_instance

            with patch("backend.api.groups._get_provider") as mock_get_provider:
                response = client.get(
                    f"/api/v1/groups/{group_id}/chart?interval=1d",
                    headers=auth_headers,
                )

                assert response.status_code == 200
                data = response.json()
                assert len(data["candles"]) == 5
                # Provider should NOT have been called
                mock_get_provider.assert_not_called()

    def test_cache_miss_fetches_and_caches(self, client, auth_headers, db_session):
        """When cache misses, provider is called and result is cached."""
        group_id = _seed_group_with_legs(db_session)

        mock_bars = _make_bars()

        with patch(
            "backend.api.groups.OHLCVCacheService"
        ) as MockCacheService:
            mock_cache_instance = MagicMock()
            mock_cache_instance.get.return_value = None  # cache miss
            MockCacheService.return_value = mock_cache_instance

            with patch("backend.api.groups._get_provider") as mock_get_provider:
                mock_provider = MagicMock()
                mock_provider.fetch_ohlcv.return_value = mock_bars
                mock_provider.__class__.__name__ = "TiingoProvider"
                mock_get_provider.return_value = mock_provider

                response = client.get(
                    f"/api/v1/groups/{group_id}/chart?interval=1d",
                    headers=auth_headers,
                )

                assert response.status_code == 200
                data = response.json()
                assert len(data["candles"]) == 5

                # Provider should have been called
                mock_provider.fetch_ohlcv.assert_called_once()
                # Cache should have been populated
                mock_cache_instance.put.assert_called_once()

    def test_provider_error_returns_502(self, client, auth_headers, db_session):
        """ProviderError should result in HTTP 502."""
        group_id = _seed_group_with_legs(db_session)

        with patch(
            "backend.api.groups.OHLCVCacheService"
        ) as MockCacheService:
            mock_cache_instance = MagicMock()
            mock_cache_instance.get.return_value = None
            MockCacheService.return_value = mock_cache_instance

            with patch("backend.api.groups._get_provider") as mock_get_provider:
                mock_provider = MagicMock()
                mock_provider.fetch_ohlcv.side_effect = ProviderError("API down")
                mock_get_provider.return_value = mock_provider

                response = client.get(
                    f"/api/v1/groups/{group_id}/chart?interval=1d",
                    headers=auth_headers,
                )

                assert response.status_code == 502
                assert "API down" in response.json()["detail"]

    def test_rate_limit_returns_429(self, client, auth_headers, db_session):
        """RateLimitError should result in HTTP 429."""
        group_id = _seed_group_with_legs(db_session)

        with patch(
            "backend.api.groups.OHLCVCacheService"
        ) as MockCacheService:
            mock_cache_instance = MagicMock()
            mock_cache_instance.get.return_value = None
            MockCacheService.return_value = mock_cache_instance

            with patch("backend.api.groups._get_provider") as mock_get_provider:
                mock_provider = MagicMock()
                mock_provider.fetch_ohlcv.side_effect = RateLimitError(
                    "tiingo daily limit (400) exceeded"
                )
                mock_get_provider.return_value = mock_provider

                response = client.get(
                    f"/api/v1/groups/{group_id}/chart?interval=1d",
                    headers=auth_headers,
                )

                assert response.status_code == 429
                assert "rate limit" in response.json()["detail"].lower()

    def test_no_bars_returns_404(self, client, auth_headers, db_session):
        """When provider returns no bars, should get 200 with empty candles."""
        group_id = _seed_group_with_legs(db_session)

        with patch(
            "backend.api.groups.OHLCVCacheService"
        ) as MockCacheService:
            mock_cache_instance = MagicMock()
            mock_cache_instance.get.return_value = None
            MockCacheService.return_value = mock_cache_instance

            with patch("backend.api.groups._get_provider") as mock_get_provider:
                mock_provider = MagicMock()
                mock_provider.fetch_ohlcv.return_value = []
                mock_get_provider.return_value = mock_provider

                response = client.get(
                    f"/api/v1/groups/{group_id}/chart?interval=1d",
                    headers=auth_headers,
                )

                assert response.status_code == 200
                data = response.json()
                assert data["candles"] == []
                assert len(data["markers"]) > 0

    def test_nonexistent_group_returns_404(self, client, auth_headers):
        """Request for a non-existent group should return 404."""
        fake_id = uuid.uuid4()
        response = client.get(
            f"/api/v1/groups/{fake_id}/chart",
            headers=auth_headers,
        )
        assert response.status_code == 404
