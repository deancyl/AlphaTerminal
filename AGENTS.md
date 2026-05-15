# AlphaTerminal 开发指南

## 服务架构

```
用户浏览器 → 前端服务器(60100) → [API代理] → 后端服务器(8002)
            → [静态文件] → dist/
```

- **前端**: Vite Preview 模式（端口 60100）
  - 提供静态文件（Vue 3 构建产物）
  - 代理 `/api/*` 请求到后端 8002 端口
  - 代理 `/health/*` 请求到后端 8002 端口
  - 代理 `/ws/*` WebSocket 到后端 8002 端口

- **后端**: FastAPI + Uvicorn（端口 8002）
  - 所有业务API
  - WebSocket 实时数据推送
  - 宏观经济数据（akshare）
  - CORS 允许所有来源

## 一键启动脚本

**文件位置**: `./start-services.sh`

### 使用方法

```bash
# 启动所有服务（推荐）
./start-services.sh all

# 重启所有服务（开发调试）
./start-services.sh restart

# 查看服务状态
./start-services.sh status

# 停止所有服务
./start-services.sh stop

# 只启动后端
./start-services.sh backend

# 只启动前端
./start-services.sh frontend
```

### 脚本特性

- ✅ 使用 `setsid` 创建新会话，完全脱离 shell
- ✅ 使用 `disown` 脱离作业控制，Bash 超时不影响
- ✅ 自动检测并释放被占用的端口
- ✅ 自动检测前端是否需要重新构建
- ✅ 健康检查（等待服务就绪）
- ✅ 彩色输出和清晰的错误提示
- ✅ 完整的日志记录到 `/tmp/backend.log` 和 `/tmp/frontend.log`

## 为什么使用 Vite Preview 而不是 Python HTTP 服务器？

### 问题
使用 `python3 -m http.server` 提供静态文件时：
- 前端 API 请求发到 60100 端口（前端服务器）
- Python HTTP 服务器无法代理 `/api/*` 请求
- 导致所有 API 返回 404

### 解决方案
使用 `vite preview` 启动前端：
- 自动应用 `vite.config.js` 中的 proxy 配置
- `/api/*` 请求自动转发到后端 8002 端口
- `/health/*` 请求自动转发到后端 8002 端口
- `/ws/*` WebSocket 自动转发到后端 8002 端口

## 开发检查清单

修改代码后：

1. **前端修改**
   ```bash
   # 修改代码后需要重新构建
   cd frontend
   npm run build
   
   # 然后重启服务（脚本会自动检测并重建）
   ./start-services.sh restart
   ```

2. **后端修改**
   ```bash
   # 使用 --reload 参数，修改后自动重启
   # 无需手动操作
   ```

3. **测试 API**
   ```bash
   # 通过前端代理测试
   curl http://localhost:60100/api/v1/macro/overview
   
   # 直接访问后端
   curl http://localhost:8002/api/v1/macro/overview
   ```

4. **查看日志**
   ```bash
   # 后端日志
   tail -f /tmp/backend.log
   
   # 前端日志
   tail -f /tmp/frontend.log
   ```

## 常见问题

### 1. 数据源异常 - API 连续 N 次失败

**原因**: 前端无法访问后端API
**检查**:
```bash
# 检查后端是否运行
./start-services.sh status

# 直接测试后端
curl http://localhost:8002/api/v1/macro/overview

# 通过前端代理测试
curl http://localhost:60100/api/v1/macro/overview
```

**解决**: 使用 `./start-services.sh restart` 重启服务

### 2. 后端启动后停止

**原因**: Bash 工具超时后会 kill 所有子进程
**解决**: 始终使用 `./start-services.sh` 脚本启动（使用 setsid + disown）

### 3. 前端修改后不生效

**原因**: 需要重新构建 dist 目录
**解决**: 使用 `./start-services.sh restart`，脚本会自动检测并重建

### 4. 宏观数据接口超时

**原因**: akshare 需要从网络抓取数据，第一次加载慢
**解决**:
- 前端超时已增加到 30 秒
- 后端已添加 5 分钟缓存机制
- 第一次加载慢（~10秒），后续很快（~100ms）

### 5. CORS 错误

**原因**: 后端 CORS 配置不允许当前域名
**解决**: 后端已配置 `allow_origins=["*"]`，允许所有来源

## 端口占用处理

如果端口被占用：
```bash
# 查看端口占用
lsof -i :8002
lsof -i :60100

# 使用脚本自动处理（会自动 kill 占用进程）
./start-services.sh restart
```

## 技术栈

- **后端**: Python 3.11, FastAPI, Uvicorn, akshare
- **前端**: Vue 3, Vite, ECharts, Tailwind CSS
- **构建**: npm run build (生成 dist/ 目录)
- **代理**: Vite Preview (内置 proxy)

## 服务信息

- **前端**: http://localhost:60100 (Vite Preview + Proxy)
- **后端**: http://localhost:8002 (FastAPI + Uvicorn)
- **工作目录**: `/vol3/1000/docker/opencode/workspace/AlphaTerminal`
- **构建产物**: `frontend/dist/`

## 网络访问

服务绑定到 `0.0.0.0`，支持：
- 本地访问: `http://localhost:60100`
- 局域网访问: `http://192.168.1.50:60100`
- 其他IP: 任何能访问该机器的网络地址

---

## F9 深度资料功能

### 功能概述

F9 深度资料是一个专业的股票深度分析面板，提供 8 个维度的股票信息：

| Tab | 功能 | 数据源 |
|-----|------|--------|
| 公司概况 | 基本信息、主营业务 | `/api/v1/stocks/quote` |
| 财务摘要 | 25+ 财务指标、8 季度趋势 | `stock_financial_analysis_indicator` |
| 机构持股 | 机构持仓、8 季度趋势 | `stock_institute_hold_detail` |
| 盈利预测 | EPS 预测、机构评级 | `stock_profit_forecast_ths` |
| 股东研究 | Top10 股东、股本变动 | `stock_circulate_stock_holder` |
| 公司公告 | 公司公告列表（分页） | `stock_notice_report` |
| 同业比较 | 行业对比、雷达图 | `stock_individual_info_em` |
| 融资融券 | 融资融券余额、30 日趋势 | `stock_margin_detail_sse/szse` |

### 使用方式

1. **键盘快捷键**: 按 `F9` 键打开深度资料
2. **命令面板**: 按 `Ctrl+K`，输入 `:F9`
3. **右键菜单**: 在股票列表中右键选择 "F9 深度资料"

### API 端点

```bash
# 健康检查
GET /api/v1/f9/health

# 财务摘要
GET /api/v1/f9/{symbol}/financial

# 机构持股
GET /api/v1/f9/{symbol}/institution

# 盈利预测
GET /api/v1/f9/{symbol}/forecast

# 股东研究
GET /api/v1/f9/{symbol}/shareholder

# 公司公告（支持分页）
GET /api/v1/f9/{symbol}/announcements?page=1&page_size=20

# 同业比较
GET /api/v1/f9/{symbol}/peers

# 融资融券
GET /api/v1/f9/{symbol}/margin
```

### 缓存策略

- **缓存时间**: 5 分钟（300 秒）
- **缓存位置**: 后端内存缓存
- **缓存键**: `{endpoint}_{symbol}`

### 测试命令

```bash
# 测试所有 F9 端点
curl http://localhost:60100/api/v1/f9/600519/financial
curl http://localhost:60100/api/v1/f9/600519/institution
curl http://localhost:60100/api/v1/f9/600519/margin
curl http://localhost:60100/api/v1/f9/600519/forecast
curl http://localhost:60100/api/v1/f9/600519/shareholder
curl http://localhost:60100/api/v1/f9/600519/announcements
curl http://localhost:60100/api/v1/f9/600519/peers
```

### 文件位置

- **后端路由**: `/backend/app/routers/f9_deep.py`
- **前端组件**: `/frontend/src/components/StockDetail.vue`
- **共享组件**: `/frontend/src/components/f9/`
  - `DataTable.vue` - 可排序、分页的数据表格
  - `InfoCard.vue` - 关键指标卡片
  - `LoadingSpinner.vue` - 加载指示器
  - `ErrorDisplay.vue` - 错误显示组件
  - `TrendChart.vue` - ECharts 趋势图封装

---

## Strategy Security Model

### Overview

The strategy execution system implements a **defense-in-depth** security model to prevent code injection attacks in user-provided strategy code. All security components work together to provide comprehensive protection.

### Security Architecture

```
User Strategy Code
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: AST Validation (ast_validator.py)                │
│  - Parse code into Abstract Syntax Tree                     │
│  - Detect forbidden imports (os, sys, subprocess, etc.)    │
│  - Detect forbidden functions (eval, exec, compile, etc.)  │
│  - Detect dangerous attribute access (__class__, etc.)     │
│  - Detect infinite loops and memory bombs                  │
└─────────────────────────────────────────────────────────────┘
       │ (Pass)
       ▼
┌─────────────────────────────────────────────────────────────┐
│  Layer 2: Sandboxed Execution (sandbox.py)                  │
│  - Restricted __builtins__ (no dangerous functions)        │
│  - Whitelisted modules (pandas, numpy, math only)          │
│  - No file system access                                    │
│  - No network access                                        │
│  - No system calls                                          │
└─────────────────────────────────────────────────────────────┘
       │ (Pass)
       ▼
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: Timeout Protection (script_strategy.py)           │
│  - 30 second execution timeout                              │
│  - SIGALRM-based enforcement                                │
│  - Automatic cleanup on timeout                             │
└─────────────────────────────────────────────────────────────┘
       │ (Pass)
       ▼
┌─────────────────────────────────────────────────────────────┐
│  Layer 4: Audit Trail (audit.py)                           │
│  - Log all executions with user ID                         │
│  - Store code hash for integrity                           │
│  - Track security errors and timeouts                       │
│  - Detect suspicious activity patterns                      │
└─────────────────────────────────────────────────────────────┘
```

### Blocked Attack Patterns

The security model blocks these 10 malicious code patterns:

| Pattern | Description | Blocked By |
|---------|-------------|------------|
| `__import__('os').system('rm -rf /')` | Dynamic import attack | AST + Sandbox |
| `open('/etc/passwd').read()` | File system access | AST + Sandbox |
| `subprocess.Popen(['cat', '/etc/passwd'])` | Process execution | AST + Sandbox |
| `eval("__import__('os').system('id')")` | Dynamic code execution | AST + Sandbox |
| `exec("import os; os.system('id')")` | Dynamic code execution | AST + Sandbox |
| `(lambda: __import__('os'))()` | Lambda-based import | AST + Sandbox |
| `getattr(__builtins__, 'eval')('1+1')` | Reflection attack | AST + Sandbox |
| `''.__class__.__base__.__subclasses__()` | Class introspection | AST |
| `while True: pass` | Infinite loop | AST + Timeout |
| `[0] * 10**10` | Memory bomb | AST |

### API Endpoints

#### Validate Strategy Code

```bash
POST /api/v1/strategy/validate
Content-Type: application/json

{
  "code": "def on_bar(ctx, bar):\n    ctx.buy(bar['close'], 100)"
}

# Response
{
  "is_valid": true,
  "errors": [],
  "warnings": [],
  "security_score": 100
}
```

### Security Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `timeout` | 30s | Maximum execution time |
| `validate_security` | true | Enable AST validation |
| `allow_pandas` | true | Allow pandas import |
| `allow_numpy` | true | Allow numpy import |
| `max_memory_mb` | 512 | Maximum memory allocation |

### File Locations

| Component | Path |
|-----------|------|
| AST Validator | `/backend/app/services/strategy/ast_validator.py` |
| Sandbox | `/backend/app/services/strategy/sandbox.py` |
| Secure Executor | `/backend/app/services/strategy/script_strategy.py` |
| Audit Trail | `/backend/app/services/strategy/audit.py` |
| Security Tests | `/backend/tests/unit/test_services/test_script_strategy_security.py` |

### Running Security Tests

```bash
cd backend
pytest tests/unit/test_services/test_script_strategy_security.py -v
```

### Audit Trail Queries

```bash
# Get audit statistics
curl http://localhost:8002/api/v1/strategy/audit/stats

# Get recent executions
curl http://localhost:8002/api/v1/strategy/audit/records?limit=10

# Check suspicious activity
curl http://localhost:8002/api/v1/strategy/audit/suspicious?user_id=xxx
```

### Best Practices

1. **Always validate before execution**: Use `/api/v1/strategy/validate` endpoint
2. **Monitor audit trail**: Check for security errors and suspicious activity
3. **Set appropriate timeouts**: Adjust based on strategy complexity
4. **Review code hashes**: Detect repeated malicious submissions
5. **Rate limit submissions**: Prevent abuse of validation endpoint

---

## Optimization Cycle Summary (70 Iterations)

### Overview

A comprehensive 70-iteration optimization cycle was completed to address the top 10 QA/UX issues. The cycle spanned 12 waves covering security, reliability, UX, performance, and configuration improvements.

### Key Metrics

| Metric | Value |
|--------|-------|
| Total Iterations | 70 |
| Waves Completed | 12 |
| New Tests Added | 195+ |
| Files Modified | 50+ |

### Wave Summary

| Wave | Focus | Key Deliverables |
|------|-------|------------------|
| 1-2 | Security | AST validation, sandboxed execution |
| 3-4 | Error Handling | Safe math utilities, user-visible errors |
| 5-6 | Reliability | Rate limiting, WebSocket heartbeat |
| 7 | Performance | ECharts memory leak prevention |
| 8 | Configuration | Pydantic settings, externalized values |
| 9 | Performance | Virtual scrolling for large datasets |
| 10 | UX | Input validation, FormField component |
| 11 | Integration | Build verification, test suite |
| 12 | Documentation | OPTIMIZATION_SUMMARY.md, cleanup |

### Documentation

See `docs/OPTIMIZATION_SUMMARY.md` for detailed wave-by-wave documentation.

---

## Macro Module Optimization Summary (50 Iterations)

### Overview

A comprehensive 50-iteration optimization cycle was completed to address the Top 10 QA/UX issues in the macroeconomic module.

### Key Improvements

| Issue | Priority | Solution | Status |
|-------|----------|----------|--------|
| Backend no timeout protection | P0 | Add `asyncio.wait_for()` with 30s timeout | ✅ Fixed |
| Chart white screen on error | P0 | Create `useEChartsErrorBoundary` composable | ✅ Fixed |
| No input validation | P1 | Add `Query(ge=1, le=100)` validation | ✅ Fixed |
| No rate limiting | P1 | Add macro to rate_limit.py (30 req/60s) | ✅ Fixed |
| No auto-refresh | P1 | Create `useSmartPolling` with Visibility API | ✅ Fixed |
| Zod schemas not used | P1 | Integrate `apiFetchValidated()` for all endpoints | ✅ Fixed |
| No ARIA accessibility | P2 | Add aria-label, tabindex to all cards/charts | ✅ Fixed |
| No chart empty states | P2 | Add empty state handling with retry button | ✅ Fixed |
| Error messages expose internals | P2 | Sanitize error messages | ✅ Fixed |
| No test coverage | P2 | Create test_macro.py with 23 tests | ✅ Fixed |

### New Files

| File | Purpose |
|------|---------|
| `frontend/src/composables/useEChartsErrorBoundary.js` | ECharts error handling |
| `backend/tests/unit/test_routers/test_macro.py` | Macro test suite |
| `docs/MACRO_OPTIMIZATION_SUMMARY.md` | Optimization documentation |

### Test Coverage

| Category | Tests | Status |
|----------|-------|--------|
| Endpoint Tests | 13 | ✅ Pass |
| Validation Tests | 4 | ✅ Pass |
| Error Handling Tests | 2 | ✅ Pass |
| Cache Tests | 1 | ✅ Pass |
| Timeout Tests | 2 | ✅ Pass |
| Rate Limit Tests | 1 | ✅ Pass |
| **Total** | **23** | **100% Pass** |

### Verification Commands

```bash
# Timeout protection
grep -c "asyncio.wait_for" backend/app/routers/macro.py  # Expected: 12+

# ECharts error handling
ls frontend/src/composables/useEChartsErrorBoundary.js

# Input validation
curl "http://localhost:8002/api/v1/macro/gdp?limit=0"  # Expected: 422

# Rate limiting
grep '"macro":' backend/app/config/rate_limit.py

# Auto-refresh
grep -c "useSmartPolling" frontend/src/components/MacroDashboard.vue

# ARIA accessibility
grep -c 'aria-label' frontend/src/components/MacroDashboard.vue  # Expected: 32+

# Tests
pytest tests/unit/test_routers/test_macro.py -v  # Expected: 23 passed
```

---

## Futures Module Optimization Summary (50 Iterations)

### Overview

A comprehensive optimization cycle was completed to address the Top 10 QA/UX issues in the futures market module.

### Key Improvements

| Issue | Priority | Solution | Status |
|-------|----------|----------|--------|
| Fake chart data | P0 | Replace Math.random() with real API | ✅ Fixed |
| Mock IF/IC/IM data | P0 | Use akshare futures_zh_realtime | ✅ Fixed |
| WebSocket no fallback | P1 | Add HTTP polling after 3 reconnects | ✅ Fixed |
| API timeout | P1 | Add 10s asyncio.wait_for protection | ✅ Fixed |
| Input validation | P1 | Add regex validation for symbols | ✅ Fixed |
| Rate limiting | P1 | Add 60 req/min for futures endpoints | ✅ Fixed |
| Chart rebuild frequency | P2 | Increase debounce to 300ms | ✅ Fixed |
| Loading states | P2 | Add skeleton + fade transition | ✅ Fixed |
| Error boundary | P2 | Add error display + retry button | ✅ Fixed |
| Heatmap interaction | P2 | Add click handler + emit event | ✅ Fixed |

### New API Endpoints

| Endpoint | Description | Timeout |
|----------|-------------|---------|
| `/api/v1/futures/index_history` | Historical K-line for IF/IC/IM | 10s |
| `/api/v1/futures/main_indexes` | Real-time stock index futures | 5s |

### WebSocket Improvements

- HTTP polling fallback after 3 failed reconnects
- "HTTP模式" status indicator in UI
- 5-second polling interval

### Test Coverage

| Category | Tests | File |
|----------|-------|------|
| P0 Integration | 22 | `test_futures_real_data.py` |
| P1 Reliability | 17 | `test_futures_rate_limit.py` |
| P2 UX | 26 | `FuturesDashboard.ux.test.js` |
| E2E Workflow | 3 | `test_futures_workflow.py` |

**Total: 68 new tests**

### Files Modified

**Backend**:
- `backend/app/routers/futures.py` - Real data API, timeout protection
- `backend/app/config/rate_limit.py` - Futures rate limits

**Frontend**:
- `frontend/src/components/FuturesDashboard.vue` - Loading, error, interaction
- `frontend/src/components/FuturesPanel.vue` - Input validation, refresh
- `frontend/src/components/FuturesMainChart.vue` - Real chart data, debounce
- `frontend/src/components/TermStructureChart.vue` - Refresh button
- `frontend/src/composables/useMarketStream.js` - HTTP polling fallback
- `frontend/src/style.css` - Fade transition CSS

### Troubleshooting

**Q: Futures data shows "mock" source**
A: Check akshare connectivity. The API will fallback to mock data if real data fetch fails.

**Q: WebSocket shows "HTTP模式"**
A: This is normal - HTTP polling activates after 3 failed WebSocket reconnects.

**Q: Term structure request times out**
A: 10-second timeout is intentional. If akshare is slow, request returns timeout error.

---

## Frontend Utilities

### Safe Math Utilities (`frontend/src/utils/safeMath.js`)

Prevents division by zero and NaN values in calculations.

```javascript
import { safeDivide, safePercent, safeAverage } from '@/utils/safeMath'

// Safe division with default value
safeDivide(100, 0, 0)      // Returns 0 (not Infinity)
safeDivide(100, 10, 0)     // Returns 10

// Safe percentage calculation
safePercent(50, 100, 0)    // Returns 50
safePercent(50, 0, 0)      // Returns 0 (not NaN)

// Safe average with null filtering
safeAverage([1, null, 3])  // Returns 2
safeAverage([])            // Returns 0
```

### Chart Manager (`frontend/src/utils/chartManager.js`)

Centralized ECharts instance management with automatic cleanup.

```javascript
import { createChartManager, safeDispose, safeResize } from '@/utils/chartManager'

// Create a chart manager
const manager = createChartManager()

// Register chart with auto-resize
manager.register('myChart', chartInstance, domElement, { resizeDelay: 100 })

// Safe operations (check isDisposed internally)
safeDispose(chartInstance)
safeResize(chartInstance)
safeSetOption(chartInstance, option)

// Cleanup all charts
manager.disposeAll()
```

### useECharts Composable (`frontend/src/composables/useECharts.js`)

Vue composable for memory-safe ECharts usage with automatic lifecycle management.

```javascript
import { useECharts } from '@/composables/useECharts'

const containerRef = ref(null)
const { initChart, setOption, resize, dispose } = useECharts(containerRef, {
  theme: 'dark',
  autoResize: true,
  resizeDelay: 100
})

// Initialize chart
onMounted(async () => {
  const chart = await initChart()
  setOption({ xAxis: {...}, series: [...] })
})

// Automatic cleanup on unmount
```

### FormField Component (`frontend/src/components/FormField.vue`)

Reusable form field with real-time validation feedback.

```vue
<FormField
  v-model="price"
  label="Stock Price"
  type="number"
  :min="0"
  :max="10000"
  :error="errors.price"
  hint="Enter a value between 0 and 10000"
  required
  showSuccess
/>
```

### VirtualizedTable Component (`frontend/src/components/VirtualizedTable.vue`)

High-performance table for large datasets using virtual scrolling.

```vue
<VirtualizedTable
  :items="stockList"
  :columns="[
    { key: 'symbol', label: '代码', width: '80px' },
    { key: 'name', label: '名称', width: '120px' },
    { key: 'price', label: '价格', format: 'price', align: 'right' }
  ]"
  :item-size="36"
  :buffer="200"
  @row-click="handleRowClick"
/>
```

---

## Backend Utilities

### Rate Limiting Middleware (`backend/app/middleware/rate_limit.py`)

IP-based rate limiting with endpoint-specific limits.

**Configuration** (`backend/app/config/rate_limit.py`):

| Endpoint | Limit | Period |
|----------|-------|--------|
| Global | 100 | 60s |
| /api/v1/backtest/run | 10 | 60s |
| /api/v1/strategy/validate | 20 | 60s |
| /api/v1/copilot/* | 30 | 60s |
| /health/* | Exempt | - |

**Response Headers**:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1699999999
Retry-After: 45  (on 429)
```

### WebSocket Heartbeat (`backend/app/services/ws_manager.py`)

Automatic connection health monitoring.

**Configuration**:
```python
PING_INTERVAL = 25      # Send ping every 25 seconds
PONG_TIMEOUT = 10       # Wait 10 seconds for pong
CLEANUP_INTERVAL = 30   # Clean dead connections every 30 seconds
```

**Protocol**:
1. Server sends `{"type": "ping"}` every 25 seconds
2. Client must respond with `{"action": "pong"}`
3. 3 missed pongs triggers automatic reconnect
4. Dead connections cleaned up every 30 seconds

### Pydantic Settings (`backend/app/config/settings.py`)

Centralized configuration from environment variables.

```python
from app.config.settings import get_settings

settings = get_settings()
print(settings.HTTP_PROXY)
print(settings.DEBUG_MODE)  # Default: False for security
```

**Environment Variables**:
```bash
HTTP_PROXY=http://192.168.1.50:7897
ALPHA_VANTAGE_API_KEY=your_key_here
ADMIN_API_KEY=admin_secret
ENV=production
DEBUG_MODE=false
ALLOWED_ORIGINS=https://yourdomain.com
```

---

## Testing

### Running Tests

```bash
# Backend tests
cd backend
pytest tests/ -v

# Specific test categories
pytest tests/unit/test_services/test_script_strategy_security.py -v  # Security
pytest tests/unit/test_middleware/test_rate_limit.py -v              # Rate limiting
pytest tests/unit/test_services/test_ws_heartbeat.py -v              # WebSocket
pytest tests/unit/test_config/test_settings.py -v                    # Config

# Frontend build
cd frontend
npm run build
```

### Test Categories

| Category | Tests | Location |
|----------|-------|----------|
| Security | 22 | `test_script_strategy_security.py` |
| Rate Limiting | 33 | `test_rate_limit.py` |
| WebSocket | 15 | `test_ws_heartbeat.py` |
| Error Handling | 36 | Various |
| Configuration | 46 | `test_settings.py` |
| Performance | 14 | Various |

### Expected Test Behavior

Note: Rate limiting tests may show 429 responses. This is **expected behavior** as tests intentionally exceed limits to verify the middleware works correctly.

---

## Copilot UI Components (v0.6.36)

### Overview

The Copilot sidebar provides an AI-powered investment research assistant with enhanced UI styling.

### Component Structure

```
frontend/src/components/copilot/
├── CopilotHeader.vue          # Header with title and controls
├── CopilotQuickCommands.vue   # Quick command buttons
├── CopilotContextSelector.vue # Context and model selection
├── CopilotMessageList.vue     # Message display with markdown
├── CopilotInput.vue           # Auto-expand input textarea
└── CopyButton.vue             # Hover-to-reveal copy button
```

### UI Features

| Feature | Description |
|---------|-------------|
| **Visual Separation** | `bg-theme-secondary` background, darker than main area |
| **User Bubble** | Minimal style - no background/border, right-aligned |
| **AI Messages** | Full-width markdown, `text-gray-200` color |
| **Code Blocks** | Darker background, hover-to-reveal copy button |
| **Input Area** | Auto-expand textarea (max 150px/6 rows) |
| **Send Button** | Glowing effect with `animate-pulse` |

### CopyButton Component

```vue
<template>
  <button
    class="absolute top-2 right-2 px-2 py-1 rounded text-xs
           opacity-0 group-hover:opacity-100 transition-opacity duration-200
           bg-agent-blue/10 border border-agent-blue/30"
    @click="handleCopy"
    aria-label="复制代码"
  >
    <span v-if="copied">✓ 已复制</span>
    <span v-else>📋 复制</span>
  </button>
</template>
```

### Markdown Renderer

Custom MarkdownIt fence renderer wraps code blocks with `group` class:

```javascript
mdParser.renderer.rules.fence = function(tokens, idx, options, env, self) {
  const code = token.content.trim()
  const encodedCode = encodeURIComponent(code)
  return `<pre class="group" data-code="${encodedCode}">...</pre>`
}
```

### CSS Styles

File: `frontend/src/styles/copilot-markdown.css`

| Selector | Changes |
|----------|---------|
| `.copilot-markdown` | Added `color: #e5e7eb` (gray-200) |
| `.copilot-markdown pre` | Enhanced background (rgba(0,0,0,0.7)), stronger border |
| `.copilot-markdown pre code` | `color: #e5e7eb` |
| Removed | Old `::before` pseudo-element for copy button |

### Auto-expand Textarea

```javascript
function autoResize() {
  const textarea = textareaRef.value
  if (!textarea) return
  textarea.style.height = 'auto'
  const newHeight = Math.min(textarea.scrollHeight, 150)
  textarea.style.height = newHeight + 'px'
}
```

### File Locations

| Component | Path |
|-----------|------|
| CopyButton | `frontend/src/components/copilot/CopyButton.vue` |
| Message List | `frontend/src/components/copilot/CopilotMessageList.vue` |
| Input | `frontend/src/components/copilot/CopilotInput.vue` |
| Markdown CSS | `frontend/src/styles/copilot-markdown.css` |
| Markdown Renderer | `frontend/src/composables/useCopilotMarkdown.js` |
