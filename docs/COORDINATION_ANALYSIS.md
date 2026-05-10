# AlphaTerminal Frontend-Backend Coordination Analysis

## Executive Summary

This document analyzes coordination issues between frontend and backend components and proposes unified standards for:
- API Response Format
- Symbol Format Standardization
- Error Handling Coordination
- WebSocket Protocol
- State Synchronization

---

## 1. API Response Format

### 1.1 Current State Documentation

#### Backend Response Formats

**Standard Envelope Format (Most Endpoints)**
```python
# Used by: stocks.py, macro.py, f9_deep.py, market.py
def success_response(data, message="success"):
    return {
        "code": 0,
        "message": message,
        "data": data,
        "timestamp": int(datetime.now().timestamp() * 1000)
    }

def error_response(message, code=1):
    return {
        "code": code,
        "message": message,
        "data": None,
        "timestamp": int(datetime.now().timestamp() * 1000)
    }
```

**Endpoints Using Standard Envelope:**
| Router | Endpoints | Format |
|--------|-----------|--------|
| `stocks.py` | `/limit_up`, `/limit_down`, `/unusual`, `/search`, `/quote`, `/limit_summary` | `{code, message, data, timestamp}` |
| `macro.py` | `/gdp`, `/cpi`, `/ppi`, `/pmi`, `/overview`, `/calendar`, `/m2`, `/social_financing`, `/industrial_production`, `/unemployment`, `/batch` | `{code, message, data, timestamp}` |
| `f9_deep.py` | `/health`, `/{symbol}/shareholder`, `/{symbol}/margin`, `/{symbol}/financial`, etc. | `{code, message, data, timestamp}` |
| `market.py` | `/market/overview`, `/market/quote`, `/market/kline`, `/market/symbols`, `/market/sectors` | `{code, message, data, timestamp}` |

**Variations Found:**
- `portfolio.py`: May return direct data in some endpoints (needs verification)
- `backtest.py`: May have different response structure (needs verification)

#### Frontend Response Handling

**Current Implementation (`frontend/src/utils/api.js`):**
```javascript
/**
 * 从 API 响应中提取 data 字段
 * 兼容：新格式 {code:0, data: {...}} → 返回 data
 *       旧格式 {...} → 直接返回（向后兼容）
 */
export function extractData(response) {
  if (response && typeof response.code === 'number' && 'data' in response) {
    if (response.code !== 0) {
      logger.warn('[API] 非0响应码:', response.code, response.message)
    }
    return response.data
  }
  return response  // Backward compatibility for direct returns
}
```

### 1.2 Proposed Unified Response Envelope

**Standard Response Format:**
```typescript
interface ApiResponse<T> {
  code: number;        // 0 = success, non-0 = error
  message: string;     // Human-readable message
  data: T | null;      // Response payload
  timestamp: number;   // Unix timestamp in milliseconds
  traceId?: string;    // Optional: Request tracing ID
}
```

**Error Code Standard:**
```typescript
enum ErrorCode {
  // Success
  SUCCESS = 0,
  
  // Client Errors (1xx)
  BAD_REQUEST = 100,
  UNAUTHORIZED = 101,
  FORBIDDEN = 102,
  NOT_FOUND = 104,
  VALIDATION_ERROR = 110,
  RATE_LIMITED = 120,
  
  // Server Errors (2xx)
  INTERNAL_ERROR = 200,
  DATABASE_ERROR = 210,
  
  // Third-party Errors (3xx)
  THIRD_PARTY_ERROR = 302,
  TIMEOUT_ERROR = 310,
}
```

### 1.3 Migration Strategy

**Phase 1: Audit (Week 1)**
- Identify all endpoints not using standard envelope
- Document exceptions and reasons

**Phase 2: Backend Standardization (Week 2)**
- Create shared response utilities in `backend/app/utils/response.py`
- Migrate all routers to use standard functions

**Phase 3: Frontend Update (Week 3)**
- Update `api.js` to enforce envelope format
- Add strict mode flag for development

---

## 2. Symbol Format Standardization

### 2.1 Current State Documentation

#### Symbol Format Variations Found

| Format | Example | Usage Location |
|--------|---------|----------------|
| Bare code | `600519` | User input, some API params |
| Lowercase prefix | `sh600519` | Backend standard, frontend stores |
| Uppercase prefix | `SH600519` | Some external APIs |
| Dot notation | `600519.SH` | Alternative format (rare) |
| US prefix | `usNDX`, `usSPX` | US indices |
| HK prefix | `hkHSI` | Hong Kong indices |
| JP prefix | `jpN225` | Japan indices |
| Macro (no prefix) | `GOLD`, `WTI`, `VIX` | Macro commodities |

#### Backend Symbol Normalization

**Location: `backend/app/routers/market.py`**
```python
def _normalize_symbol(raw: str) -> str:
    """
    将各种前端传入格式统一为带市场前缀的规范 symbol。
    例如: '000001' → 'sh000001', 'sh000001' → 'sh000001', 'NDX' → 'usNDX'
    """
    s = raw.strip()
    # 已知美股（无前缀形式，如 'ndx'）
    if s.upper() in ('NDX', 'SPX', 'DJI'):
        return 'us' + s.upper()
    # 已知日经
    if s.upper() in ('N225', 'NI225', 'NIKKEI'):
        return 'jpN225'
    # 已知港股
    if s.upper() in ('HSI',):
        return 'hkHSI'
    # 已知宏观（无前缀）
    if s.upper() in ('GOLD', 'WTI', 'VIX'):
        return s.upper()
    # CNH/USD 特殊处理
    upper_s = s.upper()
    if upper_s == 'CNHUSD':
        return 'CNHUSD'
    if upper_s.startswith('CNH'):
        suffix = upper_s[len('CNH'):]
        if suffix.isdigit() or suffix.startswith('USD'):
            return 'CNHUSD'
    # 去掉 sh/sz/hk/us/jp 前缀
    clean = s.lower()
    for pfx in ('sh', 'sz', 'hk', 'us', 'jp'):
        if clean.startswith(pfx):
            clean = clean[len(pfx):]
            break
    # A股数字段判断：6开头→上海；其余→深圳
    if clean.isdigit():
        if clean.startswith('6') or clean in ('000001', '000300', '000688'):
            return 'sh' + clean
        if clean.startswith(('0', '2', '3')):
            return 'sz' + clean
        return 'sz' + clean
    return s
```

**Location: `backend/app/services/fetchers/sina.py`**
```python
def normalize_symbol(symbol: str) -> str:
    """
    将各种格式的 symbol 规范化为 Sina 格式。
    例如: "600519" → "sh600519", "000001" → "sz000001"
    """
    s = symbol.lower().strip()
    if s.startswith("sh") or s.startswith("sz"):
        return s
    # 纯数字代码
    if s.startswith("6") or s.startswith("5"):
        return f"sh{s}"
    return f"sz{s}"
```

#### Frontend Symbol Normalization

**Location: `frontend/src/utils/symbols.js`**
```javascript
/**
 * 规范化任意格式的 symbol 为标准带前缀格式
 * 例如: '000001' → 'sh000001', 'NDX' → 'usNDX', 'sh000001' → 'sh000001'
 */
export function normalizeSymbol(raw) {
  const s = String(raw).trim()
  const upper = s.toUpperCase()

  // 已带前缀的完整symbol直接返回小写
  if (/^(sh|sz|us|hk|jp)/i.test(s)) return s.toLowerCase()

  if (US_SYMBOLS.includes(upper)) {
    return 'us' + upper
  }
  if (HK_SYMBOLS.includes(upper)) {
    return 'hkHSI'
  }
  if (JP_SYMBOLS.includes(upper)) {
    return 'jpN225'
  }
  if (MACRO_SYMBOLS.includes(upper)) {
    return upper
  }
  // CNHUSD 特殊处理
  if (upper === 'CNHUSD') return 'CNHUSD'
  if (upper.startsWith('CNH')) return 'CNHUSD'

  const clean = s.replace(/^(sh|sz|us|hk|jp)/i, '')

  if (/^\d{6}$/.test(clean)) {
    return _aSharePrefix(clean) + clean
  }
  return s.toLowerCase()
}
```

### 2.2 Proposed Canonical Format

**Canonical Format: `{exchange_prefix}{code}` (lowercase)**

| Market | Prefix | Example | Notes |
|--------|--------|---------|-------|
| Shanghai (A股) | `sh` | `sh600519` | 6xx, 9xx codes |
| Shenzhen (A股) | `sz` | `sz000001` | 0xx, 1xx, 2xx, 3xx codes |
| US Markets | `us` | `usNDX`, `usAAPL` | Indices and stocks |
| Hong Kong | `hk` | `hkHSI` | Indices |
| Japan | `jp` | `jpN225` | Indices |
| Macro | (none) | `GOLD`, `WTI`, `VIX` | Commodities |

### 2.3 Conversion Utility Design

**Backend: `backend/app/utils/symbol.py`**
```python
from typing import Literal

ExchangePrefix = Literal['sh', 'sz', 'us', 'hk', 'jp', '']

class SymbolUtils:
    """Unified symbol handling utilities"""
    
    US_SYMBOLS = {'NDX', 'SPX', 'DJI', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META'}
    HK_SYMBOLS = {'HSI', 'HKHSI', 'HK2000'}
    JP_SYMBOLS = {'N225', 'NI225', 'NIKKEI'}
    MACRO_SYMBOLS = {'GOLD', 'GLD', 'XAU', 'GC', 'WTIC', 'WTI', 'CL', 'VIX', 'CNHUSD', 'CNH', 'DXY', 'USDX'}
    
    @staticmethod
    def normalize(symbol: str) -> str:
        """Convert any format to canonical format (lowercase with prefix)"""
        s = symbol.strip()
        upper = s.upper()
        
        # Already has prefix
        if s.lower().startswith(('sh', 'sz', 'us', 'hk', 'jp')):
            return s.lower()
        
        # Known symbols
        if upper in SymbolUtils.US_SYMBOLS:
            return 'us' + upper
        if upper in SymbolUtils.HK_SYMBOLS:
            return 'hkHSI'
        if upper in SymbolUtils.JP_SYMBOLS:
            return 'jpN225'
        if upper in SymbolUtils.MACRO_SYMBOLS:
            return upper if upper != 'CNH' else 'CNHUSD'
        
        # A-share: 6-digit code
        clean = ''.join(filter(str.isdigit, s))
        if len(clean) == 6:
            if clean.startswith('6') or clean.startswith('9') or clean in ('000001', '000300', '000688'):
                return 'sh' + clean
            return 'sz' + clean
        
        return s.lower()
    
    @staticmethod
    def extract_code(symbol: str) -> str:
        """Extract bare code from canonical symbol"""
        s = symbol.lower()
        for prefix in ('sh', 'sz', 'us', 'hk', 'jp'):
            if s.startswith(prefix):
                return s[len(prefix):].upper()
        return s.upper()
    
    @staticmethod
    def get_exchange(symbol: str) -> ExchangePrefix:
        """Get exchange prefix from symbol"""
        s = symbol.lower()
        for prefix in ('sh', 'sz', 'us', 'hk', 'jp'):
            if s.startswith(prefix):
                return prefix
        return ''
```

**Frontend: `frontend/src/utils/symbols.js` (Update)**
```javascript
/**
 * Symbol utilities - MUST match backend SymbolUtils
 */
export class SymbolUtils {
  static US_SYMBOLS = new Set(['NDX', 'SPX', 'DJI', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META'])
  static HK_SYMBOLS = new Set(['HSI', 'HKHSI', 'HK2000'])
  static JP_SYMBOLS = new Set(['N225', 'NI225', 'NIKKEI'])
  static MACRO_SYMBOLS = new Set(['GOLD', 'GLD', 'XAU', 'GC', 'WTIC', 'WTI', 'CL', 'VIX', 'CNHUSD', 'CNH', 'DXY', 'USDX'])
  
  /**
   * Convert any format to canonical format (lowercase with prefix)
   */
  static normalize(symbol) {
    const s = String(symbol || '').trim()
    const upper = s.toUpperCase()
    
    // Already has prefix
    if (/^(sh|sz|us|hk|jp)/i.test(s)) return s.toLowerCase()
    
    // Known symbols
    if (this.US_SYMBOLS.has(upper)) return 'us' + upper
    if (this.HK_SYMBOLS.has(upper)) return 'hkHSI'
    if (this.JP_SYMBOLS.has(upper)) return 'jpN225'
    if (this.MACRO_SYMBOLS.has(upper)) return upper === 'CNH' ? 'CNHUSD' : upper
    
    // A-share: 6-digit code
    const clean = s.replace(/\D/g, '')
    if (clean.length === 6) {
      if (clean.startsWith('6') || clean.startsWith('9') || ['000001', '000300', '000688'].includes(clean)) {
        return 'sh' + clean
      }
      return 'sz' + clean
    }
    
    return s.toLowerCase()
  }
  
  /**
   * Extract bare code from canonical symbol
   */
  static extractCode(symbol) {
    const s = symbol.toLowerCase()
    for (const prefix of ['sh', 'sz', 'us', 'hk', 'jp']) {
      if (s.startsWith(prefix)) return s.slice(prefix.length).toUpperCase()
    }
    return s.toUpperCase()
  }
  
  /**
   * Get exchange prefix from symbol
   */
  static getExchange(symbol) {
    const s = symbol.toLowerCase()
    for (const prefix of ['sh', 'sz', 'us', 'hk', 'jp']) {
      if (s.startsWith(prefix)) return prefix
    }
    return ''
  }
}

// Export convenience functions
export const normalizeSymbol = SymbolUtils.normalize
export const extractCode = SymbolUtils.extractCode
export const getExchange = SymbolUtils.getExchange
```

---

## 3. Error Handling Coordination

### 3.1 Current State Documentation

#### Backend Error Handling

**Current Pattern:**
```python
# Most routers use try-except with error_response
@router.get("/endpoint")
async def endpoint_handler():
    try:
        # Business logic
        return success_response(data)
    except Exception as e:
        logger.error(f"[Module] Error: {e}")
        return error_response(f"操作失败: {str(e)}")
```

**Issues Found:**
- No structured error codes in most endpoints
- No request tracing (traceId)
- HTTP status codes always 200 (even for errors)

#### Frontend Error Handling

**Current Implementation (`frontend/src/utils/errorHandler.js`):**
```javascript
export const ErrorType = {
  NETWORK: 'network',
  TIMEOUT: 'timeout',
  SERVER: 'server',
  CLIENT: 'client',
  VALIDATION: 'validation',
  BUSINESS: 'business',
  UNKNOWN: 'unknown',
}

export function classifyError(error) {
  // Classifies errors based on message/name
}

export function getUserMessage(error) {
  const type = classifyError(error)
  return USER_MESSAGES[type] || error.message || '发生错误'
}
```

**Empty Catch Blocks Found:**

| File | Line | Pattern | Issue |
|------|------|---------|-------|
| `FundDashboard.vue` | 754, 962, 1015, 1059, 1124-1127 | `catch (e) {}` | ECharts dispose errors silently ignored |
| `useMarketStream.js` | 243 | `catch (_) {}` | WebSocket send errors silently ignored |
| `symbols.js` | 129 | `catch {}` | Symbol registry load failure silently ignored |

### 3.2 Proposed Error Handling Standard

#### Backend Error Response Format

```python
# backend/app/utils/response.py
from typing import Any, Optional
from datetime import datetime
import uuid

class APIResponse:
    """Standard API response format"""
    
    @staticmethod
    def success(data: Any, message: str = "success") -> dict:
        return {
            "code": 0,
            "message": message,
            "data": data,
            "timestamp": int(datetime.now().timestamp() * 1000),
        }
    
    @staticmethod
    def error(
        message: str,
        code: int = 500,
        data: Any = None,
        details: Optional[dict] = None,
        trace_id: Optional[str] = None,
    ) -> dict:
        return {
            "code": code,
            "message": message,
            "data": data,
            "timestamp": int(datetime.now().timestamp() * 1000),
            "traceId": trace_id or str(uuid.uuid4())[:8],
            "details": details,
        }
```

#### Frontend Error Handler Update

```javascript
// frontend/src/utils/errorHandler.js

export class ApiError extends Error {
  constructor(response) {
    super(response.message || 'Unknown error')
    this.code = response.code
    this.traceId = response.traceId
    this.details = response.details
    this.timestamp = response.timestamp
  }
  
  get isClientError() {
    return this.code >= 100 && this.code < 200
  }
  
  get isServerError() {
    return this.code >= 200 && this.code < 300
  }
  
  get isNetworkError() {
    return this.code >= 300
  }
}

export function handleApiError(response) {
  if (response.code !== 0) {
    throw new ApiError(response)
  }
  return response.data
}
```

### 3.3 Empty Catch Block Fix Plan

**Priority 1: Critical (Silent failures that hide bugs)**
```javascript
// BEFORE: symbols.js line 129
catch {
  return false
}

// AFTER:
catch (error) {
  logger.error('[SymbolRegistry] Failed to load:', error)
  // Fallback to local cache
  return false
}
```

**Priority 2: Acceptable (ECharts dispose - expected to fail sometimes)**
```javascript
// BEFORE: FundDashboard.vue
try { chart.dispose() } catch (e) {}

// AFTER: Add comment explaining why
try { chart.dispose() } catch (e) {
  // ECharts dispose may fail if chart was never initialized
  // This is acceptable - we just want to clean up
}
```

**Priority 3: Low (WebSocket send during close)**
```javascript
// BEFORE: useMarketStream.js line 243
catch (_) {}

// AFTER: Add comment
catch (_) {
  // WebSocket may be closing/closed, ignore send failures
}
```

---

## 4. WebSocket Protocol

### 4.1 Current State Documentation

#### Backend WebSocket Implementation

**Location: `backend/app/routers/websocket.py`**
```python
@router.websocket("/ws/market")
async def ws_market(ws: WebSocket):
    """
    统一 WebSocket 端点。

    客户端消息格式:
      {"action": "subscribe",   "symbols": ["600519", "000858"]}
      {"action": "unsubscribe", "symbols": ["600519"]}
      {"action": "ping"}       → 服务端回复 {"type": "pong"}

    服务端推送格式:
      {"symbol": "600519", "price": 1680.5, "chg": 20.5,
       "chg_pct": 1.23, "volume": 123456, "amount": 98765432,
       "timestamp": 1712467200}
    """
```

**Features:**
- Heartbeat: 55-second timeout, sends `{"type": "pong"}` as probe
- Subscription management via `ws_manager`
- Connection lifecycle handling

#### Frontend WebSocket Implementation

**Location: `frontend/src/composables/useMarketStream.js`**

**Features:**
- Singleton pattern (shared connection across components)
- Reference counting for subscriptions
- Exponential backoff with jitter for reconnection
- 30-second heartbeat interval
- Status tracking: `'idle' | 'connecting' | 'connected' | 'disconnected' | 'failed'`

### 4.2 Proposed WebSocket Protocol Standard

#### Message Format

**Client → Server (Actions)**
```typescript
interface WSMessage {
  action: 'subscribe' | 'unsubscribe' | 'ping';
  symbols?: string[];  // Required for subscribe/unsubscribe
  requestId?: string; // Optional: For request-response correlation
}
```

**Server → Client (Messages)**
```typescript
interface WSTickMessage {
  type: 'tick';
  symbol: string;
  price: number;
  chg: number;
  chg_pct: number;
  volume: number;
  amount: number;
  timestamp: number;
}

interface WSControlMessage {
  type: 'pong' | 'subscribed' | 'unsubscribed' | 'error';
  symbols?: string[];
  message?: string;
  requestId?: string;
}
```

#### Subscription Management

```javascript
// Proposed: Enhanced subscription with confirmation
class WSManager {
  subscribe(symbols) {
    const requestId = crypto.randomUUID()
    this.pendingRequests.set(requestId, { symbols, resolve, reject })
    this.ws.send(JSON.stringify({
      action: 'subscribe',
      symbols,
      requestId
    }))
    
    // Timeout after 5s
    setTimeout(() => {
      if (this.pendingRequests.has(requestId)) {
        this.pendingRequests.delete(requestId)
        reject(new Error('Subscription timeout'))
      }
    }, 5000)
  }
}
```

#### Reconnection Strategy

**Current Implementation (Good):**
- Exponential backoff: 2s → 30s max
- Jitter: ±25% to prevent thundering herd
- Max retries: 10
- Status tracking for UI feedback

**Proposed Enhancement:**
```javascript
const RECONNECT_CONFIG = {
  initialDelay: 1000,    // Start at 1s (faster initial retry)
  maxDelay: 30000,      // Max 30s
  maxRetries: 10,
  jitterFactor: 0.25,   // ±25%
  backoffMultiplier: 1.5,
}
```

---

## 5. State Synchronization

### 5.1 Current State Documentation

#### Frontend State (Pinia)

**Location: `frontend/src/stores/market.js`**
```javascript
export const useMarketStore = defineStore('market', () => {
  // State
  const currentSymbol = ref('sh000001')
  const currentSymbolName = ref('上证指数')
  const symbolRegistry = ref([])
  const quoteCache = ref({})
  
  // Methods
  function setSymbol(symbol, name, color, market) { ... }
  function cacheQuote(symbol, quote) { ... }
  function getCachedQuote(symbol) { ... }
})
```

**State Categories:**
1. **UI State**: Current symbol, theme, sidebar state
2. **Data Cache**: Quote cache, symbol registry
3. **Connection State**: WebSocket status, error state

#### Backend State

**Cache Types:**
1. **In-memory cache**: `_CACHE` in routers (5-minute TTL)
2. **SQLite cache**: `market_data_realtime` table
3. **Scheduler state**: APScheduler jobs

### 5.2 Proposed State Synchronization Strategy

#### Cache Invalidation

```javascript
// Frontend: Listen for cache invalidation events
const { tick, wsStatus } = useMarketStream()

watch(wsStatus, (status) => {
  if (status === 'connected') {
    // Clear stale cache on reconnect
    quoteCache.value = {}
  }
})
```

#### Optimistic Updates

```javascript
// Example: Portfolio update
async function updatePosition(position) {
  // 1. Optimistic update
  const previous = positions.value.find(p => p.id === position.id)
  Object.assign(previous, position)
  
  try {
    // 2. Server sync
    await apiFetch('/api/v1/portfolio/position', {
      method: 'PUT',
      body: position
    })
  } catch (error) {
    // 3. Rollback on failure
    Object.assign(previous, extractCode(position))
    toast.error('更新失败', error.message)
  }
}
```

#### Conflict Resolution

**Strategy: Server Wins**
- WebSocket tick updates always overwrite local cache
- Timestamp comparison for merge decisions
- User action required only for explicit conflicts (e.g., concurrent edits)

---

## 6. Implementation Roadmap

### Phase 1: Foundation (Week 1-2)

1. **Create shared utilities**
   - `backend/app/utils/response.py` - Standard response format
   - `backend/app/utils/symbol.py` - Symbol normalization
   - `frontend/src/utils/symbols.js` - Update to match backend

2. **Fix empty catch blocks**
   - Add logging to all catch blocks
   - Document intentional silent catches

### Phase 2: Migration (Week 3-4)

1. **Backend response standardization**
   - Migrate all routers to use `success_response`/`error_response`
   - Add traceId to all responses

2. **Frontend API layer update**
   - Update `api.js` to use new error handling
   - Add request tracing

### Phase 3: Enhancement (Week 5-6)

1. **WebSocket improvements**
   - Add request-response correlation
   - Enhance subscription confirmation
   - Document all message types

2. **State synchronization**
   - Implement cache invalidation on reconnect
   - Add optimistic update patterns

### Phase 4: Testing & Documentation (Week 7-8)

1. **Integration tests**
   - Test all response formats
   - Test symbol normalization edge cases
   - Test WebSocket reconnection

2. **Documentation**
   - API documentation
   - WebSocket protocol spec
   - Error handling guide

---

## 7. Code Examples for Key Changes

### 7.1 Backend Response Utility

```python
# backend/app/utils/response.py
from typing import Any, Optional, TypeVar, Generic
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')

class APIResponse:
    """Standard API response format for AlphaTerminal"""
    
    @staticmethod
    def success(
        data: Any,
        message: str = "success",
        meta: Optional[dict] = None
    ) -> dict:
        """Create a success response"""
        response = {
            "code": 0,
            "message": message,
            "data": data,
            "timestamp": int(datetime.now().timestamp() * 1000),
        }
        if meta:
            response["meta"] = meta
        return response
    
    @staticmethod
    def error(
        message: str,
        code: int = 500,
        data: Any = None,
        details: Optional[dict] = None,
    ) -> dict:
        """Create an error response"""
        trace_id = str(uuid.uuid4())[:8]
        logger.error(f"[API Error] traceId={trace_id} code={code}: {message}")
        
        return {
            "code": code,
            "message": message,
            "data": data,
            "timestamp": int(datetime.now().timestamp() * 1000),
            "traceId": trace_id,
            "details": details,
        }
    
    @staticmethod
    def paginated(
        items: list,
        total: int,
        page: int = 1,
        page_size: int = 20,
        message: str = "success"
    ) -> dict:
        """Create a paginated response"""
        return APIResponse.success(
            data=items,
            message=message,
            meta={
                "pagination": {
                    "total": total,
                    "page": page,
                    "pageSize": page_size,
                    "totalPages": (total + page_size - 1) // page_size,
                }
            }
        )
```

### 7.2 Frontend API Client Update

```javascript
// frontend/src/utils/apiClient.js
import { logger } from './logger.js'

class ApiClient {
  constructor(baseUrl = '') {
    this.baseUrl = baseUrl
  }
  
  async request(url, options = {}) {
    const { timeout = 8000, ...fetchOptions } = options
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeout)
    
    try {
      const response = await fetch(`${this.baseUrl}${url}`, {
        ...fetchOptions,
        signal: controller.signal,
      })
      clearTimeout(timer)
      
      const data = await response.json()
      
      // Check for API-level errors
      if (data.code !== 0) {
        throw new ApiError(data)
      }
      
      return data.data
    } catch (error) {
      clearTimeout(timer)
      if (error instanceof ApiError) throw error
      throw new ApiError({
        code: error.name === 'AbortError' ? 310 : 302,
        message: error.message,
        traceId: crypto.randomUUID?.()?.slice(0, 8),
      })
    }
  }
  
  get(url) {
    return this.request(url, { method: 'GET' })
  }
  
  post(url, body) {
    return this.request(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  }
}

class ApiError extends Error {
  constructor(response) {
    super(response.message || 'Unknown error')
    this.name = 'ApiError'
    this.code = response.code
    this.traceId = response.traceId
    this.details = response.details
    this.timestamp = response.timestamp
  }
  
  get isClientError() {
    return this.code >= 100 && this.code < 200
  }
  
  get isServerError() {
    return this.code >= 200 && this.code < 300
  }
  
  get isNetworkError() {
    return this.code >= 300
  }
  
  getUserMessage() {
    const messages = {
      100: '请求参数错误',
      101: '未授权，请先登录',
      102: '没有权限执行此操作',
      104: '请求的资源不存在',
      110: '数据验证失败',
      120: '请求过于频繁，请稍后再试',
      200: '服务器内部错误',
      210: '数据库错误',
      302: '第三方服务异常',
      310: '请求超时',
    }
    return messages[this.code] || this.message
  }
}

export const apiClient = new ApiClient('')
export { ApiError }
```

---

## Appendix A: Error Code Reference

| Code | Name | Description | User Message |
|------|------|-------------|--------------|
| 0 | SUCCESS | Request successful | - |
| 100 | BAD_REQUEST | Invalid request parameters | 请求参数错误 |
| 101 | UNAUTHORIZED | Authentication required | 未授权，请先登录 |
| 102 | FORBIDDEN | Permission denied | 没有权限执行此操作 |
| 104 | NOT_FOUND | Resource not found | 请求的资源不存在 |
| 110 | VALIDATION_ERROR | Data validation failed | 数据验证失败 |
| 120 | RATE_LIMITED | Too many requests | 请求过于频繁，请稍后再试 |
| 200 | INTERNAL_ERROR | Server error | 服务器内部错误 |
| 210 | DATABASE_ERROR | Database operation failed | 数据库错误 |
| 302 | THIRD_PARTY_ERROR | External service error | 第三方服务异常 |
| 310 | TIMEOUT_ERROR | Request timeout | 请求超时 |

---

## Appendix B: Symbol Format Reference

| Market | Prefix | Code Format | Example | Notes |
|--------|--------|-------------|---------|-------|
| Shanghai Stock Exchange | `sh` | 6-digit | `sh600519` | 6xx, 9xx, indices 000001/000300/000688 |
| Shenzhen Stock Exchange | `sz` | 6-digit | `sz000001` | 0xx, 2xx, 3xx |
| US Markets | `us` | Variable | `usNDX`, `usAAPL` | Indices and stocks |
| Hong Kong | `hk` | Variable | `hkHSI` | Indices |
| Japan | `jp` | Variable | `jpN225` | Indices |
| Macro Commodities | (none) | Uppercase | `GOLD`, `WTI`, `VIX` | No prefix |

---

*Document Version: 1.0*
*Last Updated: 2026-05-10*
*Author: AlphaTerminal Analysis*

---

## Appendix C: Detailed Backend Response Format Audit

### Response Format Variations by Router

| Router | Success Helper | Error Helper | Error Handling | Consistency |
|--------|---------------|--------------|----------------|-------------|
| `market.py` | `success_response(data, message)` | `error_response(code, message, data)` | Returns envelope | HIGH |
| `news.py` | `success_response(data, message)` | `error_response(code, message, data)` | Returns envelope | HIGH |
| `bond.py` | `success_response(data, message)` | `error_response(code, message, data)` | Returns envelope | HIGH |
| `sentiment.py` | `success_response(data, message)` | `error_response(code, message, data)` | Returns envelope | HIGH |
| `futures.py` | `success_response(data, message)` | `error_response(code, message, data)` | Returns envelope | HIGH |
| `stocks.py` | `success_response(data, message)` | **None** | Returns empty data in envelope | MEDIUM |
| `macro.py` | `success_response(data, message)` | `error_response(message, code)` | **PARAMS REVERSED!** | LOW (BUG) |
| `f9_deep.py` | `success_response(data, message)` | `error_response(message, code)` | **PARAMS REVERSED!** | LOW (BUG) |
| `portfolio.py` | `_ok(data, msg)` | **None** | Uses `HTTPException` (114+ raises) | INCONSISTENT |
| `backtest.py` | **None** | **None** | Inline `{"code": 0/1, ...}` | LOW |

### Critical Bug: `error_response()` Parameter Order Mismatch

**Standard (most routers):**
```python
def error_response(code, message, data=None):  # code FIRST
```

**Inverted (macro.py, f9_deep.py):**
```python
def error_response(message, code=500):  # message FIRST
```

This causes different JSON output:
- Standard: `{"code": 200, "message": "error text"}`
- Inverted: `{"code": 500, "message": "error text"}` (code hardcoded or passed second)

### HTTPException Usage in portfolio.py

`portfolio.py` uses 114+ HTTPException raises, returning FastAPI's default error format:
```json
{"detail": "账户不存在"}
```
Instead of the standard envelope.

---

## Appendix D: WebSocket Protocol Details

### Two WebSocket Channels

| Channel | Endpoint | Purpose | Frontend Consumer |
|---------|----------|---------|-------------------|
| Market Data | `/ws/market` | Real-time stock quotes | `useMarketStream.js` (singleton) |
| Log Stream | `/admin/logs/stream` | Backend log streaming | `AdminDashboard.vue` |

### Market Data WebSocket Message Types

**Client → Server:**
```json
{"action": "subscribe", "symbols": ["600519", "000858"]}
{"action": "unsubscribe", "symbols": ["600519"]}
{"action": "ping"}
```

**Server → Client:**
```json
{"type": "subscribed", "symbols": ["600519", "000858"]}
{"type": "unsubscribed", "symbols": ["600519"]}
{"type": "pong"}
{"symbol": "600519", "price": 1680.5, "chg": 20.5, "chg_pct": 1.23, ...}
```

### Heartbeat Configuration

| Layer | Interval | Mechanism |
|-------|----------|-----------|
| Frontend → Backend | 30 seconds | Client sends `{"action": "ping"}` |
| Backend → Client | 55 seconds timeout | If no message received, server sends `{"type": "pong"}` |

### Reconnection Strategy

- **Exponential backoff**: 2s → 30s max
- **Jitter**: ±25% to prevent thundering herd
- **Max retries**: 10
- **Backoff multiplier**: 1.5

---

## Appendix E: Empty Catch Block Locations

### Frontend Empty Catch Blocks (8 instances)

All in `FundDashboard.vue` for ECharts disposal:
- Line 754: `catch (e) {}` - compareChart dispose
- Line 962: `catch (e) {}` - klineChart dispose
- Line 1015: `catch (e) {}` - navChart dispose
- Line 1059: `catch (e) {}` - assetChart dispose
- Lines 1124-1127: `catch (e) {}` - Multiple chart disposes

**Recommendation**: Add logging:
```javascript
try { chart.dispose() } catch (e) {
  logger.warn('[FundDashboard] Chart dispose error:', e.message)
}
```

### Backend Silent Exceptions

- 50 `except Exception:` blocks without variable capture
- 1 explicit `pass` in `db_writer.py:274` (connection cleanup - acceptable)

---

## Appendix F: Symbol Format Flow Diagram

```
User Input → Frontend normalizeSymbol() → API Request
                                              ↓
                                        Backend _normalize_symbol()
                                              ↓
                                        Internal Processing
                                              ↓
                                        DB Query: _unprefix() removes prefix
                                              ↓
                                        DB Storage: bare code (000001)
                                              ↓
                                        API Response: with prefix (sh000001)
```

### Database Storage Inconsistency

| Table | Symbol Format | Example |
|-------|---------------|---------|
| `market_data_realtime` | WITHOUT prefix | `000001`, `600519` |
| `market_data_daily` | WITHOUT prefix | `000001`, `600519` |
| `positions` | WITH prefix | `sh600519`, `sz000001` |

**Recommendation**: Standardize to always use prefixes in all tables.
