# Market Data Provider Migration Design

## Overview

Migrate from the current single-provider yfinance architecture to two
purpose-built providers with a PostgreSQL cache:

- **Databento** for futures OHLCV bars (CME: ES, MES, NQ, MNQ, etc.)
- **Tiingo** for stock daily OHLCV bars (US equities)
- **PostgreSQL `ohlcv_cache` table** for permanent storage of completed bars

Design principles: trust the providers, fail fast, cache completed bars forever,
never return in-progress bars, stay within free tier limits.

## Current Architecture

```
GET /api/v1/groups/{id}/chart
        |
        v
  YFinanceProvider
  - In-memory TTLCache (maxsize=256, ttl=600s)
  - All asset classes routed to yfinance
```

### Limitations

1. yfinance has reliability issues and rate limits
2. In-memory cache lost on restart, not shared across instances
3. Inconsistent futures data quality
4. Same data re-fetched repeatedly

### Key Files

| File | Purpose |
|------|---------|
| `backend/services/market_data.py` | `MarketDataProvider` Protocol, `YFinanceProvider`, `OHLCVBar` model |
| `backend/api/groups.py` | Chart endpoint using `YFinanceProvider` directly |
| `backend/schemas/chart.py` | Response schemas (`CandleBar`, `GroupChartResponse`) |
| `backend/utils/symbol.py` | Futures symbol normalization (`MESZ5` -> `MES`) |

---

## Proposed Architecture

```
GET /api/v1/groups/{id}/chart
        |
        v
  OHLCVCacheService (PostgreSQL)
  1. Check cache for completed bars
  2. On miss: fetch from provider, filter in-progress bars, cache, return
  3. On provider error: propagate immediately (fail-fast)
        |
        v
  Pick provider by asset_class:
    future -> DabentoProvider
    stock  -> TiingoProvider
        |                       |
        v                       v
  DabentoProvider         TiingoProvider
  - CME futures            - US stocks
  - 5m/1h/1d bars          - Daily bars
  - UTC normalization       - adjClose prices
```

No ProviderRouter abstraction, no fallback chain, no circuit breakers. The
chart endpoint picks the provider directly by `asset_class` and wraps it
with the cache service. A simple daily call counter guards each provider
against exceeding API limits.

---

## Provider Protocol (Unchanged)

```python
class MarketDataProvider(Protocol):
    """Protocol for market data providers."""

    def fetch_ohlcv(
        self,
        symbol: str,
        asset_class: str,
        interval: str,
        start: datetime,
        end: datetime,
    ) -> list[OHLCVBar]: ...
```

## DabentoProvider

Handles CME futures data using the Databento Python client.

```python
# backend/services/providers/databento_provider.py

import databento as db
from datetime import datetime, timezone
from decimal import Decimal

import structlog

from backend.services.market_data import MarketDataProvider, OHLCVBar
from backend.services.providers.validation import validate_bar
from backend.config import settings

logger = structlog.get_logger(__name__)


class DabentoProvider:
    """Market data provider for CME futures via Databento.

    Uses the GLBX.MDP3 dataset for CME Globex data. Prefers native OHLCV
    schemas at the requested interval to minimize data transfer costs.

    Contract roll handling:
    - Uses ``stype_in="parent"`` for continuous front-month contracts.
    - Databento applies ratio back-adjustment by default, which preserves
      return accuracy across rolls but shifts absolute price levels. This
      is acceptable for chart visualization.
    """

    DATASET = "GLBX.MDP3"

    INTERVAL_SCHEMA_MAP: dict[str, tuple[str, bool]] = {
        "1m":  ("ohlcv-1m", False),
        "5m":  ("ohlcv-1m", True),    # Resample 1m -> 5m
        "15m": ("ohlcv-1m", True),    # Resample 1m -> 15m
        "1h":  ("ohlcv-1h", False),
        "1d":  ("ohlcv-1d", False),
    }

    RESAMPLE_RULES: dict[str, str] = {
        "5m": "5min",
        "15m": "15min",
    }

    RESAMPLE_WARN_THRESHOLD = 10_000

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or settings.databento_api_key
        self._client: db.Historical | None = None

    @property
    def client(self) -> db.Historical:
        if self._client is None:
            self._client = db.Historical(self._api_key)
        return self._client

    @staticmethod
    def _normalize_timestamp(ts: datetime) -> datetime:
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc)

    def _resolve_symbol(self, symbol: str, asset_class: str) -> str:
        from backend.utils.symbol import normalize_futures_symbol
        return normalize_futures_symbol(symbol, asset_class)

    def fetch_ohlcv(
        self,
        symbol: str,
        asset_class: str,
        interval: str,
        start: datetime,
        end: datetime,
    ) -> list[OHLCVBar]:
        if asset_class != "future":
            raise ValueError(f"DabentoProvider only supports futures, got {asset_class}")

        db_symbol = self._resolve_symbol(symbol, asset_class)
        schema_info = self.INTERVAL_SCHEMA_MAP.get(interval, ("ohlcv-1h", False))
        schema, needs_resample = schema_info

        data = self.client.timeseries.get_range(
            dataset=self.DATASET,
            symbols=db_symbol,
            schema=schema,
            stype_in="parent",
            start=start.isoformat(),
            end=end.isoformat(),
        )

        df = data.to_df()
        if df.empty:
            return []

        if needs_resample:
            rule = self.RESAMPLE_RULES.get(interval)
            if rule:
                if len(df) > self.RESAMPLE_WARN_THRESHOLD:
                    logger.warning("large_resample_dataset", symbol=db_symbol, rows=len(df))
                df = df.resample(rule).agg({
                    'open': 'first', 'high': 'max',
                    'low': 'min', 'close': 'last', 'volume': 'sum',
                }).dropna()

        return self._to_bars(df)

    def _to_bars(self, df) -> list[OHLCVBar]:
        bars: list[OHLCVBar] = []
        for row in df.itertuples():
            ts = int(self._normalize_timestamp(row.Index.to_pydatetime()).timestamp())
            bar = OHLCVBar(
                time=ts,
                open=Decimal(str(row.open)),
                high=Decimal(str(row.high)),
                low=Decimal(str(row.low)),
                close=Decimal(str(row.close)),
                volume=int(row.volume),
            )
            if validate_bar(bar):
                bars.append(bar)
            else:
                logger.warning("invalid_bar_skipped", provider="databento", time=ts)
        return bars
```

## TiingoProvider

Handles US stock daily data using the Tiingo REST API.

```python
# backend/services/providers/tiingo_provider.py

from datetime import datetime, timezone
from decimal import Decimal

import structlog
from dateutil import parser as dateutil_parser
from tiingo import TiingoClient

from backend.services.market_data import MarketDataProvider, OHLCVBar
from backend.services.providers.validation import validate_bar
from backend.config import settings

logger = structlog.get_logger(__name__)


class TiingoProvider:
    """Market data provider for US stocks via Tiingo.

    Uses adjusted prices (adjOpen/adjHigh/adjLow/adjClose) for accuracy
    across splits and dividends.

    Free tier supports end-of-day (daily) data only. Intraday requires
    IEX subscription (~$10/month).
    """

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or settings.tiingo_api_key
        self._client: TiingoClient | None = None

    @property
    def client(self) -> TiingoClient:
        if self._client is None:
            self._client = TiingoClient({'api_key': self._api_key, 'session': True})
        return self._client

    def fetch_ohlcv(
        self,
        symbol: str,
        asset_class: str,
        interval: str,
        start: datetime,
        end: datetime,
    ) -> list[OHLCVBar]:
        if asset_class not in ("stock", "option"):
            raise ValueError(f"TiingoProvider supports stocks/options, got {asset_class}")

        frequency = {"1d": "daily", "1h": "1Hour", "5m": "5Min", "1m": "1Min"}.get(interval, "daily")

        historical = self.client.get_ticker_price(
            symbol.upper(),
            fmt='json',
            startDate=start.strftime('%Y-%m-%d'),
            endDate=end.strftime('%Y-%m-%d'),
            frequency=frequency,
        )

        if not historical:
            return []

        bars: list[OHLCVBar] = []
        for item in historical:
            dt = dateutil_parser.isoparse(item['date'])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            dt = dt.astimezone(timezone.utc)

            bar = OHLCVBar(
                time=int(dt.timestamp()),
                open=Decimal(str(item.get('adjOpen', item['open']))),
                high=Decimal(str(item.get('adjHigh', item['high']))),
                low=Decimal(str(item.get('adjLow', item['low']))),
                close=Decimal(str(item.get('adjClose', item['close']))),
                volume=int(item['volume']),
            )
            if validate_bar(bar):
                bars.append(bar)
            else:
                logger.warning("invalid_bar_skipped", provider="tiingo", time=bar.time)
        return bars
```

## Bar Validation

```python
# backend/services/providers/validation.py

from decimal import Decimal
from backend.services.market_data import OHLCVBar


def validate_bar(bar: OHLCVBar) -> bool:
    """Validate OHLCV bar data integrity.

    Checks: high >= low, high >= open/close, low <= open/close,
    volume >= 0, all prices > 0.
    """
    if bar.high < bar.low:
        return False
    if bar.high < bar.open or bar.high < bar.close:
        return False
    if bar.low > bar.open or bar.low > bar.close:
        return False
    if bar.volume < 0:
        return False
    if any(p <= Decimal("0") for p in (bar.open, bar.high, bar.low, bar.close)):
        return False
    return True
```

## Rate Limiting

A lightweight daily call counter prevents exceeding provider API limits.
This is intentionally simple -- no token bucket, no sliding window, no
persistence across restarts. The PostgreSQL cache makes provider calls rare
enough that a basic counter suffices.

```python
# backend/services/providers/rate_limit.py

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
```

**Design choices:**

- **Tiingo limit set to 400** (not 500): leaves headroom below the 500
  calls/day free tier to account for test calls, manual API exploration,
  or retry scenarios.
- **Databento limit set to 500**: a conservative daily budget. Databento
  is usage-based (per GB), not strictly call-limited, so this is a
  spending guardrail rather than a hard API limit. Adjust as needed.
- **Thread-safe**: uses a `Lock` for safety under concurrent requests.
- **No persistence**: counter resets on restart, which is fine because
  the cache prevents most calls. With a 90%+ cache hit rate, actual
  provider calls are in single digits per day.
- **Fail-fast**: raises `RateLimitError` immediately when limit is hit,
  which the chart endpoint surfaces as HTTP 429.

### Provider Integration

Each provider calls `check_and_increment()` at the start of `fetch_ohlcv`:

```python
# In DabentoProvider.fetch_ohlcv:
from backend.services.providers.rate_limit import databento_counter
databento_counter.check_and_increment()

# In TiingoProvider.fetch_ohlcv:
from backend.services.providers.rate_limit import tiingo_counter
tiingo_counter.check_and_increment()
```

### Chart Endpoint Error Handling

```python
# In backend/api/groups.py
from backend.services.providers.rate_limit import RateLimitError

try:
    bars = provider.fetch_ohlcv(...)
except RateLimitError:
    raise HTTPException(status_code=429, detail="Provider rate limit exceeded. Try again tomorrow.")
except ProviderError as e:
    raise HTTPException(status_code=502, detail=str(e))
```

---

## Error Hierarchy

```python
# backend/services/providers/errors.py

class ProviderError(Exception):
    """Base exception for provider errors."""
    pass

class ProviderAuthError(ProviderError):
    """Authentication failed."""
    pass

class ProviderDataError(ProviderError):
    """No data available for symbol/range."""
    pass

# RateLimitError is in rate_limit.py (not a ProviderError subclass,
# since it's a local safety check, not a remote provider failure)
```

---

## Symbol Mapping

### Databento (Futures)

| Trading Symbol | Databento Symbol | Notes |
|---------------|------------------|-------|
| `MESZ5` | `MES` | Micro E-mini S&P 500 |
| `ESZ24` | `ES` | E-mini S&P 500 |
| `NQH5` | `NQ` | E-mini Nasdaq-100 |
| `MNQZ5` | `MNQ` | Micro E-mini Nasdaq |

Uses `stype_in="parent"` for continuous front-month contracts. The existing
`normalize_futures_symbol()` handles stripping the month/year suffix.

**Known limitation:** Databento applies ratio back-adjustment for continuous
contracts. Near roll dates the chart price may differ slightly from execution
price. Trade markers use the actual execution price from the database.

### Tiingo (Stocks)

Direct mapping -- `AAPL` -> `AAPL`. No transformation needed. All prices use
split- and dividend-adjusted values.

---

## PostgreSQL Cache

### Table Design

```sql
CREATE TABLE ohlcv_cache (
    symbol VARCHAR(50) NOT NULL,
    interval VARCHAR(10) NOT NULL,
    bar_time TIMESTAMP WITH TIME ZONE NOT NULL,

    open NUMERIC(18, 8) NOT NULL,
    high NUMERIC(18, 8) NOT NULL,
    low NUMERIC(18, 8) NOT NULL,
    close NUMERIC(18, 8) NOT NULL,
    volume BIGINT NOT NULL,

    provider VARCHAR(20) NOT NULL,
    asset_class VARCHAR(20) NOT NULL,

    PRIMARY KEY (symbol, interval, bar_time)
);

CREATE INDEX idx_ohlcv_cache_symbol_interval
    ON ohlcv_cache (symbol, interval, bar_time DESC);
```

No `fetched_at` column -- completed bars are immutable and cached permanently.
No staleness checks, no cleanup jobs.

### ORM Model

```python
# backend/models/ohlcv_cache.py

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Numeric, String, BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class OHLCVCache(Base):
    """Cached OHLCV bar data from market data providers.

    Stores only completed bars. Keyed by (symbol, interval, bar_time).
    """

    __tablename__ = "ohlcv_cache"
    __table_args__ = (
        Index("idx_ohlcv_cache_symbol_interval", "symbol", "interval", "bar_time"),
    )

    symbol: Mapped[str] = mapped_column(String(50), primary_key=True)
    interval: Mapped[str] = mapped_column(String(10), primary_key=True)
    bar_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)

    open: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)

    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    asset_class: Mapped[str] = mapped_column(String(20), nullable=False)
```

### Cache Service

```python
# backend/services/cache/ohlcv_cache.py

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import structlog
from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from backend.models.ohlcv_cache import OHLCVCache
from backend.services.market_data import OHLCVBar
from backend.services.providers.validation import validate_bar

logger = structlog.get_logger(__name__)

# Interval -> bar duration (for in-progress bar filtering)
_INTERVAL_DURATIONS: dict[str, timedelta] = {
    "1m": timedelta(minutes=1),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "1d": timedelta(days=1),
}


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
        bar_duration = _INTERVAL_DURATIONS.get(interval, timedelta(hours=1))
        last_bar_time = rows[-1].bar_time
        now = datetime.now(timezone.utc)
        expected_end = min(end, now - bar_duration)  # can't expect in-progress bars
        if last_bar_time + bar_duration * 2 < expected_end:
            return None  # partial coverage, re-fetch

        return [self._to_bar(row) for row in rows]

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
        bar_duration = _INTERVAL_DURATIONS.get(interval, timedelta(hours=1))
        values = []

        for bar in bars:
            if not validate_bar(bar):
                logger.warning("cache_put_invalid_bar_skipped", symbol=symbol, time=bar.time)
                continue

            bar_time = datetime.fromtimestamp(bar.time, tz=timezone.utc)

            # Skip in-progress bars: if bar_time + duration > now, the
            # candle hasn't closed yet.
            if bar_time + bar_duration > now:
                continue

            values.append({
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
            })

        if not values:
            return

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

    def _query_rows(self, symbol: str, interval: str, start: datetime, end: datetime) -> list[OHLCVCache]:
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
        return OHLCVBar(
            time=int(row.bar_time.timestamp()),
            open=row.open, high=row.high,
            low=row.low, close=row.close,
            volume=row.volume,
        )
```

---

## API Changes

### Chart Endpoint Update

```python
# backend/api/groups.py (modified excerpt)

from backend.services.cache.ohlcv_cache import OHLCVCacheService
from backend.services.providers.databento_provider import DabentoProvider
from backend.services.providers.tiingo_provider import TiingoProvider
from backend.services.providers.errors import ProviderError


def _get_provider(asset_class: str) -> MarketDataProvider:
    """Pick provider by asset class."""
    if asset_class == "future":
        return DabentoProvider()
    elif asset_class in ("stock", "option"):
        return TiingoProvider()
    else:
        raise ProviderError(f"No provider for asset_class={asset_class}")


@router.get("/{group_id}/chart", response_model=GroupChartResponse)
def get_group_chart(
    group_id: uuid.UUID,
    interval: str | None = Query(None, pattern=r"^(1m|5m|15m|1h|1d)$"),
    padding: int = Query(20, ge=0, le=200),
    db: Session = Depends(get_db),
) -> GroupChartResponse:
    # ... existing group loading code ...

    cache = OHLCVCacheService(db)

    # 1. Try cache
    bars = cache.get(display_symbol, resolved_interval, start, end)

    if bars is None:
        # 2. Fetch from provider (fail-fast on error)
        provider = _get_provider(group.asset_class)
        bars = provider.fetch_ohlcv(
            group.symbol, group.asset_class, resolved_interval, start, end,
        )

        # 3. Cache completed bars
        if bars:
            provider_tag = provider.__class__.__name__.lower().replace("provider", "")
            cache.put(display_symbol, resolved_interval, group.asset_class, provider_tag, bars)

    # ... rest unchanged ...
```

### Cache Invalidation Endpoint

```python
# backend/api/market_data.py

@router.delete("/cache")
def invalidate_cache(
    symbol: str | None = Query(None),
    interval: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Admin endpoint to invalidate OHLCV cache."""
    cache = OHLCVCacheService(db)
    deleted = cache.invalidate(symbol=symbol, interval=interval)
    return {"deleted": deleted}
```

---

## Configuration

```python
# backend/config/base.py additions

class BaseAppSettings(BaseSettings):
    # Databento
    databento_api_key: str = ""

    # Tiingo
    tiingo_api_key: str = ""

    # Cache
    ohlcv_cache_enabled: bool = True
```

```env
# .env
DATABENTO_API_KEY=db-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TIINGO_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
OHLCV_CACHE_ENABLED=true
```

---

## Migration Plan

### Phase 1: Database

Alembic migration for `ohlcv_cache` table:

```python
# backend/migrations/versions/006_ohlcv_cache.py

"""Add OHLCV cache table.

Revision ID: 006
Revises: 005
Create Date: 2026-02-21
"""
from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ohlcv_cache",
        sa.Column("symbol", sa.String(50), nullable=False),
        sa.Column("interval", sa.String(10), nullable=False),
        sa.Column("bar_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(18, 8), nullable=False),
        sa.Column("high", sa.Numeric(18, 8), nullable=False),
        sa.Column("low", sa.Numeric(18, 8), nullable=False),
        sa.Column("close", sa.Numeric(18, 8), nullable=False),
        sa.Column("volume", sa.BigInteger, nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("asset_class", sa.String(20), nullable=False),
        sa.PrimaryKeyConstraint("symbol", "interval", "bar_time"),
    )
    op.create_index(
        "idx_ohlcv_cache_symbol_interval",
        "ohlcv_cache",
        ["symbol", "interval", "bar_time"],
    )

def downgrade() -> None:
    op.drop_index("idx_ohlcv_cache_symbol_interval")
    op.drop_table("ohlcv_cache")
```

### Phase 2: Providers

1. Create `backend/services/providers/` package
2. Implement `validation.py`, `errors.py`
3. Implement `DabentoProvider`, `TiingoProvider`
4. Implement `OHLCVCacheService`

### Phase 3: Integration

1. Update `backend/api/groups.py` chart endpoint
2. Add config to `backend/config/base.py`
3. Remove `YFinanceProvider` usage from chart endpoint

### Phase 4: Testing & Cleanup

1. Add unit/integration tests
2. Remove yfinance dependency from `pyproject.toml`
3. Deploy

---

## Data Gap Handling

- **Provider layer**: Gaps are passed through as-is; no synthetic bars.
- **Cache layer**: Stores exactly what the provider returns.
- **Frontend**: lightweight-charts handles gaps natively as visual gaps.

---

## Testing Strategy

### Provider Tests

```python
class TestDabentoProvider:
    def test_resolve_symbol_future(self, provider):
        assert provider._resolve_symbol("MESZ5", "future") == "MES"

    def test_rejects_non_future(self, provider):
        with pytest.raises(ValueError):
            provider.fetch_ohlcv("AAPL", "stock", "1d", start, end)

    @patch("databento.Historical")
    def test_fetch_ohlcv_success(self, mock_client, provider):
        ...  # verify bars returned from mock

    @patch("databento.Historical")
    def test_empty_response(self, mock_client, provider):
        ...  # verify empty list returned
```

### Validation Tests

```python
class TestBarValidation:
    def test_valid_bar(self): ...
    def test_high_below_low(self): ...
    def test_negative_volume(self): ...
    def test_zero_price(self): ...
```

### Cache Tests

```python
class TestOHLCVCacheService:
    def test_put_and_get(self, cache): ...
    def test_cache_miss_returns_none(self, cache): ...
    def test_in_progress_bar_not_cached(self, cache): ...
    def test_partial_coverage_returns_none(self, cache): ...
    def test_invalidation(self, cache): ...
    def test_invalid_bar_skipped_on_put(self, cache): ...
```

### Chart Endpoint Tests

```python
class TestChartEndpoint:
    def test_cache_hit_skips_provider(self, db_session): ...
    def test_cache_miss_fetches_and_caches(self, db_session): ...
    def test_provider_error_returns_502(self, db_session): ...
    def test_rate_limit_returns_429(self, db_session): ...
```

### Rate Limit Tests

```python
class TestDailyCallCounter:
    def test_increments_and_tracks(self): ...
    def test_raises_when_limit_exceeded(self): ...
    def test_resets_on_new_day(self): ...
    def test_remaining_reflects_usage(self): ...
```

---

## Cost Analysis

### Databento

Usage-based at ~$0.50/GB. With 90% cache hit rate and ~50 chart views/day,
estimated monthly data transfer is ~7.5MB. **Monthly cost: < $0.01.**

### Tiingo

Free tier: 500 calls/day, end-of-day data only. With caching, ~5 API
calls/day for 50 chart views. **Monthly cost: $0 (free tier).** The daily
call counter is set to 400 as a safety margin.

Intraday stock data requires IEX subscription (~$10/month) if needed.

### Cache Storage

- 10 futures symbols at 5m: ~752MB/year
- 50 stock symbols at 1d: ~2MB/year
- PostgreSQL handles this easily with proper indexing

---

## Summary

This design introduces:

1. **Two trusted providers**: `DabentoProvider` (futures) + `TiingoProvider` (stocks)
2. **PostgreSQL cache**: Completed bars stored permanently, no expiry
3. **In-progress bar filtering**: `bar_time + interval_duration > now` -> skip
4. **Fail-fast errors**: Provider failures propagate directly as HTTP 502
5. **Simple rate limiting**: Daily call counter per provider (400/day Tiingo, 500/day Databento)
6. **Bar validation**: Rejects invalid OHLCV data before caching
7. **UTC normalization**: Explicit conversion in all providers
8. **Adjusted prices**: Split/dividend-adjusted stock prices via Tiingo
9. **Minimal API changes**: Only the provider instantiation changes in the chart endpoint
