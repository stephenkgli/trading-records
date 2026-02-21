"""Tests for the DailyCallCounter rate limiter."""

from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest

from backend.services.providers.rate_limit import DailyCallCounter, RateLimitError


class TestDailyCallCounter:
    """Tests for the DailyCallCounter class."""

    def test_increments_and_tracks(self):
        counter = DailyCallCounter("test", daily_limit=5)
        counter.check_and_increment()
        counter.check_and_increment()
        assert counter.remaining == 3

    def test_raises_when_limit_exceeded(self):
        counter = DailyCallCounter("test", daily_limit=2)
        counter.check_and_increment()
        counter.check_and_increment()
        with pytest.raises(RateLimitError, match="test daily limit"):
            counter.check_and_increment()

    def test_resets_on_new_day(self):
        counter = DailyCallCounter("test", daily_limit=2)
        counter.check_and_increment()
        counter.check_and_increment()

        # Simulate day change
        tomorrow = date(2099, 1, 2)
        with patch(
            "backend.services.providers.rate_limit.datetime"
        ) as mock_dt:
            mock_dt.now.return_value = datetime(2099, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            # Reset the internal date to trigger day change
            counter._date = date(2099, 1, 1)
            counter.check_and_increment()  # should not raise
            assert counter.remaining == 1

    def test_remaining_reflects_usage(self):
        counter = DailyCallCounter("test", daily_limit=10)
        assert counter.remaining == 10
        counter.check_and_increment()
        assert counter.remaining == 9
        counter.check_and_increment()
        assert counter.remaining == 8

    def test_remaining_resets_on_new_day(self):
        counter = DailyCallCounter("test", daily_limit=5)
        counter.check_and_increment()
        counter.check_and_increment()
        assert counter.remaining == 3

        # Force a different date
        counter._date = date(2000, 1, 1)
        assert counter.remaining == 5

    def test_limit_of_zero(self):
        counter = DailyCallCounter("test", daily_limit=0)
        with pytest.raises(RateLimitError):
            counter.check_and_increment()

    def test_limit_of_one(self):
        counter = DailyCallCounter("test", daily_limit=1)
        counter.check_and_increment()
        with pytest.raises(RateLimitError):
            counter.check_and_increment()
