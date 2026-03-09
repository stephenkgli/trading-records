"""Chart-related Pydantic schemas for the group chart API."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


TradeRole = Literal["entry", "add", "trim", "exit"]
TradeSide = Literal["buy", "sell"]


class MarkerData(BaseModel):
    """A single trade marker rendered on the K-line chart.

    Contains timestamp, execution price, side, descriptive text,
    the trade role, and the originating trade ID.
    """

    time: int
    price: float
    side: TradeSide
    text: str
    role: TradeRole
    trade_id: uuid.UUID


class GroupChartSummary(BaseModel):
    """Condensed group info included in the chart response."""

    direction: str
    realized_pnl: Decimal | None = None
    opened_at: datetime
    closed_at: datetime | None = None


class CandleBar(BaseModel):
    """A single OHLCV candle bar serialised for JSON charting (float values)."""

    time: int
    open: float
    high: float
    low: float
    close: float
    volume: int


class GroupChartResponse(BaseModel):
    """Response payload for ``GET /api/v1/groups/{group_id}/chart``."""

    symbol: str
    interval: str
    candles: list[CandleBar]
    markers: list[MarkerData]
    group: GroupChartSummary
