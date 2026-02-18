# AGENTS.md

Guidance for coding agents and contributors in this repository.

## 1) Scope and Baseline

- Backend: Python 3.12, FastAPI, SQLAlchemy 2.0, Pydantic, Alembic.
- Frontend: React 18, TypeScript 5 (strict mode), Vite.
- Production database: PostgreSQL 16.
- Test database: SQLite in-memory (via compatibility patching in `tests/conftest.py`).

Do not treat SQLite test fixtures as production database design. PostgreSQL is the source of truth for runtime features (JSONB, materialized views, UUID semantics).

## 2) Project Structure Rules

- API routes: `backend/api/*.py`
- Schemas (request/response/domain): `backend/schemas/*.py`
- ORM models: `backend/models/*.py`
- Ingestion chain: `backend/ingestion/`
- Domain services (grouping/analytics/scheduler): `backend/services/`
- Frontend routes/pages: `frontend/src/pages/`
- Frontend reusable UI: `frontend/src/components/`
- Frontend HTTP types/client: `frontend/src/api/client.ts`
- Tests: `tests/` and `tests/test_api/`

When adding features, keep this separation. Avoid mixing transport logic, domain logic, and persistence concerns in the same module.

## 3) Python Standards

Follow official Python standards and adapt to this codebase:

- Follow PEP 8 naming and readability conventions.
- Add type hints for public functions and new internal logic paths.
- Use docstrings for public modules, classes, and functions (PEP 257 style).
- Prefer small, testable functions over large procedural blocks.
- Keep datetimes timezone-aware and normalized to UTC at ingestion boundaries.
- Use `Decimal` for money/quantity values; do not use float for financial math.
- Use structured logging (`structlog`) with event names and key-value context.
- Avoid bare `except`; catch specific exceptions and log enough debugging context.

Backend-specific expectations:

- FastAPI handlers should declare `response_model` and validate inputs with `Query`/`Path`/`Body` constraints.
- Keep schema conversion explicit (`ModelResponse.model_validate(...)` style where used).
- Keep SQLAlchemy queries in 2.0 style (`select(...)` etc.) and avoid ad-hoc raw SQL unless necessary.
- For PostgreSQL-only operations (for example materialized view refresh), guard by SQL dialect so SQLite tests still run.

## 4) TypeScript Standards

Use TypeScript strictness as configured in `frontend/tsconfig.json`:

- Preserve `strict: true`.
- Do not introduce implicit `any`; prefer explicit interfaces/types.
- Keep `noUnusedLocals` and `noUnusedParameters` clean.
- Use narrow, composable types for API responses and params.
- Prefer `unknown` + narrowing over `any` when data shape is uncertain.
- Keep modules focused: API transport/types in `api/client.ts`, page composition in `pages`, reusable view logic in `components`.

## 5) React Standards

Follow React official rules for function components and hooks:

- Components and hooks must stay pure (no side effects during render).
- Call hooks only at the top level of React functions.
- Use `useEffect` only for syncing with external systems (network, subscriptions, timers), not for pure derivations.
- Keep route-level behavior in `pages/*`; keep reusable presentational pieces in `components/*`.
- Keep API interactions centralized through the typed client layer; avoid duplicating fetch logic across pages.

## 6) Ingestion and Data Integrity Rules

Critical chain (failure priority): `csv_importer -> normalizer -> validator -> dedup -> persistence`.

When touching ingestion:

- Preserve atomic import behavior (all-or-nothing write semantics).
- Preserve dedup semantics based on `(broker, broker_exec_id)`.
- Keep raw broker payload (`raw_data`) intact for auditability.
- Ensure post-import hooks do not break import success path.
- Add/adjust regression tests for parser variants and edge cases.

## 7) Database and Migration Rules

- All schema changes must go through Alembic migrations in `backend/migrations/versions/`.
- Prefer backward-compatible migration steps when possible.
- Keep PostgreSQL-specific objects (for example materialized views) explicitly documented in migration code.
- Do not add SQLite-specific production behavior to application runtime paths.

## 8) Testing and Validation Checklist

Before completing a substantial change:

1. Run backend tests:
   - `uv run pytest tests/ -v`
2. Run coverage when behavior changed broadly:
   - `uv run pytest tests/ --cov=backend --cov-report=term-missing`
3. For frontend-impacting changes:
   - `cd frontend && npm run build`
4. Add or update tests with every bug fix (especially ingestion parsing/normalization regressions).

## 9) References (Primary Sources)

- Python PEP 8: https://peps.python.org/pep-0008/
- Python PEP 257: https://peps.python.org/pep-0257/
- Python type hints (PEP 484): https://peps.python.org/pep-0484/
- TypeScript Handbook: https://www.typescriptlang.org/docs/handbook/intro.html
- TypeScript `strict`: https://www.typescriptlang.org/tsconfig/strict.html
- TypeScript `noImplicitAny`: https://www.typescriptlang.org/tsconfig/noImplicitAny.html
- React rules of hooks: https://react.dev/reference/rules/rules-of-hooks
- React component/hook purity: https://react.dev/reference/rules/components-and-hooks-must-be-pure
- React `useEffect`: https://react.dev/reference/react/useEffect
