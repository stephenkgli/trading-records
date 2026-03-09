# Changelog

本文件记录项目的所有显著变更，格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Added
- MIT 开源许可证
- 完善 README.md（功能描述、技术栈、项目结构、测试说明）
- pyproject.toml 和 package.json 项目元数据补全
- 后端代码质量工具链（ruff lint/format、mypy 类型检查）
- 前端代码质量工具链（ESLint、Prettier）
- Pre-commit hooks 配置
- 安全响应头中间件（X-Content-Type-Options、X-Frame-Options、X-XSS-Protection、Referrer-Policy）
- 前端测试基础设施（Vitest + React Testing Library）
- API client 层单元测试（13 个测试用例）
- 后端测试覆盖率配置与 70% 最低门槛
- CHANGELOG.md
- Docker 安全加固（非 root 用户、HEALTHCHECK）
- Makefile 开发工具入口

### Changed
- CORS 中间件收紧：`allow_methods` 和 `allow_headers` 从 `["*"]` 改为具体列表
- 19 处 bare `except Exception` 替换为具体异常类型

## [0.1.0] - 2026-03-09

### Added
- 初始版本
- IBKR 和 Tradovate CSV 交易导入
- 导入管线（解析 → 标准化 → 校验 → 去重 → 入库）
- FIFO 交易分组
- 分析看板（P&L 日历、权益曲线、品种分布）
- 行情数据集成（Databento / Tiingo）
- K 线图表与交易标记
- Docker 部署支持
