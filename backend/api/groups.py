"""Trade groups API endpoints."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, model_validator
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from backend.database import get_db
from backend.models.trade import Trade
from backend.models.trade_group import TradeGroup, TradeGroupLeg
from backend.schemas.chart import CandleBar, GroupChartResponse, GroupChartSummary, MarkerData
from backend.schemas.trade import TradeResponse
from backend.services.cache.ohlcv_cache import OHLCVCacheService
from backend.services.market_data import (
    MarketDataProvider,
    build_markers,
    compute_padded_range,
    default_interval,
)
from backend.services.providers.databento_provider import DabentoProvider
from backend.services.providers.errors import ProviderError
from backend.services.providers.rate_limit import RateLimitError
from backend.services.providers.tiingo_provider import TiingoProvider
from backend.services.trade_grouper import recompute_groups
from backend.services.analytics import refresh_daily_summaries
from backend.utils.symbol import normalize_futures_symbol

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/groups", tags=["groups"])


def _parse_asset_classes(raw: str | None) -> list[str] | None:
    """Parse a comma-separated asset_classes query parameter.

    Semantics:
    - ``None`` (parameter omitted) -> ``None`` (no filter).
    - ``""`` (empty string passed) -> ``[]`` (explicit empty selection).
    - ``"stock,future"`` -> ``["stock", "future"]``.
    """
    if raw is None:
        return None
    return [s.strip().lower() for s in raw.split(",") if s.strip()]


def _get_provider(asset_class: str) -> MarketDataProvider:
    """Pick provider by asset class."""
    if asset_class == "future":
        return DabentoProvider()
    elif asset_class in ("stock", "option"):
        return TiingoProvider()
    else:
        raise ProviderError(f"No provider for asset_class={asset_class}")


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
    asset_classes: str | None = Query(
        None,
        description="Comma-separated asset classes, e.g. stock,future,option,forex",
    ),
    closed_from: datetime | None = Query(None, description="Filter groups closed on or after this datetime"),
    closed_to: datetime | None = Query(None, description="Filter groups closed strictly before this datetime"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    sort: str = Query("opened_at"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    """List trade groups with filtering, global sorting, and pagination."""
    asset_class_list = _parse_asset_classes(asset_classes)
    if asset_class_list is not None and len(asset_class_list) == 0:
        return TradeGroupListResponse(groups=[], total=0, page=page, per_page=per_page)

    query = select(TradeGroup)

    if status:
        query = query.where(TradeGroup.status == status)
    if symbol:
        query = query.where(TradeGroup.symbol == symbol)
    if account_id:
        query = query.where(TradeGroup.account_id == account_id)
    if asset_class_list:
        query = query.where(TradeGroup.asset_class.in_(asset_class_list))
    if closed_from:
        query = query.where(TradeGroup.closed_at >= closed_from)
    if closed_to:
        query = query.where(TradeGroup.closed_at < closed_to)

    count_query = select(func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar_one()

    sortable_columns = {
        "symbol": TradeGroup.symbol,
        "direction": TradeGroup.direction,
        "status": TradeGroup.status,
        "realized_pnl": TradeGroup.realized_pnl,
        "opened_at": TradeGroup.opened_at,
        "closed_at": TradeGroup.closed_at,
    }
    sort_column = sortable_columns.get(sort, TradeGroup.opened_at)
    if order == "asc":
        query = query.order_by(sort_column.asc().nulls_last(), TradeGroup.id.asc())
    else:
        query = query.order_by(sort_column.desc().nulls_last(), TradeGroup.id.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    groups = db.execute(query).scalars().all()

    return TradeGroupListResponse(
        groups=[TradeGroupResponse.model_validate(g) for g in groups],
        total=total,
        page=page,
        per_page=per_page,
    )


class ActiveGroupResponse(TradeGroupResponse):
    day_roles: list[str]


class ActiveGroupsListResponse(BaseModel):
    groups: list[ActiveGroupResponse]


@router.get("/by-activity-date", response_model=ActiveGroupsListResponse)
def list_groups_by_activity_date(
    target_date: date = Query(..., alias="date", description="Date to find active groups for (YYYY-MM-DD)"),
    account_id: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """List trade groups that had any leg activity on the given date."""
    bind = db.get_bind()
    is_pg = bind is not None and bind.dialect.name == "postgresql"

    if is_pg:
        agg_fn = "STRING_AGG(DISTINCT tgl.role, ',')"
        date_cast = "DATE(t.executed_at AT TIME ZONE 'UTC')"
    else:
        agg_fn = "GROUP_CONCAT(DISTINCT tgl.role)"
        date_cast = "DATE(t.executed_at)"

    query = f"""
        SELECT tg.id, tg.account_id, tg.symbol, tg.asset_class,
               tg.direction, tg.strategy_tag, tg.status,
               tg.realized_pnl, tg.opened_at, tg.closed_at, tg.notes,
               {agg_fn} AS day_roles
        FROM trade_groups tg
        JOIN trade_group_legs tgl ON tgl.trade_group_id = tg.id
        JOIN trades t ON t.id = tgl.trade_id
        WHERE {date_cast} = :target_date
    """
    params: dict = {"target_date": target_date.isoformat() if not is_pg else target_date}

    if account_id:
        query += " AND tg.account_id = :account_id"
        params["account_id"] = account_id

    query += " GROUP BY tg.id ORDER BY tg.opened_at ASC"

    rows = db.execute(text(query), params).mappings().all()

    groups = []
    for row in rows:
        roles_str = row["day_roles"] or ""
        day_roles = [r.strip() for r in roles_str.split(",") if r.strip()]
        group_data = {
            "id": row["id"],
            "account_id": row["account_id"],
            "symbol": row["symbol"],
            "asset_class": row["asset_class"],
            "direction": row["direction"],
            "strategy_tag": row["strategy_tag"],
            "status": row["status"],
            "realized_pnl": row["realized_pnl"],
            "opened_at": row["opened_at"],
            "closed_at": row["closed_at"],
            "notes": row["notes"],
            "day_roles": day_roles,
        }
        groups.append(ActiveGroupResponse(**group_data))

    return ActiveGroupsListResponse(groups=groups)


@router.get("/{group_id}/chart", response_model=GroupChartResponse)
def get_group_chart(
    group_id: uuid.UUID,
    interval: str | None = Query(None, pattern=r"^(1m|5m|15m|1h|1d)$", description="K-line interval (1m/5m/15m/1h/1d). Auto-selected by asset class if omitted."),
    padding: int = Query(50, ge=0, le=200, description="Extra bars before/after trade range"),
    db: Session = Depends(get_db),
) -> GroupChartResponse:
    """Return OHLCV candles and trade markers for a group's chart."""
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

    # Determine interval: explicit param > asset_class default
    resolved_interval = interval or default_interval(group.asset_class)

    # Compute padded time range
    start, end = compute_padded_range(
        group.opened_at, group.closed_at, resolved_interval, padding,
    )

    # Fetch OHLCV data — provider handles symbol mapping internally
    display_symbol = normalize_futures_symbol(group.symbol, group.asset_class)
    cache_symbol = (
        f"{display_symbol}__RTH"
        if group.asset_class == "future"
        else display_symbol
    )

    cache = OHLCVCacheService(db)

    # 1. Try cache
    bars = cache.get(cache_symbol, resolved_interval, start, end)

    if bars is None:
        # 2. Fetch from provider (fail-fast on error)
        provider = _get_provider(group.asset_class)
        try:
            bars = provider.fetch_ohlcv(
                group.symbol, group.asset_class, resolved_interval, start, end,
            )
        except RateLimitError:
            raise HTTPException(
                status_code=429,
                detail="Provider rate limit exceeded. Try again tomorrow.",
            )
        except ProviderError as e:
            raise HTTPException(status_code=502, detail=str(e))
        except Exception:
            logger.exception(
                "ohlcv_fetch_failed",
                symbol=group.symbol,
                interval=resolved_interval,
                group_id=str(group_id),
            )
            raise HTTPException(
                status_code=502,
                detail="Failed to fetch market data from upstream provider",
            )

        # 3. Cache completed bars
        if bars:
            provider_tag = provider.__class__.__name__.lower().replace("provider", "")
            cache.put(cache_symbol, resolved_interval, group.asset_class, provider_tag, bars)

    if not bars:
        # Return an empty chart instead of 404 so the frontend can still
        # render markers and group info even when market data is unavailable
        # (e.g. expired contracts, weekends, provider gaps).
        bars = []

    # Build markers from legs, snap marker times to actual candle bars
    bar_times = [bar.time for bar in bars]
    markers_raw = build_markers(group.legs, group.direction, bar_times=bar_times)
    markers = [MarkerData(**m) for m in markers_raw]

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
        except SQLAlchemyError:
            logger.debug("daily_summaries_refresh_skipped_after_recompute")

    return RecomputeResponse(**result)
