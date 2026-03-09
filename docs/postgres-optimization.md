# PostgreSQL 优化方案（trading-records）

## 1. 目标

围绕当前项目的 PostgreSQL 使用，优化以下维度：

1. 查询性能（索引与查询路径）
2. 连接稳定性（连接池与超时）
3. 写入效率（批量导入与事务边界）
4. 可观测性与可恢复性（健康检查、刷新策略、回滚路径）

---

## 2. 关键现状与证据

### 2.1 连接池参数不完整
- 当前仅配置：`pool_pre_ping/pool_size/max_overflow`
- 代码位置：`backend/database.py:10`
- 风险：长连接老化、慢 SQL 无上限执行。

### 2.2 高频查询缺复合索引
- `trades` 现有索引未覆盖 `account_id + symbol + executed_at`
- 代码位置：`backend/models/trade.py:20`、查询位于 `backend/services/trade_grouper.py:123`
- 风险：按账户+品种重算分组时扫描成本高。

### 2.3 `trade_groups` 列表查询索引匹配不足
- 接口常见过滤：`status/symbol/account_id/asset_class`
- 代码位置：`backend/api/groups.py:135`
- 当前索引：`backend/models/trade_group.py:20`
- 风险：复合过滤下执行计划不稳定。

### 2.4 analytics 关键指标多次独立扫描
- `total_pnl` 与 `commissions/trades/days` 分开查询
- 代码位置：`backend/services/analytics.py:531`、`backend/services/analytics.py:553`
- 风险：同一请求内多次扫描，响应延迟增大。

### 2.5 物化视图刷新回退策略可能加锁
- 并发刷新失败后回退非并发刷新
- 代码位置：`backend/services/analytics.py:109`
- 风险：高峰期可能造成读阻塞。

### 2.6 导入路径逐条 `db.add`
- 代码位置：`backend/ingestion/base.py:90`
- 风险：大批量导入 CPU/ORM 开销偏高。

### 2.7 健康检查未返回失败状态码
- 代码位置：`backend/api/health.py:14`
- 风险：容器编排无法准确判定不可用实例。

---

## 3. 优化项（按优先级）

## P1（优先实施）

### P1-1 连接池与超时参数增强
**改动文件**：`backend/database.py`

建议为 PostgreSQL 增加：
- `pool_recycle`
- `connect_timeout`
- `statement_timeout`
- 可选 keepalive 参数

示例（仅示意，按项目风格调整）：

```python
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
    connect_args={
        "connect_timeout": 10,
        "statement_timeout": 60000,
    },
)
```

### P1-2 新增高收益复合索引
**改动文件**：新增 Alembic migration（`backend/migrations/versions/`）

建议索引：

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trades_account_symbol_executed_at
ON trades (account_id, symbol, executed_at);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trade_groups_account_symbol_status
ON trade_groups (account_id, symbol, status);
```

> 说明：`CONCURRENTLY` 需在迁移策略中谨慎处理事务语义。

### P1-3 物化视图刷新保护
**改动文件**：`backend/services/analytics.py`

建议：
1. 刷新前检查唯一索引存在（避免盲目 `CONCURRENTLY`）。
2. 刷新语句加超时控制。
3. 日志输出刷新模式与耗时，便于回溯。

---

## P2（建议紧随 P1）

### P2-1 合并性能指标查询
**改动文件**：`backend/services/analytics.py`

将 `get_performance_metrics` 中多段聚合 SQL 合并为单次查询（CTE 或子查询），减少网络往返与重复扫描。

### P2-2 物化视图补充维度（asset_class）
**改动文件**：`backend/migrations/versions/002_daily_summaries_view.py`（或新迁移替换）

当前 asset_class 过滤会绕过 MV（见 `backend/services/analytics.py:148`）。建议在 MV 中纳入 `asset_class` 维度，减少 fallback 计算。

### P2-3 导入批量写入优化
**改动文件**：`backend/ingestion/base.py`

对大批量导入场景使用批量 insert（如 `bulk_insert_mappings` 或 Core insert），降低 ORM 对象构造成本。

---

## P3（可选增强）

### P3-1 健康检查语义化状态码
**改动文件**：`backend/api/health.py`

数据库不可用时返回 `503`，让健康探针可正确剔除异常实例。

### P3-2 JSONB 索引预留
**改动文件**：后续迁移

若未来按 `raw_data` 条件查询增多，可加：

```sql
CREATE INDEX idx_trades_raw_data_gin
ON trades USING GIN (raw_data);
```

---

## 4. 建议实施顺序

1. **先 P1-1 + P1-2**：先稳连接与索引，收益最直接。
2. **再 P1-3 + P2-1**：降低分析接口和刷新阶段抖动。
3. **再 P2-2 + P2-3**：优化架构层计算路径与导入吞吐。
4. **最后 P3**：完善可观测性与前瞻性索引。

---

## 5. 验证清单

1. 查询计划验证（`EXPLAIN (ANALYZE, BUFFERS)`）
   - `recompute_groups` 相关查询是否命中新复合索引
   - `groups list` 过滤查询是否避免大范围回表
2. 导入压测
   - 大样本 CSV 导入耗时、CPU、锁等待变化
3. analytics 接口对比
   - `get_performance_metrics` 响应耗时前后对比
4. 刷新行为观测
   - MV 刷新是否稳定为并发刷新，失败回退率是否下降
5. 健康检查行为
   - DB 断开时是否返回正确失败状态

---

## 6. 风险与回滚

1. **索引创建风险**：大表创建索引期间会占用 I/O。
   - 缓解：低峰执行，优先 `CONCURRENTLY`。
2. **查询重写风险**：统计口径可能发生边界差异。
   - 缓解：重构前后跑对账测试（固定样本）。
3. **连接超时过短风险**：合法慢查询被中断。
   - 缓解：按接口分类设置超时，分阶段调参。

回滚策略：
- 索引可通过迁移 `DROP INDEX` 回滚。
- SQL 重写通过回滚版本或特性开关恢复。
- 连接参数可配置化后快速回退。

---

## 7. 结论

当前项目的 PG 优化重点应集中在：
- **连接超时与连接池韧性**
- **高频查询复合索引**
- **analytics 聚合查询合并**
- **物化视图刷新保护**

按本文分阶段执行，可在不改变业务语义前提下，显著改善查询延迟与导入稳定性。