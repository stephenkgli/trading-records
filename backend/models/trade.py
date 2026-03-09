"""Trade ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class Trade(Base):
    """Normalized trade record from any broker."""

    __tablename__ = "trades"
    __table_args__ = (
        Index("idx_trades_executed_at", "executed_at"),
        Index("idx_trades_symbol_executed_at", "symbol", "executed_at"),
        Index("idx_trades_account_symbol_executed_at", "account_id", "symbol", "executed_at"),
        Index("idx_trades_broker_account", "broker", "account_id"),
        Index("idx_trades_broker_exec_id", "broker", "broker_exec_id", unique=True),
        Index("idx_trades_import_log_id", "import_log_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    broker: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="ibkr | tradovate"
    )
    broker_exec_id: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Broker-native execution ID"
    )
    import_log_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("import_logs.id"),
        nullable=True,
        comment="Source import log",
    )
    account_id: Mapped[str] = mapped_column(String(50), nullable=False)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    underlying: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="For options/futures"
    )
    asset_class: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="stock | future | option | forex"
    )
    side: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="buy | sell"
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    commission: Mapped[Decimal] = mapped_column(
        Numeric(18, 8), nullable=False, default=Decimal("0")
    )
    multiplier: Mapped[Decimal] = mapped_column(
        Numeric(18, 8), nullable=False, default=Decimal("1"),
        comment="Contract multiplier (value per point for futures, 1 for stocks)"
    )
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="Always UTC"
    )
    order_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    exchange: Mapped[str | None] = mapped_column(String(50), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    raw_data: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="Original broker payload"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    import_log = relationship("ImportLog", back_populates="trades", foreign_keys=[import_log_id])
    group_legs = relationship("TradeGroupLeg", back_populates="trade")

    def __repr__(self) -> str:
        return (
            f"<Trade(id={self.id}, broker={self.broker}, "
            f"symbol={self.symbol}, side={self.side}, qty={self.quantity})>"
        )
