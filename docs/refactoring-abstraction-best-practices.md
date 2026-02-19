# 重构与抽象最佳实践（本项目）

> 适用范围：Python/FastAPI/SQLAlchemy 后端与 React/TypeScript 前端

## 1. 目标与基本原则

### 1.1 重构的核心定义
重构是在**不改变可观察行为**的前提下，改进代码内部结构的一系列小步改动。它应当是日常开发的一部分，而不是独立阶段。

参考：
- https://refactoring.com/

### 1.2 重构操作准则
- **小步可回滚**：每次改动尽量小，降低风险
- **持续验证**：每一步后运行测试或可验证的行为检查
- **行为保持**：重构只改变结构，不改变功能结果

## 2. 抽象的设计准则

### 2.1 抽象的目的
- 隐藏变化点，降低耦合
- 提升可读性与可替换性
- 建立清晰的业务边界

### 2.2 何时抽象
- 重复逻辑明确且未来仍会重复
- 变化频率高的实现细节需要隔离
- 跨模块共享的业务规则需要统一

### 2.3 避免过度抽象
- 抽象层越多，认知成本越高
- 无明确需求支撑的“预留扩展”会增加维护负担
- 先解决真实问题，再引入抽象层

## 3. 后端重构与抽象实践（Python/FastAPI/SQLAlchemy）

### 3.1 模块职责边界（遵循仓库架构）
- **API 层**：请求/响应与参数校验
- **Schemas**：数据形态与显式转换
- **Models**：ORM 结构
- **Services**：业务规则与流程
- **Ingestion**：导入链路处理

### 3.2 风格与可维护性
- 遵循 PEP 8 与 PEP 257
- 命名清晰、格式一致、文档字符串完整

参考：
- https://peps.python.org/pep-0008/
- https://peps.python.org/pep-0257/

### 3.3 常见重构动作
- **函数过长** → Extract Method
- **类过大** → Extract Class / 拆分职责
- **条件逻辑复杂** → 提取决策逻辑为独立函数
- **共享规则散落** → 移入 services 统一管理
- **数据转换隐式** → 显式 schema 映射或 `model_validate(...)`

### 3.4 数据与类型安全
- 金融与数量使用 `Decimal`
- 时间保持 UTC 且时区明确
- 捕获具体异常并记录上下文，避免裸 `except`

## 4. 前端重构与抽象实践（React/TypeScript）

### 4.1 Hooks 与组件纯度
- Hooks **只在组件顶层调用**
- Hooks **只在函数组件或自定义 Hook 中调用**
- 渲染过程必须**纯**，副作用放入 `useEffect` 或事件处理器

参考：
- https://react.dev/reference/rules/rules-of-hooks
- https://react.dev/reference/rules/components-and-hooks-must-be-pure

### 4.2 TypeScript 严格性
- 保持 `strict: true`
- 遵循 `noImplicitAny`，避免隐式 `any`

参考：
- https://www.typescriptlang.org/tsconfig/strict.html
- https://www.typescriptlang.org/tsconfig/noImplicitAny.html

### 4.3 抽象粒度
- **页面级逻辑**放在 `pages/`
- **可复用逻辑**抽到 `components/` 或自定义 Hook
- **API 调用**集中在 `api/client.ts`，避免跨页面复制

## 5. 重构流程建议（可操作清单）

1. **确认行为**：先写/补测试或最小化可验证步骤
2. **识别痛点**：重复、分层混乱、不可读、难扩展
3. **小步重构**：一次只做一种结构变化
4. **持续验证**：每一步后运行测试
5. **收尾清理**：命名、注释、类型、文档字符串

## 6. 抽象质量检查清单

- [ ] 是否真正隔离了变化点
- [ ] 是否减少了重复逻辑
- [ ] 是否提升了可读性与维护性
- [ ] 是否引入了不必要的间接层
- [ ] 依赖方向是否清晰
- [ ] 新成员是否能快速理解

## 7. 参考资料

- https://refactoring.com/
- https://peps.python.org/pep-0008/
- https://peps.python.org/pep-0257/
- https://react.dev/reference/rules/rules-of-hooks
- https://react.dev/reference/rules/components-and-hooks-must-be-pure
- https://www.typescriptlang.org/tsconfig/strict.html
- https://www.typescriptlang.org/tsconfig/noImplicitAny.html
