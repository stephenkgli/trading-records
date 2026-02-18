"""Trade service — encapsulates trade query logic.

Provides trade listing, detail, and summary operations so API handlers
remain thin request/response mappers.
"""

from __future__ import annotations

import uuid
from datetime import datetime

import structlog
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from backend.models.trade import Trade
from backend.schemas.trade import TradeListResponse, TradeResponse, TradeSummaryResponse

logger = structlog.get_logger(__name__)


class TradeService:
    """Service for trade query operations."""

    def list_trades(
        self,
        db: Session,
        *,
        account_id: str | None = None,
        broker: str | None = None,
        symbol: str | None = None,
        asset_class: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        page: int = 1,
        per_page: int = 50,
        sort: str = "executed_at",
        order: str = "desc",
    ) -> TradeListResponse:
        """List trades with filtering, pagination, and sorting.

        Args:
            db: Database session.
            account_id: Optional account ID filter.
            broker: Optional broker filter.
            symbol: Optional symbol filter.
            asset_class: Optional asset class filter.
            from_date: Optional start date filter.
            to_date: Optional end date filter.
            page: Page number.
            per_page: Results per page.
            sort: Column name to sort by.
            order: Sort order (``"asc"`` or ``"desc"``).

        Returns:
            Paginated trade list response.
        """
        query = select(Trade)

        if account_id:
            query = query.where(Trade.account_id == account_id)
        if broker:
            query = query.where(Trade.broker == broker)
        if symbol:
            query = query.where(Trade.symbol == symbol)
        if asset_class:
            query = query.where(Trade.asset_class == asset_class)
        if from_date:
            query = query.where(Trade.executed_at >= from_date)
        if to_date:
            query = query.where(Trade.executed_at <= to_date)

        count_query = select(func.count()).select_from(query.subquery())
        total = db.execute(count_query).scalar_one()

        sort_column = getattr(Trade, sort, Trade.executed_at)
        if order == "asc":
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())

        offset = (page - 1) * per_page
        query = query.offset(offset).limit(per_page)

        trades = db.execute(query).scalars().all()
        pages = (total + per_page - 1) // per_page if total > 0 else 1

        return TradeListResponse(
            trades=[TradeResponse.model_validate(t) for t in trades],
            total=total,
            page=page,
            per_page=per_page,
            pages=pages,
        )

    def get_trade(self, db: Session, trade_id: uuid.UUID) -> TradeResponse | None:
        """Get a single trade by ID.

        Args:
            db: Database session.
            trade_id: Trade UUID.

        Returns:
            TradeResponse or None if not found.
        """
        trade = db.get(Trade, trade_id)
        if not trade:
            return None
        return TradeResponse.model_validate(trade)

    def get_summary(
        self,
        db: Session,
        *,
        account_id: str | None = None,
        broker: str | None = None,
        symbol: str | None = None,
        asset_class: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> TradeSummaryResponse:
        """Get aggregated trade statistics for a filtered scope.

        Args:
            db: Database session.
            account_id: Optional account filter.
            broker: Optional broker filter.
            symbol: Optional symbol filter.
            asset_class: Optional asset class filter.
            from_date: Optional start date.
            to_date: Optional end date.

        Returns:
            Trade summary statistics.
        """
        pnl_expr = case(
            (Trade.side == "sell", Trade.price * Trade.quantity),
            (Trade.side == "buy", -Trade.price * Trade.quantity),
            else_=0,
        )

        query = select(
            func.count(Trade.id).label("total_trades"),
            func.coalesce(func.sum(Trade.quantity), 0).label("total_quantity"),
            func.coalesce(func.sum(func.abs(Trade.commission)), 0).label("total_commissions"),
            func.coalesce(func.sum(pnl_expr), 0).label("gross_pnl"),
            (
                func.coalesce(func.sum(pnl_expr), 0)
                - func.coalesce(func.sum(func.abs(Trade.commission)), 0)
            ).label("net_pnl"),
        )

        if account_id:
            query = query.where(Trade.account_id == account_id)
        if broker:
            query = query.where(Trade.broker == broker)
        if symbol:
            query = query.where(Trade.symbol == symbol)
        if asset_class:
            query = query.where(Trade.asset_class == asset_class)
        if from_date:
            query = query.where(Trade.executed_at >= from_date)
        if to_date:
            query = query.where(Trade.executed_at <= to_date)

        row = db.execute(query).mappings().one()
        return TradeSummaryResponse(**dict(row))
