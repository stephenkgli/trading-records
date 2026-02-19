"""Market data provider for OHLCV candle data.

Implements a protocol-based abstraction over market data sources.
The default provider uses yfinance; the protocol allows swapping
to Twelve Data, IBKR, or other sources by implementing
``MarketDataProvider``.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Protocol

import structlog
from cachetools import TTLCache
from pydantic import BaseModel

from backend.utils.symbol import normalize_futures_symbol

logger = structlog.get_logger(__name__)


def _format_decimal(d: Decimal) -> str:
    """Format a Decimal value without trailing zeros or scientific notation.

    ``Decimal.normalize()`` can produce scientific notation (e.g. ``5E+1``),
    so this function converts the normalized value back to fixed-point.
    """
    return format(d.normalize(), "f")


# ---------------------------------------------------------------------------
# Interval mapping: asset_class -> default K-line interval
# ---------------------------------------------------------------------------

ASSET_CLASS_INTERVALS: dict[str, str] = {
    "future": "5m",
    "stock": "1d",
    "option": "1d",
    "forex": "1h",
}


def default_interval(asset_class: str) -> str:
    """Return the default K-line interval for a given asset class."""
    return ASSET_CLASS_INTERVALS.get(asset_class, "1d")


# ---------------------------------------------------------------------------
# Role color constants for trade markers (lightweight-charts format)
# ---------------------------------------------------------------------------

ROLE_COLORS_LONG: dict[str, str] = {
    "entry": "#22c55e",
    "add": "#86efac",
    "trim": "#fca5a5",
    "exit": "#ef4444",
}

ROLE_COLORS_SHORT: dict[str, str] = {
    "entry": "#ef4444",
    "add": "#fca5a5",
    "trim": "#86efac",
    "exit": "#22c55e",
}


# ---------------------------------------------------------------------------
# OHLCV bar model
# ---------------------------------------------------------------------------


class OHLCVBar(BaseModel):
    """Single OHLCV candlestick bar for charting."""

    time: int  # Unix timestamp (seconds)
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


# ---------------------------------------------------------------------------
# Market data provider protocol
# ---------------------------------------------------------------------------


class MarketDataProvider(Protocol):
    """Protocol for market data providers.

    Implementations must accept a *raw* trading symbol plus asset_class
    and handle any provider-specific symbol mapping internally.
    """

    def fetch_ohlcv(
        self,
        symbol: str,
        asset_class: str,
        interval: str,
        start: datetime,
        end: datetime,
    ) -> list[OHLCVBar]: ...


# ---------------------------------------------------------------------------
# In-memory TTL cache for OHLCV data
# ---------------------------------------------------------------------------

_ohlcv_cache: TTLCache[str, list[OHLCVBar]] = TTLCache(maxsize=256, ttl=600)


def _cache_key(symbol: str, interval: str, start: datetime, end: datetime) -> str:
    """Build a deterministic cache key for an OHLCV request."""
    raw = f"{symbol}|{interval}|{start.isoformat()}|{end.isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()


# ---------------------------------------------------------------------------
# YFinance provider implementation
# ---------------------------------------------------------------------------


class YFinanceProvider:
    """Market data provider backed by yfinance.

    Handles provider-specific symbol mapping internally:
    - futures ``MESZ5`` -> ``MES=F``
    - other asset classes: symbol as-is.
    """

    @staticmethod
    def _resolve_symbol(symbol: str, asset_class: str) -> str:
        """Map a raw trading symbol to a yfinance-compatible ticker."""
        if asset_class == "future":
            base = normalize_futures_symbol(symbol, asset_class)
            return f"{base}=F"
        return symbol

    def fetch_ohlcv(
        self,
        symbol: str,
        asset_class: str,
        interval: str,
        start: datetime,
        end: datetime,
    ) -> list[OHLCVBar]:
        """Fetch OHLCV bars from Yahoo Finance.

        Args:
            symbol: Raw ticker symbol from the DB (e.g. ``"MESZ5"``, ``"AAPL"``).
            asset_class: Asset class (``"future"``, ``"stock"``, etc.).
            interval: Bar interval (``"5m"``, ``"1d"``, etc.).
            start: Start of the time range (inclusive, UTC).
            end: End of the time range (inclusive, UTC).

        Returns:
            Ordered list of OHLCVBar from oldest to newest.
        """
        yf_symbol = self._resolve_symbol(symbol, asset_class)

        key = _cache_key(yf_symbol, interval, start, end)
        cached = _ohlcv_cache.get(key)
        if cached is not None:
            logger.debug("ohlcv_cache_hit", symbol=yf_symbol, interval=interval)
            return cached

        import yfinance as yf  # noqa: PLC0415 — lazy import

        logger.info(
            "fetching_ohlcv",
            symbol=yf_symbol,
            interval=interval,
            start=start.isoformat(),
            end=end.isoformat(),
        )

        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(interval=interval, start=start, end=end)

        if df.empty:
            logger.warning("ohlcv_empty_response", symbol=yf_symbol, interval=interval)
            return []

        bars: list[OHLCVBar] = []
        for row in df.itertuples():
            ts = int(row.Index.timestamp())
            bars.append(
                OHLCVBar(
                    time=ts,
                    open=Decimal(str(row.Open)),
                    high=Decimal(str(row.High)),
                    low=Decimal(str(row.Low)),
                    close=Decimal(str(row.Close)),
                    volume=int(row.Volume),
                )
            )

        _ohlcv_cache[key] = bars
        logger.info(
            "ohlcv_fetched",
            symbol=yf_symbol,
            interval=interval,
            bar_count=len(bars),
        )
        return bars


# ---------------------------------------------------------------------------
# Interval -> approximate bar duration mapping
# ---------------------------------------------------------------------------

_INTERVAL_DURATIONS: dict[str, timedelta] = {
    "1m": timedelta(minutes=1),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "1d": timedelta(days=1),
}


def compute_padded_range(
    opened_at: datetime,
    closed_at: datetime | None,
    interval: str,
    padding: int,
) -> tuple[datetime, datetime]:
    """Compute a padded time range for OHLCV data fetching.

    Extends the trade group's time range by ``padding`` bars on each side
    so that the chart shows context before and after the trade.

    Args:
        opened_at: Group open timestamp.
        closed_at: Group close timestamp (or ``None`` for open groups).
        interval: The bar interval string.
        padding: Number of extra bars on each side.

    Returns:
        A ``(start, end)`` tuple of datetimes.
    """
    bar_duration = _INTERVAL_DURATIONS.get(interval, timedelta(hours=1))
    pad = bar_duration * padding

    start = opened_at - pad
    end = (closed_at or datetime.now(UTC)) + pad

    # Clamp end to now so we never request future data from providers.
    # Use tz-aware or naive now to match the input timestamps.
    now = datetime.now(UTC) if end.tzinfo else datetime.utcnow()  # noqa: DTZ003
    if end > now:
        end = now

    return start, end


# ---------------------------------------------------------------------------
# Marker generation
# ---------------------------------------------------------------------------


def build_markers(
    legs: list,  # list of TradeGroupLeg ORM objects (with .trade loaded)
    direction: str,
) -> list[dict]:
    """Convert trade group legs into lightweight-charts marker dicts.

    Each marker includes time, position, color, shape, text, role, and
    trade_id fields ready for the frontend ``setMarkers()`` API.

    Args:
        legs: TradeGroupLeg objects with eagerly loaded ``.trade`` relationships.
        direction: ``"long"`` or ``"short"``.

    Returns:
        List of marker dicts sorted by trade execution time.
    """
    colors = ROLE_COLORS_LONG if direction == "long" else ROLE_COLORS_SHORT
    markers: list[dict] = []

    for leg in sorted(legs, key=lambda lg: lg.trade.executed_at):
        trade = leg.trade
        is_buy = trade.side == "buy"

        shape = "arrowUp" if is_buy else "arrowDown"

        if direction == "long":
            position = "belowBar" if is_buy else "aboveBar"
        else:
            position = "aboveBar" if is_buy else "belowBar"

        color = colors.get(leg.role, "#9ca3af")

        qty = _format_decimal(trade.quantity)
        px = _format_decimal(trade.price)
        markers.append(
            {
                "time": int(trade.executed_at.timestamp()),
                "position": position,
                "color": color,
                "shape": shape,
                "text": f"{leg.role.upper()} {qty} @ {px}",
                "role": leg.role,
                "trade_id": str(trade.id),
            }
        )

    return markers
