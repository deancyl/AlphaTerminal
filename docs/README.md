# AlphaTerminal 文档目录

> 最后更新: 2026-05-12  
> 当前版本: v0.6.30  
> 开发计划: 见 [PRD_DEVELOPMENT_PLAN.md](planning/PRD_DEVELOPMENT_PLAN.md)

---

## 📁 文档结构

```
docs/
├── README.md                    # 本文档 - 文档导航
├── API_GUIDE.md                 # API 文档
├── DEV_SETUP.md                 # 开发环境搭建指南
├── TESTING_GUIDE.md             # 测试编写指南
├── KNOWN_ISSUES_TODO.md         # 已知问题和待办 ⭐
│
├── guides/                      # 使用指南
│   ├── QUICKSTART.md           # 快速开始
│   ├── deployment_guide.md     # 部署指南
│   ├── WIKI_ARCHITECTURE.md    # 架构设计文档
│   ├── DATA_SOURCE_ABSTRACTION.md # 数据源抽象
│   ├── HISTORICAL_DATA_GUIDE.md # 历史数据指南
│   ├── ALPHA_VANTAGE_GUIDE.md  # AlphaVantage 指南
│   └── PRD-SPEC-v0.4-KLINE-MODULE.md # K线模块PRD
│
├── architecture/                # 架构文档
│   ├── HIGH_AVAILABILITY_ARCHITECTURE.md # 高可用架构
│   ├── GAP_ANALYSIS.md         # 功能差距分析
│   ├── COORDINATION_ANALYSIS.md # 前后端协调分析
│   └── PROFESSIONAL_FEATURE_GAP_ANALYSIS.md # 专业功能差距
│
├── planning/                    # 规划文档
│   ├── PRD_DEVELOPMENT_PLAN.md # 产品开发计划
│   ├── IMPLEMENTATION_ROADMAP.md # 实施路线图
│   └── WEEK1_2_GUIDE.md        # Week 1-2 开发指南
│
├── releases/                    # 发布记录
│   └── RELEASE_v0.6.12.md      # v0.6.12 发布说明
│
├── agents/                      # AI Agent 配置
│   ├── README.md
│   ├── CODER.md
│   ├── AUDITOR.md
│   ├── ORCHESTRATOR.md
│   └── VERIFIER.md
│
├── reports/                     # 报告文档
│   ├── PERFORMANCE_REPORT.md   # 性能优化报告
│   └── heartbeat-reports/      # 心跳检测报告
│
└── archive/                     # 归档文档（历史版本）
    ├── audits/                  # 审计报告
    ├── quantdinger/             # QuantDinger 集成记录
    ├── completed/               # 已完成任务记录
    ├── deprecated/              # 过期文档
    └── experience/              # 开发经验记录
```

---

## 📖 快速导航

### 开始使用
| 文档 | 说明 |
|------|------|
| [QUICKSTART.md](guides/QUICKSTART.md) | 5分钟快速开始 |
| [DEV_SETUP.md](DEV_SETUP.md) | 完整开发环境搭建 |
| [API_GUIDE.md](API_GUIDE.md) | API 接口文档 |

### 开发指南
| 文档 | 说明 |
|------|------|
| [TESTING_GUIDE.md](TESTING_GUIDE.md) | 如何编写测试 |
| [WIKI_ARCHITECTURE.md](guides/WIKI_ARCHITECTURE.md) | 系统架构 |
| [DATA_SOURCE_ABSTRACTION.md](guides/DATA_SOURCE_ABSTRACTION.md) | 数据源设计 |

### 架构设计
| 文档 | 说明 |
|------|------|
| [HIGH_AVAILABILITY_ARCHITECTURE.md](architecture/HIGH_AVAILABILITY_ARCHITECTURE.md) | 高可用架构设计 |
| [GAP_ANALYSIS.md](architecture/GAP_ANALYSIS.md) | 与专业平台差距分析 |
| [PROFESSIONAL_FEATURE_GAP_ANALYSIS.md](architecture/PROFESSIONAL_FEATURE_GAP_ANALYSIS.md) | 专业功能差距详细分析 |

### 规划路线
| 文档 | 说明 |
|------|------|
| [KNOWN_ISSUES_TODO.md](KNOWN_ISSUES_TODO.md) | 当前待办和路线图 ⭐ |
| [IMPLEMENTATION_ROADMAP.md](planning/IMPLEMENTATION_ROADMAP.md) | 实施路线图 |
| [PRD_DEVELOPMENT_PLAN.md](planning/PRD_DEVELOPMENT_PLAN.md) | 产品开发计划 |

### 部署运维
| 文档 | 说明 |
|------|------|
| [deployment_guide.md](guides/deployment_guide.md) | 生产部署指南 |
| [PERFORMANCE_REPORT.md](reports/PERFORMANCE_REPORT.md) | 性能优化报告 |

---

## 🗂️ 归档说明

`archive/` 目录包含历史版本的文档，按类别组织：

| 子目录 | 内容 |
|--------|------|
| `audits/` | 各版本审计报告 (AUDIT_*.md) |
| `quantdinger/` | QuantDinger 集成历史记录 |
| `completed/` | 已完成的功能开发记录 |
| `deprecated/` | 过期的开发计划和 wishlist |
| `experience/` | 开发经验记录 |

这些文档保留用于历史参考，新项目请使用上述最新文档。

---

## 🔗 根目录核心文件

| 文件 | 说明 |
|------|------|
| [README.md](../README.md) | 项目主入口文档 |
| [CHANGELOG.md](../CHANGELOG.md) | 版本变更记录 |
| [AGENTS.md](../AGENTS.md) | AI Agent 开发指南 |
| [AI_CONTEXT.md](../AI_CONTEXT.md) | AI 开发上下文索引 |

---

## 🚀 脚本文件

| 文件 | 说明 |
|------|------|
| `start-services.sh` | 一键启动脚本（推荐） |
| `start.sh` | 详细启动脚本 |
| `start.ps1` | Windows 启动脚本 |
| `scripts/init_env.sh` | 环境初始化脚本 |
| `scripts/init_alphaterminal.sh` | AlphaTerminal 初始化 |

过期脚本已移至 `scripts/archive/`。