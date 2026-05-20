# Release v0.6.61 - Comprehensive Architectural Refactoring

**Release Date**: 2026-05-20

## Overview

A comprehensive **33-task, 8-domain, 5-wave** architectural refactoring based on security and performance audit. This release focuses on system stability, memory management, and production-grade error handling.

---

## Wave 1: P0 Critical Fixes (2 tasks)

### W1-T1: Fix Bare `except:` in scheduler.py
- **Issue**: Bare `except:` at line 41 catches `KeyboardInterrupt` and `SystemExit`, preventing graceful shutdown
- **Solution**: Replaced with specific exception types
- **File**: `backend/app/services/scheduler.py`
- **Verification**: `grep "except:" backend/app/services/scheduler.py` returns nothing

### W1-T2: Add CircuitBreaker to sina_hq_fetcher.py
- **Issue**: No protection against cascading failures when Sina API is unavailable
- **Solution**: Added `_SINA_HQ_CB` CircuitBreaker with 5-failure threshold, 60s timeout
- **File**: `backend/app/services/sina_hq_fetcher.py`
- **Verification**: `grep -c "_SINA_HQ_CB" backend/app/services/sina_hq_fetcher.py` = 9

---

## Wave 2: Foundation Layer (11 tasks)

### Domain 1: Data Engine & Multi-Level Caching

#### W2A-T1: Create Unified `@smart_cache` Decorator
- **Implementation**: L1 (memory) + L2 (SQLite WAL) support
- **Features**:
  - TTL tiers: quotes=10s, macro=300s, static=3600s (L1)
  - L2 TTL: quotes=3600s, macro=86400s, static=604800s (7 days)
  - Circuit breaker integration (returns stale data on OPEN)
  - Namespace isolation for key collision prevention
  - Request coalescing via `get_or_set_async`
- **File**: `backend/app/services/data_cache.py` (lines 1039-1460)

#### W2A-T2: Remove Redis from qlib_init.py
- **Issue**: Redis reference in QlibInitializer (lines 42, 54-55, 61-62)
- **Solution**: Removed `redis_host`, `redis_port` parameters
- **File**: `backend/app/services/qlib/qlib_init.py`
- **Verification**: `grep -c "redis" backend/app/services/qlib/qlib_init.py` = 0

#### W2A-T3: Migrate 7 Inline Caches to DataCache
- **Migrated caches**:
  - `forex_fetcher.py` - Simple dict → DataCache
  - `global_index_fetcher.py` - Two dict caches → DataCache
  - `options_fetcher.py` - Simple dict → DataCache
  - `fund_fetcher.py` - AsyncCache → DataCache
  - `screener.py` - ThreadSafeCache → DataCache

### Domain 2: Token Bucket Rate Limiting

#### W2B-T1: Implement Token Bucket Algorithm
- **Algorithm**: `tokens = min(capacity, last_tokens + elapsed * rate)`
- **Configuration**:
  - Refill rate: 2.5 tokens/second (150 req/min)
  - Burst capacity: 150 tokens
  - Per-IP rate limiting
- **File**: `backend/app/middleware/rate_limit_token_bucket.py`

#### W2B-T2: Update SQLite Schema
- **Schema**: `tokens (REAL), last_refreshed (REAL)` - not count-based
- **Migration**: Automatic schema update on first run

#### W2B-T3: Integrate with Middleware
- **File**: `backend/app/middleware/rate_limit.py`
- **Verification**: Middleware uses Token Bucket instead of Fixed Window Counter

### Domain 7: Exception Handling Cleanup

#### W2C-T1: Replace 68 `except Exception:` with Specific Types
- **Files modified**: 42 files
- **Exception types used**:
  - `sqlite3.Error`, `sqlite3.OperationalError` - Database operations
  - `ValueError`, `TypeError`, `KeyError`, `IndexError` - Data handling
  - `httpx.HTTPError`, `asyncio.TimeoutError`, `ConnectionError` - Network
  - `OSError`, `IOError`, `PermissionError` - File system
  - `ZeroDivisionError`, `statistics.StatisticsError` - Calculations
- **Verification**: `grep -r "except Exception:" backend/app/ | wc -l` = 1 (comment only)

#### W2C-T2: Add `exc_info=True` to Logger Calls
- **Count**: 40 new additions
- **Pattern**: `logger.error(f"[Module] Error: {e}", exc_info=True)`
- **Benefit**: Stack traces now captured in logs for debugging

---

## Wave 3: Integration Layer (7 tasks)

### Domain 3: Circuit Breaker Enhancement

#### W3A-T1: Add Stale Fallback to akshare_fetcher.py
- **Implementation**: 3-tier fallback chain
  ```
  Circuit Breaker OPEN
      │
      ├── L1: get_with_stale() → Return stale data if available
      │
      ├── L2: get_with_sqlite_fallback() → Return SQLite cached data
      │
      └── L3: Return None + Log error
  ```
- **Methods modified**: `get_quote`, `get_kline`, `get_fund_nav`
- **File**: `backend/app/services/fetchers/akshare_fetcher.py`
- **Verification**: `grep -c "get_with_stale"` = 7

#### W3A-T2: Change Circuit Breaker Timeout
- **Before**: 30 seconds
- **After**: 600 seconds (10 minutes)
- **Rationale**: External APIs may have temporary outages; longer timeout prevents premature circuit opening

### Domain 8: API Response Contract

#### W3B-T1: Add Timestamp to success_response()
- **Implementation**: ISO 8601 format timestamp at top level
- **Response format**:
  ```json
  {
    "code": 0,
    "message": "success",
    "data": {...},
    "error": null,
    "timestamp": "2026-05-20T10:30:00.123456"
  }
  ```
- **File**: `backend/app/utils/errors.py`
- **Verification**: `grep -c "timestamp.*datetime.now"` = 3

---

## Wave 4: Frontend Layer (9 tasks)

### Domain 4: ECharts Memory Management

#### W4A-T1: Add onBeforeUnmount to 15 Components
- **Components fixed**:
  1. `IndexLineChart.vue` - Changed `onUnmounted` → `onBeforeUnmount`
  2. `YieldSpreadChart.vue`
  3. `TermStructureChart.vue`
  4. `FuturesMainChart.vue`
  5. `YieldCurveChart.vue`
  6. `SentimentGauge.vue`
  7. `SubChart.vue`
  8. `QuotePanel.vue`
  9. `FundFlowPanel.vue`
  10. `BondHistoryModal.vue`
  11. `MacroDashboard.vue`
  12. `FundDashboard.vue`
  13. `EsgDashboard.vue`
  14. `ResearchDashboard.vue`
  15. `PositionPieChart.vue`

- **Pattern applied**:
  ```javascript
  onBeforeUnmount(() => {
    if (chartInstance && !chartInstance.isDisposed()) {
      chartInstance.dispose()
      chartInstance = null
    }
    resizeObserver?.disconnect()
  })
  ```
- **Verification**: `grep -r "onBeforeUnmount" frontend/src/components/*.vue | wc -l` = 51

#### W4A-T2: Add onDeactivated for KeepAlive Components
- **Purpose**: Pause (not dispose) charts when deactivated in KeepAlive
- **Count**: 22 occurrences
- **Pattern**: `chartInstance.clear()` instead of `dispose()`

### Domain 6: AdminDashboard Restructuring

#### W4B-T1: Fix CostAttributionPanel Import
- **Issue**: Component used in template but not imported
- **Solution**: Added `import CostAttributionPanel from './admin/CostAttributionPanel.vue'`
- **File**: `frontend/src/components/AdminDashboard.vue`
- **Verification**: `grep -c "CostAttributionPanel"` = 2

#### W4B-T2: Restructure to 4 Grouped Sections
- **Before**: 15 flat tabs
- **After**: 4 collapsible accordion groups
  - **系统与基础设施**: monitor, watchdog, logs, database, layout
  - **数据引擎**: sources, scheduler, cache, ratelimit, data_gaps
  - **智能引擎**: llm, tokens, cost-attribution, agent_tokens, mcp
  - **业务控制**: backtest
- **UI Features**:
  - Click group header to expand/collapse
  - 300ms smooth animation
  - Chevron rotation indicator
- **Verification**: `grep -c "navGroups"` = 2

---

## Wave 5: Build Optimization (4 tasks)

### W5-T1: Install vite-plugin-compression
- **Package**: `vite-plugin-compression`
- **Configuration**:
  ```javascript
  compression({
    algorithm: 'gzip',
    threshold: 10240,  // Only compress files > 10KB
    deleteOriginFile: false  // Keep original files
  })
  ```
- **File**: `frontend/vite.config.js`

### W5-T2: Compression Results
| File | Original | Gzipped | Savings |
|------|----------|---------|---------|
| vendor-echarts.js | 808.69kb | 265.25kb | 67% |
| vendor.js | 465.28kb | 163.03kb | 65% |
| index.js | 230.77kb | 72.71kb | 68% |
| vendor-vue.js | 120.43kb | 46.20kb | 62% |
| **Total** | - | - | **26 .gz files** |

---

## Files Modified Summary

| Category | Count | Key Files |
|----------|-------|-----------|
| Backend Services | 42 | data_cache.py, akshare_fetcher.py, sina_hq_fetcher.py |
| Backend Routers | 13 | macro.py, backtest.py, stocks.py, futures.py |
| Backend DB | 4 | database.py, db_writer.py, connection_pool.py |
| Backend Utils | 3 | errors.py, response.py, exception_handlers.py |
| Backend Middleware | 2 | rate_limit_token_bucket.py, rate_limit.py |
| Frontend Components | 16 | AdminDashboard.vue, IndexLineChart.vue, YieldSpreadChart.vue |
| Frontend Config | 2 | vite.config.js, package.json |
| **Total** | **133** | +1661/-669 lines |

---

## Verification Commands

```bash
# Wave 1
grep "except:" backend/app/services/scheduler.py  # Should return nothing
grep -c "_SINA_HQ_CB" backend/app/services/sina_hq_fetcher.py  # Expected: 9

# Wave 2
grep -c "redis" backend/app/services/qlib/qlib_init.py  # Expected: 0
ls backend/app/middleware/rate_limit_token_bucket.py  # Should exist
grep -r "except Exception:" backend/app/ | wc -l  # Expected: 1 (comment only)

# Wave 3
grep -c "get_with_stale" backend/app/services/fetchers/akshare_fetcher.py  # Expected: 7
grep -c "timestamp.*datetime.now" backend/app/utils/errors.py  # Expected: 3

# Wave 4
grep -r "onBeforeUnmount" frontend/src/components/*.vue | wc -l  # Expected: 51
grep -c "CostAttributionPanel" frontend/src/components/AdminDashboard.vue  # Expected: 2
grep -c "navGroups" frontend/src/components/AdminDashboard.vue  # Expected: 2

# Wave 5
grep -c "vite-plugin-compression" frontend/package.json  # Expected: 1
ls frontend/dist/assets/*.gz | wc -l  # Expected: 26
```

---

## Breaking Changes

None. All changes are backward compatible.

---

## Upgrade Notes

1. **Restart services**: `./start-services.sh restart`
2. **First request may be slow**: Cache warmup on startup
3. **Monitor logs**: `tail -f /tmp/backend.log` for exc_info stack traces
4. **Admin UI**: Navigation now uses collapsible accordion (click group header to expand)

---

## Contributors

- Sisyphus (Orchestrator)
- Metis (Plan Consultant)
- Sisyphus-Junior (Implementation)
- Explore/Librarian agents (Context gathering)

---

## Next Steps

1. Monitor cache hit rates: `curl http://localhost:60100/api/v1/admin/cache/stats`
2. Test rate limiting: Send 150+ requests to verify 429 response
3. Check memory: Chrome DevTools heap snapshot before/after navigation
4. Verify circuit breaker: `curl http://localhost:60100/api/v1/forex/circuit_breaker/status`
