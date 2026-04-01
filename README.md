# AlphaTerminal

<div align="center">

# 📊 AlphaTerminal — 本地化 AI 智能投研沙盒终端

**高性能 · 高密度 · 可联动 · 完全开源**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Vue.js](https://img.shields.io/badge/Vue-3.5-green.svg)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-blue.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Release](https://img.shields.io/badge/Release-Beta%200.3.1-orange.svg)](https://github.com/deancyl/AlphaTerminal/releases/tag/Beta-0.3.1)

*"让每一位个人投资者，都拥有一座专业的投研数据堡垒。"*

</div>

---

## 🎯 项目简介

AlphaTerminal 是一款**完全本地运行**的高性能金融投研终端，汇聚全市场数据、A 股情绪图谱、机构级新闻引擎与 AI Copilot 助手于一身。

不同于传统终端依赖付费数据源，AlphaTerminal 全部基于免费开源数据（AkShare、东方财富、Sina HQ），配合本地 SQLite 缓存与后台增量刷新，实现**零成本、零外部依赖、毫秒级响应**的专业级体验。

---

## ⚡ 核心特性

### 1. 毫秒级全市场数据底座
- **多周期 K 线**：分时 / 日K / 周K / 月K，完整 OHLCV 数据
- **全市场覆盖**：A股（沪深300+重点蓝筹）、港股、美股、日经、恒生
- **实时刷新**：后台 APScheduler 每 3 分钟增量拉取，API 响应 **< 5ms**

### 2. 机构级高密度数据面板
- **市场情绪直方图**：11 个涨跌区间桶（跌停 → 涨停），实时统计上涨/下跌家数
- **沪深 300 个股透视**：按涨跌幅/换手率/成交额排序，支持分页浏览
- **行业风口**：真实行业板块（AkShare 数据），而非用指数冒充行业

### 3. 真实时间戳快讯引擎
- **主源**：`akshare stock_news_em`（东方财富，**真实发布时间字段**），150 条/次
- **宏观+个股双通道**：13 只核心指数/行业标的 + 20 只重点股票
- **强制刷新**：`POST /api/v1/news/force_refresh` 穿透外网，真实抓取最新数据
- **MD5 URL 去重**：进程内存缓存，保留最新 200 条，**严格倒序排列**

### 4. 响应式 AI Copilot 侧边栏
- **默认收起**，点击「🤖 展开 AI 助理」滑出 340px 抽屉
- 支持市场数据分析、标的推荐、事件影响解读

### 5. GridStack 交互加固
- **默认网格锁定**：防止移动端误拖拽
- **NavBar 一键切换**：🔒 已锁定（琥珀色）/ 🔓 可拖拽（绿色）

---

## 🏗 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                    前端 (Vite Dev Server)                │
│              http://localhost:60100  (Web UI)            │
│         Vue 3 + TailwindCSS + GridStack 12列           │
└─────────────────────┬───────────────────────────────────┘
                      │ proxy /api/* → :8002
┌─────────────────────▼───────────────────────────────────┐
│                  后端 (FastAPI)                          │
│              http://0.0.0.0:8002  (API Only)             │
│                                                           │
│  /api/v1/market/overview   /api/v1/news/flash           │
│  /api/v1/news/force_refresh  /api/v1/debug/scheduler     │
│                                                           │
│  APScheduler 调度任务（后台线程）                         │
│  ├── NewsRefresh (每20分钟) ←─ stock_news_em 真实抓取    │
│  ├── AkShareDataFetch (每3分钟)                         │
│  └── SentimentFetch (每3分钟)                            │
│                                                           │
│  ┌──────────────────────────────────────────────┐        │
│  │  _NEWS_CACHE (进程内全局列表)                │        │
│  │  clear() + extend() 原地修改，线程安全       │        │
│  └──────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────┘
                      │
                      ▼
         ┌──────────────────────────┐
         │  AkShare / 东方财富 / Sina HQ │
         │  HTTP_PROXY: 192.168.1.50:7897  │
         └──────────────────────────┘
```

---

## 🆕 Beta 0.2.2 里程碑（2026-03-31）

| 指标 | 修复前 | Beta 0.2.2 |
|------|--------|-------------|
| `GET /news/flash` 响应 | ~10s（阻塞） | **< 5ms**（缓存读取） |
| 新闻时间戳 | 全部相同（`datetime.now()` 造假） | **真实发布时间字段** |
| 双引擎竞态 | 两个线程同时写缓存互相覆盖 | **单一 NewsRefresh 调度** |
| 缓存引用失效 | `=` rebind 导致子进程读不到 | **in-place `clear()+extend()`** |
| CORS POST 拦截 | 跨域 preflight 返回 200 但浏览器拦截 | **正确白名单** |
| Navbar 锁定按钮 | 游离在 GridStack 内部被覆盖 | **融入 Navbar 状态栏** |
| Copilot 默认状态 | 默认展开 | **默认收起** |

------

## 🆕 Beta 0.2.3 里程碑（2026-04-01）

| 指标 | 修复前 | Beta 0.2.3 |
|------|--------|-------------|
| 前端合并排序 | `[...newItems,...items]` 无全局重排 | **`.sort((a,b)=>b.time.localeCompare(a.time))` 强制倒序** |
| 刷新提示文案 | 静态"刚刚更新" | **动态`✅ 获取到 N 条（来源: 证券时报网）`** |
| 刷新频率 | 20 分钟 | **5 分钟** |
| 快讯情感联动 | 快讯仅展示，无情绪分析 | **Phase 4：关键词扫描 + 全局情感缓存** |
| `/market/sentiment/histogram` | 仅股票直方图 | **附带 `news_sentiment` 字段** |
| `/market/sentiment/news` | 无此接口 | **新增：返回 `{score, label, bullish_count, bearish_count, keywords}`** |

### Phase 4：快讯情感联动机制

```
force_refresh 抓取完成
    ↓
_analyze_news_sentiment(final)  [sentiment_engine.py]
    ↓
关键词扫描: 利好(暴涨/涨停/增持...) vs 利空(暴跌/黑天鹅/债务违约...)
    ↓
更新 _NEWS_SENTIMENT 全局缓存
    ↓
GET /market/sentiment/histogram → 附带 news_sentiment
GET /market/sentiment/news     → 独立情感端点
```

---

## 🆕 Beta 0.3.1 里程碑（2026-04-01）

> Phase 5-8 精准增量合入，修复 SSHFS 死锁 + ECharts 溢出 + 国内指数归零

| 指标 | 修复前 | Beta 0.3.1 |
|------|--------|-------------|
| SSHFS 死锁 | SQLite 在 FUSE 网络盘上卡死 | **DB 迁移至 `/home/deancyl0607/alpha_ultimate.db`** |
| Wind 指数 | 仅 4 条（缺深证/创业板）| **Wind 6 指数：000001/000300/399001/399006/HSI/IXIC** |
| ECharts 溢出 | BondDashboard/FuturesDashboard 图表溢出 | **`overflow-hidden relative` + `min-h-0` 约束** |
| `_parse_sina_index` | `len < 10` 拒绝 6 字段 Sina 数据 | **`len < 6` 修正，parts[3] 直接作为 chg_pct** |
| data_sources 注册表 | 无统一数据源配置 | **`app/config/data_sources.py` 完整注册表** |
| bond/futures 路由 | Phase 7 路由骨架 | **完整 Mock + 真实接口降级** |
| RLock 死锁 | 嵌套 `Lock.acquire()` 死锁 | **`threading.RLock()` 可重入锁** |

### Phase 5-8 Cherry-pick 时间线

```
f87ea20  Phase 5: RLock 死锁修复 + 风向标 8 标的
3f46a2d  Phase 6: BondDashboard + FuturesDashboard + Sidebar active
773402f  Phase 7: bond/futures 路由 + 宏观数据 ECharts 骨架
fe688ed  Phase 7P0: VHSI 真实数据 + 热力图塌陷修复
16dda82   Phase 8: ECharts 溢出 + _parse_sina_index + data_sources.py
0125dca  精准增量合入 commit
```

## 🚀 快速启动

```bash
# 后端（端口 8002）
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8002

# 前端（端口 60100，另一终端窗口）
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 60100
```

访问：`http://localhost:60100`

---

## 📂 项目结构

```
AlphaTerminal/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口 + CORS + lifespan
│   │   ├── routers/
│   │   │   ├── news.py         # /news/flash + /news/force_refresh
│   │   │   ├── debug.py        # /debug/scheduler
│   │   │   ├── market.py       # /market/overview 等
│   │   │   └── sentiment.py    # 市场情绪
│   │   └── services/
│   │       ├── news_engine.py  # 进程内新闻缓存（_NEWS_CACHE）
│   │       ├── sentiment_engine.py
│   │       └── scheduler.py    # APScheduler 调度
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── App.vue              # Navbar：锁定按钮 + Copilot 开关
│       └── components/
│           ├── DashboardGrid.vue  # GridStack 网格（接受 isLocked prop）
│           └── NewsFeed.vue      # 快讯（POST force_refresh）
├── docs/
│   ├── deployment_guide.md       # 运维部署手册
│   └── WIKI_ARCHITECTURE.md    # 核心模块技术维基
├── KNOWN_ISSUES_TODO.md         # 缺陷追踪 + Phase 4 路线图
└── README.md                    # 本文件
```

---

## 📜 许可

MIT License · 欢迎 Star & Fork
