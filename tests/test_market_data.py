"""
Tests for market data service (backend/services/market_data.py).

Tests:
- default_interval() per asset class
- build_markers() output semantics
- Marker text formatting (trailing zeros)
- Marker sorting by executed_at
- compute_padded_range() end-time clamping
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

from backend.services.market_data import (
    OHLCVBar,
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


class TestBuildMarkers:
    """Test marker generation semantics."""

    def test_entry_marker(self):
        leg = _make_leg(side="buy", role="entry")
        markers = build_markers([leg])

        assert len(markers) == 1
        m = markers[0]
        assert m["side"] == "buy"
        assert m["role"] == "entry"
        assert m["text"] == "100"
        assert m["price"] == 185.50

    def test_exit_marker(self):
        leg = _make_leg(side="sell", role="exit")
        markers = build_markers([leg])

        assert len(markers) == 1
        m = markers[0]
        assert m["side"] == "sell"
        assert m["role"] == "exit"
        assert m["text"] == "100"
        assert m["price"] == 185.50

    def test_add_marker(self):
        leg = _make_leg(side="buy", role="add")
        markers = build_markers([leg])

        assert len(markers) == 1
        m = markers[0]
        assert m["side"] == "buy"
        assert m["role"] == "add"
        assert m["text"] == "100"

    def test_trim_marker(self):
        leg = _make_leg(side="sell", role="trim")
        markers = build_markers([leg])

        assert len(markers) == 1
        m = markers[0]
        assert m["side"] == "sell"
        assert m["text"] == "100"

    def test_marker_text_contains_only_quantity(self):
        leg = _make_leg(
            side="buy",
            role="entry",
            quantity=Decimal("50"),
            price=Decimal("182.55"),
        )
        markers = build_markers([leg])
        assert markers[0]["text"] == "50"
        assert markers[0]["price"] == 182.55

    def test_marker_has_trade_id(self):
        leg = _make_leg(side="buy", role="entry")
        markers = build_markers([leg])
        assert "trade_id" in markers[0]
        assert markers[0]["trade_id"] == str(leg.trade.id)

    def test_marker_time_is_unix_timestamp(self):
        ts = datetime(2025, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
        leg = _make_leg(side="buy", role="entry", executed_at=ts)
        markers = build_markers([leg])
        assert markers[0]["time"] == int(ts.timestamp())


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
        markers = build_markers(legs)

        times = [m["time"] for m in markers]
        assert times == sorted(times)

    def test_empty_legs_returns_empty(self):
        markers = build_markers([])
        assert markers == []

    def test_stable_order_for_same_timestamp(self):
        ts = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        first = _make_leg(side="sell", role="entry", executed_at=ts)
        second = _make_leg(side="buy", role="add", executed_at=ts)
        third = _make_leg(side="sell", role="trim", executed_at=ts)

        markers = build_markers([first, second, third])

        assert [m["trade_id"] for m in markers] == [
            str(first.trade.id),
            str(second.trade.id),
            str(third.trade.id),
        ]
        assert [m["side"] for m in markers] == ["sell", "buy", "sell"]


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
        markers = build_markers([leg])
        assert markers[0]["text"] == "1"

    def test_trailing_zeros_stripped_from_price(self):
        leg = _make_leg(
            side="buy",
            role="entry",
            quantity=Decimal("100"),
            price=Decimal("182.55000000"),
        )
        markers = build_markers([leg])
        assert markers[0]["text"] == "100"

    def test_integer_values_no_decimal_point(self):
        leg = _make_leg(
            side="sell",
            role="exit",
            quantity=Decimal("50.00000000"),
            price=Decimal("200.00000000"),
        )
        markers = build_markers([leg])
        assert markers[0]["text"] == "50"

    def test_fractional_values_preserved(self):
        leg = _make_leg(
            side="buy",
            role="entry",
            quantity=Decimal("0.5"),
            price=Decimal("3.14159"),
        )
        markers = build_markers([leg])
        assert markers[0]["text"] == "0.5"


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
