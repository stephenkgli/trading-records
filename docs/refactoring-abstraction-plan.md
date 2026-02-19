# 重构与抽象计划（基于当前项目）

> 本计划基于 `docs/refactoring-abstraction-best-practices.md` 与当前代码现状制定。

## 1) 统一分析统计的过滤与参数构建

**问题**：日期/账户/资产类型过滤与参数拼装在多个函数中重复，空资产类型处理逻辑重复。

**涉及位置**：
- `backend/services/analytics.py:80-114`
- `backend/services/analytics.py:174-193`
- `backend/services/analytics.py:404-456`
- `backend/services/analytics.py:459-555`
- 资产类型空数组检查：`backend/services/analytics.py:89-91`, `226-228`, `412-414`, `471-486`
- API 解析：`backend/api/analytics.py:39-54`

**计划**：
- 抽取 `build_date_range_filters(...)` 与 `build_asset_class_filters(...)` 辅助函数，统一 SQL 片段与参数字典构造。
- 统一 `asset_classes` 的空数组语义处理，避免多处手写分支。
- API 层解析逻辑收敛成单一函数，供多处调用。

---

## 2) 抽取会话/事务使用的通用上下文管理器

**问题**：一次性操作函数使用 `own_session` 模式重复。

**涉及位置**：
- `backend/services/analytics.py:39-63`
- `backend/ingestion/base.py:58-160`

**计划**：
- 在 `backend/utils/db.py` 引入 `session_scope()`（或类似）上下文管理器。
- 对简单“自建会话 + try/commit/rollback/close”的场景迁移使用。
- 保留 `BaseIngester.import_records()` 的事务语义，仅在可替代处使用，避免影响嵌套事务行为。

---

## 3) 统一 CSV 解析器模板逻辑

**问题**：多个 CSV 解析器中“遍历-解析-异常处理-日志”的样板逻辑重复。

**涉及位置**：
- `backend/ingestion/csv_importer.py:136-201`
- `backend/ingestion/csv_importer.py:300-330`
- `backend/ingestion/csv_importer.py:405-449`

**计划**：
- 抽取共享解析框架（如 `_parse_rows(reader, normalize_func, ...)`），集中处理行计数、异常日志与统计。
- 仅保留每种格式特有的 `normalize` 实现。
- 保持导入链路与 dedup 语义不变（遵循导入链规则）。

---

## 4) TradeService 过滤条件去重

**问题**：Trade 列表与统计使用相同过滤逻辑，重复维护。

**涉及位置**：
- `backend/services/trade_service.py:58-71`
- `backend/services/trade_service.py:153-164`

**计划**：
- 提取 `_apply_trade_filters(query, ...)` 辅助函数，统一过滤逻辑。
- 保证筛选行为一致，降低后续变更成本。

---

## 5) 前端 Analytics API 的抽象统一

**问题**：analytics fetcher 在 `client.ts` 与 `endpoints/analytics.ts` 中重复实现。

**涉及位置**：
- `frontend/src/api/client.ts:138-209`
- `frontend/src/api/endpoints/analytics.ts:18-35`

**计划**：
- 统一使用 `endpoints/analytics.ts` 的工厂方法，或将 `client.ts` 迁移为 re-export。
- 提炼 `asset_classes` 参数拼装函数，保证空数组语义与后端一致。

---

## 验证与回归建议

- 后端测试：`uv run pytest tests/ -v`
- 变更广泛时补充覆盖率：`uv run pytest tests/ --cov=backend --cov-report=term-missing`
- 前端变更：`cd frontend && npm run build`
