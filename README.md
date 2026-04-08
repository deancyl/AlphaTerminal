# AlphaTerminal

<div align="center">

# 📊 AlphaTerminal — 本地化 AI 智能投研终端

**高性能 · 高密度 · 可联动 · 完全免费 · 完全开源**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Vue.js](https://img.shields.io/badge/Vue-3.5-green.svg)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-blue.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Release](https://img.shields.io/badge/Release-Beta%20v0.4.57-orange.svg)](https://github.com/deancyl/AlphaTerminal/releases)

*"让每一位个人投资者，都拥有一座专业的投研数据堡垒。"*

</div>

---

## 🚀 快速启动

```bash
# 1. 克隆仓库
git clone https://github.com/deancyl/AlphaTerminal.git
cd AlphaTerminal

# 2. 一键初始化环境（自动安装 Python + Node 依赖）
bash scripts/init_env.sh

# 3. 启动后端（端口 8002）
cd backend && source .venv/bin/activate
python start_backend.py

# 4. 启动前端（端口 60100，另一终端窗口）
cd frontend && npm run dev -- --host 0.0.0.0 --port 60100

# 5. 访问 http://localhost:60100
```

> 💡 **初始化脚本** (`scripts/init_env.sh`) 会自动完成：
> - Python 虚拟环境创建 + 依赖安装
> - SQLite 数据库初始化
> - 前端 `node_modules` 安装
> - 启动命令说明

> ⚠️ 若数据接口连接失败，请设置代理环境变量：
> ```bash
> export HTTP_PROXY=http://你的代理IP:端口
> export HTTPS_PROXY=http://你的代理IP:端口
> ```

---

## 🎯 核心功能

### 市场数据
- **多周期 K 线**：分时 / 日K / 周K / 月K，完整 OHLCV
- **全市场覆盖**：A股（沪深 300 + 重点蓝筹）/ 港股 / 美股指数
- **实时刷新**：后台每 3 分钟增量拉取，API 响应 < 5ms

### 债券分析（Phase 8）
- **真实信用利差**：接入 `/bond/curve` API，商业银行 AAA vs 国债实时利差（bp）
- **历史曲线对比**：今日实线 + 1个月前虚线（dashed）+ 1年前点线（dotted）
- **期限利差矩阵**：7 期限 × 3 品种（国债/国开/商A-AAA）利率估值表

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
- **画线工具**：趋势线 / 水平线 / 斐波那契
- **AI Copilot 侧边栏**：市场分析 / 标的推荐 / 事件解读

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
│   │   │   └── sentiment.py    # 市场情绪
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
│           └── YieldCurveChart.vue  # 收益率曲线（含历史截面对比）
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
