"""Tests for OHLCVCacheService."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.models.ohlcv_cache import OHLCVCache
from backend.services.cache.ohlcv_cache import OHLCVCacheService
from backend.services.market_data import OHLCVBar


def _make_bar(time_offset_hours: int = 0, **overrides) -> OHLCVBar:
    """Create an OHLCVBar with a timestamp offset from a base time."""
    base = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    ts = int((base + timedelta(hours=time_offset_hours)).timestamp())
    defaults = {
        "time": ts,
        "open": Decimal("100.00"),
        "high": Decimal("110.00"),
        "low": Decimal("90.00"),
        "close": Decimal("105.00"),
        "volume": 1000,
    }
    defaults.update(overrides)
    return OHLCVBar(**defaults)


@pytest.fixture
def cache(db_session):
    """Create an OHLCVCacheService backed by the test db_session."""
    return OHLCVCacheService(db_session)


class TestOHLCVCacheService:
    """Tests for the OHLCVCacheService class."""

    def test_put_and_get(self, cache):
        """Bars stored via put() should be retrievable via get()."""
        # Create bars far enough in the past to not be in-progress
        bars = [_make_bar(i) for i in range(3)]

        cache.put("AAPL", "1h", "stock", "tiingo", bars)

        start = datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 15, 13, 0, 0, tzinfo=timezone.utc)

        result = cache.get("AAPL", "1h", start, end)
        assert result is not None
        assert len(result) == 3
        assert result[0].open == Decimal("100.00")
        assert result[0].volume == 1000

    def test_cache_miss_returns_none(self, cache):
        """get() returns None when no bars are cached."""
        start = datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 15, 13, 0, 0, tzinfo=timezone.utc)

        result = cache.get("AAPL", "1h", start, end)
        assert result is None

    def test_in_progress_bar_not_cached(self, cache):
        """Bars whose candle period hasn't closed should be filtered out."""
        # Create a bar in the far future that is definitely in-progress
        future_time = datetime(2099, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        future_bar = OHLCVBar(
            time=int(future_time.timestamp()),
            open=Decimal("100.00"),
            high=Decimal("110.00"),
            low=Decimal("90.00"),
            close=Decimal("105.00"),
            volume=1000,
        )
        # Also include a valid past bar
        past_bars = [_make_bar(0)]

        cache.put("AAPL", "1h", "stock", "tiingo", past_bars + [future_bar])

        # Query the full range - should only have the past bar
        start = datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
        end = datetime(2099, 2, 1, 0, 0, 0, tzinfo=timezone.utc)

        result = cache.get("AAPL", "1h", start, end)
        # The future bar should have been filtered during put()
        # Only the past bar is in the cache
        if result is not None:
            for bar in result:
                bar_dt = datetime.fromtimestamp(bar.time, tz=timezone.utc)
                assert bar_dt < future_time

    def test_partial_coverage_returns_none(self, cache):
        """When cache has bars but doesn't cover the full range, return None."""
        # Store a single bar at the start of a wide range
        bars = [_make_bar(0)]
        cache.put("AAPL", "1h", "stock", "tiingo", bars)

        start = datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
        # Request a range that extends far beyond cached data
        end = datetime(2024, 1, 20, 0, 0, 0, tzinfo=timezone.utc)

        result = cache.get("AAPL", "1h", start, end)
        assert result is None

    def test_invalidation(self, cache):
        """invalidate() should remove matching cached entries."""
        bars = [_make_bar(i) for i in range(3)]
        cache.put("AAPL", "1h", "stock", "tiingo", bars)
        cache.put("MSFT", "1h", "stock", "tiingo", bars)

        deleted = cache.invalidate(symbol="AAPL")
        assert deleted == 3

        start = datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 15, 13, 0, 0, tzinfo=timezone.utc)

        assert cache.get("AAPL", "1h", start, end) is None
        # MSFT should still be cached
        result = cache.get("MSFT", "1h", start, end)
        assert result is not None
        assert len(result) == 3

    def test_invalidation_by_interval(self, cache):
        """invalidate() can filter by interval."""
        bars = [_make_bar(i) for i in range(3)]
        cache.put("AAPL", "1h", "stock", "tiingo", bars)
        cache.put("AAPL", "1d", "stock", "tiingo", bars)

        deleted = cache.invalidate(symbol="AAPL", interval="1h")
        assert deleted == 3

        start = datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 15, 13, 0, 0, tzinfo=timezone.utc)

        assert cache.get("AAPL", "1h", start, end) is None
        result = cache.get("AAPL", "1d", start, end)
        assert result is not None

    def test_invalidation_all(self, cache):
        """invalidate() with no filters deletes everything."""
        bars = [_make_bar(i) for i in range(2)]
        cache.put("AAPL", "1h", "stock", "tiingo", bars)
        cache.put("MSFT", "1d", "stock", "tiingo", bars)

        deleted = cache.invalidate()
        assert deleted == 4

    def test_invalid_bar_skipped_on_put(self, cache):
        """Bars that fail validation should be skipped during put()."""
        invalid_bar = OHLCVBar(
            time=int(datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc).timestamp()),
            open=Decimal("100.00"),
            high=Decimal("80.00"),  # high < low
            low=Decimal("90.00"),
            close=Decimal("85.00"),
            volume=1000,
        )
        valid_bar = _make_bar(1)

        cache.put("AAPL", "1h", "stock", "tiingo", [invalid_bar, valid_bar])

        start = datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 15, 13, 0, 0, tzinfo=timezone.utc)

        result = cache.get("AAPL", "1h", start, end)
        assert result is not None
        assert len(result) == 1

    def test_put_empty_bars(self, cache):
        """put() with empty list should be a no-op."""
        cache.put("AAPL", "1h", "stock", "tiingo", [])

        start = datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 15, 13, 0, 0, tzinfo=timezone.utc)

        result = cache.get("AAPL", "1h", start, end)
        assert result is None

    def test_upsert_updates_existing(self, cache):
        """put() should update existing bars on conflict."""
        bars = [_make_bar(0)]
        cache.put("AAPL", "1h", "stock", "tiingo", bars)

        # Put again with different price (still valid: high >= close)
        updated_bar = _make_bar(0, close=Decimal("108.00"))
        cache.put("AAPL", "1h", "stock", "tiingo", [updated_bar])

        # Use a tight range around the single bar so coverage check passes
        start = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 15, 11, 0, 0, tzinfo=timezone.utc)

        result = cache.get("AAPL", "1h", start, end)
        assert result is not None
        assert len(result) == 1
        assert result[0].close == Decimal("108.00")
