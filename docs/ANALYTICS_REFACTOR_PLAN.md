# Analytics Subsystem Refactoring Plan

## Current State Analysis

The analytics subsystem currently spans 7 files across backend and frontend. Adding a
single new analytics view (e.g. "by day-of-week") requires manual edits to all 7:

| Layer | File | What you add per view |
|-------|------|-----------------------|
| SQL queries | `backend/services/analytics.py` | New `get_*()` function with raw SQL |
| Service wrapper | `backend/services/analytics_service.py` | New method calling query, converting to schema |
| Pydantic schema | `backend/schemas/analytics.py` | New `BaseModel` class |
| FastAPI endpoint | `backend/api/analytics.py` | New `@router.get()` handler |
| TS types | `frontend/src/api/types/analytics.ts` | New `interface` |
| TS fetch | `frontend/src/api/endpoints/analytics.ts` | New `fetch*()` function |
| React hook | `frontend/src/api/hooks/index.ts` | New `use*()` hook |

Additionally, each endpoint/service/type barrel file must be updated with new exports.

### Pattern Observations

Despite having 5 views, almost all of them share the same shape:

- **Standard date-range views** (`daily`, `by-symbol`, `by-strategy`, `performance`): Accept
  `from_date`, `to_date`, `account_id` query parameters. The API handler, service method,
  and query function all repeat the same 3-parameter plumbing.

- **Calendar view**: A special case that takes `year`/`month` instead, but internally
  delegates to `get_daily_summaries` with computed date bounds.

On the frontend, every analytics hook follows the exact same `useQuery` wrapper pattern
with identical loading/error/refetch lifecycle.

### Where duplication lives

1. **Parameter threading**: `from_date`/`to_date`/`account_id` is declared identically in
   the API handler, service method, and query function -- 3x per view.
2. **Service layer**: `AnalyticsService` methods do almost nothing except call the
   corresponding query function and wrap results in `[Schema(**row) for row in data]`.
3. **API handlers**: Every handler is ~8 lines of identical structure: extract params, call
   service, return result.
4. **Frontend fetch functions**: Identical `URLSearchParams` construction and
   `handleResponse` call pattern.
5. **Frontend hooks**: Identical `useQuery` wrapping with the same deps pattern.

---

## Problem Statement

Adding a new analytics view requires touching 7 files and writing ~80 lines of
mostly-boilerplate code across backend and frontend. This creates friction for new
views and increases the surface area for copy-paste errors.

The goal: reduce the "new view" change surface so that a developer defines (a) the SQL
query logic, (b) the Pydantic response schema, and has everything else either auto-wired
or generated with minimal additional code.

---

## Proposed Architecture

### Design Principles

1. **Convention over configuration** -- views that follow the standard
   `(from_date, to_date, account_id)` parameter pattern get wired automatically.
2. **Explicit registration, not magic** -- a simple registry dict, not metaclasses or
   module scanning.
3. **Preserve type safety** -- Pydantic `response_model` stays explicit on every route;
   TypeScript interfaces remain hand-written (not codegen).
4. **No changes outside analytics** -- models, ingestion, trades, config, exceptions,
   dependencies are untouched.
5. **Backward compatible** -- same URL paths, same response shapes, same query params.
   Zero breaking changes for frontend consumers.

### Backend: View Registry + Route Factory

#### 1. Define an `AnalyticsView` descriptor

Each analytics view is described by a small dataclass that holds everything the framework
needs to wire up the service method and API route:

```python
# backend/services/analytics_registry.py

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any, Callable, TypeVar

from pydantic import BaseModel
from sqlalchemy.orm import Session


class ParamStyle(Enum):
    """Parameter patterns for analytics views."""
    DATE_RANGE = "date_range"       # from_date, to_date, account_id
    CALENDAR = "calendar"           # year, month, account_id
    CUSTOM = "custom"               # view provides its own params


T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class AnalyticsViewDef:
    """Descriptor for a single analytics view."""

    name: str                           # URL slug: "daily", "by-symbol", etc.
    query_fn: Callable[..., Any]        # The raw SQL query function
    schema: type[BaseModel]             # Pydantic response model
    is_list: bool = True                # True -> list[schema], False -> schema
    param_style: ParamStyle = ParamStyle.DATE_RANGE
    summary: str = ""                   # OpenAPI summary for the route
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
```

#### 2. Register existing views

The existing query functions in `analytics.py` stay as-is. Registration happens in
a single block at the bottom of `analytics_service.py` (or a dedicated file):

```python
# backend/services/analytics_views.py  (new file, ~60 lines)

"""Analytics view registrations.

Each call to register_view() wires a SQL query function + Pydantic schema
into the analytics route factory. To add a new standard date-range view,
add one register_view() call here and one Pydantic model in schemas/analytics.py.
"""

from backend.schemas.analytics import (
    CalendarEntry,
    DailySummary,
    PerformanceMetrics,
    StrategyBreakdown,
    SymbolBreakdown,
)
from backend.services.analytics import (
    get_by_strategy,
    get_by_symbol,
    get_calendar_data,
    get_daily_summaries,
    get_performance_metrics,
)
from backend.services.analytics_registry import (
    AnalyticsViewDef,
    ParamStyle,
    register_view,
)


register_view(AnalyticsViewDef(
    name="daily",
    query_fn=get_daily_summaries,
    schema=DailySummary,
    summary="Get daily P&L summaries from materialized view",
))

register_view(AnalyticsViewDef(
    name="calendar",
    query_fn=get_calendar_data,
    schema=CalendarEntry,
    param_style=ParamStyle.CALENDAR,
    summary="Get monthly calendar data for P&L heatmap",
))

register_view(AnalyticsViewDef(
    name="by-symbol",
    query_fn=get_by_symbol,
    schema=SymbolBreakdown,
    summary="Get per-symbol P&L breakdown",
))

register_view(AnalyticsViewDef(
    name="by-strategy",
    query_fn=get_by_strategy,
    schema=StrategyBreakdown,
    summary="Get per-strategy P&L breakdown",
))

register_view(AnalyticsViewDef(
    name="performance",
    query_fn=get_performance_metrics,
    schema=PerformanceMetrics,
    is_list=False,
    summary="Get overall performance statistics",
))
```

#### 3. Replace AnalyticsService with a generic dispatcher

The current `AnalyticsService` has one method per view. Replace it with a single
`execute_view()` method that looks up the registry:

```python
# backend/services/analytics_service.py  (simplified, ~40 lines)

from __future__ import annotations

from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.services.analytics_registry import AnalyticsViewDef, get_views

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
```

#### 4. Replace hand-written routes with a route factory

The API file becomes a loop that generates one route per registered view:

```python
# backend/api/analytics.py  (simplified, ~70 lines)

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.api.dependencies import get_analytics_service
from backend.database import get_db
from backend.services.analytics_registry import (
    AnalyticsViewDef,
    ParamStyle,
    get_views,
)
from backend.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


def _make_date_range_handler(view: AnalyticsViewDef):
    """Create a FastAPI handler for a standard date-range view."""

    # Build the correct response_model annotation
    resp_model = list[view.schema] if view.is_list else view.schema

    @router.get(f"/{view.name}", response_model=resp_model, summary=view.summary)
    def handler(
        from_date: date | None = Query(None, alias="from"),
        to_date: date | None = Query(None, alias="to"),
        account_id: str | None = Query(None),
        db: Session = Depends(get_db),
        service: AnalyticsService = Depends(get_analytics_service),
    ):
        return service.execute(
            view, db,
            from_date=from_date, to_date=to_date, account_id=account_id,
        )

    handler.__name__ = view.name.replace("-", "_")
    handler.__qualname__ = handler.__name__
    return handler


def _make_calendar_handler(view: AnalyticsViewDef):
    """Create a FastAPI handler for the calendar param style."""

    @router.get(f"/{view.name}", response_model=list[view.schema], summary=view.summary)
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
```

#### Key detail: `response_model` stays explicit

FastAPI uses `response_model` for OpenAPI schema generation and response validation.
The factory builds `list[view.schema]` or `view.schema` dynamically, but each
generated route still has a concrete `response_model` -- no `Any` leaks.

### Frontend: Thin Fetch Generator + Hooks Stay Generic

The frontend already has a good generic `useQuery` hook. The main savings come from
the fetch function layer.

#### 5. Replace per-view fetch functions with a factory

```typescript
// frontend/src/api/endpoints/analytics.ts  (simplified)

import { getApiBase, getHeaders, handleResponse } from "./http";
import type {
  DailySummary,
  CalendarEntry,
  SymbolBreakdown,
  PerformanceMetrics,
} from "../types";

// -- Generic date-range fetcher factory --

function makeDateRangeFetcher<T>(path: string) {
  return async (from?: string, to?: string): Promise<T> => {
    const params = new URLSearchParams();
    if (from) params.set("from", from);
    if (to) params.set("to", to);
    const qs = params.toString();
    const url = `${getApiBase()}/analytics/${path}${qs ? `?${qs}` : ""}`;
    const response = await fetch(url, { headers: getHeaders() });
    return handleResponse(response);
  };
}

// -- Exported fetch functions (same signatures as before) --

export const fetchDailySummaries = makeDateRangeFetcher<DailySummary[]>("daily");
export const fetchBySymbol = makeDateRangeFetcher<SymbolBreakdown[]>("by-symbol");
export const fetchPerformance = makeDateRangeFetcher<PerformanceMetrics>("performance");

// Calendar has different params, stays explicit but is still just 7 lines
export async function fetchCalendar(
  year: number,
  month: number
): Promise<CalendarEntry[]> {
  const response = await fetch(
    `${getApiBase()}/analytics/calendar?year=${year}&month=${month}`,
    { headers: getHeaders() }
  );
  return handleResponse(response);
}
```

The hooks file (`frontend/src/api/hooks/index.ts`) requires no structural change
because the hook signatures match the fetch function signatures. Each `useQuery` call
already delegates to the fetch function by reference. If the fetch function signature
is unchanged, the hook needs no edit.

#### 6. TypeScript types remain hand-written

Automatic TS type generation (e.g. from OpenAPI) is a separate concern and would add
a build step dependency. The types file is small (5 interfaces, ~50 lines) and changes
only when a view is added. This is acceptable cost and preserves full type control.

If the team later wants codegen, the refactored backend's OpenAPI spec will still
produce correct schemas since `response_model` is explicit on every route.

---

## File-by-File Change List

### New Files

| File | Purpose | Lines (est.) |
|------|---------|-------------|
| `backend/services/analytics_registry.py` | `AnalyticsViewDef` dataclass + registry dict | ~50 |
| `backend/services/analytics_views.py` | 5x `register_view()` calls | ~60 |

### Modified Files

| File | Change | Impact |
|------|--------|--------|
| `backend/services/analytics.py` | **No change.** Query functions stay as-is. | None |
| `backend/services/analytics_service.py` | Replace 5 typed methods with single `execute()` dispatcher. | Moderate -- simpler file |
| `backend/schemas/analytics.py` | **No change.** Schemas stay as-is. | None |
| `backend/api/analytics.py` | Replace 5 hand-written handlers with registry-driven loop. | Moderate -- same URLs, same behavior |
| `frontend/src/api/endpoints/analytics.ts` | Replace 3 date-range functions with `makeDateRangeFetcher` factory. Keep `fetchCalendar` explicit. | Low |
| `frontend/src/api/types/analytics.ts` | **No change.** | None |
| `frontend/src/api/hooks/index.ts` | **No change.** | None |

### Untouched Files (explicitly scoped out)

- `backend/api/v1/__init__.py` -- still imports `router` from `backend.api.analytics`
- `backend/api/dependencies.py` -- still provides `get_analytics_service()`
- `backend/models/*`, `backend/ingestion/*`, `backend/config/*`, `backend/exceptions/*`
- All non-analytics frontend files
- `tests/test_api/test_analytics.py` -- **existing tests should pass unchanged** since
  URL paths, param names, and response shapes are identical

---

## Migration Strategy

### Phase 1: Add registry alongside existing code (non-breaking)

1. Create `backend/services/analytics_registry.py` with the `AnalyticsViewDef`
   dataclass and registry functions.
2. Create `backend/services/analytics_views.py` with the 5 `register_view()` calls.
3. Run existing tests to confirm no import-time side effects.

### Phase 2: Refactor service layer

1. Replace `AnalyticsService` body with the generic `execute()` method.
2. Update `backend/api/analytics.py` to use the route factory loop.
3. Run full test suite: `uv run pytest tests/ -v`
4. Verify all 5 endpoints return identical responses (same status codes, same JSON
   shapes, same values).

### Phase 3: Frontend fetch simplification

1. Replace the 3 date-range fetch functions with `makeDateRangeFetcher` calls.
2. Verify `npm run build` succeeds with no type errors.
3. Hooks file needs no changes.

### Rollback

Since URL paths and response schemas are unchanged, rolling back is simply reverting
the Python files. No database migration, no frontend type changes, no API contract
changes.

---

## What Adding a New View Looks Like: Before vs After

### Example: Add a "by day-of-week" analytics view

#### BEFORE (current state): 7 files, ~80 lines

1. **`backend/services/analytics.py`** -- Add `get_by_day_of_week()` with SQL query (~25 lines)
2. **`backend/schemas/analytics.py`** -- Add `DayOfWeekBreakdown(BaseModel)` (~8 lines)
3. **`backend/services/analytics_service.py`** -- Add `by_day_of_week()` method (~12 lines)
4. **`backend/api/analytics.py`** -- Add `@router.get("/by-day-of-week")` handler (~12 lines)
5. **`frontend/src/api/types/analytics.ts`** -- Add `DayOfWeekBreakdown` interface (~6 lines)
6. **`frontend/src/api/endpoints/analytics.ts`** -- Add `fetchByDayOfWeek()` function (~10 lines)
7. **`frontend/src/api/hooks/index.ts`** -- Add `useByDayOfWeek()` hook (~5 lines)

Plus: update barrel exports in `endpoints/index.ts` and `types/index.ts`.

#### AFTER (proposed state): 4 files, ~35 lines

1. **`backend/services/analytics.py`** -- Add `get_by_day_of_week()` with SQL query (~25 lines, same as before)

2. **`backend/schemas/analytics.py`** -- Add `DayOfWeekBreakdown(BaseModel)` (~8 lines, same as before)

3. **`backend/services/analytics_views.py`** -- Add one `register_view()` call:
   ```python
   register_view(AnalyticsViewDef(
       name="by-day-of-week",
       query_fn=get_by_day_of_week,
       schema=DayOfWeekBreakdown,
       summary="Get P&L breakdown by day of week",
   ))
   ```
   That is 5 lines. The route, service dispatch, and OpenAPI docs are auto-wired.

4. **`frontend/src/api/endpoints/analytics.ts`** -- Add one line:
   ```typescript
   export const fetchByDayOfWeek = makeDateRangeFetcher<DayOfWeekBreakdown[]>("by-day-of-week");
   ```

Plus: add the TS interface in `types/analytics.ts` (~6 lines), add the hook in
`hooks/index.ts` (~5 lines) -- these two are unchanged in effort since they are
type/contract definitions that cannot be auto-generated without a build step.

**Net reduction**: eliminated the need to write a service method (~12 lines), API
handler (~12 lines), and full fetch function (~10 lines). The service and API layers
are fully auto-wired. The remaining manual steps are the irreducible parts: the SQL
query, the schema definition, and the frontend type + hook.

---

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Dynamic route generation breaks OpenAPI docs | Each generated route has explicit `response_model` and `summary`. Verified by inspecting `/docs` after migration. |
| `handler.__name__` collision | Registry enforces unique view names at registration time. |
| Loss of per-endpoint customization | `ParamStyle.CUSTOM` escape hatch allows hand-written routes alongside registry-driven ones. |
| Import ordering issues | `analytics_views.py` is imported at top of `analytics_service.py`, ensuring views are registered before the factory loop runs in `analytics.py`. |
| Test breakage | All existing tests target URL paths and JSON shapes, both of which are preserved. Run `uv run pytest tests/test_api/test_analytics.py -v` as gate. |

---

## Out of Scope

The following are explicitly excluded from this refactoring:

- **OpenAPI-to-TypeScript codegen**: Would eliminate the TS type/hook manual step but
  adds a build-time dependency. Can be layered on later.
- **Materialized view management**: `refresh_daily_summaries()` is operational
  infrastructure, not a view concern. Left unchanged.
- **Query builder abstraction**: The SQL queries have enough variation (joins, CTEs,
  Python post-processing like futures symbol normalization) that a query builder
  abstraction would add complexity without reducing lines. Raw SQL functions stay.
- **Non-analytics subsystems**: Trades, imports, groups, ingestion, config, models,
  exceptions, migrations.
