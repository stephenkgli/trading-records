"""
Shared pytest fixtures for trading-records test suite.

Provides:
- SQLite in-memory database session (lightweight, no external deps)
- FastAPI TestClient with database override
- Common test data factories
- Fixture data loaders
"""

import csv
import io
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Callable, Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import JSON, String, TypeDecorator, create_engine, event
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session, sessionmaker

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# SQLite compatibility for PostgreSQL types
# ---------------------------------------------------------------------------
# The ORM models use PostgreSQL-specific JSONB and UUID types.
# For SQLite testing we override them before importing models.

import sqlalchemy.dialects.postgresql as pg_types

# Monkey-patch PostgreSQL types to work with SQLite
_original_jsonb = pg_types.JSONB
_original_uuid = pg_types.UUID


class _SQLiteJSONB(JSON):
    """SQLite-compatible replacement for pg JSONB."""
    pass


class _SQLiteUUID(TypeDecorator):
    """SQLite-compatible replacement for pg UUID — stores as varchar."""
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return str(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            import uuid as _uuid
            return _uuid.UUID(str(value))
        return value


# Apply patches before importing any models
pg_types.JSONB = _SQLiteJSONB
pg_types.UUID = _SQLiteUUID

# Now import backend modules (they use the patched types)
from backend.database import Base, get_db  # noqa: E402
from backend.main import app  # noqa: E402


# ---------------------------------------------------------------------------
# Database fixtures (SQLite in-memory)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def engine():
    """Create a SQLite in-memory engine for the entire test session."""
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Enable foreign key support in SQLite
    @event.listens_for(test_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=test_engine)
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def db_session(engine) -> Generator[Session, None, None]:
    """Provide a transactional database session that rolls back after each test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# ---------------------------------------------------------------------------
# FastAPI TestClient
# ---------------------------------------------------------------------------

@pytest.fixture
def client(db_session) -> Generator[TestClient, None, None]:
    """Provide a FastAPI TestClient with overridden database session."""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Fixture data loaders
# ---------------------------------------------------------------------------

@pytest.fixture
def ibkr_activity_csv() -> str:
    """Load IBKR Activity Statement CSV fixture."""
    return (FIXTURES_DIR / "ibkr_activity.csv").read_text(encoding="utf-8-sig")


@pytest.fixture
def ibkr_activity_no_trades_csv() -> str:
    """Load IBKR Activity Statement CSV fixture with no trades."""
    return (FIXTURES_DIR / "ibkr_activity_no_trades.csv").read_text(
        encoding="utf-8-sig"
    )


@pytest.fixture
def tradovate_export_csv() -> str:
    """Load Tradovate export CSV fixture."""
    return (FIXTURES_DIR / "tradovate_export.csv").read_text(encoding="utf-8-sig")


@pytest.fixture
def tradovate_performance_csv() -> str:
    """Load Tradovate Performance report CSV fixture."""
    return (FIXTURES_DIR / "tradovate_performance.csv").read_text(
        encoding="utf-8-sig"
    )


@pytest.fixture
def ibkr_expected_trade_count(ibkr_activity_csv: str) -> int:
    """Expected IBKR trades from the fixture CSV."""
    from backend.ingestion.csv_importer import CSVImporter

    return len(CSVImporter()._parse_ibkr_csv(ibkr_activity_csv, "ibkr_activity.csv"))


@pytest.fixture
def tradovate_expected_trade_count(tradovate_performance_csv: str) -> int:
    """Expected Tradovate trades from the fixture CSV (2 trades per row)."""
    row_count = 0
    for row in csv.DictReader(io.StringIO(tradovate_performance_csv)):
        symbol = (row.get("symbol") or "").strip()
        qty = (row.get("qty") or "").strip()
        if symbol and qty and Decimal(qty) != 0:
            row_count += 1
    return row_count * 2


# ---------------------------------------------------------------------------
# NormalizedTrade factory
# ---------------------------------------------------------------------------

@pytest.fixture
def make_normalized_trade():
    """
    Factory fixture that creates NormalizedTrade instances with sensible defaults.

    Usage:
        trade = make_normalized_trade(symbol="AAPL", side="buy", quantity=100)
    """
    from backend.schemas.trade import NormalizedTrade

    counter = 0

    def _factory(**overrides) -> "NormalizedTrade":
        nonlocal counter
        counter += 1
        defaults = {
            "broker": "ibkr",
            "broker_exec_id": f"EXEC{counter:06d}",
            "account_id": "U1234567",
            "symbol": "AAPL",
            "underlying": None,
            "asset_class": "stock",
            "side": "buy",
            "quantity": Decimal("100"),
            "price": Decimal("185.50"),
            "commission": Decimal("1.00"),
            "executed_at": datetime(2025, 1, 15, 14, 35, 0, tzinfo=timezone.utc),
            "order_id": f"ORD{counter:06d}",
            "exchange": "SMART",
            "currency": "USD",
            "raw_data": {"test": True, "counter": counter},
        }
        defaults.update(overrides)
        return NormalizedTrade(**defaults)

    return _factory


# ---------------------------------------------------------------------------
# Trade/Group factories and seed helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def make_trade(db_session) -> Callable[..., "Trade"]:
    """Factory fixture that creates Trade records with sensible defaults."""
    from backend.models.trade import Trade
    import uuid

    counter = 0

    def _factory(
        *,
        broker: str = "ibkr",
        account_id: str = "U1234567",
        symbol: str = "AAPL",
        asset_class: str = "stock",
        side: str = "buy",
        quantity: Decimal | int = Decimal("100"),
        price: Decimal | int = Decimal("150.00"),
        commission: Decimal | int = Decimal("1.00"),
        executed_at: datetime | None = None,
        currency: str = "USD",
        raw_data: dict | None = None,
        exec_prefix: str = "SEED",
        broker_exec_id: str | None = None,
    ) -> "Trade":
        nonlocal counter

        if executed_at is None:
            executed_at = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        if raw_data is None:
            raw_data = {}
        if broker_exec_id is None:
            counter += 1
            broker_exec_id = f"{exec_prefix}{counter:04d}"

        trade = Trade(
            id=uuid.uuid4(),
            broker=broker,
            broker_exec_id=broker_exec_id,
            account_id=account_id,
            symbol=symbol,
            asset_class=asset_class,
            side=side,
            quantity=Decimal(str(quantity)),
            price=Decimal(str(price)),
            commission=Decimal(str(commission)),
            executed_at=executed_at,
            currency=currency,
            raw_data=raw_data,
        )
        db_session.add(trade)
        return trade

    return _factory


@pytest.fixture
def make_trade_group(db_session) -> Callable[..., "TradeGroup"]:
    """Factory fixture that creates TradeGroup records with sensible defaults."""
    from backend.models.trade_group import TradeGroup
    import uuid

    def _factory(
        *,
        account_id: str = "U1234567",
        symbol: str = "AAPL",
        asset_class: str = "stock",
        direction: str = "long",
        status: str = "closed",
        realized_pnl: Decimal | int = Decimal("500.00"),
        opened_at: datetime | None = None,
        closed_at: datetime | None = None,
        strategy_tag: str = "momentum",
    ) -> "TradeGroup":
        if opened_at is None:
            opened_at = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        if closed_at is None:
            closed_at = datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc)

        group = TradeGroup(
            id=uuid.uuid4(),
            account_id=account_id,
            symbol=symbol,
            asset_class=asset_class,
            direction=direction,
            status=status,
            realized_pnl=Decimal(str(realized_pnl)),
            opened_at=opened_at,
            closed_at=closed_at,
            strategy_tag=strategy_tag,
        )
        db_session.add(group)
        return group

    return _factory


@pytest.fixture
def seed_trades(db_session, make_trade) -> Callable[..., list["Trade"]]:
    """Create multiple trades with varied symbols and brokers."""
    def _seed(
        *,
        count: int = 5,
        symbols: list[str] | None = None,
        brokers: list[str] | None = None,
        exec_prefix: str = "SEED",
        account_id: str = "U1234567",
    ) -> list["Trade"]:
        if symbols is None:
            symbols = ["AAPL", "MSFT", "GOOG"]
        if brokers is None:
            brokers = ["ibkr"]

        trades = []
        for i in range(count):
            executed_at = datetime(
                2025,
                1,
                15 + (i % 15),
                10,
                i % 60,
                0,
                tzinfo=timezone.utc,
            )
            trade = make_trade(
                symbol=symbols[i % len(symbols)],
                broker=brokers[i % len(brokers)],
                side="buy" if i % 2 == 0 else "sell",
                price=Decimal(f"{150 + i}.00"),
                executed_at=executed_at,
                account_id=account_id,
                raw_data={"seed": i},
                exec_prefix=exec_prefix,
            )
            trades.append(trade)

        db_session.flush()
        return trades

    return _seed


@pytest.fixture
def seed_trade_groups(db_session, make_trade_group) -> Callable[..., list["TradeGroup"]]:
    """Create multiple trade groups with varied symbols."""
    def _seed(
        *,
        count: int = 2,
        symbols: list[str] | None = None,
        account_id: str = "U1234567",
    ) -> list["TradeGroup"]:
        if symbols is None:
            symbols = ["AAPL", "MSFT"]

        groups = []
        strategy_tags = ["momentum", "mean_reversion", "breakout"]

        for i in range(count):
            pnl = Decimal("500.00") if i % 2 == 0 else Decimal("-250.00")
            day_offset = i
            opened_at = datetime(
                2025, 1, 15 + day_offset, 10, 0, 0, tzinfo=timezone.utc
            )
            closed_at = datetime(
                2025, 1, 15 + day_offset, 14, 0, 0, tzinfo=timezone.utc
            )
            group = make_trade_group(
                account_id=account_id,
                symbol=symbols[i % len(symbols)],
                realized_pnl=pnl,
                opened_at=opened_at,
                closed_at=closed_at,
                strategy_tag=strategy_tags[i % len(strategy_tags)],
            )
            groups.append(group)

        db_session.flush()
        return groups

    return _seed


@pytest.fixture
def seed_group_trades(db_session, make_trade) -> Callable[[], list["Trade"]]:
    """Seed trades used by the groups recompute API tests."""
    def _seed() -> list["Trade"]:
        trades = [
            make_trade(
                broker_exec_id="GRP0001",
                symbol="AAPL",
                side="buy",
                quantity=Decimal("100"),
                price=Decimal("100"),
                commission=Decimal("1"),
                executed_at=datetime(2025, 1, 10, 10, 0, 0, tzinfo=timezone.utc),
            ),
            make_trade(
                broker_exec_id="GRP0002",
                symbol="AAPL",
                side="sell",
                quantity=Decimal("100"),
                price=Decimal("110"),
                commission=Decimal("1"),
                executed_at=datetime(2025, 1, 10, 14, 0, 0, tzinfo=timezone.utc),
            ),
            make_trade(
                broker_exec_id="GRP0003",
                symbol="MSFT",
                side="buy",
                quantity=Decimal("50"),
                price=Decimal("300"),
                commission=Decimal("1"),
                executed_at=datetime(2025, 1, 11, 10, 0, 0, tzinfo=timezone.utc),
            ),
        ]
        db_session.flush()
        return trades

    return _seed


@pytest.fixture
def seed_analytics_data(db_session, make_trade, make_trade_group) -> Callable[[], dict]:
    """Seed trades and groups used by analytics API tests."""
    def _seed() -> dict:
        trades = [
            make_trade(
                symbol="AAPL",
                side="buy",
                quantity=Decimal("100"),
                price=Decimal("150.00"),
                executed_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
                exec_prefix="ANALYTICS",
            ),
            make_trade(
                symbol="AAPL",
                side="sell",
                quantity=Decimal("100"),
                price=Decimal("155.00"),
                executed_at=datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc),
                exec_prefix="ANALYTICS",
            ),
            make_trade(
                symbol="MSFT",
                side="buy",
                quantity=Decimal("50"),
                price=Decimal("400.00"),
                executed_at=datetime(2025, 1, 16, 10, 0, 0, tzinfo=timezone.utc),
                exec_prefix="ANALYTICS",
            ),
            make_trade(
                symbol="MSFT",
                side="sell",
                quantity=Decimal("50"),
                price=Decimal("395.00"),
                executed_at=datetime(2025, 1, 16, 14, 0, 0, tzinfo=timezone.utc),
                exec_prefix="ANALYTICS",
            ),
        ]

        groups = [
            make_trade_group(
                symbol="AAPL",
                realized_pnl=Decimal("500.00"),
                opened_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
                closed_at=datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc),
                strategy_tag="momentum",
            ),
            make_trade_group(
                symbol="MSFT",
                realized_pnl=Decimal("-250.00"),
                opened_at=datetime(2025, 1, 16, 10, 0, 0, tzinfo=timezone.utc),
                closed_at=datetime(2025, 1, 16, 14, 0, 0, tzinfo=timezone.utc),
                strategy_tag="mean_reversion",
            ),
        ]

        db_session.flush()
        return {"trades": trades, "groups": groups}

    return _seed


@pytest.fixture
def seed_contract_analytics_data(
    db_session, make_trade, make_trade_group
) -> Callable[[], dict]:
    """Seed trades and groups used by analytics contract tests."""
    def _seed() -> dict:
        trades = [
            make_trade(
                symbol="GOOG",
                side="buy",
                quantity=Decimal("200"),
                price=Decimal("175.00"),
                executed_at=datetime(2025, 3, 10, 9, 30, 0, tzinfo=timezone.utc),
                account_id="U9999999",
                commission=Decimal("1.50"),
                exec_prefix="CONTRACT",
            ),
            make_trade(
                symbol="GOOG",
                side="sell",
                quantity=Decimal("200"),
                price=Decimal("180.00"),
                executed_at=datetime(2025, 3, 10, 15, 0, 0, tzinfo=timezone.utc),
                account_id="U9999999",
                commission=Decimal("1.50"),
                exec_prefix="CONTRACT",
            ),
            make_trade(
                symbol="TSLA",
                side="buy",
                quantity=Decimal("100"),
                price=Decimal("250.00"),
                executed_at=datetime(2025, 3, 11, 10, 0, 0, tzinfo=timezone.utc),
                account_id="U9999999",
                commission=Decimal("1.50"),
                exec_prefix="CONTRACT",
            ),
            make_trade(
                symbol="TSLA",
                side="sell",
                quantity=Decimal("100"),
                price=Decimal("245.00"),
                executed_at=datetime(2025, 3, 11, 14, 0, 0, tzinfo=timezone.utc),
                account_id="U9999999",
                commission=Decimal("1.50"),
                exec_prefix="CONTRACT",
            ),
        ]

        groups = [
            make_trade_group(
                account_id="U9999999",
                symbol="GOOG",
                realized_pnl=Decimal("1000.00"),
                opened_at=datetime(2025, 3, 10, 9, 30, 0, tzinfo=timezone.utc),
                closed_at=datetime(2025, 3, 10, 15, 0, 0, tzinfo=timezone.utc),
                strategy_tag="breakout",
            ),
            make_trade_group(
                account_id="U9999999",
                symbol="TSLA",
                realized_pnl=Decimal("-500.00"),
                opened_at=datetime(2025, 3, 11, 10, 0, 0, tzinfo=timezone.utc),
                closed_at=datetime(2025, 3, 11, 14, 0, 0, tzinfo=timezone.utc),
                strategy_tag="momentum",
            ),
        ]

        db_session.flush()
        return {"trades": trades, "groups": groups}

    return _seed
