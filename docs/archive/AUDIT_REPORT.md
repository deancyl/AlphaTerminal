# AlphaTerminal 前端代码审计报告

**审计时间**: 2026-04-21  
**项目路径**: `/vol3/@apphome/picoclaw/.picoclaw/workspace/AlphaTerminal/frontend/`

---

## 执行摘要

本次审计发现 **4 个关键问题** 需要修复，主要涉及 API 响应数据解包不一致。

---

## 问题清单与修复方案

### 问题1：DashboardGrid.vue 模板语法 ✅ 无问题

**状态**: 已验证通过

模板中使用的 `:title="item.name"` 写法实际上不存在，代码正确使用了 `{{ item.name }}` 插值表达式，没有 Vue 警告。

---

### 问题2：API 响应数据解包不一致

**严重程度**: 🔴 高

**问题描述**: 
API 返回统一的响应格式 `{ code, message, data: {...} }`，但多处代码对数据解包处理不一致。

**影响范围**:
1. `App.vue` - `fetchHighFreq()` 函数
2. `FullscreenKline.vue` - `fetchData()` 函数  
3. `FullscreenKline.vue` - `fetchQuote()` 函数

**验证结果**:

```bash
# /api/v1/market/overview 实际返回:
{
  "code": 0, "message": "success", 
  "data": { "wind": { "000001": {...}, ... } },
  "timestamp": 1776763146747
}

# /api/v1/market/history/{symbol} 实际返回:
{
  "code": 0, "message": "success",
  "data": { "symbol": "000001", "period": "daily", "history": [...] },
  "timestamp": 1776763153280
}

# /api/v1/market/quote_detail/{symbol} 实际返回:
{
  "code": 0, "message": "success",
  "data": { "name": "上证指数", "symbol": "sh000001", ... },
  "timestamp": 1776763153262
}
```

**修复方案**:

#### 修复 2.1: App.vue - fetchHighFreq()

```javascript
// 修复前:
async function fetchHighFreq() {
  try {
    const d = await apiFetch('/api/v1/market/overview')
    marketOverview.value = d?.wind || d || null  // ❌ 错误
  }
}

// 修复后:
async function fetchHighFreq() {
  try {
    const d = await apiFetch('/api/v1/market/overview')
    // 统一解包: data.wind
    marketOverview.value = d?.data?.wind || d?.wind || d?.data || d || null
    loadError.value = null
  } catch { /* apiErrorState 已记录 */ }
}
```

#### 修复 2.2: FullscreenKline.vue - fetchData()

```javascript
// 修复前:
async function fetchData() {
  const d = await apiFetch(`/api/v1/market/history/${props.symbol}?${params}`)
  const historyArray = d?.history || d || []  // ❌ 错误
}

// 修复后:
async function fetchData() {
  const d = await apiFetch(`/api/v1/market/history/${props.symbol}?${params}`)
  // 统一解包: data.history
  const payload = d?.data || d
  const historyArray = payload?.history || payload || []
}
```

#### 修复 2.3: FullscreenKline.vue - fetchQuote()

```javascript
// 修复前:
async function fetchQuote() {
  const d = await apiFetch(`/api/v1/market/quote_detail/${props.symbol}?_t=${Date.now()}`)
  if (d) quoteData.value = d.data || d  // ⚠️ 不完整
}

// 修复后:
async function fetchQuote() {
  try {
    const d = await apiFetch(`/api/v1/market/quote_detail/${props.symbol}?_t=${Date.now()}`)
    // 统一解包: data
    quoteData.value = d?.data || d || {}
  } catch (e) {
    logger.warn('[FullscreenKline] fetchQuote error:', e.message)
  }
}
```

---

### 问题3：风向标数据展示验证 ✅ 功能正常

**验证结果**: 
- `/api/v1/market/global` 返回宏观数据正常
- `/api/v1/market/macro` 返回宏观数据正常（USD/CNH、黄金、WTI、VHSI）
- DashboardGrid.vue 中 `windItems` 计算属性正确处理了 index 和 macro 数据

**数据结构验证**:
```javascript
// 指数行 (Sina 格式)
{ symbol: "000001", name: "上证指数", price: 4085.07, change_pct: 0.07, category: "index" }

// 宏观行
{ name: "美元/离岸人民币", price: 6.8166, change_pct: 0.0, unit: "", category: "macro" }
```

---

### 问题4：StockScreener 组件检查 ✅ 功能正常

**验证结果**: 
- 分页功能正常（`currentPage`, `pageSize`, `totalPages`）
- 无限滚动正常（IntersectionObserver + scroll 兜底）
- API `/api/v1/market/stocks/search` 返回正常

**代码质量**: 
- `fetchStocks()` 正确构建查询参数
- 搜索防抖 300ms 正常工作
- sentinelEl 用于触底检测

---

### 问题5：板块数据展示 ✅ 功能正常

**验证结果**:
- `/api/v1/market/sectors` 返回正常
- HotSectors 组件接收 `sectorsData` prop 正常
- 数据包含 top_stock（领涨股）用于 K 线跳转

---

### 问题6：全屏K线功能检查 ✅ 功能正常

**验证结果**:
- K 线数据获取正常
- 画线工具组件（DrawingCanvas, DrawingToolbar）已正确引用
- WebSocket 降级到 HTTP 轮询机制已实现

**代码亮点**:
```javascript
// WS 断开时自动降级
watch(wsStatus, (status) => {
  if (status === 'connected') {
    if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null }
  } else if (status === 'disconnected' || status === 'failed') {
    if (!refreshTimer && props.symbol) {
      refreshTimer = setInterval(() => { fetchData(); fetchQuote() }, 30_000)
    }
  }
})
```

---

### 问题7：WebSocket 连接状态 ✅ 机制完善

**验证结果**:
- `useMarketStream.js` 单例模式设计合理
- 重连逻辑带 jitter（±25%）防止惊群
- 引用计数管理订阅/取消订阅
- HTTP 轮询降级机制完善

---

## 修复文件清单

| 文件 | 修复类型 | 优先级 |
|------|----------|--------|
| `src/App.vue` | 数据解包修复 | 🔴 高 |
| `src/components/FullscreenKline.vue` | 数据解包修复 | 🔴 高 |

---

## API 响应格式规范

```
统一格式: { code: 0/1, message: "success"/"error", data: {...}, timestamp: number }

解包规则:
1. 始终检查 d?.data 是否存在
2. 再检查 d?.xxx (直接字段)
3. 最后使用 d 作为兜底
```

---

## 验证检查清单

- [x] DashboardGrid.vue 模板语法
- [x] 风向标数据展示
- [x] 板块数据展示
- [x] 新闻快讯展示
- [x] StockScreener 虚拟滚动
- [x] StockScreener 分页功能
- [x] FullscreenKline 组件
- [x] 画线工具组件
- [x] WebSocket 连接状态
- [x] HTTP 轮询降级

---

## 建议（非阻塞）

1. **日志增强**: 在 api.js 中统一打印 API 错误日志，便于调试
2. **类型检查**: 考虑添加 PropType 验证
3. **错误边界**: 考虑为各组件添加独立的错误边界

---

*报告生成时间: 2026-04-21 17:20*
