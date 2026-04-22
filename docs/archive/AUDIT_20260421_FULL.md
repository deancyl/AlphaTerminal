# AlphaTerminal 代码审计报告

**审计日期**: 2026-04-21  
**审计范围**: 完整读取全部 28 个后端+前端文件  
**审计维度**: 前端 UI 问题 · 前后端协同 · P0/P1/P2 代码质量 · 专业金融平台差距  

---

## 1. 综合评分

**总分: 5.8 / 10**

| 维度 | 得分 | 说明 |
|------|------|------|
| 前端 UI 健壮性 | 5.5 | 空数据处理部分到位，但 watch 风暴/ECharts 实例管理有隐患 |
| 前后端接口契约 | 6.5 | 大部分匹配，copilot context 字段被忽略，SSRF 漏洞 |
| 后端代码质量 | 6.5 | 熔断器 reset 逻辑不完整，部分 error handling 偏弱 |
| 安全性 | 4.0 | news/detail 端点存在 SSRF 漏洞（无 URL 校验） |
| 专业功能完整度 | 3.0 | 相比 Wind/同花顺/Choice，缺失 Level 2/财务/因子/回测等核心模块 |

---

## 2. 问题清单

---

### 🔴 P0 — 崩溃 / 白屏 / 安全漏洞

---

#### P0-1: `news.py` — SSRF 漏洞（严重安全漏洞）

**文件**: `backend/app/routers/news.py` 第 113-165 行  
**严重性**: 严重 — 攻击者可利用 AlphaTerminal 服务器作跳板访问内网资源

```python
@router.get("/news/detail")
async def news_detail(url: str = Query(..., description="新闻原文 URL")):
    ...
    content = akshare.get_news_content(url)  # ⚠️ 直接将用户输入的 url 传给第三方库
```

**问题**: `url` 参数未做任何校验，攻击者可构造 `http://127.0.0.1:6379/`、`file:///etc/passwd`、`http://169.254.169.254/` 等请求，利用 AlphaTerminal 服务器作跳板扫描内网或获取云元数据。

**修复建议**: 
```python
from urllib.parse import urlparse
parsed = urlparse(url)
if parsed.scheme not in ('http', 'https') or parsed.netloc.endswith(('localhost', '127.0.0.1', '0.0.0.0')):
    raise HTTPException(400, "禁止访问内网地址")
```

---

#### P0-2: `copilot.py` — Copilot 上下文参数被完全忽略

**文件**: `backend/app/routers/copilot.py`（实际在 `routers/copilot.py`）  
**前端**: `frontend/src/components/CopilotSidebar.vue` 第 ~420 行  
**严重性**: 功能性错误 — 前端发送的 `context` 参数被后端完全忽略

```python
# CopilotSidebar.vue 发送：
body: JSON.stringify({ prompt: text, context: context || undefined })
# context 由前端构建，包含大盘/板块/宏观数据

# copilot.py 接收后：
prompt = body.get("prompt", "")
_context = body.get("context", "")  # ⚠️ 读取了但从未使用
```

**后果**: 前端根据用户勾选的"大盘/利率/快讯"上下文开关构建的 `context` 字符串被后端完全忽略，Copilot 无法真正使用这些上下文数据。实际只用了 `_fetch_price_context` 拉取的少量股票数据。

**修复建议**: 在 copilot.py 的 prompt 构建逻辑中实际使用 `_context` 变量。

---

#### P0-3: `circuit_breaker.py` — HALF_OPEN→CLOSED 时未重置失败计数

**文件**: `backend/app/services/circuit_breaker.py` 第 ~行  
**严重性**: 熔断器功能损坏 — `consecutive_failures` 从不清零，导致断路器状态机紊乱

```python
# 当前代码：
def record_success(self):
    ...
    if self.state == State.HALF_OPEN:
        self.state = State.CLOSED          # ← 只重置 successes
        self.consecutive_successes = 0       # ← 未重置 failures！
```

**后果**: 假设 HALF_OPEN 状态下失败 2 次（`consecutive_failures=2`）后切到 OPEN，然后第一次成功后切到 HALF_OPEN，但 `consecutive_failures` 仍是 2，再失败 1 次（`2+1=3` 达到阈值）就 OPEN——而正常逻辑应该是 HALF_OPEN 成功后直接 CLOSED，`consecutive_failures` 必须清零。

---

#### P0-4: `IndexLineChart.vue` — watch 触发两次渲染

**文件**: `frontend/src/components/IndexLineChart.vue` 第 ~350-370 行  
**严重性**: 白屏/抖动 — `watch(symbol)` 和 `watch(indicators)` 存在竞态，可能导致 ECharts 实例状态损坏

```javascript
watch(() => props.symbol, async (sym) => {
  currentName.value = props.name || '指标图表'
  await fetchAndRender()          // 第一次 fetchAndRender
  currentName.value = props.name || '指标图表'  // 重复赋值
})

watch(() => props.indicators, () => { fetchAndRender() }, { deep: true })
```

**问题**: 
1. `fetchAndRender` 没有防抖，快速连续调用会触发两次 API 请求
2. `chartInstance.clear()` + `setOption(notMerge:true)` 组合在高频调用时可能产生闪屏
3. `chartInstance` 的 `off('mousemove')` 解绑如果时序不对，可能丢失 mousemove 事件

**修复建议**: 
```javascript
import { useDebounceFn } from '@vueuse/core'
const debouncedFetch = useDebounceFn(fetchAndRender, 300)
watch(() => props.symbol, () => { chartInstance?.clear(); debouncedFetch() })
```

---

### 🟠 P1 — 功能错误 / 严重性能问题

---

#### P1-1: `HotSectors.vue` — onUnmounted 未清理定时器

**文件**: `frontend/src/components/HotSectors.vue` 第 ~80 行  
**严重性**: 内存泄漏 — 定时器在组件销毁后继续运行

```javascript
onMounted(() => {
  fetchSectors()
  refreshTimer = setInterval(fetchSectors, 5 * 60 * 1000)  // 5分钟定时器
})
// ⚠️ 没有 onUnmounted(() => clearInterval(refreshTimer))
```

**修复建议**: 添加 `onUnmounted(() => clearInterval(refreshTimer))`

---

#### P1-2: `DashboardGrid.vue` — watch 竞态可能引发重复 fetch

**文件**: `frontend/src/components/DashboardGrid.vue` 第 ~290-310 行  
**严重性**: 性能 — 无防抖的 watch 在 symbol 快速切换时触发 N 次 fetch

```javascript
watch(() => currentSymbol.value, (sym) => {
  if (sym && sym !== selectedIndex.value) {
    selectedIndex.value = sym
  }
})
```

当 `currentSymbol` 在 100ms 内变化 5 次（Copilot/StockScreener 等组件联动），会触发 5 次 `selectedIndex` 更新，进而可能触发 `watch(selectedIndex)` 的分页周期回退逻辑（虽然后者有防抖但 watch 本身没有）。

**修复建议**: 同样使用 `useDebounceFn` 包装 `setSymbol` 联动逻辑。

---

#### P1-3: `SentimentGauge.vue` — watch(data) 可能在 dispose 后触发

**文件**: `frontend/src/components/SentimentGauge.vue` 第 ~220 行  
**严重性**: 潜在崩溃 — `watch(data, ...)` 回调在 `onUnmounted` 之后仍可能被触发

```javascript
watch(data, () => {
  if (chartInst) chartInst.setOption(...)
})
onUnmounted(() => {
  clearInterval(refreshTimer)
  chartInst?.dispose()    // chartInst = null
  intradayInst?.dispose()  // intradayInst = null
})
```

若 `fetchHistogram()` 在 `onUnmounted` 刚执行完后完成（异步定时器竞争），`watch` 回调仍会执行，此时 `chartInst` 可能已为 null（如果 Vue 的 cleanup 还没运行），但 `if (chartInst)` guard 会防止崩溃。这是个边缘竞态，不严重但存在。

---

#### P1-4: `copilotData.js` — 使用原始 `fetch` 而非 `apiFetch`

**文件**: `frontend/src/services/copilotData.js` 第 ~55-80 行  
**严重性**: API 格式不一致 — `getLimitUpStocks` 等使用原始 `fetch('/api/v1/stocks/limit_up')`，不经过 `apiFetch` 的统一解包/重试/熔断逻辑

```javascript
const res = await apiFetch(`${API_BASE}/api/v1/stocks/search?q=...`, ...)  // 使用 apiFetch
// 但 success_response 包装后 apiFetch 会 extractData 提取 .data
// copilotData.js 里直接 raw fetch，绕过了这些保护
```

混用 `apiFetch` 和 `fetch` 导致：某些请求超时时不重试、某些 5xx 错误不自动降后备数据源、熔断广播不触发。

---

#### P1-5: `NewsFeed.vue` — module-level 计数器跨实例共享

**文件**: `frontend/src/components/NewsFeed.vue` 第 ~180 行  
**严重性**: 状态污染 — 若同一页面有两个 NewsFeed 实例，`forceRefreshCounter` 会相互干扰

```javascript
let forceRefreshCounter = ref(0)  // ⚠️ 模块级，不是组件 data
// 应该: const forceRefreshCounter = ref(0) 在 setup() 里
```

---

#### P1-6: `market.py` — 股票缓存加载逻辑重复覆盖 bug

**文件**: `backend/app/routers/stocks.py` 第 ~行  
**严重性**: 数据完整性 — SZ 市场股票可能永远不会被加载

`_STOCK_CACHE_LOADED = False`，加载顺序：
1. 检查 `STOCK_CACHE` 中是否有 SH 代码 → 没有 → 加载 SH → 设置 `_STOCK_CACHE_LOADED = True`
2. 再次调用 `_load_stock_cache()`（加载 SZ） → 检查 `_STOCK_CACHE_LOADED` → 直接返回（**SZ 股票从未加载**）

```python
if not _STOCK_CACHE:
    _load_stock_cache()  # 只加载 SH，_STOCK_CACHE_LOADED = True
    return  # ← 这里 return 了！
if not _STOCK_CACHE_LOADED:
    _load_stock_cache()  # 永远不会执行到这里
```

---

### 🟡 P2 — 代码不规范 / 潜在风险

---

#### P2-1: `api.js` — `extractData` 对非标准格式返回直接透传

**文件**: `frontend/src/utils/api.js`  
**风险**: 后端某些端点返回非标准格式时，`extractData` 直接返回原始对象，前端代码若期望特定字段会得到 `undefined`

```javascript
export function extractData(response) {
  if (response && typeof response.code === 'number' && 'data' in response) {
    return response.data
  }
  return response  // ⚠️ 非标准格式直接透传，无告警
}
```

某些端点（如 `news/flash` 某些错误路径）可能返回 `{items_stale: true, stale_count: N}` 格式，绕过了 `success_response` 包装，`extractData` 原样返回，`apiFetch` 调用方收到 `{items_stale: true}` 而非 `{data: {items_stale: true}}`。

---

#### P2-2: `IndexLineChart.vue` — `buildOption` 返回 `null` 时的处理

**文件**: `frontend/src/components/IndexLineChart.vue` 第 ~430 行  
**风险**: 低 — `buildOption` 返回 `null` 时，`fetchAndRender` 设置 `chartError = '暂无历史数据'`，UI 显示友好，但未记录日志

```javascript
const opt = buildOption(sortedHist, type)
if (!opt) {
  chartError.value = '暂无历史数据'
  if (chartInstance) chartInstance.clear()  // chartError 遮罩显示，无日志
  return
}
```

---

#### P2-3: `copilotResponse.js` — `formatMarketOverview` 期望索引字段

**文件**: `frontend/src/services/copilotResponse.js` 第 ~60 行  
**风险**: `getMarketOverview()` 返回 `data.indices`，但实际后端返回的是 `wind` 对象（`{wind: {'000001': {...}}}`）

```javascript
// copilotResponse.js:
export function formatMarketOverview(data) {
  if (!data || !data.indices || data.indices.length === 0) {  // ⚠️ 期望 data.indices
    return '📊 【大盘指数】\n暂无数据'
  }
  for (const idx of data.indices) { ... }  // 永远走不到
}
```

但 `copilotData.js` 的 `getMarketOverview()` 已经做了转换：
```javascript
const indices = Object.values(wind).filter(v => v && v.price !== undefined...)
return { indices, meta: res?.meta || {} }
```

所以这个问题已被 `copilotData.js` 吸收，实际不构成 Bug。但 `copilotResponse.js` 的格式函数依赖 `data.indices` 字段是转换后的格式，与后端 `success_response` 直接返回的格式不匹配。

---

#### P2-4: `market.py` — `_get_cached_wind` 异常时无感知

**文件**: `backend/app/routers/market.py` 第 ~行  
**风险**: 若 `fetch_china_indices` 和 `fetch_global_indices` 都抛异常，返回旧缓存可能已完全过期（TTL 10 秒但实际缓存可能更旧）

```python
except Exception as e:
    logger.warning(f"[market_overview] 实时拉取失败，回退缓存: {e}")
    return _REALTIME_CACHE["wind"] or {}  # ⚠️ 如果 wind 也为 None，返回空字典
```

---

#### P2-5: `IndexLineChart.vue` — `hoverBar` 数据未做空值保护

**文件**: `frontend/src/components/IndexLineChart.vue` 第 ~行（hoverBar 部分）  
**风险**: 低 — 虽然模板里用了 `hoverBar.price?.toFixed(2)` 做可选链，但 `_sanitize` 函数里的 `parseFloat` 在 `'-'` 字符串时会返回 `NaN`

```javascript
high: Number(r.high) || 0,  // BOLL 数据中 high='-' 时 Number('-')=NaN
```

不过实际上 BOLL 的 `'-'` 只存在于 MA/BOLL series 数据中，不影响 OHLC 渲染（OHLC 数据是数值），风险较低。

---

#### P2-6: `DashboardGrid.vue` — `handleSectorClick` 假设领涨股代码规则

**文件**: `frontend/src/components/DashboardGrid.vue` 第 ~350 行  
**风险**: `top_stock.code` 为纯 6 位数字时假设以 6 开头是沪、0/3 开头是深，但科创板（688）也以 6 开头，会被错误地加 `sh` 前缀

```javascript
code = code.startsWith('6') ? 'sh' + code : 'sz' + code
// 688 是科创板，实际上交所，应该用 sh
// 但 6 开头的也有可能是深交所的 600xxx... 这条规则本身是对的，但 688 也以 6 开头，会被归入 sh
```

实际上 688xxx 是上交所（沪），被归入 `sh` 是对的。真正的问题是：**创业板（300xxx）、中小板（002xxx）也以 0 开头**，会被归入 `sz`，但 002 是深交所主板，300 是创业板，两者都对。这个规则基本正确，但不够精确（没有考虑 002/300/688 的具体区分）。

---

## 3. API 端点对照表

### 3.1 前端调用的 API vs 后端实际端点

| 前端调用 | 方法 | 实际端点 | 参数匹配 | 状态 |
|----------|------|----------|----------|------|
| `apiFetch('/api/v1/market/overview')` | GET | `/api/v1/market/overview` | ✅ | OK |
| `apiFetch('/api/v1/market/macro')` | GET | `/api/v1/market/macro` | ✅ | OK |
| `apiFetch('/api/v1/market/rates')` | GET | `/api/v1/market/rates` | ✅ | OK |
| `apiFetch('/api/v1/market/global')` | GET | `/api/v1/market/global` | ✅ | OK |
| `apiFetch('/api/v1/market/sectors')` | GET | `/api/v1/market/sectors` | ✅ | OK |
| `apiFetch('/api/v1/market/sentiment/histogram')` | GET | `/api/v1/market/sentiment/histogram` | ✅ | OK |
| `apiFetch('/api/v1/market/sentiment/intraday')` | GET | `/api/v1/market/sentiment/intraday` | ✅ | OK |
| `apiFetch('/api/v1/news/flash')` | GET | `/api/v1/news/flash` | ✅ | OK |
| `fetch('/api/v1/news/force_refresh', {method:'POST'})` | POST | `/api/v1/news/force_refresh` | ✅ | OK |
| `fetch('/api/v1/news/detail?url=...')` | GET | `/api/v1/news/detail` | ✅ | ⚠️ SSRF |
| `apiFetch('/api/v1/market/china_all')` | GET | `/api/v1/market/china_all` | ✅ | OK |
| `apiFetch('/api/v1/market/stocks/search?keyword=...&sort_by=...')` | GET | `/api/v1/market/stocks/search` | ✅ | OK |
| `fetch('/api/v1/chat', {method:'POST'})` | POST | `/api/v1/chat` | ⚠️ context 被忽略 | P0-2 |
| `apiFetch('/api/v1/stocks/limit_up')` | GET | `/api/v1/stocks/limit_up` | ✅ | OK |
| `apiFetch('/api/v1/stocks/limit_down')` | GET | `/api/v1/stocks/limit_down` | ✅ | OK |
| `apiFetch('/api/v1/stocks/unusual')` | GET | `/api/v1/stocks/unusual` | ✅ | OK |
| `apiFetch('/api/v1/stocks/limit_summary')` | GET | `/api/v1/stocks/limit_summary` | ✅ | OK |
| `apiFetch('/api/v1/stocks/search?q=...')` | GET | `/api/v1/stocks/search` | ✅ | OK |
| `apiFetch('/api/v1/market/history/...')` | GET | `/api/v1/market/history/{symbol}` | ✅ | OK |

### 3.2 后端独有 / 前端未使用

| 端点 | 功能 | 前端使用情况 |
|------|------|-------------|
| `/api/v1/market/all_stocks` | 全市场个股缓存 | ❌ 未调用 |
| `/api/v1/market/all_stocks_lite` | 轻量全市场个股 | ❌ 未调用 |
| `/api/v1/market/symbols` | 符号注册表 | ✅ market.js 使用 |
| `/api/v1/market/lookup/{symbol}` | 单标的查询 | ❌ |
| `/api/v1/market/quote/{symbol}` | 单标的实时行情 | ❌ |
| `/api/v1/market/fund_flow` | 板块资金流 | ❌ |
| `/api/v1/market/futures/{symbol}` | 期货历史 | ❌ |
| `/api/v1/market/derivatives` | 衍生品行情 | ❌ |
| `/api/v1/market/quote_v2/{symbol}` | V2 实时行情 | ❌ |
| `/api/v1/market/order_book/{symbol}` | 订单簿（Level 2） | ❌ |
| `/api/v1/bond/...` | 债券数据 | ❌ 未深入审计 |
| `/api/v1/futures/...` | 期货数据 | ❌ 未深入审计 |
| `/api/v1/portfolio/...` | 组合管理 | ❌ 未深入审计 |
| `/api/v1/admin/...` | 管理后台 | ❌ 未深入审计 |
| `/api/v1/backtest/...` | 回测引擎 | ❌ 未深入审计 |

---

## 4. 与专业金融平台（Wind / 同花顺 / Choice）差距分析

### 4.1 数据深度差距

| 功能 | AlphaTerminal | Wind/Choice | 差距等级 |
|------|--------------|-------------|----------|
| Level 2 行情（委托明细、逐笔成交） | ❌ 无 | ✅ 完整 | 🔴 核心 |
| Tick 级历史数据 | ❌ 无 | ✅ 完整 | 🔴 核心 |
| 分钟/日线/周线/月线 | ✅ 日/周/月K+分时 | ✅ 全周期+分钟 | 🟡 次要 |
| 财务三大表（资产负债表等） | ❌ 无 | ✅ 完整 | 🔴 核心 |
| 分析师一致预期数据 | ❌ 无 | ✅ EPS/ROE 等 | 🔴 核心 |
| 基金持仓/重仓股数据 | ❌ 无 | ✅ 季度更新 | 🔴 核心 |
| 股票因子数据（PB/PE/ROE 等） | ✅ 基础 | ✅ 完整 | 🟡 |
| 宏观指标（GDP/CPI/PMI） | ❌ 无（仅有黄金/WTI） | ✅ 完整 | 🔴 核心 |
| 期权数据 | ❌ 无 | ✅ 完整链 | 🔴 核心 |
| 期货曲线/升贴水 | ❌ 无 | ✅ 完整 | 🔴 核心 |

### 4.2 分析工具差距

| 功能 | AlphaTerminal | Wind/Choice | 差距等级 |
|------|--------------|-------------|----------|
| 技术指标（MACD/BOLL/KDJ 等） | ✅ 7个指标 | ✅ 50+ | 🟡 |
| 条件选股（基本面+技术面组合） | ✅ 基础服务端筛选 | ✅ 完整公式系统 | 🟡 |
| 板块资金流（行业/个股） | ✅ 基础 | ✅ 完整（含北向分项） | 🟡 |
| 问财/自然语言选股 | ⚠️ 简单命令 | ✅ 完整问财引擎 | 🔴 |
| 选股回测（事件驱动） | ❌ 无 | ✅ 完整 | 🔴 |
| 组合归因分析（Brinson） | ❌ 无 | ✅ 完整 | 🔴 |
| VaR/CVaR 风险指标 | ❌ 无 | ✅ 完整 | 🔴 |
| 新闻舆情分析 | ⚠️ 简单情感统计 | ✅ 完整 | 🟡 |
| 研报结构化解析 | ❌ 无 | ✅ PDF+结构化 | 🔴 |
| 一键模板（脱水研报/业绩预测） | ❌ 无 | ✅ 完整 | 🔴 |

### 4.3 交易与执行差距

| 功能 | AlphaTerminal | Wind/Choice | 差距等级 |
|------|--------------|-------------|----------|
| 模拟交易（纸盆） | ⚠️ 基础持仓管理 | ✅ 完整（含杠杆/保证金） | 🟡 |
| 闪电下单/快捷交易 | ❌ 无 | ✅ | 🔴 |
| 预警提醒（价格/涨跌/资金流入） | ❌ 无 | ✅ 完整 | 🔴 |
| 持仓实时盈亏计算 | ⚠️ 基础 | ✅ 完整（含持仓分析） | 🟡 |
| 收益归因 | ❌ 无 | ✅ | 🔴 |

### 4.4 平台生态差距

| 维度 | AlphaTerminal | Wind/Choice | 差距等级 |
|------|--------------|-------------|----------|
| 数据延迟（A股） | ~10-30秒（Sina/腾讯） | Level 2: <1s | 🔴 |
| 稳定性/可靠性 | ⚠️ 开源项目 | ✅ 商业级 | 🔴 |
| 客服/技术支持 | ❌ 无 | ✅ 专业团队 | 🔴 |
| 数据合规授权 | ⚠️ 爬虫风险 | ✅ 合规授权 | 🔴 |
| 移动端 App | ❌ 无 | ✅ iOS/Android | 🔴 |
| 多账号管理 | ❌ 单账户 | ✅ 多券商账号 | 🔴 |

---

## 5. 修复优先级排序

### 第一优先级（必须修复，影响核心功能/安全）

| # | 问题 | 文件 | 修复难度 |
|---|------|------|----------|
| P0-1 | SSRF 漏洞（news/detail URL 无校验） | `news.py` | 简单 |
| P0-2 | Copilot context 参数被忽略 | `copilot.py` | 中等 |
| P0-3 | 熔断器 consecutive_failures 不重置 | `circuit_breaker.py` | 简单 |
| P0-4 | IndexLineChart watch 双重触发 + 无防抖 | `IndexLineChart.vue` | 中等 |
| P1-6 | SZ 股票缓存永远不加载 | `stocks.py` | 简单 |

### 第二优先级（重要，影响稳定性/性能）

| # | 问题 | 文件 | 修复难度 |
|---|------|------|----------|
| P1-1 | HotSectors 定时器未清理（内存泄漏） | `HotSectors.vue` | 简单 |
| P1-2 | DashboardGrid watch 竞态（无防抖） | `DashboardGrid.vue` | 简单 |
| P1-4 | copilotData.js 混用 fetch 和 apiFetch | `copilotData.js` | 中等 |
| P1-5 | NewsFeed module-level 状态污染 | `NewsFeed.vue` | 简单 |

### 第三优先级（建议改进）

| # | 问题 | 文件 |
|---|------|------|
| P2-1 | extractData 非标准格式无告警 | `api.js` |
| P2-3 | copilotResponse 格式函数与后端直接格式不匹配 | `copilotResponse.js` |
| P2-4 | wind 缓存异常时无感知返回空 | `market.py` |
| P2-6 | handleSectorClick 假设纯数字代码规则（基本正确但不够精确） | `DashboardGrid.vue` |

---

## 6. 正面发现（做得好）

1. **`database.py` 搜索功能完整**: `search_stocks` 函数实现了完整的服务端过滤+排序+分页，解决了前端全量拉取的性能瓶颈。
2. **ECharts 实例生命周期管理**: `IndexLineChart.vue` 和 `SentimentGauge.vue` 都在 `onUnmounted` 正确调用 `dispose()`，无明显泄漏。
3. **熔断器设计**: `circuit_breaker.py` 的 HALF_OPEN 状态转换逻辑大部分正确，只是 `consecutive_failures` reset 缺失。
4. **数据中心化**: `/market/history` 端点支持按需 AkShare 穿透写入 SQLite，减少重复爬取。
5. **SentimentGauge 双重轮询**: 15 秒内推 + 3 分钟完整刷新，平衡了实时性和资源消耗。
6. **NewsFeed 去重逻辑**: 使用 `Set` 基于 `id` 或 `title` 去重，防止新闻列表重复。
7. **GridStack 锁定机制**: `isLocked` 控制 widget 拖拽，防止意外操作。
8. **前端 API 工具层**: `apiFetch` 的自动重试（指数退避）、统一错误解包、熔断广播是良好的基础设施设计。

---

## 7. 总结

AlphaTerminal 是一个功能较全的 A 股投研终端原型，在数据展示层面（K 线、情绪仪表、新闻快讯、板块热度）已经覆盖了核心场景。前后端接口契约在大部分场景下匹配，代码结构清晰。

**主要短板**集中在：

1. **安全性**: news/detail 端点 SSRF 漏洞必须立即修复
2. **健壮性**: 熔断器状态机 bug、watch 风暴、内存泄漏需系统性修复
3. **数据深度**: 相比 Wind/Choice，缺少 Level 2、财务数据、因子库、回测引擎等核心专业功能
4. **工程成熟度**: 无鉴权、无审计日志、请求无结构化限流、数据合规性存疑

建议分三阶段修复：① 紧急修 SSRF + 熔断器 + SZ 缓存 bug；② 修 watch 防抖 + 内存泄漏；③ 补充数据深度短板（与合规数据源合作）。
