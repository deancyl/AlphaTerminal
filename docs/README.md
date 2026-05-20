# AlphaTerminal 文档目录

> 最后更新: 2026-05-20  
> 当前版本: v0.6.58  
> 开发计划: [todo0429.md](../todo0429.md) - v0.6.x路线图

## 📁 文档结构

```
docs/
├── README.md                    # 本文档 - 文档导航
├── API_GUIDE.md                 # API 文档
├── DEV_SETUP.md                 # 开发环境搭建指南
├── TESTING_GUIDE.md             # 测试编写指南
├── E2E_TEST_PLAN.md             # E2E 测试计划 ⭐ NEW
├── E2E_DEPENDENCIES.md          # E2E 依赖环境指南 ⭐ NEW
├── AUTO_DIAGNOSIS_WORKFLOW.md   # 自动化诊断工作流 ⭐
├── KNOWN_ISSUES_TODO.md         # 已知问题和待办
├── todo0429.md                  # v0.6.x 开发计划 ⭐
├── guides/                      # 使用指南
│   ├── QUICKSTART.md           # 快速开始
│   ├── deployment_guide.md     # 部署指南
│   ├── WIKI_ARCHITECTURE.md    # 架构设计文档
│   ├── DATA_SOURCE_ABSTRACTION.md # 数据源抽象
│   ├── HISTORICAL_DATA_GUIDE.md # 历史数据指南
│   ├── ALPHA_VANTAGE_GUIDE.md  # AlphaVantage 指南
│   └── PRD-SPEC-v0.4-KLINE-MODULE.md # K线模块PRD
├── tests/                       # 测试文档 ⭐ NEW
│   └── COPILOT_TEST_COVERAGE.md # Copilot 测试覆盖 (63 tests)
├── reports/                     # 报告文档
│   └── PERFORMANCE_REPORT.md   # 性能优化报告
├── archive/                     # 归档文档（历史版本）
│   ├── DEV_PROGRESS_*.md       # 开发进度报告
│   ├── AUDIT_*.md              # 审计报告
│   └── ...                     # 其他历史文档
└── agents/                      # AI Agent 配置
    ├── README.md
    ├── CODER.md
    ├── AUDITOR.md
    ├── ORCHESTRATOR.md
    └── VERIFIER.md
```

## 📖 快速导航

### 开始使用
1. [QUICKSTART.md](guides/QUICKSTART.md) - 5分钟快速开始
2. [DEV_SETUP.md](DEV_SETUP.md) - 完整开发环境搭建
3. [API_GUIDE.md](API_GUIDE.md) - API 接口文档

### 开发指南
1. [TESTING_GUIDE.md](TESTING_GUIDE.md) - 如何编写测试
2. [E2E_TEST_PLAN.md](E2E_TEST_PLAN.md) - E2E 测试计划 ⭐ NEW
3. [E2E_DEPENDENCIES.md](E2E_DEPENDENCIES.md) - E2E 依赖环境指南 ⭐ NEW
4. [WIKI_ARCHITECTURE.md](guides/WIKI_ARCHITECTURE.md) - 系统架构
5. [DATA_SOURCE_ABSTRACTION.md](guides/DATA_SOURCE_ABSTRACTION.md) - 数据源设计

### 测试文档
1. [TESTING_GUIDE.md](TESTING_GUIDE.md) - 测试编写指南
2. [COPILOT_TEST_COVERAGE.md](tests/COPILOT_TEST_COVERAGE.md) - Copilot 测试覆盖 (63 tests) ⭐ NEW
3. [E2E_TEST_PLAN.md](E2E_TEST_PLAN.md) - E2E 测试计划

### 部署运维
1. [deployment_guide.md](guides/deployment_guide.md) - 生产部署
2. [PERFORMANCE_REPORT.md](reports/PERFORMANCE_REPORT.md) - 性能优化

### 运维工具
1. [AUTO_DIAGNOSIS_WORKFLOW.md](AUTO_DIAGNOSIS_WORKFLOW.md) - 自动化诊断工作流 ⭐
2. [../auto_diagnosis.sh](../auto_diagnosis.sh) - 自动化诊断脚本

### E2E 测试
1. [E2E_TEST_PLAN.md](E2E_TEST_PLAN.md) - 完整测试架构设计 (260+ 测试用例)
2. [E2E_DEPENDENCIES.md](E2E_DEPENDENCIES.md) - 依赖环境安装指南
3. [../scripts/setup-e2e.sh](../scripts/setup-e2e.sh) - 一键安装脚本
4. [../scripts/verify-e2e-env.sh](../scripts/verify-e2e-env.sh) - 环境验证脚本

## 🗂️ 归档说明

`archive/` 目录包含历史版本的文档，包括：
- 开发进度报告 (DEV_PROGRESS_*.md)
- 审计报告 (AUDIT_*.md)
- 旧版设计文档

这些文档保留用于历史参考，新项目请使用根目录和 guides/ 下的最新文档。
