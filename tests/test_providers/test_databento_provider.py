"""Tests for DabentoProvider."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from backend.services.market_data import OHLCVBar
from backend.services.providers.databento_provider import DabentoProvider


@pytest.fixture
def provider():
    """Create a DabentoProvider with a fake API key."""
    return DabentoProvider(api_key="test-key")


class TestDabentoProvider:
    """Tests for the DabentoProvider class."""

    def test_resolve_symbol_future(self, provider):
        assert provider._resolve_symbol("MESZ5", "future") == "MES.c.0"

    def test_resolve_symbol_strips_month_year(self, provider):
        assert provider._resolve_symbol("ESZ24", "future") == "ES.c.0"
        assert provider._resolve_symbol("NQH5", "future") == "NQ.c.0"
        assert provider._resolve_symbol("MNQZ5", "future") == "MNQ.c.0"

    def test_rejects_non_future(self, provider):
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 1, 2, tzinfo=timezone.utc)
        with pytest.raises(ValueError, match="only supports futures"):
            provider.fetch_ohlcv("AAPL", "stock", "1d", start, end)

    @patch("backend.services.providers.databento_provider.databento_counter")
    def test_fetch_ohlcv_success(self, mock_counter, provider):
        """Verify bars are returned from a mocked Databento response."""
        mock_counter.check_and_increment = MagicMock()

        # Create a mock DataFrame with proper datetime index
        index = pd.DatetimeIndex(
            [
                pd.Timestamp("2025-01-15 10:00:00", tz="UTC"),
                pd.Timestamp("2025-01-15 11:00:00", tz="UTC"),
            ]
        )
        df = pd.DataFrame(
            {
                "open": [100.0, 101.0],
                "high": [105.0, 106.0],
                "low": [99.0, 100.0],
                "close": [104.0, 105.0],
                "volume": [1000, 2000],
            },
            index=index,
        )

        mock_data = MagicMock()
        mock_data.to_df.return_value = df

        mock_client = MagicMock()
        mock_client.timeseries.get_range.return_value = mock_data
        provider._client = mock_client

        start = datetime(2025, 1, 15, tzinfo=timezone.utc)
        end = datetime(2025, 1, 16, tzinfo=timezone.utc)

        bars = provider.fetch_ohlcv("MESZ5", "future", "1h", start, end)

        assert len(bars) == 2
        assert bars[0].open == Decimal("100.0")
        assert bars[0].high == Decimal("105.0")
        assert bars[1].close == Decimal("105.0")
        assert bars[0].volume == 1000

        mock_counter.check_and_increment.assert_called_once()

    @patch("backend.services.providers.databento_provider.databento_counter")
    def test_empty_response(self, mock_counter, provider):
        """Verify empty list returned for empty DataFrame."""
        mock_counter.check_and_increment = MagicMock()

        mock_data = MagicMock()
        mock_data.to_df.return_value = pd.DataFrame()

        mock_client = MagicMock()
        mock_client.timeseries.get_range.return_value = mock_data
        provider._client = mock_client

        start = datetime(2025, 1, 15, tzinfo=timezone.utc)
        end = datetime(2025, 1, 16, tzinfo=timezone.utc)

        bars = provider.fetch_ohlcv("MESZ5", "future", "1h", start, end)
        assert bars == []

    @patch("backend.services.providers.databento_provider.databento_counter")
    def test_invalid_bars_skipped(self, mock_counter, provider):
        """Bars with high < low should be filtered out."""
        mock_counter.check_and_increment = MagicMock()

        index = pd.DatetimeIndex(
            [
                pd.Timestamp("2025-01-15 10:00:00", tz="UTC"),
                pd.Timestamp("2025-01-15 11:00:00", tz="UTC"),
            ]
        )
        df = pd.DataFrame(
            {
                "open": [100.0, 101.0],
                "high": [90.0, 106.0],  # first bar: high < low (invalid)
                "low": [99.0, 100.0],
                "close": [95.0, 105.0],
                "volume": [1000, 2000],
            },
            index=index,
        )

        mock_data = MagicMock()
        mock_data.to_df.return_value = df

        mock_client = MagicMock()
        mock_client.timeseries.get_range.return_value = mock_data
        provider._client = mock_client

        start = datetime(2025, 1, 15, tzinfo=timezone.utc)
        end = datetime(2025, 1, 16, tzinfo=timezone.utc)

        bars = provider.fetch_ohlcv("MESZ5", "future", "1h", start, end)
        assert len(bars) == 1
        assert bars[0].close == Decimal("105.0")

    def test_normalize_timestamp_naive(self):
        dt = datetime(2025, 1, 15, 10, 0, 0)
        result = DabentoProvider._normalize_timestamp(dt)
        assert result.tzinfo == timezone.utc

    def test_normalize_timestamp_aware(self):
        from datetime import timedelta

        eastern = timezone(timedelta(hours=-5))
        dt = datetime(2025, 1, 15, 10, 0, 0, tzinfo=eastern)
        result = DabentoProvider._normalize_timestamp(dt)
        assert result.tzinfo == timezone.utc
        assert result.hour == 15  # 10 EST = 15 UTC

    def test_interval_schema_map(self):
        """Verify all expected intervals are mapped."""
        assert "1m" in DabentoProvider.INTERVAL_SCHEMA_MAP
        assert "5m" in DabentoProvider.INTERVAL_SCHEMA_MAP
        assert "15m" in DabentoProvider.INTERVAL_SCHEMA_MAP
        assert "1h" in DabentoProvider.INTERVAL_SCHEMA_MAP
        assert "1d" in DabentoProvider.INTERVAL_SCHEMA_MAP
