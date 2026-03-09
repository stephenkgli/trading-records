"""Market data provider for OHLCV candle data.

Implements a protocol-based abstraction over market data sources.
Providers (Databento for futures, Tiingo for stocks) implement
the ``MarketDataProvider`` protocol. A PostgreSQL cache layer
(``OHLCVCacheService``) stores completed bars permanently.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Protocol

import structlog
from pydantic import BaseModel

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
# Interval -> approximate bar duration mapping
# ---------------------------------------------------------------------------

INTERVAL_DURATIONS: dict[str, timedelta] = {
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
    bar_duration = INTERVAL_DURATIONS.get(interval, timedelta(hours=1))
    pad = bar_duration * padding

    start = opened_at - pad
    end = (closed_at or datetime.now(UTC)) + pad

    # Clamp end to now so we never request future data from providers.
    # SQLite returns naive datetimes, so handle both cases.
    if end.tzinfo is None:
        now = datetime.now(UTC).replace(tzinfo=None)
    else:
        now = datetime.now(UTC)
    if end > now:
        end = now

    return start, end


# ---------------------------------------------------------------------------
# Marker generation
# ---------------------------------------------------------------------------


def _snap_to_bar(marker_ts: int, bar_times: list[int]) -> int:
    """将 marker 时间戳 snap 到它所属的 K 线 bar 时间。

    核心逻辑：找到 bar_time <= marker_ts 的最大 bar_time，即交易发生时所属
    的那根 K 线。例如交易在 22:04:17 执行，5 分钟 K 线间距下应 snap 到
    22:00:00 的 bar（而不是距离更近的 22:05:00）。

    特殊处理：当 marker 落在 K 线缺口中（如 CME 维护窗口 21:00-22:00 UTC
    造成的 65 分钟缺口）时，marker 与左侧 bar 的距离会远超正常 bar 间距。
    此时改为 snap 到缺口后的第一根 bar，因为交易实际上是在市场恢复后成交的。

    bar_times 为空时原样返回。
    """
    if not bar_times:
        return marker_ts

    # bar_times 已经按升序排列（来自 OHLCV 数据）
    # 二分查找最后一个 <= marker_ts 的 bar_time
    lo, hi = 0, len(bar_times) - 1
    left_idx = -1  # 最后一个 <= marker_ts 的索引
    while lo <= hi:
        mid = (lo + hi) // 2
        if bar_times[mid] <= marker_ts:
            left_idx = mid
            lo = mid + 1
        else:
            hi = mid - 1

    # 边界情况：marker 比所有 bar 都早
    if left_idx < 0:
        return bar_times[0]

    # right_idx: 第一个 > marker_ts 的索引
    right_idx = left_idx + 1

    # 正常情况：snap 到所属的 bar（left_idx 对应的 bar）
    # 但如果存在 K 线缺口（marker 与 left bar 之间距离远超正常 bar 间距），
    # 则 snap 到缺口后的第一根 bar（right_idx）。
    if right_idx < len(bar_times):
        # 推断正常的 bar 间距（取相邻 bar 的最小间距）
        normal_gap = bar_times[right_idx] - bar_times[left_idx]
        if left_idx > 0:
            prev_gap = bar_times[left_idx] - bar_times[left_idx - 1]
            normal_gap = min(normal_gap, prev_gap)

        left_dist = marker_ts - bar_times[left_idx]
        # 如果与左侧 bar 的距离超过 2 倍正常间距，说明处于缺口中，
        # snap 到右侧 bar（缺口后的第一根）
        if left_dist > normal_gap * 2:
            return bar_times[right_idx]

    return bar_times[left_idx]


def build_markers(
    legs: list,  # list of TradeGroupLeg ORM objects (with .trade loaded)
    bar_times: list[int] | None = None,
) -> list[dict]:
    """Convert trade group legs into lightweight-charts marker dicts.

    Each marker includes time, price, side, text, role, and trade_id
    fields ready for frontend marker layout and rendering.

    When ``bar_times`` is provided, each marker's time will be snapped
    to the candle bar it belongs to (the largest bar_time <= marker_time),
    ensuring markers align correctly on the chart.

    Args:
        legs: TradeGroupLeg objects with eagerly loaded ``.trade`` relationships.
        bar_times: Sorted list of candle bar Unix timestamps (seconds).

    Returns:
        List of marker dicts sorted by trade execution time.
    """
    markers: list[dict] = []

    for leg in sorted(legs, key=lambda lg: lg.trade.executed_at):
        trade = leg.trade
        side = "buy" if trade.side == "buy" else "sell"

        raw_ts = int(trade.executed_at.timestamp())
        snapped_ts = _snap_to_bar(raw_ts, bar_times or [])

        qty = _format_decimal(trade.quantity)
        markers.append(
            {
                "time": snapped_ts,
                "price": float(trade.price),
                "side": side,
                "text": qty,
                "role": leg.role,
                "trade_id": str(trade.id),
            }
        )

    return markers
