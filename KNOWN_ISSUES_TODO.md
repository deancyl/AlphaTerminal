# KNOWN ISSUES — Beta 0.2.1

> 记录所有已知缺陷，下一步迭代待修复。

---

## 🔴 P0 — 必须修复

### Issue #1：新闻时间戳全部相同（均为 fetch 时间）

**描述**：快讯列表中所有新闻的 `time` 字段值完全一致（如 `2026-03-31 23:01`），而非各条新闻的真实发布时间。

**根因分析**：`stock_news_main_cx`（财新）数据源只返回 `tag`（分类标签）、`summary`（内容摘要）、`url`（链接），**不包含新闻原始发布时间**。当前代码把所有财新快讯的时间统一设为 `datetime.now().strftime("%Y-%m-%d %H:%M")`（fetch 执行时刻），导致全部雷同。

**涉及文件**：`backend/app/services/news_engine.py`（`_do_fetch` 中的财新处理分支）

**修复方向**：
- 方案A：切换回带有时间字段的新闻源（如 `news_economic_baidu` 已损坏，可测试 `news_cctv`）
- 方案B：改用 `stock_news_em` 的个股新闻（包含原始 `发布时间` 字段），叠加财新做标题补充
- 方案C：在 `stock_news_main_cx` 的每条摘要中解析时间信息（如检测「昨日」「今日」等关键词）

---

### Issue #2：前端刷新按钮点击后未触发真实外网抓取

**描述**：用户点击快讯模块右上角刷新按钮后，界面显示「✅ 刚刚更新」，但数据实际未变化（仍为 fetch 时间点的旧数据）。

**根因分析**：`NewsFeed.vue` 的 `fetchNews(quiet = false)` 在手动刷新时应调用 `POST /api/v1/news/force_refresh`，但若 `force_refresh` 的后台线程抓取失败（如代理超时），API 仍返回 200 + 旧缓存数据，前端无法感知差异。

**涉及文件**：
- 前端：`frontend/src/components/NewsFeed.vue`
- 后端：`backend/app/routers/news.py`

**修复方向**：
- 后端 `POST /api/v1/news/force_refresh` 应在抓取失败时返回 `{"error": "...", "items_stale": true}` 字段
- 前端根据 `error` 或 `items_stale` 字段显示不同的错误提示（如「⚠️ 抓取超时，数据可能过期」）
- 前端设置 5s 请求超时，超时后提示用户重试

---

## 🟡 P1 — 建议优化

### Issue #3：Vite Dev Server 在某些网络环境下无法热更新
- **描述**：修改 `.vue` 文件后浏览器未自动刷新
- **修复方向**：检查 `vite.config.js` 中 `server.hmr` 配置

### Issue #4：GitHub Push 因容器 TLS 限制失败
- **描述**：从容器内无法 `git push`（TLS 握手被阻断）
- **修复方向**：需要手动在本地 clone 后 pull，或配置 SSH 密钥

---

## ✅ 已修复（P0→Done）

| 日期 | Issue | 修复方案 |
|------|-------|---------|
| 2026-03-31 | 首屏 `GET /news/flash` 阻塞 10s | lifespan 立即预热，缓存读取降至 <5ms |
| 2026-03-31 | `news_economic_baidu` SSL 失败 | 切换为 `stock_news_main_cx` 财新源 |
| 2026-03-31 | 锁定按钮被网格覆盖 | 移出 `grid-stack` DOM，放入 Navbar |
| 2026-03-31 | Copilot 默认展开 | `isCopilotOpen = ref(false)` |
| 2026-03-31 | force_refresh 后端死代码 | 删除 `news.py` 中 except 后无效 return |

---

_Last Updated: 2026-03-31 by OpenClaw Agent_
