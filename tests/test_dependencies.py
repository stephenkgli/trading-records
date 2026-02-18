"""
Tests for the dependency injection module (backend/api/dependencies.py).

Verifies:
1. get_import_service returns ImportService instance
2. get_trade_service returns TradeService instance
3. get_analytics_service returns AnalyticsService instance
4. Services are usable (not stale singletons)
"""

from __future__ import annotations

from backend.api.dependencies import (
    get_analytics_service,
    get_import_service,
    get_trade_service,
)
from backend.services.analytics_service import AnalyticsService
from backend.services.import_service import ImportService
from backend.services.trade_service import TradeService


class TestDependencyInjection:
    """Test dependency injection factory functions."""

    def test_get_import_service_type(self):
        """get_import_service should return an ImportService."""
        svc = get_import_service()
        assert isinstance(svc, ImportService)

    def test_get_trade_service_type(self):
        """get_trade_service should return a TradeService."""
        svc = get_trade_service()
        assert isinstance(svc, TradeService)

    def test_get_analytics_service_type(self):
        """get_analytics_service should return an AnalyticsService."""
        svc = get_analytics_service()
        assert isinstance(svc, AnalyticsService)

    def test_get_import_service_new_instance(self):
        """Each call should return a new instance (not cached)."""
        svc1 = get_import_service()
        svc2 = get_import_service()
        assert svc1 is not svc2

    def test_get_trade_service_new_instance(self):
        """Each call should return a new instance."""
        svc1 = get_trade_service()
        svc2 = get_trade_service()
        assert svc1 is not svc2

    def test_get_analytics_service_new_instance(self):
        """Each call should return a new instance."""
        svc1 = get_analytics_service()
        svc2 = get_analytics_service()
        assert svc1 is not svc2
