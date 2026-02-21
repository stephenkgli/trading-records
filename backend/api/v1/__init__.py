"""API v1 router aggregation.

Collects all v1 route modules and exposes a single ``v1_router`` that
can be included in the FastAPI app.
"""

from fastapi import APIRouter

from backend.api.analytics import router as analytics_router
from backend.api.config import router as config_router
from backend.api.groups import router as groups_router
from backend.api.health import router as health_router
from backend.api.imports import router as imports_router
from backend.api.market_data import router as market_data_router
from backend.api.trades import router as trades_router

v1_router = APIRouter()
v1_router.include_router(health_router)
v1_router.include_router(trades_router)
v1_router.include_router(imports_router)
v1_router.include_router(groups_router)
v1_router.include_router(analytics_router)
v1_router.include_router(config_router)
v1_router.include_router(market_data_router)

__all__ = ["v1_router"]
