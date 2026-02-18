"""
Shared pytest fixtures for trading-records test suite.

Provides:
- SQLite in-memory database session (lightweight, no external deps)
- FastAPI TestClient with database and auth overrides
- Auth header fixture
- Common test data factories
- Fixture data loaders
"""

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Generator
from unittest.mock import patch

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
# FastAPI TestClient — with auth enabled
# ---------------------------------------------------------------------------

@pytest.fixture
def client(db_session) -> Generator[TestClient, None, None]:
    """
    Provide a FastAPI TestClient with overridden database session and
    API key set to 'test-api-key-12345'.

    The auth middleware reads backend.config.settings.api_key directly,
    so we patch it at module level.
    """
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with patch("backend.auth.settings") as mock_settings, \
         patch("backend.main.settings") as mock_main_settings:
        mock_settings.api_key = "test-api-key-12345"
        mock_main_settings.api_key = "test-api-key-12345"
        mock_main_settings.cors_origins_list = ["http://localhost:3000"]

        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

    app.dependency_overrides.clear()


@pytest.fixture
def client_no_auth(db_session) -> Generator[TestClient, None, None]:
    """
    Provide a TestClient where API_KEY is empty (auth disabled).
    """
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with patch("backend.auth.settings") as mock_settings, \
         patch("backend.main.settings") as mock_main_settings:
        mock_settings.api_key = ""
        mock_main_settings.api_key = ""
        mock_main_settings.cors_origins_list = ["http://localhost:3000"]

        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Auth header
# ---------------------------------------------------------------------------

@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Return headers with the correct test API key."""
    return {"X-API-Key": "test-api-key-12345"}


@pytest.fixture
def bad_auth_headers() -> dict[str, str]:
    """Return headers with an incorrect API key."""
    return {"X-API-Key": "wrong-key"}


# ---------------------------------------------------------------------------
# Fixture data loaders
# ---------------------------------------------------------------------------

@pytest.fixture
def ibkr_flex_sample_xml() -> str:
    """Load the IBKR Flex Query sample XML fixture."""
    return (FIXTURES_DIR / "ibkr_flex_sample.xml").read_text()


@pytest.fixture
def ibkr_flex_empty_xml() -> str:
    """Load the IBKR Flex Query empty XML fixture (zero trades)."""
    return (FIXTURES_DIR / "ibkr_flex_empty.xml").read_text()


@pytest.fixture
def ibkr_flex_malformed_xml() -> str:
    """Load the malformed IBKR Flex Query XML fixture."""
    return (FIXTURES_DIR / "ibkr_flex_malformed.xml").read_text()


@pytest.fixture
def ibkr_activity_csv() -> str:
    """Load the IBKR Activity Statement CSV fixture."""
    return (FIXTURES_DIR / "ibkr_activity.csv").read_text()


@pytest.fixture
def ibkr_activity_no_trades_csv() -> str:
    """Load the IBKR Activity Statement CSV with no trades."""
    return (FIXTURES_DIR / "ibkr_activity_no_trades.csv").read_text()


@pytest.fixture
def tradovate_fills_json() -> list[dict]:
    """Load the Tradovate fills JSON fixture."""
    return json.loads((FIXTURES_DIR / "tradovate_fills.json").read_text())


@pytest.fixture
def tradovate_contracts_json() -> dict:
    """Load the Tradovate contracts JSON fixture."""
    return json.loads((FIXTURES_DIR / "tradovate_contracts.json").read_text())


@pytest.fixture
def tradovate_auth_response_json() -> dict:
    """Load the Tradovate OAuth auth response fixture."""
    return json.loads((FIXTURES_DIR / "tradovate_auth_response.json").read_text())


@pytest.fixture
def tradovate_export_csv() -> str:
    """Load the Tradovate export CSV fixture."""
    return (FIXTURES_DIR / "tradovate_export.csv").read_text()


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
