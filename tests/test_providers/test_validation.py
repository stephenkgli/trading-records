"""Tests for OHLCV bar validation."""

from decimal import Decimal

import pytest

from backend.services.market_data import OHLCVBar
from backend.services.providers.validation import validate_bar


def _bar(**overrides) -> OHLCVBar:
    """Create an OHLCVBar with sensible defaults."""
    defaults = {
        "time": 1700000000,
        "open": Decimal("100.00"),
        "high": Decimal("110.00"),
        "low": Decimal("90.00"),
        "close": Decimal("105.00"),
        "volume": 1000,
    }
    defaults.update(overrides)
    return OHLCVBar(**defaults)


class TestBarValidation:
    """Tests for the validate_bar function."""

    def test_valid_bar(self):
        bar = _bar()
        assert validate_bar(bar) is True

    def test_high_below_low(self):
        bar = _bar(high=Decimal("80.00"), low=Decimal("90.00"))
        assert validate_bar(bar) is False

    def test_high_below_open(self):
        bar = _bar(high=Decimal("95.00"), open=Decimal("100.00"), low=Decimal("90.00"))
        assert validate_bar(bar) is False

    def test_high_below_close(self):
        bar = _bar(high=Decimal("95.00"), close=Decimal("100.00"), low=Decimal("90.00"))
        assert validate_bar(bar) is False

    def test_low_above_open(self):
        bar = _bar(low=Decimal("105.00"), open=Decimal("100.00"))
        assert validate_bar(bar) is False

    def test_low_above_close(self):
        bar = _bar(low=Decimal("110.00"), close=Decimal("105.00"))
        assert validate_bar(bar) is False

    def test_negative_volume(self):
        bar = _bar(volume=-1)
        assert validate_bar(bar) is False

    def test_zero_volume_is_valid(self):
        bar = _bar(volume=0)
        assert validate_bar(bar) is True

    def test_zero_price(self):
        bar = _bar(open=Decimal("0"))
        assert validate_bar(bar) is False

    def test_negative_price(self):
        bar = _bar(close=Decimal("-5.00"))
        assert validate_bar(bar) is False

    def test_all_same_price(self):
        """OHLC all equal should be valid (flat bar)."""
        bar = _bar(
            open=Decimal("100.00"),
            high=Decimal("100.00"),
            low=Decimal("100.00"),
            close=Decimal("100.00"),
        )
        assert validate_bar(bar) is True
