"""Cached OHLCV bar data from market data providers.

Stores only completed bars. Keyed by (symbol, interval, bar_time).
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Index, Numeric, String
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
