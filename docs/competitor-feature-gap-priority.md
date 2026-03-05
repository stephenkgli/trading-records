# 竞品对标与功能优先级路线图（TradesViz / TradeZella）

更新日期：2026-02-21

## 1. 目标

对比当前项目与 TradesViz（常被写作 Tradsviz）和 TradeZella 的功能能力，输出可执行的增量功能优先级。

本文件重点是功能差距与落地顺序，不讨论 UI 视觉细节。

## 2. 对标范围与信息来源

对标范围：
- TradesViz 官方站点与功能词条
- TradeZella 官方站点与帮助中心
- 当前仓库实际能力（README、API、页面与服务层）

主要来源：
- TradesViz 首页：https://www.tradesviz.com/
- TradesViz 自动同步词条：https://www.tradesviz.com/glossary/auto-sync/
- TradesViz Options Greeks 词条：https://www.tradesviz.com/glossary/options-greeks/
- TradeZella 首页：https://www.tradezella.com/
- TradeZella Features：https://www.tradezella.com/features
- TradeZella 帮助中心总览：https://help.tradezella.com/en/articles/5801077-welcome-to-tradezella
- TradeZella Replay 与 Backtesting 区别：https://help.tradezella.com/en/articles/11787298-what-is-the-trade-replay-feature-in-tradezella-and-how-does-it-compare-to-backtesting
- TradeZella Backtesting：https://help.tradezella.com/en/articles/9854312-what-is-backtesting-in-tradezella
- TradeZella Broker Sync 行为：https://help.tradezella.com/en/articles/8542897-broker-sync-same-day-trades

## 3. 当前项目能力基线

已具备：
- IBKR / Tradovate 的 CSV/XLSX 导入
- 交易标准化、校验、去重、持久化
- FIFO 交易分组（round-trip）
- Analytics 核心指标接口（daily/calendar/by-symbol/by-strategy/performance）
- Groups 列表/详情/图表（含 marker 与资产类型筛选）
- Databento + Tiingo 行情能力与缓存
- 交易组维度的 strategy_tag 与 notes

相对竞品的主要缺口：
- Broker 自动同步导入
- Playbook 与规则执行跟踪
- Replay / Backtesting
- 结构化复盘字段（错误类型、情绪、执行评分等）
- 自定义分析看板 / Pivot 风格分析
- Options 深度分析（多腿、Greeks）
- Mentor/团队协作能力

## 4. 功能差距矩阵

| 功能域 | TradesViz | TradeZella | 当前项目 | 差距等级 |
|---|---|---|---|---|
| 自动化记账（Broker Sync） | 强（多券商、多同步模式） | 强（自动同步+定时重拉） | 仅手动文件导入 | 高 |
| 报表深度 | 600+ 指标、可定制看板、Pivot 分析 | 50+ 报表、钻取分析 | 核心固定报表 | 高 |
| Playbook/策略执行一致性 | 有计划与检查能力 | 有 Playbook 与规则追踪 | 仅 strategy_tag | 高 |
| 交易复盘回放 | 有模拟/回放能力 | 有 Replay（含执行复盘） | 无 | 高 |
| 策略回测 | 多资产模拟器能力强 | Backtesting 能力强 | 无 | 高 |
| 质化复盘体系 | 笔记/标签/计划/目标 | 复盘模板与结构化记录 | 仅 notes | 中高 |
| Options 专项能力 | 有 Greeks 等专项模块 | 有期权相关功能 | 很弱 | 高 |
| 协作/带教 | 有社区/分享 | Mentor Mode + 分享 | 无 | 中 |
| 教学内容层 | 有 | 有（Zella University） | 无 | 中低 |

## 5. 优先级路线图

优先级规则：
- P0：业务价值最高，且可在现有架构中较快落地
- P1：显著增强竞争力，放在 P0 稳定后
- P2：进阶/扩展能力

### P0（下一阶段必须补齐）

1. Broker Auto-Sync（先做 IBKR + Tradovate）
- 优先原因：这是与竞品差距最大的入口能力，且可显著降低用户使用门槛。
- MVP 范围：
  - 账户连接模型（只读凭证/令牌）
  - 增量同步任务（定时）
  - 手动重同步接口
  - 同步日志与错误诊断
- 非 MVP：
  - 首期覆盖 10+ 券商
  - 全实时推送

2. Playbook 与规则执行跟踪
- 优先原因：竞品核心价值不是“看收益”，而是“改行为”。
- MVP 范围：
  - Playbook 实体（策略说明、检查项、setup 标签）
  - 交易组关联 playbook/setup
  - 规则执行结果（遵守/未遵守 + 原因）
  - Playbook 绩效报表
- 非 MVP：
  - 复杂流程编排

3. 结构化复盘字段（替代纯文本）
- 优先原因：为行为统计、策略归因、后续 AI 分析打基础。
- MVP 范围：
  - 错误类型、情绪、信心、执行评分等标准字段
  - 日级复盘（盘前计划/盘后总结）
  - 支持筛选和聚合统计
- 非 MVP：
  - NLP 自动打标

### P1（P0 稳定后）

4. Replay Lite（基于真实交易的回放）
- 优先原因：对“执行质量复盘”价值高，可直接提升复盘效率。
- MVP 范围：
  - 在 Group 图表上提供时间线回放
  - 逐步查看入场/出场，支持假设出场对比
  - 回放注释持久化
- 非 MVP：
  - 全量 Level2/逐笔成交级仿真

5. 高级分析构建器（自定义看板/Pivot 风格）
- 优先原因：当前分析视图固定，进阶用户缺少自助分析能力。
- MVP 范围：
  - 自定义卡片/图表/表格并保存
  - 维度筛选（broker、asset_class、setup、playbook、tag）
  - 表格导出
- 非 MVP：
  - 自然语言 AI 分析

6. Backtesting Sessions
- 优先原因：竞品标配能力，且可与 Replay 形成闭环。
- MVP 范围：
  - 回测会话模型（品种+时间区间）
  - 基于历史 K 线的手动模拟开平仓
  - 会话统计与可选复盘沉淀
- 非 MVP：
  - 全资产高精度撮合模型

### P2（扩展能力）

7. Options 分析升级
- 优先原因：价值高，但模型和数据复杂度也高。
- MVP 范围：
  - 多腿期权仓位分组
  - 策略级统计（价差类型、DTE 分桶）
- 下一步：
  - Greeks 暴露分析

8. 多用户协作 / Mentor Mode
- 优先原因：对带教场景有价值，但对当前单机自托管用户不是刚需。
- MVP 范围：
  - 用户与角色模型（owner/mentor/member）
  - 复盘记录评论与只读共享

9. 教学内容层
- 优先原因：长期价值有，但不是核心基础设施。
- MVP 范围：
  - 内部 playbook 文档与模板体系

## 6. 推荐落地顺序

Phase A（P0）：
- 自动同步基础设施
- Playbook + 规则执行
- 结构化复盘字段

Phase B（P1）：
- Replay Lite
- 自定义分析看板
- Backtesting 会话

Phase C（P2）：
- Options 深化
- 协作/带教
- 内容层

## 7. 明确暂缓项

- 交易所级逐笔 + Level2 全仿真回放
- 先做“AI 聊天分析”再补基础数据模型
- 在 IBKR/Tradovate 同步质量稳定前扩展大量新券商

## 8. 对当前仓库的实现建议

后端重点扩展目录：
- `backend/ingestion/`：连接器化同步导入
- `backend/services/`：playbook、replay、backtesting、分析构建器
- `backend/api/`：新增 `/playbooks`、`/replay`、`/backtesting`、`/sync` 路由
- `backend/models/` + Alembic：新增实体与迁移

前端重点扩展目录：
- `frontend/src/pages/`：Playbooks、Replay、Backtesting、Journals 页面
- `frontend/src/components/`：复盘组件与回放控制组件
- `frontend/src/api/`：新增类型与请求封装

