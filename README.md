# Trading Records

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-green.svg)](https://www.python.org/downloads/)
[![React 18](https://img.shields.io/badge/React-18-61DAFB.svg)](https://react.dev/)
[![PostgreSQL 16](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)

自托管交易记录系统，用于导入、标准化、分组并分析交易数据（当前支持 **IBKR** 与 **Tradovate**），并提供交易标记与 K 线图表能力。

<!-- TODO: 添加截图
![Dashboard Screenshot](docs/screenshots/dashboard.png)
-->

---

## 核心功能

- **多券商交易导入** — 支持 CSV/XLSX，自动识别券商格式
- **导入管线** — 解析 → 标准化 → 校验 → 去重 → 入库
- **去重语义** — 基于 `(broker, broker_exec_id)` 防止重复导入
- **原始数据保留** — 保留原始券商数据（`raw_data`）便于审计与复算
- **FIFO 交易分组** — 自动 round-trip 分组，FIFO 匹配
- **分析看板** — P&L 日历、权益曲线、品种分布、关键指标卡片
- **行情数据集成** — Databento / Tiingo + 本地 OHLCV 缓存
- **K 线图表** — 交互式图表，支持交易标记和绘图工具

## 技术栈

```
前端:     React 18 · TypeScript 5 · Vite · TailwindCSS · TanStack Query/Table · Recharts
后端:     Python 3.12 · FastAPI · SQLAlchemy 2.0 · Pydantic · Alembic · structlog
数据库:   PostgreSQL 16 (JSONB、物化视图、UUID)
基础设施: Docker · Docker Compose
```

## 快速开始

### 方式一：Docker 启动（推荐）

```bash
git clone https://github.com/stephenkgli/trading-records.git
cd trading-records
cp .env.example .env
docker compose up -d
docker compose exec app alembic upgrade head
```

### 方式二：本地开发

**Terminal 1** — 启动 PostgreSQL：

```bash
docker run -d \
  --name trading-records-pg \
  -e POSTGRES_USER=trading \
  -e POSTGRES_PASSWORD=trading \
  -e POSTGRES_DB=trading_records \
  -v ./pgdata:/var/lib/postgresql/data \
  -p 5432:5432 \
  postgres:16-alpine
```

**Terminal 2** — 启动后端：

```bash
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 3** — 启动前端：

```bash
cd frontend
npm install
npm run dev
```

## 访问地址

| 服务 | 地址 |
|------|------|
| 前端 | http://localhost:3000 |
| 后端 API | http://localhost:8000 |
| API 文档 (Swagger) | http://localhost:8000/docs |

## 项目结构

```
trading-records/
├── backend/
│   ├── api/            # FastAPI 路由处理
│   ├── config/         # 应用配置
│   ├── exceptions/     # 自定义异常
│   ├── ingestion/      # CSV/XLSX 导入管线
│   ├── migrations/     # Alembic 数据库迁移
│   ├── models/         # SQLAlchemy ORM 模型
│   ├── schemas/        # Pydantic 请求/响应模式
│   ├── services/       # 业务逻辑（分组、分析）
│   └── utils/          # 工具函数
├── frontend/
│   └── src/
│       ├── api/        # HTTP 客户端与类型定义
│       ├── components/ # 可复用 UI 组件
│       ├── hooks/      # 自定义 React Hooks
│       ├── pages/      # 页面级路由组件
│       └── utils/      # 前端工具函数
├── tests/              # 后端测试套件
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```

## 运行测试

```bash
# 后端测试
uv run pytest tests/ -v

# 后端测试 + 覆盖率
uv run pytest tests/ --cov=backend --cov-report=term-missing

# 前端构建检查
cd frontend && npm run build
```

## 许可证

本项目采用 MIT 许可证 — 详见 [LICENSE](LICENSE)。
