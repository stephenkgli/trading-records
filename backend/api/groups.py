"""Trade groups API endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from backend.database import get_db
from backend.models.trade import Trade
from backend.models.trade_group import TradeGroup, TradeGroupLeg
from backend.schemas.chart import CandleBar, GroupChartResponse, GroupChartSummary, MarkerData
from backend.schemas.trade import TradeResponse
from backend.services.market_data import (
    YFinanceProvider,
    build_markers,
    choose_interval,
    compute_padded_range,
    resolve_yfinance_symbol,
)
from backend.services.trade_grouper import recompute_groups
from backend.services.analytics import refresh_daily_summaries
from backend.utils.symbol import normalize_futures_symbol

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/groups", tags=["groups"])


class TradeGroupLegResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    trade_group_id: uuid.UUID
    trade_id: uuid.UUID
    role: str


class TradeGroupResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    account_id: str
    symbol: str
    asset_class: str
    direction: str
    strategy_tag: str | None = None
    status: str
    realized_pnl: Decimal | None = None
    opened_at: datetime
    closed_at: datetime | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _normalize_symbol(self) -> "TradeGroupResponse":
        """对期货品种 symbol 进行归一化（如 MESZ5 -> MES）。"""
        self.symbol = normalize_futures_symbol(self.symbol, self.asset_class)
        return self


class TradeGroupDetailResponse(TradeGroupResponse):
    legs: list[TradeGroupLegResponse] = []


class TradeGroupListResponse(BaseModel):
    groups: list[TradeGroupResponse]
    total: int
    page: int
    per_page: int


class TradeGroupUpdateRequest(BaseModel):
    strategy_tag: str | None = None
    notes: str | None = None


class RecomputeResponse(BaseModel):
    groups_created: int
    groups_closed: int


@router.get("", response_model=TradeGroupListResponse)
def list_groups(
    status: str | None = Query(None),
    symbol: str | None = Query(None),
    account_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List trade groups with optional filters."""
    query = select(TradeGroup)

    if status:
        query = query.where(TradeGroup.status == status)
    if symbol:
        query = query.where(TradeGroup.symbol == symbol)
    if account_id:
        query = query.where(TradeGroup.account_id == account_id)

    count_query = select(func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar_one()

    query = query.order_by(TradeGroup.opened_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    groups = db.execute(query).scalars().all()

    return TradeGroupListResponse(
        groups=[TradeGroupResponse.model_validate(g) for g in groups],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{group_id}/chart", response_model=GroupChartResponse)
def get_group_chart(
    group_id: uuid.UUID,
    interval: str | None = Query(None, pattern=r"^(1m|5m|15m|1h|1d)$", description="K-line interval (1m/5m/15m/1h/1d). Auto-selected if omitted."),
    padding: int = Query(20, ge=0, le=200, description="Extra bars before/after trade range"),
    db: Session = Depends(get_db),
) -> GroupChartResponse:
    """Return OHLCV candles and trade markers for a group's chart.

    Loads the trade group and its legs (with associated trades), fetches
    market data for the symbol over the relevant time range, and returns
    candle data plus lightweight-charts-compatible markers.
    """
    # Load group with legs -> trades eagerly
    group = db.execute(
        select(TradeGroup)
        .options(
            joinedload(TradeGroup.legs).joinedload(TradeGroupLeg.trade),
        )
        .where(TradeGroup.id == group_id)
    ).unique().scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail="Trade group not found")

    if not group.legs:
        raise HTTPException(status_code=404, detail="Trade group has no legs")

    # Determine interval
    resolved_interval = interval or choose_interval(group.opened_at, group.closed_at)

    # Compute padded time range
    start, end = compute_padded_range(
        group.opened_at, group.closed_at, resolved_interval, padding,
    )

    # Resolve symbol for yfinance (e.g. MESZ5 -> MES=F for futures)
    display_symbol = normalize_futures_symbol(group.symbol, group.asset_class)
    yf_symbol = resolve_yfinance_symbol(group.symbol, group.asset_class)

    # Fetch OHLCV data
    provider = YFinanceProvider()
    try:
        bars = provider.fetch_ohlcv(yf_symbol, resolved_interval, start, end)
    except Exception:
        logger.exception(
            "ohlcv_fetch_failed",
            symbol=yf_symbol,
            interval=resolved_interval,
            group_id=str(group_id),
        )
        raise HTTPException(
            status_code=502,
            detail="Failed to fetch market data from upstream provider",
        )

    # Build markers from legs
    markers_raw = build_markers(group.legs, group.direction)
    markers = [MarkerData(**m) for m in markers_raw]

    # Serialize candles as typed models with float values for JSON charting compatibility
    candles = [
        CandleBar(
            time=bar.time,
            open=float(bar.open),
            high=float(bar.high),
            low=float(bar.low),
            close=float(bar.close),
            volume=bar.volume,
        )
        for bar in bars
    ]

    return GroupChartResponse(
        symbol=display_symbol,
        interval=resolved_interval,
        candles=candles,
        markers=markers,
        group=GroupChartSummary(
            direction=group.direction,
            realized_pnl=group.realized_pnl,
            opened_at=group.opened_at,
            closed_at=group.closed_at,
        ),
    )


@router.get("/{group_id}", response_model=TradeGroupDetailResponse)
def get_group(group_id: uuid.UUID, db: Session = Depends(get_db)):
    """Get a single trade group with its legs."""
    group = db.execute(
        select(TradeGroup)
        .options(joinedload(TradeGroup.legs))
        .where(TradeGroup.id == group_id)
    ).unique().scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail="Trade group not found")

    return TradeGroupDetailResponse(
        id=group.id,
        account_id=group.account_id,
        symbol=group.symbol,
        asset_class=group.asset_class,
        direction=group.direction,
        strategy_tag=group.strategy_tag,
        status=group.status,
        realized_pnl=group.realized_pnl,
        opened_at=group.opened_at,
        closed_at=group.closed_at,
        notes=group.notes,
        legs=[TradeGroupLegResponse.model_validate(leg) for leg in group.legs],
    )


@router.patch("/{group_id}", response_model=TradeGroupResponse)
def update_group(
    group_id: uuid.UUID,
    update: TradeGroupUpdateRequest,
    db: Session = Depends(get_db),
):
    """Update strategy tag and/or notes on a group."""
    group = db.get(TradeGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Trade group not found")

    if update.strategy_tag is not None:
        group.strategy_tag = update.strategy_tag
    if update.notes is not None:
        group.notes = update.notes

    db.commit()
    db.refresh(group)
    return TradeGroupResponse.model_validate(group)


@router.post("/recompute", response_model=RecomputeResponse)
def recompute(
    symbol: str | None = Query(None),
    account_id: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Recompute trade groupings.

    Optionally filter by symbol and/or account_id.
    Deletes existing groups for the scope and rebuilds from scratch.
    """
    result = recompute_groups(db=db, symbol=symbol, account_id=account_id)

    # 刷新 materialized view，使 daily_summaries 反映最新的 trade_groups 数据
    bind = db.get_bind()
    if bind and bind.dialect.name == "postgresql":
        try:
            refresh_daily_summaries(db=db)
        except Exception:
            pass  # 刷新失败不影响 recompute 结果

    return RecomputeResponse(**result)
