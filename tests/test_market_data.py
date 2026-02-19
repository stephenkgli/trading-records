"""
Tests for market data service (backend/services/market_data.py).

Tests:
- choose_interval() with various trade durations
- build_markers() for long and short directions
- Marker sorting by executed_at
- YFinanceProvider with mocked yfinance
- resolve_yfinance_symbol() for futures and stocks
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
    choose_interval,
    compute_padded_range,
    resolve_yfinance_symbol,
)


# ===========================================================================
# choose_interval
# ===========================================================================


class TestChooseInterval:
    """Test automatic interval selection based on trade duration.

    Uses recent dates (relative to now) so the age-based promotion
    does not interfere with the pure duration logic.
    """

    def _recent(self, **kwargs: int) -> datetime:
        """Return a datetime in the recent past (within 1 day of now)."""
        return datetime.now(timezone.utc) - timedelta(hours=1, **kwargs)

    def test_short_duration_returns_1m(self):
        """Duration < 2h should return '1m'."""
        opened = self._recent()
        closed = opened + timedelta(hours=1)
        assert choose_interval(opened, closed) == "1m"

    def test_very_short_duration_returns_1m(self):
        """Duration of a few minutes should return '1m'."""
        opened = self._recent()
        closed = opened + timedelta(minutes=15)
        assert choose_interval(opened, closed) == "1m"

    def test_medium_duration_returns_5m(self):
        """Duration 2-8h should return '5m'."""
        opened = self._recent()
        closed = opened + timedelta(hours=4)
        assert choose_interval(opened, closed) == "5m"

    def test_boundary_2h_returns_5m(self):
        """Duration exactly 2h should return '5m' (>= 2h boundary)."""
        opened = self._recent()
        closed = opened + timedelta(hours=2)
        assert choose_interval(opened, closed) == "5m"

    def test_multi_day_returns_15m(self):
        """Duration 8h-3d should return '15m'."""
        opened = self._recent()
        closed = opened + timedelta(days=1)
        assert choose_interval(opened, closed) == "15m"

    def test_long_duration_returns_1h(self):
        """Duration 3-30d should return '1h'."""
        opened = datetime.now(timezone.utc) - timedelta(days=5)
        closed = opened + timedelta(days=10)
        assert choose_interval(opened, closed) == "1h"

    def test_very_long_duration_returns_1d(self):
        """Duration > 30d should return '1d'."""
        opened = datetime.now(timezone.utc) - timedelta(days=40)
        closed = opened + timedelta(days=60)
        assert choose_interval(opened, closed) == "1d"

    def test_none_closed_at_uses_now(self):
        """When closed_at is None, use current time (open position)."""
        opened = datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        # Open since 2020 -> very long duration -> "1d"
        result = choose_interval(opened, None)
        assert result == "1d"


class TestChooseIntervalAgePromotion:
    """Test that old trades get promoted to coarser intervals."""

    def test_old_short_trade_promoted_to_1h(self):
        """A 1h trade from 5 months ago should be promoted from 1m to 1h."""
        opened = datetime.now(timezone.utc) - timedelta(days=150)
        closed = opened + timedelta(hours=1)
        assert choose_interval(opened, closed) == "1h"

    def test_old_trade_7_days_promoted_to_5m(self):
        """A short trade from 10 days ago should be promoted from 1m to 5m."""
        opened = datetime.now(timezone.utc) - timedelta(days=10)
        closed = opened + timedelta(hours=1)
        assert choose_interval(opened, closed) == "5m"

    def test_very_old_trade_promoted_to_1d(self):
        """A trade from 3 years ago should be promoted to 1d."""
        opened = datetime.now(timezone.utc) - timedelta(days=1000)
        closed = opened + timedelta(hours=4)
        assert choose_interval(opened, closed) == "1d"

    def test_already_coarse_not_demoted(self):
        """If duration already selects 1d, age guard doesn't change it."""
        opened = datetime.now(timezone.utc) - timedelta(days=100)
        closed = opened + timedelta(days=60)
        assert choose_interval(opened, closed) == "1d"


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
        """Long entry (buy) should be green arrow below bar."""
        leg = _make_leg(side="buy", role="entry")
        markers = build_markers([leg], direction="long")

        assert len(markers) == 1
        m = markers[0]
        assert m["position"] == "belowBar"
        assert m["shape"] == "arrowUp"
        assert m["role"] == "entry"
        assert "ENTRY" in m["text"]

    def test_exit_marker_long(self):
        """Long exit (sell) should be red arrow above bar."""
        leg = _make_leg(side="sell", role="exit")
        markers = build_markers([leg], direction="long")

        assert len(markers) == 1
        m = markers[0]
        assert m["position"] == "aboveBar"
        assert m["shape"] == "arrowDown"
        assert m["role"] == "exit"
        assert "EXIT" in m["text"]

    def test_add_marker_long(self):
        """Long add (buy) should be below bar with arrowUp."""
        leg = _make_leg(side="buy", role="add")
        markers = build_markers([leg], direction="long")

        assert len(markers) == 1
        m = markers[0]
        assert m["position"] == "belowBar"
        assert m["shape"] == "arrowUp"
        assert m["role"] == "add"
        assert "ADD" in m["text"]

    def test_trim_marker_long(self):
        """Long trim (sell) should be above bar with arrowDown."""
        leg = _make_leg(side="sell", role="trim")
        markers = build_markers([leg], direction="long")

        assert len(markers) == 1
        m = markers[0]
        assert m["position"] == "aboveBar"
        assert m["shape"] == "arrowDown"
        assert m["role"] == "trim"
        assert "TRIM" in m["text"]

    def test_marker_text_contains_quantity_and_price(self):
        """Marker text should include quantity and price."""
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
        """Each marker should include the trade_id."""
        leg = _make_leg(side="buy", role="entry")
        markers = build_markers([leg], direction="long")
        assert "trade_id" in markers[0]
        assert markers[0]["trade_id"] == str(leg.trade.id)

    def test_marker_time_is_unix_timestamp(self):
        """Marker time should be a Unix timestamp integer."""
        ts = datetime(2025, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
        leg = _make_leg(side="buy", role="entry", executed_at=ts)
        markers = build_markers([leg], direction="long")
        assert markers[0]["time"] == int(ts.timestamp())


class TestBuildMarkersShort:
    """Test marker generation for short-direction groups."""

    def test_entry_marker_short(self):
        """Short entry (sell) should be arrow below bar."""
        leg = _make_leg(side="sell", role="entry")
        markers = build_markers([leg], direction="short")

        assert len(markers) == 1
        m = markers[0]
        assert m["position"] == "belowBar"
        assert m["shape"] == "arrowDown"
        assert m["role"] == "entry"

    def test_exit_marker_short(self):
        """Short exit (buy) should be arrow above bar."""
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
        """Markers should be returned sorted by trade executed_at."""
        t1 = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        t3 = datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc)

        # Create legs out of chronological order
        legs = [
            _make_leg(side="sell", role="exit", executed_at=t3),
            _make_leg(side="buy", role="entry", executed_at=t1),
            _make_leg(side="buy", role="add", executed_at=t2),
        ]
        markers = build_markers(legs, direction="long")

        times = [m["time"] for m in markers]
        assert times == sorted(times)

    def test_empty_legs_returns_empty(self):
        """No legs should return no markers."""
        markers = build_markers([], direction="long")
        assert markers == []


# ===========================================================================
# YFinanceProvider
# ===========================================================================


class TestYFinanceProvider:
    """Test YFinanceProvider with mocked yfinance library."""

    def setup_method(self):
        """Clear the OHLCV cache before each test to avoid cross-test interference."""
        from backend.services.market_data import _ohlcv_cache

        _ohlcv_cache.clear()

    def test_fetch_ohlcv_returns_bars(self):
        """YFinanceProvider should convert yfinance DataFrame to OHLCVBar list."""
        import pandas as pd

        # Build a mock DataFrame similar to what yfinance returns
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
            bars = provider.fetch_ohlcv("AAPL", "5m", start, end)

        assert len(bars) == 2
        assert isinstance(bars[0], OHLCVBar)
        assert bars[0].open == Decimal("182.50")
        assert bars[0].volume == 12345
        assert bars[1].close == Decimal("183.40")

        mock_yf.Ticker.assert_called_once_with("AAPL")

    def test_fetch_ohlcv_empty_df(self):
        """Empty DataFrame from yfinance should return empty list."""
        import pandas as pd

        mock_yf = MagicMock()
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_yf.Ticker.return_value = mock_ticker

        with patch.dict("sys.modules", {"yfinance": mock_yf}):
            provider = YFinanceProvider()
            start = datetime(2025, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
            end = datetime(2025, 1, 15, 11, 0, 0, tzinfo=timezone.utc)
            bars = provider.fetch_ohlcv("INVALID", "5m", start, end)

        assert bars == []


# ===========================================================================
# resolve_yfinance_symbol
# ===========================================================================


class TestResolveYfinanceSymbol:
    """Test yfinance symbol resolution for various asset classes."""

    def test_future_contract_normalized_with_suffix(self):
        """Futures contract MESZ5 should resolve to MES=F."""
        assert resolve_yfinance_symbol("MESZ5", "future") == "MES=F"

    def test_future_two_digit_year(self):
        """Futures contract ESZ24 should resolve to ES=F."""
        assert resolve_yfinance_symbol("ESZ24", "future") == "ES=F"

    def test_future_different_month(self):
        """Futures contract NQH5 should resolve to NQ=F."""
        assert resolve_yfinance_symbol("NQH5", "future") == "NQ=F"

    def test_stock_unchanged(self):
        """Stock symbols should pass through unchanged."""
        assert resolve_yfinance_symbol("AAPL", "stock") == "AAPL"

    def test_option_unchanged(self):
        """Option symbols should pass through unchanged."""
        assert resolve_yfinance_symbol("AAPL230120C00150000", "option") == "AAPL230120C00150000"

    def test_future_already_base(self):
        """If a future symbol has no contract suffix, still append =F."""
        assert resolve_yfinance_symbol("MES", "future") == "MES=F"


# ===========================================================================
# build_markers text formatting (trailing zeros)
# ===========================================================================


class TestBuildMarkersTextFormatting:
    """Test that marker text strips trailing zeros from Decimal values."""

    def test_trailing_zeros_stripped_from_quantity(self):
        """Quantity like 1.00000000 should display as '1'."""
        leg = _make_leg(
            side="buy",
            role="entry",
            quantity=Decimal("1.00000000"),
            price=Decimal("182.55"),
        )
        markers = build_markers([leg], direction="long")
        assert markers[0]["text"] == "ENTRY 1 @ 182.55"

    def test_trailing_zeros_stripped_from_price(self):
        """Price like 182.55000000 should display as '182.55'."""
        leg = _make_leg(
            side="buy",
            role="entry",
            quantity=Decimal("100"),
            price=Decimal("182.55000000"),
        )
        markers = build_markers([leg], direction="long")
        assert markers[0]["text"] == "ENTRY 100 @ 182.55"

    def test_integer_values_no_decimal_point(self):
        """Whole number values should display without a decimal point."""
        leg = _make_leg(
            side="sell",
            role="exit",
            quantity=Decimal("50.00000000"),
            price=Decimal("200.00000000"),
        )
        markers = build_markers([leg], direction="long")
        assert markers[0]["text"] == "EXIT 50 @ 200"

    def test_fractional_values_preserved(self):
        """Meaningful fractional digits should be preserved."""
        leg = _make_leg(
            side="buy",
            role="entry",
            quantity=Decimal("0.5"),
            price=Decimal("3.14159"),
        )
        markers = build_markers([leg], direction="long")
        assert markers[0]["text"] == "ENTRY 0.5 @ 3.14159"


# ===========================================================================
# compute_padded_range end-time clamping
# ===========================================================================


class TestComputePaddedRangeClamp:
    """Test that compute_padded_range clamps end to now."""

    def test_end_clamped_to_now_for_future_date(self):
        """If closed_at + padding extends past now, end should be clamped."""
        far_future = datetime(2099, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        opened = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        _, end = compute_padded_range(opened, far_future, "1d", 20)
        now = datetime.now(timezone.utc)
        assert end <= now

    def test_end_not_clamped_for_past_date(self):
        """If the padded range is entirely in the past, end should not be clamped."""
        opened = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        closed = datetime(2024, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
        _, end = compute_padded_range(opened, closed, "1h", 5)
        # 5 hours after 2024-01-02 is still in the past
        expected = closed + timedelta(hours=5)
        assert end == expected
