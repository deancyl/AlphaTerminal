# Changelog

All notable changes to AlphaTerminal are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.18] - 2026-05-10

### Code Quality Improvements

- **API Response Format Standardization** — Converted `portfolio.py` and `backtest.py` to use standard `success_response/error_response` format from `utils/response.py`
  - 42 endpoints in portfolio.py now use consistent response format
  - 15 endpoints in backtest.py now use consistent response format
  - Eliminated manual `{"code": 0, ...}` construction

- **Exception Handling Improvements** — Added specific exception types before generic `Exception` fallback in 46 blocks across 7 production files:
  - `portfolio.py`: 20 blocks (sqlite3.IntegrityError, OperationalError, ValueError, TypeError, KeyError, ZeroDivisionError)
  - `f9_deep.py`: 18 blocks (KeyError, ValueError, TypeError, AttributeError)
  - `main.py`: 2 blocks (ImportError, AttributeError, SyntaxError)
  - `mcp.py`: 1 block (asyncio.CancelledError)
  - `agent_auth.py`: 1 block (AttributeError, KeyError, ValueError, TypeError)
  - `notification_service.py`: 2 blocks (ValueError, KeyError)
  - `market_status.py`: 2 blocks (KeyError for timezone operations)

### Metrics

- **Files changed**: 8
- **Lines changed**: +399 / -120
- **Exception blocks improved**: 46
- **API endpoints standardized**: 57

---

## [0.6.17] - 2026-05-10

### Audit & Code Quality

- **Comprehensive Platform Audit** — Completed full audit comparing AlphaTerminal to professional platforms (Bloomberg/Wind/TradingView), identifying 47 gaps across 6 categories
- **Code Quality Evaluation** — Overall score 50/100, identified 204 hours of technical debt remediation needed
- **Documentation Created** — Added comprehensive audit documents in `docs/` folder

### Fixes

- **Bare Except Blocks (P0)** — Fixed 10 bare `except:` blocks in `stocks.py`, `portfolio.py`, `market.py`, `compiler.py`, replaced with specific exception types `(ValueError, TypeError)`
- **success_response Consolidation (P0)** — Removed 8 duplicate `success_response()` definitions from routers, consolidated to single import from `utils/response.py`, reducing ~120 lines of duplicate code
- **Circuit Breaker Application (P0)** — Applied circuit breaker pattern to all 6 data sources in `quote_source.py`:
  - Tencent (failure_threshold=5, recovery_timeout=30s)
  - Sina (failure_threshold=5, recovery_timeout=30s)
  - Sina Kline (failure_threshold=5, recovery_timeout=30s)
  - Eastmoney (failure_threshold=3, recovery_timeout=60s)
  - Tencent HK (failure_threshold=5, recovery_timeout=30s)
  - Alpha Vantage (failure_threshold=3, recovery_timeout=120s)
- **SQL Injection Review (P0)** — Verified all 9 f-string SQL usages are safe (using parameterized queries)
- **ARIA Accessibility (P1)** — Added ARIA attributes to critical navigation components (`Sidebar.vue`, `CommandPalette.vue`)

### Features

- **Circuit Breaker Status API** — Added `/api/v1/market/source/circuit-breaker` endpoint for monitoring circuit breaker status

### Documentation

- `docs/COMPREHENSIVE_AUDIT_SUMMARY.md` — Full audit summary with scores and priority matrix
- `docs/GAP_ANALYSIS.md` — 47 gaps vs professional platforms
- `docs/COORDINATION_ANALYSIS.md` — Frontend-backend coordination issues
- `docs/HIGH_AVAILABILITY_ARCHITECTURE.md` — Data source reliability design
- `docs/IMPLEMENTATION_ROADMAP.md` — HA implementation plan
- `PROFESSIONAL_FEATURE_GAP_ANALYSIS.md` — Regulatory compliance gaps

### Metrics

- **Files changed**: 15
- **Lines changed**: +200 / -150
- **Code reduction**: ~120 lines from duplicate removal
- **Critical fixes**: 4 P0 issues resolved

---

## [0.6.11] - 2026-05-07

### Fixes

- **基金港股名称显示** — 修复港股代码位数问题（zfill(5) for HK, zfill(6) for A-share），添加 HK_STOCK_NAMES 映射表
- **A股名称查询修复** — 修复 _get_stock_names 重复加前缀和 key 不匹配问题
- **移动端主题切换** — 手机版添加主题切换按钮，隐藏无效的侧边栏按钮
- **快讯移动端优化** — 手机版快讯每页显示10条，移除 max-height 限制
- **涨跌百分比精度** — 修复浮点误差，统一下跌百分比显示为小数点后2位

## [0.6.10] - 2026-05-06

### Fixes

- **按钮高度修复** — 修复顶部状态栏 AI 按钮、锁定按钮及全屏按钮垂直高度过高问题，添加 `btn-xs` CSS 类使小按钮不受触控热区最小高度规则约束（桌面端 44px / 移动端 48px）
- **移动端触控例外** — `style.css` 中为移动端（`pointer: coarse`）媒体查询添加小按钮例外规则，与桌面端保持一致
- **指标图表全屏按钮** — 重新设计 IndexLineChart 全屏按钮，统一桌面端和移动端样式，移除不必要的 `isMobile` 逻辑
- **DashboardGrid 全屏按钮** — 精简样式，去掉 emoji 图标，统一为文字按钮

### Features

- **Copilot 两级模型选择器** — Provider → Model 二级选择，支持 DeepSeek/硅基流动/通义千问/OpenAI/OpenCode/MiniMax
- **Copilot 对话历史持久化** — 对话记录存入 SQLite `copilot_conversations` 表，支持 session 续接
- **数据源探测增强** — 增强数据源健康检查和管理能力

### Fixes

- **Copilot MiniMax 配置统一** — 修复 opencode 检测逻辑，配置来源统一为 DB > .env > 默认值
- **后台管理面板修复** — 修复多处 AdminDashboard 模板结构问题
- **快讯浏览器打开按钮** — 修复 NewsFeed 浏览器打开按钮报错问题
- **Debug 工具卸载** — 卸载所有 Debug 诊断工具及相关组件，简化代码库

### Refactor

- **启动脚本优化** — start-services.sh 重构，增强错误处理和日志记录

### Metrics

- **Files changed**: 25
- **Lines changed**: +402 / -4363
- **主要变更**: 移除 debug 目录（-700+ 行），Copilot 功能增强，AdminDashboard 精简

---

## [0.6.8] - 2026-05-03

### Fixes

- **Backtest API 500错误** — 修复`backtest_strategies`表不存在时的崩溃，现在返回空列表
- **WebSocket连接失败** — 添加`ws.accept()`修复HTTP 500错误
- **内存优化** — 延迟加载akshare/pandas/numpy，后端内存从334MB降至225MB（节省33%）
- **缓存限制** — 为macro、fund_fetcher、stocks添加缓存过期清理和大小限制
- **Playwright缓存清理** — 清理631MB未使用的Chromium浏览器缓存
- **内存监控** — 添加定时内存监控任务，超过512MB自动执行gc

### Metrics

- **Files changed**: 15
- **Lines changed**: +428 / -128
- **Tests**: 所有110个后端测试通过

---

## [0.6.7] - 2026-05-03

### Fixes

- **AdminDashboard模板结构** — 修复Vue模板中缺失的结束标签和重复section问题

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
