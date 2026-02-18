"""
Tests for the trade grouper (FIFO round-trip matching).

Tests the standalone trade grouping logic:
1. Simple long round trip (buy then sell)
2. Simple short round trip (sell then buy)
3. Partial close (trim leg)
4. Add to position (add leg)
5. Multiple symbols grouped independently
6. Out-of-order recompute (trades arriving not in time order)
7. P&L calculation on closed groups

The grouper function is:
    recompute_groups(db, symbol=..., account_id=...) -> dict
It deletes existing groups and rebuilds from scratch.

Reference: design-doc-final.md Section 4.4
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from backend.models.trade import Trade
from backend.models.trade_group import TradeGroup, TradeGroupLeg
from backend.services.trade_grouper import recompute_groups


def _make_trade(
    db_session,
    *,
    account_id: str = "U1234567",
    symbol: str = "AAPL",
    asset_class: str = "stock",
    side: str = "buy",
    quantity: Decimal = Decimal("100"),
    price: Decimal = Decimal("100.00"),
    executed_at: datetime = None,
) -> Trade:
    """Helper to create and persist a Trade ORM instance for grouper tests."""
    trade = Trade(
        id=uuid.uuid4(),
        broker="ibkr",
        broker_exec_id=f"EXEC-{uuid.uuid4().hex[:8]}",
        account_id=account_id,
        symbol=symbol,
        asset_class=asset_class,
        side=side,
        quantity=quantity,
        price=price,
        commission=Decimal("1.00"),
        executed_at=executed_at or datetime(2025, 1, 15, 14, 30, 0, tzinfo=timezone.utc),
        currency="USD",
        raw_data={},
    )
    db_session.add(trade)
    db_session.flush()
    return trade


def _get_groups(db_session, symbol: str, account_id: str = "U1234567") -> list[TradeGroup]:
    """Query trade groups for a given symbol and account."""
    return db_session.execute(
        select(TradeGroup).where(
            TradeGroup.account_id == account_id,
            TradeGroup.symbol == symbol,
        ).order_by(TradeGroup.opened_at)
    ).scalars().all()


# ===========================================================================
# Simple Long Round Trip
# ===========================================================================

class TestSimpleLongRoundTrip:
    """Test a basic buy-then-sell (long) round trip."""

    def test_long_group_created(self, db_session):
        """Buying then selling same qty should create one closed long group."""
        _make_trade(db_session, symbol="AAPL", side="buy", quantity=Decimal("100"),
                    price=Decimal("150.00"),
                    executed_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc))
        _make_trade(db_session, symbol="AAPL", side="sell", quantity=Decimal("100"),
                    price=Decimal("160.00"),
                    executed_at=datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc))

        recompute_groups(db=db_session, symbol="AAPL", account_id="U1234567")
        groups = _get_groups(db_session, "AAPL")

        assert len(groups) == 1
        assert groups[0].direction == "long"
        assert groups[0].status == "closed"

    def test_long_group_legs(self, db_session):
        """Long round trip should have entry and exit legs."""
        _make_trade(db_session, symbol="AAPL", side="buy", quantity=Decimal("100"),
                    price=Decimal("150.00"),
                    executed_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc))
        _make_trade(db_session, symbol="AAPL", side="sell", quantity=Decimal("100"),
                    price=Decimal("160.00"),
                    executed_at=datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc))

        recompute_groups(db=db_session, symbol="AAPL", account_id="U1234567")
        groups = _get_groups(db_session, "AAPL")

        legs = db_session.query(TradeGroupLeg).filter_by(trade_group_id=groups[0].id).all()
        roles = {leg.role for leg in legs}
        assert "entry" in roles
        assert "exit" in roles

    def test_long_group_timestamps(self, db_session):
        """Closed long group should have opened_at and closed_at set."""
        _make_trade(db_session, symbol="AAPL", side="buy", quantity=Decimal("100"),
                    price=Decimal("150.00"),
                    executed_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc))
        _make_trade(db_session, symbol="AAPL", side="sell", quantity=Decimal("100"),
                    price=Decimal("160.00"),
                    executed_at=datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc))

        recompute_groups(db=db_session, symbol="AAPL", account_id="U1234567")
        groups = _get_groups(db_session, "AAPL")

        assert groups[0].opened_at is not None
        assert groups[0].closed_at is not None
        assert groups[0].closed_at > groups[0].opened_at


# ===========================================================================
# Simple Short Round Trip
# ===========================================================================

class TestSimpleShortRoundTrip:
    """Test a basic sell-then-buy (short) round trip."""

    def test_short_group_created(self, db_session):
        """Selling then buying same qty should create one closed short group."""
        _make_trade(db_session, symbol="TSLA", side="sell", quantity=Decimal("50"),
                    price=Decimal("200.00"),
                    executed_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc))
        _make_trade(db_session, symbol="TSLA", side="buy", quantity=Decimal("50"),
                    price=Decimal("190.00"),
                    executed_at=datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc))

        recompute_groups(db=db_session, symbol="TSLA", account_id="U1234567")
        groups = _get_groups(db_session, "TSLA")

        assert len(groups) == 1
        assert groups[0].direction == "short"
        assert groups[0].status == "closed"

    def test_short_group_pnl_positive(self, db_session):
        """Short round trip: sell high, buy low -> positive P&L."""
        _make_trade(db_session, symbol="TSLA", side="sell", quantity=Decimal("50"),
                    price=Decimal("200.00"),
                    executed_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc))
        _make_trade(db_session, symbol="TSLA", side="buy", quantity=Decimal("50"),
                    price=Decimal("190.00"),
                    executed_at=datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc))

        recompute_groups(db=db_session, symbol="TSLA", account_id="U1234567")
        groups = _get_groups(db_session, "TSLA")

        assert groups[0].realized_pnl is not None
        assert groups[0].realized_pnl > 0


# ===========================================================================
# Partial Close
# ===========================================================================

class TestPartialClose:
    """Test partial closing of positions (trim legs)."""

    def test_partial_close_keeps_group_open(self, db_session):
        """Selling part of a long position should keep the group open."""
        _make_trade(db_session, symbol="AAPL", side="buy", quantity=Decimal("100"),
                    price=Decimal("150.00"),
                    executed_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc))
        _make_trade(db_session, symbol="AAPL", side="sell", quantity=Decimal("50"),
                    price=Decimal("155.00"),
                    executed_at=datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc))

        recompute_groups(db=db_session, symbol="AAPL", account_id="U1234567")
        groups = _get_groups(db_session, "AAPL")

        assert len(groups) == 1
        assert groups[0].status == "open"

    def test_partial_close_then_full_close(self, db_session):
        """Partial close followed by full close should result in one closed group."""
        _make_trade(db_session, symbol="AAPL", side="buy", quantity=Decimal("100"),
                    price=Decimal("150.00"),
                    executed_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc))
        _make_trade(db_session, symbol="AAPL", side="sell", quantity=Decimal("50"),
                    price=Decimal("155.00"),
                    executed_at=datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc))
        _make_trade(db_session, symbol="AAPL", side="sell", quantity=Decimal("50"),
                    price=Decimal("160.00"),
                    executed_at=datetime(2025, 1, 16, 10, 0, 0, tzinfo=timezone.utc))

        recompute_groups(db=db_session, symbol="AAPL", account_id="U1234567")
        groups = _get_groups(db_session, "AAPL")

        assert len(groups) == 1
        assert groups[0].status == "closed"

    def test_trim_leg_role(self, db_session):
        """The partial close trade should have role 'trim'."""
        _make_trade(db_session, symbol="AAPL", side="buy", quantity=Decimal("100"),
                    price=Decimal("150.00"),
                    executed_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc))
        _make_trade(db_session, symbol="AAPL", side="sell", quantity=Decimal("50"),
                    price=Decimal("155.00"),
                    executed_at=datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc))
        _make_trade(db_session, symbol="AAPL", side="sell", quantity=Decimal("50"),
                    price=Decimal("160.00"),
                    executed_at=datetime(2025, 1, 16, 10, 0, 0, tzinfo=timezone.utc))

        recompute_groups(db=db_session, symbol="AAPL", account_id="U1234567")
        groups = _get_groups(db_session, "AAPL")

        legs = db_session.query(TradeGroupLeg).filter_by(trade_group_id=groups[0].id).all()
        roles = [leg.role for leg in legs]
        assert "trim" in roles


# ===========================================================================
# Add to Position
# ===========================================================================

class TestAddToPosition:
    """Test adding to an existing position (add legs)."""

    def test_add_to_long_position(self, db_session):
        """Buying more shares while long should create an 'add' leg."""
        _make_trade(db_session, symbol="AAPL", side="buy", quantity=Decimal("100"),
                    price=Decimal("150.00"),
                    executed_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc))
        _make_trade(db_session, symbol="AAPL", side="buy", quantity=Decimal("50"),
                    price=Decimal("148.00"),
                    executed_at=datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc))
        _make_trade(db_session, symbol="AAPL", side="sell", quantity=Decimal("150"),
                    price=Decimal("155.00"),
                    executed_at=datetime(2025, 1, 16, 10, 0, 0, tzinfo=timezone.utc))

        recompute_groups(db=db_session, symbol="AAPL", account_id="U1234567")
        groups = _get_groups(db_session, "AAPL")

        assert len(groups) == 1
        assert groups[0].status == "closed"

        legs = db_session.query(TradeGroupLeg).filter_by(trade_group_id=groups[0].id).all()
        roles = [leg.role for leg in legs]
        assert "add" in roles


# ===========================================================================
# Multiple Symbols
# ===========================================================================

class TestMultipleSymbols:
    """Test that trades in different symbols are grouped independently."""

    def test_different_symbols_separate_groups(self, db_session):
        """Trades in AAPL and MSFT should create separate groups."""
        _make_trade(db_session, symbol="AAPL", side="buy", quantity=Decimal("100"),
                    price=Decimal("150.00"),
                    executed_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc))
        _make_trade(db_session, symbol="MSFT", side="buy", quantity=Decimal("50"),
                    price=Decimal("400.00"),
                    executed_at=datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc))
        _make_trade(db_session, symbol="AAPL", side="sell", quantity=Decimal("100"),
                    price=Decimal("155.00"),
                    executed_at=datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc))
        _make_trade(db_session, symbol="MSFT", side="sell", quantity=Decimal("50"),
                    price=Decimal("405.00"),
                    executed_at=datetime(2025, 1, 15, 14, 30, 0, tzinfo=timezone.utc))

        recompute_groups(db=db_session, account_id="U1234567")

        aapl_groups = _get_groups(db_session, "AAPL")
        msft_groups = _get_groups(db_session, "MSFT")

        assert len(aapl_groups) == 1
        assert aapl_groups[0].symbol == "AAPL"
        assert len(msft_groups) == 1
        assert msft_groups[0].symbol == "MSFT"

    def test_same_symbol_different_accounts(self, db_session):
        """Same symbol in different accounts should create separate groups."""
        _make_trade(db_session, account_id="U1111111", symbol="AAPL", side="buy",
                    quantity=Decimal("100"), price=Decimal("150.00"),
                    executed_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc))
        _make_trade(db_session, account_id="U2222222", symbol="AAPL", side="buy",
                    quantity=Decimal("100"), price=Decimal("150.00"),
                    executed_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc))

        recompute_groups(db=db_session, symbol="AAPL")

        groups1 = _get_groups(db_session, "AAPL", account_id="U1111111")
        groups2 = _get_groups(db_session, "AAPL", account_id="U2222222")

        assert len(groups1) == 1
        assert len(groups2) == 1
        assert groups1[0].account_id == "U1111111"
        assert groups2[0].account_id == "U2222222"


# ===========================================================================
# Out-of-Order Recompute
# ===========================================================================

class TestOutOfOrderRecompute:
    """Test that recomputation handles trades arriving out of chronological order."""

    def test_recompute_is_idempotent(self, db_session):
        """Running recompute multiple times should produce the same result."""
        _make_trade(db_session, symbol="AAPL", side="buy", quantity=Decimal("100"),
                    price=Decimal("150.00"),
                    executed_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc))
        _make_trade(db_session, symbol="AAPL", side="sell", quantity=Decimal("100"),
                    price=Decimal("160.00"),
                    executed_at=datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc))

        result1 = recompute_groups(db=db_session, symbol="AAPL", account_id="U1234567")
        groups1 = _get_groups(db_session, "AAPL")

        result2 = recompute_groups(db=db_session, symbol="AAPL", account_id="U1234567")
        groups2 = _get_groups(db_session, "AAPL")

        assert len(groups1) == len(groups2)
        assert groups2[0].direction == "long"
        assert groups2[0].status == "closed"

    def test_late_arriving_trade_recomputed(self, db_session):
        """Adding a trade that arrived late should recompute groups correctly."""
        # First, only the sell trade
        _make_trade(db_session, symbol="AAPL", side="sell", quantity=Decimal("100"),
                    price=Decimal("155.00"),
                    executed_at=datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc))
        recompute_groups(db=db_session, symbol="AAPL", account_id="U1234567")

        # This sell without prior buy creates a short group
        groups = _get_groups(db_session, "AAPL")
        assert len(groups) == 1
        assert groups[0].direction == "short"

        # Now add the earlier buy trade (arrived late)
        _make_trade(db_session, symbol="AAPL", side="buy", quantity=Decimal("100"),
                    price=Decimal("150.00"),
                    executed_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc))

        # Recompute — should now be a long buy-then-sell group
        recompute_groups(db=db_session, symbol="AAPL", account_id="U1234567")
        groups = _get_groups(db_session, "AAPL")

        assert len(groups) == 1
        assert groups[0].direction == "long"
        assert groups[0].status == "closed"


# ===========================================================================
# P&L Calculation
# ===========================================================================

class TestPnLCalculation:
    """Test realized P&L computation on closed groups."""

    def test_long_profit(self, db_session):
        """Long round trip with profit: buy low, sell high."""
        _make_trade(db_session, symbol="AAPL", side="buy", quantity=Decimal("100"),
                    price=Decimal("150.00"),
                    executed_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc))
        _make_trade(db_session, symbol="AAPL", side="sell", quantity=Decimal("100"),
                    price=Decimal("160.00"),
                    executed_at=datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc))

        recompute_groups(db=db_session, symbol="AAPL", account_id="U1234567")
        groups = _get_groups(db_session, "AAPL")

        assert groups[0].realized_pnl is not None
        assert groups[0].realized_pnl > 0

    def test_long_loss(self, db_session):
        """Long round trip with loss: buy high, sell low."""
        _make_trade(db_session, symbol="AAPL", side="buy", quantity=Decimal("100"),
                    price=Decimal("160.00"),
                    executed_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc))
        _make_trade(db_session, symbol="AAPL", side="sell", quantity=Decimal("100"),
                    price=Decimal("150.00"),
                    executed_at=datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc))

        recompute_groups(db=db_session, symbol="AAPL", account_id="U1234567")
        groups = _get_groups(db_session, "AAPL")

        assert groups[0].realized_pnl is not None
        assert groups[0].realized_pnl < 0

    def test_open_group_no_pnl(self, db_session):
        """Open group should have realized_pnl = None."""
        _make_trade(db_session, symbol="AAPL", side="buy", quantity=Decimal("100"),
                    price=Decimal("150.00"),
                    executed_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc))

        recompute_groups(db=db_session, symbol="AAPL", account_id="U1234567")
        groups = _get_groups(db_session, "AAPL")

        assert len(groups) == 1
        assert groups[0].status == "open"
        assert groups[0].realized_pnl is None

    def test_multiple_round_trips_same_symbol(self, db_session):
        """Multiple sequential round trips in the same symbol."""
        # Round trip 1
        _make_trade(db_session, symbol="AAPL", side="buy", quantity=Decimal("100"),
                    price=Decimal("150.00"),
                    executed_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc))
        _make_trade(db_session, symbol="AAPL", side="sell", quantity=Decimal("100"),
                    price=Decimal("155.00"),
                    executed_at=datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc))
        # Round trip 2
        _make_trade(db_session, symbol="AAPL", side="buy", quantity=Decimal("200"),
                    price=Decimal("152.00"),
                    executed_at=datetime(2025, 1, 16, 10, 0, 0, tzinfo=timezone.utc))
        _make_trade(db_session, symbol="AAPL", side="sell", quantity=Decimal("200"),
                    price=Decimal("158.00"),
                    executed_at=datetime(2025, 1, 16, 14, 0, 0, tzinfo=timezone.utc))

        recompute_groups(db=db_session, symbol="AAPL", account_id="U1234567")
        groups = _get_groups(db_session, "AAPL")

        assert len(groups) == 2
        assert all(g.status == "closed" for g in groups)
        assert all(g.realized_pnl is not None for g in groups)
