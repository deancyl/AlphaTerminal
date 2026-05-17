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

---

## Theme System (v0.6.37)

### Overview

AlphaTerminal implements a semantic CSS variable-based theme system supporting 4 themes: dark, black, wind, light.

### Architecture

```
index.html (FOUC prevention script)
    ↓
style.css ([data-theme] selectors)
    ↓
tailwind.config.js (CSS variable mapping)
    ↓
useTheme.js (theme state management)
    ↓
echartsTheme.js (dynamic chart colors)
    ↓
BaseKLineChart.vue (incremental update)
```

### Semantic CSS Variables

| Category | Variables | Description |
|----------|-----------|-------------|
| **Background** | `--bg-base`, `--bg-surface`, `--bg-surface-hover` | Base, panel, hover states |
| **Border** | `--border-base`, `--border-light` | Primary and secondary borders |
| **Text** | `--text-primary`, `--text-secondary`, `--text-muted` | Text hierarchy |
| **Brand** | `--color-primary`, `--color-primary-hover` | Brand accent colors |
| **Financial** | `--color-bull`, `--color-bear` | Rise/fall semantic colors |

### Theme Switching

```javascript
import { useTheme } from '@/composables/useTheme'

const { activeTheme, setTheme, onThemeChange } = useTheme()

// Switch theme
setTheme('dark')  // or 'black', 'wind', 'light'

// Subscribe to theme changes (for ECharts)
onThemeChange((theme) => {
  chart.setOption(buildOption(data), { notMerge: false })
})
```

### Tailwind Usage

```vue
<template>
  <!-- Background -->
  <div class="bg-base">Page background</div>
  <div class="bg-surface">Panel background</div>
  
  <!-- Text -->
  <p class="text-primary">Primary text</p>
  <p class="text-secondary">Secondary text</p>
  
  <!-- Financial colors -->
  <span class="text-bull">+2.35%</span>
  <span class="text-bear">-1.28%</span>
</template>
```

### FOUC Prevention

Blocking script in `index.html` sets `data-theme` before Vue renders:

```html
<script>
(function() {
  var saved = localStorage.getItem('alphaterminal-theme');
  var theme = saved || 'dark';
  document.documentElement.setAttribute('data-theme', theme);
})();
</script>
```

### ECharts Integration

```javascript
import { getDynamicThemeColors, getDynamicMarketColors } from '@/utils/echartsTheme'

// Get colors from CSS variables
const colors = getDynamicThemeColors()
const marketColors = getDynamicMarketColors()

// Use in chart option
series.push({
  type: 'candlestick',
  itemStyle: {
    color: marketColors.UP,        // Bull color
    color0: marketColors.DOWN,     // Bear color
  }
})
```

### File Locations

| Component | Path |
|-----------|------|
| CSS Variables | `frontend/src/style.css` |
| Tailwind Config | `frontend/tailwind.config.js` |
| Theme Manager | `frontend/src/composables/useTheme.js` |
| ECharts Theme | `frontend/src/utils/echartsTheme.js` |
| K-Line Chart | `frontend/src/components/BaseKLineChart.vue` |
| FOUC Script | `frontend/index.html` |

---

## Multi-Model Configuration System (v0.6.38)

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  ModelConfigService (Singleton)                              │
│  - Hot-reload: reads from DB on each request                 │
│  - Multi-model: multiple models per provider                 │
│  - Config versioning for session binding                     │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  model_config_db (SQLite)                                    │
│  - Provider configs: llm_openai, llm_deepseek, etc.          │
│  - Model configs: enabled, max_concurrent, context_length    │
│  - Config versions for rollback                              │
└─────────────────────────────────────────────────────────────┘
```

### Configuration Schema

```python
@dataclass
class ModelInstance:
    model_id: str          # Model identifier
    provider: str          # Provider name
    api_key: str           # API key (shared per provider)
    base_url: str          # API base URL
    enabled: bool          # Model enabled status
    is_default: bool       # Default model for provider
    max_concurrent: int    # Max concurrent requests
    context_length: int    # Context window size
    metadata: Dict         # Additional metadata
```

### Hot-Reload Mechanism

- **No in-memory caching**: Each `get_model()` call reads from DB
- **Immediate updates**: Config changes take effect instantly
- **Fallback**: Environment variables if DB config missing

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/config/providers` | GET | Get all provider configs |
| `/api/v1/config/models/{provider}` | GET | Get models for provider |
| `/api/v1/config/models/{provider}/{model}` | POST | Add new model |
| `/api/v1/config/models/{provider}/{model}` | PUT | Update model config |
| `/api/v1/config/models/{provider}/{model}` | DELETE | Remove model |
| `/api/v1/config/test/{provider}/{model}` | POST | Test connection |

### File Locations

| Component | Path |
|-----------|------|
| Service | `backend/app/services/model_config_service.py` |
| DB Helpers | `backend/app/db/model_config_db.py` |
| Router | `backend/app/routers/config.py` |
| Tests | `backend/tests/unit/test_services/test_model_config_service.py` |

---

## Token Monitoring System (v0.6.38)

### Tracking Flow

```
LLM Request → TokenTrackingService.track_usage()
    │
    ├── Calculate cost (pricing catalog)
    │
    ├── Log to token_usage_logs table
    │
    └── Background aggregation thread (5 min)
        │
        └── Aggregate hourly/daily stats
```

### Cost Calculation

Uses pricing catalog (`seed_pricing_catalog`) for accurate costs:

```python
# Example: GPT-4 pricing
prompt_rate = 0.03 / 1000  # $0.03 per 1K prompt tokens
completion_rate = 0.06 / 1000  # $0.06 per 1K completion tokens

cost = prompt_tokens * prompt_rate + completion_tokens * completion_rate
```

### WebSocket Real-Time Updates

Token usage broadcasts via WebSocket:

```json
{
  "type": "token_usage",
  "data": {
    "model_id": "gpt-4",
    "prompt_tokens": 100,
    "completion_tokens": 50,
    "cost_usd": 0.003
  }
}
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/tokens/history` | GET | Get usage history |
| `/api/v1/tokens/stats` | GET | Get aggregated stats |
| `/api/v1/tokens/breakdown/models` | GET | Model breakdown |
| `/api/v1/tokens/breakdown/providers` | GET | Provider breakdown |

### File Locations

| Component | Path |
|-----------|------|
| Service | `backend/app/services/token_tracking_service.py` |
| DB Helpers | `backend/app/db/token_usage_db.py` |
| Pricing Catalog | `backend/app/db/seed_pricing_catalog.py` |
| Tests | `backend/tests/unit/test_services/test_token_tracking_service.py` |

---

## Session Management (v0.6.38)

### Session Lifecycle

```
Create Session → Bind Config Version → Bind Models
    │
    ├── Active: touch_session() extends TTL
    │
    ├── Usage: update_session_usage() tracks tokens/cost
    │
    └── Expired: cleanup thread removes (60s interval)
```

### Config Binding

Sessions bind to specific config versions:

```python
session = session_manager.create_or_get_session(
    session_id="abc123",
    user_id="user-1",
    config_version=5  # Bind to config version 5
)

# Get bound model
model = session_manager.get_bound_model("abc123", "openai")
# Returns: "gpt-4" (from session's bound_models)
```

### TTL and Cleanup

- **Default TTL**: 30 minutes
- **Cleanup interval**: 60 seconds
- **Background thread**: Daemon thread removes expired sessions

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/session/create` | POST | Create new session |
| `/api/v1/session/{id}` | GET | Get session state |
| `/api/v1/session/{id}/bind` | POST | Bind model to session |
| `/api/v1/session/{id}/extend` | POST | Extend session TTL |
| `/api/v1/session/{id}` | DELETE | Delete session |

### File Locations

| Component | Path |
|-----------|------|
| Service | `backend/app/services/session_manager.py` |
| DB Helpers | `backend/app/db/session_db.py` |
| Tests | `backend/tests/unit/test_services/test_session_manager.py` |

---

## Portfolio Module Optimization Summary (v0.6.38)

### Overview

A comprehensive 50-iteration optimization cycle was completed to address the Top 10 QA/UX issues in the Portfolio module.

### Key Improvements

| Issue | Priority | Solution | Status |
|-------|----------|----------|--------|
| No timeout protection | P0 | Add `asyncio.wait_for()` with 30s timeout | ✅ Fixed |
| Missing input validation | P0 | Add `ge=0` to TransactionIn/CashOpIn | ✅ Fixed |
| N+1 query pattern | P0 | Replace recursive build_node with CTE | ✅ Fixed |
| No pagination | P1 | Add limit/offset to positions/lots | ✅ Fixed |
| Error not displayed | P1 | Fix AttributionPanel error state | ✅ Fixed |
| Missing ARIA tabs | P1 | Implement WAI-ARIA tab pattern | ✅ Fixed |
| Double API call | P1 | Combine /lots + /lots/summary | ✅ Fixed |
| Undebounced watchers | P2 | Add 300ms debounce to 6 watchers | ✅ Fixed |
| No virtual scrolling | P2 | VirtualizedTable already in use | ✅ Verified |
| Missing dialog ARIA | P2 | Add dialog accessibility to Transfer modal | ✅ Fixed |

### Performance Improvements

| Metric | Before | After |
|--------|--------|-------|
| API Timeout | None | 30s |
| Query Count (Tree) | 3N | 2 |
| API Calls (OpenLotsPanel) | 2 | 1 |
| Form Re-renders | Every keystroke | 300ms debounced |

### Test Coverage

- **51 new tests** in `test_portfolio_optimization.py`
- **44 tests passing** (7 integration tests need DB)
- Enabled skipped tests in `test_portfolio.py`

### Documentation

See `docs/PORTFOLIO_OPTIMIZATION_SUMMARY.md` for detailed wave-by-wave documentation.

### File Locations

| Component | Path |
|-----------|------|
| Positions Router | `backend/app/routers/portfolio/positions.py` |
| Lots Router | `backend/app/routers/portfolio/lots.py` |
| Schemas | `backend/app/routers/portfolio/schemas.py` |
| Trading Service | `backend/app/services/trading.py` |
| Portfolio Dashboard | `frontend/src/components/PortfolioDashboard.vue` |
| Attribution Panel | `frontend/src/components/AttributionPanel.vue` |
| Open Lots Panel | `frontend/src/components/OpenLotsPanel.vue` |
| Tests | `backend/tests/unit/test_routers/test_portfolio_optimization.py` |

---

## Forex Module Optimization Summary (30 Iterations)

### Overview

A comprehensive 30-iteration optimization cycle was completed to address the Top 10 QA/UX issues in the Forex module.

### Key Improvements

| Issue | Priority | Solution | Status |
|-------|----------|----------|--------|
| Frontend race conditions | P0 | Request versioning + onWatcherCleanup | ✅ Fixed |
| Backend cache without lock | P0 | asyncio.Lock protection | ✅ Fixed |
| ECharts memory leak | P0 | isDisposed checks + chart.off | ✅ Fixed |
| Generic error messages | P1 | ForexError enum + classifyForexError | ✅ Fixed |
| Inconsistent loading states | P1 | Unified skeleton loading | ✅ Fixed |
| No keyboard navigation | P1 | tabindex + @keydown handlers | ✅ Fixed |
| Circuit breaker silent | P1 | circuit_breaker status in API | ✅ Fixed |
| No debounce on symbol switch | P1 | useDebounceFn(300ms) | ✅ Fixed |
| Missing aria-live | P2 | aria-live="polite" on dynamic regions | ✅ Fixed |
| No amount max validation | P2 | Field(le=1000000000) | ✅ Fixed |

### New Files

| File | Purpose |
|------|---------|
| `frontend/src/utils/forexErrors.js` | Error classification utility |
| `backend/tests/unit/test_routers/test_forex.py` | Forex test suite |

### API Changes

- `/api/v1/forex/spot` now returns `circuit_breaker` status object
- `/api/v1/forex/convert` validates `amount <= 1000000000`

### Verification Commands

```bash
# P0-1: Race conditions
grep -c "requestId" frontend/src/components/ForexDashboard.vue  # Expected: 6+

# P0-2: Cache lock
grep -c "asyncio.Lock" backend/app/routers/forex.py  # Expected: 1

# P0-3: ECharts memory
grep -c "isDisposed" frontend/src/components/BaseKLineChart.vue  # Expected: 4+

# P1-4: Error classification
ls frontend/src/utils/forexErrors.js

# P1-5: Loading states
grep -c "animate-pulse" frontend/src/components/CrossRateMatrix.vue  # Expected: 2+

# P1-6: Keyboard navigation
grep -c "@keydown" frontend/src/components/ForexQuotePanel.vue  # Expected: 4+

# P1-7: Circuit breaker
curl http://localhost:60100/api/v1/forex/spot | jq '.circuit_breaker'

# P1-8: Debounce
grep -c "debouncedFetchKline" frontend/src/components/ForexDashboard.vue  # Expected: 2+

# P2-9: ARIA
grep -c "aria-live" frontend/src/components/ForexDashboard.vue  # Expected: 2+

# P2-10: Validation
grep -c "le=1000000000" backend/app/forex_schemas/schemas.py  # Expected: 1

# Tests
pytest backend/tests/unit/test_routers/test_forex.py -v
```

---

## Forex Module Display Fix (v0.6.40)

### Overview

Fixed critical display issues in the Forex module: real-time quotes, cross-rate matrix, and K-line chart rendering.

### Issues Fixed

| Issue | Root Cause | Solution |
|-------|------------|----------|
| Real-time quotes only showing 6 items | Circuit breaker returning empty array | Added `_get_fallback_quotes()` with 10 pairs |
| Cross-rate matrix showing N/A | Missing USD-based pairs for triangular arbitrage | Added EURUSD, GBPUSD, USDJPY, AUDUSD |
| K-line chart not rendering | Grid container had no minimum height | Added `min-h-[400px]` to grid container |

### Fallback Quotes Data

When circuit breaker is open (network blocked), the system returns 10 currency pairs:

| Symbol | Name | Type |
|--------|------|------|
| USDCNY | 美元/人民币 | CNY-based |
| EURCNY | 欧元/人民币 | CNY-based |
| GBPCNY | 英镑/人民币 | CNY-based |
| JPYCNY | 日元/人民币 | CNY-based |
| HKDCNY | 港币/人民币 | CNY-based |
| AUDCNY | 澳元/人民币 | CNY-based |
| EURUSD | 欧元/美元 | USD-based (triangular) |
| GBPUSD | 英镑/美元 | USD-based (triangular) |
| USDJPY | 美元/日元 | USD-based (triangular) |
| AUDUSD | 澳元/美元 | USD-based (triangular) |

### Triangular Arbitrage for Cross-Rates

With USD-based pairs, the matrix can calculate cross-rates:

```
EUR/GBP = EURUSD ÷ GBPUSD
EUR/JPY = EURUSD × USDJPY
GBP/JPY = GBPUSD × USDJPY
AUD/JPY = AUDUSD × USDJPY
```

### K-Line Chart Height Fix

The `BaseKLineChart` component requires minimum 100x100 pixels via `waitForDimensions()`. The grid container needed explicit height:

```vue
<!-- Before -->
<div class="grid grid-cols-1 lg:grid-cols-2 gap-4">

<!-- After -->
<div class="grid grid-cols-1 lg:grid-cols-2 gap-4 min-h-[400px]">
```

### Circuit Breaker Reset Endpoint

```bash
# Reset circuit breaker manually
POST /api/v1/forex/circuit_breaker/reset

# Response
{
  "success": true,
  "state": "closed",
  "message": "Circuit breaker reset successfully"
}
```

### Offline Mode Banner

The offline mode banner now only shows when:
- Circuit breaker is open **AND**
- No data is available

Previously it showed whenever circuit breaker was open, even with fallback data.

### File Locations

| Component | Path |
|-----------|------|
| Fallback Quotes | `backend/app/services/fetchers/forex_fetcher.py` |
| Forex Router | `backend/app/routers/forex.py` |
| Forex Dashboard | `frontend/src/components/ForexDashboard.vue` |
| Circuit Breaker Tests | `backend/tests/unit/test_services/test_circuit_breaker.py` |

### Verification Commands

```bash
# Check spot quotes (should return 10 items)
curl http://localhost:60100/api/v1/forex/spot | jq '.data.quotes | length'

# Check matrix (USD row should have calculated rates)
curl http://localhost:60100/api/v1/forex/matrix | jq '.data.matrix[0]'

# Check K-line history
curl http://localhost:60100/api/v1/forex/history/USDCNH | jq '.data | length'

# Reset circuit breaker
curl -X POST http://localhost:60100/api/v1/forex/circuit_breaker/reset
```

---

## Frontend Performance Optimization (v0.6.41)

### Overview

A comprehensive frontend performance optimization was implemented to reduce API calls, improve chart rendering, and offload heavy calculations to Web Workers.

### Key Improvements

| Feature | Before | After | Impact |
|---------|--------|-------|--------|
| MacroDashboard API calls | 10 parallel requests | 1 BFF request | 90% reduction |
| Chart series rendering | Full data | LTTB sampling | 30-50% faster |
| IndexLineChart calculations | Main thread blocking | Web Worker async | Non-blocking UI |

### MacroDashboard BFF Integration

The MacroDashboard component now uses a single BFF endpoint instead of 10 separate API calls:

```javascript
// Before: 10 parallel requests
const requests = [
  { key: 'overview', fetchFn: () => apiFetchValidated('/api/v1/macro/overview', ...) },
  { key: 'calendar', fetchFn: () => apiFetchValidated('/api/v1/macro/calendar', ...) },
  // ... 8 more requests
]

// After: 1 BFF request with caching
const { data, loading, error, fetch } = useDataCache('/api/v1/macro/dashboard', {
  ttl: 5 * 60 * 1000, // 5 minutes
  staleWhileRevalidate: true
})
```

### ECharts LTTB Sampling

Added `sampling: 'lttb'` to 63 candlestick and line series across 5 components:

| Component | Series Count |
|-----------|-------------|
| BaseKLineChart.vue | 11 |
| FullscreenKline.vue | 22 |
| IndexLineChart.vue | 19 |
| BacktestChart.vue | 2 |
| MacroDashboard.vue | 9 |

Example:
```javascript
// Before
{ name: 'K线', type: 'candlestick', data: klineData }

// After
{ name: 'K线', type: 'candlestick', data: klineData, sampling: 'lttb' }
```

### IndexLineChart Web Worker Integration

Indicator calculations are now offloaded to a Web Worker:

```javascript
import { useIndicatorWorker } from '../composables/useIndicatorWorker.js'

const { calculate, isReady } = useIndicatorWorker()

// Async calculation with fallback
const ma5 = await calculate('MA', { closes }, { period: 5 })
const macd = await calculate('MACD', { closes }, { fast: 12, slow: 26, signal: 9 })
```

### New Utilities

| File | Purpose |
|------|---------|
| `frontend/src/composables/useDataCache.js` | Short-term memory cache with stale-while-revalidate |
| `frontend/src/utils/downsample.js` | LTTB downsampling utility |
| `frontend/src/utils/requestQueue.js` | Request queue for rate limiting |

### Backend Improvements

- **GZipMiddleware**: Added to `backend/app/main.py` for response compression
- **BFF Endpoint**: `/api/v1/macro/dashboard` returns all macro data in single request
- **Caching**: Enhanced caching in `useGracefulDegradation.js`

### File Locations

| Component | Path |
|-----------|------|
| MacroDashboard | `frontend/src/components/MacroDashboard.vue` |
| BFF Endpoint | `backend/app/routers/macro.py` (line 1092) |
| BFF Schema | `frontend/src/schemas/macro.js` |
| Data Cache | `frontend/src/composables/useDataCache.js` |
| Indicator Worker | `frontend/src/composables/useIndicatorWorker.js` |
| Worker Implementation | `frontend/src/workers/indicators.worker.js` |

### Verification Commands

```bash
# Check BFF endpoint
curl http://localhost:60100/api/v1/macro/dashboard | jq '.data | keys'

# Count LTTB sampling in components
grep -c "sampling: 'lttb'" frontend/src/components/BaseKLineChart.vue  # Expected: 11
grep -c "sampling: 'lttb'" frontend/src/components/FullscreenKline.vue # Expected: 22

# Check Web Worker integration
grep -c "useIndicatorWorker" frontend/src/components/IndexLineChart.vue # Expected: 2
```

---

## Core Web Vitals Performance Optimization (v0.6.42)

### Overview

A focused optimization cycle to fix CLS (Cumulative Layout Shift) and INP (Interaction to Next Paint) performance issues, improving Core Web Vitals scores.

### Key Improvements

| Issue | Category | Solution | Impact |
|-------|----------|----------|--------|
| Layout shift on load | CLS | Add min-height to containers | Stable initial render |
| GridStack layout shift | CLS | Add CSS containment | Better rendering isolation |
| Heavy indicator calculations | INP | Enable Web Worker | Non-blocking UI |
| Search input lag | INP | Add 300ms debounce | Reduced main thread work |
| Spread operator overhead | INP | Loop-based min/max | Faster calculations |

### CLS Fixes

#### 1. Main Content Container (App.vue)

```vue
<!-- Before -->
<main class="flex-1 overflow-hidden">
  <!-- content -->
</main>

<!-- After -->
<main class="flex-1 overflow-hidden" style="min-height: 600px;">
  <!-- content -->
</main>
```

#### 2. GridStack Container (DashboardGrid.vue)

```css
/* Before */
.grid-stack {
  min-height: 600px;
}

/* After */
.grid-stack {
  min-height: 600px;
  contain: layout;
}
```

The `contain: layout` CSS property isolates the GridStack's layout from the rest of the page, preventing layout thrashing.

### INP Fixes

#### 1. Web Worker for ForexKLineChart

```javascript
// Before
const chartData = buildChartData(data, period, params, overlay)

// After
const chartData = await buildChartData(data, period, params, overlay, {
  useWorker: true,
  timeout: 10000
})
```

#### 2. Debounced Search (CommandPalette.vue)

```javascript
import { useDebounceFn } from '@vueuse/core'

const debouncedQuery = ref('')
const debouncedSearch = useDebounceFn((value) => {
  debouncedQuery.value = value
}, 300)

watch(query, (newQuery) => {
  debouncedSearch(newQuery)
})
```

#### 3. Loop-Based Min/Max (indicators.js)

```javascript
// Before - Spread operator creates new array
const rh = Math.max(...highs.slice(i - n + 1, i + 1))
const rl = Math.min(...lows.slice(i - n + 1, i + 1))

// After - Loop avoids array allocation
let rh = highs[i - n + 1], rl = lows[i - n + 1]
for (let j = i - n + 2; j <= i; j++) {
  if (highs[j] > rh) rh = highs[j]
  if (lows[j] < rl) rl = lows[j]
}
```

### Performance Impact

| Metric | Before | After |
|--------|--------|-------|
| CLS Score | 0.15+ | < 0.1 |
| INP Score | 200ms+ | < 150ms |
| Search response | Immediate | 300ms debounced |
| Indicator calc | Main thread | Web Worker |

### File Locations

| Component | Path |
|-----------|------|
| App.vue | `frontend/src/App.vue` |
| DashboardGrid.vue | `frontend/src/components/DashboardGrid.vue` |
| ForexKLineChart.vue | `frontend/src/components/forex/ForexKLineChart.vue` |
| CommandPalette.vue | `frontend/src/components/CommandPalette.vue` |
| indicators.js | `frontend/src/utils/indicators.js` |

### Verification Commands

```bash
# Check min-height in App.vue
grep -c "min-height: 600px" frontend/src/App.vue  # Expected: 1

# Check CSS containment
grep -c "contain: layout" frontend/src/components/DashboardGrid.vue  # Expected: 1

# Check Web Worker in ForexKLineChart
grep -c "useWorker: true" frontend/src/components/forex/ForexKLineChart.vue  # Expected: 1

# Check debounce in CommandPalette
grep -c "useDebounceFn" frontend/src/components/CommandPalette.vue  # Expected: 2

# Check loop optimization in indicators.js
grep -c "for (let j = i - n + 2" frontend/src/utils/indicators.js  # Expected: 2
```

---

## Macro Module Bug Fixes (v0.6.43)

### Overview

Fixed critical Pandas KeyError issues causing white screen in macro dashboard, and implemented proper BFF aggregation endpoint.

### Key Improvements

| Issue | Category | Solution | Impact |
|-------|----------|----------|--------|
| Pandas KeyError | Backend | Use .get() for column access | No more crashes |
| White screen on error | Frontend | Add v-else fallback UI | User-friendly error display |
| BFF not implemented | Backend | True aggregation endpoint | Single API call for all data |

### Backend Pandas KeyError Fixes

#### 1. Safe Column Access

```python
# Before - Direct access causes KeyError
ind_df_valid = ind_df[pd.notna(ind_df['今值'])]

# After - Safe access with fallback
value_col = '今值' if '今值' in ind_df.columns else '今值(%)'
if value_col:
    ind_df_valid = ind_df[pd.notna(ind_df[value_col])]
```

#### 2. Dynamic Column Detection

| Original Column | Fallback Column | Endpoint |
|-----------------|-----------------|----------|
| `今值` | `今值(%)` | industrial_production |
| `item` | Check existence first | unemployment |
| `date` | `月份` | unemployment |
| `value` | `失业率` | unemployment |

#### 3. BFF Endpoint Implementation

```python
@router.get("/dashboard")
async def get_macro_dashboard():
    # Fetch all 8 indicators in parallel
    gdp_df, cpi_df, ppi_df, pmi_df, m2_df, sf_df, ind_df, unemp_df = await asyncio.gather(
        fetch_gdp(), fetch_cpi(), fetch_ppi(), fetch_pmi(),
        fetch_m2(), fetch_sf(), fetch_ind(), fetch_unemp()
    )
    
    # Return aggregated data
    return success_response({
        'overview': {...},
        'gdp': {'data': [...]},
        'cpi': {'data': [...]},
        # ... all 8 indicators
        'calendar': [...],
        'last_update': datetime.now().isoformat()
    })
```

### Frontend White Screen Fix

```vue
<!-- Before - No fallback, white screen on error -->
<div v-if="loading && !overview">Loading...</div>
<div v-else-if="overview">Cards...</div>
<!-- Nothing rendered if overview is null! -->

<!-- After - Fallback UI for error state -->
<div v-if="loading && !overview">Loading...</div>
<div v-else-if="overview">Cards...</div>
<div v-else>
  <div class="error-state">
    <p>暂无数据或数据加载失败</p>
    <button @click="refreshNow">重新加载</button>
  </div>
</div>
```

### Error Handling Flow

```
API Request → KeyError (before) → 500 Error → Frontend receives null → White Screen

API Request → Safe .get() (after) → Graceful handling → Frontend receives data or empty → Shows UI
```

### File Locations

| Component | Path |
|-----------|------|
| Macro Router | `backend/app/routers/macro.py` |
| MacroDashboard | `frontend/src/components/MacroDashboard.vue` |

### Verification Commands

```bash
# Test BFF endpoint
curl http://localhost:60100/api/v1/macro/dashboard | jq '.data | keys'

# Test individual endpoints
curl http://localhost:60100/api/v1/macro/overview
curl http://localhost:60100/api/v1/macro/industrial_production?limit=24
curl http://localhost:60100/api/v1/macro/unemployment?limit=24

# Check safe column access in macro.py
grep -c "\.get(" backend/app/routers/macro.py  # Expected: 10+

# Check v-else fallback in MacroDashboard
grep -c "v-else" frontend/src/components/MacroDashboard.vue  # Expected: 1+
```

---

## WebSocket Streaming Module (v0.6.44)

### Overview

Real-time market data streaming infrastructure with circuit breaker protection and HTTP fallback.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  StreamingManager                                            │
│  - Connection lifecycle (start/stop/reconnect)              │
│  - Health monitoring (30s interval)                         │
│  - Message broadcasting to ws_manager                        │
└─────────────────────────────────────────────────────────────┘
       │
       ├── WebSocket Mode (Primary)
       │   └── SinaStreamer → Real-time quotes
       │
       └── HTTP Fallback Mode (Degraded)
           └── HTTP polling every 10s
```

### Circuit Breaker States

| State | Description | Transition |
|-------|-------------|------------|
| CLOSED | Normal operation | Opens after 5 consecutive failures |
| OPEN | Traffic blocked | Transitions to HALF_OPEN after 30s |
| HALF_OPEN | Testing recovery | Closes after 2 successes, opens on failure |

### API Endpoints

```bash
# Start streaming
POST /api/v1/streaming/start
{"symbols": ["sh600519", "sz000001"]}

# Stop streaming
POST /api/v1/streaming/stop

# Get streaming status
GET /api/v1/streaming/status

# Force failover to HTTP
POST /api/v1/streaming/failover
```

### File Locations

| Component | Path |
|-----------|------|
| Streaming Manager | `backend/app/services/streaming/streaming_manager.py` |
| Base Streamer | `backend/app/services/streaming/base_streamer.py` |
| Sina Streamer | `backend/app/services/streaming/sina_streamer.py` |
| Circuit Breaker | `backend/app/services/circuit_breaker.py` |
| Tests | `backend/tests/unit/test_services/test_streaming.py` |

### Verification Commands

```bash
# Check streaming module exists
ls backend/app/services/streaming/

# Run streaming tests
pytest backend/tests/unit/test_services/test_streaming.py -v

# Check circuit breaker
grep -c "CircuitState" backend/app/services/circuit_breaker.py  # Expected: 3
```

---

## OMS State Machine (v0.6.44)

### Overview

Order Management System with 9-state machine, pre-trade validation, and broker adapter interface.

### State Diagram

```
STAGED ──► SUBMITTED ──► VALIDATED ──► PENDING ──► FILLED
   │           │             │           │
   ▼           ▼             ▼           ├──► PARTIAL_FILLED ──► FILLED
CANCELLED   REJECTED      REJECTED       │
                                        ├──► CANCELLED
                                        ├──► EXPIRED
                                        └──► REJECTED
```

### Order Status Enum

| Status | Type | Description |
|--------|------|-------------|
| STAGED | Initial | Order created, not submitted |
| SUBMITTED | Processing | Sent to validation |
| VALIDATED | Processing | Pre-trade checks passed |
| PENDING | Active | Waiting for execution |
| PARTIAL_FILLED | Active | Partially executed |
| FILLED | Terminal | Fully executed |
| CANCELLED | Terminal | Cancelled by user |
| REJECTED | Terminal | Rejected by system |
| EXPIRED | Terminal | Order expired |

### Pre-Trade Validation

| Check | Description |
|-------|-------------|
| Cash Availability | Buy: estimated_cost ≤ cash_balance |
| Position Availability | Sell: quantity ≤ total_shares |
| Price Sanity | Limit price within 10% of market |
| Position Limit | New position ≤ 30% of portfolio |

### API Endpoints

```bash
# Create order
POST /api/v1/oms/orders
{
  "portfolio_id": 1,
  "symbol": "sh600519",
  "direction": "buy",
  "order_type": "limit",
  "quantity": 100,
  "price": 1800.00
}

# Get order status
GET /api/v1/oms/orders/{order_id}

# Cancel order
POST /api/v1/oms/orders/{order_id}/cancel

# Get open orders
GET /api/v1/oms/portfolios/{portfolio_id}/orders
```

### File Locations

| Component | Path |
|-----------|------|
| Order Status | `backend/app/services/oms/order_status.py` |
| Order Engine | `backend/app/services/oms/order_engine.py` |
| Pre-Trade Validation | `backend/app/services/oms/pre_trade_validation.py` |
| Broker Adapter | `backend/app/services/oms/broker_adapter.py` |
| OMS Router | `backend/app/routers/oms.py` |
| Tests | `backend/tests/unit/test_oms.py` |

### Verification Commands

```bash
# Check OMS module exists
ls backend/app/services/oms/

# Run OMS tests
pytest backend/tests/unit/test_oms.py -v

# Check state count
grep -c "class OrderStatus" backend/app/services/oms/order_status.py
```

---

## Audit Trail HMAC-SHA256 (v0.6.44)

### Overview

Hash chain audit trail for SEC 17a-4 compliance with 7-year retention.

### Hash Chain Structure

```
Genesis Hash (64 zeros)
       │
       ▼
Record 1: hash = HMAC-SHA256(prev_hash + data)
       │
       ▼
Record 2: hash = HMAC-SHA256(Record1.hash + data)
       │
       ▼
Record N: hash = HMAC-SHA256(RecordN-1.hash + data)
```

### Audit Record Schema

```python
@dataclass
class AuditChainRecord:
    id: str
    timestamp: datetime
    actor_id: str
    action: str
    resource_type: str
    resource_id: str
    outcome: str
    before_state: Optional[dict]
    after_state: Optional[dict]
    prev_hash: str
    record_hash: str
    chain_index: int
    ip_address: Optional[str]
    user_agent: Optional[str]
```

### Retention Policy

- **Retention Period**: 7 years (2555 days)
- **Genesis Hash**: `"0" * 64`
- **Algorithm**: HMAC-SHA256

### API Endpoints

```bash
# Verify chain integrity
GET /api/v1/audit/verify

# Get audit statistics
GET /api/v1/audit/stats

# Query audit logs
GET /api/v1/audit/logs?actor_id=xxx&action=trade

# Health check
GET /api/v1/audit/health
```

### File Locations

| Component | Path |
|-----------|------|
| Audit Chain | `backend/app/services/audit_chain.py` |
| Audit DB | `backend/app/db/audit_db.py` |
| Audit Router | `backend/app/routers/audit.py` |

### Verification Commands

```bash
# Check audit chain exists
ls backend/app/services/audit_chain.py

# Test verify endpoint
curl http://localhost:60100/api/v1/audit/verify

# Check retention days
grep "SEC_RETENTION_DAYS" backend/app/services/audit_chain.py
```

---

## Options Chain Module (v0.6.44)

### Overview

Options chain data fetcher and T-quote table display for CFFEX and SSE options.

### Supported Exchanges

| Exchange | Products | API |
|----------|----------|-----|
| CFFEX | 沪深300, 中证1000 | `option_cffex_hs300_spot_sina` |
| SSE | ETF Options | `option_sse_greeks_sina` |

### T-Quote Table Layout

```
┌─────────────────┬──────────────┬─────────────────┐
│   Call Options   │ Strike Price │   Put Options   │
│    (看涨期权)    │   (行权价)   │    (看跌期权)   │
├─────────────────┼──────────────┼─────────────────┤
│ Bid/Ask/Vol/IV  │    1800      │ Bid/Ask/Vol/IV  │
│ Delta/Gamma     │    1850      │ Delta/Gamma     │
│ Theta/Vega      │    1900      │ Theta/Vega      │
└─────────────────┴──────────────┴─────────────────┘
```

### API Endpoints

```bash
# Get CFFEX options chain
GET /api/v1/options/cffex/chain?symbol=io2506

# Get Greeks for specific contract
GET /api/v1/options/greeks?code=io2506C1800

# List available contracts
GET /api/v1/options/contracts?exchange=CFFEX

# Health check
GET /api/v1/options/health
```

### Greeks Display

| Greek | Description |
|-------|-------------|
| Delta | Price sensitivity |
| Gamma | Delta sensitivity |
| Theta | Time decay |
| Vega | Volatility sensitivity |
| IV | Implied volatility |

### File Locations

| Component | Path |
|-----------|------|
| Options Fetcher | `backend/app/services/fetchers/options_fetcher.py` |
| Options Router | `backend/app/routers/options.py` |
| Options Analysis | `frontend/src/components/OptionsAnalysis.vue` |
| Options Chain | `frontend/src/components/OptionsChain.vue` |

### Verification Commands

```bash
# Check options fetcher exists
ls backend/app/services/fetchers/options_fetcher.py

# Test options endpoint
curl http://localhost:60100/api/v1/options/health

# Check frontend component
ls frontend/src/components/OptionsChain.vue
```

---

## K-Line News Markers (v0.6.44)

### Overview

Display news events as markers on K-line charts with sentiment coloring.

### Marker Types

| Type | Color | Description |
|------|-------|-------------|
| Bullish | Green (#22c55e) | Positive news (利好) |
| Bearish | Red (#ef4444) | Negative news (利空) |
| Neutral | Yellow (#fbbf24) | Neutral news (中性) |

### Sentiment Keywords

```python
bullish_keywords = ["利好", "上涨", "突破", "新高", "增长", "盈利", "增持", "回购", "中标", "签约"]
bearish_keywords = ["利空", "下跌", "暴跌", "亏损", "减持", "质押", "违约", "诉讼", "调查", "处罚"]
```

### API Endpoint

```bash
# Get news events for symbol
GET /api/v1/news/events/{symbol}?limit=20

# Response
{
  "events": [
    {
      "date": "2024-01-15",
      "headline": "贵州茅台发布业绩预告",
      "type": "bullish",
      "url": "...",
      "source": "eastmoney"
    }
  ],
  "symbol": "600519",
  "total": 5
}
```

### Integration Flow

```
User selects symbol
       │
       ▼
AdvancedKlinePanel.fetchNewsEvents()
       │
       ▼
GET /api/v1/news/events/{symbol}
       │
       ▼
Match dates to K-line prices
       │
       ▼
Pass to BaseKLineChart as :news-events prop
       │
       ▼
markPoint renders diamond markers
       │
       ▼
Hover shows headline in tooltip
```

### File Locations

| Component | Path |
|-----------|------|
| K-Line Chart | `frontend/src/components/BaseKLineChart.vue` |
| Advanced Panel | `frontend/src/components/AdvancedKlinePanel.vue` |
| Tooltip Formatter | `frontend/src/utils/echartsTheme.js` |
| News Router | `backend/app/routers/news.py` |

### Verification Commands

```bash
# Test news events endpoint
curl http://localhost:60100/api/v1/news/events/600519

# Check markPoint in BaseKLineChart
grep -c "markPoint" frontend/src/components/BaseKLineChart.vue  # Expected: 2+

# Check news events prop
grep "newsEvents" frontend/src/components/BaseKLineChart.vue
```

---

## Defensive UX (v0.6.44)

### Overview

Two-step confirmation for critical operations (trades and transfers) to prevent accidental actions.

### Trade Confirmation Flow

```
Step 1: Fill trade form
    │
    ▼
Step 2: Click "确认买入/卖出"
    │
    ▼
Step 3: Review confirmation panel
    │  - Account, Direction, Symbol
    │  - Price, Shares, Total
    │  - Date, Time
    │
    ▼
Step 4: Check "我已确认以上交易信息"
    │
    ▼
Step 5: Click "✓ 确认提交"
    │
    ▼
Execute trade
```

### Transfer Confirmation Flow

```
Step 1: Fill transfer form
    │
    ▼
Step 2: Click "下一步"
    │
    ▼
Step 3: Review confirmation panel
    │  - From Account, To Account
    │  - Amount, Time
    │
    ▼
Step 4: Check "我已确认以上划转信息"
    │
    ▼
Step 5: Click "确认划转"
    │
    ▼
Execute transfer
```

### UI Elements

| Element | Purpose |
|---------|---------|
| Warning Message | "⚠️ 此操作不可撤销，请确认信息无误" |
| Checkbox | Must be checked before submit |
| Cancel Button | "返回修改" - returns to form |
| Confirm Button | "✓ 确认提交" / "确认划转" |

### File Locations

| Component | Path |
|-----------|------|
| Trade Modal | `frontend/src/components/SimulatedTradeModal.vue` |
| Portfolio Dashboard | `frontend/src/components/PortfolioDashboard.vue` |

### Verification Commands

```bash
# Check confirmation in trade modal
grep -c "showConfirmation" frontend/src/components/SimulatedTradeModal.vue  # Expected: 5+

# Check confirmation in portfolio
grep -c "showTransferConfirmation" frontend/src/components/PortfolioDashboard.vue  # Expected: 3+

# Check checkbox requirement
grep "confirmedCheckbox" frontend/src/components/SimulatedTradeModal.vue
```

---

## ML Strategy Module (v0.6.45)

### Overview

The ML Strategy Module provides machine learning-based trading strategies integrated with Microsoft Qlib framework. It includes model management, training, prediction, portfolio optimization, and factor analysis.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend: StrategyCenter.vue                               │
│  ├── Tab 1: 快速回测 → BacktestDashboard.vue                │
│  ├── Tab 2: 策略开发 → StrategyLab.vue                      │
│  └── Tab 3: ML策略 → MLStrategyPanel.vue                    │
│       ├── MLModelManager.vue                                │
│       ├── MLTrainingPanel.vue                               │
│       ├── MLPredictionPanel.vue                             │
│       ├── MLPortfolioOptimizer.vue                          │
│       └── MLFactorAnalysis.vue                              │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  Backend: /api/v1/ml/*                                      │
│  ├── GET/POST /models - Model CRUD                          │
│  ├── POST /train - Train ML model                           │
│  ├── POST /predict - Generate predictions                   │
│  ├── POST /optimize - Portfolio optimization                │
│  ├── POST /factors - Factor analysis                        │
│  └── GET /health - Health check                             │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  Qlib Integration Layer                                     │
│  ├── qlib_init.py - Qlib initialization                    │
│  ├── model_loader.py - Model management                     │
│  ├── feature_pipeline.py - Alpha158/Alpha360 features       │
│  └── data_adapter.py - Data format conversion               │
└─────────────────────────────────────────────────────────────┘
```

### Supported ML Models

| Model | Type | Description |
|-------|------|-------------|
| LightGBM | Gradient Boosting | Fast, accurate for tabular data |
| HIST | Transformer | Graph-based stock prediction |
| GATE | Transformer | Attention-based model |
| GRU | RNN | Sequential pattern recognition |
| LSTM | RNN | Long-term dependencies |
| MLP | Neural Network | Simple feedforward network |
| XGBoost | Gradient Boosting | Alternative boosting model |
| CatBoost | Gradient Boosting | Categorical feature support |

### Feature Sets

| Feature Set | Count | Description |
|-------------|-------|-------------|
| Alpha158 | 158 | Standard Qlib features (MA, MACD, RSI, BOLL, etc.) |
| Alpha360 | 360 | Extended features with longer time windows |

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/ml/models` | List all ML models |
| POST | `/api/v1/ml/models` | Register new model |
| GET | `/api/v1/ml/models/{id}` | Get model details |
| DELETE | `/api/v1/ml/models/{id}` | Delete model |
| POST | `/api/v1/ml/train` | Train model on historical data |
| POST | `/api/v1/ml/predict` | Generate predictions |
| POST | `/api/v1/ml/optimize` | Portfolio optimization |
| POST | `/api/v1/ml/factors` | Factor analysis |
| GET | `/api/v1/ml/health` | Health check |

### Portfolio Optimization Methods

| Method | Description |
|--------|-------------|
| `mvo` | Mean-Variance Optimization |
| `gmv` | Global Minimum Variance |
| `rp` | Risk Parity |
| `inv` | Inverse Volatility (Equal Weight) |

### ML Strategy Integration with Backtest

The backtest module supports ML strategies:

```python
# Strategy types
strategy_type: "ml_lightgbm" | "ml_qlib_hist" | "ml_ensemble"

# ML-specific parameters
params: {
    "model_id": "my_model",
    "feature_set": "Alpha158",
    "threshold": 0.5
}
```

### File Locations

| Component | Path |
|-----------|------|
| MLStrategyPanel | `frontend/src/components/MLStrategyPanel.vue` |
| ML Sub-components | `frontend/src/components/ml/*.vue` |
| ML Schemas | `frontend/src/schemas/ml.js` |
| ML Router | `backend/app/routers/ml.py` |
| Qlib Services | `backend/app/services/qlib/*.py` |
| ML Strategy Classes | `backend/app/services/strategy/ml_strategy.py` |
| Integration Tests | `backend/tests/unit/test_routers/test_ml.py` |

### Verification Commands

```bash
# Check ML endpoints
curl http://localhost:60100/api/v1/ml/health

# Check ML components
ls frontend/src/components/ml/

# Check ML tab in StrategyCenter
grep -c "ML策略" frontend/src/components/StrategyCenter.vue  # Expected: 3

# Check ML strategies in backtest
grep -c "ml_lightgbm" backend/app/routers/backtest.py  # Expected: 4

# Run ML tests
pytest backend/tests/unit/test_routers/test_ml.py -v
```

### Usage Example

```bash
# Train a LightGBM model
curl -X POST http://localhost:60100/api/v1/ml/train \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "my_lightgbm",
    "symbol": "sh600519",
    "start_date": "2022-01-01",
    "end_date": "2024-01-01",
    "feature_set": "Alpha158"
  }'

# Generate predictions
curl -X POST http://localhost:60100/api/v1/ml/predict \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "my_lightgbm",
    "symbol": "sh600519",
    "start_date": "2024-01-01",
    "end_date": "2024-12-31"
  }'

# Optimize portfolio
curl -X POST http://localhost:60100/api/v1/ml/optimize \
  -H "Content-Type: application/json" \
  -d '{
    "method": "mvo",
    "symbols": ["sh600519", "sh600036", "sh601318"],
    "start_date": "2023-01-01",
    "end_date": "2024-01-01"
  }'
```

---

## ML Strategy Module (v0.6.45)

### Overview

The ML Strategy Module provides machine learning-based trading strategies integrated with Microsoft Qlib framework. It includes model management, training, prediction, portfolio optimization, and factor analysis.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend: StrategyCenter.vue                               │
│  ├── Tab 1: 快速回测 → BacktestDashboard.vue                │
│  ├── Tab 2: 策略开发 → StrategyLab.vue                      │
│  └── Tab 3: ML策略 → MLStrategyPanel.vue                    │
│       ├── MLModelManager.vue                                │
│       ├── MLTrainingPanel.vue                               │
│       ├── MLPredictionPanel.vue                             │
│       ├── MLPortfolioOptimizer.vue                          │
│       └── MLFactorAnalysis.vue                              │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  Backend: /api/v1/ml/*                                      │
│  ├── GET/POST /models - Model CRUD                          │
│  ├── POST /train - Train ML model                           │
│  ├── POST /predict - Generate predictions                   │
│  ├── POST /optimize - Portfolio optimization                │
│  ├── POST /factors - Factor analysis                        │
│  ├── POST /risk-metrics - Risk metrics calculation          │
│  ├── GET /methods - List available methods                  │
│  └── GET /health - Health check                             │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  Qlib Integration Layer                                     │
│  ├── qlib_init.py - Qlib initialization                    │
│  ├── model_loader.py - Model management                     │
│  ├── feature_pipeline.py - Alpha158/Alpha360 features       │
│  └── data_adapter.py - Data format conversion               │
└─────────────────────────────────────────────────────────────┘
```

### Supported ML Models

| Model | Type | Description |
|-------|------|-------------|
| LightGBM | Gradient Boosting | Fast, accurate for tabular data |
| HIST | Transformer | Graph-based stock prediction |
| GATE | Transformer | Attention-based model |
| GRU | RNN | Sequential pattern recognition |
| LSTM | RNN | Long-term dependencies |
| MLP | Neural Network | Simple feedforward network |
| XGBoost | Gradient Boosting | Alternative boosting model |
| CatBoost | Gradient Boosting | Categorical feature support |

### Feature Sets

| Feature Set | Count | Description |
|-------------|-------|-------------|
| Alpha158 | 158 | Standard Qlib features (MA, MACD, RSI, BOLL, etc.) |
| Alpha360 | 360 | Extended features with longer time windows |

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/ml/models` | List all ML models |
| POST | `/api/v1/ml/models` | Register new model |
| GET | `/api/v1/ml/models/{id}` | Get model details |
| DELETE | `/api/v1/ml/models/{id}` | Delete model |
| POST | `/api/v1/ml/train` | Train model on historical data |
| POST | `/api/v1/ml/predict` | Generate predictions |
| POST | `/api/v1/ml/optimize` | Portfolio optimization |
| POST | `/api/v1/ml/factors` | Factor analysis |
| POST | `/api/v1/ml/risk-metrics` | Risk metrics calculation |
| GET | `/api/v1/ml/methods` | List available optimization methods |
| GET | `/api/v1/ml/health` | Health check |

### Portfolio Optimization Methods

| Method | Description |
|--------|-------------|
| `mvo` | Mean-Variance Optimization |
| `gmv` | Global Minimum Variance |
| `rp` | Risk Parity |
| `inv` | Inverse Volatility (Equal Weight) |

### ML Strategy Integration with Backtest

The backtest module supports ML strategies:

```python
# Strategy types
strategy_type: "ml_lightgbm" | "ml_qlib_hist" | "ml_ensemble"

# ML-specific parameters
params: {
    "model_id": "my_model",
    "feature_set": "Alpha158",
    "threshold": 0.5
}
```

### File Locations

| Component | Path |
|-----------|------|
| MLStrategyPanel | `frontend/src/components/MLStrategyPanel.vue` |
| ML Sub-components | `frontend/src/components/ml/*.vue` |
| ML Schemas | `frontend/src/schemas/ml.js` |
| ML Router | `backend/app/routers/ml.py` |
| Qlib Services | `backend/app/services/qlib/*.py` |
| ML Strategy Classes | `backend/app/services/strategy/ml_strategy.py` |
| Integration Tests | `backend/tests/unit/test_routers/test_ml.py` |

### Verification Commands

```bash
# Check ML endpoints
curl http://localhost:60100/api/v1/ml/health

# Check ML components
ls frontend/src/components/ml/

# Check ML tab in StrategyCenter
grep -c "ML策略" frontend/src/components/StrategyCenter.vue  # Expected: 3

# Check ML strategies in backtest
grep -c "ml_lightgbm" backend/app/routers/backtest.py  # Expected: 4

# Run ML tests
pytest backend/tests/unit/test_routers/test_ml.py -v
```

### Usage Example

```bash
# Train a LightGBM model
curl -X POST http://localhost:60100/api/v1/ml/train \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "my_lightgbm",
    "symbol": "sh600519",
    "start_date": "2022-01-01",
    "end_date": "2024-01-01",
    "feature_set": "Alpha158"
  }'

# Generate predictions
curl -X POST http://localhost:60100/api/v1/ml/predict \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "my_lightgbm",
    "symbol": "sh600519",
    "start_date": "2024-01-01",
    "end_date": "2024-12-31"
  }'

# Optimize portfolio
curl -X POST http://localhost:60100/api/v1/ml/optimize \
  -H "Content-Type: application/json" \
  -d '{
    "method": "mvo",
    "symbols": ["sh600519", "sh600036", "sh601318"],
    "start_date": "2023-01-01",
    "end_date": "2024-01-01"
  }'
```
