# AlphaTerminal

<div align="center">

# 📊 AlphaTerminal — 本地化 AI 智能投研沙盒终端

**高性能 · 高密度 · 可联动 · 完全开源**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Vue.js](https://img.shields.io/badge/Vue-3.5-green.svg)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-blue.svg)](https://fastapi.tiangolo.com/)
[![SQLite](https://img.shields.io/badge/SQLite-WAL-orange.svg)](https://sqlite.org/)
[![AkShare](https://img.shields.io/badge/AkShare-1.18+-red.svg)](https://akshare.akfamily.xyz/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

*"让每一位个人投资者，都拥有一座专业的投研数据堡垒。"*

</div>

---

## 🎯 项目简介

AlphaTerminal 是一款**完全本地运行**的高性能金融投研终端，汇聚全市场数据、A 股情绪图谱、机构级新闻引擎与 AI Copilot 助手于一身。

不同于传统终端依赖付费数据源，AlphaTerminal 全部基于免费开源数据（AkShare、Sina HQ、东方财富），配合本地 SQLite 缓存与后台增量刷新，实现**零成本、零外部依赖、毫秒级响应**的专业级体验。

> ⚠️ **网络说明**：中国市场数据接口（AkShare/东方财富/Sina）需要**中国大陆网络环境**或配置代理。详细避坑指南见 [部署指南](docs/deployment_guide.md)。

---

## ⚡ 核心特性

### 1. 毫秒级全市场数据底座
- **多周期 K 线**：分时 / 日K / 周K / 月K，完整 OHLCV 数据
- **全市场覆盖**：A股（沪深300+重点蓝筹）、港股、美股、日经、恒生
- **实时刷新**：后台 APScheduler 每 3 分钟增量拉取，API 响应 **< 10ms**

### 2. 机构级高密度数据面板
- **市场情绪直方图**：11 个涨跌区间桶（跌停 → 涨停），实时统计上涨/下跌家数
- **沪深 300 个股透视**：按涨跌幅/换手率/成交额排序，支持分页浏览
- **行业风口**：真实行业板块（AkShare 数据），而非用指数冒充行业

### 3. 20 分钟多源新闻引擎
- **主源**：东方财富 `stock_news_em`（30 只核心标的）
- **宏观快讯**：百度财经 `news_economic_baidu`（~100 条/次）
- **正文抓取**：BS4 纯文本提取，支持 eastmoney/sina/ifeng 等主流媒体
- **MD5 URL 去重**：进程内存缓存，保留最新 200 条

### 4. 响应式 AI Copilot 侧边栏
- **抽屉式设计**：可折叠/展开，不占用看盘空间
- **全局 K 线联动**：点击任意指数/板块，K 线主图立即切换
- **SSE 流式对话**：打字机效果，支持上下文注入

---

## 🏗️ 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Vue 3 + Vite + TailwindCSS            │
│                  GridStack · ECharts · CopilotSidebar       │
│                         (Frontend :60100)                   │
└─────────────────────┬───────────────────────────────────────┘
                      │ Proxy /api/*
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                 FastAPI + APScheduler + SQLite               │
│   ┌─────────────────────────────────────────────────────┐    │
│   │ REST API Routes (< 10ms)                            │    │
│   │   /market/overview · /sentiment · /stocks         │    │
│   │   /news/flash · /market/history                     │    │
│   └─────────────────────────────────────────────────────┘    │
│   ┌─────────────────────────────────────────────────────┐    │
│   │ Global Caches (in-memory, bg-refreshed)             │    │
│   │   SpotCache · NewsCache · SectorsCache              │    │
│   └─────────────────────────────────────────────────────┘    │
│   ┌─────────────────────────────────────────────────────┐    │
│   │ APScheduler (bg threads)                           │    │
│   │   DataFetch 3min · SentimentRefresh 3min           │    │
│   │   NewsRefresh 20min · SectorsRefresh 5min          │    │
│   └─────────────────────────────────────────────────────┘    │
│                     (Backend :8002)                         │
└─────────────────────┬───────────────────────────────────────┘
                      │
           ┌──────────▼──────────┐
           │    SQLite WAL DB      │
           │  market_data_realtime │
           │  market_data_daily   │
           └───────────────────────┘
```

---

## 🛡️ 数据源

| 数据类型 | 来源 | 刷新频率 |
|----------|------|----------|
| A股实时行情 | 腾讯 qt.gtimg.cn（Sina HQ） | ~3 min |
| 国内指数 | 东方财富 / AkShare | ~3 min |
| 行业板块 | AkShare `stock_board_industry_name_em` | ~5 min |
| 港美股 | AkShare + yfinance | ~5 min |
| 新闻快讯 | 东方财富 + 百度财经 | ~20 min |
| 利率/宏观 | AkShare `macro_china_shibor_all` | ~3 min |

---

## 🚀 快速启动

> 完整部署步骤见 [docs/deployment_guide.md](docs/deployment_guide.md)

```bash
# ── 1. 后端（端口 8002）───────────────────────────────────────────────
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
nohup .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8002 > backend.log 2>&1 &

# ── 2. 前端（端口 60100）──────────────────────────────────────────────
cd frontend
npm install
npm run dev

# 浏览器访问：http://localhost:60100
```

---

## 📁 目录结构

```
AlphaTerminal/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI 入口 + lifespan
│   │   ├── routers/                 # API 路由层（全部 < 10ms）
│   │   │   ├── market.py            # /market/* (overview/k线/sectors)
│   │   │   ├── news.py              # /news/* (flash/detail)
│   │   │   ├── sentiment.py          # /sentiment/histogram/stocks
│   │   │   └── copilot.py           # /chat (SSE AI对话)
│   │   ├── services/
│   │   │   ├── data_fetcher.py      # AkShare 数据拉取
│   │   │   ├── sina_hq_fetcher.py   # 腾讯行情（沪深300成分股）
│   │   │   ├── sectors_cache.py     # 行业板块全局缓存
│   │   │   ├── sentiment_engine.py   # 市场情绪 + SpotCache
│   │   │   ├── news_engine.py       # 新闻缓存 + 多源轮询
│   │   │   └── scheduler.py         # APScheduler 后台任务调度
│   │   └── db/
│   │       └── database.py          # SQLite WAL 读写
│   ├── cache/
│   │   └── alphaterminal.db         # SQLite 数据库文件
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.vue                  # 根组件 + Copilot 抽屉
│   │   ├── components/
│   │   │   ├── DashboardGrid.vue    # GridStack 7-widget 布局
│   │   │   ├── IndexLineChart.vue    # ECharts K 线图
│   │   │   ├── SentimentGauge.vue    # 情绪直方图
│   │   │   ├── HotSectors.vue        # 行业风口
│   │   │   ├── NewsFeed.vue          # 新闻瀑布流
│   │   │   ├── StockScreener.vue     # 个股透视看板
│   │   │   └── CopilotSidebar.vue    # AI Copilot
│   │   └── composables/
│   │       └── useMarketStore.js    # 全局状态（symbol 联动）
│   └── vite.config.js               # 端口 60100，/api 代理到 8002
├── docs/
│   ├── dev_log.md                   # 开发日志
│   └── deployment_guide.md           # 部署运维指南
└── README.md
```

---

## 🔌 API 一览

| 方法 | 路由 | 说明 | 响应时间 |
|------|------|------|----------|
| GET | `/health` | 健康检查 | < 1ms |
| GET | `/api/v1/market/overview` | 风向标（上证/沪深300/恒生/纳斯达克） | ~5ms |
| GET | `/api/v1/market/china_all` | 国内 9 只核心指数 | ~5ms |
| GET | `/api/v1/market/global` | 全球 5 大市场指数 | ~5ms |
| GET | `/api/v1/market/sectors` | 真实行业板块（缓存） | **< 3ms** |
| GET | `/api/v1/market/history/{sym}` | K 线历史（分时/日/周/月） | ~10ms |
| GET | `/api/v1/market/sentiment/histogram` | 11 桶情绪直方图 | **< 3ms** |
| GET | `/api/v1/market/stocks` | 个股透视（沪深300） | < 10ms |
| GET | `/api/v1/news/flash` | 快讯新闻（150条） | **< 5ms** |
| GET | `/api/v1/news/detail?url=` | 新闻正文抓取 | ~500ms |

---

## ⚠️ 已知限制与解决方案

| 限制 | 说明 | 解决方案 |
|------|------|----------|
| GFW 封锁 | AkShare/东方财富部分接口需大陆网络 | 配置代理（如 `http://192.168.1.50:7897`）|
| Git push 失败 | git-remote-https（GnuTLS）与代理不兼容 | 使用 REST API 推送，或配置 SSH over `nc -X connect` |
| 市场休市 | 沪深交易所休市时数据停止更新 | 正常现象，数据来源于真实交易所 |
| 全市场覆盖 | 当前沪深 300 约 100 只（熔断优化） | 未来扩展至全市场 5000+ |

---

## 📸 界面预览

```
┌─────────────────────────────────────────────────────────────────────┐
│  📊 AlphaTerminal                      21:37:12 CST  ● LIVE  [☰展开] │
├────────────────────────────────────────────────┬────────────────────┤
│                                                │  🌐 市场风向标       │
│           📈 上证指数 K线（日K）                │  上证  3891.86 -0.80%│
│                                                │  沪深300 4450.05 -0.93%│
│     [K线图 - ECharts 烛台]                    │  恒生  24788.14 +0.15%│
│                                                │  纳斯达克 20794 -0.73%│
│                                                ├────────────────────┤
│                                                │  📊 A股市场情绪      │
├────────────────────────────────────────────────│  [11桶直方图]       │
│  📊 A股市场情绪直方图                          │  涨 15 / 跌 85      │
│  [跌停][<-7%][-7~-5%][-5~-2%][-2~0%][平][0~2%][2~5%][5~7%][>7%][涨停] │
├────────────────────────────────────────────────┤  🔥 行业风口        │
│  🗞️ 快讯新闻                                  │  酿酒行业  +1.23%   │
│  [📈 A股] 创业板ETF成交53亿 证券时报          │  医疗器械 +0.87%    │
│  [🖥️ AI] 百度连获AI基建大单 财中社           │  半导体   +0.54%    │
│  [📰 其他] 三一重工净利增四成 澎湃新闻        │  ...               │
├────────────────────────────────────────────────┴────────────────────┤
│  🔍 全市场个股透视（沪深300）                    [涨跌幅▼][换手率▼] │
│  序号 │ 代码   │ 名称     │ 最新价 │ 涨跌幅  │ 换手率 │ 市场        │
│  ──────────────────────────────────────────────────────────────── │
│   1   │ 600519 │ 贵州茅台 │ 1450.00│  +2.11% │  0.32% │ SH         │
│   2   │ 300750 │ 宁德时代 │  182.50│  +1.87% │  1.24% │ SZ         │
└─────────────────────────────────────────────────────────────────────┘
```

*[界面截图占位符 - 正式发布前请替换为真实截图]*

---

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.11 · FastAPI · APScheduler · SQLite WAL |
| 数据 | AkShare 1.18+ · Sina HQ (qt.gtimg.cn) · 东方财富 |
| 前端 | Vue 3 · Vite 4 · TailwindCSS 3 · ECharts 5 |
| 布局 | GridStack.js 10 · 响应式 Copilot 抽屉 |
| 缓存 | 进程内存（SpotCache / NewsCache / SectorsCache） |

---

## 📄 License

MIT License - 欢迎 fork · star · 提交 PR

---

*AlphaTerminal v0.1.0-beta | 2026-03-31 | https://github.com/deancyl/AlphaTerminal*
