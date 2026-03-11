# Trading Records

Self-hosted trading records system for IBKR and Tradovate. Python/FastAPI backend + React/TypeScript frontend + PostgreSQL.

## Quick Reference

- Backend: `cd backend && uvicorn main:app --reload` (http://localhost:8000)
- Frontend: `cd frontend && npm run dev` (http://localhost:3000)
- API Docs: http://localhost:8000/docs
- DB: PostgreSQL 16 (see `.env` for connection)

## Code Style

- Python: Ruff (line-length=120), target Python 3.12, isort with `backend` as first-party
- TypeScript: ES modules, strict mode, Prettier formatting
- SQL: Use parameterized queries via SQLAlchemy ORM, never raw string interpolation

## Domain Rules

- Trade deduplication key: `(broker, broker_exec_id)` — unique constraint, prevents duplicate imports
- Trade grouping is per `(account_id, symbol)`, uses FIFO matching for round-trip detection
- Overfill on close: excess quantity creates a NEW group, not appended to current group
- All trade timestamps (`executed_at`) MUST be timezone-aware UTC — ingestion converts broker-local times to UTC
- Broker timezone defaults: IBKR=America/New_York, Tradovate=Asia/Shanghai (configurable via env vars)
- Quantity is always stored as positive `abs(value)`, direction encoded in `side` field
- Futures `multiplier` is critical for P&L (e.g., ES=50). Default 1 for stocks. Missing multiplier = wrong P&L
- Futures symbols are normalized to root (e.g., `ESZ24` -> `ES`) for cross-contract analytics
- P&L comes from `trade_groups.realized_pnl` (closed round-trips), never from raw trade amounts
- Import order matters: recompute groups FIRST, then refresh `daily_summaries` materialized view
- `daily_summaries` unique on `(date, account_id, asset_class)` — concurrent refresh with exclusive fallback
- Monetary values are strings in frontend TypeScript types to preserve decimal precision
- Databento futures use `ROOT.c.0` continuous format with `stype_in="continuous"`, filtered to RTH only
- OHLCV cache never stores in-progress (incomplete) bars

## Workflow

IMPORTANT: Every code change MUST go through以下完整流程，不得跳过任何步骤：

1. **Write code** - implement the change
2. **Run tests** - ensure all tests pass
3. **Verify locally** - validate the change actually works in the running dev environment:
   - Frontend: use the `agent-browser` cli to open pages, click through UI, take screenshots, and visually confirm behavior
   - Backend: call API endpoints directly (via `curl`) to verify response data
   - Database: execute SQL queries against PostgreSQL to verify data integrity
4. **If issues found** - fix and repeat from step 2 until no remaining issues
5. **Optimize** - use the `code-simplifier:code-simplifier` agent to review and optimize all changed code for clarity, consistency, and maintainability

YOU MUST NOT consider a task complete until step 5 is done.

## Skill Compliance

IMPORTANT: The following skills MUST be consulted for their respective domains:

- **Database changes** (schema, queries, migrations): Follow `supabase-postgres-best-practices` skill strictly. This includes query performance, indexing, RLS, connection management, and schema design.
- **Frontend code** (React components, hooks, data fetching, performance): Follow `vercel-react-best-practices` and `vercel-composition-patterns` skills. This covers re-render optimization, bundle size, component architecture, and state management.
- **UI/UX design** (layout, styling, accessibility, interactions): Follow `web-design-guidelines` and `frontend-design` skills. This covers accessibility, visual consistency, and production-grade design quality.
