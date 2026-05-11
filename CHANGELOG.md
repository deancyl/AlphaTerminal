# Changelog

All notable changes to AlphaTerminal are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.28] - 2026-05-11

### Bug Fixes

- **AlertManager Widget Removed** — Removed price alert module from DashboardGrid
  - User requested removal due to awkward UI placement
  - Widget completely removed from mobile and desktop layouts

- **Layout Mode Toggle Removed** — Removed "专业/简洁" buttons from status bar
  - User requested removal as feature was not necessary
  - All widgets now always display (no simple/advanced mode distinction)

- **Conservation API Fixed** — Fixed portfolio audit "获取失败" error
  - Changed from querying `positions` table to `position_summary` table
  - Uses pre-calculated `market_value` when available
  - Properly handles lot-based portfolio system

- **Mobile Swipe Navigation Fixed** — Fixed swipe navigation order for fund module
  - Updated VIEW_ORDER to match MobileBottomNav visual order
  - Fund module now accessible via swipe: stock → fund → bond → futures

- **Chrome Pull-to-Refresh Conflict Fixed** — Added `overscroll-behavior: contain`
  - Prevents Chrome's native pull-to-refresh from interfering
  - Custom pull-to-refresh now works correctly on mobile

### Technical Details

- Conservation API now uses `position_summary` aggregation table
- Swipe navigation order: `['stock', 'fund', 'bond', 'futures', 'portfolio', 'macro']`
- Mobile container CSS updated with overscroll behavior

---

## [0.6.27] - 2026-05-11

### Bug Fixes

- **ETF Data Compatibility** — Fixed ETF data fetching with improved column name handling
  - Added `get_col_val()` helper function for flexible column name lookup
  - Support for Chinese/English column names (open/开盘, high/最高, low/最低, close/收盘, volume/成交量, amount/成交额)
  - Resolves issues with AkShare returning different column names for ETFs vs stocks

- **Production Domain Configuration** — Added `allowedHosts` for production domain in `vite.config.js`
  - Supports `finance.deancylnextcloud.eu.org` domain

### Code Quality

- **Comprehensive Quality Audit Completed**
  - Backend code quality assessment (100+ Python files)
  - Frontend code quality assessment (96 Vue components)
  - API design patterns review (21 routers)
  - Test coverage analysis (19% router coverage, 16% service coverage)
  - Configuration and infrastructure audit

### Security Findings (Require Attention)

- ⚠️ Hardcoded API keys detected in `scripts/fetch_historical_data.py` and test files
- ⚠️ SQL injection risk in `admin.py` dynamic table queries
- ⚠️ No TypeScript configuration (frontend uses plain JavaScript)

### Test Coverage Summary

| Category | Files | Coverage |
|----------|-------|----------|
| Backend Routers | 21 | 19% (4 tested) |
| Backend Services | 49 | 16% (8 tested) |
| Frontend Components | 30+ | 17% (5 tested) |

### Technical Details

- Added safe column value extraction with fallback support
- Improved error handling for missing columns
- Minor UI fixes in IndexLineChart and SentimentGauge components

---

## [0.6.26] - 2026-05-10

### Bug Fixes (Critical)

- **Duplicate health() Function** — Fixed duplicate `health()` function definition in `main.py`
  - Removed unreachable code at lines 223-234
  - Only one health endpoint now exists (decorated with `@app.get("/health")`)

### Code Quality Improvements

- **DEBUG-CYCLE Logs Removal** — Removed 38 debug console.log statements from 7 Vue files
  - App.vue: 2 logs removed
  - Sidebar.vue: 5 logs removed
  - AgentTokenManager.vue: 2 logs removed
  - WalkForwardPanel.vue: 7 logs removed
  - PerformanceAnalyzer.vue: 5 logs removed
  - MCPConfigDashboard.vue: 12 logs removed
  - StrategyCenter.vue: 5 logs removed

- **Formatting Functions Consolidation** — Consolidated duplicate formatting functions
  - Added `formatNumber`, `formatMoney`, `formatVolume`, `formatHolderShares`, `formatHolderPct` to `utils/formatters.js`
  - Updated `useStockDetail.js` to import from formatters.js
  - Updated `f9/InfoCard.vue` to import from formatters.js
  - Removed duplicate function definitions

### WebSocket Protocol Improvements

- **Message Type Field** — Added `"type": "tick"` to WebSocket broadcast messages
  - Makes protocol self-documenting
  - Consistent with other message types (`"subscribed"`, `"pong"`)
  - Updated `ws_manager.py` to include type field in broadcasts

- **Symbol Case Handling** — Improved symbol case consistency
  - Backend now properly normalizes symbols
  - Frontend receives consistent symbol format

### Metrics

- **Lines removed**: 391 (debug logs, duplicate code)
- **Lines added**: 97 (consolidated functions, WebSocket improvements)
- **Net reduction**: 294 lines
- **Files modified**: 14

---

## [0.6.25] - 2026-05-10

### Code Refactoring (P1-018)

- **CopilotSidebar Split** — Split CopilotSidebar.vue (1228 lines) into composables and subcomponents
  - **Composables** (6 files, 631 lines):
    - `useCopilotMarkdown.js` (53 lines): Markdown rendering with XSS prevention
    - `useCopilotCache.js` (36 lines): Response cache with 5-min TTL
    - `useCopilotData.js` (88 lines): Market data fetching wrappers
    - `useCopilotCommands.js` (124 lines): Command parsing logic
    - `useCopilotStock.js` (60 lines): Stock operations
    - `useCopilotChat.js` (170 lines): LLM chat with SSE streaming
  - **Subcomponents** (5 files, 204 lines):
    - `CopilotHeader.vue` (17 lines): Title section
    - `CopilotQuickCommands.vue` (23 lines): Quick command buttons
    - `CopilotContextSelector.vue` (80 lines): Context checkboxes + model selectors
    - `CopilotMessageList.vue` (44 lines): Message history display
    - `CopilotInput.vue` (40 lines): Input textarea + send button
  - **Styles**: Extracted markdown CSS to `copilot-markdown.css` (100 lines)

- **Main Component Reduction** — CopilotSidebar.vue reduced from 1228 to 296 lines (76% reduction)
  - All functionality preserved
  - No breaking changes to props/emits
  - Build verified successful

### Metrics

- **Original file**: 1228 lines
- **New modules**: 935 lines (composables + subcomponents + CSS)
- **Main component**: 296 lines
- **Files created**: 12

---

## [0.6.24] - 2026-05-10

### Code Refactoring (P1-018)

- **Market Module Split** — Split market.py (1869 lines) into 8 domain modules
  - `overview.py`: Market overview, macro data (5 endpoints, 552 lines)
  - `quotes.py`: Quote, quote_detail, order_book (4 endpoints, 432 lines)
  - `history.py`: Price history, futures (2 endpoints, 256 lines)
  - `symbols.py`: Symbol registry, search (5 endpoints, 289 lines)
  - `sectors.py`: Sector data (2 endpoints, 47 lines)
  - `source.py`: Data source management (10 endpoints, 159 lines)
  - `system.py`: System info (2 endpoints, 81 lines)
  - `dependencies.py`: Shared utilities, caches, constants (650+ lines)

- **Router Aggregation** — `__init__.py` combines all sub-routers
  - All 33 endpoints preserved
  - No breaking changes to API routes

### Metrics

- **Original file**: 1869 lines
- **New modules**: ~2500 lines (better organized)
- **Endpoints preserved**: 33
- **Files created**: 9

---

## [0.6.23] - 2026-05-10

### Code Refactoring (P1-018)

- **Portfolio Module Split** — Split portfolio.py (2206 lines) into 6 domain modules
  - `accounts.py`: Portfolio CRUD (3 endpoints, 103 lines)
  - `positions.py`: Position management + PnL (7 endpoints, 594 lines)
  - `analytics.py`: Attribution, performance, risk (4 endpoints, 791 lines)
  - `cash.py`: Cash operations, transfers (6 endpoints, 173 lines)
  - `lots.py`: Lot trading, conservation (9 endpoints, 499 lines)
  - `schemas.py`: Pydantic models (9 classes, 114 lines)
  - `dependencies.py`: Helper functions (8 functions, 275 lines)

- **Router Aggregation** — `__init__.py` combines all sub-routers
  - All 29 endpoints preserved
  - No breaking changes to API routes
  - Better code organization and maintainability

### Metrics

- **Original file**: 2206 lines
- **New modules**: 2573 lines (better organized)
- **Endpoints preserved**: 29
- **Files created**: 8

---

## [0.6.22] - 2026-05-10

### Error Handling (P1-014)

- **useApiError Composable** — Unified error handling across all components
  - Created `useApiError.js` with `handleError`, `wrapApiCall`, `errorState`
  - Auto-classifies errors by type (network, timeout, server, client, validation)
  - Optional toast notifications and retry support
  - Centralized error reporting

- **Enhanced errorHandler.js** — Added utility functions
  - `isRetryable(error)` — Determines if error should be retried
  - `formatErrorForUser(error, context)` — Context-aware user messages

- **Component Refactoring** — Adopted useApiError in:
  - StockDetail.vue (7 error handlers)
  - MacroDashboard.vue (10 error handlers)

### Retry Mechanism (P1-015)

- **Jitter in Exponential Backoff** — Prevents thundering herd
  - ±25% random jitter on retry delays
  - Base delay: 500ms, max delay: 8000ms

- **Per-Endpoint Retry Config** — `retryConfig.js`
  - Macro endpoints: 2-3 retries, 30s timeout
  - Market endpoints: 1-2 retries, 10s timeout
  - F9 endpoints: 2 retries, 15s timeout
  - Backtest: 0 retries, 60s timeout

### WebSocket Reconnection (P1-016)

- **Manual Reconnect** — User-triggered reconnection
  - `manualReconnect()` function in useMarketStream
  - Resets retry count and delay
  - Clean disconnect before reconnect

- **Connection Stats** — Enhanced monitoring
  - `lastConnectedAt` timestamp
  - `connectionAttempts` counter
  - Exposed via `getStats()`

- **StatusBar Enhancements** — Visual feedback
  - Reconnect button when disconnected
  - Connection duration display
  - Retry count tooltip

### Data Validation (P1-017)

- **Zod Integration** — Schema validation library
  - Installed zod package
  - Type-safe API response validation

- **Schema Definitions** — Created schemas for:
  - Stock quotes, market overview, sectors
  - Portfolio holdings and summary
  - Macro indicators and time series

- **apiFetchValidated()** — Validated API calls
  - Automatic schema validation
  - Detailed error messages on validation failure
  - Type inference from schemas

### Metrics

- **Error handling**: 1 composable, 2 utility functions, 2 components refactored
- **Retry improvements**: Jitter + per-endpoint config
- **WebSocket enhancements**: Manual reconnect + connection stats
- **Validation**: 4 schema files, 1 validated fetch function
- **Lines added**: 630

---

## [0.6.21] - 2026-05-10

### Mobile/Desktop Optimizations

- **Swipe Navigation** — Added touch swipe gestures for mobile
  - Created `useSwipe` composable for left/right swipe detection
  - Integrated with App.vue for view navigation
  - Threshold: 50px minimum swipe distance

- **Hardware Back Button** — Android back button support
  - History management with `popstate` event listener
  - Back button closes modals, exits fullscreen, navigates views
  - Proper cleanup on component unmount

- **Pull-to-Refresh** — DashboardGrid refresh gesture
  - Created `usePullToRefresh` composable
  - Visual feedback with loading indicator
  - Threshold: 80px pull distance

- **Layout Persistence** — GridStack layout saved to localStorage
  - Auto-saves on every layout change
  - Auto-restores on component mount
  - Key: `dashboard_grid_layout`

- **Bundle Size Optimization** — Lazy loading and code splitting
  - Created `lazyEcharts.js` utility for dynamic ECharts import
  - Lazy loaded components: TrendChart, InstitutionalHoldings, MarginTrading, PeerComparison
  - Reduced initial bundle size by ~30%

### New Components

- **LayoutPanel** — Admin dashboard layout configuration panel
  - GridStack layout preview and reset functionality
  - Integration with AdminDashboard

### Metrics

- **Mobile features**: 4 (swipe, back button, pull-to-refresh, persistence)
- **Performance improvements**: 1 (bundle optimization)
- **New files**: 4 (useSwipe, usePullToRefresh, lazyEcharts, LayoutPanel)
- **Lines added**: 876

---

## [0.6.20] - 2026-05-10

### Security

- **XSS Prevention** — Added DOMPurify sanitization for all v-html content
  - CopilotSidebar: LLM markdown output sanitized
  - DrawingToolbar: SVG icons sanitized
  - Installed dompurify npm package

### Data Source Reliability

- **AkShare Circuit Breaker** — Added circuit breaker protection for all AkShare calls
  - 3 consecutive failures → circuit OPEN
  - 60 second recovery timeout
  - Graceful degradation with HTTP 503 when unavailable

- **CircuitBreaker Consolidation** — Removed duplicate implementation
  - Single source of truth in `services/circuit_breaker.py`
  - Deleted `fetchers/circuit_breaker.py` (161 lines eliminated)
  - Updated all imports to use consolidated implementation

### Frontend-Backend Coordination

- **F9 Symbol Format Fix** — F9 endpoints now accept both formats
  - `sh600519` and `600519` return same data
  - Added `normalize_f9_symbol()` helper to strip prefixes
  - Applied to all 7 F9 endpoints

### Accessibility (WCAG 2.1)

- **Focus Trap in Modals** — Implemented WAI-ARIA focus management
  - Tab cycles within modal only
  - Escape closes modal
  - Focus returns to trigger element
  - Added to NewsFeed, SimulatedTradeModal, BondHistoryModal

- **ARIA Navigation** — Enhanced StockDetail tab navigation
  - Added `role="tablist"` and `role="tab"` attributes
  - Implemented arrow key navigation
  - Added `aria-selected` state binding

- **Touch Target Sizes** — Increased to 44px minimum
  - Fixed period/indicator buttons in FullscreenKline
  - Fixed more menu buttons in MobileBottomNav
  - All interactive elements now meet WCAG 2.1 guidelines

### Metrics

- **Security fixes**: 1 (XSS prevention)
- **Data source improvements**: 2 (circuit breaker + consolidation)
- **Accessibility fixes**: 3 (focus trap, ARIA, touch targets)
- **Coordination fixes**: 1 (symbol format)
- **Lines eliminated**: ~161 (duplicate code)

---

## [0.6.19] - 2026-05-10

### Code Quality Improvements

- **Exception Handling in Test Files** — Added specific exception types in 22 blocks across 5 test files
  - `test_data_validation.py`: ValidationError, ValueError handlers
  - `test_integration.py`: AssertionError, KeyError, ValueError handlers
  - `test_data_cache.py`: RuntimeError handlers
  - `test_agent_db.py`: sqlite3.Error handlers
  - `test_normalization.py`: URLError, HTTPError, JSONDecodeError handlers

### Accessibility (ARIA)

- **ARIA Attributes Added** — Added accessibility attributes to 14 Vue components
  - Interactive controls: MobileBottomNav, ContextMenu, SimulatedTradeModal, BondHistoryModal
  - Data display: DataTable with sortable headers
  - Status components: ToastContainer, LoadingSpinner, ErrorDisplay, ErrorBoundary
  - Navigation: DashboardGrid, BacktestDashboard, StockScreener, AlertManager

### Component Refactoring

- **StockDetail.vue Split** — Refactored from 1688 lines to modular structure
  - Created 8 tab components in `stock-detail/` directory
  - Extracted shared logic to `useStockDetail.js` composable
  - Main component reduced to 377 lines (orchestrator only)

- **AdminDashboard.vue Split** — Refactored into 10 panel components
  - Created panel components in `admin/` directory
  - Added AgentTokensPanel and McpPanel for inline sections
  - Fixed missing `</ul>` tag in MonitorPanel

- **DrawingCanvas.vue Split** — Refactored from 1367 lines to composables
  - Created 4 composables: useDrawingState, useDrawingRenderer, useDrawingEvents, useDrawingStorage
  - Main component reduced to ~420 lines
  - All 11 drawing tools and magnet mode preserved

### Metrics

- **Files changed**: 45
- **New files created**: 22
- **Exception blocks improved**: 68 (46 production + 22 test)
- **Components refactored**: 3 large components split
- **ARIA components**: 14

---

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
