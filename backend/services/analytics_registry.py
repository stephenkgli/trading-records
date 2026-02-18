"""Analytics view registry.

Defines the ``AnalyticsViewDef`` descriptor and a simple module-level
registry so that views can be declared once and auto-wired into both
the service dispatcher and the FastAPI route factory.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from pydantic import BaseModel
from sqlalchemy.orm import Session


class ParamStyle(Enum):
    """Parameter patterns for analytics views."""

    DATE_RANGE = "date_range"  # from_date, to_date, account_id
    CALENDAR = "calendar"  # year, month, account_id
    CUSTOM = "custom"  # view provides its own params


@dataclass(frozen=True)
class AnalyticsViewDef:
    """Descriptor for a single analytics view."""

    name: str  # URL slug: "daily", "by-symbol", etc.
    query_fn: Callable[..., Any]  # The raw SQL query function
    schema: type[BaseModel]  # Pydantic response model
    is_list: bool = True  # True -> list[schema], False -> schema
    param_style: ParamStyle = ParamStyle.DATE_RANGE
    summary: str = ""  # OpenAPI summary for the route
    row_converter: Callable[[dict], dict] | None = None  # Optional pre-schema transform


# Module-level registry
_VIEWS: dict[str, AnalyticsViewDef] = {}


def register_view(view: AnalyticsViewDef) -> AnalyticsViewDef:
    """Register an analytics view definition."""
    if view.name in _VIEWS:
        raise ValueError(f"Duplicate analytics view name: {view.name!r}")
    _VIEWS[view.name] = view
    return view


def get_views() -> dict[str, AnalyticsViewDef]:
    """Return a read-only copy of registered views."""
    return dict(_VIEWS)
