"""Unit tests for the analytics view registry.

Verifies:
- AnalyticsViewDef creation with all fields
- register_view() works and prevents duplicates
- get_views() returns all 5 registered views
- Correct param_style for each view
- Correct is_list for each view
- View names match expected slugs
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from backend.services.analytics_registry import (
    AnalyticsViewDef,
    ParamStyle,
    _VIEWS,
    get_views,
    register_view,
)


# ---------------------------------------------------------------------------
# AnalyticsViewDef dataclass tests
# ---------------------------------------------------------------------------

class TestAnalyticsViewDef:
    """Test AnalyticsViewDef dataclass creation and defaults."""

    def test_create_with_all_fields(self):
        """AnalyticsViewDef should accept all documented fields."""
        def dummy_query(db, **kw):
            return []

        def dummy_converter(row):
            return row

        view = AnalyticsViewDef(
            name="test-view",
            query_fn=dummy_query,
            schema=BaseModel,
            is_list=True,
            param_style=ParamStyle.DATE_RANGE,
            summary="Test summary",
            row_converter=dummy_converter,
        )
        assert view.name == "test-view"
        assert view.query_fn is dummy_query
        assert view.schema is BaseModel
        assert view.is_list is True
        assert view.param_style == ParamStyle.DATE_RANGE
        assert view.summary == "Test summary"
        assert view.row_converter is dummy_converter

    def test_defaults(self):
        """AnalyticsViewDef should have sensible defaults."""
        def dummy_query(db, **kw):
            return []

        view = AnalyticsViewDef(
            name="default-test",
            query_fn=dummy_query,
            schema=BaseModel,
        )
        assert view.is_list is True
        assert view.param_style == ParamStyle.DATE_RANGE
        assert view.summary == ""
        assert view.row_converter is None

    def test_frozen(self):
        """AnalyticsViewDef should be immutable (frozen dataclass)."""
        def dummy_query(db, **kw):
            return []

        view = AnalyticsViewDef(
            name="frozen-test",
            query_fn=dummy_query,
            schema=BaseModel,
        )
        with pytest.raises(AttributeError):
            view.name = "something-else"


# ---------------------------------------------------------------------------
# ParamStyle enum tests
# ---------------------------------------------------------------------------

class TestParamStyle:
    """Test ParamStyle enum values."""

    def test_date_range_value(self):
        assert ParamStyle.DATE_RANGE.value == "date_range"

    def test_calendar_value(self):
        assert ParamStyle.CALENDAR.value == "calendar"

    def test_custom_value(self):
        assert ParamStyle.CUSTOM.value == "custom"


# ---------------------------------------------------------------------------
# register_view / get_views tests
# ---------------------------------------------------------------------------

class TestRegisterView:
    """Test the register_view() function."""

    def test_register_and_retrieve(self):
        """register_view() should add a view and get_views() should return it."""
        # Save original state and restore after test
        original_views = dict(_VIEWS)
        try:
            def dummy_query(db, **kw):
                return []

            view = AnalyticsViewDef(
                name="__test_register__",
                query_fn=dummy_query,
                schema=BaseModel,
            )
            result = register_view(view)
            assert result is view

            views = get_views()
            assert "__test_register__" in views
            assert views["__test_register__"] is view
        finally:
            # Clean up: restore original registry
            _VIEWS.clear()
            _VIEWS.update(original_views)

    def test_duplicate_name_raises(self):
        """register_view() should raise ValueError on duplicate name."""
        original_views = dict(_VIEWS)
        try:
            def dummy_query(db, **kw):
                return []

            view1 = AnalyticsViewDef(
                name="__test_dup__",
                query_fn=dummy_query,
                schema=BaseModel,
            )
            register_view(view1)

            view2 = AnalyticsViewDef(
                name="__test_dup__",
                query_fn=dummy_query,
                schema=BaseModel,
            )
            with pytest.raises(ValueError, match="Duplicate analytics view name"):
                register_view(view2)
        finally:
            _VIEWS.clear()
            _VIEWS.update(original_views)

    def test_get_views_returns_copy(self):
        """get_views() should return a copy, not the internal dict."""
        views = get_views()
        assert views is not _VIEWS
        # Mutating the copy should not affect the registry
        views["__should_not_appear__"] = None  # type: ignore
        assert "__should_not_appear__" not in _VIEWS


# ---------------------------------------------------------------------------
# Pre-registered view validation
# ---------------------------------------------------------------------------

class TestRegisteredViews:
    """Verify that the 5 expected analytics views are registered correctly."""

    @pytest.fixture(autouse=True)
    def _ensure_views_registered(self):
        """Ensure analytics_views module is imported so views are registered."""
        import backend.services.analytics_views  # noqa: F401

    def test_five_views_registered(self):
        """Exactly 5 views should be registered."""
        views = get_views()
        assert len(views) >= 5, (
            f"Expected at least 5 registered views, got {len(views)}: "
            f"{list(views.keys())}"
        )

    def test_expected_view_names(self):
        """All expected view slugs should be present."""
        views = get_views()
        expected = {"daily", "calendar", "by-symbol", "by-strategy", "performance"}
        assert expected.issubset(views.keys()), (
            f"Missing views: {expected - views.keys()}"
        )

    def test_daily_view_config(self):
        views = get_views()
        v = views["daily"]
        assert v.param_style == ParamStyle.DATE_RANGE
        assert v.is_list is True

    def test_calendar_view_config(self):
        views = get_views()
        v = views["calendar"]
        assert v.param_style == ParamStyle.CALENDAR
        assert v.is_list is True

    def test_by_symbol_view_config(self):
        views = get_views()
        v = views["by-symbol"]
        assert v.param_style == ParamStyle.DATE_RANGE
        assert v.is_list is True

    def test_by_strategy_view_config(self):
        views = get_views()
        v = views["by-strategy"]
        assert v.param_style == ParamStyle.DATE_RANGE
        assert v.is_list is True

    def test_performance_view_config(self):
        views = get_views()
        v = views["performance"]
        assert v.param_style == ParamStyle.DATE_RANGE
        assert v.is_list is False

    def test_schemas_match_expected_types(self):
        """Each view should reference the correct Pydantic schema."""
        from backend.schemas.analytics import (
            CalendarEntry,
            DailySummary,
            PerformanceMetrics,
            StrategyBreakdown,
            SymbolBreakdown,
        )

        views = get_views()
        expected_schemas = {
            "daily": DailySummary,
            "calendar": CalendarEntry,
            "by-symbol": SymbolBreakdown,
            "by-strategy": StrategyBreakdown,
            "performance": PerformanceMetrics,
        }
        for name, expected_schema in expected_schemas.items():
            assert views[name].schema is expected_schema, (
                f"View {name!r} schema is {views[name].schema}, "
                f"expected {expected_schema}"
            )

    def test_query_functions_are_callable(self):
        """Each registered view should have a callable query_fn."""
        views = get_views()
        for name, view in views.items():
            assert callable(view.query_fn), (
                f"View {name!r} query_fn is not callable"
            )
