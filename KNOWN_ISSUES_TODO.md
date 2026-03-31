# KNOWN ISSUES & ROADMAP — Beta 0.2.2

> 研发进度表与技术债记录。

---

## ✅ Beta 0.2.2 — 已修复（历史归档）

| 日期 | Issue | 根因 | 修复方案 |
|------|-------|------|---------|
| 2026-03-31 | 时间戳全部相同 | `stock_news_main_cx` 无时间字段，`datetime.now()` 批量造假 | 切换至 `akshare stock_news_em`，提取真实 `发布时间` |
| 2026-03-31 | `_NEWS_CACHE` 永远为空 | `=` rebind 后子进程持有旧引用 | `clear() + extend()` 原地修改 |
| 2026-03-31 | 双引擎竞态写入 | scheduler + sentiment_engine 同时写缓存 | 统一由 `NewsRefresh` 调度，移除重复触发 |
| 2026-03-31 | CORS POST preflight 拦截 | `192.168.2.186:60100` 不在白名单 | CORS 白名单扩展 |
| 2026-03-31 | 首屏 `GET /news/flash` 阻塞 10s | lifespan 延迟 3s 触发 + 同步导入 akshare | lifespan 立即触发 + 后台线程预热 |
| 2026-03-31 | 锁定按钮被 GridStack 覆盖 | 按钮在 `grid-stack` DOM 内部 | 移出至 Navbar `header` 内 |
| 2026-03-31 | Copilot 默认展开 | `isCopilotOpen = ref(true)` | `isCopilotOpen = ref(false)` |

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

## 🟡 P1 — 计划中（Phase 4）

### Feature #1：K线图接入真实日/周/月 K 数据
- **现状**：K线组件存在但数据源不稳定（akshare 指数历史数据接口频繁变动）
- **方向**：测试 `ak.stock_zh_index_daily`（指数日线）+ `ak.stock_zh_a_hist`（个股历史）
- **依赖**：Phase 4.1 数据验证后接入

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
| 高 | Vite 热更新在某些网络下失效 | `vite.config.js` HMR 配置待优化 |
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

---

_Last Updated: 2026-03-31 by OpenClaw Agent_
