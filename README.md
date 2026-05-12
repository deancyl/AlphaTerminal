# AlphaTerminal

<div align="center">

# 📊 AlphaTerminal — 本地化 AI 智能投研终端

**高性能 · 高密度 · 可联动 · 完全免费 · 完全开源**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Vue.js](https://img.shields.io/badge/Vue-3.5-green.svg)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-blue.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Release](https://img.shields.io/badge/Release-v0.6.30-blue.svg)](https://github.com/deancyl/AlphaTerminal/releases)

*"让每一位个人投资者，都拥有一座专业的投研数据堡垒。"*

</div>

---

## 🚀 快速启动（一键启动）

### 方式一：一键启动脚本（推荐）

我们提供了一键启动脚本，自动完成环境检查、依赖安装和服务启动：

#### Linux / macOS
```bash
# 1. 克隆仓库
git clone https://github.com/deancyl/AlphaTerminal.git
cd AlphaTerminal

# 2. 一键启动（自动安装依赖 + 启动前后端）
./start-services.sh all

# 3. 访问 http://localhost:60100
```

#### Windows
```powershell
# 1. 克隆仓库
git clone https://github.com/deancyl/AlphaTerminal.git
cd AlphaTerminal

# 2. 一键启动（自动安装依赖 + 启动前后端）
.\start-services.ps1 all

# 3. 访问 http://localhost:60100
```

### 常用命令

| 命令 | Linux/macOS | Windows | 说明 |
|------|-------------|---------|------|
| 启动全部 | `./start-services.sh all` | `.\start-services.ps1 all` | 启动前后端 |
| 仅后端 | `./start-services.sh backend` | `.\start-services.ps1 backend` | 仅启动后端 |
| 仅前端 | `./start-services.sh frontend` | `.\start-services.ps1 frontend` | 仅启动前端 |
| 重启服务 | `./start-services.sh restart` | `.\start-services.ps1 restart` | 重启所有服务 |
| 停止服务 | `./start-services.sh stop` | `.\start-services.ps1 stop` | 停止所有服务 |
| 查看状态 | `./start-services.sh status` | `.\start-services.ps1 status` | 查看运行状态 |

### 服务架构

```
用户浏览器 → 前端服务器(60100) → [API代理] → 后端服务器(8002)
            → [静态文件] → dist/
```

- **前端**: Vite Preview 模式（端口 60100）
  - 提供静态文件（Vue 3 构建产物）
  - 代理 `/api/*` 请求到后端 8002 端口
  
- **后端**: FastAPI + Uvicorn（端口 8002）
  - 所有业务API
  - 宏观经济数据（akshare）
  - 5分钟缓存机制

### 方式二：手动启动

如果需要手动控制启动过程：

```bash
# 1. 安装后端依赖
cd backend
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install psutil  # 额外依赖

# 2. 安装前端依赖
cd ../frontend
npm install

# 3. 启动后端（端口 8002）
cd ../backend
python start_backend.py

# 4. 启动前端（端口 60100，另一终端窗口）
cd ../frontend
npm run dev -- --host 0.0.0.0 --port 60100

# 5. 访问 http://localhost:60100
```

### 环境要求

- **Python**: 3.11+（推荐 3.11 或 3.12）
- **Node.js**: 20+（推荐 20.x LTS）
- **操作系统**: Linux / macOS / Windows
- **内存**: 至少 2GB 可用内存
- **磁盘**: 至少 1GB 可用空间

### 常见问题

#### 1. Python externally-managed-environment 错误
如果看到此错误，请使用虚拟环境：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### 2. Node.js / npm 未找到
请安装 Node.js 20+：
- **官方下载**: https://nodejs.org/
- **macOS**: `brew install node`
- **Ubuntu/Debian**: `sudo apt install nodejs npm`

#### 3. 端口被占用
启动脚本会自动检测并尝试释放端口。如果失败，请手动停止占用进程：
```bash
# Linux/macOS
lsof -ti:8002 | xargs kill -9  # 后端端口
lsof -ti:60100 | xargs kill -9  # 前端端口

# Windows
Get-Process -Id (Get-NetTCPConnection -LocalPort 8002).OwningProcess | Stop-Process
```

#### 4. 宏观经济面板显示错误
如果宏观经济面板显示"应用出现错误"或echarts相关错误：
- 确保使用 `./start-services.sh restart` 重启服务
- 脚本会自动重新构建前端并清理缓存
- 第一次加载可能需要10-15秒（akshare获取数据）

#### 5. 前端请求直接访问localhost:8002导致连接失败
**症状**: 浏览器控制台显示 `net::ERR_CONNECTION_REFUSED localhost:8002`

**原因**: 前端代码直接访问 `localhost:8002` 而不是通过前端代理

**解决**: 
- 确保所有API请求使用相对路径（如 `/api/v1/...`）
- 检查 `frontend/src/utils/api.js` 和 `frontend/src/services/copilotData.js` 中的 `API_BASE_URL` 配置
- 正确配置应为 `const API_BASE_URL = ''`（空字符串，使用相对路径）
- 重启服务：`./start-services.sh restart`

#### 6. 数据接口连接失败
如果数据接口无法连接，请设置代理环境变量：
```bash
export HTTP_PROXY=http://你的代理IP:端口
export HTTPS_PROXY=http://你的代理IP:端口
```

#### 5. Rollup native module 错误（Linux）
如果遇到 `@rollup/rollup-linux-x64-gnu` 错误，启动脚本会自动修复。如果手动修复：
```bash
cd frontend
mkdir -p node_modules/@rollup
cd node_modules/@rollup
curl -L -o rollup-linux-x64-gnu.tgz https://registry.npmjs.org/@rollup/rollup-linux-x64-gnu/-/rollup-linux-x64-gnu-4.34.8.tgz
tar xzf rollup-linux-x64-gnu.tgz
mv package rollup-linux-x64-gnu
rm rollup-linux-x64-gnu.tgz
```

---

## 🎯 核心功能

### 市场数据
- **多周期 K 线**：分时 / 日K / 周K / 月K，完整 OHLCV
- **全市场覆盖**：A股（沪深 300 + 重点蓝筹）/ 港股 / 美股指数
- **实时刷新**：后台每 3 分钟增量拉取，API 响应 < 5ms

### 债券分析（Phase 8–9）
- **真实信用利差**：接入 `/bond/curve` API，商业银行 AAA vs 国债实时利差（bp）
- **历史曲线对比**：今日实线 + 1个月前虚线（dashed）+ 1年前点线（dotted）
- **期限利差矩阵**：7 期限 × 3 品种（国债/国开/商A-AAA）利率估值表
- **隐含税率**：国开-国债利差百分比，机构买债免税溢价
- **10Y-2Y 期限利差图**：每日利差 bp 柱状图，红绿区分正常/倒挂

### 期货分析（Phase 8）
- **量价仓联动（ΔOI）**：持仓变化红绿柱（涨增仓红/跌增仓绿/减仓灰）
- **期限结构图（Forward Curve）**：主力 K 线 / 期限结构双视图切换
  - Contango（远月升水↑）：远月 > 近月，现货充足
  - Backwardation（近月升水↓）：近月 > 远月，现货紧缺

### 行业板块
- **真实行业板块**：新浪财经行业（84个）+ 概念板块（175个）融合
- **关键词加权**：AI / 算力 / 半导体 / 机器人等主题优先展示
- **领涨股标注**：每个板块显示对应代表性股票

### 新闻快讯
- **东方财富实时新闻**：150 条/次，真实发布时间戳
- **强制刷新**：`POST /api/v1/news/force_refresh` 穿透缓存
- **情感分类**：利好/利空关键词扫描

### 交互界面
- **GridStack 响应式网格**：拖拽布局，锁定/解锁切换
- **全屏 K 线**：F 按键进入，Esc 退出，鼠标滚轮缩放
- **画线工具**：趋势线 / 水平线 / 斐波那契 / 内联文本标注
- **AI Copilot 侧边栏（Phase 6 增强）**：真实市场数据 + 新闻上下文分析 + 智能意图识别 + LLM扩展接口

### 回测实验室（v0.5.54+）
- **三大策略**：双均线交叉 / RSI 超卖 / 布林带回归
- **股票/组合双模式**：直接输入股票代码，或从投资组合导入持仓一键回测
- **持仓自动前缀补全**：投资组合中的 `"600519"` 自动转为 `"sh600519"`
- **策略体检报告**：收益率、年化、夏普比率、最大回撤、胜率、盈亏比
- **基准对比**：策略 vs 持股不动，超额收益一目了然

### Debug 诊断控制台（v0.6.7+）
- **10 个诊断工具**：快速健康检查、API 测试、数据库诊断、安全审计、性能分析、WebSocket 测试、日志分析、前端调试等
- **Web UI 集成**：管理面板一键执行诊断工具，实时查看执行结果
- **健康仪表盘**：实时监控后端服务、数据库、前端状态
- **执行历史**：保留最近 50 次执行记录，支持报告导出
- **命令行支持**：`./scripts/debug/debug.sh full` 一键完整诊断

### F9 深度资料（v0.6.16+）
- **8 维度分析**：公司概况、财务摘要、机构持股、盈利预测、股东研究、公司公告、同业比较、融资融券
- **实时数据**：25+ 财务指标、8 季度趋势、机构持仓变化、30 日融资融券数据
- **可视化图表**：趋势图、饼图、雷达图、对比表格
- **快捷操作**：F9 键盘快捷键、Ctrl+K 命令面板、右键菜单
- **智能缓存**：5 分钟缓存，首次加载后快速响应

---

## 🏗 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                   前端 (Vite Dev Server)                  │
│             http://localhost:60100  (Web UI)              │
│        Vue 3 + TailwindCSS + GridStack + ECharts         │
└─────────────────────┬───────────────────────────────────┘
                      │ proxy /api/* → :8002
┌─────────────────────▼───────────────────────────────────┐
│                   后端 (FastAPI)                          │
│               http://0.0.0.0:8002  (API Only)             │
│                                                             │
│   /api/v1/market/overview    /api/v1/news/flash           │
│   /api/v1/bond/curve          /api/v1/futures/term_structure │
│   /api/v1/news/force_refresh  /api/v1/market/sectors      │
│   /api/v1/portfolio/          /api/v1/backtest/run         │
│   /api/v1/copilot/status      /api/v1/market/stocks/search │
│   /api/v1/f9/{symbol}/financial  /api/v1/f9/{symbol}/institution │
│   /api/v1/f9/{symbol}/margin     /api/v1/f9/{symbol}/forecast    │
│   /api/v1/f9/{symbol}/shareholder /api/v1/f9/{symbol}/announcements│
│   /api/v1/f9/{symbol}/peers      /api/v1/f9/health               │
│                                                             │
│   APScheduler 调度任务（后台线程）                          │
│   ├── NewsRefresh (每 5 分钟) ←─ 东方财富实时新闻        │
│   ├── AkShareDataFetch (每 3 分钟)                        │
│   └── SentimentFetch (每 3 分钟)                           │
└─────────────────────────────────────────────────────────┘
                      │
                      ▼
         ┌─────────────────────────────────┐
         │  AkShare / 东方财富 / 新浪财经     │
         │  HTTP_PROXY: 环境变量或 start_backend.py 配置
         └─────────────────────────────────┘
```

---

## 📂 项目结构

```
AlphaTerminal/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口 + CORS + lifespan
│   │   ├── routers/
│   │   │   ├── market.py       # 行情 / 板块 / 个股搜索
│   │   │   ├── news.py         # 快讯 / force_refresh
│   │   │   ├── bond.py         # 债券收益率曲线 / 信用利差
│   │   │   ├── futures.py      # 期货行情 / 期限结构
│   │   │   ├── sentiment.py    # 市场情绪
│   │   │   ├── portfolio.py    # 投资组合 CRUD / PnL / 快照
│   │   │   ├── backtest.py     # 回测引擎
│   │   │   ├── copilot.py     # AI Copilot
│   │   │   └── f9_deep.py     # F9 深度资料 API
│   │   └── services/
│   │       ├── data_fetcher.py  # AkShare / httpx 数据获取
│   │       ├── news_engine.py    # 新闻缓存引擎
│   │       ├── sentiment_engine.py
│   │       ├── scheduler.py     # APScheduler 调度
│   │       └── sectors_cache.py # 行业/概念板块缓存
│   ├── requirements.txt
│   └── start_backend.py         # 后端启动入口
├── frontend/
│   └── src/
│       ├── App.vue              # 主布局 + Navbar
│       ├── utils/
│       │   ├── chartDataBuilder.js  # K线数据计算引擎（MA/BOLL/MACD/KDJ/RSI/ΔOI）
│       │   ├── indicators.js        # 技术指标纯函数
│       │   └── symbols.js           # 符号工具函数
│       └── components/
│           ├── DashboardGrid.vue    # GridStack 网格
│           ├── NewsFeed.vue         # 快讯面板
│           ├── QuotePanel.vue        # 行情卡片
│           ├── DrawingCanvas.vue     # 画线工具
│           ├── BaseKLineChart.vue   # 统一K线哑组件（数据驱动）
│           ├── AdvancedKlinePanel.vue # 高级K线面板（Controller层）
│           ├── FullscreenKline.vue  # 全屏K线
│           ├── FuturesPanel.vue     # 期货面板（K线+ΔOI+期限结构）
│           ├── TermStructureChart.vue # 期限结构图（Forward Curve）
│           ├── BondDashboard.vue   # 债券看板（利率矩阵+历史曲线对比）
│           ├── YieldCurveChart.vue  # 收益率曲线（含历史截面对比）
│           ├── BacktestDashboard.vue # 回测实验室
│           ├── PortfolioDashboard.vue # 投资组合面板
│           ├── StockScreener.vue     # 条件选股
│           ├── SentimentGauge.vue    # 市场情绪仪表
│           ├── FundFlowPanel.vue     # 资金流向面板
│           ├── StockDetail.vue       # F9 深度资料面板
│           └── f9/                   # F9 共享组件
│               ├── DataTable.vue     # 数据表格
│               ├── InfoCard.vue      # 信息卡片
│               ├── LoadingSpinner.vue # 加载指示器
│               ├── ErrorDisplay.vue  # 错误显示
│               └── TrendChart.vue    # 趋势图表
├── scripts/
│   ├── init_env.sh              # ✅ 环境初始化脚本（克隆后运行）
│   ├── init_database.py         # 数据库初始化
│   └── fetch_historical_data.py  # 历史数据回填
├── docs/
├── KNOWN_ISSUES_TODO.md         # 缺陷追踪 + 路线图
└── README.md
```

---

## 🔧 常见问题

**Q: 板块数据/新闻拉取失败？**
> 检查网络代理设置。数据源（东方财富/新浪/AkShare）需访问国内服务器。

**Q: 前端显示空白或卡住？**
> 检查后端是否正常运行：`curl http://localhost:8002/api/v1/market/overview`
> 如返回数据则后端正常，检查浏览器控制台。

**Q: 数据库写入报错？**
> 确保 `backend/cache/` 目录在本地磁盘（非 SSHFS/FUSE 网络盘），SQLite 在网络盘上会死锁。

---

## 📜 许可

MIT License · 欢迎 Star & Fork
