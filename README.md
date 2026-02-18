# Trading Records

Self-hosted trading records system for capturing, normalizing, and analyzing trading data from Interactive Brokers (IBKR) and Tradovate, with full data ownership.

## Architecture

```
+------------------+     +--------------------+     +------------------+
|  Data Sources    |     |   Ingestion Layer  |     |      Core        |
|                  |     |                    |     |                  |
| IBKR Flex Query -+---->| Flex Ingester      |     |                  |
| (XML over REST)  |     | - Request report   +---->| Normalizer       |
|                  |     | - Poll completion  |     | - Broker-specific|
| Tradovate API   -+---->| - Circuit breaker  |     |   to unified     |
| (JSON over REST) |     |                    |     |   NormalizedTrade|
|                  |     | Tradovate Ingester |     |                  |
| CSV / XLSX      -+---->| - OAuth token mgmt +---->| Validator        |
| (Manual Upload)  |     | - REST /fill/list  |     | - Required fields|
|                  |     |                    |     | - Range checks   |
+------------------+     | CSV Importer       |     | - Timestamp sanity
                         | - Format detection +---->|                  |
                         | - Column mapping   |     | Dedup Engine     |
                         +--------------------+     | - Composite key  |
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
| - Equity Curve  |     | Health Check       |     | - trade_groups   |
| - Metrics Cards |     |                    |     | - import_logs    |
| Trade Table     |     | REST Endpoints     |     | - daily_summaries|
| Import UI       |     | - Trades CRUD      |     |   (mat. view)   |
| Analytics Charts|     | - Groups           |     | - JSONB raw data |
|                 |     | - Imports          |     |                  |
| React+TS / Vite |     | - Analytics        |     +------------------+
+-----------------+     +--------------------+
                                                    +------------------+
                                                    |    Services      |
                                                    |                  |
                                                    | Trade Grouper    |
                                                    | - FIFO matching  |
                                                    | - Round-trip     |
                                                    |   tracking       |
                                                    |                  |
                                                    | Analytics Engine |
                                                    | - P&L aggregation|
                                                    | - Daily summaries|
                                                    |                  |
                                                    | Scheduler        |
                                                    | - APScheduler    |
                                                    | - Idempotency    |
                                                    +------------------+
```

### Data Flow

1. **Ingestion** - Import trades from IBKR Flex Query (XML), Tradovate API (JSON), or CSV/XLSX files
2. **Normalization** - Convert broker-specific formats into a unified `NormalizedTrade` Pydantic schema
3. **Validation** - Verify required fields, value ranges, and timestamp consistency (all UTC)
4. **Deduplication** - Composite key check (`broker + broker_exec_id`) prevents duplicate records
5. **Persistence** - Atomic transaction writes trades to PostgreSQL; raw broker payloads preserved in JSONB
6. **Grouping** - Standalone FIFO algorithm matches buy/sell pairs into round-trip trade groups (re-runnable, decoupled from import)
7. **Analytics** - P&L dynamically computed; daily summaries via materialized views, refreshed after each import

### Key Design Decisions

- **Batch-first** - Reliable batch imports over real-time streaming
- **Raw data preservation** - Original broker payloads stored in JSONB for audit and reprocessing
- **Atomic imports** - All-or-nothing transactions ensure data consistency
- **UTC everywhere** - All timestamps stored as `timestamptz`; display-time conversion in frontend
- **Single container** - Frontend built as static files and served from FastAPI

## Features

### Supported

- Multi-broker trade import: IBKR Flex Query (XML), Tradovate REST API (JSON), CSV/XLSX
- Automatic broker format detection for CSV files (IBKR Activity Statement, Tradovate export)
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
│   ├── config.py             # Environment-based settings (pydantic-settings)
│   ├── database.py           # SQLAlchemy engine + session
│   ├── auth.py               # API key middleware
│   ├── api/                  # REST route handlers
│   ├── ingestion/            # Broker-specific importers + normalizer + validator
│   ├── models/               # SQLAlchemy ORM models
│   ├── schemas/              # Pydantic request/response schemas
│   ├── services/             # Trade grouper, analytics, scheduler
│   └── migrations/           # Alembic migration versions
├── frontend/
│   └── src/
│       ├── pages/            # Dashboard, Trades, Groups, Analytics, Import, Settings
│       ├── components/       # TradeTable, EquityCurve, PnLCalendar, MetricsCards, etc.
│       └── api/              # HTTP client (TanStack Query)
├── tests/
│   ├── fixtures/             # Sample broker data (XML, JSON, CSV)
│   └── test_api/             # API integration tests
├── Dockerfile                # Multi-stage build (Node + Python)
├── docker-compose.yml        # PostgreSQL + FastAPI
├── pyproject.toml            # Python dependencies (uv)
└── .env.example              # Environment variable template
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
curl -X POST http://localhost:8000/api/v1/imports/csv \
  -H "X-API-Key: <your-api-key>" \
  -F "file=@trades.csv"
```

**IBKR Flex Query:**
```bash
curl -X POST http://localhost:8000/api/v1/imports/flex-query \
  -H "X-API-Key: <your-api-key>"
```

**Tradovate API:**
```bash
curl -X POST http://localhost:8000/api/v1/imports/tradovate \
  -H "X-API-Key: <your-api-key>"
```

## API Endpoints

| Method  | Endpoint                             | Description                    |
|---------|--------------------------------------|--------------------------------|
| GET     | `/health`                            | Service health check           |
| GET     | `/api/v1/trades`                     | List trades (paginated)        |
| GET     | `/api/v1/trades/{id}`                | Trade detail                   |
| POST    | `/api/v1/trades`                     | Create manual trade            |
| GET     | `/api/v1/groups`                     | List trade groups              |
| GET     | `/api/v1/groups/{id}`                | Group detail with legs         |
| POST    | `/api/v1/groups/recompute`           | Recompute grouping for symbol  |
| PATCH   | `/api/v1/groups/{id}`                | Update strategy tag / notes    |
| POST    | `/api/v1/imports/csv`                | Upload and import CSV          |
| POST    | `/api/v1/imports/flex-query`         | Trigger IBKR Flex Query        |
| POST    | `/api/v1/imports/tradovate`          | Trigger Tradovate API pull     |
| GET     | `/api/v1/imports/history`            | Import attempt history         |
| GET     | `/api/v1/analytics/daily`            | Daily P&L summary              |
| GET     | `/api/v1/analytics/symbol/{symbol}`  | Per-symbol statistics          |
| GET     | `/api/v1/analytics/summary`          | Overall portfolio metrics      |

## Running Tests

```bash
uv run pytest tests/ -v

# With coverage
uv run pytest tests/ --cov=backend --cov-report=term-missing
```

## License

Private - All rights reserved.
