# Trading Records

自托管交易记录系统，用于导入、标准化、分组并分析交易数据（目前支持 IBKR 与 Tradovate CSV/XLSX），并提供 K 线与交易标记图表。

## Architecture

系统由四层组成，核心链路如下：

1. Data Ingestion
- 上传 CSV/XLSX（Import API 或前端页面）
- 解析与格式识别（IBKR / Tradovate）
- 标准化、校验、去重（`broker + broker_exec_id`）
- 原始数据持久化（`raw_data`）

2. Domain Services
- 交易分组（FIFO，生成 round-trip trade groups）
- 分析统计（按日期、品种、策略、绩效指标）
- 图表数据服务（OHLCV 缓存 + 市场数据 Provider）

3. API Layer
- FastAPI + `/api/v1` 路由
- API Key 鉴权
- 统一错误响应与结构化日志

4. Storage
- PostgreSQL 16（生产）
- 关键表：`trades`、`trade_groups`、`trade_group_legs`、`import_logs`、`ohlcv_cache`
- 物化视图：`daily_summaries`

## Key Features

- 多券商交易导入（IBKR / Tradovate）
- 自动格式识别与标准化
- 原始数据保留（审计/复算友好）
- 去重导入（可重复导入同一文件）
- FIFO 交易分组（支持多次重算）
- Analytics 页面（绩效、按品种统计、权益曲线）
- Groups 页面（状态/排序/资产类型筛选）
- Group 详情 K 线图（交易标记）
- 市场数据 Provider（Databento / Tiingo）+ PostgreSQL 缓存
- FastAPI + React TypeScript 单仓库开发体验

## Quick Start

### 1) Prerequisites

- Docker + Docker Compose
- 或本地开发环境：Python 3.12+、`uv`、Node.js 20+、PostgreSQL 16

### 2) Docker（推荐）

```bash
git clone <repo-url>
cd trading-records
cp .env.example .env
docker compose up -d
docker compose exec app alembic upgrade head
```

访问：
- App: http://localhost:8000
- API Docs: http://localhost:8000/docs

### 3) 本地开发

```bash
git clone <repo-url>
cd trading-records
cp .env.example .env

# Backend
uv sync
uv run alembic upgrade head
uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Frontend（新终端）
cd frontend
npm install
npm run dev
```

访问：
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Configuration

通过环境变量与 `.env` 配置，常见项如下：

```env
DATABASE_URL=postgresql://trading:trading@localhost:5432/trading_records
API_KEY=
CORS_ORIGINS=http://localhost:3000,http://localhost:8000

DATABENTO_API_KEY=
TIINGO_API_KEY=
OHLCV_CACHE_ENABLED=true

LOG_LEVEL=INFO
IBKR_CSV_TIMEZONE=America/New_York
TRADOVATE_CSV_TIMEZONE=Asia/Shanghai
```

## Testing

```bash
uv run pytest tests/ -v
uv run pytest tests/ --cov=backend --cov-report=term-missing
```

说明：测试默认使用 SQLite in-memory；生产数据库能力以 PostgreSQL 为准。

## Project Structure

- `backend/api/`：HTTP 路由
- `backend/services/`：业务逻辑（分组、分析、市场数据）
- `backend/ingestion/`：导入链路（解析/标准化/校验/去重）
- `backend/models/`：SQLAlchemy ORM
- `backend/schemas/`：Pydantic schema
- `backend/migrations/`：Alembic 迁移
- `frontend/src/pages/`：页面
- `frontend/src/components/`：可复用组件
- `frontend/src/api/`：类型与请求封装
- `tests/`：测试

## License

Private - All rights reserved.
