"""Trade groups API endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from backend.database import get_db
from backend.models.trade_group import TradeGroup, TradeGroupLeg
from backend.schemas.trade import TradeResponse
from backend.services.trade_grouper import recompute_groups

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
    realized_pnl: str | None = None
    opened_at: str
    closed_at: str | None = None
    notes: str | None = None


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
        realized_pnl=str(group.realized_pnl) if group.realized_pnl is not None else None,
        opened_at=group.opened_at.isoformat(),
        closed_at=group.closed_at.isoformat() if group.closed_at else None,
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
    return RecomputeResponse(**result)
