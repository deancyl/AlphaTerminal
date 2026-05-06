# AlphaTerminal — AI 开发上下文索引

> 本文件是 AlphaTerminal 的**高密度知识索引**，包含开发所需的核心架构信息。
> 不包含历史审计记录 — 那些归档在 `docs/archive/`。
> 每次开发任务优先阅读本文件 + `README.md`。

---

## 1. 项目概览

| 字段 | 值 |
|------|-----|
| **版本** | v0.6.10 (master 分支) |
| **GitHub** | https://github.com/deancyl/AlphaTerminal |
| **架构** | 前后端分离 (FastAPI + Vue 3 + SQLite) |
| **工作目录** | `/vol3/@apphome/trim.openclaw/data/workspace/AlphaTerminal` |
| **核心目标** | K线模块完善、子账户系统、数据源熔断容错 |

### 技术栈

```
Backend:  Python 3.11 + FastAPI + SQLite (WAL模式) + Uvicorn
Frontend: Vue 3 + Pinia + ECharts + Vite + Tailwind CSS
Database: SQLite (database.db)，路径在工作区根目录
数据源:   Sina/腾讯/东方财富 (抓取) + Alpha Vantage (历史K线)
代理:     http://192.168.1.50:7897 (已配置 Git/npm/http)
```

---

## 2. 系统架构

```
┌─────────────────────────────────────────────────────┐
│                    Vue 3 Frontend                    │
│  Pinia Stores (market.js, drawing.js)               │
│  ECharts K线渲染 + 40+ 组件 (components/)           │
└────────────────────┬────────────────────────────────┘
                     │ HTTP / WebSocket
              ┌──────▼──────────────────┐
              │   FastAPI Backend        │
              │   /api/v1/*  (REST)     │
              │   /ws/market/* (WS)     │
              └──────┬──────────────────┘
                     │
    ┌────────────────┼────────────────┐
    ▼                ▼                ▼
market_data      portfolios        admin_config
(realtime/daily   子账户/持仓       系统配置
 /periodic)                            │
                                   ┌───▼────┐
                                  SQLite DB  │
                             (database.db)   │
                                  └──────────┘
```

### 目录结构

```
AlphaTerminal/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口，注册所有 router
│   │   ├── config/               # 配置
│   │   ├── routers/              # API 路由
│   │   │   ├── market.py         # /api/v1/market — 行情
│   │   │   ├── portfolio.py      # /api/v1/portfolio — 子账户/持仓
│   │   │   ├── admin.py          # /api/v1/admin — 系统管理
│   │   │   ├── admin_source.py   # /api/v1/admin/admin_source — 数据源管理
│   │   │   ├── copilot.py        # /api/v1/copilot — AI 副驾驶
│   │   │   ├── bond.py/fund.py/futures.py/stocks.py  # 各类品种
│   │   │   ├── sentiment.py/news.py  # 舆情/新闻
│   │   │   ├── backtest.py       # 回测
│   │   │   ├── websocket.py      # WebSocket 实时行情
│   │   │   └── debug.py          # 调试路由（兜底）
│   │   ├── services/
│   │   │   ├── scheduler.py      # 定时任务调度
│   │   │   ├── logging_queue.py  # 日志队列
│   │   │   ├── db_writer.py      # 异步数据库写入
│   │   │   ├── circuit_breaker.py # 熔断器
│   │   │   ├── fetcher_factory.py # 数据源工厂 (Sina/Tencent/Eastmoney)
│   │   │   └── market.py         # 市场数据获取服务
│   │   ├── db/
│   │   │   └── database.py       # SQLite 连接/表初始化
│   │   └── utils/
│   │       └── market_status.py   # 市场状态判断
│   ├── requirements.txt
│   └── start_backend.py
├── frontend/
│   ├── src/
│   │   ├── App.vue
│   │   ├── stores/
│   │   │   ├── market.js         # Pinia market store (currentSymbol, quoteCache)
│   │   │   └── drawing.js        # 绘图状态
│   │   ├── utils/
│   │   │   └── symbols.js        # 符号规范化 (normalizeSymbol)
│   │   └── components/            # 40+ Vue 组件
│   │       ├── BaseKLineChart.vue     # 基础K线
│   │       ├── AdvancedKlinePanel.vue  # 高级K线面板
│   │       ├── PortfolioDashboard.vue  # 组合仪表盘
│   │       ├── AdminDashboard.vue     # 管理面板
│   │       ├── StockScreener.vue      # 个股筛选器
│   │       └── ... (40+ components)
│   └── package.json
├── docs/
│   ├── archive/                  # 历史文件（不主动读取）
│   ├── WIKI_ARCHITECTURE.md      # 核心模块技术维基
│   ├── PRD-SPEC-v0.4-KLINE-MODULE.md  # K线模块实施规范
│   ├── DATA_SOURCE_ABSTRACTION.md # 数据源抽象层设计
│   ├── QUICKSTART.md             # 快速启动
│   ├── ALPHA_VANTAGE_GUIDE.md    # Alpha Vantage 使用指南
│   ├── HISTORICAL_DATA_GUIDE.md  # 历史数据获取指南
│   ├── deployment_guide.md       # 部署指南
│   └── agents/                   # Agent 系统
│       ├── ORCHESTRATOR.md
│       ├── AUDITOR.md
│       ├── CODER.md
│       └── VERIFIER.md
├── AI_CONTEXT.md                 # 本文件
├── README.md                     # 项目入口
└── KNOWN_ISSUES_TODO.md         # 当前路线图/待办
```

---

## 3. SQLite Schema

所有表定义在 `backend/app/db/database.py`。DB 路径：`AlphaTerminal/database.db`（支持 WAL 模式，网络挂载时自动降级为 DELETE journal）。

### 核心表

```sql
-- 实时行情缓存（内存级，TTL 内刷新）
market_data_realtime(
  symbol TEXT PK, name, price REAL, change_pct REAL,
  volume REAL, market TEXT, data_type TEXT, timestamp INTEGER
)

-- 日K线历史（主数据）
market_data_daily(
  id INT PK AUTOINCREMENT,
  symbol, date UNIQUE(symbol,date),
  open, high, low, close, volume,
  amount, turnover_rate, amplitude,
  timestamp, data_type DEFAULT 'daily'
)

-- 周期K线（周线/月线/季线）
market_data_periodic(
  symbol, date, period,
  UNIQUE(symbol,date,period),
  open, high, low, close, volume, change_pct, timestamp
)

-- 组合/子账户
portfolios(
  id INT PK, name UNIQUE, type DEFAULT 'main',
  created_at, total_cost DEFAULT 0.0
)

-- 持仓
positions(
  id INT PK, portfolio_id FK→portfolios,
  symbol, shares DEFAULT 0, avg_cost DEFAULT 0.0,
  updated_at, UNIQUE(portfolio_id,symbol)
)

-- 组合快照
portfolio_snapshots(
  id INT PK, portfolio_id FK→portfolios,
  date, total_asset DEFAULT 0.0, total_cost DEFAULT 0.0,
  UNIQUE(portfolio_id,date)
)

-- 系统配置
admin_config(key TEXT PK, value TEXT, updated_at)

-- 全市场个股缓存
market_all_stocks(
  symbol PK, code, name, price, change_pct,
  per, pb, mktcap, nmc, volume, amount,
  turnover, price_high, price_low, open_price, updated_at
)

-- 写入缓冲（异步批量写入）
write_buffer(symbol, name, data TEXT)
```

### 索引

```sql
idx_daily_sym       ON market_data_daily(symbol)
idx_periodic_sym_p  ON market_data_periodic(symbol, period)
idx_pos_port        ON positions(portfolio_id)
idx_snap_port       ON portfolio_snapshots(portfolio_id)
```

---

## 4. FastAPI 路由规范

所有 REST 路由前缀 `/api/v1`，WebSocket 独立路径 `/ws/market/{symbol}`。

### 路由模块

| 路由文件 | 路径前缀 | 主要功能 |
|---------|---------|---------|
| `market.py` | `/api/v1/market` | 实时行情/历史K线/分页 |
| `admin.py` | `/api/v1/admin` | 系统指标/日志/配置/缓存 |
| `admin_source.py` | `/api/v1/admin` | 数据源健康检查/熔断/切换 |
| `portfolio.py` | `/api/v1/portfolio` | 子账户 CRUD/持仓/快照 |
| `stocks.py` | `/api/v1/stocks` | 个股列表/筛选 |
| `copilot.py` | `/api/v1/copilot` | AI 助手 |
| `sentiment.py` | `/api/v1/sentiment` | 舆情 |
| `news.py` | `/api/v1/news` | 新闻 |
| `bond.py` | `/api/v1/bond` | 债券 |
| `fund.py` | `/api/v1/fund` | 基金 |
| `futures.py` | `/api/v1/futures` | 期货 |
| `backtest.py` | `/api/v1/backtest` | 回测 |
| `websocket.py` | `/ws/market/{symbol}` | 实时行情 WebSocket |
| `debug.py` | `/api/v1/debug` | 调试（兜底路由） |

### 关键 API

```python
# admin 数据源管理
GET  /api/v1/admin/data-sources/status          # 各数据源健康状态
POST /api/v1/admin/data-sources/switch/{name}  # 切换数据源
POST /api/v1/admin/data-sources/health-check    # 触发健康检查
POST /api/v1/admin/data-sources/reset/{name}    # 重置熔断状态

# admin 系统
GET  /api/v1/system/metrics                    # 系统指标
GET  /api/v1/cache/status                       # 缓存状态
POST /api/v1/cache/invalidate                   # 清空缓存
GET  /api/v1/database/status                    # DB 状态
GET  /api/v1/logs/recent                        # 最近日志
GET  /config                                    # 获取配置
POST /config/{key}                              # 更新配置

# portfolio (子账户系统)
GET  /api/v1/strategies                         # 策略列表
POST /api/v1/strategies                         # 创建策略
POST /api/v1/run                                # 运行策略
```

---

## 5. 前端核心

### Pinia Stores

```javascript
// stores/market.js
useMarketStore: {
  state: {
    currentSymbol,     // 当前标的符号 (e.g. 'sh000001')
    currentSymbolName,// 名称
    currentColor,     // 颜色
    currentMarket,   // 'AShare' | 'US' | 'HK' | 'JP'
    symbolRegistry,   // 搜索索引
    quoteCache,      // 行情缓存 {symbol: quote}
  },
  methods: setSymbol(symbol, name, color, market)
}

// stores/drawing.js — 绘图工具状态
```

### 符号规范

```
上证指数: sh000001 (normalizeSymbol → 'sh000001')
沪深300:  sh000300
科创50:   sh000688
纳斯达克: usNDX
恒生:     hkHSI
```

### 关键组件

```
BaseKLineChart.vue      — K线核心渲染（ECharts）
AdvancedKlinePanel.vue  — 高级K线面板
PortfolioDashboard.vue   — 组合仪表盘
AdminDashboard.vue      — 管理面板
StockScreener.vue       — 个股筛选（后端过滤+分页）
CopilotSidebar.vue      — AI 副驾驶侧边栏
```

---

## 6. 数据源与熔断机制

### 数据源

| 来源 | 类型 | 用途 |
|------|------|------|
| Sina (hq.sinajs.cn) | 实时行情 | 主要行情源 |
| 腾讯 | 备用行情 | 熔断切换 |
| 东方财富 | 辅助 | 扩展数据 |
| Alpha Vantage | 历史K线 | 补充历史数据 |

### 熔断器 (circuit_breaker.py)

```python
class CircuitBreaker:
  # 状态: CLOSED(正常) → OPEN(熔断) → HALF_OPEN(试探)
  # 触发条件: 连续 N 次失败
  # 自动恢复: N 秒后尝试半开
```

### 数据源工厂 (fetcher_factory.py)

```python
FetcherFactory.get_fetcher("sina")  # 主数据源
FetcherFactory.get_fetcher("tencent")  # 备用
FetcherFactory.get_fetcher("eastmoney") # 第三选择
```

---

## 7. 当前开发主线 (v0.5.142+)

### 优先级 1：K 线模块完善
- 参照 `docs/PRD-SPEC-v0.4-KLINE-MODULE.md`
- 多周期切换（日/周/月/季/年）
- 高级绘图工具（趋势线/斐波那契）

### 优先级 2：子账户系统
- 已有 `portfolios` / `positions` / `portfolio_snapshots` 表
- 需要完善 CRUD API (`portfolio.py`)
- 需要前端 `PortfolioDashboard.vue` 对接

### 优先级 3：数据源熔断与容错
- 参照 `docs/DATA_SOURCE_ABSTRACTION.md`
- `admin_source.py` 已有基础框架
- 需要完善健康检查 → 熔断 → 自动切换流程

---

## 8. 开发备忘

### 常用命令

```bash
# 启动后端
cd backend && python3 start_backend.py

# 安装依赖
pip3 install -r backend/requirements.txt

# 前端开发
cd frontend && npm install && npm run dev

# Git 操作（已配置代理）
git clone --depth=1 https://github.com/deancyl/AlphaTerminal.git

# 数据库路径
AlphaTerminal/database.db
```

---

## 9. Target Architecture Vision（目标架构蓝图）

> 本章节是 AlphaTerminal 系统设计的**最高指导原则**。
> 所有技术决策必须与本章描述的方向一致。

---

### 9.1 核心理念

AlphaTerminal 的终极目标是成为**完全免费、可扩展的在线金融投研终端**，
在不依赖重型本地硬件的前提下，通过云端 API 与多模型协同，实现专业级投研能力。

---

### 9.2 三层核心架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        表现层 (Vue 3 + ECharts)                  │
│         40+ 组件、K线图表、组合仪表盘、舆情面板                    │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                    AI 编排层 (Multi-Agent)                        │
│                                                                  │
│  ┌──────────┐  ┌────────────────┐  ┌─────────────────────────┐  │
│  │协调者 Agent│  │ 技术分析 Agent │  │  基本面分析 Agent        │  │
│  │(Orchestrator)│ │(Technical)   │  │(Fundamental)          │  │
│  └──────────┘  └────────────────┘  └─────────────────────────┘  │
│                                                                  │
│  ┌──────────────────┐  ┌───────────────────────────────────┐   │
│  │ 动态模型路由      │  │ 配额 & 熔断管理                    │   │
│  │(Dynamic Model    │  │(CircuitBreaker + QuotaMonitor)    │   │
│  │ Model Router)    │  │                                    │   │
│  └──────────────────┘  └───────────────────────────────────┘   │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                   数据源插件层 (Plugin Layer)                     │
│                                                                  │
│  国内源（免费）：          海外源（免费）：      补充源：           │
│  ─────────────────        ────────────────      ─────────────   │
│  • Sina (hq.sinajs.cn)   • Alpha Vantage       • Twelve Data   │
│  • 腾讯 (qt.gtimg.cn)    • Finnhub             • Yahoo Finance │
│  • 东方财富              • Alpha Vantage FX    • FRED/Macro   │
│  • 网易财经              • Polygon.io          • ...扩展至20+  │
│                                                                  │
│  每一数据源 = 一个插件Fetcher，遵循 BaseMarketFetcher 接口        │
│  插件注册 → 健康检查 → 熔断 → 自动故障转移（Failover）           │
└─────────────────────────────────────────────────────────────────┘
```

---

### 9.3 数据源插件体系

**目标：支持 20+ 独立数据源插件，零硬编码依赖**

| 插件 | 用途 | 熔断策略 |
|------|------|---------|
| SinaFetcher | A股实时行情 | 连续5次失败 OPEN |
| TencentFetcher | A股备用 | 同上 |
| EastmoneyFetcher | 扩展数据 | 同上 |
| AlphavantageFetcher | 美股/FX/历史K线 | 限速：5req/min，25req/day |
| FinnhubFetcher | 美股报价/新闻 | 限速：60req/min |
| TwelveDataFetcher | 多资产综合 | 限速：800req/day |
| ... | ... | ... |

**熔断状态机**：
```
CLOSED ─[连续5次失败]→ OPEN ─[30s后]→ HALF_OPEN ─[成功2次]→ CLOSED
                         ↑                    │
                         └────[失败]──────────┘
```

---

### 9.4 AI 多智能体协作

```
用户请求
    │
    ▼
┌─────────────────────┐
│   协调者 Agent       │ ← 意图分类 / 任务分解
│ (Orchestrator)      │
└──────────┬──────────┘
           │ 路由
    ┌──────┼──────────────────┐
    ▼      ▼                   ▼
┌─────────────┐  ┌──────────────┐  ┌────────────────┐
│技术分析Agent│  │基本面分析Agent│  │  风控 Agent    │
│(Technical) │  │(Fundamental) │  │ (Risk)        │
└──────┬─────┘  └──────┬───────┘  └───────┬────────┘
       │                │                   │
       ▼                ▼                   ▼
  K线/指标            财报/估值          仓位/VaR
  趋势判断            估值区间           风险提示
```

---

### 9.5 动态模型路由（Dynamic Model Routing）

**核心思想：根据任务特性，动态选择最适合的云端模型**

| 任务类型 | 推荐模型 | 原因 |
|---------|---------|------|
| **极速渲染**（K线标注、指标计算） | Groq / Claude-mini | 低延迟 < 500ms |
| **深度推理**（投资逻辑、策略评估） | DeepSeek V3 | 强推理能力 |
| **长文本解析**（财报分析、年报摘要） | Zhipu / Claude Sonnet | 128K+ 上下文 |
| **代码生成**（指标公式、回测脚本） | Claude Sonnet 4 | 代码质量最高 |

**路由策略**：
```python
def route_model(task: str) -> str:
    if is_long_text_task(task):    return "zhipu"
    elif is_code_generation(task): return "claude-sonnet"
    elif is_realtime_render(task): return "groq"
    else:                          return "deepseek"
```

---

### 9.6 配额与限流管理

```
每数据源独立配额计数器（存入 admin_config 表）：

AlphaVantage:  25 req/day  → 配额耗尽 → 自动切换 TwelveData
Finnhub:       60 req/min → 触发限流 → 退避 60s
TwelveData:    800 req/day → 配额预警 → 降级至免费层
```

---

### 9.7 当前开发阶段 vs 目标架构

| 组件 | 当前状态 | 目标状态 |
|------|---------|---------|
| 数据源 | Sina/Tencent/Alphavantage 插件 | 20+ 插件 + 自动 failover |
| 熔断器 | CircuitBreaker (CLOSED/OPEN/HALF_OPEN) | 配额感知 + 多源协调熔断 |
| HTTP Client | ValidatedHTTPClient (retry + CB) | 全局 proxy + 统一 retry 策略 |
| 数据校验 | QuoteData / KlineData Pydantic Schema | 所有数据源统一 Schema |
| AI Agent | CopilotSidebar (单 Agent) | Orchestrator + 3+ 专业 Agent |
| 模型路由 | MiniMax CN (单一) | Groq / DeepSeek / Zhipu 动态切换 |

---

### 9.8 技术债务预警

| 债项 | 风险 | 计划 |
|------|------|------|
| AlphaVantage API Key 明文 | 泄露风险 | 迁移至 .env + gitignore |
| 子账户系统 CRUD 不完整 | 功能缺失 | v0.6.x 完成 |
| AkShare 债券数据停更 | 数据不准确 | 切换至东方财富债券接口 |
| 前端无 E2E 测试 | 回归风险 | Playwright 已装（devDependency）|
| SQLite WAL 不支持网络盘 | 数据损坏 | 已在 database.py 降级为 DELETE journal |
