# Trading Records

Self-hosted trading records system for capturing, normalizing, and analyzing trading data from Interactive Brokers (IBKR) and Tradovate CSV exports, with full data ownership.

## Architecture

```
+------------------+     +--------------------+     +------------------+
|  Data Sources    |     |   Ingestion Layer  |     |      Core        |
|                  |     |                    |     |                  |
| CSV / XLSX      -+---->| ImportSource       |     |                  |
| (Manual Upload)  |     | (pluggable iface)  |     | Normalizer       |
|                  |     |                    |     | - Broker-specific|
|                  |     | Sources:           |     |   to unified     |
|                  |     | - CsvSource        +---->|   NormalizedTrade|
|                  |     |                    |     |                  |
|                  |     |                    |     | Validator        |
|                  |     |                    |     | - Required fields|
|                  |     | IngestionPipeline  |     | - Range checks   |
+------------------+     | (orchestrator)     |     | - Timestamp sanity
                         +--------------------+     |                  |
                                                    | Dedup Engine     |
                                                    | - Composite key  |
                                                    |   (broker +      |
                                                    |    broker_exec_id)
                                                    +--------+---------+
                                                             |
                                                    Atomic Transaction
                                                             |
                                                             v
+-----------------+     +--------------------+     +------------------+
|    Frontend     |     |    API Layer       |     |    Database      |
|                 |     |                    |     |                  |
| Dashboard       |     | FastAPI + CORS     |     | PostgreSQL 16    |
| - P&L Calendar  |<----+ API Key Auth       |<----+ - trades         |
| - Equity Curve  |     | /api/v1 prefix     |     | - trade_groups   |
| - Metrics Cards |     |                    |     | - import_logs    |
| Trade Table     |     | Dependency Inject. |     | - daily_summaries|
| Import UI       |     | - TradeService     |     |   (mat. view)   |
| Analytics Charts|     | - ImportService    |     | - ohlcv_cache    |
| OHLCV Charts    |     | - AnalyticsService |     | - JSONB raw data |
|                 |     |                    |     |                  |
| React+TS / Vite |     | Unified Exceptions |     +------------------+
| api/types/      |     | - AppException     |
| api/endpoints/  |     | - Structured JSON  |     +------------------+
| api/hooks/      |     +--------------------+     |    Services      |
+-----------------+                                |                  |
                                                   | Trade Grouper    |
                        +--------------------+     | - FIFO matching  |
                        |    Config          |     | - Round-trip     |
                        |                    |     |   tracking       |
                        | Env-aware settings |     |                  |
                        | - Dev / Test / Prod|     | Analytics Engine |
                        | - Pydantic-settings|     | - P&L aggregation|
                        | - APP_ENV driven   |     | - Daily summaries|
                        +--------------------+     |                  |
                                                   | Scheduler        |
                                                   | - APScheduler    |
                                                   | - Idempotency    |
                                                   +------------------+
```

### Market Data Providers

```
GET /api/v1/groups/{id}/chart
        |
        v
  OHLCVCacheService (PostgreSQL)
  1. Check cache for completed bars
  2. On miss: fetch from provider, filter in-progress bars, cache, return
  3. On provider error: propagate immediately (fail-fast)
        |
        v
  Pick provider by asset_class:
    future -> DabentoProvider (Databento)
    stock  -> TiingoProvider (Tiingo)
        |                       |
        v                       v
  DabentoProvider         TiingoProvider
  - CME futures            - US stocks
  - 1m/5m/15m/1h/1d bars  - Daily bars (free tier)
  - UTC normalization      - Adjusted prices
  - Continuous contracts   - Split/dividend adjusted
```

- **Databento** for CME futures OHLCV bars (ES, MES, NQ, MNQ, etc.)
- **Tiingo** for US stock daily OHLCV bars (equities)
- **PostgreSQL `ohlcv_cache` table** for permanent storage of completed bars
- **Daily call counters** per provider to stay within API limits (400/day Tiingo, 500/day Databento)
- **Bar validation** rejects invalid OHLCV data before caching
- **In-progress bar filtering** ensures only completed candles are cached

### Data Flow

1. **Ingestion** - Import trades from IBKR and Tradovate CSV/XLSX files via pluggable `ImportSource` implementations
2. **Pipeline** - `IngestionPipeline` orchestrates: source.fetch -> validate -> dedup -> persist
3. **Normalization** - Convert broker-specific formats into a unified `NormalizedTrade` Pydantic schema
4. **Validation** - Verify required fields, value ranges, and timestamp consistency (all UTC)
5. **Deduplication** - Composite key check (`broker + broker_exec_id`) prevents duplicate records
6. **Persistence** - Atomic transaction writes trades to PostgreSQL; raw broker payloads preserved in JSONB
7. **Grouping** - Standalone FIFO algorithm matches buy/sell pairs into round-trip trade groups (re-runnable, decoupled from import)
8. **Analytics** - P&L dynamically computed; daily summaries via materialized views, refreshed after each import

### Key Design Decisions

- **Batch-first** - Reliable batch imports over real-time streaming
- **Raw data preservation** - Original broker payloads stored in JSONB for audit and reprocessing
- **Atomic imports** - All-or-nothing transactions ensure data consistency
- **UTC everywhere** - All timestamps stored as `timestamptz`; display-time conversion in frontend
- **Single container** - Frontend built as static files and served from FastAPI
- **Pluggable sources** - New import sources implement the `ImportSource` interface without modifying the pipeline
- **Service layer** - Business logic concentrated in services; API handlers remain thin request/response mappers
- **Environment-aware config** - Settings loaded per environment (dev/test/prod) via `APP_ENV`
- **Unified exceptions** - Structured JSON error responses with error code, message, and context
- **Dependency injection** - Services injected via FastAPI `Depends()` for testability
- **Fail-fast market data** - Provider errors propagate directly; no fallback chains or circuit breakers
- **Permanent OHLCV cache** - Completed bars cached forever in PostgreSQL; no expiry, no staleness checks

## Features

### Supported

- Multi-broker trade import from IBKR and Tradovate CSV/XLSX exports
- Automatic broker format detection for CSV files (IBKR Activity Statement, Tradovate export)
- Pluggable import source architecture (add new brokers without modifying the pipeline)
- Unified trade schema across all brokers
- Composite-key deduplication (safe to re-import)
- FIFO trade grouping into round-trips (long/short, entry/exit/add/trim)
- Strategy tagging and journal notes on trade groups
- OHLCV price charts with trade markers (Lightweight Charts)
  - Databento for CME futures (continuous front-month contracts)
  - Tiingo for US stocks (split/dividend-adjusted prices)
  - PostgreSQL OHLCV cache with in-progress bar filtering
  - Daily rate limiting per provider
- P&L calendar heatmap, equity curve, per-symbol breakdown
- Key metrics dashboard (win rate, profit factor, average win/loss)
- Sortable/filterable trade table
- API key authentication
- Import audit trail with error reporting
- Docker Compose single-command deployment (127.0.0.1 bound)
- PostgreSQL materialized views for analytics performance
- Structured JSON logging (structlog)
- Unified exception handling with structured error responses
- Environment-aware configuration (dev/test/prod)
- Service-layer architecture with dependency injection
- Versioned REST API (`/api/v1`)
- Typed frontend API layer with separated types, endpoints, and hooks
- Comprehensive test suite (unit, integration, API)

### Not Yet Supported

- Order placement or trade execution
- Mobile application
- Multi-user / multi-tenant
- Options exercise/assignment handling
- Futures rollover linking
- Multi-leg options strategy grouping
- Push notifications / alerts
- PostgreSQL-backed job scheduling (currently in-process APScheduler)
- WAL archiving / point-in-time recovery

## Tech Stack

| Layer      | Technology                                                  |
|------------|-------------------------------------------------------------|
| Frontend   | React 18, TypeScript 5.7, Vite 6, Tailwind CSS 3           |
| Charts     | Recharts, Lightweight Charts                                |
| State      | Zustand, TanStack React Query v5, TanStack React Table v8  |
| Backend    | Python 3.12, FastAPI, SQLAlchemy 2.0, Pydantic             |
| Market Data| Databento (futures), Tiingo (stocks)                        |
| Database   | PostgreSQL 16                                               |
| Migrations | Alembic                                                     |
| Testing    | pytest, pytest-asyncio, respx, testcontainers               |
| Deploy     | Docker, Docker Compose                                      |
| Deps       | uv (Python), npm (Frontend)                                 |

## Project Structure

```
trading-records/
├── backend/
│   ├── main.py              # FastAPI entry point + static file serving
│   ├── config/              # Environment-aware settings (pydantic-settings)
│   │   ├── base.py          # Base settings definitions
│   │   ├── environments.py  # Dev / Test / Prod overrides
│   │   └── loader.py        # APP_ENV resolution and singleton
│   ├── exceptions/          # Unified exception hierarchy
│   │   ├── base.py          # AppException base class
│   │   └── handlers.py      # Global FastAPI exception handlers
│   ├── logging_config.py    # structlog setup
│   ├── database.py          # SQLAlchemy engine + session
│   ├── auth.py              # API key middleware
│   ├── api/                 # REST route handlers
│   │   ├── v1/              # Versioned router aggregation (/api/v1)
│   │   ├── market_data.py   # OHLCV cache admin endpoints
│   │   └── dependencies.py  # Service dependency injection (Depends)
│   ├── ingestion/           # Import pipeline
│   │   ├── pipeline.py      # IngestionPipeline orchestrator
│   │   ├── sources/         # Pluggable import sources
│   │   │   ├── base.py      # ImportSource ABC + SourceRegistry
│   │   │   ├── csv_source.py
│   │   ├── base.py          # BaseIngester (validate/dedup/persist)
│   │   ├── csv_importer.py  # CSV format detection + column mapping
│   │   ├── normalizer.py    # Broker-specific normalization
│   │   └── validator.py     # Field and range validation
│   ├── models/              # SQLAlchemy ORM models
│   │   └── ohlcv_cache.py   # OHLCV cache table model
│   ├── schemas/             # Pydantic request/response schemas
│   ├── services/            # Domain services
│   │   ├── trade_service.py      # Trade query logic
│   │   ├── import_service.py     # Import orchestration
│   │   ├── analytics_service.py  # Analytics query wrapper
│   │   ├── analytics.py          # P&L aggregation and summaries
│   │   ├── market_data.py        # MarketDataProvider protocol + helpers
│   │   ├── trade_grouper.py      # FIFO round-trip matching
│   │   ├── scheduler.py          # APScheduler management
│   │   ├── providers/            # Market data provider implementations
│   │   │   ├── databento_provider.py  # CME futures via Databento
│   │   │   ├── tiingo_provider.py     # US stocks via Tiingo
│   │   │   ├── validation.py          # OHLCV bar integrity checks
│   │   │   ├── rate_limit.py          # Daily API call counters
│   │   │   └── errors.py             # Provider error hierarchy
│   │   └── cache/                # OHLCV cache layer
│   │       └── ohlcv_cache.py    # PostgreSQL cache service
│   └── migrations/          # Alembic migration versions
├── config/
│   └── config.example.yaml  # Configuration template
├── frontend/
│   └── src/
│       ├── pages/           # Dashboard, Trades, Groups, Analytics, Import, Settings
│       ├── components/      # TradeTable, EquityCurve, PnLCalendar, MetricsCards, etc.
│       └── api/             # Typed API client layer
│           ├── client.ts    # Legacy HTTP client (TanStack Query)
│           ├── types/       # TypeScript interfaces for API responses
│           ├── endpoints/   # Fetch functions per resource (trades, imports, etc.)
│           └── hooks/       # React hooks wrapping endpoints with loading/error state
├── tests/
│   ├── conftest.py          # SQLite test fixtures and session setup
│   ├── fixtures/            # Sample broker data (CSV)
│   ├── test_api/            # API integration tests
│   ├── test_providers/      # Market data provider tests
│   │   ├── test_validation.py         # Bar validation tests
│   │   ├── test_rate_limit.py         # Rate limiter tests
│   │   ├── test_databento_provider.py # Databento provider tests (mocked)
│   │   ├── test_tiingo_provider.py    # Tiingo provider tests (mocked)
│   │   ├── test_ohlcv_cache.py        # Cache service tests
│   │   └── test_chart_endpoint.py     # Chart endpoint integration tests
│   ├── test_pipeline.py     # Ingestion pipeline tests
│   ├── test_services.py     # Service layer tests
│   ├── test_exceptions.py   # Exception handling tests
│   ├── test_config.py       # Config loading tests
│   └── test_dependencies.py # DI tests
├── docs/
│   └── design-market-data-providers.md  # Market data provider design doc
├── Dockerfile               # Multi-stage build (Node + Python)
├── docker-compose.yml       # PostgreSQL + FastAPI
├── pyproject.toml           # Python dependencies (uv)
└── .env.example             # Environment variable template
```

## Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/)
- Or for local development:
  - Python 3.12+
  - [uv](https://github.com/astral-sh/uv) (Python package manager)
  - Node.js 20+
  - PostgreSQL 16

### Option 1: Docker Compose (Recommended)

```bash
git clone <repo-url>
cd trading-records
cp .env.example .env
# Edit .env with your API keys and local settings
docker compose up -d
docker compose exec app alembic upgrade head
```

Access: http://localhost:8000 (frontend) | http://localhost:8000/docs (API docs)

### Option 2: Local Development

```bash
git clone <repo-url>
cd trading-records
cp .env.example .env

# Start PostgreSQL
docker run -d --name trading-pg \
  -e POSTGRES_USER=trading \
  -e POSTGRES_PASSWORD=trading \
  -e POSTGRES_DB=trading_records \
  -p 5432:5432 \
  postgres:16-alpine

# Backend
uv sync
uv run alembic upgrade head
uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Access: http://localhost:3000 (Vite dev) | http://localhost:8000 (API) | http://localhost:8000/docs

### Environment Configuration

The backend loads settings based on the `APP_ENV` environment variable:

| `APP_ENV`     | Settings class | Env file fallback    |
|---------------|----------------|----------------------|
| `dev` (default) | `DevSettings`  | `.env`, `.env.dev`  |
| `test`        | `TestSettings`  | `.env`, `.env.test` |
| `prod`        | `ProdSettings`  | `.env`, `.env.prod` |

When `APP_ENV` is unset, the loader auto-detects `test` if running under pytest, otherwise defaults to `dev`.

## Broker Configuration

### CSV Import

No configuration required. Upload CSV/XLSX files via the Import page or API. The system auto-detects:
- **IBKR Activity Statement CSV** (exported from Account Management)
- **Tradovate trade history CSV** (exported from platform)
- Unknown formats fall back to user-provided column mapping

### Market Data Providers

OHLCV chart data is fetched from two purpose-built providers. Set API keys in `.env`:

```
DATABENTO_API_KEY=db-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TIINGO_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
OHLCV_CACHE_ENABLED=true
```

**Databento** (futures): Sign up at [databento.com](https://databento.com). Usage-based pricing (~$0.50/GB). With the PostgreSQL cache, typical usage is < $0.01/month.

**Tiingo** (stocks): Sign up at [tiingo.com](https://www.tiingo.com). Free tier provides 500 API calls/day for end-of-day data. The daily call counter is set to 400 as a safety margin.

Completed bars are cached permanently in PostgreSQL. After initial fetches, subsequent chart views are served from cache with no provider calls.

## Importing Trades

**CSV Upload:**
```bash
curl -X POST http://localhost:8000/api/v1/import/csv \
  -H "X-API-Key: <your-api-key>" \
  -F "file=@trades.csv"
```

## API Endpoints

All endpoints are served under the `/api/v1` prefix. Error responses follow a unified JSON format:

```json
{
  "detail": "Human-readable message",
  "error": {
    "code": "error_code",
    "message": "Structured error description",
    "context": {}
  }
}
```

| Method  | Endpoint                             | Description                               |
|---------|--------------------------------------|-------------------------------------------|
| GET     | `/health`                            | Service health check                      |
| GET     | `/api/v1/trades`                     | List trades (paginated)                   |
| GET     | `/api/v1/trades/{id}`                | Trade detail                              |
| GET     | `/api/v1/trades/summary`             | Trade summary metrics                     |
| GET     | `/api/v1/groups`                     | List trade groups                         |
| GET     | `/api/v1/groups/{id}`                | Group detail with legs                    |
| GET     | `/api/v1/groups/{id}/chart`          | OHLCV candles + trade markers             |
| PATCH   | `/api/v1/groups/{id}`                | Update strategy tag / notes               |
| POST    | `/api/v1/groups/recompute`           | Recompute grouping for symbol             |
| POST    | `/api/v1/import/csv`                 | Upload and import CSV                     |
| GET     | `/api/v1/import/logs`                | Import attempt history                    |
| GET     | `/api/v1/analytics/daily`            | Daily P&L summary                         |
| GET     | `/api/v1/analytics/calendar`         | P&L calendar data                         |
| GET     | `/api/v1/analytics/by-symbol`        | Per-symbol statistics                     |
| GET     | `/api/v1/analytics/by-strategy`      | Per-strategy statistics                   |
| GET     | `/api/v1/analytics/performance`      | Overall performance metrics               |
| DELETE  | `/api/v1/market-data/cache`          | Invalidate OHLCV cache (admin)            |
| GET     | `/api/v1/config`                     | Read runtime config (redacted secrets)    |
| PUT     | `/api/v1/config`                     | Update runtime config                     |

## Running Tests

```bash
uv run pytest tests/ -v

# With coverage
uv run pytest tests/ --cov=backend --cov-report=term-missing
```

Tests use SQLite in-memory databases for speed. PostgreSQL-specific features (materialized views, JSONB operations, upsert with `ON CONFLICT`) are guarded by dialect checks so tests run without a PostgreSQL instance.

## License

Private - All rights reserved.
