# 外汇模块深度审计报告 v0.6.210

## 审计概述

**审计日期**: 2026-05-29
**审计范围**: Forex Module (Frontend + Backend)
**审计代理**: 6个并行代理（UI/UX、Security、Reliability、State Management、ECharts Performance、API Consistency）

---

## 审计统计

| Domain | Issues | P0 | P1 | P2 |
|--------|---------|----|----|-----|
| UI/UX | 13 | 3 | 5 | 5 |
| Security | 9 | 4 | 3 | 2 |
| Reliability | 11 | 3 | 5 | 3 |
| State Management | 7 | 1 | 4 | 2 |
| ECharts Performance | 10 | 2 | 4 | 4 |
| API Consistency | 15 | 2 | 8 | 5 |
| **Total** | **65** | **12** | **23** | **30** |

---

## Wave 1: P0 Critical Fixes (9 Tasks - 无依赖，可并行执行)

### Task 1: ForexDashboard Missing onActivated Hook

**问题**: ForexDashboard.vue has `onDeactivated` hook to stop polling, but NO `onActivated` hook to restart them when component is reactivated via KeepAlive.

**影响**: After navigating away and back, dashboard shows stale data, no auto-refresh.

**文件**: `frontend/src/components/ForexDashboard.vue`

**修复方案**:
```javascript
import { onActivated } from 'vue'

onActivated(() => {
  // Refresh data when component is reactivated via KeepAlive
  if (!quotes.value || quotes.value.length === 0) {
    fetchAllQuotes()
  }
  // Restart time updates
  updateTime()
  timeInterval = setInterval(updateTime, 1000)
  startPolling()
})
```

**验证命令**:
```bash
grep -c "onActivated" frontend/src/components/ForexDashboard.vue
# Expected: 2 (import + hook)
```

---

### Task 2: ForexKLineChart Missing onDeactivated/onActivated

**问题**: Component uses `<BaseKLineChart>` inside KeepAlive context but has NO lifecycle hooks.

**影响**: ResizeObserver and theme subscription continue running, wasting CPU cycles and creating memory leak risk.

**文件**: `frontend/src/components/forex/ForexKLineChart.vue`

**修复方案**:
```javascript
import { onDeactivated, onActivated } from 'vue'

onDeactivated(() => {
  // Clear chart data but preserve instance for quick reactivation
  if (chartInstance.value && !chartInstance.value.isDisposed()) {
    chartInstance.value.clear()
  }
})

onActivated(() => {
  // Redraw chart with existing data when reactivated
  if (chartInstance.value && !chartInstance.value.isDisposed() && props.data) {
    chartInstance.value.setOption(buildChartOption(props.data), { notMerge: false })
  }
})
```

**验证命令**:
```bash
grep -c "onDeactivated" frontend/src/components/forex/ForexKLineChart.vue
# Expected: 2 (import + hook)

grep -c "onActivated" frontend/src/components/forex/ForexKLineChart.vue
# Expected: 2 (import + hook)
```

---

### Task 3: Backend Missing httpx Import Causes NameError

**问题**: Code references `httpx.HTTPError` in exception handlers but never imports `httpx` module.

**影响**: Any network error triggers `NameError: name 'httpx' is not defined`, bypassing circuit breaker protection.

**文件**: `backend/app/routers/forex.py`

**修复方案**:
```python
import httpx  # Add this line at top of file (line 19)
```

**验证命令**:
```bash
grep "^import httpx" backend/app/routers/forex.py
# Expected: 1

python3 -c "import sys; sys.path.insert(0, 'backend'); from app.routers.forex import *"
# Expected: No errors
```

---

### Task 4: Error Messages Expose Internals via str(e) (CWE-209)

**问题**: Error responses expose internal exception details via `str(e)` at 6 locations.

**影响**: Error message reveals database paths, API keys, stack traces.

**文件**: `backend/app/routers/forex.py:492, 522, 552, 580, 1095, 1262`

**修复方案**:
```python
from app.utils.error_sanitizer import sanitize_error

# Replace all instances of:
return error_response(ErrorCode.INTERNAL_ERROR, str(e))

# With:
return error_response(ErrorCode.INTERNAL_ERROR, sanitize_error(e))
```

**验证命令**:
```bash
grep -n "str(e)" backend/app/routers/forex.py
# Expected: 0 (all replaced)

grep -c "sanitize_error(e)" backend/app/routers/forex.py
# Expected: 10+ (depends on current error handling)
```

---

### Task 5: Circuit Breaker Never Resets on Successful Fallback Fetch

**问题**: `_get_fallback_quotes()` successfully fetches data from CFETS/BOC but never calls `self.cb.record_success()`. Circuit breaker remains OPEN even when fallback succeeds.

**影响**: After 5 failures → CB opens → fallback fetch succeeds → CB stays OPEN → ALL subsequent requests use fallback (never recover).

**文件**: `backend/app/services/fetchers/forex_fetcher.py:224-275`

**修复方案**:
```python
def _get_fallback_quotes(self) -> List[Dict[str, Any]]:
    ts = int(datetime.now().timestamp())
    
    # Try CFETS
    try:
        ak = _get_akshare()
        df = ak.fx_spot_quote()
        if df is not None and not df.empty:
            quotes = self._parse_cfets_to_quotes(df, ts)
            if quotes:
                self.cb.record_success()  # ← ADD THIS LINE
                logger.info(f"[Forex] 使用CFETS报价作为回退数据: {len(quotes)} 条")
                return quotes
    except Exception as e:
        logger.warning(f"[Forex] CFETS银行间报价获取失败: {e}", exc_info=True)
    
    # Similar for BOC fallback
```

**验证命令**:
```bash
grep -c "record_success()" backend/app/services/fetchers/forex_fetcher.py
# Expected: 2+ (at least one per fallback path)
```

---

### Task 6: WebSocket Recovery Sequence Validation

**问题**: Recovery timeout (2s) processes buffered ticks without checking if recovery response arrived. Stale buffered data overwrites fresh recovery data.

**影响**: Double processing, potential data corruption during WebSocket reconnect.

**文件**: `frontend/src/composables/useMarketStream.js:345-363`

**修复方案**:
```javascript
let lastReceivedSeq = 0

// In recovery response handler:
onRecoveryResponse((response) => {
  const maxSeq = Math.max(...response.data.map(t => t.seq))
  
  // Only process if recovery is newer
  if (maxSeq > lastReceivedSeq) {
    // Clear tick buffer (stale data)
    tickBuffer.value = {}
    
    // Process recovery data
    processData(response.data)
    lastReceivedSeq = maxSeq
  }
})

// In tick handler:
onTick((tick) => {
  // Ignore stale ticks
  if (tick.seq <= lastReceivedSeq) {
    return
  }
  
  lastReceivedSeq = tick.seq
  processData([tick])
})
```

**验证命令**:
```bash
grep -c "lastReceivedSeq" frontend/src/composables/useMarketStream.js
# Expected: 5+ (declaration + recovery + tick handler)
```

---

### Task 7: CrossRateCell Missing Required bid/ask/spread Fields

**问题**: `CrossRateCell` Pydantic model requires `bid`, `ask`, `spread` fields but they're not provided in 5 locations.

**影响**: Pydantic validation fails with 500 error.

**文件**: `backend/app/routers/forex.py:902, 913, 922, 953, 962`

**修复方案**:
```python
# Line 902 - Add missing fields
row_rates.append(
    CrossRateCell(
        rate=1.0,
        bid=1.0,
        ask=1.0,
        spread=0.0,
        change_pct=0.0,
        is_base=True,
        is_calculated=False
    )
)

# Apply same fix to lines 913, 922, 953, 962
```

**验证命令**:
```bash
grep -c "bid:" backend/app/routers/forex.py
# Expected: 5+ (one per CrossRateCell call)
```

---

### Task 8: onDeactivated Doesn't Clear AbortController Timer

**问题**: `onDeactivated` stops polling and clears `timeInterval`, but doesn't cancel pending `createSignal` AbortController or clear the `_disconnectTimer`.

**影响**: Old AbortController state may interfere on reactivation.

**文件**: `frontend/src/components/ForexDashboard.vue:403-409`

**修复方案**:
```javascript
onDeactivated(() => {
  stopPolling()
  if (timeInterval) {
    clearInterval(timeInterval)
    timeInterval = null
  }
  completeAbort()  // Cancel all pending AbortControllers
})
```

**验证命令**:
```bash
grep -c "completeAbort" frontend/src/components/ForexDashboard.vue
# Expected: 2 (onUnmounted + onDeactivated)
```

---

### Task 9: Missing Timeout Protection on CFETS Endpoints

**问题**: `/cfets`, `/cfets/cross`, and `/official` endpoints call `forex_fetcher` methods without `asyncio.wait_for()` timeout protection.

**影响**: Network slowness causes indefinite hanging.

**文件**: `backend/app/routers/forex.py:508-522, 537-553, 573-580`

**修复方案**:
```python
FOREX_API_TIMEOUT = 30.0

@router.get("/cfets")
async def get_cfets():
    try:
        data = await asyncio.wait_for(
            fetch_cfets_data(),
            timeout=FOREX_API_TIMEOUT
        )
        return success_response(data)
    except asyncio.TimeoutError:
        logger.error("[CFETS] Timeout after 30s", exc_info=True)
        return error_response(ErrorCode.TIMEOUT_ERROR, "请求超时，请稍后重试")
```

**验证命令**:
```bash
grep -c "asyncio.wait_for" backend/app/routers/forex.py
# Expected: 3+ (one per CFETS endpoint)
```

---

## Wave 2: P1 High Priority Fixes (3 Tasks - 依赖Wave 1)

### Task 10: BaseKLineChart Theme Re-subscription

**问题**: Theme subscription cancelled in `onDeactivated` but never re-established in `onActivated`.

**影响**: After navigating away and back, theme changes don't update the chart.

**依赖**: Task 1 (ForexDashboard onActivated pattern)

**文件**: `frontend/src/components/BaseKLineChart.vue`

**修复方案**:
```javascript
let themeUnsubscribe = null

onDeactivated(() => {
  if (themeUnsubscribe) {
    themeUnsubscribe()
    themeUnsubscribe = null
  }
})

onActivated(() => {
  const { onThemeChange } = useTheme()
  themeUnsubscribe = onThemeChange((theme) => {
    if (chartInstance.value && !chartInstance.value.isDisposed()) {
      chartInstance.value.setOption(buildOption(props.data), { notMerge: false })
    }
  })
})
```

**验证命令**:
```bash
grep -c "themeUnsubscribe" frontend/src/components/BaseKLineChart.vue
# Expected: 3+ (declaration + onDeactivated + onActivated)
```

---

### Task 11: Symbol Parameter Validation

**问题**: `symbol` path parameter has no validation, allowing injection attacks.

**影响**: Path traversal, SQL injection, format string attacks possible.

**依赖**: Task 4 (Error sanitization)

**文件**: `backend/app/routers/forex.py`

**修复方案**:
```python
import re
from fastapi import HTTPException

SYMBOL_PATTERN = re.compile(r'^[A-Z]{3}(CNY|CNH)?$')

def validate_symbol(symbol: str) -> str:
    if not SYMBOL_PATTERN.match(symbol):
        raise HTTPException(status_code=400, detail=f"Invalid symbol format: {symbol}")
    return symbol

@router.get("/history/{symbol}")
async def get_history(symbol: str = Depends(validate_symbol)):
    ...
```

**验证命令**:
```bash
grep -c "SYMBOL_PATTERN" backend/app/routers/forex.py
# Expected: 2 (pattern + usage)
```

---

### Task 12: Stale-While-Revalidate Singleflight

**问题**: `_fetch_forex_spot_background()` is fire-and-forget. Multiple clients requesting stale data simultaneously trigger thundering herd.

**影响**: 10 clients request spot quotes → 10 background tasks → 10 simultaneous akshare calls → rate limit exceeded.

**依赖**: Task 5 (Circuit breaker reset)

**文件**: `backend/app/routers/forex.py`

**修复方案**:
```python
from app.utils.singleflight import singleflight

_forex_fetch_lock = asyncio.Lock()
_forex_fetch_in_progress = False

async def _fetch_forex_spot_background():
    async with _forex_fetch_lock:
        if _forex_fetch_in_progress:
            return
        _forex_fetch_in_progress = True
    
    try:
        # ... existing fetch logic ...
    finally:
        async with _forex_fetch_lock:
            _forex_fetch_in_progress = False
```

**验证命令**:
```bash
grep -c "_forex_fetch_lock" backend/app/routers/forex.py
# Expected: 3+ (declaration + acquire + release)
```

---

## Final Verification Checklist

```bash
# P0 Fixes Verification
grep -c "onActivated" frontend/src/components/ForexDashboard.vue  # Expected: 2+
grep -c "onDeactivated" frontend/src/components/forex/ForexKLineChart.vue  # Expected: 2+
grep "^import httpx" backend/app/routers/forex.py  # Expected: 1
grep -n "str(e)" backend/app/routers/forex.py  # Expected: 0
grep -c "record_success()" backend/app/services/fetchers/forex_fetcher.py  # Expected: 2+
grep -c "lastReceivedSeq" frontend/src/composables/useMarketStream.js  # Expected: 5+
grep -c "bid:" backend/app/routers/forex.py  # Expected: 5+
grep -c "completeAbort" frontend/src/components/ForexDashboard.vue  # Expected: 2+
grep -c "asyncio.wait_for" backend/app/routers/forex.py  # Expected: 3+

# P1 Fixes Verification
grep -c "themeUnsubscribe" frontend/src/components/BaseKLineChart.vue  # Expected: 3+
grep -c "SYMBOL_PATTERN" backend/app/routers/forex.py  # Expected: 2
grep -c "_forex_fetch_lock" backend/app/routers/forex.py  # Expected: 3+

# Build & Test
cd frontend && npm run build  # Expected: Success
cd backend && pytest tests/unit/test_routers/test_forex.py -v  # Expected: All pass
```

---

## Commit Strategy

**Wave 1 Commit** (after all 9 tasks complete):
```bash
git add -A
git commit -m "fix(forex): P0 Critical Fixes - Wave 1

- Add onActivated hook to ForexDashboard for KeepAlive support
- Add lifecycle hooks to ForexKLineChart for ECharts management
- Add missing httpx import to forex.py
- Replace str(e) with sanitize_error(e) for CWE-209
- Fix circuit breaker reset on successful fallback
- Add sequence validation to WebSocket recovery
- Add bid/ask/spread to CrossRateCell schema
- Clear AbortController timer in onDeactivated
- Add timeout protection to CFETS endpoints

Fixes: P0-1 (UI), P0-5 (UI), P0-1 (Security), P0-2 (Security), 
       P0-1 (Reliability), P0-1 (State), P0-4 (Security), P1-6 (State), P0-2 (API)"
```

**Wave 2 Commit** (after all 3 tasks complete):
```bash
git add -A
git commit -m "fix(forex): P1 High Priority Fixes - Wave 2

- Cancel and re-subscribe theme in BaseKLineChart lifecycle
- Add symbol parameter validation to prevent injection
- Add singleflight to prevent thundering herd

Fixes: P0-12 (ECharts), P0-3 (Security), P0-2 (Reliability)"
```

---

## 下一步行动

1. **在新会话中**: 使用本报告作为参考，执行所有12个修复任务
2. **执行顺序**: Wave 1 (9任务并行) → Wave 2 (3任务并行)
3. **验证**: 每个任务完成后立即验证
4. **提交**: 按Wave分批提交，保持原子性

---

**生成时间**: 2026-05-29
**版本**: v0.6.210+
**状态**: 已保存，待执行