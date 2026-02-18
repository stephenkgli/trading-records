# Trading Records

Self-hosted trading records system for capturing, normalizing, and analyzing trading data from Interactive Brokers (IBKR) and Tradovate, with full data ownership.

## Architecture

```
+------------------+     +--------------------+     +------------------+
|  Data Sources    |     |   Ingestion Layer  |     |      Core        |
|                  |     |                    |     |                  |
| IBKR Flex Query -+---->| ImportSource       |     |                  |
| (XML over REST)  |     | (pluggable iface)  |     | Normalizer       |
|                  |     |                    |     | - Broker-specific|
| Tradovate API   -+---->| Sources:           |     |   to unified     |
| (JSON over REST) |     | - CsvSource        +---->|   NormalizedTrade|
|                  |     | - FlexQuerySource  |     |                  |
| CSV / XLSX      -+---->| - TradovateSource  |     | Validator        |
| (Manual Upload)  |     |                    |     | - Required fields|
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
| Analytics Charts|     | - ImportService    |     | - JSONB raw data |
|                 |     | - AnalyticsService |     |                  |
| React+TS / Vite |     |                    |     +------------------+
| api/types/      |     | Unified Exceptions |
| api/endpoints/  |     | - AppException     |     +------------------+
| api/hooks/      |     | - Structured JSON  |     |    Services      |
+-----------------+     +--------------------+     |                  |
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

### Data Flow

1. **Ingestion** - Import trades from IBKR Flex Query (XML), Tradovate API (JSON), or CSV/XLSX files via pluggable `ImportSource` implementations
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

## Features

### Supported

- Multi-broker trade import: IBKR Flex Query (XML), Tradovate REST API (JSON), CSV/XLSX
- Automatic broker format detection for CSV files (IBKR Activity Statement, Tradovate export)
- Pluggable import source architecture (add new brokers without modifying the pipeline)
- Unified trade schema across all brokers
- Composite-key deduplication (safe to re-import)
- FIFO trade grouping into round-trips (long/short, entry/exit/add/trim)
- Strategy tagging and journal notes on trade groups
- P&L calendar heatmap, equity curve, per-symbol breakdown
- Key metrics dashboard (win rate, profit factor, average win/loss)
- Sortable/filterable trade table
- Scheduled automatic imports (APScheduler with idempotency)
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

- Real-time WebSocket streaming (IBKR Client Portal, Tradovate WebSocket)
- Order placement or trade execution
- Mobile application
- Multi-user / multi-tenant
- Options exercise/assignment handling
- Futures rollover linking
- Stock split adjustment
- Multi-leg options strategy grouping
- Price charts with trade overlays (TradingView Lightweight Charts planned)
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
│   │   └── dependencies.py  # Service dependency injection (Depends)
│   ├── ingestion/           # Import pipeline
│   │   ├── pipeline.py      # IngestionPipeline orchestrator
│   │   ├── sources/         # Pluggable import sources
│   │   │   ├── base.py      # ImportSource ABC + SourceRegistry
│   │   │   ├── csv_source.py
│   │   │   ├── flex_query_source.py
│   │   │   └── tradovate_source.py
│   │   ├── base.py          # BaseIngester (validate/dedup/persist)
│   │   ├── csv_importer.py  # CSV format detection + column mapping
│   │   ├── ibkr_flex.py     # IBKR Flex Query client
│   │   ├── tradovate.py     # Tradovate REST client
│   │   ├── normalizer.py    # Broker-specific normalization
│   │   └── validator.py     # Field and range validation
│   ├── models/              # SQLAlchemy ORM models
│   ├── schemas/             # Pydantic request/response schemas
│   ├── services/            # Domain services
│   │   ├── trade_service.py      # Trade query logic
│   │   ├── import_service.py     # Import orchestration
│   │   ├── analytics_service.py  # Analytics query wrapper
│   │   ├── analytics.py          # P&L aggregation and summaries
│   │   ├── trade_grouper.py      # FIFO round-trip matching
│   │   └── scheduler.py          # APScheduler management
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
│   ├── fixtures/            # Sample broker data (XML, JSON, CSV)
│   ├── test_api/            # API integration tests
│   ├── test_pipeline.py     # Ingestion pipeline tests
│   ├── test_services.py     # Service layer tests
│   ├── test_exceptions.py   # Exception handling tests
│   ├── test_config.py       # Config loading tests
│   └── test_dependencies.py # DI tests
├── docs/
│   └── REFACTOR_PLAN.md     # Refactoring plan and design rationale
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
# Edit .env with your credentials (see "Broker Configuration" below)
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

### IBKR Flex Query

To import trades from Interactive Brokers, you need a **Flex Query Token** and a **Query ID**.

1. Log in to [IBKR Account Management](https://www.interactivebrokers.com/sso/Login)
2. Navigate to **Reports / Tax Reports > Flex Queries**
3. Create a new **Activity Flex Query**:
   - Include **Trade Confirmations** with all fields
   - Set the desired date range (up to 365 days)
   - Save the query and note the **Query ID**
4. Navigate to **Settings > Account Settings > Flex Web Service**
   - Click **Create Token** to generate a Flex token
   - Note the generated **token** (it will only be shown once)
5. Set in `.env`:
   ```
   IBKR_FLEX_TOKEN=<your-flex-token>
   IBKR_QUERY_ID=<your-query-id>
   ```

### Tradovate

To import trades from Tradovate, you need API credentials from the Tradovate developer portal.

1. Register at the [Tradovate API Portal](https://api.tradovate.com)
2. Create a new **API Application**:
   - Note the **Client ID** and **Client Secret**
3. Generate a **Device ID** (any unique string, e.g. a UUID; generate once and reuse)
4. Set in `.env`:
   ```
   TRADOVATE_USERNAME=<your-tradovate-username>
   TRADOVATE_PASSWORD=<your-tradovate-password>
   TRADOVATE_CLIENT_ID=<your-client-id>
   TRADOVATE_CLIENT_SECRET=<your-client-secret>
   TRADOVATE_DEVICE_ID=<your-device-id>
   TRADOVATE_ENVIRONMENT=demo   # or "live" for production
   ```

> **Security Note:** Tradovate credentials grant trading access. Use a dedicated API-only account if available, or at minimum a unique password. Run only in a trusted local environment.

### CSV Import

No configuration required. Upload CSV/XLSX files via the Import page or API. The system auto-detects:
- **IBKR Activity Statement CSV** (exported from Account Management)
- **Tradovate trade history CSV** (exported from platform)
- Unknown formats fall back to user-provided column mapping

## Importing Trades

**CSV Upload:**
```bash
curl -X POST http://localhost:8000/api/v1/import/csv \
  -H "X-API-Key: <your-api-key>" \
  -F "file=@trades.csv"
```

**IBKR Flex Query:**
```bash
curl -X POST http://localhost:8000/api/v1/import/flex/trigger \
  -H "X-API-Key: <your-api-key>"
```

**Tradovate API:**
```bash
curl -X POST http://localhost:8000/api/v1/import/tradovate/trigger \
  -H "X-API-Key: <your-api-key>"
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
| PATCH   | `/api/v1/groups/{id}`                | Update strategy tag / notes               |
| POST    | `/api/v1/groups/recompute`           | Recompute grouping for symbol             |
| POST    | `/api/v1/import/csv`                 | Upload and import CSV                     |
| POST    | `/api/v1/import/flex/trigger`        | Trigger IBKR Flex Query                   |
| POST    | `/api/v1/import/tradovate/trigger`   | Trigger Tradovate API pull                |
| GET     | `/api/v1/import/logs`                | Import attempt history                    |
| GET     | `/api/v1/analytics/daily`            | Daily P&L summary                         |
| GET     | `/api/v1/analytics/calendar`         | P&L calendar data                         |
| GET     | `/api/v1/analytics/by-symbol`        | Per-symbol statistics                     |
| GET     | `/api/v1/analytics/by-strategy`      | Per-strategy statistics                   |
| GET     | `/api/v1/analytics/performance`      | Overall performance metrics               |
| GET     | `/api/v1/config`                     | Read runtime config (redacted secrets)    |
| PUT     | `/api/v1/config`                     | Update runtime config                     |

## Running Tests

```bash
uv run pytest tests/ -v

# With coverage
uv run pytest tests/ --cov=backend --cov-report=term-missing
```

Tests use SQLite in-memory databases for speed. PostgreSQL-specific features (materialized views, JSONB operations) are guarded by dialect checks so tests run without a PostgreSQL instance.

## License

Private - All rights reserved.
