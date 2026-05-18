# Release v0.6.48 - Async Performance Optimization

**Release Date**: 2026-05-18

## Overview

This release addresses critical performance bottlenecks caused by synchronous blocking operations in FastAPI event loops. The changes eliminate "database is locked" errors and improve concurrent request handling.

## Problem Statement

External audit identified the following issues:
1. **Event Loop Blocking**: AkShare and SQLite operations were blocking the FastAPI event loop
2. **Retry Storms**: Frontend was retrying AbortError, causing request amplification
3. **SQLite Concurrency**: Concurrent writes caused "database is locked" errors

## Solution

### 1. Async Database Wrapper Layer

**New Files**:
- `backend/app/db/async_db.py` - 14 async wrapper functions for database operations
- `backend/app/db/connection_pool.py` - SQLite connection pool implementation

### 2. AkShare Async Wrappers

**Files Modified**:
- `backend/app/routers/market/history.py` - 3 `asyncio.to_thread` wrappers
- `backend/app/routers/bond.py` - 2 `asyncio.to_thread` wrappers

### 3. SQLite Async Wrappers

**Files Modified**:
- `backend/app/routers/portfolio/accounts.py` - `run_in_executor` wrappers
- `backend/app/routers/portfolio/analytics.py` - `run_in_executor` wrappers
- `backend/app/routers/portfolio/cash.py` - `run_in_executor` wrappers
- `backend/app/routers/portfolio/lots.py` - `run_in_executor` wrappers
- `backend/app/routers/portfolio/positions.py` - `run_in_executor` wrappers
- `backend/app/routers/backtest.py` - 7 `run_in_executor` wrappers
- `backend/app/routers/ml.py` - 4 `run_in_executor` wrappers
- `backend/app/routers/copilot.py` - 7 `run_in_executor` wrappers
- `backend/app/routers/admin.py` - 5 `run_in_executor` wrappers
- `backend/app/routers/export.py` - 3 `run_in_executor` wrappers

### 4. Trading Service Async Wrappers

**Files Modified**:
- `backend/app/services/trading.py` - 3 async wrapper functions

### 5. Frontend Improvements

**Files Modified**:
- `frontend/src/utils/constants.js` - `API_DEFAULT` timeout: 8000ms → 15000ms
- `frontend/src/utils/api.js` - Circuit breaker threshold: 10 → 5, AbortError no longer retries

## Technical Details

### Thread Pool Configuration

```python
_executor = ThreadPoolExecutor(max_workers=20, thread_name_prefix="portfolio_positions_")
```

- **18 independent thread pools** with unique `thread_name_prefix`
- Each pool handles specific module's blocking operations
- Prevents cross-module thread contention

### Async Wrapper Pattern

```python
async def async_get_positions(portfolio_id: int):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, get_positions, portfolio_id)
```

### Frontend AbortError Handling

```javascript
// Before: AbortError triggered retry
if (error.name === 'AbortError') {
  throw error  // Now: Direct throw, no retry
}
```

## Files Changed

| File | Changes |
|------|---------|
| `backend/app/db/async_db.py` | New file (14 functions) |
| `backend/app/db/connection_pool.py` | New file |
| `backend/app/routers/admin.py` | 5 async wrappers |
| `backend/app/routers/backtest.py` | 7 async wrappers |
| `backend/app/routers/bond.py` | 2 async wrappers |
| `backend/app/routers/copilot.py` | 7 async wrappers |
| `backend/app/routers/export.py` | 3 async wrappers |
| `backend/app/routers/market/history.py` | 3 async wrappers |
| `backend/app/routers/ml.py` | 4 async wrappers |
| `backend/app/routers/portfolio/*.py` | 29 async wrappers |
| `backend/app/services/trading.py` | 3 async wrappers |
| `frontend/src/utils/api.js` | Retry logic fix |
| `frontend/src/utils/constants.js` | Timeout increase |

**Total**: 17 files changed, 1907 insertions(+), 1096 deletions(-)

## Performance Impact

| Metric | Before | After |
|--------|--------|-------|
| Concurrent requests | Frequent 500 errors | All 200 OK |
| "database is locked" errors | 84+ occurrences | 0 new errors |
| Request timeout rate | High | Reduced |

## Breaking Changes

None. This release is backward compatible.

## Upgrade Notes

No special upgrade steps required. The async wrappers are transparent to API consumers.

## Known Issues

1. `market/overview.py` still uses synchronous database calls (not wrapped to avoid performance regression)
2. `export.py` has 6 `regex` parameter deprecation warnings (non-blocking)

## Contributors

- AlphaTerminal Team

## Next Steps

- Monitor performance metrics in production
- Consider SQLite WAL mode for better concurrency
- Evaluate async SQLite libraries (aiosqlite)

---

**Full Changelog**: [v0.6.47...v0.6.48](https://github.com/deancyl/AlphaTerminal/compare/v0.6.47...v0.6.48)
