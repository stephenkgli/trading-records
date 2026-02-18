"""
Tests for the deduplication engine in BaseIngester.

Tests the composite natural key dedup strategy (broker, broker_exec_id):
1. First import — all records inserted
2. Duplicate import — exact same records skipped
3. Partial overlap — new records inserted, duplicates skipped
4. Transaction rollback — no partial data on failure
5. ImportResult field correctness

Reference: design-doc-final.md Sections 4.3, 5.2
"""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.ingestion.base import BaseIngester
from backend.models.trade import Trade
from backend.models.import_log import ImportLog


class _TestIngester(BaseIngester):
    """Concrete ingester for testing import_records()."""
    source = "test"


class TestFirstImport:
    """Test that the first import of new records inserts all of them."""

    def test_all_records_inserted(self, db_session, make_normalized_trade):
        """First import of unique trades should insert all records."""
        trades = [
            make_normalized_trade(broker_exec_id="FIRST001", symbol="AAPL"),
            make_normalized_trade(broker_exec_id="FIRST002", symbol="MSFT"),
            make_normalized_trade(broker_exec_id="FIRST003", symbol="GOOG"),
        ]

        ingester = _TestIngester()
        result = ingester.import_records(trades, db=db_session)

        assert result.records_total == 3
        assert result.records_imported == 3
        assert result.records_skipped_dup == 0
        assert result.records_failed == 0

    def test_trades_exist_in_db(self, db_session, make_normalized_trade):
        """After first import, trades should be queryable from the database."""
        trades = [
            make_normalized_trade(broker_exec_id="DB001", symbol="AAPL"),
        ]

        ingester = _TestIngester()
        ingester.import_records(trades, db=db_session)

        db_trades = db_session.query(Trade).filter_by(broker_exec_id="DB001").all()
        assert len(db_trades) == 1
        assert db_trades[0].symbol == "AAPL"
        assert db_trades[0].broker == "ibkr"

    def test_import_log_created(self, db_session, make_normalized_trade):
        """An import_log entry should be created for the import."""
        trades = [make_normalized_trade(broker_exec_id="LOG001")]

        ingester = _TestIngester()
        result = ingester.import_records(trades, db=db_session)

        log = db_session.query(ImportLog).filter_by(id=result.import_log_id).first()
        assert log is not None
        assert log.source == "test"
        assert log.status == "success"


class TestDuplicateImport:
    """Test that re-importing the same records skips all duplicates."""

    def test_exact_duplicate_skipped(self, db_session, make_normalized_trade):
        """Importing the same trade twice should skip it on the second import."""
        trade = make_normalized_trade(broker_exec_id="DUP001", symbol="AAPL")

        ingester = _TestIngester()

        # First import
        result1 = ingester.import_records([trade], db=db_session)
        assert result1.records_imported == 1

        # Second import — exact duplicate
        result2 = ingester.import_records([trade], db=db_session)
        assert result2.records_imported == 0
        assert result2.records_skipped_dup == 1

    def test_duplicate_detection_by_composite_key(self, db_session, make_normalized_trade):
        """Dedup is based on (broker, broker_exec_id), not other fields."""
        trade1 = make_normalized_trade(
            broker="ibkr", broker_exec_id="COMP001", price=Decimal("100.00")
        )
        trade2 = make_normalized_trade(
            broker="ibkr", broker_exec_id="COMP001", price=Decimal("200.00")
        )

        ingester = _TestIngester()
        ingester.import_records([trade1], db=db_session)
        result = ingester.import_records([trade2], db=db_session)

        # Same (broker, broker_exec_id) — should be skipped even though price differs
        assert result.records_skipped_dup == 1
        assert result.records_imported == 0

    def test_same_exec_id_different_broker_not_duplicate(self, db_session, make_normalized_trade):
        """Same broker_exec_id but different broker should NOT be considered duplicate."""
        trade1 = make_normalized_trade(broker="ibkr", broker_exec_id="CROSS001")
        trade2 = make_normalized_trade(broker="tradovate", broker_exec_id="CROSS001")

        ingester = _TestIngester()
        ingester.import_records([trade1], db=db_session)
        result = ingester.import_records([trade2], db=db_session)

        assert result.records_imported == 1
        assert result.records_skipped_dup == 0

    def test_db_count_unchanged_on_duplicate(self, db_session, make_normalized_trade):
        """Database trade count should not increase on duplicate import."""
        trade = make_normalized_trade(broker_exec_id="COUNT001")

        ingester = _TestIngester()
        ingester.import_records([trade], db=db_session)
        count_after_first = db_session.query(Trade).count()

        ingester.import_records([trade], db=db_session)
        count_after_second = db_session.query(Trade).count()

        assert count_after_first == count_after_second


class TestPartialOverlap:
    """Test imports with a mix of new and duplicate records."""

    def test_partial_overlap_counts(self, db_session, make_normalized_trade):
        """Import with some existing and some new records should handle both correctly."""
        existing = make_normalized_trade(broker_exec_id="PART001", symbol="AAPL")
        ingester = _TestIngester()
        ingester.import_records([existing], db=db_session)

        # Second import: one duplicate, two new
        batch = [
            make_normalized_trade(broker_exec_id="PART001", symbol="AAPL"),  # dup
            make_normalized_trade(broker_exec_id="PART002", symbol="MSFT"),  # new
            make_normalized_trade(broker_exec_id="PART003", symbol="GOOG"),  # new
        ]
        result = ingester.import_records(batch, db=db_session)

        assert result.records_total == 3
        assert result.records_imported == 2
        assert result.records_skipped_dup == 1

    def test_partial_overlap_db_state(self, db_session, make_normalized_trade):
        """After partial overlap import, DB should contain correct total trades."""
        existing = make_normalized_trade(broker_exec_id="STATE001")
        ingester = _TestIngester()
        ingester.import_records([existing], db=db_session)

        batch = [
            make_normalized_trade(broker_exec_id="STATE001"),  # dup
            make_normalized_trade(broker_exec_id="STATE002"),  # new
        ]
        ingester.import_records(batch, db=db_session)

        total = db_session.query(Trade).count()
        assert total == 2  # 1 existing + 1 new

    def test_large_overlap_batch(self, db_session, make_normalized_trade):
        """Large batch with many duplicates should process correctly."""
        ingester = _TestIngester()

        # Insert 10 trades
        first_batch = [
            make_normalized_trade(broker_exec_id=f"LARGE{i:03d}")
            for i in range(10)
        ]
        ingester.import_records(first_batch, db=db_session)

        # Import 15 trades: 10 duplicates + 5 new
        second_batch = [
            make_normalized_trade(broker_exec_id=f"LARGE{i:03d}")
            for i in range(15)
        ]
        result = ingester.import_records(second_batch, db=db_session)

        assert result.records_imported == 5
        assert result.records_skipped_dup == 10


class TestImportResultFields:
    """Test that ImportResult has correct field values."""

    def test_source_field(self, db_session, make_normalized_trade):
        """ImportResult.source should reflect the ingester source."""
        trades = [make_normalized_trade(broker_exec_id="SRC001")]

        class CSVIngester(BaseIngester):
            source = "csv"

        ingester = CSVIngester()
        result = ingester.import_records(trades, db=db_session)
        assert result.source == "csv"

    def test_status_success(self, db_session, make_normalized_trade):
        """Successful import should have status = 'success'."""
        trades = [make_normalized_trade(broker_exec_id="STAT001")]
        ingester = _TestIngester()
        result = ingester.import_records(trades, db=db_session)
        assert result.status == "success"

    def test_records_total(self, db_session, make_normalized_trade):
        """records_total should count all input records."""
        trades = [
            make_normalized_trade(broker_exec_id=f"TOTAL{i}")
            for i in range(7)
        ]
        ingester = _TestIngester()
        result = ingester.import_records(trades, db=db_session)
        assert result.records_total == 7

    def test_empty_import(self, db_session):
        """Importing zero trades should still create a log entry."""
        ingester = _TestIngester()
        result = ingester.import_records([], db=db_session)

        assert result.records_total == 0
        assert result.records_imported == 0
        assert result.records_skipped_dup == 0
        assert result.status == "success"

    def test_trades_linked_to_import_log(self, db_session, make_normalized_trade):
        """Imported trades should have import_log_id set to the log entry's ID."""
        trades = [make_normalized_trade(broker_exec_id="LINK001")]
        ingester = _TestIngester()
        result = ingester.import_records(trades, db=db_session)

        trade = db_session.query(Trade).filter_by(broker_exec_id="LINK001").first()
        assert trade is not None
        assert str(trade.import_log_id) == str(result.import_log_id)


class TestTransactionRollback:
    """Test all-or-nothing import transaction behavior."""

    def test_insert_failure_rolls_back_all_trades(self, make_normalized_trade):
        """If one row fails at insert time, no trades from the batch should persist."""
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        Base.metadata.create_all(bind=engine)
        db_session = Session(bind=engine)

        trades = [
            make_normalized_trade(broker_exec_id="RB001", raw_data={"ok": True}),
            # set() is not JSON-serializable and should fail DB bind/flush
            make_normalized_trade(broker_exec_id="RB002", raw_data={"bad": {1, 2}}),
        ]

        ingester = _TestIngester()
        with pytest.raises(Exception):
            ingester.import_records(trades, db=db_session)

        db_session.rollback()
        persisted = (
            db_session.query(Trade)
            .filter(Trade.broker_exec_id.in_(["RB001", "RB002"]))
            .count()
        )
        assert persisted == 0
        db_session.close()
        engine.dispose()
