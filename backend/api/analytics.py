"""Analytics API endpoints.

Routes are generated from the analytics view registry so that adding
a new view requires only a ``register_view()`` call in
``backend/services/analytics_views`` (plus the query function and
Pydantic schema).
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.api.dependencies import get_analytics_service
from backend.database import get_db
from backend.services.analytics import get_available_asset_classes
from backend.services.analytics_registry import (
    AnalyticsViewDef,
    ParamStyle,
    get_views,
)
from backend.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


def _parse_asset_classes(raw: str | None) -> list[str] | None:
    """Parse a comma-separated asset_classes query parameter.

    Semantics:
    - ``None`` (parameter omitted) -> ``None`` (no filter, query all).
    - ``""`` (empty string passed) -> ``[]`` (empty list, return empty results).
    - ``"stock,future"`` -> ``["stock", "future"]`` (filter by these types).
    """
    if raw is None:
        return None
    return [s.strip().lower() for s in raw.split(",") if s.strip()]


def _make_date_range_handler(view: AnalyticsViewDef):
    """Create a FastAPI handler for a standard date-range view."""
    resp_model = list[view.schema] if view.is_list else view.schema

    @router.get(f"/{view.name}", response_model=resp_model, summary=view.summary)
    def handler(
        from_date: date | None = Query(None, alias="from"),
        to_date: date | None = Query(None, alias="to"),
        account_id: str | None = Query(None),
        asset_classes: Optional[str] = Query(None, description="逗号分隔的资产类型列表，如 stock,future,option,forex"),
        db: Session = Depends(get_db),
        service: AnalyticsService = Depends(get_analytics_service),
    ):
        # 将逗号分隔的 asset_classes 字符串解析为列表
        asset_class_list = _parse_asset_classes(asset_classes)
        return service.execute(
            view, db,
            from_date=from_date, to_date=to_date, account_id=account_id,
            asset_classes=asset_class_list,
        )

    handler.__name__ = view.name.replace("-", "_")
    handler.__qualname__ = handler.__name__
    return handler


def _make_calendar_handler(view: AnalyticsViewDef):
    """Create a FastAPI handler for the calendar param style."""

    @router.get(
        f"/{view.name}",
        response_model=list[view.schema],
        summary=view.summary,
    )
    def handler(
        year: int = Query(...),
        month: int = Query(..., ge=1, le=12),
        account_id: str | None = Query(None),
        db: Session = Depends(get_db),
        service: AnalyticsService = Depends(get_analytics_service),
    ):
        return service.execute(
            view, db,
            year=year, month=month, account_id=account_id,
        )

    handler.__name__ = view.name.replace("-", "_")
    handler.__qualname__ = handler.__name__
    return handler


# --- Wire up all registered views ---
_FACTORY = {
    ParamStyle.DATE_RANGE: _make_date_range_handler,
    ParamStyle.CALENDAR: _make_calendar_handler,
}

for _view in get_views().values():
    factory = _FACTORY.get(_view.param_style)
    if factory is None:
        raise ValueError(
            f"No route factory for param_style={_view.param_style!r} "
            f"on view {_view.name!r}. Use ParamStyle.CUSTOM and register "
            f"the route manually."
        )
    factory(_view)


# --- 手动注册的端点 ---

@router.get("/asset-classes", response_model=list[str], summary="获取所有可用的资产类型列表")
def list_available_asset_classes(
    db: Session = Depends(get_db),
):
    """返回数据库中所有已关闭 trade_group 的资产类型（去重排序）。"""
    return get_available_asset_classes(db)
