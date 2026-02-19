"""Chart-related Pydantic schemas for the group chart API."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class MarkerData(BaseModel):
    """A single trade marker for lightweight-charts ``setMarkers()``."""

    time: int
    position: str  # "aboveBar" | "belowBar"
    color: str
    shape: str  # "arrowUp" | "arrowDown"
    text: str
    role: str  # "entry" | "add" | "trim" | "exit"
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
