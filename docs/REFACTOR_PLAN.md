# 重构方案

## 1. 背景与目标
本方案基于当前仓库结构与 AGENTS.md 规范要求，目标是：
- 明确分层边界（API / Service / Ingestion / Model / Schema）
- 降低摄取链耦合、提升可扩展性
- 统一异常与配置管理，提高可维护性
- 强化 API 版本化与依赖注入能力
- 提升前端 API 类型与调用层一致性
- 分层测试，保证回归质量

## 2. 当前结构概览（摘要）
- 后端：`backend/{api, schemas, models, ingestion, services, migrations}`
- 前端：`frontend/src/{pages, components, api}`
- 测试：`tests/{test_api, 单元测试}`

## 3. 主要问题与改进点
1. 摄取链耦合度较高，导入源与链路编排混在同一层，新增导入源成本高。
2. Service 层覆盖不足，业务逻辑仍部分散落在 API 层。
3. 异常处理缺少统一格式与规范。
4. 配置管理未分环境，不利于 dev/test/prod 隔离。
5. API 未版本化，升级风险高。
6. 前端 API 类型与请求层拆分不足，易产生重复逻辑。
7. 测试缺少明显分层，难以区分单元与集成。

## 4. 重构原则
- 遵循 AGENTS.md 约束：分层清晰、业务逻辑集中、数据完整性优先。
- 以最小可行改动分阶段推进，避免大规模一次性迁移。
- 任何行为变更需新增或更新测试。
- PostgreSQL 为生产基准，SQLite 仅限测试兼容。

## 5. 分阶段重构方案

### 阶段 1：基础规范化
**目标**：统一异常与配置体系。

**动作**：
- 新增 `backend/exceptions/`：定义 `AppException` 等基类与全局处理器。
- 新增 `backend/config/`：拆分 dev/test/prod 配置，并提供工厂加载。

**产出**：
- 异常响应格式统一（错误码、消息、上下文）。
- 配置加载可按环境切换。

### 阶段 2：摄取链解耦与服务层补齐
**目标**：导入源可插拔，业务逻辑集中到 Service 层。

**动作**：
- `ingestion/` 内拆出 `sources/` 目录，统一导入源接口。
- 引入 `pipeline.py` 作为摄取链编排器。
- 新增 `ImportService`、`TradeService` 等核心服务。

**产出**：
- 新增导入源仅需实现 `ImportSource`。
- API 层只负责请求/响应，不处理业务细节。

### 阶段 3：API 版本化与依赖注入
**目标**：稳定对外 API，并提升可测试性。

**动作**：
- 将路由移至 `backend/api/v1/`，统一 `/api/v1` 前缀。
- 新增 `backend/api/dependencies.py`，集中 Service 注入。

**产出**：
- 版本化 API 路由。
- 可在测试中替换依赖实现。

### 阶段 4：前端 API 层标准化
**目标**：类型与请求层分离，减少重复逻辑。

**动作**：
- 拆分 `frontend/src/api/`：`types/` + `endpoints/` + `hooks/`。
- 页面层使用 hooks 获取数据，避免直接调用 client。

**产出**：
- API 调用集中、类型安全增强。
- 页面逻辑更聚焦。

### 阶段 5：测试分层与回归保障
**目标**：明确单元/集成边界，提升回归效率。

**动作**：
- `tests/` 下新增 `unit/` 与 `integration/` 分层。
- 对 ImportService、Ingestion Pipeline 补充单元测试。

**产出**：
- 单元测试更快，集成测试更清晰。

## 6. 建议目录结构（示意）
```
backend/
  exceptions/
  config/
  api/
    v1/
    dependencies.py
  ingestion/
    sources/
    pipeline.py
    normalizer.py
    validator.py
    dedup.py
  services/
    trade_service.py
    import_service.py
    analytics_service.py

frontend/src/
  api/
    client.ts
    types/
    endpoints/
    hooks/
```

## 7. 执行顺序建议
优先顺序：阶段 1 → 阶段 2 → 阶段 5 → 阶段 3 → 阶段 4

理由：先建立基础规范与链路稳定，再补强测试与版本化，最后优化前端调用层。

## 8. 验收标准
- API 返回错误格式统一。
- 新增导入源无需修改 pipeline 内部逻辑。
- Service 层承载核心业务逻辑，API 层仅编排请求/响应。
- 测试分层清晰且核心链路有覆盖。
- 前端 API 调用收敛到 endpoints/hooks。
