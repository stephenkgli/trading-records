"""Market data provider for US stocks via Tiingo.

Uses adjusted prices (adjOpen/adjHigh/adjLow/adjClose) for accuracy
across splits and dividends.

Free tier supports end-of-day (daily) data only. Intraday requires
IEX subscription (~$10/month).
"""

from datetime import datetime, timezone
from decimal import Decimal

import structlog
from dateutil import parser as dateutil_parser
from tiingo import TiingoClient

from backend.config import settings
from backend.services.market_data import MarketDataProvider, OHLCVBar
from backend.services.providers.errors import ProviderAuthError, ProviderError
from backend.services.providers.rate_limit import tiingo_counter
from backend.services.providers.validation import validate_bar

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
            self._client = TiingoClient({"api_key": self._api_key, "session": True})
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

        tiingo_counter.check_and_increment()

        frequency = {"1d": "daily", "1h": "1Hour", "5m": "5Min", "1m": "1Min"}.get(
            interval, "daily"
        )

        try:
            historical = self.client.get_ticker_price(
                symbol.upper(),
                fmt="json",
                startDate=start.strftime("%Y-%m-%d"),
                endDate=end.strftime("%Y-%m-%d"),
                frequency=frequency,
            )
        except Exception as exc:
            logger.error(
                "tiingo_api_error",
                symbol=symbol,
                interval=interval,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            if "auth" in str(exc).lower() or "key" in str(exc).lower() or "401" in str(exc):
                raise ProviderAuthError(f"Tiingo auth failed: {exc}") from exc
            raise ProviderError(f"Tiingo API error: {exc}") from exc

        if not historical:
            return []

        bars: list[OHLCVBar] = []
        for item in historical:
            dt = dateutil_parser.isoparse(item["date"])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            dt = dt.astimezone(timezone.utc)

            bar = OHLCVBar(
                time=int(dt.timestamp()),
                open=Decimal(str(item.get("adjOpen", item["open"]))),
                high=Decimal(str(item.get("adjHigh", item["high"]))),
                low=Decimal(str(item.get("adjLow", item["low"]))),
                close=Decimal(str(item.get("adjClose", item["close"]))),
                volume=int(item["volume"]),
            )
            if validate_bar(bar):
                bars.append(bar)
            else:
                logger.warning("invalid_bar_skipped", provider="tiingo", time=bar.time)
        return bars
