"""PostgreSQL cache for completed OHLCV bars.

Bars whose candle period hasn't fully closed are never stored or
returned. Completed bars are cached permanently.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import structlog
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.models.ohlcv_cache import OHLCVCache
from backend.services.market_data import INTERVAL_DURATIONS, OHLCVBar
from backend.services.providers.validation import filter_outlier_bars, validate_bar

logger = structlog.get_logger(__name__)


class OHLCVCacheService:
    """PostgreSQL cache for completed OHLCV bars.

    Bars whose candle period hasn't fully closed are never stored or
    returned. Completed bars are cached permanently.
    """

    def __init__(self, db: Session):
        self.db = db

    def get(
        self,
        symbol: str,
        interval: str,
        start: datetime,
        end: datetime,
    ) -> list[OHLCVBar] | None:
        """Get cached bars. Returns None on cache miss or partial coverage.

        Detects incomplete cache ranges by comparing the last cached bar
        against the expected end of the requested range. If the gap exceeds
        2x the bar duration, the cache is considered incomplete and None is
        returned so the caller re-fetches from the provider.
        """
        rows = self._query_rows(symbol, interval, start, end)
        if not rows:
            return None

        # Check if cache covers the full requested range.
        # If the last cached bar is more than 2x bar_duration before `end`,
        # the cache is likely incomplete -- return None to trigger re-fetch.
        bar_duration = INTERVAL_DURATIONS.get(interval, timedelta(hours=1))
        last_bar_time = rows[-1].bar_time
        # SQLite returns naive datetimes; ensure timezone-aware for comparison
        if last_bar_time.tzinfo is None:
            last_bar_time = last_bar_time.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        expected_end = min(end, now - bar_duration)  # can't expect in-progress bars
        if last_bar_time + bar_duration * 2 < expected_end:
            return None  # partial coverage, re-fetch

        bars = [self._to_bar(row) for row in rows]
        # 缓存中可能存有历史脏数据，返回前过滤毛刺
        return filter_outlier_bars(bars)

    def put(
        self,
        symbol: str,
        interval: str,
        asset_class: str,
        provider: str,
        bars: list[OHLCVBar],
    ) -> None:
        """Store completed bars. In-progress bars are filtered out."""
        if not bars:
            return

        now = datetime.now(timezone.utc)
        bar_duration = INTERVAL_DURATIONS.get(interval, timedelta(hours=1))
        values = []

        for bar in bars:
            if not validate_bar(bar):
                logger.warning(
                    "cache_put_invalid_bar_skipped", symbol=symbol, time=bar.time
                )
                continue

            bar_time = datetime.fromtimestamp(bar.time, tz=timezone.utc)

            # Skip in-progress bars: if bar_time + duration > now, the
            # candle hasn't closed yet.
            if bar_time + bar_duration > now:
                continue

            values.append(
                {
                    "symbol": symbol,
                    "interval": interval,
                    "bar_time": bar_time,
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                    "volume": bar.volume,
                    "provider": provider,
                    "asset_class": asset_class,
                }
            )

        if not values:
            return

        # Use dialect-aware upsert: PostgreSQL uses ON CONFLICT DO UPDATE,
        # SQLite uses INSERT OR REPLACE via a fallback path.
        dialect = self.db.bind.dialect.name if self.db.bind else "unknown"

        if dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert

            stmt = insert(OHLCVCache).values(values)
            stmt = stmt.on_conflict_do_update(
                index_elements=["symbol", "interval", "bar_time"],
                set_={
                    "open": stmt.excluded.open,
                    "high": stmt.excluded.high,
                    "low": stmt.excluded.low,
                    "close": stmt.excluded.close,
                    "volume": stmt.excluded.volume,
                    "provider": stmt.excluded.provider,
                },
            )
            self.db.execute(stmt)
        else:
            # SQLite fallback: delete + insert for upsert semantics
            for val in values:
                self.db.execute(
                    delete(OHLCVCache).where(
                        OHLCVCache.symbol == val["symbol"],
                        OHLCVCache.interval == val["interval"],
                        OHLCVCache.bar_time == val["bar_time"],
                    )
                )
            self.db.execute(OHLCVCache.__table__.insert(), values)

        self.db.commit()
        logger.info("cache_put", symbol=symbol, interval=interval, count=len(values))

    def invalidate(
        self,
        symbol: str | None = None,
        interval: str | None = None,
    ) -> int:
        """Delete cached entries matching criteria."""
        query = delete(OHLCVCache)
        if symbol:
            query = query.where(OHLCVCache.symbol == symbol)
        if interval:
            query = query.where(OHLCVCache.interval == interval)
        result = self.db.execute(query)
        self.db.commit()
        return result.rowcount

    def _query_rows(
        self, symbol: str, interval: str, start: datetime, end: datetime
    ) -> list[OHLCVCache]:
        query = (
            select(OHLCVCache)
            .where(OHLCVCache.symbol == symbol)
            .where(OHLCVCache.interval == interval)
            .where(OHLCVCache.bar_time >= start)
            .where(OHLCVCache.bar_time <= end)
            .order_by(OHLCVCache.bar_time.asc())
        )
        return list(self.db.execute(query).scalars().all())

    def _to_bar(self, row: OHLCVCache) -> OHLCVBar:
        bar_time = row.bar_time
        # SQLite returns naive datetimes; ensure timezone-aware
        if bar_time.tzinfo is None:
            bar_time = bar_time.replace(tzinfo=timezone.utc)
        return OHLCVBar(
            time=int(bar_time.timestamp()),
            open=row.open,
            high=row.high,
            low=row.low,
            close=row.close,
            volume=row.volume,
        )
