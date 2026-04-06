# KNOWN ISSUES & ROADMAP — Beta 0.3.1

> 研发进度表与技术债记录。

---

## ✅ Beta 0.3.1 — 已发布（2026-04-01）

| 日期 | Issue | 根因 | 修复方案 |
|------|-------|------|---------|
| 2026-04-01 | 分时显示 11.xx（平安银行价格） | `secid=0.000001` 指向错误标的 | `_INDEX_SECID_MAP` 精确映射 `000001→1.000001` |
| 2026-04-01 | 月K/周K全空 | `buffer_insert_periodic(,"weekly")` 硬编码覆盖 | 移除第二个参数，动态列名匹配 |
| 2026-04-01 | 风向标垂直留白 | 单列 full-width 垂直堆叠 | `grid grid-cols-2` 两列卡片网格 |
| 2026-04-01 | 行业板块稀缺（仅8个） | 接口返回数据少 | 行业+概念融合 Top 20 + 关键词加权 |
| 2026-04-01 | Header 名称残留 | `currentName` 仅从 props 初始化 | `watch props.symbol` 响应式重置 |
| 2026-04-01 | SSHFS 死锁 | WAL 模式在 FUSE 挂载层卡死 | DB 迁移至 `/home/deancyl0607/alpha_ultimate.db` |
| 2026-04-01 | DB 权限壁垒 | trim.openclaw UID 无写权限 | chmod 666 + DELETE 模式降级 |
| 2026-04-06 | AkShare change_pct 列名差异 | `pct_chg`/`pct_change`/`涨跌幅` 各版本不同 | 改用相邻 close 自主计算 |
| 2026-04-06 | Eastmoney 分时网络不稳定 | subprocess curl 无重试无代理 | 改用 httpx + 重试3次 + 代理 192.168.1.50:7897 |
| 2026-04-06 | DashboardGrid handleWindClick 宏观处理 | macro category 未处理 | 增加 macro 分支，映射至 GOLD |
| 2026-04-06 | K线标题显示残留 | 固定显示「上证指数K线」等 | 统一「指标图表」，增加 currentIndexName 子标题 |
| 2026-04-06 | .gitignore 误追踪 database.db | 35MB live market data 入库 | 移除追踪，加入 .gitignore |

---

## 🔴 P0 — 进行中

### Issue #1：Force Refresh 无差异化错误提示

**描述**：`POST /news/force_refresh` 在抓取失败时仍返回 HTTP 200 + 旧缓存，前端显示"✅ 刚刚更新"但数据实为过期。

**涉及文件**：
- 后端：`backend/app/routers/news.py`
- 前端：`frontend/src/components/NewsFeed.vue`

**修复方向**：
- [ ] 后端返回 `{"error": "...", "items_stale": true, "total": N}`（N=旧缓存条数）
- [ ] 前端检测 `error` 字段，显示红色「⚠️ 抓取失败，显示 {N} 条旧数据」
- [ ] 前端设置 5s 请求超时，超时显示「⚠️ 抓取超时，请检查网络」

---

### Issue #2：全市场个股名称未同步

**描述**：`_SYMBOL_REGISTRY`（`backend/app/routers/market.py` 第 414 行）仅含 5 只示例股，全市场几千只 A 股个股名称缺失。导致前端 CommandCenter 搜索无法找到大多数股票。

**涉及文件**：
- 后端：`backend/app/routers/market.py`（`_SYMBOL_REGISTRY`）
- 前端：`frontend/src/composables/useMarketStore.js`（`symbolRegistry`）

**修复方向**：
- [ ] 方案A（静态）：`akshare stock_info_a_code_name()` 启动时一次性加载全市场 A 股代码+名称，写入 `_SYMBOL_REGISTRY`
- [ ] 方案B（动态）：前端搜索时从 `StockScreener` 全市场行情数据实时匹配名称

---

### Issue #3：分时数据 Bug（未确认根因）

**描述**：前端选择"分时"周期时图表显示错误。dev_log 记录 2026-04-01 已修复，但 2026-04-06 用户仍反馈。

**分析**：
- `_INDEX_SECID_MAP` 在 `fetch_index_minute_history()` 内定义（`data_fetcher.py` 第 661 行）
- 映射：`000001→1.000001`，`399001→0.399001`，`000300→1.000300`，`399006→0.399006`，`000688→1.000688`
- `_MIN_KLINE_SUPPORTED` 在 `market.py` 第 594 行：`{"000001", "000300", "399001", "399006", "000688"}`

**涉及文件**：
- `backend/app/services/data_fetcher.py`（`fetch_index_minute_history`）
- `backend/app/routers/market.py`（`_MIN_KLINE_SUPPORTED`，`clean_sym` 标准化）
- `frontend/src/components/IndexLineChart.vue`（图表渲染）

**修复方向**：
- [ ] 物理验证：前端传 `sh000001` vs `000001` 经 `_clean_symbol()` 后的实际值
- [ ] 验证 Eastmoney API 返回的 klines 数据是否正确

---

## 🟡 P1 — 计划中（Phase 4）

### Feature #1：K线图接入真实日/周/月 K 数据
- **现状**：✅ Beta 0.3.1 已接入 AkShare A股指数历史数据（`stock_zh_index_daily`）
- **方向**：Phase 4.1 测试个股日K（`stock_zh_a_hist`）+ 美股（Alpha Vantage）

### Feature #2：Copilot 与快讯模块上下文打通
- **现状**：CopilotSidebar 是独立面板，无快讯数据传入
- **方向**：将 `newsData` prop 注入 Copilot，支持「分析今日最新快讯」类指令
- **依赖**：Phase 4.2 AI 指令路由设计

### Feature #3：板块/行业数据稳定化
- **现状**：`SectorsCache` 依赖 `akshare` 接口，`industry` 和 `concept` 接口均失败，静态兜底数据为旧数据
- **方向**：接入东方财富行业板块 API 作为主源
- **依赖**：Phase 4.3 代理网络验证

### Feature #4：数据库持久化（SQLite WAL）
- **现状**：所有数据存于内存，重启后需重新拉取
- **方向**：将 `_NEWS_CACHE` + `SpotCache` 定期写入 SQLite，支持启动时加载历史

---

## 📋 技术债

| 优先级 | 项目 | 说明 |
|--------|------|------|
| 高 | 分时数据 Bug 未彻底定位 | 需物理验证 symbol 标准化链路 |
| 高 | 全市场个股名称缺失 | CommandCenter 搜索不可用 |
| 中 | Vite 热更新在某些网络下失效 | `vite.config.js` HMR 配置待优化 |
| 中 | `sentiment_engine.py` 仍有 Sina 来源代码残留 | 旧 `news_economic_baidu` 分支未完全删除 |
| 中 | 单元测试覆盖率为 0 | 建议对 `news_engine.py` 缓存逻辑添加 pytest |
| 低 | `akshare` 无代理时直接失败 | 当前强依赖 `HTTP_PROXY`，断网场景无降级 |

---

## 📅 发布节奏

| 版本 | 目标 | 状态 |
|------|------|------|
| Beta 0.2.0 | 核心 UI + 情绪面板 + 快讯初版 | ✅ 已发布 |
| Beta 0.2.1 | 交互加固（锁定/Copilot） | ✅ 已发布 |
| Beta 0.2.2 | 快讯时间戳修复 + CORS + 竞态消除 | ✅ 已发布 |
| Beta 0.3.0 | Phase 4：K线数据 + Copilot 打通 + 板块稳定化 | 🚧 规划中 |
| Beta 0.3.1 | Phase 5-8 修复 + 分时数据 + ECharts 溢出 | ✅ 已发布（2026-04-01） |

---

## 关键路径速查

| 资源 | 路径 |
|------|------|
| 后端入口 | `backend/start_backend.py`（端口 8002） |
| 前端入口 | `frontend/`（Vite，端口 60100） |
| 数据库 | `/home/deancyl0607/alpha_ultimate.db` |
| 代理 | `http://192.168.1.50:7897` |
| GitHub | https://github.com/deancyl/AlphaTerminal |
| Alpha Vantage API | `https://www.alphavantage.co`（美股数据） |
| Eastmoney 分时 API | `https://push2his.eastmoney.com/api/qt/stock/kline/get` |

---

_Last Updated: 2026-04-06 by OpenClaw Agent_
