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
                        | Pydantic settings  |     |                  |
                        | - .env loading     |     | Analytics Engine |
                        | - Runtime updates  |     | - P&L aggregation|
                        | - Typed fields     |     | - Daily summaries|
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
- **Pydantic config** - Settings loaded from environment variables and `.env`
- **Unified exceptions** - Structured JSON error responses with error code, message, and context
- **Dependency injection** - Services injected via FastAPI `Depends()` for testability
- **Fail-fast market data** - Provider errors propagate directly; no fallback chains or circuit breakers
- **Permanent OHLCV cache** - Completed bars cached forever in PostgreSQL; no expiry, no staleness checks

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

## Running Tests

```bash
uv run pytest tests/ -v

# With coverage
uv run pytest tests/ --cov=backend --cov-report=term-missing
```

Tests use SQLite in-memory databases for speed. PostgreSQL-specific features (materialized views, JSONB operations, upsert with `ON CONFLICT`) are guarded by dialect checks so tests run without a PostgreSQL instance.

## License

Private - All rights reserved.
