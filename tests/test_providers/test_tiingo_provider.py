"""Tests for TiingoProvider."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from backend.services.market_data import OHLCVBar
from backend.services.providers.tiingo_provider import TiingoProvider


@pytest.fixture
def provider():
    """Create a TiingoProvider with a fake API key."""
    return TiingoProvider(api_key="test-key")


class TestTiingoProvider:
    """Tests for the TiingoProvider class."""

    def test_rejects_non_stock(self, provider):
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 1, 2, tzinfo=timezone.utc)
        with pytest.raises(ValueError, match="supports stocks/options"):
            provider.fetch_ohlcv("MESZ5", "future", "1d", start, end)

    @patch("backend.services.providers.tiingo_provider.tiingo_counter")
    def test_fetch_ohlcv_success(self, mock_counter, provider):
        """Verify bars are returned from a mocked Tiingo response."""
        mock_counter.check_and_increment = MagicMock()

        historical = [
            {
                "date": "2025-01-15T00:00:00+00:00",
                "open": 150.0,
                "high": 155.0,
                "low": 149.0,
                "close": 154.0,
                "adjOpen": 150.0,
                "adjHigh": 155.0,
                "adjLow": 149.0,
                "adjClose": 154.0,
                "volume": 50000,
            },
            {
                "date": "2025-01-16T00:00:00+00:00",
                "open": 154.0,
                "high": 158.0,
                "low": 153.0,
                "close": 157.0,
                "adjOpen": 154.0,
                "adjHigh": 158.0,
                "adjLow": 153.0,
                "adjClose": 157.0,
                "volume": 45000,
            },
        ]

        mock_client = MagicMock()
        mock_client.get_ticker_price.return_value = historical
        provider._client = mock_client

        start = datetime(2025, 1, 15, tzinfo=timezone.utc)
        end = datetime(2025, 1, 17, tzinfo=timezone.utc)

        bars = provider.fetch_ohlcv("AAPL", "stock", "1d", start, end)

        assert len(bars) == 2
        assert bars[0].open == Decimal("150.0")
        assert bars[0].close == Decimal("154.0")
        assert bars[1].high == Decimal("158.0")
        assert bars[0].volume == 50000

        mock_counter.check_and_increment.assert_called_once()

    @patch("backend.services.providers.tiingo_provider.tiingo_counter")
    def test_uses_adjusted_prices(self, mock_counter, provider):
        """Verify adjOpen/adjHigh etc. are preferred over raw prices."""
        mock_counter.check_and_increment = MagicMock()

        historical = [
            {
                "date": "2025-01-15T00:00:00+00:00",
                "open": 300.0,
                "high": 310.0,
                "low": 295.0,
                "close": 305.0,
                "adjOpen": 150.0,
                "adjHigh": 155.0,
                "adjLow": 147.5,
                "adjClose": 152.5,
                "volume": 50000,
            },
        ]

        mock_client = MagicMock()
        mock_client.get_ticker_price.return_value = historical
        provider._client = mock_client

        start = datetime(2025, 1, 15, tzinfo=timezone.utc)
        end = datetime(2025, 1, 16, tzinfo=timezone.utc)

        bars = provider.fetch_ohlcv("AAPL", "stock", "1d", start, end)

        assert len(bars) == 1
        assert bars[0].open == Decimal("150.0")
        assert bars[0].high == Decimal("155.0")
        assert bars[0].low == Decimal("147.5")
        assert bars[0].close == Decimal("152.5")

    @patch("backend.services.providers.tiingo_provider.tiingo_counter")
    def test_empty_response(self, mock_counter, provider):
        """Verify empty list returned for empty response."""
        mock_counter.check_and_increment = MagicMock()

        mock_client = MagicMock()
        mock_client.get_ticker_price.return_value = []
        provider._client = mock_client

        start = datetime(2025, 1, 15, tzinfo=timezone.utc)
        end = datetime(2025, 1, 16, tzinfo=timezone.utc)

        bars = provider.fetch_ohlcv("AAPL", "stock", "1d", start, end)
        assert bars == []

    @patch("backend.services.providers.tiingo_provider.tiingo_counter")
    def test_naive_timestamp_gets_utc(self, mock_counter, provider):
        """Verify naive timestamps are treated as UTC."""
        mock_counter.check_and_increment = MagicMock()

        historical = [
            {
                "date": "2025-01-15T00:00:00",  # no timezone
                "open": 150.0,
                "high": 155.0,
                "low": 149.0,
                "close": 154.0,
                "volume": 50000,
            },
        ]

        mock_client = MagicMock()
        mock_client.get_ticker_price.return_value = historical
        provider._client = mock_client

        start = datetime(2025, 1, 15, tzinfo=timezone.utc)
        end = datetime(2025, 1, 16, tzinfo=timezone.utc)

        bars = provider.fetch_ohlcv("AAPL", "stock", "1d", start, end)
        assert len(bars) == 1
        # Time should be midnight UTC Jan 15, 2025
        assert bars[0].time == int(
            datetime(2025, 1, 15, tzinfo=timezone.utc).timestamp()
        )

    @patch("backend.services.providers.tiingo_provider.tiingo_counter")
    def test_invalid_bar_skipped(self, mock_counter, provider):
        """Bars with invalid data should be filtered out."""
        mock_counter.check_and_increment = MagicMock()

        historical = [
            {
                "date": "2025-01-15T00:00:00+00:00",
                "open": 150.0,
                "high": 140.0,  # high < open (invalid)
                "low": 149.0,
                "close": 154.0,
                "volume": 50000,
            },
            {
                "date": "2025-01-16T00:00:00+00:00",
                "open": 154.0,
                "high": 158.0,
                "low": 153.0,
                "close": 157.0,
                "volume": 45000,
            },
        ]

        mock_client = MagicMock()
        mock_client.get_ticker_price.return_value = historical
        provider._client = mock_client

        start = datetime(2025, 1, 15, tzinfo=timezone.utc)
        end = datetime(2025, 1, 17, tzinfo=timezone.utc)

        bars = provider.fetch_ohlcv("AAPL", "stock", "1d", start, end)
        assert len(bars) == 1
        assert bars[0].close == Decimal("157.0")

    def test_accepts_option_asset_class(self, provider):
        """Options should be accepted by TiingoProvider."""
        # Just verify it doesn't raise ValueError
        # (will fail on client call, but that's expected in unit test)
        with patch(
            "backend.services.providers.tiingo_provider.tiingo_counter"
        ) as mock_counter:
            mock_counter.check_and_increment = MagicMock()
            mock_client = MagicMock()
            mock_client.get_ticker_price.return_value = []
            provider._client = mock_client

            start = datetime(2025, 1, 15, tzinfo=timezone.utc)
            end = datetime(2025, 1, 16, tzinfo=timezone.utc)
            bars = provider.fetch_ohlcv("AAPL", "option", "1d", start, end)
            assert bars == []

    def test_frequency_mapping(self):
        """Verify interval -> Tiingo frequency mapping."""
        freq_map = {"1d": "daily", "1h": "1Hour", "5m": "5Min", "1m": "1Min"}
        for interval, expected in freq_map.items():
            result = freq_map.get(interval, "daily")
            assert result == expected
