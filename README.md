# Trading Records

自托管交易记录系统，用于导入、标准化、分组并分析交易数据（当前支持 IBKR 与 Tradovate），并提供交易标记与 K 线图表能力。

---

## 核心能力

- 多券商交易导入（CSV/XLSX）
- 导入链路标准化：解析 → 标准化 → 校验 → 去重 → 入库
- 去重语义：`broker + broker_exec_id`
- 保留原始数据（`raw_data`）便于审计与复算
- FIFO 交易分组（round-trip）
- 分析统计（按日期/品种等维度）
- 市场数据集成（Databento / Tiingo）+ 本地缓存（OHLCV）

---

## 快速开始

## 1）Docker 启动（推荐）

```bash
cp .env.example .env
docker compose up -d
docker compose exec app alembic upgrade head
```

访问：

- 前端开发服务：`http://localhost:3000`
- 后端 API：`http://localhost:8000`
- API 文档：`http://localhost:8000/docs`

---

## 2）本地开发（PG 容器 + Backend + Frontend）

### Terminal 1：启动 PostgreSQL（容器）

```bash
# 首次创建并启动 PG16 容器
docker run -d \
  --name trading-records-pg \
  -e POSTGRES_USER=trading \
  -e POSTGRES_PASSWORD=trading \
  -e POSTGRES_DB=trading_records \
  -p 5432:5432 \
  postgres:16-alpine

```

### Terminal 2：启动后端

```bash
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Terminal 3：启动前端

```bash
cd frontend
npm install
npm run dev
```

访问：

- 前端开发服务：`http://localhost:3000`
- 后端 API：`http://localhost:8000`
- API 文档：`http://localhost:8000/docs`
