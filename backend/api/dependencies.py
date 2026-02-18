"""FastAPI dependency injection for services.

Centralises service instantiation so API handlers receive services
via ``Depends()`` and tests can override them.
"""

from __future__ import annotations

from backend.services.analytics_service import AnalyticsService
from backend.services.import_service import ImportService
from backend.services.trade_service import TradeService


def get_import_service() -> ImportService:
    """Provide an ImportService instance."""
    return ImportService()


def get_trade_service() -> TradeService:
    """Provide a TradeService instance."""
    return TradeService()


def get_analytics_service() -> AnalyticsService:
    """Provide an AnalyticsService instance."""
    return AnalyticsService()
