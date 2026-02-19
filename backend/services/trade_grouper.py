"""Trade grouper — FIFO round-trip matching.

Standalone, re-runnable process decoupled from the import pipeline.
Groups trades into round trips using FIFO matching rules.

FIFO Matching Rules:
1. Group by (account_id, symbol).
2. Sort all trades by executed_at ascending.
3. BUY without open group → open new long group.
4. SELL without open group → open new short group.
5. SELL with open long group → match against oldest open long (FIFO).
6. BUY with open short group → match against oldest open short (FIFO).
7. When net quantity reaches zero, close the group and compute realized_pnl.
8. Partial closes create trim legs; adding to position creates add legs.
"""

from __future__ import annotations

from decimal import Decimal

import structlog
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models.trade import Trade
from backend.models.trade_group import TradeGroup, TradeGroupLeg

logger = structlog.get_logger(__name__)


def recompute_groups(
    db: Session | None = None,
    symbol: str | None = None,
    account_id: str | None = None,
) -> dict:
    """Recompute trade groups for specified scope.

    Deletes existing groups for the scope and rebuilds from scratch.

    Args:
        db: Database session. Created if None.
        symbol: Optional symbol filter.
        account_id: Optional account filter.

    Returns:
        Summary dict with groups_created, groups_closed counts.
    """
    own_session = db is None
    if own_session:
        db = SessionLocal()

    try:
        # Get distinct (account_id, symbol) combinations to process
        query = select(Trade.account_id, Trade.symbol).distinct()
        if symbol:
            query = query.where(Trade.symbol == symbol)
        if account_id:
            query = query.where(Trade.account_id == account_id)

        pairs = db.execute(query).all()

        total_created = 0
        total_closed = 0

        for acct, sym in pairs:
            created, closed = _recompute_for_pair(db, acct, sym)
            total_created += created
            total_closed += closed

        if own_session:
            db.commit()

        logger.info(
            "trade_groups_recomputed",
            symbol=symbol,
            account_id=account_id,
            groups_created=total_created,
            groups_closed=total_closed,
        )

        return {
            "groups_created": total_created,
            "groups_closed": total_closed,
        }

    except Exception:
        if own_session:
            db.rollback()
        raise
    finally:
        if own_session:
            db.close()


def _recompute_for_pair(db: Session, account_id: str, symbol: str) -> tuple[int, int]:
    """Recompute groups for a single (account_id, symbol) pair.

    Returns (groups_created, groups_closed).
    """
    # Delete existing groups and legs for this pair
    existing_groups = db.execute(
        select(TradeGroup.id).where(
            TradeGroup.account_id == account_id,
            TradeGroup.symbol == symbol,
        )
    ).scalars().all()

    if existing_groups:
        db.execute(
            delete(TradeGroupLeg).where(
                TradeGroupLeg.trade_group_id.in_(existing_groups)
            )
        )
        db.execute(
            delete(TradeGroup).where(
                TradeGroup.id.in_(existing_groups)
            )
        )
        db.flush()

    # Fetch all trades for this pair sorted by executed_at
    trades = db.execute(
        select(Trade)
        .where(Trade.account_id == account_id, Trade.symbol == symbol)
        .order_by(Trade.executed_at.asc())
    ).scalars().all()

    if not trades:
        return 0, 0

    # FIFO matching
    groups_created = 0
    groups_closed = 0
    open_groups: list[_OpenGroup] = []

    for trade in trades:
        side = trade.side
        qty = abs(trade.quantity)

        # Find matching open group
        matched_group = _find_matching_group(open_groups, side)

        if matched_group is None:
            # Open a new group
            direction = "long" if side == "buy" else "short"
            group = TradeGroup(
                account_id=account_id,
                symbol=symbol,
                asset_class=trade.asset_class,
                direction=direction,
                status="open",
                opened_at=trade.executed_at,
            )
            db.add(group)
            db.flush()  # Get the ID

            leg = TradeGroupLeg(
                trade_group_id=group.id,
                trade_id=trade.id,
                role="entry",
            )
            db.add(leg)

            open_groups.append(
                _OpenGroup(
                    group=group,
                    net_qty=qty,
                    cost_basis=trade.price * qty,
                    direction=direction,
                    multiplier=trade.multiplier if trade.multiplier else Decimal("1"),
                )
            )
            groups_created += 1

        else:
            # Match against existing group
            is_closing = _is_closing_trade(matched_group.direction, side)

            if is_closing:
                if qty >= matched_group.net_qty:
                    # Full close or overfill
                    role = "exit"
                    close_qty = matched_group.net_qty

                    # Compute realized PnL
                    avg_entry = (
                        matched_group.cost_basis / matched_group.net_qty
                        if matched_group.net_qty > 0
                        else Decimal("0")
                    )
                    if matched_group.direction == "long":
                        exit_pnl = (trade.price - avg_entry) * close_qty * matched_group.multiplier
                    else:
                        exit_pnl = (avg_entry - trade.price) * close_qty * matched_group.multiplier

                    # 总已实现盈亏 = 累积的 trim 盈亏 + 最终 exit 盈亏
                    total_pnl = matched_group.accumulated_pnl + exit_pnl

                    matched_group.group.status = "closed"
                    matched_group.group.realized_pnl = total_pnl
                    matched_group.group.closed_at = trade.executed_at

                    leg = TradeGroupLeg(
                        trade_group_id=matched_group.group.id,
                        trade_id=trade.id,
                        role=role,
                    )
                    db.add(leg)

                    open_groups.remove(matched_group)
                    groups_closed += 1

                    # Handle overfill — remaining qty opens new group
                    remaining = qty - close_qty
                    if remaining > Decimal("0"):
                        new_direction = "long" if side == "buy" else "short"
                        new_group = TradeGroup(
                            account_id=account_id,
                            symbol=symbol,
                            asset_class=trade.asset_class,
                            direction=new_direction,
                            status="open",
                            opened_at=trade.executed_at,
                        )
                        db.add(new_group)
                        db.flush()

                        new_leg = TradeGroupLeg(
                            trade_group_id=new_group.id,
                            trade_id=trade.id,
                            role="entry",
                        )
                        db.add(new_leg)

                        open_groups.append(
                            _OpenGroup(
                                group=new_group,
                                net_qty=remaining,
                                cost_basis=trade.price * remaining,
                                direction=new_direction,
                                multiplier=trade.multiplier if trade.multiplier else Decimal("1"),
                            )
                        )
                        groups_created += 1

                else:
                    # Partial close (trim)
                    role = "trim"
                    avg_entry = (
                        matched_group.cost_basis / matched_group.net_qty
                        if matched_group.net_qty > 0
                        else Decimal("0")
                    )

                    # 计算 trim 阶段的已实现盈亏并累积
                    if matched_group.direction == "long":
                        trim_pnl = (trade.price - avg_entry) * qty * matched_group.multiplier
                    else:
                        trim_pnl = (avg_entry - trade.price) * qty * matched_group.multiplier
                    matched_group.accumulated_pnl += trim_pnl

                    matched_group.net_qty -= qty
                    matched_group.cost_basis = avg_entry * matched_group.net_qty

                    leg = TradeGroupLeg(
                        trade_group_id=matched_group.group.id,
                        trade_id=trade.id,
                        role=role,
                    )
                    db.add(leg)

            else:
                # Adding to position
                role = "add"
                matched_group.net_qty += qty
                matched_group.cost_basis += trade.price * qty

                leg = TradeGroupLeg(
                    trade_group_id=matched_group.group.id,
                    trade_id=trade.id,
                    role=role,
                )
                db.add(leg)

    db.flush()
    return groups_created, groups_closed


class _OpenGroup:
    """Tracks state for an open group during FIFO matching."""

    def __init__(
        self,
        group: TradeGroup,
        net_qty: Decimal,
        cost_basis: Decimal,
        direction: str,
        multiplier: Decimal = Decimal("1"),
    ):
        self.group = group
        self.net_qty = net_qty
        self.cost_basis = cost_basis
        self.direction = direction
        self.multiplier = multiplier
        # 累积 trim（部分平仓）阶段的已实现盈亏
        self.accumulated_pnl = Decimal("0")


def _find_matching_group(
    open_groups: list[_OpenGroup], side: str
) -> _OpenGroup | None:
    """Find the oldest open group that matches for FIFO.

    - SELL matches the oldest open long group.
    - BUY matches the oldest open short group.
    """
    for g in open_groups:
        if _is_closing_trade(g.direction, side) or _is_adding_trade(g.direction, side):
            return g
    return None


def _is_closing_trade(direction: str, side: str) -> bool:
    """Check if a trade closes (reduces) a group."""
    return (direction == "long" and side == "sell") or (
        direction == "short" and side == "buy"
    )


def _is_adding_trade(direction: str, side: str) -> bool:
    """Check if a trade adds to a group."""
    return (direction == "long" and side == "buy") or (
        direction == "short" and side == "sell"
    )
