# QuantDinger & awesome-quant 深度整合报告

> 分析日期: 2026-05-07  
> 当前版本: v0.6.11  
> 状态: ✅ 深度审计完成  
> 仓库: https://github.com/deancyl/AlphaTerminal

---

## 目录

1. [项目审计](#1-项目审计)
   - [1.1 QuantDinger 深度审计](#11-quantdinger-深度审计)
   - [1.2 awesome-quant 资源索引](#12-awesome-quant-资源索引)
   - [1.3 AlphaTerminal 当前状态](#13-alphaterminal-当前状态)
2. [功能对比矩阵](#2-功能对比矩阵)
3. [技术整合路线图](#3-技术整合路线图)
   - [3.1 AI Agent & MCP 整合](#31-ai-agent--mcp-整合)
   - [3.2 数据源整合](#32-数据源整合)
   - [3.3 回测引擎整合](#33-回测引擎整合)
   - [3.4 策略框架整合](#34-策略框架整合)
   - [3.5 UI/UX 整合](#35-ux-整合)
   - [3.6 安全机制整合](#36-安全机制整合)
4. [实施计划](#4-实施计划)
5. [参考资源](#5-参考资源)

---

## 1. 项目审计

### 1.1 QuantDinger 深度审计

**GitHub**: https://github.com/brokermr810/QuantDinger  
**版本**: v3.0.3  
**定位**: 自托管量化交易操作系统 (Private AI Quant OS)

#### 1.1.1 技术栈

```
Frontend:  Vue.js (预构建静态文件, 私有前端仓库)
Backend:   Flask (Python 3.10+)
Database:  PostgreSQL 15
Cache:     Redis 7
Proxy:     Nginx
Deploy:    Docker Compose
ML:       LLM (OpenAI/Anthropic)
```

#### 1.1.2 后端架构 (backend_api_python/app/)

**Routes (19 个路由文件, 总计约 800KB)**:

| 路由文件 | 大小 | 功能 |
|----------|------|------|
| `auth.py` | 47KB | 认证授权、JWT、OAuth |
| `user.py` | 74KB | 用户管理、订阅、计费 |
| `strategy.py` | 84KB | 策略 CRUD、版本管理 |
| `quick_trade.py` | 71KB | 快捷交易引擎 |
| `trading_executor.py` | 182KB | 订单执行引擎 |
| `indicator.py` | 55KB | 技术指标计算 |
| `backtest.py` | 40KB | 回测引擎 |
| `portfolio.py` | 42KB | 组合管理 |
| `market.py` | 22KB | 市场数据 |
| `kline.py` | 3KB | K线数据 |
| `dashboard.py` | 29KB | 仪表板数据 |
| `fast_analysis.py` | 24KB | 快速分析 (AI) |
| `ai_chat.py` | 1KB | AI 对话 |
| `ibkr.py` | 10KB | IBKR 券商接口 |
| `mt5.py` | 12KB | MT5 外汇接口 |
| `billing.py` | 3KB | 计费系统 |
| `community.py` | 15KB | 社区功能 |
| `experiment.py` | 6KB | 实验编排 (AI) |
| `polymarket.py` | 11KB | Polymarket 预测市场 |

**Services (33 个服务文件, 总计约 1.5MB)**:

| 服务文件 | 大小 | 功能 |
|----------|------|------|
| `trading_executor.py` | 182KB | 核心交易执行引擎 |
| `pending_order_worker.py` | 133KB | 挂单处理 |
| `portfolio_monitor.py` | 81KB | 组合监控 |
| `fast_analysis.py` | 131KB | AI 快速分析 |
| `llm.py` | 27KB | LLM 接口封装 |
| `strategy.py` | 71KB | 策略服务 |
| `strategy_compiler.py` | 29KB | 策略编译 |
| `market_data_collector.py` | 99KB | 市场数据采集 |
| `security_service.py` | 15KB | 安全服务 |
| `oauth_service.py` | 29KB | OAuth 服务 |
| `email_service.py` | 14KB | 邮件通知 |
| `signal_notifier.py` | 36KB | 信号通知 |
| `builtin_indicators.py` | 8KB | 内置指标 |
| `exchange_execution.py` | 4KB | 交易所执行 |

**Data Providers (12 个数据提供者)**:
- `adanos_sentiment.py` - 情绪数据
- `crypto.py` - 加密货币
- `forex.py` - 外汇
- `commodities.py` - 大宗商品
- `indices.py` - 指数
- `news.py` - 新闻
- `heatmap.py` - 热力图
- `opportunities.py` - 机会发现

#### 1.1.3 AI Agent Gateway 架构 (核心亮点) ⭐

**文档**: `docs/agent/AGENT_ENVIRONMENT_DESIGN.md`, `docs/agent/AGENT_QUICKSTART.md`

**安全设计**:
- Agent Token 颁发和管理 (JWT)
- 细粒度权限控制 (R/W/B/N/C/T Scopes)
- 审计日志
- 交易 Token 默认 `paper_only=true`
- 限流 (rate_limit_per_min)

**Scope 权限矩阵**:

| Scope | 类名 | 默认 | 说明 |
|-------|------|------|------|
| `R` | Read | yes | 市场数据、策略、任务 |
| `W` | Workspace write | no | 创建/修改策略 |
| `B` | Backtest | no | 异步任务 |
| `N` | Notifications | no | 通知和副作用 |
| `C` | Credentials | no | admin 专用 |
| `T` | Trading | no | 交易/资金, 默认 paper-only |

**Agent API 端点**:

```bash
# 发行 Token
POST /api/agent/v1/admin/tokens

# 健康检查
GET /api/agent/v1/health

# 身份验证
GET /api/agent/v1/whoami

# 市场数据
GET /api/agent/v1/markets
GET /api/agent/v1/markets/{market}/symbols
GET /api/agent/v1/klines
GET /api/agent/v1/price

# 策略管理
GET /api/agent/v1/strategies
GET /api/agent/v1/strategies/{id}

# 回测
POST /api/agent/v1/backtests
GET /api/agent/v1/jobs/{id}
```

#### 1.1.4 MCP Server 实现 ⭐

**路径**: `mcp_server/`  
**PyPI**: `quantdinger-mcp`

**暴露的 MCP 工具**:

| 工具 | 类 | 功能 |
|------|-----|------|
| `whoami` | R | 检查调用 token |
| `list_markets` | R | 可访问市场 |
| `search_symbols` | R | 搜索标的 |
| `get_klines` | R | OHLCV 数据 |
| `get_price` | R | 最新价格 |
| `list_strategies` | R | 列出策略 |
| `get_strategy` | R | 获取策略详情 |
| `submit_backtest` | B | 提交回测 |
| `get_job` | R | 查询任务状态 |
| `regime_detect` | B | 市场状态检测 |
| `submit_structured_tune` | B | 提交参数调优 |

**MCP 配置示例**:

```json
{
  "mcpServers": {
    "quantdinger": {
      "command": "quantdinger-mcp",
      "env": {
        "QUANTDINGER_BASE_URL": "http://localhost:8888",
        "QUANTDINGER_AGENT_TOKEN": "qd_agent_xxxxx"
      }
    }
  }
}
```

#### 1.1.5 AI 交易系统架构 ⭐

**文档**: `docs/AI_TRADING_SYSTEM_PLAN_CN.md`

**目标架构**:
```
Market Regime Engine -> Strategy Generator -> Backtest Engine 
-> Strategy Scoring -> Strategy Evolution -> Best Strategy Output
```

**Phase 1 (当前)**:
- AI 识别市场状态
- 批量生成/接收策略候选
- 自动回测并评分
- 参数进化
- 输出最优策略供人工确认

**新增 API**:

```bash
# 市场状态识别
POST /api/experiment/regime/detect

# 完整实验管线
POST /api/experiment/pipeline/run
```

**Experiment 服务**:
- `regime.py` - 规则型市场状态识别
- `scoring.py` - 多因子评分
- `evolution.py` - 参数空间生成候选变体
- `runner.py` - 串联状态识别、批量回测、评分

#### 1.1.6 策略框架 ⭐

**文档**: `docs/STRATEGY_DEV_GUIDE_CN.md`

**两种策略模式**:

| 模式 | 用途 | 特点 |
|------|------|------|
| **IndicatorStrategy** | 指标/信号脚本 | df 计算, 布尔信号, 图表展示 |
| **ScriptStrategy** | 事件驱动脚本 | on_bar, ctx.position, ctx.buy/sell |

**IndicatorStrategy 示例**:

```python
# @name 均量金叉策略
# @description 均线金叉策略
# @param period 周期 20
# @strategy stopLossPct 2
# @strategy takeProfitPct 6

import pandas as pd

ma5 = df['close'].rolling(5).mean()
ma20 = df['close'].rolling(20).mean()

df['buy'] = (ma5 > ma20) & (ma5.shift(1) <= ma20.shift(1))
df['sell'] = (ma5 < ma20) & (ma5.shift(1) >= ma20.shift(1))

output = {
    'indicators': {'ma5': ma5, 'ma20': ma20},
    'signals': {'buy': df['buy'], 'sell': df['sell']}
}
```

#### 1.1.7 技术指标定义 ⭐

**文档**: `docs/INDICATOR_DEFINITIONS_CN.md`

| 指标 | 实现要点 |
|------|---------|
| **RSI(14)** | Wilder RSI, α=1/14 |
| **MACD(12,26,9)** | EMA12/26, DIF, DEA, 柱 |
| **MA5/10/20** | SMA |
| **布林(20,2)** | 中轨 SMA, 上下轨 ±2σ |
| **ATR(14)** | Wilder ATR, α=1/14 |
| **枢轴 Pivot** | R1/S1/R2/S2 |

#### 1.1.8 前端 Fast Analysis 对接

**文档**: `docs/FRONTEND_FAST_ANALYSIS.md`

**API 返回约定**:
```python
trading_plan = {
    "entryPrice": float,
    "stopLoss": float,      # 止损价
    "takeProfit": float,    # 止盈价
    "positionSizePct": float,
    "decision": "BUY" | "SELL"
}
```

#### 1.1.9 部署架构

**Docker Compose**:
```yaml
services:
  postgres:  image: postgres:15
  redis:     image: redis:7
  api:       build: ./backend_api_python
  nginx:      image: nginx
  frontend:  image: nginx (预构建 dist)
```

#### 1.1.10 核心文档列表

| 文档 | 内容 |
|------|------|
| `AI_TRADING_SYSTEM_PLAN_CN.md` | AI 完整交易系统改造方案 |
| `STRATEGY_DEV_GUIDE_CN.md` | Python 策略开发指南 |
| `INDICATOR_DEFINITIONS_CN.md` | 技术指标计算口径 |
| `AGENT_ENVIRONMENT_DESIGN.md` | 多 Agent 运行环境设计 |
| `AGENT_QUICKSTART.md` | Agent 快速入门 |
| `FRONTEND_FAST_ANALYSIS.md` | 前端快速分析对接 |
| `IBKR_TRADING_GUIDE_EN.md` | IBKR 交易指南 |
| `MT5_TRADING_GUIDE_CN.md` | MT5 外汇交易指南 |

---

### 1.2 awesome-quant 资源索引

**GitHub**: https://github.com/thuquant/awesome-quant

#### 1.2.1 数据源

| 资源 | 类型 | 价值评分 | AlphaTerminal 状态 |
|------|------|----------|-------------------|
| **AkShare** | 免费开源 | ⭐⭐⭐ | ✅ 已在用 |
| TuShare | 免费 | ⭐⭐ | ⚪ 备选 |
| pytdx | 通达信 | ⭐⭐ | ⚪ 未用 |
| JoinQuant SDK | 在线 | ⭐⭐ | ⚪ 备选 |
| zvt | 量化框架 | ⭐⭐ | ⚪ 未用 |
| fooltrader | 大数据 | ⭐⭐ | ⚪ 未用 |
| FXMacroData | 外汇宏观 | ⭐⭐ | ⚪ 未用 |
| **Adanos Sentiment** | 情绪 API | ⭐⭐⭐ | ⚪ 未用 |

#### 1.2.2 回测框架

| 框架 | 语言 | 特点 | 集成难度 |
|------|------|------|----------|
| **Zipline** | Python | 业界标准, 事件驱动 | ⭐⭐⭐ |
| **RQAlpha** | Python | RiceQuant 开源 | ⭐⭐⭐ |
| QuantConnect Lean | C#/Python | 多语言 | ⭐⭐⭐ |
| QUANTAXIS | Python | 国产量化框架 | ⭐⭐ |
| pyalgotrade | Python | 轻量级 | ⭐⭐ |
| finclaw | Python | AI 驱动, 遗传算法 | ⭐⭐ |

#### 1.2.3 技术指标库

| 库 | 用途 | 安装难度 |
|----|------|----------|
| **TA-Lib** | RSI, MACD, Bollinger | ⭐ (需编译) |
| **pandas-ta** | Pandas 原生 | ⭐ (纯 Python) |
| **ta** | 轻量级 | ⭐ (纯 Python) |
| **ffn** | 绩效评估 | ⭐ |
| **pyfolio** | 组合风险分析 | ⭐ |

#### 1.2.4 交易 API

| 资源 | 市场 | 集成价值 |
|------|------|----------|
| IB API | 股票/期权 | ⭐⭐⭐ |
| Futu Open API | 港股/美股 | ⭐⭐ |
| vnpy | 期货/期权 | ⭐⭐ |
| tqsdk | 期货/期权 | ⭐⭐ |

#### 1.2.5 数据库

| 数据库 | 类型 | 适用场景 |
|--------|------|----------|
| **TimescaleDB** | 时序 (PostgreSQL) | 中小规模量化 |
| Arctic | MongoDB 时序 | 高性能 tick |
| InfluxDB | 时序 | 监控场景 |
| kdb+ | 时序 | 超大规模 (收费) |

---

### 1.3 AlphaTerminal 当前状态

**GitHub**: https://github.com/deancyl/AlphaTerminal  
**当前版本**: v0.6.11

#### 1.3.1 技术栈

```
Frontend:  Vue 3 + ECharts + Vite
Backend:   FastAPI (Python 3.11+)
Database:  SQLite (WAL 模式)
Cache:     内存缓存 (SpotCache)
Data:      AkShare / 腾讯财经 / 新浪财经 / Eastmoney
LLM:       多 Provider (MiniMax, DeepSeek, OpenAI, Kimi 等)
```

#### 1.3.2 Backend Routers (17 个)

| 路由 | 大小 | 功能 |
|------|------|------|
| `portfolio.py` | 90KB | 组合管理 (核心) |
| `market.py` | 80KB | 市场数据 |
| `copilot.py` | 46KB | AI Copilot |
| `admin.py` | 25KB | 管理面板 |
| `backtest.py` | 21KB | 回测引擎 |
| `stocks.py` | 17KB | 股票数据 |
| `macro.py` | 27KB | 宏观数据 |
| `futures.py` | 14KB | 期货数据 |
| `bond.py` | 14KB | 债券数据 |
| `fund.py` | 9KB | 基金数据 |
| `sentiment.py` | 9KB | 市场情绪 |
| `news.py` | 7KB | 快讯新闻 |
| `export.py` | 16KB | 数据导出 |
| `websocket.py` | 2KB | WebSocket |
| `admin_source.py` | 4KB | 数据源管理 |
| `market_mock.py` | 2KB | Mock 数据 |

#### 1.3.3 Backend Services

| 服务 | 功能 |
|------|------|
| `sentiment_engine.py` | 情绪引擎 |
| `proxy_config.py` | 智能代理分流 |
| `data_validator.py` | 数据验证 |
| `scheduler.py` | 定时任务 |

#### 1.3.4 Frontend Components

**主要组件**:
- `AdminDashboard.vue` - 管理面板
- `AdvancedKlinePanel.vue` - K线面板
- `BacktestDashboard.vue` - 回测仪表板
- `BacktestChart.vue` - 回测图表
- `PortfolioDashboard.vue` - 组合仪表板
- `SentimentGauge.vue` - 情绪仪表
- `NewsFeed.vue` - 快讯
- `FundHoldings.vue` - 基金持仓
- `CommandCenter.vue` - 命令中心
- `CommandPalette.vue` - 命令面板

#### 1.3.5 已有功能

| 功能 | 状态 | 说明 |
|------|------|------|
| K线模块 | ✅ | 数据管道贯通 |
| 子账户系统 | ✅ | Phase 1-4 完成 |
| Copilot 对话 | ✅ | 多 Provider |
| 情绪/快讯 | ✅ | 实时数据 |
| 基金板块 | ✅ | Eastmoney 数据 |
| 回测框架 | ⚠️ | 基础功能 |
| 技术指标 | ⚠️ | 基础指标 |

#### 1.3.6 缺失功能

| 功能 | 优先级 | 说明 |
|------|--------|------|
| Agent Gateway | ⭐⭐⭐ | 无安全 Token 管理 |
| MCP Server | ⭐⭐⭐ | 无 MCP 协议支持 |
| 策略框架 | ⭐⭐⭐ | 无 Indicator/Script 策略 |
| 高级回测 | ⭐⭐ | 需增强绩效分析 |
| 实盘交易 | ⭐⭐ | 无券商接口 |
| 通知系统 | ⭐⭐ | 邮件/TG/短信 |
| 多用户 | ⭐⭐ | 需用户系统 |

---

## 2. 功能对比矩阵

| 功能模块 | QuantDinger | AlphaTerminal | 差距 | 整合优先级 |
|----------|-------------|---------------|------|-----------|
| **AI Agent** | | | | |
| Agent Gateway | ✅ 完整 | ❌ 无 | 大 | ⭐⭐⭐ |
| MCP Server | ✅ PyPI | ❌ 无 | 大 | ⭐⭐⭐ |
| Token 管理 | ✅ 完整 | ❌ 无 | 大 | ⭐⭐⭐ |
| 审计日志 | ✅ 完整 | ❌ 无 | 大 | ⭐⭐ |
| **策略框架** | | | | |
| IndicatorStrategy | ✅ 完整 | ❌ 无 | 大 | ⭐⭐⭐ |
| ScriptStrategy | ✅ 完整 | ❌ 无 | 大 | ⭐⭐ |
| 策略版本管理 | ✅ | ❌ 无 | 中 | ⭐⭐ |
| **回测引擎** | | | | |
| 事件驱动回测 | ✅ 完整 | ⚠️ 基础 | 中 | ⭐⭐ |
| 参数调优 | ✅ grid/random | ❌ 无 | 大 | ⭐⭐ |
| Walk-forward | ⚠️ Phase 2 | ❌ 无 | 大 | ⭐ |
| 绩效分析 | ✅ pyfolio | ⚠️ 基础 | 中 | ⭐⭐ |
| **数据源** | | | | |
| 多交易所 | ✅ IBKR/MT5/Binance | ⚠️ A股为主 | 中 | ⭐ |
| 情绪数据 | ✅ Adanos | ✅ 自有 | 小 | ⭐ |
| 技术指标 | ✅ 内置 50+ | ⚠️ 基础 | 中 | ⭐⭐ |
| **执行** | | | | |
| 快捷交易 | ✅ | ❌ 无 | 大 | ⭐ |
| 订单管理 | ✅ 完整 | ⚠️ 基础 | 中 | ⭐ |
| Paper Trading | ✅ | ❌ 无 | 大 | ⭐ |
| **UI/UX** | | | | |
| Fast Analysis | ✅ AI | ⚠️ Copilot | 中 | ⭐⭐ |
| 多用户支持 | ✅ | ❌ 无 | 大 | ⭐ |
| 通知系统 | ✅ 邮件/TG/短信 | ❌ 无 | 大 | ⭐ |

---

## 3. 技术整合路线图

### 3.1 AI Agent & MCP 整合

#### 3.1.1 为什么重要

QuantDinger 的 Agent Gateway 允许 AI Agent (Claude Code, Cursor) 直接调用量化系统，这是未来趋势。AlphaTerminal 目前只有简单的 Copilot，无法被 AI Agent 驱动。

#### 3.1.2 实现方案

**1. 创建 Agent Token 系统**

参考 `backend_api_python/app/routes/auth.py` 和 `backend_api_python/app/services/security_service.py`:

```python
# backend/app/services/agent_token.py

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import hashlib
import secrets

class TokenScope(Enum):
    READ = "R"           # 市场数据、策略、任务
    WRITE = "W"          # 创建/修改策略
    BACKTEST = "B"       # 异步任务
    NOTIFY = "N"         # 通知和副作用
    CREDENTIAL = "C"     # 凭证管理
    TRADE = "T"          # 交易/资金

@dataclass
class AgentToken:
    id: int
    name: str
    token_hash: str
    token_prefix: str     # 用于显示
    scopes: list[str]
    markets: list[str]
    instruments: list[str]
    paper_only: bool = True
    rate_limit: int = 120  # per minute
    expires_at: datetime
    created_at: datetime

class AgentTokenService:
    def __init__(self, db):
        self.db = db
    
    def create_token(
        self,
        name: str,
        scopes: list[str],
        markets: list[str] = None,
        instruments: list[str] = None,
        expires_in_days: int = 30,
        rate_limit: int = 120
    ) -> AgentToken:
        """创建新的 Agent Token"""
        raw_token = f"at_{secrets.token_hex(32)}"
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        
        token = AgentToken(
            id=self._next_id(),
            name=name,
            token_hash=token_hash,
            token_prefix=raw_token[:20],
            scopes=scopes,
            markets=markets or ["*"],
            instruments=instruments or ["*"],
            paper_only=True,  # 默认 paper-only
            rate_limit=rate_limit,
            expires_at=datetime.now() + timedelta(days=expires_in_days),
            created_at=datetime.now()
        )
        
        self._save(token)
        # 返回原始 token (只显示一次)
        return raw_token, token
    
    def verify_token(self, raw_token: str) -> AgentToken | None:
        """验证 Token"""
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        return self.db.get(token_hash=token_hash)
    
    def check_scope(self, token: AgentToken, required_scope: TokenScope) -> bool:
        """检查 Token 是否有权限"""
        return required_scope.value in token.scopes
```

**2. 创建 Agent Router**

```python
# backend/app/routers/agent.py

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/agent/v1", tags=["agent"])

class AgentTokenService:
    def __init__(self):
        self.tokens = {}
    
    async def verify(self, authorization: str = Header(...)) -> dict:
        if not authorization.startswith("Bearer "):
            raise HTTPException(401, "Invalid authorization header")
        token = authorization[7:]
        # verify logic...
        return {"scopes": ["R", "B"], "markets": ["Crypto"]}

agent_service = AgentTokenService()

# Market Data Endpoints
@router.get("/health")
async def health():
    return {"status": "ok"}

@router.get("/whoami")
async def whoami(token: dict = Depends(agent_service.verify)):
    return {
        "scopes": token["scopes"],
        "markets": token["markets"],
        "paper_only": True
    }

@router.get("/markets")
async def list_markets(token: dict = Depends(agent_service.verify)):
    if "R" not in token["scopes"]:
        raise HTTPException(403, "Insufficient scope")
    # 返回支持的市场列表
    return ["Crypto", "USStock", "Forex", "AStock"]

@router.get("/markets/{market}/symbols")
async def search_symbols(
    market: str,
    keyword: str = "",
    limit: int = 20,
    token: dict = Depends(agent_service.verify)
):
    # 搜索市场内的标的
    ...

@router.get("/klines")
async def get_klines(
    market: str,
    symbol: str,
    timeframe: str = "1D",
    limit: int = 100,
    token: dict = Depends(agent_service.verify)
):
    # 获取 K 线数据
    ...

# Backtest Endpoints
@router.post("/backtests")
async def submit_backtest(
    strategy_code: str,
    market: str,
    symbol: str,
    timeframe: str,
    start_date: str,
    end_date: str,
    token: dict = Depends(agent_service.verify)
):
    if "B" not in token["scopes"]:
        raise HTTPException(403, "Insufficient scope")
    # 提交回测任务
    ...
```

**3. 创建 MCP Server**

```python
# backend/mcp_server/src/server.py

from mcp.server import Server
from mcp.types import Tool, Resource
import httpx

server = Server("alphaterminal")

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_market_data",
            description="获取市场 K 线数据",
            inputSchema={
                "type": "object",
                "properties": {
                    "market": {"type": "string"},
                    "symbol": {"type": "string"},
                    "timeframe": {"type": "string"}
                }
            }
        ),
        Tool(
            name="get_portfolio",
            description="获取组合摘要",
            inputSchema={"type": "object"}
        ),
        Tool(
            name="submit_backtest",
            description="提交回测任务",
            inputSchema={
                "type": "object",
                "properties": {
                    "strategy_code": {"type": "string"},
                    "symbol": {"type": "string"}
                }
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[dict]:
    base_url = os.environ["ALPHATERMINAL_BASE_URL"]
    token = os.environ["ALPHATERMINAL_AGENT_TOKEN"]
    
    async with httpx.AsyncClient() as client:
        if name == "get_market_data":
            resp = await client.get(
                f"{base_url}/api/agent/v1/klines",
                params=arguments,
                headers={"Authorization": f"Bearer {token}"}
            )
            return [{"content": resp.json()}]
        # ...
```

#### 3.1.3 实施步骤

| 阶段 | 任务 | 工作量 | 依赖 |
|------|------|--------|------|
| 1 | 设计 Token 数据模型 | 0.5d | 无 |
| 2 | 实现 Token CRUD API | 1d | 1 |
| 3 | 实现 Agent 验证中间件 | 0.5d | 2 |
| 4 | 实现 /api/agent/v1 路由 | 2d | 3 |
| 5 | 实现 MCP Server 框架 | 1d | 4 |
| 6 | 实现 MCP 工具 (read only) | 1d | 5 |
| 7 | 测试和文档 | 1d | 6 |

**总工期**: 约 7 个工作日

#### 3.1.4 实施难度

⭐⭐⭐ (3/5)

---

### 3.2 数据源整合

#### 3.2.1 现状

AlphaTerminal 目前使用:
- AkShare (主力数据源)
- 腾讯财经 (实时行情)
- 新浪财经 (备用)
- Eastmoney (基金数据)

#### 3.2.2 可整合的数据源

**1. TuShare** (备选数据源)

```python
# backend/app/services/tushare_fetcher.py

import tushare as ts

class TushareFetcher:
    def __init__(self, token: str = None):
        self.pro = ts.pro_api(token)
    
    def get_stock_basic(self) -> pd.DataFrame:
        """获取股票基本信息"""
        return self.pro.stock_basic(exchange='', list_status='L')
    
    def get_daily(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取日线数据"""
        return self.pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
    
    def get_financial_data(self, ts_code: str, period: str) -> pd.DataFrame:
        """获取财务数据"""
        return self.pro.fina_indicator(ts_code=ts_code, period=period)
```

**2. pytdx** (通达信数据)

```python
# backend/app/services/pytdx_fetcher.py

from pytdx.hq import TdxHq_API

class PytdxFetcher:
    def __init__(self):
        self.api = TdxHq_API(heartbeat=True)
    
    def connect(self, ip: str = "101.227.73.33", port: int = 7709):
        self.api.connect(ip, port)
    
    def get_quote(self, code: str) -> dict:
        """获取实时行情"""
        data = self.api.get_security_quote([(code,)])[0]
        return {
            "code": data["code"],
            "name": data["name"],
            "price": data["price"],
            "volume": data["vol"]
        }
```

**3. Adanos Market Sentiment API**

```python
# backend/app/services/adanos_fetcher.py

import httpx

class AdanosSentimentFetcher:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.adanos.org"
    
    async def get_trending(self, category: str = "stocks") -> dict:
        """获取 trending tickers"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/v1/trending",
                params={"category": category},
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
            return resp.json()
```

#### 3.2.3 实施步骤

| 阶段 | 任务 | 工作量 | 依赖 |
|------|------|--------|------|
| 1 | TuShare 集成 (基础行情) | 2d | 无 |
| 2 | pytdx 集成 (Level2) | 3d | 1 |
| 3 | Adanos 情绪 API | 2d | 无 |
| 4 | 统一数据接口 | 2d | 1,2,3 |

**总工期**: 约 9 个工作日

#### 3.2.4 实施难度

⭐⭐ (2/5)

---

### 3.3 回测引擎整合

#### 3.3.1 现状

AlphaTerminal 目前有基础回测功能，但缺少:
- 绩效分析 (pyfolio)
- 参数调优
- Walk-forward 分析
- 多策略对比

#### 3.3.2 实现方案

**1. 集成 pyfolio**

```python
# backend/app/services/portfolio/perf_analysis.py

import pyfolio as pf
import empyrical as ep

class PerformanceAnalyzer:
    def __init__(self, returns: pd.Series, positions: pd.DataFrame = None):
        self.returns = returns
        self.positions = positions
    
    def get_metrics(self) -> dict:
        """计算绩效指标"""
        return {
            "total_return": ep.cum_returns_final(self.returns),
            "annual_return": ep.annual_return(self.returns, period='daily'),
            "sharpe_ratio": ep.sharpe_ratio(self.returns),
            "sortino_ratio": ep.sortino_ratio(self.returns),
            "max_drawdown": ep.max_drawdown(self.returns),
            "calmar_ratio": ep.calmar_ratio(self.returns),
            "win_rate": (self.returns > 0).sum() / len(self.returns),
        }
    
    def generate_pyfolio_report(self, benchmark_returns: pd.Series = None):
        """生成 pyfolio 报告"""
        return pf.create_full_tear_sheet(
            self.returns,
            positions=self.positions,
            benchmark_returns=benchmark_returns
        )
```

**2. 参数调优框架**

```python
# backend/app/services/backtest/optimizer.py

from dataclasses import dataclass
from enum import Enum
import itertools

class OptimizationMethod(Enum):
    GRID = "grid"        # 网格搜索
    RANDOM = "random"    # 随机搜索

@dataclass
class ParameterSpace:
    name: str
    values: list

class BacktestOptimizer:
    def __init__(self, strategy_code: str, parameter_space: list[ParameterSpace]):
        self.strategy_code = strategy_code
        self.parameter_space = parameter_space
    
    def generate_variants(self, method: OptimizationMethod, max_variants: int = 100):
        """生成参数变体"""
        if method == OptimizationMethod.GRID:
            # 网格搜索
            keys = [p.name for p in self.parameter_space]
            values = [p.values for p in self.parameter_space]
            for combo in itertools.product(*values):
                yield dict(zip(keys, combo))
        elif method == OptimizationMethod.RANDOM:
            import random
            keys = [p.name for p in self.parameter_space]
            for _ in range(max_variants):
                yield {k: random.choice(p.values) for k, p in zip(keys, self.parameter_space)}
    
    def run_optimization(
        self,
        method: OptimizationMethod,
        metric: str = "sharpe_ratio",
        max_variants: int = 100
    ) -> list[dict]:
        """运行优化"""
        results = []
        for params in self.generate_variants(method, max_variants):
            # 运行回测
            result = self.run_backtest(params)
            result["params"] = params
            results.append(result)
        
        # 按指标排序
        results.sort(key=lambda x: x.get(metric, 0), reverse=True)
        return results
```

#### 3.3.3 实施步骤

| 阶段 | 任务 | 工作量 | 依赖 |
|------|------|--------|------|
| 1 | pyfolio 集成 | 2d | 无 |
| 2 | 绩效指标计算 | 1d | 1 |
| 3 | 参数调优框架 | 3d | 无 |
| 4 | 多策略对比 UI | 2d | 1,2,3 |

**总工期**: 约 8 个工作日

#### 3.3.4 实施难度

⭐⭐⭐ (3/5)

---

### 3.4 策略框架整合

#### 3.4.1 为什么重要

QuantDinger 的 IndicatorStrategy 允许用户用简单的 Python 脚本定义指标和信号，适合非程序员用户。AlphaTerminal 目前没有这个功能。

#### 3.4.2 实现方案

**IndicatorStrategy 模式**:

```python
# backend/app/services/strategy/indicator_strategy.py

from dataclasses import dataclass
from typing import Callable, Dict
import pandas as pd

@dataclass
class StrategySpec:
    """策略规格定义"""
    name: str
    description: str
    parameters: Dict[str, any]
    stop_loss_pct: float = 2.0
    take_profit_pct: float = 6.0

class IndicatorStrategy:
    def __init__(self, code: str, spec: StrategySpec):
        self.code = code
        self.spec = spec
    
    def compile(self) -> Callable:
        """编译策略代码为可执行函数"""
        local_vars = {"pd": pd}
        exec(self.code, local_vars)
        return local_vars["output"]
    
    def evaluate(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        """评估策略生成信号"""
        output_func = self.compile()
        return output_func(df)
    
    def to_signal_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """转换为信号 DataFrame"""
        result = self.evaluate(df)
        signals = result.get("signals", {})
        
        return pd.DataFrame({
            "buy": signals.get("buy", pd.Series(False, index=df.index)),
            "sell": signals.get("sell", pd.Series(False, index=df.index)),
            "indicators": result.get("indicators", {})
        })

# 策略执行器
class StrategyRunner:
    def __init__(self, strategy: IndicatorStrategy):
        self.strategy = strategy
    
    def backtest(self, df: pd.DataFrame, initial_capital: float = 10000) -> BacktestResult:
        """回测策略"""
        signals = self.strategy.to_signal_df(df)
        # ... 回测逻辑
        return BacktestResult(...)
    
    def walk_forward(self, df: pd.DataFrame, train_window: int, test_window: int):
        """Walk-forward 分析"""
        results = []
        for i in range(train_window, len(df), test_window):
            train_df = df[i-train_window:i]
            test_df = df[i:i+test_window]
            
            # 在训练集上优化参数
            best_params = self.optimize(train_df)
            
            # 在测试集上验证
            result = self.backtest_with_params(test_df, best_params)
            results.append(result)
        
        return results
```

**ScriptStrategy 模式**:

```python
# backend/app/services/strategy/script_strategy.py

from dataclasses import dataclass

@dataclass
class StrategyContext:
    """策略执行上下文"""
    df: pd.DataFrame
    position: float = 0.0
    cash: float = 0.0
    entry_price: float = 0.0
    orders: list = None

class ScriptStrategy:
    def __init__(self, code: str):
        self.code = code
        self._compile()
    
    def _compile(self):
        """编译策略代码"""
        self._namespace = {
            "pd": pd,
            "ctx": StrategyContext(df=pd.DataFrame()),
            "buy": self._buy,
            "sell": self._sell,
            "close_position": self._close_position,
        }
        exec(self.code, self._namespace)
    
    def on_init(self, ctx: StrategyContext):
        """初始化回调"""
        if "on_init" in self._namespace:
            self._namespace["on_init"](ctx)
    
    def on_bar(self, ctx: StrategyContext, bar: pd.Series):
        """每根 K 线回调"""
        if "on_bar" in self._namespace:
            self._namespace["on_bar"](ctx, bar)
    
    def _buy(self, ctx: StrategyContext, quantity: float, price: float = None):
        ctx.position += quantity
        ctx.cash -= quantity * (price or ctx.df["close"].iloc[-1])
    
    def _sell(self, ctx: StrategyContext, quantity: float, price: float = None):
        ctx.position -= quantity
        ctx.cash += quantity * (price or ctx.df["close"].iloc[-1])
    
    def _close_position(self, ctx: StrategyContext):
        ctx.position = 0
```

#### 3.4.3 实施步骤

| 阶段 | 任务 | 工作量 | 依赖 |
|------|------|--------|------|
| 1 | 策略 DSL 设计 | 2d | 无 |
| 2 | IndicatorStrategy 解析器 | 3d | 1 |
| 3 | ScriptStrategy 运行时 | 3d | 1 |
| 4 | 策略 IDE UI | 5d | 2,3 |
| 5 | 策略版本管理 | 2d | 2,3 |

**总工期**: 约 15 个工作日

#### 3.4.4 实施难度

⭐⭐⭐⭐ (4/5)

---

### 3.5 UI/UX 整合

#### 3.5.1 QuantDinger UI 设计模式

QuantDinger 有私有前端仓库 (`frontend/` 仅含构建产物)。但从文档 `docs/FRONTEND_FAST_ANALYSIS.md` 可以看出:

**UI 设计原则**:
1. **Fast Analysis 组件化** - 快速分析结果应该是一个独立组件
2. **Trading Plan 明确** - 止损/止盈应该从 `trading_plan` 字段读取，而非 `trading_levels`
3. **Market Regime 展示** - 市场状态应该可视化展示

**参考组件结构**:
```
FastAnalysisReport.vue
├── TrendOutlook.vue      # 趋势预判
├── TradingPlan.vue      # 交易计划
│   ├── EntryPrice.vue
│   ├── StopLoss.vue
│   └── TakeProfit.vue
└── IndicatorsPro.vue   # 技术指标详情
```

#### 3.5.2 AlphaTerminal UI 当前状态

| 组件 | 状态 | 说明 |
|------|------|------|
| DashboardGrid | ✅ | 响应式网格布局 |
| SentimentGauge | ✅ | 情绪仪表 |
| NewsFeed | ✅ | 快讯列表 |
| FundHoldings | ✅ | 基金持仓 |
| Copilot | ⚠️ | 基础对话 |

#### 3.5.3 UI 整合建议

| 功能 | 优先级 | 实现方案 |
|------|--------|---------|
| 策略 IDE | ⭐⭐⭐ | 参考 QuantDinger Indicator IDE |
| Fast Analysis | ⭐⭐ | 新增 AI 分析结果组件 |
| Market Regime 展示 | ⭐⭐ | 新增市场状态组件 |
| 多窗口布局 | ⭐ | 参考 GridStack 实现 |

#### 3.5.4 实施难度

⭐⭐⭐ (3/5)

---

### 3.6 安全机制整合

#### 3.6.1 为什么重要

QuantDinger 的安全机制确保:
- Agent Token 不会被滥用
- 交易操作默认 paper-only
- 所有操作都有审计日志

AlphaTerminal 目前没有这些机制。

#### 3.6.2 实现方案

**1. 审计日志**:

```python
# backend/app/services/audit.py

from dataclasses import dataclass
from datetime import datetime
import json

@dataclass
class AuditLog:
    id: int
    timestamp: datetime
    agent_id: str
    action: str
    resource: str
    details: dict
    ip_address: str
    user_agent: str

class AuditService:
    def __init__(self, db):
        self.db = db
    
    def log(
        self,
        agent_id: str,
        action: str,
        resource: str,
        details: dict = None,
        request: Request = None
    ):
        """记录审计日志"""
        log = AuditLog(
            id=self._next_id(),
            timestamp=datetime.now(),
            agent_id=agent_id,
            action=action,
            resource=resource,
            details=details or {},
            ip_address=request.client.host if request else None,
            user_agent=request.headers.get("user-agent") if request else None
        )
        self._save(log)
    
    def query(
        self,
        agent_id: str = None,
        action: str = None,
        start_time: datetime = None,
        end_time: datetime = None,
        limit: int = 100
    ) -> list[AuditLog]:
        """查询审计日志"""
        query = "SELECT * FROM audit_logs WHERE 1=1"
        params = []
        
        if agent_id:
            query += " AND agent_id = ?"
            params.append(agent_id)
        
        return self.db.execute(query, params).fetchall()
```

**2. Paper Trading 模式**:

```python
# backend/app/services/paper_trading.py

from enum import Enum
from dataclasses import dataclass

class TradingMode(Enum):
    PAPER = "paper"
    LIVE = "live"

@dataclass
class Order:
    id: str
    symbol: str
    side: str  # BUY / SELL
    quantity: float
    price: float
    mode: TradingMode
    status: str  # PENDING / FILLED / CANCELLED

class PaperTradingService:
    def __init__(self, portfolio_service):
        self.portfolio = portfolio_service
        self.orders = []
    
    def submit_order(self, order: Order) -> Order:
        """提交订单 (paper 模式)"""
        if order.mode != TradingMode.PAPER:
            raise ValueError("PaperTradingService only accepts PAPER orders")
        
        order.status = "FILLED"
        self.orders.append(order)
        
        # 更新 paper portfolio
        if order.side == "BUY":
            self.portfolio.buy(order.symbol, order.quantity, order.price)
        else:
            self.portfolio.sell(order.symbol, order.quantity, order.price)
        
        return order
    
    def get_paper_positions(self) -> dict:
        """获取 paper 持仓"""
        return self.portfolio.get_positions()
```

#### 3.6.3 实施难度

⭐⭐ (2/5)

---

## 4. 实施计划

### 4.1 优先级排序

| 优先级 | 任务 | 工作量 | 价值 |
|--------|------|--------|------|
| **P0** | MCP Server 集成 | 7d | ⭐⭐⭐⭐⭐ |
| **P0** | Agent Token 系统 | 5d | ⭐⭐⭐⭐⭐ |
| **P1** | 数据源扩展 (TuShare) | 4d | ⭐⭐⭐⭐ |
| **P1** | 策略框架基础 | 10d | ⭐⭐⭐⭐ |
| **P2** | pyfolio 集成 | 4d | ⭐⭐⭐ |
| **P2** | 参数调优 | 5d | ⭐⭐⭐ |
| **P3** | 通知系统 | 3d | ⭐⭐ |
| **P3** | 多用户支持 | 10d | ⭐⭐ |

### 4.2 实施路线图

```
Q2 2026 (当前季度)
├── P0: MCP Server + Agent Token
├── P1: 数据源扩展
└── P1: 策略框架基础

Q3 2026
├── P2: pyfolio 集成
├── P2: 参数调优
└── P3: 通知系统

Q4 2026
└── P3: 多用户支持
```

### 4.3 详细实施计划

#### Phase 1: AI Agent 基础设施 (4 周)

**目标**: 让 AI Agent 可以安全地调用 AlphaTerminal

| 周 | 任务 | 交付物 |
|----|------|--------|
| 1 | Agent Token 数据模型和 CRUD | Token 管理 API |
| 2 | Agent 验证中间件 | `/api/agent/v1/*` 路由 |
| 3 | MCP Server 框架 | MCP 工具定义 |
| 4 | MCP 工具实现 (Read) | get_klines, get_price, search_symbols |

#### Phase 2: 数据源扩展 (2 周)

**目标**: 扩展数据覆盖范围

| 周 | 任务 | 交付物 |
|----|------|--------|
| 1 | TuShare 集成 | 基础行情 API |
| 2 | pytdx 集成 | Level2 行情 |

#### Phase 3: 策略框架 (6 周)

**目标**: 支持用户自定义策略

| 周 | 任务 | 交付物 |
|----|------|--------|
| 1-2 | IndicatorStrategy DSL | 策略解析器 |
| 3-4 | ScriptStrategy 运行时 | 事件驱动执行 |
| 5-6 | 策略 IDE UI | 策略编辑器 |

#### Phase 4: 回测增强 (4 周)

**目标**: 增强回测和绩效分析

| 周 | 任务 | 交付物 |
|----|------|--------|
| 1 | pyfolio 集成 | 绩效报告 |
| 2 | 参数调优框架 | Grid/Random 搜索 |
| 3-4 | 多策略对比 UI | 策略排行 |

---

## 5. 参考资源

### 5.1 QuantDinger

| 资源 | 路径/链接 |
|------|-----------|
| GitHub | https://github.com/brokermr810/QuantDinger |
| AI 交易系统方案 | `docs/AI_TRADING_SYSTEM_PLAN_CN.md` |
| 策略开发指南 | `docs/STRATEGY_DEV_GUIDE_CN.md` |
| Agent 设计 | `docs/agent/AGENT_ENVIRONMENT_DESIGN.md` |
| Agent 快速入门 | `docs/agent/AGENT_QUICKSTART.md` |
| 技术指标定义 | `docs/INDICATOR_DEFINITIONS_CN.md` |
| MCP Server | `mcp_server/` |

### 5.2 awesome-quant

| 资源 | 链接 |
|------|------|
| GitHub | https://github.com/thuquant/awesome-quant |

### 5.3 推荐集成

| 资源 | 用途 | 链接 |
|------|------|------|
| pyfolio | 绩效分析 | https://github.com/quantopian/pyfolio |
| TA-Lib | 技术指标 | https://github.com/mrjbq7/ta-lib |
| Zipline | 回测框架 | https://github.com/quantopian/zipline |
| RQAlpha | 回测框架 | https://github.com/ricequant/rqalpha |
| pandas-ta | 技术指标 | https://github.com/tedchuai/pandas-ta |

---

## 附录 A: QuantDinger 后端路由详细列表

| 文件 | 功能 | API 数量 |
|------|------|----------|
| `auth.py` | 认证授权 | 15+ |
| `user.py` | 用户管理 | 20+ |
| `strategy.py` | 策略 CRUD | 15+ |
| `quick_trade.py` | 快捷交易 | 10+ |
| `trading_executor.py` | 订单执行 | 15+ |
| `indicator.py` | 技术指标 | 10+ |
| `backtest.py` | 回测引擎 | 8+ |
| `portfolio.py` | 组合管理 | 12+ |
| `market.py` | 市场数据 | 10+ |
| `experiment.py` | 实验编排 | 5+ |
| `polymarket.py` | 预测市场 | 5+ |

## 附录 B: awesome-quant 完整资源列表

### 数据源 (15+)
- TuShare, AkShare, pytdx, JoinQuant SDK, zvt, fooltrader
- FXMacroData, Adanos Sentiment API
- Wind, Bloomberg (收费)

### 回测框架 (8+)
- Zipline, RQAlpha, QuantConnect Lean
- QUANTAXIS, pyalgotrade, finclaw

### 技术指标库 (5+)
- TA-Lib, pandas-ta, ta, ffn, pyfolio

### 交易 API (10+)
- IB API, Futu Open API, vnpy, tqsdk

---

*报告生成时间: 2026-05-07*  
*分析工具: OpenCode ULW Agent*  
*数据来源: QuantDinger v3.0.3, awesome-quant, AlphaTerminal v0.6.11*
