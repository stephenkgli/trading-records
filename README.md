# Trading Records

Self-hosted trading records system for capturing, normalizing, and analyzing trading data from Interactive Brokers (IBKR) and Tradovate, with full data ownership.

## Architecture

```
                         +-------------------+
                         |   React Frontend  |
                         |  (TypeScript/Vite)|
                         +--------+----------+
                                  |
                                  | REST API
                                  v
                         +-------------------+
                         |  FastAPI Backend   |
                         |  (Python 3.12)    |
                         +--------+----------+
                                  |
                    +-------------+-------------+
                    |             |              |
              +-----+----+ +-----+-----+ +-----+-----+
              | Ingestion| | Services  | |    API     |
              |  Layer   | |  Layer    | |  Routes    |
              +-----+----+ +-----+-----+ +-----------+
                    |             |
                    v             v
                         +-------------------+
                         |  PostgreSQL 16    |
                         +-------------------+
```

**Data Flow:**

1. **Ingestion** - Import trades from IBKR Flex Query (XML), Tradovate API (JSON), or CSV/XLSX files
2. **Normalization** - Convert broker-specific formats into a unified `NormalizedTrade` schema
3. **Validation** - Verify required fields, value ranges, and timestamp consistency
4. **Deduplication** - Composite key check (`broker + broker_exec_id`) prevents duplicate records
5. **Persistence** - Atomic transaction writes trades to PostgreSQL with JSONB raw data preservation
6. **Grouping** - FIFO algorithm matches buy/sell pairs into round-trip trade groups
7. **Analytics** - P&L calculations, daily summaries via materialized views, per-symbol statistics

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
│   ├── main.py                 # FastAPI app entry point
│   ├── config.py               # Environment-based configuration
│   ├── database.py             # SQLAlchemy session factory
│   ├── auth.py                 # API key authentication middleware
│   ├── logging_config.py       # structlog JSON logging
│   ├── api/                    # REST API route handlers
│   │   ├── health.py           #   Health check
│   │   ├── trades.py           #   Trade CRUD
│   │   ├── groups.py           #   Trade groups (round-trips)
│   │   ├── imports.py          #   Import orchestration
│   │   └── analytics.py        #   P&L and aggregations
│   ├── ingestion/              # Multi-broker data ingestion
│   │   ├── base.py             #   Abstract base ingester
│   │   ├── ibkr_flex.py        #   IBKR Flex Query XML importer
│   │   ├── tradovate.py        #   Tradovate REST API importer
│   │   ├── csv_importer.py     #   CSV/XLSX format detection importer
│   │   ├── normalizer.py       #   Broker -> NormalizedTrade conversion
│   │   └── validator.py        #   Data validation
│   ├── models/                 # SQLAlchemy ORM models
│   │   ├── trade.py            #   Trade record
│   │   ├── trade_group.py      #   TradeGroup + TradeGroupLeg
│   │   └── import_log.py       #   Import audit trail
│   ├── schemas/                # Pydantic request/response models
│   │   ├── trade.py
│   │   ├── analytics.py
│   │   └── import_result.py
│   ├── services/               # Business logic
│   │   ├── analytics.py        #   P&L aggregation
│   │   ├── scheduler.py        #   APScheduler job management
│   │   └── trade_grouper.py    #   FIFO round-trip grouping
│   └── migrations/             # Alembic database migrations
│       └── versions/
│           ├── 001_initial_schema.py
│           └── 002_daily_summaries_view.py
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── src/
│       ├── main.tsx            # React entry point
│       ├── App.tsx             # Route definitions
│       ├── index.css           # Global styles
│       ├── api/
│       │   └── client.ts       # HTTP API client (TanStack Query)
│       ├── pages/
│       │   ├── DashboardPage.tsx
│       │   ├── TradesPage.tsx
│       │   ├── GroupsPage.tsx
│       │   ├── AnalyticsPage.tsx
│       │   ├── ImportPage.tsx
│       │   └── SettingsPage.tsx
│       └── components/
│           ├── Layout.tsx       # Navigation shell
│           ├── TradeTable.tsx   # Sortable trade data table
│           ├── EquityCurve.tsx  # Equity growth chart
│           ├── PnLCalendar.tsx  # Daily P&L heatmap
│           ├── SymbolBreakdown.tsx
│           ├── MetricsCards.tsx # KPI cards
│           └── CsvUpload.tsx   # File upload component
├── tests/
│   ├── conftest.py             # Shared fixtures
│   ├── fixtures/               # Test data (CSV, XML, JSON)
│   ├── test_api/               # API integration tests
│   ├── test_csv_importer.py
│   ├── test_ibkr_flex.py
│   ├── test_tradovate.py
│   ├── test_normalizer.py
│   ├── test_validator.py
│   ├── test_trade_grouper.py
│   └── test_dedup.py
├── config/
│   └── config.example.yaml
├── Dockerfile                  # Multi-stage build
├── docker-compose.yml          # PostgreSQL + FastAPI
├── pyproject.toml              # Python project config (uv)
├── alembic.ini                 # Migration config
├── .env.example                # Environment variable template
└── .gitignore
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

1. **Clone the repository:**

   ```bash
   git clone <repo-url>
   cd trading-records
   ```

2. **Create the environment file:**

   ```bash
   cp .env.example .env
   ```

3. **Edit `.env`** with your broker credentials (IBKR / Tradovate) and a custom `API_KEY`.

4. **Start all services:**

   ```bash
   docker compose up -d
   ```

5. **Run database migrations:**

   ```bash
   docker compose exec app alembic upgrade head
   ```

6. **Access the application:**

   - Frontend: http://localhost:8000
   - API docs: http://localhost:8000/docs

### Option 2: Local Development

1. **Clone and set up environment:**

   ```bash
   git clone <repo-url>
   cd trading-records
   cp .env.example .env
   ```

2. **Start PostgreSQL** (via Docker or local install):

   ```bash
   docker run -d --name trading-pg \
     -e POSTGRES_USER=trading \
     -e POSTGRES_PASSWORD=trading \
     -e POSTGRES_DB=trading_records \
     -p 5432:5432 \
     postgres:16-alpine
   ```

3. **Install Python dependencies:**

   ```bash
   uv sync
   ```

4. **Run database migrations:**

   ```bash
   uv run alembic upgrade head
   ```

5. **Start the backend:**

   ```bash
   uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
   ```

6. **Install and start the frontend** (in a separate terminal):

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

7. **Access the application:**

   - Frontend: http://localhost:3000 (Vite dev server)
   - Backend API: http://localhost:8000
   - API docs: http://localhost:8000/docs

### Importing Trades

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

### Running Tests

```bash
uv run pytest tests/ -v
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

## Environment Variables

| Variable                   | Description                          | Required |
|----------------------------|--------------------------------------|----------|
| `DATABASE_URL`             | PostgreSQL connection string         | Yes      |
| `DB_USER`                  | Database user                        | Yes      |
| `DB_PASSWORD`              | Database password                    | Yes      |
| `API_KEY`                  | API authentication key               | No       |
| `CORS_ORIGINS`             | Allowed CORS origins                 | No       |
| `LOG_LEVEL`                | Logging level (default: INFO)        | No       |
| `IBKR_FLEX_TOKEN`          | IBKR Flex Query token                | No       |
| `IBKR_QUERY_ID`            | IBKR Flex Query ID                   | No       |
| `TRADOVATE_USERNAME`       | Tradovate account username           | No       |
| `TRADOVATE_PASSWORD`       | Tradovate account password           | No       |
| `TRADOVATE_CLIENT_ID`      | Tradovate API client ID              | No       |
| `TRADOVATE_CLIENT_SECRET`  | Tradovate API client secret          | No       |
| `TRADOVATE_DEVICE_ID`      | Tradovate device identifier          | No       |
| `TRADOVATE_ENVIRONMENT`    | Tradovate env (demo/live)            | No       |

## License

Private - All rights reserved.
