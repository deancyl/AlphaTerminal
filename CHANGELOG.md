# Changelog

All notable changes to AlphaTerminal are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.8] - 2026-05-03

### Fixes

- **数据库诊断工具** — 安装sqlite3依赖，修复数据库完整性检查失败的问题
- **Backtest API 500错误** — 修复`backtest_strategies`表不存在时的崩溃，现在返回空列表
- **WebSocket连接失败** — 添加`ws.accept()`修复HTTP 500错误，WebSocket测试现在通过
- **API测试端点** — 更新`api_debug.sh`使用正确的API路径（`/api/v1/news/flash`和`/api/v1/admin/sources/status`）
- **内存优化** — 延迟加载akshare/pandas/numpy，后端内存从334MB降至225MB（节省33%）
- **缓存限制** — 为macro、fund_fetcher、stocks添加缓存过期清理和大小限制
- **Playwright缓存清理** — 清理631MB未使用的Chromium浏览器缓存
- **内存监控** — 添加定时内存监控任务，超过512MB自动执行gc

### Metrics

- **Files changed**: 15
- **Lines changed**: +428 / -128
- **Tests**: 所有110个后端测试通过
- **Debug工具**: 7/7 全部通过

---

## [0.6.7] - 2026-05-03

### Features

- **Debug诊断面板** — 新增系统诊断控制台，集成10个诊断工具：
  - 快速健康检查、API测试、数据库诊断、安全审计
  - 性能分析、WebSocket测试、日志分析、前端调试
  - 支持命令行和Web UI两种方式执行
- **Debug API路由** — 后端新增9个Debug端点：
  - `GET /api/v1/debug/tools` — 获取可用工具列表
  - `POST /api/v1/debug/execute` — 执行诊断工具
  - `GET /api/v1/debug/executions` — 获取执行历史
  - `GET /api/v1/debug/health/aggregate` — 聚合健康状态
  - `GET /api/v1/debug/reports` — 获取报告列表
  - `DELETE /api/v1/debug/reports/{id}` — 删除报告
  - `WS /api/v1/debug/ws` — WebSocket实时通信
  - `GET /api/v1/debug/system/info` — 系统信息
- **管理面板集成** — 前端AdminDashboard新增"Debug诊断"标签页：
  - 健康状态仪表盘（整体/后端/数据库）
  - 诊断工具网格（一键执行）
  - 执行结果展示（JSON格式化输出）
  - 执行历史记录

### Fixes

- **api_debug.sh参数解析** — 修复`--json`被误识别为base URL的问题
- **database_debug.sh路径解析** — 修复SQLite数据库文件查找逻辑，支持多路径搜索
- **quick_check.sh JSON输出** — 修复associative array声明位置导致的JSON生成错误
- **AdminDashboard模板结构** — 修复Vue模板中缺失的结束标签和重复section问题
- **Debug面板初始化** — 添加`onMounted`和`watch`自动加载Debug数据，避免页面卡住

### Documentation

- 更新`AGENTS.md` — 添加完整的Debug工作流文档
- 新增`scripts/debug/README.md` — Debug工具使用说明
- 新增`scripts/debug/WORKFLOW.md` — Debug架构设计文档

### Metrics

- **Files changed**: 32
- **Lines changed**: +5666 / -630
- **Tests**: 110个后端测试全部通过

---

## [0.6.5] - 2025-05-01

### Critical Fixes (P0)

- **DB Export API Stability** — Added `try/except` guards around `PRAGMA table_info` queries in `admin.py` to prevent crashes when referencing non-existent tables (`stock_quotes`, `market_overview`).
- **DB Connection Leak** — Fixed connection leaks in all `admin.py` endpoints by wrapping every SQLite operation in `try/finally: conn.close()` blocks.
- **Chart DOM Contamination** — `FullscreenKline.vue` now properly disposes the ECharts instance (`chart.dispose(); chart = null`) before re-initializing on symbol switch, preventing event leaks and canvas accumulation.
- **Color Inversion Bug** — Fixed `SentimentGauge.vue` where the "交易中" (trading) status was incorrectly styled with green (`text-bearish`) + success background. Now uses `text-theme-accent` for semantic correctness.

### High Priority Fixes (P1)

- **Minute-Bar Timestamp Corruption** — Removed erroneous `* 1000` multiplication in `data_fetcher.py:765` that was corrupting Unix timestamps into millisecond-range values.
- **News Cache Race Condition** — Eliminated dual-thread cache corruption by replacing duplicated news-fetch logic in `sentiment_engine.py` with a single delegation to `news_engine.refresh_news_cache()`. The sentiment engine now reads the unified cache post-refresh instead of writing to it independently.
- **FundFlowPanel ECharts Guard** — Added a lazy `getEcharts()` getter with null-safety check. Prevents `TypeError` when the CDN fails to load.
- **Circuit Breaker Double-Recording** — Removed redundant `cb.record_success()` / `cb.record_failure()` calls in `fetch_with_fallback()`. The `CircuitContext` context manager already handles state transitions automatically.

### Medium Priority Fixes (P2)

- **Timezone-Aware Market Status** — `market_status.py` now uses `datetime.now(ZoneInfo("Asia/Shanghai"))` instead of naive `datetime.now()`, ensuring correct market-open detection regardless of server timezone.
- **Watchdog SIGKILL Safety** — Added `ProcessLookupError` guards and re-validated PID ownership before issuing `SIGKILL`, preventing accidental termination of unrelated processes due to PID recycling.

### Low Priority Fixes (P3)

- **FRED Typo** — Fixed `fRED.stlouisfed.org` → `fred.stlouisfed.org` in `proxy_config.py` `OVERSEAS_HOSTS` frozenset.
- **HTTP Status Codes** — `exception_handlers.py` now returns proper HTTP status codes: `400` for business errors, `422` for validation errors, `500` for unhandled exceptions (previously all returned `200`).
- **ECharts CDN Fallback** — Added `onerror` handler to the CDN `<script>` tag in `index.html`, falling back to `unpkg.com` if `jsdelivr.net` fails.
- **Dead Code Removal** — Removed unused `getCategoryIcon()` function, dead `loading` refs in `NewsFeed.vue` and `StockDetail.vue`, and unused `_SEEN_URL_HASHES` / `_MAX_CACHE_SIZE` variables in `news_engine.py`.

### Metrics

- **Files changed**: 15
- **Lines changed**: +142 / -188 (net -46, cleaner codebase)
- **Build status**: ✅ Vite production build passing (7.26s, 191 modules)
- **Tests**: All existing E2E tests continue to pass

---

## [0.6.4] - 2025-04-28

### UI/UX Improvements

- **Professional Color Scheme** — Replaced cyberpunk aesthetic with muted professional financial terminal colors:
  - Background: `#141414` (neutral dark)
  - Primary accent: `#4a6fa5` (desaturated blue)
  - Text: `#c0c0c0` (soft gray)
  - Removed all `backdrop-blur` and glow effects
- **NewsFeed Refactor** — Complete redesign:
  - Removed duplicate sentiment summary panel
  - Fixed duplicate `sentimentBadgeClass` declaration
  - 2-row list layout (time+tag → title)
  - Compressed item density (`py-1.5`, `gap-1`)
  - Corrected bullish/bearish color mappings (red=up, green=down)
  - Removed all emoji from UI
  - Merged category + sentiment filters into single scrollable row
- **Mobile Navigation Deduplication** — Removed redundant mobile Sidebar; `MobileBottomNav` is now the sole mobile navigation component.
- **Responsive Design** — Mobile-bottom-nav "More" menu, `PortfolioDashboard` grid fixes, `FundDashboard`, `AdminDashboard`, `BacktestDashboard` mobile adaptations.

### Build & CI

- **Vue Compiler Fixes** — Fixed `App.vue` brace mismatch and `FundDashboard.vue` duplicate `class` attributes.
- **GitHub Actions** — Frontend CI and E2E Integration Tests both passing (38/38 tests).
- **Tailwind Standardization** — Batch-replaced 153× `text-[9px]` → `text-[10px]`, unified shadow classes to `shadow-sm`.

---

## [0.6.0] - 2025-04-25

### Major Features

- **Wind Terminal-Inspired UI** — Complete visual overhaul following Wind (万德) terminal design spec v1.0:
  - Color convention: Red = Bullish/Up, Green = Bearish/Down (Chinese A-share standard)
  - High-density data presentation
  - Professional typography and spacing
- **Sidebar Redesign** — Collapsible 64px icon mode / 220px expanded mode, Escape key support.
- **StatusBar Component** — New 24px footer with connection status, refresh timestamp, and market open indicator.
- **One-Click Start Scripts** — `start.sh` (Linux/macOS) and `start.ps1` (Windows) for automated environment setup and service launch.

### Infrastructure

- **GitHub Actions CI/CD** — Added `.github/workflows/e2e-test.yml` with Playwright E2E testing.
- **Documentation** — Updated `README.md` and added `docs/DEV_SETUP.md`.

---

## [0.5.187] - 2025-04-20

### Previous Beta Release

- Initial public beta with core market data, news, sentiment analysis, and portfolio tracking.
- GridStack-based dashboard layout.
- Real-time WebSocket data streaming.

[0.6.5]: https://github.com/deancyl/AlphaTerminal/compare/v0.6.4...v0.6.5
[0.6.4]: https://github.com/deancyl/AlphaTerminal/compare/v0.6.0...v0.6.4
[0.6.0]: https://github.com/deancyl/AlphaTerminal/compare/v0.5.187...v0.6.0
[0.5.187]: https://github.com/deancyl/AlphaTerminal/releases/tag/v0.5.187
