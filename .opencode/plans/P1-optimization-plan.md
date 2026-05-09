# P1 Optimization Implementation Plan

**Status**: Planning Phase  
**Total Issues**: 16 (6 Backend)  
**Estimated Duration**: 2-3 days  
**Risk Level**: Medium (requires careful testing)

---

## Executive Summary

This plan addresses 16 P1-level (Important) optimizations for AlphaTerminal backend, focusing on:
- **Cache unification** (8 locations) → 80%+ cache hit rate
- **Parallelization** (2 locations) → 75% faster data refresh
- **Database optimization** (3 indexes) → 90% query speedup
- **Resource optimization** (3 locations) → 30% CPU reduction

**Key Principle**: Incremental implementation with atomic commits and comprehensive testing after each change.

---

## Priority Ranking (Risk × Impact)

| Rank | Optimization | Risk | Impact | Priority Score | Effort |
|------|--------------|------|--------|----------------|--------|
| 1 | News Parallel Fetch | Low | High | **9/10** | 2h |
| 2 | ThreadPoolExecutor Config | Low | High | **9/10** | 30m |
| 3 | Database Indexes | Low | High | **9/10** | 1h |
| 4 | Cache Unification (macro.py) | Low | Medium | **7/10** | 1h |
| 5 | Cache Unification (stocks.py) | Low | Medium | **7/10** | 1h |
| 6 | Cache Unification (futures.py) | Low | Medium | **7/10** | 1h |
| 7 | Cache Unification (bond.py) | Low | Medium | **7/10** | 1h |
| 8 | Cache Unification (market.py) | Medium | Medium | **6/10** | 2h |
| 9 | Cache Unification (sectors_cache.py) | Medium | Medium | **6/10** | 1h |
| 10 | Cache Unification (news_engine.py) | Medium | Medium | **6/10** | 1h |
| 11 | HTTP Client Pool | Medium | Medium | **6/10** | 2h |
| 12 | Scheduler Task Consolidation | Medium | Medium | **6/10** | 2h |

---

## Phase 1: Low-Risk High-Impact Optimizations (Day 1)

### 1.1 News Parallel Fetch (Priority: 9/10)

**Current State**: Sequential loop fetching 32 symbols (12 macro + 20 stocks)  
**Target State**: Parallel fetch using `asyncio.gather()`  
**Expected Speedup**: 10-20x (from ~3s to ~300ms)

#### Implementation Steps

```python
# File: backend/app/services/news_engine.py

# BEFORE (lines 159-193):
for sym in _MACRO_SYMBOLS:  # Sequential
    df = _get_ak().stock_news_em(symbol=sym)
    time.sleep(0.05)

# AFTER:
import asyncio
from concurrent.futures import ThreadPoolExecutor

_news_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="news_")

async def _fetch_news_parallel(symbols: list[str]) -> list[dict]:
    """Fetch news for multiple symbols in parallel"""
    loop = asyncio.get_event_loop()
    
    async def fetch_one(sym: str) -> list[dict]:
        def _sync_fetch():
            try:
                df = _get_ak().stock_news_em(symbol=sym)
                # ... process df ...
                return rows
            except Exception as e:
                logger.warning(f"News fetch failed for {sym}: {e}")
                return []
        
        return await loop.run_in_executor(_news_executor, _sync_fetch)
    
    # Fetch all symbols concurrently
    results = await asyncio.gather(*[fetch_one(sym) for sym in symbols])
    
    # Flatten results
    all_news = []
    for items in results:
        all_news.extend(items)
    
    return all_news
```

#### TDD Approach

**Test File**: `backend/tests/test_news_parallel.py`

```python
import pytest
import asyncio
import time
from app.services.news_engine import _fetch_news_parallel

@pytest.mark.asyncio
async def test_parallel_fetch_faster():
    """Parallel fetch should be 5x+ faster than sequential"""
    symbols = ["000001", "399001", "600036", "601318", "600519"]
    
    start = time.time()
    results = await _fetch_news_parallel(symbols)
    elapsed = time.time() - start
    
    assert elapsed < 1.0  # Should complete in < 1 second
    assert len(results) > 0  # Should return data

@pytest.mark.asyncio
async def test_parallel_fetch_all_symbols():
    """Should fetch all 32 symbols successfully"""
    from app.services.news_engine import _MACRO_SYMBOLS, NEWS_SYMBOLS
    
    all_symbols = list(set(_MACRO_SYMBOLS + NEWS_SYMBOLS))
    results = await _fetch_news_parallel(all_symbols)
    
    assert len(results) > 50  # Expect at least 50 news items
```

#### Verification Method

```bash
# 1. Run unit tests
pytest backend/tests/test_news_parallel.py -v

# 2. Check API response time
time curl http://localhost:8002/api/v1/news/flash

# 3. Monitor logs for parallel execution
tail -f /tmp/backend.log | grep "News"

# 4. Verify no errors in diagnostics
curl http://localhost:8002/api/v1/admin/diagnostic/full
```

#### Rollback Strategy

If issues arise:
1. Revert commit (atomic revert)
2. Restore sequential loop
3. No data loss (same data, just slower)

#### Atomic Commit Message

```
perf(news): parallel fetch 32 symbols with asyncio.gather

- Replace sequential loop with ThreadPoolExecutor + asyncio.gather
- Add 10 worker threads for concurrent akshare calls
- Reduce news refresh time from ~3s to ~300ms (10x speedup)
- Add test_news_parallel.py with performance benchmarks

Refs: P1-optimization-plan.md#1.1
```

---

### 1.2 ThreadPoolExecutor Configuration (Priority: 9/10)

**Current State**: `stocks.py` uses `max_workers=2`  
**Target State**: Dynamic based on CPU cores  
**Expected Speedup**: 2-4x under load

#### Implementation Steps

```python
# File: backend/app/routers/stocks.py

# BEFORE (line 21):
_executor = ThreadPoolExecutor(max_workers=2)

# AFTER:
import os

def _get_optimal_workers() -> int:
    """Calculate optimal thread pool size based on CPU cores"""
    cpu_count = os.cpu_count() or 4
    # Use 2x CPU cores for I/O-bound tasks (akshare HTTP calls)
    # Cap at 16 to avoid overwhelming external APIs
    return min(cpu_count * 2, 16)

_executor = ThreadPoolExecutor(
    max_workers=_get_optimal_workers(),
    thread_name_prefix="stocks_"
)
```

#### TDD Approach

```python
# File: backend/tests/test_threadpool_config.py

def test_optimal_workers_calculation():
    """Should calculate workers based on CPU count"""
    from app.routers.stocks import _get_optimal_workers
    
    workers = _get_optimal_workers()
    cpu_count = os.cpu_count() or 4
    
    assert workers >= 4  # Minimum 4 workers
    assert workers <= 16  # Maximum 16 workers
    assert workers == min(cpu_count * 2, 16)  # Formula check

def test_executor_initialized():
    """Executor should be initialized with optimal workers"""
    from app.routers.stocks import _executor
    
    assert _executor._max_workers >= 4
    assert _executor._max_workers <= 16
```

#### Verification Method

```bash
# 1. Check thread pool size in logs
grep "ThreadPoolExecutor" /tmp/backend.log

# 2. Load test with concurrent requests
ab -n 100 -c 10 http://localhost:8002/api/v1/stocks/limit_up

# 3. Monitor thread count
ps -eLf | grep python | wc -l
```

#### Atomic Commit Message

```
perf(stocks): dynamic ThreadPoolExecutor based on CPU cores

- Replace fixed max_workers=2 with dynamic calculation
- Use min(cpu_count * 2, 16) for I/O-bound optimization
- Add thread_name_prefix for better debugging
- Improve concurrent request handling 2-4x

Refs: P1-optimization-plan.md#1.2
```

---

### 1.3 Database Indexes (Priority: 9/10)

**Current State**: Missing indexes on `market_all_stocks` for common queries  
**Target State**: Composite indexes for filter + sort operations  
**Expected Speedup**: 90% query time reduction

#### Implementation Steps

```python
# File: backend/app/db/database.py

# Add to init_tables() function (after line 372):

def init_all_stocks_table():
    """Initialize全市场个股表 + 性能索引"""
    with _lock:
        conn = _get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS market_all_stocks (...)
        """)
        
        # NEW: Performance indexes for StockScreener queries
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_all_stocks_change_pct 
            ON market_all_stocks(change_pct DESC)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_all_stocks_turnover 
            ON market_all_stocks(turnover DESC)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_all_stocks_mktcap 
            ON market_all_stocks(mktcap DESC)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_all_stocks_pe 
            ON market_all_stocks(per) WHERE per > 0 AND per < 1000
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_all_stocks_pb 
            ON market_all_stocks(pb) WHERE pb > 0 AND pb < 100
        """)
        # Composite index for multi-column filters
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_all_stocks_composite 
            ON market_all_stocks(change_pct, turnover, mktcap)
        """)
        
        conn.commit()
        conn.close()
```

#### TDD Approach

```python
# File: backend/tests/test_database_indexes.py

def test_indexes_created():
    """Verify all performance indexes exist"""
    from app.db.database import _get_conn
    
    conn = _get_conn()
    indexes = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='market_all_stocks'"
    ).fetchall()
    index_names = [row[0] for row in indexes]
    
    assert "idx_all_stocks_change_pct" in index_names
    assert "idx_all_stocks_turnover" in index_names
    assert "idx_all_stocks_mktcap" in index_names
    assert "idx_all_stocks_composite" in index_names
    
    conn.close()

def test_query_performance():
    """Verify query uses index (EXPLAIN QUERY PLAN)"""
    from app.db.database import _get_conn
    
    conn = _get_conn()
    
    # Test change_pct filter uses index
    plan = conn.execute(
        "EXPLAIN QUERY PLAN SELECT * FROM market_all_stocks WHERE change_pct > 5"
    ).fetchall()
    plan_str = str(plan)
    assert "idx_all_stocks_change_pct" in plan_str or "SCAN" not in plan_str
    
    conn.close()
```

#### Verification Method

```bash
# 1. Run migration
python -c "from app.db.database import init_tables; init_tables()"

# 2. Verify indexes exist
sqlite3 database.db "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='market_all_stocks'"

# 3. Benchmark query performance
time sqlite3 database.db "SELECT * FROM market_all_stocks WHERE change_pct > 5 ORDER BY turnover DESC LIMIT 50"

# 4. Check query plan
sqlite3 database.db "EXPLAIN QUERY PLAN SELECT * FROM market_all_stocks WHERE change_pct > 5"
```

#### Atomic Commit Message

```
perf(db): add performance indexes for market_all_stocks

- Add idx_all_stocks_change_pct for change filter
- Add idx_all_stocks_turnover for turnover sort
- Add idx_all_stocks_mktcap for market cap filter
- Add idx_all_stocks_composite for multi-column queries
- Add partial indexes for PE/PB (exclude outliers)
- Reduce StockScreener query time by 90%

Refs: P1-optimization-plan.md#1.3
```

---

## Phase 2: Cache Unification (Day 1-2)

### 2.1 Cache Unification - macro.py (Priority: 7/10)

**Current State**: Custom dict cache with manual TTL management  
**Target State**: Unified DataCache with automatic TTL/LRU  
**Expected Benefit**: Consistent API, built-in stats, memory safety

#### Implementation Steps

```python
# File: backend/app/routers/macro.py

# BEFORE (lines 64-101):
_cache = {}
_cache_ttl = {}
CACHE_DURATION = 300
MAX_CACHE_SIZE = 50

def get_cached(key):
    _cleanup_expired()
    if key in _cache and key in _cache_ttl:
        if datetime.now() < _cache_ttl[key]:
            return _cache[key]
    return None

def set_cached(key, value):
    _cleanup_expired()
    if len(_cache) >= MAX_CACHE_SIZE and key not in _cache:
        oldest_key = min(_cache_ttl, key=_cache_ttl.get)
        _cache.pop(oldest_key, None)
        _cache_ttl.pop(oldest_key, None)
    _cache[key] = value
    _cache_ttl[key] = datetime.now() + timedelta(seconds=CACHE_DURATION)

# AFTER:
from app.services.data_cache import get_cache

_cache = get_cache()  # Singleton DataCache
CACHE_DURATION = 300  # Keep for reference

# Replace all get_cached(key) → _cache.get(key)
# Replace all set_cached(key, value) → _cache.set(key, value, ttl=300)
```

#### Migration Checklist

- [ ] Import `get_cache` from `data_cache`
- [ ] Replace `_cache` dict with `_cache = get_cache()`
- [ ] Remove `_cache_ttl` dict
- [ ] Remove `_cleanup_expired()` function
- [ ] Remove `get_cached()` function
- [ ] Remove `set_cached()` function
- [ ] Update all `get_cached("key")` → `_cache.get("macro:key")`
- [ ] Update all `set_cached("key", value)` → `_cache.set("macro:key", value, ttl=300)`
- [ ] Add cache namespace prefix `"macro:"` to all keys
- [ ] Run tests

#### TDD Approach

```python
# File: backend/tests/test_macro_cache.py

def test_macro_cache_unified():
    """Verify macro.py uses DataCache"""
    from app.routers.macro import _cache
    from app.services.data_cache import DataCache
    
    assert isinstance(_cache, DataCache)

def test_macro_cache_namespace():
    """Verify cache keys use 'macro:' namespace"""
    from app.routers.macro import get_macro_overview
    from app.services.data_cache import get_cache
    
    cache = get_cache()
    cache.clear()
    
    # Call endpoint
    # ... 
    
    # Verify key format
    stats = cache.get_stats()
    # Keys should start with "macro:"
```

#### Atomic Commit Message

```
refactor(macro): unify caching with DataCache

- Replace custom dict cache with DataCache singleton
- Remove manual TTL management (_cleanup_expired)
- Remove manual LRU eviction
- Add 'macro:' namespace to all cache keys
- Enable cache statistics via get_stats()
- Reduce code by ~40 lines

Refs: P1-optimization-plan.md#2.1
```

---

### 2.2-2.4 Cache Unification - stocks.py, futures.py, bond.py

**Same pattern as 2.1, apply to each file:**

| File | Namespace | TTL | Special Considerations |
|------|-----------|-----|------------------------|
| stocks.py | `stocks:` | 300s | Keep `_cache_or_fetch` decorator pattern |
| futures.py | `futures:` | 180s | Keep background refresh logic |
| bond.py | `bond:` | 300s | Keep separate `_HISTORY_CACHE` DataFrame |

#### Parallel Implementation Opportunity

These 3 files can be migrated **in parallel** by different developers or in separate commits on the same day, as they are independent.

---

### 2.5 Cache Unification - market.py (Priority: 6/10)

**Complexity**: Multiple caches with different TTLs  
**Strategy**: Use DataCache with different TTL values per key

```python
# BEFORE:
_MACRO_CACHE = {}      # 600s TTL
_REALTIME_CACHE = {}   # 10s TTL

# AFTER:
from app.services.data_cache import get_cache

_cache = get_cache()

# Macro cache: 600s TTL
_cache.set("market:macro:usdcny", data, ttl=600)

# Realtime cache: 10s TTL
_cache.set("market:realtime:sh000001", data, ttl=10)
```

---

### 2.6 Cache Unification - sectors_cache.py (Priority: 6/10)

**Current State**: Simple list cache with no TTL  
**Target State**: DataCache with 120s TTL (matching scheduler interval)

```python
# BEFORE:
_SECTORS_CACHE = []
_SECTORS_CACHE_TIME = 0

# AFTER:
from app.services.data_cache import get_cache

_cache = get_cache()

def get_cached_sectors():
    return _cache.get("sectors:all") or []

def set_cached_sectors(sectors):
    _cache.set("sectors:all", sectors, ttl=120)
```

---

### 2.7 Cache Unification - news_engine.py (Priority: 6/10)

**Current State**: Simple list cache with ready flag  
**Target State**: DataCache with TTL and size limits

```python
# BEFORE:
_NEWS_CACHE = []
_NEWS_CACHE_READY = False

# AFTER:
from app.services.data_cache import get_cache

_cache = get_cache()

def get_cached_news(limit=150):
    news = _cache.get("news:all") or []
    return news[:limit]

def set_cached_news(news):
    _cache.set("news:all", news[:200], ttl=120)  # Top 200, 2min TTL
```

---

## Phase 3: Resource Optimization (Day 2)

### 3.1 HTTP Client Connection Pool (Priority: 6/10)

**Current State**: Each request may create new client  
**Target State**: Global shared client pool

#### Implementation Steps

```python
# File: backend/app/services/http_client.py

# Add global client pool at module level:

_global_clients: dict[str, ValidatedHTTPClient] = {}
_global_clients_lock = threading.Lock()

def get_shared_client(
    name: str = "default",
    proxy: Optional[str] = None,
    timeout: float = 10.0,
    **kwargs
) -> ValidatedHTTPClient:
    """Get or create a shared HTTP client by name"""
    with _global_clients_lock:
        if name not in _global_clients:
            _global_clients[name] = ValidatedHTTPClient(
                proxy=proxy,
                timeout=timeout,
                **kwargs
            )
        return _global_clients[name]

# Usage in routers:
from app.services.http_client import get_shared_client

client = get_shared_client("sina", proxy=None, timeout=5.0)
resp = await client.get_with_retry("https://hq.sinajs.cn/...")
```

#### Atomic Commit Message

```
perf(http): global connection pool for HTTP clients

- Add get_shared_client() for client reuse
- Reduce connection overhead by 50ms per request
- Enable connection pooling across all routers
- Add client name namespacing for different configs

Refs: P1-optimization-plan.md#3.1
```

---

### 3.2 Scheduler Task Consolidation (Priority: 6/10)

**Current State**: Overlapping tasks for daily K-line refresh  
**Target State**: Consolidated tasks with no redundancy

#### Consolidation Plan

**Merge 1: Daily K-line Tasks**

```python
# REMOVE: today_daily_refresh (5min)
# ENHANCE: realtime_daily (10s) to include fallback

def _realtime_daily_job():
    """Unified daily K-line refresh"""
    from app.services.data_fetcher import (
        refresh_today_from_minute,
        refresh_period_klines,
        fetch_china_index_history
    )
    
    try:
        # Primary: Minute data aggregation (fast)
        refresh_today_from_minute()
        refresh_period_klines()
    except Exception as e:
        logger.warning(f"Minute refresh failed: {e}, trying akshare fallback")
        # Fallback: Akshare historical API (slower but reliable)
        for sym in ["000001", "000300", "399001", "399006", "000688"]:
            try:
                fetch_china_index_history(sym)
            except Exception as e2:
                logger.error(f"Fallback failed for {sym}: {e2}")
```

**Merge 2: News Fetching**

```python
# UNIFY: sentiment_engine._MACRO_NEWS_SYMBOLS + news_engine.NEWS_SYMBOLS

# New unified symbol list (deduplicated):
UNIFIED_NEWS_SYMBOLS = list(set([
    "000001", "399001", "399006", "000300",  # Core indices
    "600036", "601318", "600030", "600016",  # Banks
    "600519", "002594", "300750", "688981",  # Consumer/Tech
    "601628", "000776", "002230", "300059",  # Insurance/Tech
    "688111", "600028", "601899", "600050",  # Cyclical
    "600887", "603288", "000858", "600009", "601888"  # Consumer
]))
```

#### Atomic Commit Message

```
refactor(scheduler): consolidate overlapping tasks

- Merge today_daily_refresh into realtime_daily with fallback
- Unify news symbol lists (remove 10 duplicates)
- Remove redundant sector fetch from data_fetch
- Reduce scheduled tasks from 10 to 8
- Lower CPU usage by 30%

Refs: P1-optimization-plan.md#3.2
```

---

## Testing Strategy

### Unit Tests (Per Optimization)

Each optimization must have:
1. **Functionality test**: Verify behavior unchanged
2. **Performance test**: Verify speedup achieved
3. **Integration test**: Verify no breaking changes

### Integration Tests (After Each Phase)

```bash
# Phase 1 tests
pytest backend/tests/test_news_parallel.py
pytest backend/tests/test_threadpool_config.py
pytest backend/tests/test_database_indexes.py

# Phase 2 tests
pytest backend/tests/test_macro_cache.py
pytest backend/tests/test_stocks_cache.py
pytest backend/tests/test_futures_cache.py
pytest backend/tests/test_bond_cache.py

# Phase 3 tests
pytest backend/tests/test_http_client_pool.py
pytest backend/tests/test_scheduler_consolidation.py
```

### End-to-End Verification

```bash
# 1. Start services
./start-services.sh restart

# 2. Run full diagnostic
curl http://localhost:8002/api/v1/admin/diagnostic/full

# 3. Test all major endpoints
curl http://localhost:8002/api/v1/macro/overview
curl http://localhost:8002/api/v1/news/flash
curl http://localhost:8002/api/v1/market/overview
curl http://localhost:8002/api/v1/stocks/limit_up

# 4. Monitor cache statistics
curl http://localhost:8002/api/v1/admin/cache/stats

# 5. Check memory usage
curl http://localhost:8002/api/v1/admin/system/memory
```

---

## Rollback Strategy

### Per-Optimization Rollback

Each commit is atomic and can be individually reverted:

```bash
# View commit history
git log --oneline --grep="P1-optimization"

# Revert specific optimization
git revert <commit-hash>

# Example: Revert news parallel fetch
git revert abc1234  # perf(news): parallel fetch 32 symbols
```

### Full Rollback

If multiple issues arise:

```bash
# Create rollback branch from pre-optimization state
git checkout -b rollback-p1 <pre-p1-commit>

# Or reset to pre-P1 state (DESTRUCTIVE)
git reset --hard <pre-p1-commit>
```

### Backup Strategy

Before starting P1 implementation:

```bash
# Create backup branch
git checkout -b backup-pre-p1

# Tag current state
git tag -a v0.6.14-pre-p1 -m "State before P1 optimizations"

# Return to main branch
git checkout main
```

---

## Parallel Execution Opportunities

### Independent Optimizations (Can Run in Parallel)

These optimizations have **no dependencies** and can be implemented simultaneously:

| Group | Optimizations | Can Parallelize |
|-------|--------------|-----------------|
| **Phase 1** | News Parallel, ThreadPool, DB Indexes | ✅ Yes (3 developers) |
| **Phase 2** | Cache (stocks), Cache (futures), Cache (bond) | ✅ Yes (3 developers) |
| **Phase 3** | HTTP Pool, Scheduler Consolidation | ✅ Yes (2 developers) |

### Dependent Optimizations (Must Be Sequential)

| Sequence | Optimizations | Reason |
|----------|--------------|--------|
| Cache (macro) → Cache (market) | market.py uses macro cache pattern | Shared pattern |
| Cache (simple) → Cache (complex) | Start with simple routers first | Learn pattern |

### Recommended Execution Flow

```
Day 1 Morning (Parallel):
├─ Dev A: News Parallel Fetch (2h)
├─ Dev B: ThreadPool Config (30m) + DB Indexes (1h)
└─ Dev C: Cache Unification (macro.py) (1h)

Day 1 Afternoon (Parallel):
├─ Dev A: Cache Unification (stocks.py) (1h)
├─ Dev B: Cache Unification (futures.py) (1h)
└─ Dev C: Cache Unification (bond.py) (1h)

Day 2 Morning (Sequential):
├─ Dev A: Cache Unification (market.py) (2h)
├─ Dev B: Cache Unification (sectors_cache.py) (1h)
└─ Dev C: Cache Unification (news_engine.py) (1h)

Day 2 Afternoon (Parallel):
├─ Dev A: HTTP Client Pool (2h)
└─ Dev B: Scheduler Consolidation (2h)

Day 3: Testing & Verification
├─ All Devs: Integration testing
├─ All Devs: Performance benchmarking
└─ All Devs: Documentation updates
```

---

## Success Criteria

### Performance Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| News refresh time | ~3s | <500ms | `time curl /api/v1/news/flash` |
| Cache hit rate | ~40% | >80% | `cache.get_stats()['hit_rate']` |
| StockScreener query | ~200ms | <20ms | SQLite EXPLAIN |
| Memory usage | ~300MB | <250MB | `psutil.Process().memory_info().rss` |
| CPU usage (idle) | ~15% | <10% | `psutil.cpu_percent()` |

### Functional Requirements

- [ ] All existing API endpoints return same data
- [ ] No new errors in logs
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Frontend displays data correctly
- [ ] WebSocket broadcasts work
- [ ] Scheduler tasks execute on schedule

---

## Risk Mitigation

### High-Risk Areas

1. **Cache unification in market.py**
   - **Risk**: Multiple caches with different TTLs
   - **Mitigation**: Test thoroughly with different TTL values

2. **Scheduler consolidation**
   - **Risk**: Breaking data flow dependencies
   - **Mitigation**: Monitor data freshness after each task

3. **Database indexes**
   - **Risk**: Index creation may lock database
   - **Mitigation**: Create indexes during low-traffic period

### Monitoring During Implementation

```bash
# Continuous monitoring script
watch -n 5 '
  echo "=== Backend Health ==="
  curl -s http://localhost:8002/health | jq
  echo "=== Cache Stats ==="
  curl -s http://localhost:8002/api/v1/admin/cache/stats | jq ".data"
  echo "=== Memory Usage ==="
  ps aux | grep python | grep -v grep
'
```

---

## Documentation Updates

After implementation, update:

1. **AGENTS.md**: Add cache unification guidelines
2. **README.md**: Update performance characteristics
3. **Inline docs**: Add docstrings for new functions
4. **Test docs**: Document test coverage

---

## Appendix: Code Templates

### DataCache Migration Template

```python
# Step 1: Import
from app.services.data_cache import get_cache

# Step 2: Initialize
_cache = get_cache()
NAMESPACE = "your_router:"
TTL = 300  # seconds

# Step 3: Replace get_cached
# OLD: cached = get_cached("key")
# NEW: cached = _cache.get(f"{NAMESPACE}key")

# Step 4: Replace set_cached
# OLD: set_cached("key", value)
# NEW: _cache.set(f"{NAMESPACE}key", value, ttl=TTL)

# Step 5: Remove old cache code
# - Remove _cache dict
# - Remove _cache_ttl dict
# - Remove _cleanup_expired()
# - Remove get_cached()
# - Remove set_cached()
```

### Parallel Fetch Template

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

_executor = ThreadPoolExecutor(max_workers=10)

async def fetch_parallel(items: list) -> list:
    loop = asyncio.get_event_loop()
    
    async def fetch_one(item):
        def _sync():
            # Your sync fetch logic here
            return result
        return await loop.run_in_executor(_executor, _sync)
    
    results = await asyncio.gather(*[fetch_one(i) for i in items])
    return [r for r in results if r]  # Filter None
```

---

**End of P1 Optimization Implementation Plan**
