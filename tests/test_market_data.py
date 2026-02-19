"""
Tests for market data service (backend/services/market_data.py).

Tests:
- default_interval() per asset class
- build_markers() for long and short directions
- Marker text formatting (trailing zeros)
- Marker sorting by executed_at
- YFinanceProvider with mocked yfinance (including symbol resolution)
- compute_padded_range() end-time clamping
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend.services.market_data import (
    OHLCVBar,
    YFinanceProvider,
    build_markers,
    compute_padded_range,
    default_interval,
)


# ===========================================================================
# default_interval
# ===========================================================================


class TestDefaultInterval:
    """Test asset-class-based interval selection."""

    def test_future_returns_5m(self):
        assert default_interval("future") == "5m"

    def test_stock_returns_1d(self):
        assert default_interval("stock") == "1d"

    def test_option_returns_1d(self):
        assert default_interval("option") == "1d"

    def test_forex_returns_1h(self):
        assert default_interval("forex") == "1h"

    def test_unknown_defaults_to_1d(self):
        assert default_interval("crypto") == "1d"


# ===========================================================================
# build_markers
# ===========================================================================


def _make_leg(
    *,
    side: str,
    role: str,
    quantity: Decimal = Decimal("100"),
    price: Decimal = Decimal("185.50"),
    executed_at: datetime = datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc),
) -> SimpleNamespace:
    """Create a fake leg object that mimics TradeGroupLeg with nested trade."""
    trade = SimpleNamespace(
        id=uuid.uuid4(),
        side=side,
        quantity=quantity,
        price=price,
        executed_at=executed_at,
    )
    return SimpleNamespace(role=role, trade=trade)


class TestBuildMarkersLong:
    """Test marker generation for long-direction groups."""

    def test_entry_marker_long(self):
        leg = _make_leg(side="buy", role="entry")
        markers = build_markers([leg], direction="long")

        assert len(markers) == 1
        m = markers[0]
        assert m["position"] == "belowBar"
        assert m["shape"] == "arrowUp"
        assert m["role"] == "entry"
        assert "ENTRY" in m["text"]

    def test_exit_marker_long(self):
        leg = _make_leg(side="sell", role="exit")
        markers = build_markers([leg], direction="long")

        assert len(markers) == 1
        m = markers[0]
        assert m["position"] == "aboveBar"
        assert m["shape"] == "arrowDown"
        assert m["role"] == "exit"
        assert "EXIT" in m["text"]

    def test_add_marker_long(self):
        leg = _make_leg(side="buy", role="add")
        markers = build_markers([leg], direction="long")

        assert len(markers) == 1
        m = markers[0]
        assert m["position"] == "belowBar"
        assert m["shape"] == "arrowUp"
        assert m["role"] == "add"
        assert "ADD" in m["text"]

    def test_trim_marker_long(self):
        leg = _make_leg(side="sell", role="trim")
        markers = build_markers([leg], direction="long")

        assert len(markers) == 1
        m = markers[0]
        assert m["position"] == "aboveBar"
        assert m["shape"] == "arrowDown"
        assert m["role"] == "trim"
        assert "TRIM" in m["text"]

    def test_marker_text_contains_quantity_and_price(self):
        leg = _make_leg(
            side="buy",
            role="entry",
            quantity=Decimal("50"),
            price=Decimal("182.55"),
        )
        markers = build_markers([leg], direction="long")
        assert "50" in markers[0]["text"]
        assert "182.55" in markers[0]["text"]

    def test_marker_has_trade_id(self):
        leg = _make_leg(side="buy", role="entry")
        markers = build_markers([leg], direction="long")
        assert "trade_id" in markers[0]
        assert markers[0]["trade_id"] == str(leg.trade.id)

    def test_marker_time_is_unix_timestamp(self):
        ts = datetime(2025, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
        leg = _make_leg(side="buy", role="entry", executed_at=ts)
        markers = build_markers([leg], direction="long")
        assert markers[0]["time"] == int(ts.timestamp())


class TestBuildMarkersShort:
    """Test marker generation for short-direction groups."""

    def test_entry_marker_short(self):
        leg = _make_leg(side="sell", role="entry")
        markers = build_markers([leg], direction="short")

        assert len(markers) == 1
        m = markers[0]
        assert m["position"] == "belowBar"
        assert m["shape"] == "arrowDown"
        assert m["role"] == "entry"

    def test_exit_marker_short(self):
        leg = _make_leg(side="buy", role="exit")
        markers = build_markers([leg], direction="short")

        assert len(markers) == 1
        m = markers[0]
        assert m["position"] == "aboveBar"
        assert m["shape"] == "arrowUp"
        assert m["role"] == "exit"


class TestBuildMarkersSorting:
    """Test that markers are sorted by executed_at."""

    def test_markers_sorted_by_time(self):
        t1 = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        t3 = datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc)

        legs = [
            _make_leg(side="sell", role="exit", executed_at=t3),
            _make_leg(side="buy", role="entry", executed_at=t1),
            _make_leg(side="buy", role="add", executed_at=t2),
        ]
        markers = build_markers(legs, direction="long")

        times = [m["time"] for m in markers]
        assert times == sorted(times)

    def test_empty_legs_returns_empty(self):
        markers = build_markers([], direction="long")
        assert markers == []


# ===========================================================================
# build_markers text formatting (trailing zeros)
# ===========================================================================


class TestBuildMarkersTextFormatting:
    """Test that marker text strips trailing zeros from Decimal values."""

    def test_trailing_zeros_stripped_from_quantity(self):
        leg = _make_leg(
            side="buy",
            role="entry",
            quantity=Decimal("1.00000000"),
            price=Decimal("182.55"),
        )
        markers = build_markers([leg], direction="long")
        assert markers[0]["text"] == "ENTRY 1 @ 182.55"

    def test_trailing_zeros_stripped_from_price(self):
        leg = _make_leg(
            side="buy",
            role="entry",
            quantity=Decimal("100"),
            price=Decimal("182.55000000"),
        )
        markers = build_markers([leg], direction="long")
        assert markers[0]["text"] == "ENTRY 100 @ 182.55"

    def test_integer_values_no_decimal_point(self):
        leg = _make_leg(
            side="sell",
            role="exit",
            quantity=Decimal("50.00000000"),
            price=Decimal("200.00000000"),
        )
        markers = build_markers([leg], direction="long")
        assert markers[0]["text"] == "EXIT 50 @ 200"

    def test_fractional_values_preserved(self):
        leg = _make_leg(
            side="buy",
            role="entry",
            quantity=Decimal("0.5"),
            price=Decimal("3.14159"),
        )
        markers = build_markers([leg], direction="long")
        assert markers[0]["text"] == "ENTRY 0.5 @ 3.14159"


# ===========================================================================
# YFinanceProvider
# ===========================================================================


class TestYFinanceProvider:
    """Test YFinanceProvider with mocked yfinance library."""

    def setup_method(self):
        from backend.services.market_data import _ohlcv_cache

        _ohlcv_cache.clear()

    def test_fetch_ohlcv_returns_bars(self):
        import pandas as pd

        index = pd.DatetimeIndex(
            [
                pd.Timestamp("2025-01-15 10:00:00", tz="UTC"),
                pd.Timestamp("2025-01-15 10:05:00", tz="UTC"),
            ]
        )
        df = pd.DataFrame(
            {
                "Open": [182.50, 183.00],
                "High": [183.20, 183.50],
                "Low": [182.30, 182.80],
                "Close": [183.00, 183.40],
                "Volume": [12345, 23456],
            },
            index=index,
        )

        mock_yf = MagicMock()
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = df
        mock_yf.Ticker.return_value = mock_ticker

        with patch.dict("sys.modules", {"yfinance": mock_yf}):
            provider = YFinanceProvider()
            start = datetime(2025, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
            end = datetime(2025, 1, 15, 11, 0, 0, tzinfo=timezone.utc)
            bars = provider.fetch_ohlcv("AAPL", "stock", "5m", start, end)

        assert len(bars) == 2
        assert isinstance(bars[0], OHLCVBar)
        assert bars[0].open == Decimal("182.50")
        assert bars[0].volume == 12345
        assert bars[1].close == Decimal("183.40")

        # Stock symbol should be passed through as-is
        mock_yf.Ticker.assert_called_once_with("AAPL")

    def test_fetch_ohlcv_empty_df(self):
        import pandas as pd

        mock_yf = MagicMock()
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_yf.Ticker.return_value = mock_ticker

        with patch.dict("sys.modules", {"yfinance": mock_yf}):
            provider = YFinanceProvider()
            start = datetime(2025, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
            end = datetime(2025, 1, 15, 11, 0, 0, tzinfo=timezone.utc)
            bars = provider.fetch_ohlcv("INVALID", "stock", "5m", start, end)

        assert bars == []

    def test_futures_symbol_resolved_to_yfinance_format(self):
        """Futures contract MESZ5 should be resolved to MES=F for yfinance."""
        import pandas as pd

        mock_yf = MagicMock()
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_yf.Ticker.return_value = mock_ticker

        with patch.dict("sys.modules", {"yfinance": mock_yf}):
            provider = YFinanceProvider()
            start = datetime(2025, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
            end = datetime(2025, 1, 15, 11, 0, 0, tzinfo=timezone.utc)
            provider.fetch_ohlcv("MESZ5", "future", "5m", start, end)

        mock_yf.Ticker.assert_called_once_with("MES=F")


class TestYFinanceSymbolResolution:
    """Test YFinanceProvider._resolve_symbol directly."""

    def test_future_mesz5(self):
        assert YFinanceProvider._resolve_symbol("MESZ5", "future") == "MES=F"

    def test_future_esz24(self):
        assert YFinanceProvider._resolve_symbol("ESZ24", "future") == "ES=F"

    def test_future_nqh5(self):
        assert YFinanceProvider._resolve_symbol("NQH5", "future") == "NQ=F"

    def test_stock_unchanged(self):
        assert YFinanceProvider._resolve_symbol("AAPL", "stock") == "AAPL"

    def test_future_already_base(self):
        assert YFinanceProvider._resolve_symbol("MES", "future") == "MES=F"


# ===========================================================================
# compute_padded_range end-time clamping
# ===========================================================================


class TestComputePaddedRangeClamp:
    """Test that compute_padded_range clamps end to now."""

    def test_end_clamped_to_now_for_future_date(self):
        far_future = datetime(2099, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        opened = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        _, end = compute_padded_range(opened, far_future, "1d", 20)
        now = datetime.now(timezone.utc)
        assert end <= now

    def test_end_not_clamped_for_past_date(self):
        opened = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        closed = datetime(2024, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
        _, end = compute_padded_range(opened, closed, "1h", 5)
        expected = closed + timedelta(hours=5)
        assert end == expected
