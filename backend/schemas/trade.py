"""Trade-related Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class NormalizedTrade(BaseModel):
    """Normalized trade record produced by all ingesters.

    This is the canonical schema that sits between normalization and deduplication.
    All ingesters must produce this type.
    """

    broker: Literal["ibkr", "tradovate"]
    broker_exec_id: str
    account_id: str
    symbol: str
    underlying: str | None = None
    asset_class: Literal["stock", "future", "option", "forex"]
    side: str
    quantity: Decimal
    price: Decimal
    commission: Decimal = Decimal("0")
    executed_at: datetime  # must be UTC
    order_id: str | None = None
    exchange: str | None = None
    currency: str = "USD"
    raw_data: dict = Field(default_factory=dict)


class TradeResponse(BaseModel):
    """Single trade in API response."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    broker: str
    broker_exec_id: str
    import_log_id: uuid.UUID | None = None
    account_id: str
    symbol: str
    underlying: str | None = None
    asset_class: str
    side: str
    quantity: Decimal
    price: Decimal
    commission: Decimal
    executed_at: datetime
    order_id: str | None = None
    exchange: str | None = None
    currency: str
    raw_data: dict | None = None
    created_at: datetime
    updated_at: datetime


class TradeListResponse(BaseModel):
    """Paginated list of trades."""

    trades: list[TradeResponse]
    total: int
    page: int
    per_page: int
    pages: int


class TradeSummaryResponse(BaseModel):
    """Aggregated trade statistics for a filtered scope."""

    total_trades: int
    total_quantity: Decimal
    total_commissions: Decimal
    gross_pnl: Decimal
    net_pnl: Decimal
