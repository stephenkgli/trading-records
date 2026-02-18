# Implement Trading Records System (Phase 1 + Phase 2)

Implemented the complete Trading Records system following the design document, covering both Phase 1 (Core MVP) and Phase 2 (Tradovate + Analytics).

## Phase 1 Implementation

### Project Skeleton
- `pyproject.toml` with uv, all dependencies (fastapi, sqlalchemy, alembic, structlog, httpx, lxml, apscheduler, etc.)
- `.python-version` (3.12), `.gitignore`, `.env.example`, `config/config.example.yaml`
- Full directory structure: `backend/`, `frontend/`, `tests/`, `config/`

### Backend Core
- **Config** (`backend/config.py`): pydantic-settings with env vars for DB, API key, IBKR, Tradovate, CORS
- **Database** (`backend/database.py`): SQLAlchemy 2.0 sync engine + session factory
- **ORM Models**: Trade, ImportLog, TradeGroup, TradeGroupLeg with all FK constraints and indexes
- **Alembic Migrations**: Initial schema (001) + daily_summaries materialized view (002)
- **Pydantic Schemas**: NormalizedTrade, TradeResponse, ImportResult, analytics schemas

### Ingestion Pipeline
- **Validator** (`backend/ingestion/validator.py`): 6 validation rules (required fields, price > 0, qty != 0, timestamp sanity, broker enum, asset class enum)
- **Base Ingester** (`backend/ingestion/base.py`): Transaction-wrapped import with dedup using composite key (broker, broker_exec_id)
- **Normalizer** (`backend/ingestion/normalizer.py`): Side/asset class normalization, safe_decimal, ensure_utc
- **IBKR Flex Ingester** (`backend/ingestion/ibkr_flex.py`): Two-step REST + polling + circuit breaker + idempotency
- **CSV Importer** (`backend/ingestion/csv_importer.py`): Auto-detection of IBKR/Tradovate format, SHA-256 dedup hash with filename+row

### API Layer
- **Auth** (`backend/auth.py`): API Key middleware (X-API-Key header), public paths for /health and static files
- **Health** (`backend/api/health.py`): DB connectivity check
- **Trades API** (`backend/api/trades.py`): List (paginated, filterable, sortable) + detail
- **Imports API** (`backend/api/imports.py`): CSV upload, Flex trigger, Tradovate trigger, import logs
- **structlog** (`backend/logging_config.py`): JSON structured logging
- **Scheduler** (`backend/services/scheduler.py`): APScheduler with configurable cron for IBKR and Tradovate

### Frontend (Phase 1)
- React 18 + TypeScript + Vite + TailwindCSS
- TanStack Query for server state, TanStack Table for trade table
- Pages: TradesPage, ImportPage, SettingsPage
- Components: Layout (nav), TradeTable (sortable), CsvUpload (drag-and-drop)

### Docker
- Multi-stage Dockerfile (Node build + Python runtime)
- docker-compose.yml with 127.0.0.1 binding, healthchecks, no DB port exposure

## Phase 2 Implementation

### Tradovate Integration
- **Tradovate Ingester** (`backend/ingestion/tradovate.py`): OAuth token manager + REST /fill/list + contract lookup cache
- **Tradovate CSV**: Full parsing support added to csv_importer.py

### Trade Grouper
- **FIFO Matching** (`backend/services/trade_grouper.py`): 8 rules - group by (account, symbol), BUY/SELL opens long/short, FIFO close matching, partial fills, overfills
- **Groups API** (`backend/api/groups.py`): List, detail with legs, update tags/notes, recompute endpoint

### Analytics
- **Materialized View**: `daily_summaries` with concurrent refresh
- **Analytics Service** (`backend/services/analytics.py`): Daily summaries, calendar, by-symbol, by-strategy, performance metrics (win rate, profit factor, expectancy, Sharpe)
- **Analytics API** (`backend/api/analytics.py`): 5 endpoints

### Dashboard Frontend
- DashboardPage with MetricsCards, PnLCalendar, EquityCurve, SymbolBreakdown
- GroupsPage with status filtering and recompute button
- AnalyticsPage with full performance metrics display
- Updated routing and navigation for all pages
