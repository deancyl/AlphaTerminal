# AlphaTerminal High-Availability Data Source Architecture

## Executive Summary

This document designs a comprehensive high-availability data source architecture to address critical issues:

- ❌ AkShare IP blocking risk (~200 requests then blocked)
- ❌ 767 bare except blocks (silent failures)
- ❌ No fallback mechanism between sources
- ❌ Circuit breaker not applied to core fetchers

---

## 1. Data Source Assessment Matrix

### 1.1 Reliability Scoring (0-10)

| Source | Reliability | Rate Limit | Quality | Latency | Cost | Score | Notes |
|--------|-------------|------------|---------|---------|------|-------|-------|
| **Tencent** | 9/10 | None | ⭐⭐⭐⭐⭐ | 50-200ms | Free | **9.0** | ✅ Primary |
| **Sina** | 8/10 | None | ⭐⭐⭐⭐ | 100-300ms | Free | **8.0** | ✅ Backup |
| **Eastmoney** | 7/10 | Proxy needed | ⭐⭐⭐⭐⭐ | 200-500ms | Free | **7.0** | ⚠️ Needs proxy |
| **AkShare** | 3/10 | ~200 req/IP | ⭐⭐⭐⭐ | 500-2000ms | Free | **3.0** | ❌ **Not production-ready** |
| **Alpha Vantage** | 5/10 | 5 req/min | ⭐⭐⭐ | 500-1000ms | Free/Paid | **5.0** | ⚠️ Strict limits |
| **Tushare Pro** | 8/10 | Credit-based | ⭐⭐⭐⭐⭐ | 200-500ms | Free/Paid | **8.0** | ✅ Professional |

### 1.2 Data Source Classification

#### 🔴 Critical (Must be HA)
- **A-share quotes** → Tencent(primary) + Sina(backup) + Eastmoney(backup)
- **Index quotes** → Tencent(primary) + Sina(backup)
- **K-line data** → Sina K-line(primary) + Tencent(backup)
- **Sector data** → Sina Industry(primary) + Eastmoney(backup)

#### 🟡 Important (Can degrade)
- **Financial data** → AkShare(primary) + Tushare(backup) + Mock(fallback)
- **Margin trading** → AkShare(primary) + Mock(fallback)
- **Institutional holdings** → AkShare(primary) + Mock(fallback)

#### 🟢 Auxiliary (Acceptable failure)
- **News** → Eastmoney(primary) + Mock(fallback)
- **Market sentiment** → AkShare(primary) + Mock(fallback)
- **US stocks** → Alpha Vantage(primary) + Mock(fallback)

---

## 2. Circuit Breaker Architecture

### 2.1 Current Status

**Existing Implementation**:
- ✅ `backend/app/services/fetchers/circuit_breaker.py` - Complete implementation
- ✅ `backend/app/services/fetcher_factory.py` - Factory pattern + fallback
- ❌ **NOT applied to core fetchers** (`sina_hq_fetcher.py`, `quote_source.py`)
- ❌ **F9 deep data endpoints have no circuit breaker protection**

### 2.2 Circuit Breaker Configuration

```python
# backend/app/config/circuit_breaker.py

CIRCUIT_BREAKER_CONFIGS = {
    # High-availability sources (fast break, fast recovery)
    "tencent": CircuitBreakerConfig(
        failure_threshold=3,
        recovery_timeout=30.0,
        success_threshold=2,
        timeout=5.0
    ),
    "sina": CircuitBreakerConfig(
        failure_threshold=3,
        recovery_timeout=30.0,
        success_threshold=2,
        timeout=5.0
    ),
    "eastmoney": CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=60.0,
        success_threshold=3,
        timeout=10.0
    ),
    
    # Low-reliability sources (strict break, slow recovery)
    "akshare": CircuitBreakerConfig(
        failure_threshold=2,    # 2 failures = break (IP block risk)
        recovery_timeout=300.0, # 5 min recovery
        success_threshold=5,    # Need 5 successes to close
        timeout=15.0
    ),
    "alpha_vantage": CircuitBreakerConfig(
        failure_threshold=2,
        recovery_timeout=300.0,
        success_threshold=3,
        timeout=10.0
    ),
}
```

### 2.3 Apply to Core Fetchers

**Key Change**: Wrap all `_parse_*` functions with circuit breaker context

```python
# Example: quote_source_v2.py

async def get_quote_with_protection(symbol: str) -> dict:
    sources_order = ["tencent", "sina", "eastmoney"]
    
    for source_name in sources_order:
        cb = get_circuit_breaker(source_name)
        if not cb.can_execute():
            continue
        
        try:
            with CircuitContext(cb, source_name):
                result = await asyncio.wait_for(
                    _fetch_from_source(source_name, symbol),
                    timeout=cb.config.timeout
                )
                return result
        except asyncio.TimeoutError:
            cb.record_failure()
        except Exception as e:
            logger.warning(f"[Quote] {source_name} failed: {e}")
            cb.record_failure()
    
    return {"source": "none", "error": "All sources failed"}
```

---

## 3. Fallback Architecture

### 3.1 Data Type → Source Mapping

```python
DATA_TYPE_SOURCES = {
    # High-availability (3-level fallback)
    "quote_a_stock": ["tencent", "sina", "eastmoney"],
    "quote_index": ["tencent", "sina"],
    "kline_60min": ["sina_kline", "tencent"],
    
    # Important (2-level fallback)
    "financial_indicator": ["akshare", "tushare", "mock"],
    "institution_hold": ["akshare", "mock"],
    "margin_trading": ["akshare", "mock"],
    
    # Auxiliary (1-level fallback)
    "news": ["eastmoney", "mock"],
    "sentiment": ["akshare", "mock"],
    "sector": ["sina_industry", "eastmoney", "mock"],
}
```

### 3.2 Automatic Failover Logic

```python
# backend/app/services/failover_manager.py

class FailoverManager:
    async def fetch_with_failover(
        self,
        data_type: str,
        fetch_fn: Callable,
        context: dict
    ) -> Any:
        sources = DATA_TYPE_SOURCES.get(data_type, [])
        
        for source_name in sources:
            cb = self.circuit_breakers.get(source_name)
            if cb and not cb.can_execute():
                continue
            
            try:
                result = await fetch_fn(source_name)
                if cb:
                    cb.record_success()
                self._update_health(source_name, success=True)
                return result
            except Exception as e:
                if cb:
                    cb.record_failure()
                self._update_health(source_name, success=False, error=str(e))
        
        raise AllSourcesFailedError(data_type)
```

---

## 4. Rate Limiting Architecture

### 4.1 Rate Limit Strategy

```python
RATE_LIMIT_CONFIGS = {
    "akshare": RateLimitConfig(
        max_requests=150,    # 150 req/hour (below 200 block threshold)
        window_seconds=3600,
        burst_size=10
    ),
    "alpha_vantage": RateLimitConfig(
        max_requests=5,      # 5 req/min
        window_seconds=60,
        burst_size=0
    ),
    "tushare": RateLimitConfig(
        max_requests=100,    # Adjust based on credit level
        window_seconds=60,
        burst_size=20
    ),
}
```

### 4.2 Request Queue with Priority

```python
class Priority(Enum):
    CRITICAL = 0   # Real-time quotes
    HIGH = 1       # K-line data
    NORMAL = 2     # Financial data
    LOW = 3        # Historical data

class RequestQueue:
    async def enqueue(
        self,
        request_id: str,
        fetch_fn: Callable,
        priority: Priority = Priority.NORMAL
    ) -> str:
        # Priority queue with max concurrent requests
        pass
```

---

## 5. Caching Strategy

### 5.1 Cache Duration Matrix

| Data Type | TTL | Cache Key | Invalidation | Priority |
|-----------|-----|-----------|--------------|----------|
| Real-time quotes | 30s | `quote:{symbol}` | TTL | 🔴 High |
| 60min K-line | 60s | `kline:{symbol}:60min` | TTL | 🔴 High |
| Daily K-line | 300s | `kline:{symbol}:day` | TTL | 🟡 Medium |
| Financial data | 300s | `financial:{symbol}` | TTL + Manual | 🟡 Medium |
| Sector data | 300s | `sector:all` | TTL | 🟡 Medium |
| News | 60s | `news:flash` | TTL + Force refresh | 🟢 Low |
| Margin trading | 300s | `margin:{symbol}` | TTL | 🟢 Low |
| Institutional holdings | 3600s | `institution:{symbol}` | TTL | 🟢 Low |

### 5.2 Stale-While-Revalidate

```python
class StaleWhileRevalidateCache:
    """
    Strategy:
    - Data before stale_at: Return cache directly
    - Data between stale_at and expires_at: Return cache + background refresh
    - Data after expires_at: Wait for refresh
    """
    async def get_or_fetch(self, key: str, fetch_fn: Callable, ttl: int) -> Any:
        entry = self.cache.get(key)
        
        if entry:
            if now < entry.stale_at:
                return entry.value
            elif now < entry.expires_at:
                asyncio.create_task(self._refresh(key, fetch_fn, ttl))
                return entry.value
            else:
                return await self._refresh_and_wait(key, fetch_fn, ttl)
        
        return await self._refresh_and_wait(key, fetch_fn, ttl)
```

---

## 6. Error Handling Improvements

### 6.1 Fix Bare Except Blocks

**Current Problem** (767 bare except blocks):
```python
# ❌ Bad
try:
    data = fetch_data()
except:
    pass  # Silent failure

# ❌ Bad
try:
    result = parse_response()
except Exception:
    return None  # Swallow all exceptions
```

**Improved Approach**:
```python
# ✅ Good
try:
    data = fetch_data()
except httpx.TimeoutException as e:
    logger.warning(f"[Fetcher] Timeout: {e}")
    raise DataSourceTimeoutError(source="sina", timeout=10.0)
except httpx.HTTPStatusError as e:
    logger.error(f"[Fetcher] HTTP error: {e.response.status_code}")
    raise DataSourceHTTPError(source="sina", status_code=e.response.status_code)
except json.JSONDecodeError as e:
    logger.error(f"[Fetcher] JSON decode error: {e}")
    raise DataSourceParseError(source="sina", message="Invalid JSON")
except Exception as e:
    logger.exception(f"[Fetcher] Unexpected error: {e}")
    raise DataSourceError(source="sina", message=str(e))
```

### 6.2 Structured Error Types

```python
class DataSourceError(Exception):
    def __init__(self, source: str, message: str, context: dict = None):
        self.source = source
        self.message = message
        self.context = context or {}
        super().__init__(f"[{source}] {message}")

class DataSourceTimeoutError(DataSourceError):
    pass

class DataSourceHTTPError(DataSourceError):
    def __init__(self, source: str, status_code: int):
        super().__init__(source, f"HTTP {status_code}")
        self.status_code = status_code

class DataSourceParseError(DataSourceError):
    pass

class AllSourcesFailedError(Exception):
    def __init__(self, data_type: str, attempted_sources: list):
        self.data_type = data_type
        self.attempted_sources = attempted_sources
        super().__init__(f"All sources failed for {data_type}")
```

---

## 7. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         API Layer                                 │
│  /api/v1/market/overview  /api/v1/f9/{symbol}/financial         │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│                    Failover Manager                               │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  1. Check circuit breaker state                           │   │
│  │  2. Try primary source (with timeout)                     │   │
│  │  3. On failure → try next source                          │   │
│  │  4. On success → update health metrics                    │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────┬────────────────────────────────────────────────────┘
             │
    ┌────────┴────────┬──────────────┬──────────────┐
    │                 │              │              │
┌───▼────┐      ┌─────▼─────┐  ┌────▼─────┐  ┌────▼─────┐
│Tencent │      │   Sina    │  │Eastmoney │  │ AkShare  │
│   CB   │      │    CB     │  │    CB    │  │    CB    │
└───┬────┘      └─────┬─────┘  └────┬─────┘  └────┬─────┘
    │                 │              │              │
    └────────┬────────┴──────────────┴──────────────┘
             │
┌────────────▼────────────────────────────────────────────────────┐
│                      Cache Layer (SWR)                           │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  - TTL-based expiration                                   │   │
│  │  - Stale-while-revalidate                                 │   │
│  │  - LRU eviction                                           │   │
│  │  - Memory limits                                          │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
             │
┌────────────▼────────────────────────────────────────────────────┐
│                    Rate Limiter                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  - Sliding window algorithm                               │   │
│  │  - Per-source limits                                      │   │
│  │  - Burst handling                                         │   │
│  │  - Request queuing with priority                          │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
             │
┌────────────▼────────────────────────────────────────────────────┐
│                  Monitoring & Alerting                            │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  - Circuit breaker state dashboard                        │   │
│  │  - Source health metrics                                  │   │
│  │  - Cache hit/miss rates                                   │   │
│  │  - Rate limit utilization                                 │   │
│  │  - Error rate alerts                                      │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8. Implementation Priority

### Phase 1: Critical Fixes (Week 1)
1. ✅ Apply circuit breaker to `quote_source.py`
2. ✅ Apply circuit breaker to `sina_hq_fetcher.py`
3. ✅ Apply circuit breaker to F9 deep data endpoints
4. ✅ Fix bare except blocks in core fetchers
5. ✅ Add rate limiting for AkShare

### Phase 2: Fallback & Caching (Week 2)
1. ✅ Implement `FailoverManager`
2. ✅ Implement `StaleWhileRevalidateCache`
3. ✅ Create data source mapping configuration
4. ✅ Add cache invalidation endpoints

### Phase 3: Monitoring & Alerting (Week 3)
1. ✅ Create circuit breaker status dashboard
2. ✅ Add source health monitoring
3. ✅ Implement error rate alerting
4. ✅ Add Prometheus metrics export

### Phase 4: Advanced Features (Week 4)
1. ✅ Implement request queue with priority
2. ✅ Add backpressure handling
3. ✅ Consider Redis for distributed caching
4. ✅ Performance testing and optimization

---

## 9. Monitoring Dashboard Design

### 9.1 Key Metrics

```python
METRICS = {
    # Circuit Breaker
    "circuit_breaker_state": {"tencent": "closed", "akshare": "open"},
    "circuit_breaker_failures": {"tencent": 0, "akshare": 5},
    
    # Source Health
    "source_success_rate": {"tencent": 0.99, "sina": 0.95},
    "source_latency_p95": {"tencent": 150, "sina": 250},
    
    # Cache
    "cache_hit_rate": 0.85,
    "cache_memory_usage_mb": 45,
    
    # Rate Limiting
    "rate_limit_remaining": {"akshare": 120, "alpha_vantage": 3},
    
    # Errors
    "error_rate": 0.02,
    "timeout_rate": 0.01,
}
```

### 9.2 Dashboard Endpoints

```python
# backend/app/routers/admin_monitoring.py

@router.get("/admin/monitoring/health")
async def get_system_health():
    return {
        "circuit_breakers": get_all_circuit_breaker_status(),
        "source_health": failover_manager.get_source_health(),
        "cache_stats": cache.get_stats(),
        "rate_limits": rate_limiter.get_all_status(),
    }

@router.get("/admin/monitoring/metrics")
async def get_prometheus_metrics():
    # Export Prometheus-compatible metrics
    pass
```

---

## 10. Code Patterns

### 10.1 Protected Fetch Pattern

```python
async def protected_fetch(
    data_type: str,
    symbol: str,
    priority: Priority = Priority.NORMAL
) -> dict:
    """
    Universal protected data fetch pattern
    
    Flow:
    1. Check cache (SWR)
    2. Check rate limit
    3. Try sources with failover
    4. Update cache
    5. Return data
    """
    cache_key = f"{data_type}:{symbol}"
    
    # 1. Try cache
    cached = await cache.get_or_fetch(
        cache_key,
        lambda: _fetch_with_failover(data_type, symbol),
        ttl=CACHE_TTLS[data_type]
    )
    
    return cached

async def _fetch_with_failover(data_type: str, symbol: str) -> dict:
    sources = DATA_TYPE_SOURCES[data_type]
    
    for source in sources:
        # Check rate limit
        if not rate_limiter.is_allowed(source):
            continue
        
        # Check circuit breaker
        cb = get_circuit_breaker(source)
        if not cb.can_execute():
            continue
        
        try:
            with CircuitContext(cb, source):
                result = await fetch_from_source(source, symbol)
                return result
        except Exception as e:
            logger.warning(f"[{source}] Failed: {e}")
            continue
    
    # All sources failed
    if data_type in DEGRADABLE_DATA_TYPES:
        return get_mock_data(data_type, symbol)
    
    raise AllSourcesFailedError(data_type)
```

### 10.2 Error Handling Pattern

```python
def safe_fetch(fetch_fn: Callable, *args, **kwargs) -> Any:
    """
    Safe fetch with structured error handling
    """
    try:
        return fetch_fn(*args, **kwargs)
    except httpx.TimeoutException as e:
        raise DataSourceTimeoutError(
            source=kwargs.get("source", "unknown"),
            timeout=e.timeout
        )
    except httpx.HTTPStatusError as e:
        raise DataSourceHTTPError(
            source=kwargs.get("source", "unknown"),
            status_code=e.response.status_code
        )
    except json.JSONDecodeError as e:
        raise DataSourceParseError(
            source=kwargs.get("source", "unknown"),
            message=f"JSON decode error: {e}"
        )
    except Exception as e:
        logger.exception(f"Unexpected error in {fetch_fn.__name__}")
        raise DataSourceError(
            source=kwargs.get("source", "unknown"),
            message=str(e)
        )
```

---

## Summary

This architecture provides:

1. **High Availability**: Multiple fallback sources with automatic failover
2. **Fault Tolerance**: Circuit breaker pattern prevents cascading failures
3. **Rate Limiting**: Prevents IP blocking and respects API limits
4. **Performance**: Multi-level caching with stale-while-revalidate
5. **Observability**: Comprehensive monitoring and alerting
6. **Graceful Degradation**: Mock data fallback for non-critical features

**Key Implementation Files**:
- `backend/app/config/circuit_breaker.py` - Circuit breaker configurations
- `backend/app/config/data_source_mapping.py` - Source mapping
- `backend/app/services/failover_manager.py` - Failover logic
- `backend/app/services/rate_limiter.py` - Rate limiting
- `backend/app/services/stale_cache.py` - SWR cache
- `backend/app/routers/admin_monitoring.py` - Monitoring endpoints
