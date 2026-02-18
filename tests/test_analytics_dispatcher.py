"""Unit tests for the AnalyticsService generic dispatcher.

Verifies:
- AnalyticsService.execute() calls the query function correctly
- is_list=True returns list of Pydantic models
- is_list=False returns single Pydantic model
- row_converter is applied when provided
- Parameters are forwarded correctly to the query function
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from backend.services.analytics_registry import AnalyticsViewDef, ParamStyle
from backend.services.analytics_service import AnalyticsService


# ---------------------------------------------------------------------------
# Test schemas for dispatcher tests
# ---------------------------------------------------------------------------

class _FakeItem(BaseModel):
    """Minimal schema for list-mode tests."""
    name: str
    value: Decimal


class _FakeSingle(BaseModel):
    """Minimal schema for single-mode tests."""
    total: int
    rate: float


# ---------------------------------------------------------------------------
# AnalyticsService.execute() tests
# ---------------------------------------------------------------------------

class TestAnalyticsServiceExecute:
    """Test the generic execute() dispatcher."""

    def test_execute_list_mode(self):
        """execute() with is_list=True should return list[schema]."""
        mock_db = MagicMock()
        raw_data = [
            {"name": "AAPL", "value": "100.50"},
            {"name": "MSFT", "value": "-25.00"},
        ]
        mock_query_fn = MagicMock(return_value=raw_data)

        view = AnalyticsViewDef(
            name="test-list",
            query_fn=mock_query_fn,
            schema=_FakeItem,
            is_list=True,
        )

        service = AnalyticsService()
        result = service.execute(view, mock_db, from_date=None, to_date=None)

        # Verify query function was called with the db and params
        mock_query_fn.assert_called_once_with(
            mock_db, from_date=None, to_date=None,
        )

        # Verify result is a list of Pydantic models
        assert isinstance(result, list)
        assert len(result) == 2
        assert isinstance(result[0], _FakeItem)
        assert result[0].name == "AAPL"
        assert result[0].value == Decimal("100.50")
        assert result[1].name == "MSFT"
        assert result[1].value == Decimal("-25.00")

    def test_execute_single_mode(self):
        """execute() with is_list=False should return a single schema instance."""
        mock_db = MagicMock()
        raw_data = {"total": 42, "rate": 0.75}
        mock_query_fn = MagicMock(return_value=raw_data)

        view = AnalyticsViewDef(
            name="test-single",
            query_fn=mock_query_fn,
            schema=_FakeSingle,
            is_list=False,
        )

        service = AnalyticsService()
        result = service.execute(view, mock_db, from_date=None, to_date=None)

        mock_query_fn.assert_called_once()

        assert isinstance(result, _FakeSingle)
        assert result.total == 42
        assert result.rate == pytest.approx(0.75)

    def test_execute_with_row_converter_list(self):
        """execute() should apply row_converter to each row when is_list=True."""
        mock_db = MagicMock()
        raw_data = [
            {"name": "aapl", "value": "10"},
            {"name": "msft", "value": "20"},
        ]
        mock_query_fn = MagicMock(return_value=raw_data)

        def upper_name(row: dict) -> dict:
            return {**row, "name": row["name"].upper()}

        view = AnalyticsViewDef(
            name="test-converter-list",
            query_fn=mock_query_fn,
            schema=_FakeItem,
            is_list=True,
            row_converter=upper_name,
        )

        service = AnalyticsService()
        result = service.execute(view, mock_db)

        assert len(result) == 2
        assert result[0].name == "AAPL"
        assert result[1].name == "MSFT"

    def test_execute_with_row_converter_single(self):
        """execute() should apply row_converter for is_list=False."""
        mock_db = MagicMock()
        raw_data = {"total": 10, "rate": 0.5}
        mock_query_fn = MagicMock(return_value=raw_data)

        def double_total(row: dict) -> dict:
            return {**row, "total": row["total"] * 2}

        view = AnalyticsViewDef(
            name="test-converter-single",
            query_fn=mock_query_fn,
            schema=_FakeSingle,
            is_list=False,
            row_converter=double_total,
        )

        service = AnalyticsService()
        result = service.execute(view, mock_db)

        assert isinstance(result, _FakeSingle)
        assert result.total == 20

    def test_execute_forwards_kwargs(self):
        """execute() should forward all kwargs to the query function."""
        mock_db = MagicMock()
        mock_query_fn = MagicMock(return_value=[])

        view = AnalyticsViewDef(
            name="test-kwargs",
            query_fn=mock_query_fn,
            schema=_FakeItem,
        )

        service = AnalyticsService()
        service.execute(
            view, mock_db,
            from_date="2025-01-01",
            to_date="2025-01-31",
            account_id="U1234",
        )

        mock_query_fn.assert_called_once_with(
            mock_db,
            from_date="2025-01-01",
            to_date="2025-01-31",
            account_id="U1234",
        )

    def test_execute_empty_list(self):
        """execute() should return empty list when query returns no data."""
        mock_db = MagicMock()
        mock_query_fn = MagicMock(return_value=[])

        view = AnalyticsViewDef(
            name="test-empty",
            query_fn=mock_query_fn,
            schema=_FakeItem,
        )

        service = AnalyticsService()
        result = service.execute(view, mock_db)

        assert result == []

    def test_execute_calendar_params(self):
        """execute() should forward year/month params for calendar-style views."""
        mock_db = MagicMock()
        mock_query_fn = MagicMock(return_value=[])

        view = AnalyticsViewDef(
            name="test-calendar-params",
            query_fn=mock_query_fn,
            schema=_FakeItem,
            param_style=ParamStyle.CALENDAR,
        )

        service = AnalyticsService()
        service.execute(view, mock_db, year=2025, month=1, account_id=None)

        mock_query_fn.assert_called_once_with(
            mock_db, year=2025, month=1, account_id=None,
        )
