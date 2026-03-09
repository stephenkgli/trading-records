"""TradeGroup and TradeGroupLeg ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class TradeGroup(Base):
    """A round-trip trade group (long or short position lifecycle)."""

    __tablename__ = "trade_groups"
    __table_args__ = (
        Index("idx_trade_groups_status", "status"),
        Index("idx_trade_groups_status_closed_at", "status", "closed_at"),
        Index("idx_trade_groups_account_symbol", "account_id", "symbol"),
        Index("idx_trade_groups_account_symbol_status", "account_id", "symbol", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="Scoped per account"
    )
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    asset_class: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="stock | future | option | forex"
    )
    direction: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="long | short"
    )
    strategy_tag: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="Optional user tag"
    )
    status: Mapped[str] = mapped_column(
        String(10), nullable=False, default="open", comment="open | closed"
    )
    realized_pnl: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 8), nullable=True, comment="Null if open"
    )
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="User journal notes"
    )

    # Relationships
    legs = relationship(
        "TradeGroupLeg", back_populates="trade_group", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<TradeGroup(id={self.id}, symbol={self.symbol}, "
            f"direction={self.direction}, status={self.status})>"
        )


class TradeGroupLeg(Base):
    """Links a trade to a trade group with a role."""

    __tablename__ = "trade_group_legs"
    __table_args__ = (
        Index("idx_trade_group_legs_group_id", "trade_group_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    trade_group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trade_groups.id"), nullable=False
    )
    trade_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trades.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="entry | exit | add | trim"
    )

    # Relationships
    trade_group = relationship("TradeGroup", back_populates="legs")
    trade = relationship("Trade", back_populates="group_legs")

    def __repr__(self) -> str:
        return f"<TradeGroupLeg(id={self.id}, role={self.role})>"
