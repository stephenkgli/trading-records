"""Tests for helper functions introduced during the refactoring.

Covers:
- ``session_scope()`` from ``backend.utils.db``
- ``_parse_asset_classes()`` from ``backend.api.analytics``
- ``_check_empty_asset_classes()``, ``_build_asset_class_in_clause()``,
  ``_append_date_account_filters()`` from ``backend.services.analytics``
- ``_apply_trade_filters()`` from ``backend.services.trade_service``
- ``_parse_rows()`` from ``backend.ingestion.csv_importer``
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from backend.ingestion.csv_importer import CSVImporter
from backend.models.trade import Trade
from backend.services.analytics import (
    _EMPTY,
    _append_date_account_filters,
    _build_asset_class_in_clause,
    _check_empty_asset_classes,
)
from backend.services.trade_service import TradeService
from backend.api.analytics import _parse_asset_classes
from backend.utils.db import session_scope


# ---------------------------------------------------------------------------
# _parse_asset_classes (API layer)
# ---------------------------------------------------------------------------

class TestParseAssetClasses:
    """Tests for the ``_parse_asset_classes`` query parameter parser."""

    def test_none_returns_none(self):
        """Omitted parameter (None) means no filter."""
        assert _parse_asset_classes(None) is None

    def test_empty_string_returns_empty_list(self):
        """Empty string means user selected nothing -> empty results."""
        assert _parse_asset_classes("") == []

    def test_single_value(self):
        result = _parse_asset_classes("stock")
        assert result == ["stock"]

    def test_multiple_values(self):
        result = _parse_asset_classes("stock,future,option")
        assert result == ["stock", "future", "option"]

    def test_strips_whitespace(self):
        result = _parse_asset_classes("  stock , future  ")
        assert result == ["stock", "future"]

    def test_lowercases_values(self):
        result = _parse_asset_classes("Stock,FUTURE")
        assert result == ["stock", "future"]

    def test_ignores_empty_segments(self):
        """Trailing commas or double commas produce no empty entries."""
        result = _parse_asset_classes("stock,,future,")
        assert result == ["stock", "future"]


# ---------------------------------------------------------------------------
# _check_empty_asset_classes (analytics service)
# ---------------------------------------------------------------------------

class TestCheckEmptyAssetClasses:
    """Tests for the empty-asset-class sentinel check."""

    def test_none_returns_none(self):
        """None input (parameter omitted) -> None (no short-circuit)."""
        assert _check_empty_asset_classes(None) is None

    def test_non_empty_list_returns_none(self):
        """Non-empty list -> None (caller proceeds normally)."""
        assert _check_empty_asset_classes(["stock"]) is None

    def test_empty_list_returns_sentinel(self):
        """Explicit empty list -> _EMPTY sentinel."""
        assert _check_empty_asset_classes([]) is _EMPTY


# ---------------------------------------------------------------------------
# _build_asset_class_in_clause (analytics service)
# ---------------------------------------------------------------------------

class TestBuildAssetClassInClause:
    """Tests for the SQL IN clause builder."""

    def test_single_asset_class(self):
        sql, params = _build_asset_class_in_clause(["stock"])
        assert sql == ":ac_0"
        assert params == {"ac_0": "stock"}

    def test_multiple_asset_classes(self):
        sql, params = _build_asset_class_in_clause(["stock", "future", "option"])
        assert sql == ":ac_0, :ac_1, :ac_2"
        assert params == {"ac_0": "stock", "ac_1": "future", "ac_2": "option"}

    def test_custom_prefix(self):
        sql, params = _build_asset_class_in_clause(["stock"], prefix="pnl_ac")
        assert sql == ":pnl_ac_0"
        assert params == {"pnl_ac_0": "stock"}

    def test_preserves_order(self):
        classes = ["future", "stock", "option"]
        sql, params = _build_asset_class_in_clause(classes)
        for i, ac in enumerate(classes):
            assert params[f"ac_{i}"] == ac


# ---------------------------------------------------------------------------
# _append_date_account_filters (analytics service)
# ---------------------------------------------------------------------------

class TestAppendDateAccountFilters:
    """Tests for the raw-SQL filter appender."""

    def test_no_filters(self):
        params: dict = {}
        result = _append_date_account_filters(
            "SELECT 1 WHERE 1=1", params,
            date_col="d", account_col="a",
        )
        assert result == "SELECT 1 WHERE 1=1"
        assert params == {}

    def test_from_date_only(self):
        params: dict = {}
        d = date(2025, 1, 1)
        result = _append_date_account_filters(
            "SELECT 1 WHERE 1=1", params,
            date_col="d", account_col="a",
            from_date=d,
        )
        assert "d >= :from_date" in result
        assert params["from_date"] == d

    def test_to_date_only(self):
        params: dict = {}
        d = date(2025, 12, 31)
        result = _append_date_account_filters(
            "SELECT 1 WHERE 1=1", params,
            date_col="d", account_col="a",
            to_date=d,
        )
        assert "d <= :to_date" in result
        assert params["to_date"] == d

    def test_account_id_only(self):
        params: dict = {}
        result = _append_date_account_filters(
            "SELECT 1 WHERE 1=1", params,
            date_col="d", account_col="a",
            account_id="U123",
        )
        assert "a = :account_id" in result
        assert params["account_id"] == "U123"

    def test_all_filters(self):
        params: dict = {}
        result = _append_date_account_filters(
            "SELECT 1 WHERE 1=1", params,
            date_col="my_date", account_col="my_acct",
            from_date=date(2025, 1, 1),
            to_date=date(2025, 12, 31),
            account_id="U999",
        )
        assert "my_date >= :from_date" in result
        assert "my_date <= :to_date" in result
        assert "my_acct = :account_id" in result
        assert len(params) == 3

    def test_mutates_params_in_place(self):
        params: dict = {"existing": "value"}
        _append_date_account_filters(
            "Q", params,
            date_col="d", account_col="a",
            from_date=date(2025, 6, 1),
        )
        assert "existing" in params
        assert "from_date" in params


# ---------------------------------------------------------------------------
# _apply_trade_filters (TradeService)
# ---------------------------------------------------------------------------

class TestApplyTradeFilters:
    """Tests for TradeService._apply_trade_filters using real DB session."""

    def _seed(self, db_session, **overrides):
        """Insert a single trade with optional overrides."""
        defaults = dict(
            id=uuid.uuid4(),
            broker="ibkr",
            broker_exec_id=f"EXEC_{uuid.uuid4().hex[:8]}",
            account_id="U1234567",
            symbol="AAPL",
            asset_class="stock",
            side="buy",
            quantity=Decimal("10"),
            price=Decimal("150.00"),
            commission=Decimal("1.00"),
            executed_at=datetime(2025, 3, 15, 12, 0, 0, tzinfo=timezone.utc),
            currency="USD",
            raw_data={"test": True},
        )
        defaults.update(overrides)
        t = Trade(**defaults)
        db_session.add(t)
        db_session.flush()
        return t

    def test_no_filters_returns_all(self, db_session):
        self._seed(db_session, symbol="AAPL")
        self._seed(db_session, symbol="MSFT")
        query = select(Trade)
        query = TradeService._apply_trade_filters(query)
        results = db_session.execute(query).scalars().all()
        assert len(results) == 2

    def test_filter_by_symbol(self, db_session):
        self._seed(db_session, symbol="AAPL")
        self._seed(db_session, symbol="MSFT")
        query = select(Trade)
        query = TradeService._apply_trade_filters(query, symbol="AAPL")
        results = db_session.execute(query).scalars().all()
        assert len(results) == 1
        assert results[0].symbol == "AAPL"

    def test_filter_by_broker(self, db_session):
        self._seed(db_session, broker="ibkr")
        self._seed(db_session, broker="tradovate")
        query = select(Trade)
        query = TradeService._apply_trade_filters(query, broker="tradovate")
        results = db_session.execute(query).scalars().all()
        assert len(results) == 1
        assert results[0].broker == "tradovate"

    def test_filter_by_asset_class(self, db_session):
        self._seed(db_session, asset_class="stock")
        self._seed(db_session, asset_class="future")
        query = select(Trade)
        query = TradeService._apply_trade_filters(query, asset_class="stock")
        results = db_session.execute(query).scalars().all()
        assert len(results) == 1
        assert results[0].asset_class == "stock"

    def test_filter_by_date_range(self, db_session):
        self._seed(
            db_session,
            executed_at=datetime(2025, 1, 10, 12, 0, 0, tzinfo=timezone.utc),
        )
        self._seed(
            db_session,
            executed_at=datetime(2025, 3, 20, 12, 0, 0, tzinfo=timezone.utc),
        )
        query = select(Trade)
        query = TradeService._apply_trade_filters(
            query,
            from_date=datetime(2025, 3, 1, 0, 0, 0, tzinfo=timezone.utc),
        )
        results = db_session.execute(query).scalars().all()
        assert len(results) == 1

    def test_filter_by_account_id(self, db_session):
        self._seed(db_session, account_id="U111")
        self._seed(db_session, account_id="U222")
        query = select(Trade)
        query = TradeService._apply_trade_filters(query, account_id="U222")
        results = db_session.execute(query).scalars().all()
        assert len(results) == 1
        assert results[0].account_id == "U222"

    def test_combined_filters(self, db_session):
        self._seed(db_session, symbol="AAPL", broker="ibkr")
        self._seed(db_session, symbol="AAPL", broker="tradovate")
        self._seed(db_session, symbol="MSFT", broker="ibkr")
        query = select(Trade)
        query = TradeService._apply_trade_filters(
            query, symbol="AAPL", broker="ibkr",
        )
        results = db_session.execute(query).scalars().all()
        assert len(results) == 1


# ---------------------------------------------------------------------------
# session_scope (utils/db)
# ---------------------------------------------------------------------------

class TestSessionScope:
    """Tests for the session_scope context manager."""

    def test_with_existing_session_yields_same(self, db_session):
        """When given an existing session, it yields it unchanged."""
        with session_scope(db_session) as s:
            assert s is db_session

    def test_with_none_creates_new_session(self):
        """When db=None, a new session is created."""
        mock_session = MagicMock()
        with patch("backend.utils.db.SessionLocal", return_value=mock_session):
            with session_scope(None) as s:
                assert s is mock_session
            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()

    def test_with_none_rollback_on_error(self):
        """When db=None and an error occurs, the session is rolled back."""
        mock_session = MagicMock()
        with patch("backend.utils.db.SessionLocal", return_value=mock_session):
            with pytest.raises(RuntimeError):
                with session_scope(None) as s:
                    raise RuntimeError("test error")
            mock_session.rollback.assert_called_once()
            mock_session.commit.assert_not_called()
            mock_session.close.assert_called_once()

    def test_existing_session_not_committed(self, db_session):
        """When given an existing session, commit/rollback/close are not called."""
        original_commit = db_session.commit
        original_close = db_session.close
        commit_called = False
        close_called = False

        def track_commit():
            nonlocal commit_called
            commit_called = True
            original_commit()

        def track_close():
            nonlocal close_called
            close_called = True
            original_close()

        db_session.commit = track_commit
        db_session.close = track_close

        with session_scope(db_session) as s:
            pass

        assert not commit_called
        assert not close_called

        # Restore
        db_session.commit = original_commit
        db_session.close = original_close

    def test_existing_session_no_rollback_on_error(self, db_session):
        """When given an existing session, rollback is NOT called on error."""
        rollback_called = False
        original_rollback = db_session.rollback

        def track_rollback():
            nonlocal rollback_called
            rollback_called = True
            original_rollback()

        db_session.rollback = track_rollback

        with pytest.raises(RuntimeError):
            with session_scope(db_session) as s:
                raise RuntimeError("test error")

        assert not rollback_called
        db_session.rollback = original_rollback


# ---------------------------------------------------------------------------
# _parse_rows (CSVImporter shared parse template)
# ---------------------------------------------------------------------------

class TestParseRows:
    """Tests for the shared ``_parse_rows`` DictReader loop."""

    def _make_csv(self, headers: list[str], rows: list[list[str]]) -> str:
        """Build a simple CSV string."""
        import csv
        import io
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)
        return buf.getvalue()

    def test_collects_single_results(self):
        """normalize_fn returning a single object is appended."""
        csv_text = self._make_csv(["a", "b"], [["1", "2"], ["3", "4"]])
        importer = CSVImporter()

        def normalizer(record, filename, row_number):
            return {"row": row_number, "a": record["a"]}

        results = importer._parse_rows(
            csv_text, "test.csv", normalizer,
            log_event="test_parsed", error_event="test_error",
        )
        assert len(results) == 2
        assert results[0]["row"] == 1
        assert results[1]["row"] == 2

    def test_collects_list_results(self):
        """normalize_fn returning a list has items flattened."""
        csv_text = self._make_csv(["a"], [["1"], ["2"]])
        importer = CSVImporter()

        def normalizer(record, filename, row_number):
            return [f"item_{row_number}_a", f"item_{row_number}_b"]

        results = importer._parse_rows(
            csv_text, "test.csv", normalizer,
            log_event="test_parsed", error_event="test_error",
        )
        assert len(results) == 4

    def test_skips_none_results(self):
        """normalize_fn returning None is silently skipped."""
        csv_text = self._make_csv(["a"], [["1"], ["2"], ["3"]])
        importer = CSVImporter()

        def normalizer(record, filename, row_number):
            if row_number == 2:
                return None
            return record["a"]

        results = importer._parse_rows(
            csv_text, "test.csv", normalizer,
            log_event="test_parsed", error_event="test_error",
        )
        assert len(results) == 2

    def test_handles_exceptions_gracefully(self):
        """Exceptions in normalize_fn are logged but do not stop parsing."""
        csv_text = self._make_csv(["a"], [["1"], ["2"], ["3"]])
        importer = CSVImporter()

        def normalizer(record, filename, row_number):
            if row_number == 2:
                raise ValueError("bad row")
            return record["a"]

        results = importer._parse_rows(
            csv_text, "test.csv", normalizer,
            log_event="test_parsed", error_event="test_error",
        )
        # Row 2 raised, so only rows 1 and 3 are included
        assert len(results) == 2

    def test_empty_csv(self):
        """Empty CSV (headers only) produces empty results."""
        csv_text = self._make_csv(["a", "b"], [])
        importer = CSVImporter()

        def normalizer(record, filename, row_number):
            return record

        results = importer._parse_rows(
            csv_text, "test.csv", normalizer,
            log_event="test_parsed", error_event="test_error",
        )
        assert results == []

    def test_passes_filename_and_row_number(self):
        """normalize_fn receives correct filename and incrementing row_number."""
        csv_text = self._make_csv(["x"], [["a"], ["b"]])
        importer = CSVImporter()
        calls = []

        def normalizer(record, filename, row_number):
            calls.append((filename, row_number))
            return record

        importer._parse_rows(
            csv_text, "my_file.csv", normalizer,
            log_event="test_parsed", error_event="test_error",
        )
        assert calls == [("my_file.csv", 1), ("my_file.csv", 2)]
