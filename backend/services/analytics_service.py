"""Analytics service -- generic analytics query dispatcher.

Provides a single ``execute()`` method that looks up a registered
:class:`AnalyticsViewDef` and returns validated Pydantic model(s).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.services.analytics_registry import AnalyticsViewDef

# Ensure views are registered on import
import backend.services.analytics_views  # noqa: F401


class AnalyticsService:
    """Generic analytics query dispatcher."""

    def execute(
        self,
        view: AnalyticsViewDef,
        db: Session,
        **params: Any,
    ) -> BaseModel | list[BaseModel]:
        """Execute an analytics view and return validated Pydantic model(s)."""
        raw = view.query_fn(db, **params)

        if view.is_list:
            if view.row_converter:
                raw = [view.row_converter(row) for row in raw]
            return [view.schema(**row) for row in raw]

        if view.row_converter:
            raw = view.row_converter(raw)
        return view.schema(**raw)
