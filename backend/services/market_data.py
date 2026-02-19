"""Market data provider for OHLCV candle data.

Implements a protocol-based abstraction over market data sources.
The default provider uses yfinance for development; the protocol
allows swapping to Twelve Data, IBKR, or other sources later.
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
    normalized = d.normalize()
    # normalize() may use exponent notation; to_integral_value check + fixed-point
    return format(normalized, "f")

# ---------------------------------------------------------------------------
# Role color constants for trade markers (lightweight-charts format)
# ---------------------------------------------------------------------------

# Long direction: entry/add are green shades, trim/exit are red shades
ROLE_COLORS_LONG: dict[str, str] = {
    "entry": "#22c55e",
    "add": "#86efac",
    "trim": "#fca5a5",
    "exit": "#ef4444",
}

# Short direction: entry/add are red shades (opening short), trim/exit are green shades (covering)
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

    Implementations must return a list of OHLCVBar for the requested
    symbol, interval, and time range.
    """

    def fetch_ohlcv(
        self,
        symbol: str,
        interval: str,
        start: datetime,
        end: datetime,
    ) -> list[OHLCVBar]: ...


# ---------------------------------------------------------------------------
# In-memory TTL cache for OHLCV data
# ---------------------------------------------------------------------------

# Max 256 entries, 10-minute TTL for development usage
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

    Suitable for development and personal use. Not rate-limited but
    relies on an unofficial Yahoo Finance API.
    """

    def fetch_ohlcv(
        self,
        symbol: str,
        interval: str,
        start: datetime,
        end: datetime,
    ) -> list[OHLCVBar]:
        """Fetch OHLCV bars from Yahoo Finance.

        Args:
            symbol: Ticker symbol (e.g. ``"AAPL"``).
            interval: Bar interval (``"1m"``, ``"5m"``, ``"15m"``, ``"1h"``, ``"1d"``).
            start: Start of the time range (inclusive, UTC).
            end: End of the time range (inclusive, UTC).

        Returns:
            Ordered list of OHLCVBar from oldest to newest.
        """
        key = _cache_key(symbol, interval, start, end)
        cached = _ohlcv_cache.get(key)
        if cached is not None:
            logger.debug(
                "ohlcv_cache_hit",
                symbol=symbol,
                interval=interval,
            )
            return cached

        import yfinance as yf  # noqa: PLC0415 — lazy import

        logger.info(
            "fetching_ohlcv",
            symbol=symbol,
            interval=interval,
            start=start.isoformat(),
            end=end.isoformat(),
        )

        ticker = yf.Ticker(symbol)
        df = ticker.history(interval=interval, start=start, end=end)

        if df.empty:
            logger.warning("ohlcv_empty_response", symbol=symbol, interval=interval)
            return []

        bars: list[OHLCVBar] = []
        for row in df.itertuples():
            # row.Index is a pandas Timestamp
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
            symbol=symbol,
            interval=interval,
            bar_count=len(bars),
        )
        return bars


# ---------------------------------------------------------------------------
# Symbol resolution for yfinance
# ---------------------------------------------------------------------------


def resolve_yfinance_symbol(symbol: str, asset_class: str) -> str:
    """Resolve a trading symbol to its yfinance-compatible ticker.

    For futures, normalizes the contract symbol (e.g. ``MESZ5`` -> ``MES``)
    then appends ``=F`` for yfinance's continuous front-month convention.
    For all other asset classes, returns the symbol unchanged.

    Args:
        symbol: Raw symbol from the database (e.g. ``"MESZ5"``, ``"AAPL"``).
        asset_class: Asset class string (``"future"``, ``"stock"``, etc.).

    Returns:
        A yfinance-compatible ticker string.
    """
    if asset_class == "future":
        base = normalize_futures_symbol(symbol, asset_class)
        return f"{base}=F"
    return symbol


# ---------------------------------------------------------------------------
# Interval auto-selection
# ---------------------------------------------------------------------------


def choose_interval(opened_at: datetime, closed_at: datetime | None) -> str:
    """Select an appropriate K-line interval based on trade duration.

    The interval is chosen primarily by trade duration, then raised if
    needed to respect yfinance's historical data availability limits:

    - ``1m``: ~7 days back
    - ``5m`` / ``15m``: ~60 days back
    - ``1h``: ~730 days back
    - ``1d``: unlimited

    Args:
        opened_at: When the trade group was opened.
        closed_at: When the trade group was closed, or ``None`` if still open.

    Returns:
        An interval string compatible with yfinance
        (``"1m"``, ``"5m"``, ``"15m"``, ``"1h"``, or ``"1d"``).
    """
    # Match tz-awareness of the input timestamps (SQLite strips tzinfo)
    if opened_at.tzinfo:
        now = datetime.now(UTC)
    else:
        now = datetime.utcnow()  # noqa: DTZ003
    duration = (closed_at or now) - opened_at

    # Primary selection based on trade duration
    if duration < timedelta(hours=2):
        interval = "1m"
    elif duration < timedelta(hours=8):
        interval = "5m"
    elif duration < timedelta(days=3):
        interval = "15m"
    elif duration < timedelta(days=30):
        interval = "1h"
    else:
        interval = "1d"

    # Enforce minimum interval based on data age (yfinance availability limits)
    age = now - opened_at
    if age > timedelta(days=730):
        return max(interval, "1d", key=_INTERVAL_RANK.get)
    if age > timedelta(days=60):
        return max(interval, "1h", key=_INTERVAL_RANK.get)
    if age > timedelta(days=7):
        return max(interval, "5m", key=_INTERVAL_RANK.get)
    return interval


# ---------------------------------------------------------------------------
# Interval -> approximate bar duration mapping
# ---------------------------------------------------------------------------

_INTERVAL_RANK: dict[str, int] = {
    "1m": 0,
    "5m": 1,
    "15m": 2,
    "1h": 3,
    "1d": 4,
}

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
        A ``(start, end)`` tuple of timezone-aware datetimes.
    """
    bar_duration = _INTERVAL_DURATIONS.get(interval, timedelta(hours=1))
    pad = bar_duration * padding

    start = opened_at - pad
    end = (closed_at or datetime.now(UTC)) + pad

    # Clamp end to now so we never request future data from yfinance.
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

        # Arrow shape always follows trade side: buy=arrowUp, sell=arrowDown.
        # Position depends on direction:
        #   Long:  buy (entry/add) below bar, sell (trim/exit) above bar.
        #   Short: sell (entry/add) below bar, buy (trim/exit) above bar.
        shape = "arrowUp" if is_buy else "arrowDown"

        if direction == "long":
            position = "belowBar" if is_buy else "aboveBar"
        else:
            position = "aboveBar" if is_buy else "belowBar"

        color = colors.get(leg.role, "#9ca3af")  # fallback grey

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
