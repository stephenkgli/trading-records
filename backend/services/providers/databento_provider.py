"""Market data provider for CME futures via Databento.

Uses the GLBX.MDP3 dataset for CME Globex data. Prefers native OHLCV
schemas at the requested interval to minimize data transfer costs.

Contract roll handling:
- Uses ``stype_in="continuous"`` with ``ROOT.c.0`` symbols for
  continuous front-month contracts.
- Unlike ``parent`` stype which can mix ticks from both the expiring
  and incoming contracts during roll periods (causing dual-track
  OHLC bars), ``continuous`` ensures each bar contains data from
  only one contract at a time.
"""

from datetime import datetime, timezone
from decimal import Decimal

import databento as db
import structlog

from backend.config import settings
from backend.services.market_data import MarketDataProvider, OHLCVBar
from backend.services.providers.errors import ProviderAuthError, ProviderError
from backend.services.providers.rate_limit import databento_counter
from backend.services.providers.validation import filter_outlier_bars, validate_bar

logger = structlog.get_logger(__name__)


class DabentoProvider:
    """Market data provider for CME futures via Databento.

    Uses the GLBX.MDP3 dataset for CME Globex data. Prefers native OHLCV
    schemas at the requested interval to minimize data transfer costs.

    Contract roll handling:
    - Uses ``stype_in="continuous"`` with ``ROOT.c.0`` for front-month.
    - This avoids dual-track OHLC bars during contract rolls that
      ``parent`` stype produces when mixing expiring/incoming ticks.
    """

    DATASET = "GLBX.MDP3"

    INTERVAL_SCHEMA_MAP: dict[str, tuple[str, bool]] = {
        "1m": ("ohlcv-1m", False),
        "5m": ("ohlcv-1m", True),  # Resample 1m -> 5m
        "15m": ("ohlcv-1m", True),  # Resample 1m -> 15m
        "1h": ("ohlcv-1h", False),
        "1d": ("ohlcv-1d", False),
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
        """Map a trading symbol to Databento continuous contract format.

        Uses ``ROOT.c.0`` (calendar roll, front-month rank 0) with
        ``stype_in="continuous"``.  This ensures each OHLCV bar
        contains data from only a single contract, avoiding the
        dual-track price issue that ``parent`` stype produces during
        roll periods.
        """
        from backend.utils.symbol import normalize_futures_symbol

        root = normalize_futures_symbol(symbol, asset_class)
        return f"{root}.c.0"

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

        databento_counter.check_and_increment()

        db_symbol = self._resolve_symbol(symbol, asset_class)
        schema_info = self.INTERVAL_SCHEMA_MAP.get(interval, ("ohlcv-1h", False))
        schema, needs_resample = schema_info

        try:
            data = self.client.timeseries.get_range(
                dataset=self.DATASET,
                symbols=db_symbol,
                schema=schema,
                stype_in="continuous",
                start=start.isoformat(),
                end=end.isoformat(),
            )

            df = data.to_df()
        except Exception as exc:
            logger.error(
                "databento_api_error",
                symbol=db_symbol,
                interval=interval,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            if "auth" in str(exc).lower() or "key" in str(exc).lower():
                raise ProviderAuthError(f"Databento auth failed: {exc}") from exc
            raise ProviderError(f"Databento API error: {exc}") from exc
        if df.empty:
            return []

        if needs_resample:
            rule = self.RESAMPLE_RULES.get(interval)
            if rule:
                if len(df) > self.RESAMPLE_WARN_THRESHOLD:
                    logger.warning("large_resample_dataset", symbol=db_symbol, rows=len(df))
                df = df.resample(rule).agg(
                    {
                        "open": "first",
                        "high": "max",
                        "low": "min",
                        "close": "last",
                        "volume": "sum",
                    }
                ).dropna()

        bars = self._to_bars(df)
        # 跨 Bar 统计学异常检测：移除偏离中位数过大的毛刺
        return filter_outlier_bars(bars)

    def _to_bars(self, df) -> list[OHLCVBar]:
        bars: list[OHLCVBar] = []
        for row in df.itertuples():
            # Skip zero-volume bars: these appear during contract rolls
            # and CME maintenance windows with unreliable prices.
            if int(row.volume) == 0:
                continue

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
