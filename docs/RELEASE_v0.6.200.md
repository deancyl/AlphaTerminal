# AlphaTerminal v0.6.200 Release Notes

## Architecture Refactoring Complete

This release implements comprehensive architecture refactoring based on external security audit recommendations, achieving a pure single-process architecture with no external dependencies.

## Key Improvements

### Centralized ThreadPoolExecutor (v0.6.103)

**Problem**: 43 separate ThreadPoolExecutor instances across the codebase, totaling 460+ workers, causing thread fragmentation and resource inefficiency.

**Solution**: Created `backend/app/utils/executor.py` with:
- Main I/O executor: 32 workers
- Fast executor: 16 workers
- Proper `atexit` cleanup

```python
from app.utils.executor import get_executor

# Main I/O executor
result = await loop.run_in_executor(get_executor(), blocking_function)
```

### Unified Circuit Breaker Registry (v0.6.108)

**Problem**: 72 scattered CircuitBreaker instances, with duplicate `_EASTMONEY_CB` in `anomaly_detector.py` and `treemap_builder.py` causing inconsistent state.

**Solution**: Added `_SOURCE_STATUS_MAP` to `unified_fetcher.py`:

```python
from app.services.unified_fetcher import get_source_breaker

cb = get_source_breaker("eastmoney")
if cb.state == CircuitState.OPEN:
    # Use fallback
    pass
```

### Execution Engine (v0.6.121)

**Problem**: Missing execution engine with proper async task tracking.

**Solution**: Created `backend/app/services/execution_engine.py` with:
- `_running_tasks: Dict[str, asyncio.Task]` for task handles
- Proper `task.cancel()` cancellation
- SQLite persistence via `execution_db.py`

```python
from app.services.execution_engine import get_execution_engine

engine = get_execution_engine()
execution_id = await engine.start_execution("abc123", my_async_function)
await engine.cancel_execution("abc123")  # Proper cancellation
```

### Legacy Exception Handlers Removed (v0.6.141)

**Problem**: Redundant handlers in `main.py` overriding standard format.

**Solution**: Removed 72 lines of legacy handlers, ensuring all responses follow `{code, message, data, error}` format.

### WebSocket Memory Leak Fix (v0.6.181)

**Problem**: No `asyncio.shield` on cleanup operations, causing incomplete cleanup on cancellation.

**Solution**: Added `asyncio.shield()` to `ws_manager.py` disconnect method.

### Database Path for Tauri (v0.6.191)

**Problem**: Database path hardcoded to project directory.

**Solution**: Moved to `~/.config/alphaterminal/database.db` with `APP_DATA` environment variable support.

### Router Migration (v0.6.105)

**Migrated routers**:
- `stocks.py` - 6 usages
- `macro.py` - 27 usages
- `futures.py` - 4 usages
- `forex.py` - Multiple executors
- `bond.py` - 2 usages

### Frontend ApiResponseError (v0.6.146, v0.6.153)

**Problem**: Circuit breaker counting business errors (code != 0) as failures.

**Solution**: Created `ApiResponseError` class and modified error handling:

```javascript
try {
  const data = await apiFetch('/api/v1/market/overview')
} catch (error) {
  if (error instanceof ApiResponseError) {
    // Business error - does NOT trigger circuit breaker
  } else {
    // Network error - triggers circuit breaker
  }
}
```

## New Files

| File | Purpose |
|------|---------|
| `backend/app/utils/executor.py` | Centralized ThreadPoolExecutor |
| `backend/app/services/execution_engine.py` | Async task tracking |
| `backend/app/db/execution_db.py` | Execution history persistence |

## Architecture Principles

1. **Single-Process Architecture**: No Redis, Celery, or Nginx
2. **User Permissions Only**: No root/sudo required
3. **Tauri Compatible**: Database in user config directory, relative API paths
4. **WAL Mode SQLite**: `journal_mode=WAL`, `synchronous=NORMAL`, `cache_size=-64000`

## Verification

```bash
# Check centralized executor
python3 -c "from app.utils.executor import get_executor; e = get_executor(); assert e._max_workers >= 8"

# Check source status map
grep -c "_SOURCE_STATUS_MAP" backend/app/services/unified_fetcher.py  # Expected: 5+

# Check execution engine
python3 -c "from app.services.execution_engine import ExecutionEngine; assert hasattr(ExecutionEngine, '_running_tasks')"

# Check EASTMONEY_CB removed
grep -c "_EASTMONEY_CB" backend/app/services/market_radar/*.py  # Expected: 0

# Check frontend ApiResponseError
grep -c "ApiResponseError" frontend/src/utils/api.js  # Expected: 5+
```

## Breaking Changes

None. All changes are backward compatible.

## Upgrade Path

1. Pull latest changes: `git pull origin master`
2. Rebuild frontend: `cd frontend && npm run build`
3. Restart services: `./start-services.sh restart`
4. Verify: `curl http://localhost:60100/api/v1/macro/overview`

---

**Full Changelog**: https://github.com/deancyl/AlphaTerminal/compare/v0.6.102...v0.6.200
