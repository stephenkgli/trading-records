"""Lightweight daily call counter for provider rate limiting."""

from datetime import date, datetime, timezone
from threading import Lock

import structlog

logger = structlog.get_logger(__name__)


class DailyCallCounter:
    """Track daily API call counts per provider.

    Resets automatically at midnight UTC. Not persisted across restarts,
    which is acceptable because the OHLCV cache prevents most repeat calls.
    """

    def __init__(self, provider_name: str, daily_limit: int):
        self._provider = provider_name
        self._daily_limit = daily_limit
        self._count = 0
        self._date: date = datetime.now(timezone.utc).date()
        self._lock = Lock()

    def check_and_increment(self) -> None:
        """Increment counter. Raises RateLimitError if limit exceeded."""
        with self._lock:
            today = datetime.now(timezone.utc).date()
            if today != self._date:
                self._count = 0
                self._date = today
            if self._count >= self._daily_limit:
                logger.warning(
                    "rate_limit_exceeded",
                    provider=self._provider,
                    limit=self._daily_limit,
                )
                raise RateLimitError(
                    f"{self._provider} daily limit ({self._daily_limit}) exceeded"
                )
            self._count += 1

    @property
    def remaining(self) -> int:
        """Calls remaining today."""
        with self._lock:
            today = datetime.now(timezone.utc).date()
            if today != self._date:
                return self._daily_limit
            return max(0, self._daily_limit - self._count)


class RateLimitError(Exception):
    """Raised when a provider's daily call limit is exceeded."""

    pass


# Shared counters (module-level singletons)
tiingo_counter = DailyCallCounter("tiingo", daily_limit=400)
databento_counter = DailyCallCounter("databento", daily_limit=500)
