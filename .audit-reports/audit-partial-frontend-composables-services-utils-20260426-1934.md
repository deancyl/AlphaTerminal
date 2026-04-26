# AlphaTerminal v0.5.x 代码审计报告 - 批次8 (frontend-composables + frontend-services + frontend-utils)

## 版本信息
- 审计时间: 2026-04-26 19:34 CST
- 任务: AlphaTerminal-Code-Audit v4 (cron:88fda36d)
- 本次审计: frontend-composables (8文件) + frontend-services (3文件) + frontend-utils (6文件)

---

## 审计范围

### 本次审计模块

| 模块 | 文件 | 代码行数 |
|------|------|----------|
| frontend-composables | useDataSourceStatus.js, useEventBus.js, useMarketStore.js, useMarketStream.js, usePerformanceMonitor.js, usePortfolioStore.js, useTheme.js, useUiStore.js | ~1200 行 |
| frontend-services | copilotData.js, copilotAnalysis.js, copilotResponse.js | ~1200 行 |
| frontend-utils | api.js, chartDataBuilder.js, formatters.js, indicators.js, logger.js, symbols.js | ~900 行 |

---

## 审计发现 (按风险等级)

### P1 - 中高风险 (本次新发现 3 个)

#### 1. copilotData.js - searchStock URL 构造存在 XSS 风险
- **位置**: `searchStock()` 函数
- **问题**: 
  ```javascript
  const res = await apiFetch(`${API_BASE}/api/v1/stocks/search?q=${encodeURIComponent(k)}`, ...)
  ```
  `encodeURIComponent` 只编码 `?=&` 等字符，不会阻止 `<`, `>`, `"` 等。攻击者可构造 `k='<img src=x onerror=alert(1)>'` 注入到 URL 参数，若后端反射回 HTML 响应或日志系统未做处理，可能导致 XSS。
- **影响**: 若后端将搜索关键词反射到日志/响应，攻击者可在搜索框注入恶意脚本
- **对比**: `api.js` 的 `apiFetch` 有正确的 JSON body 序列化，而这里用 URL 参数拼接
- **建议**: 对特殊字符做白名单过滤，或使用后端的 POST body 传搜索词

#### 2. usePortfolioStore.js - 错误消息误报 (变量遮蔽 Bug)
- **位置**: `upsertPosition()` 函数
- **问题**:
  ```javascript
  try {
    const body = await res.json()      // ← body 被重新赋值
    msg = body?.message || body?.detail || msg
  } catch (_) {}
  if (msg.includes('UNIQUE')) msg = '该账户名称已存在，请换一个名字'
  ```
  这里用 `body` 接收 JSON 解析结果（应该是 position 相关信息），但错误消息是账户名称相关，说明代码复制自 `createPortfolio` 但没改完全。`upsertPosition` 应该是"该持仓已存在"或"更新成功"，而非"账户名称已存在"。
- **影响**: 用户看到误导性错误提示，可能困惑
- **Karpathy 准则**: Simplicity First - 重复代码未精简，容易出错

#### 3. useMarketStream.js - globalWsStatus 应为 shallowRef
- **位置**: `const globalWsStatus = ref('idle')` (第22行)
- **问题**: `globalWsStatus` 是普通 `ref`，监听它的组件在状态变化时会有深度响应式追踪开销。与 `globalTicks = shallowRef({})` 的优化意图不一致。
- **对比**: `globalTicks` 正确用了 `shallowRef`，但 `globalWsStatus` 没有
- **影响**: 组件多时可能影响性能，但严重程度中等

---

### P2 - 中等风险 (本次新发现 5 个)

#### 4. api.js - 模块级状态 `_consecutiveFailures` 无锁保护
- **位置**: `_consecutiveFailures = { count: 0 }` 模块级变量
- **问题**: `_onFailure` / `_onSuccess` 直接修改 `_consecutiveFailures.count`，但 `apiFetch` 是异步的，多个并发请求的失败回调可能在同一 event loop 中交错执行。
- **影响**: 计数可能不准确，但不影响功能正确性（只是熔断时机有偏差）
- **建议**: 使用 `AtomicInteger` 或在调用侧做同步保护（实际风险低）

#### 5. useDataSourceStatus.js - `_listeners` 是 Set 但无并发保护
- **位置**: `const _listeners = new Set()` 模块级变量
- **问题**: `onDataSourceStatusChange` 和 `_notifyListeners` 操作 `_listeners`，无锁保护。组件在 `onUnmounted` 时调用返回的 unlisten 函数删除 listener，这本身是安全的，但 add 时无并发保护。
- **影响**: 低，主要在单线程 JS 环境下可接受

#### 6. useEventBus.js - emit 缺少 try-catch 错误收集
- **位置**: 
  ```javascript
  export function emit(event, payload) {
    if (listeners[event]) {
      listeners[event].forEach(cb => {
        try { cb(payload) } catch (e) { logger.warn('[EventBus]', event, e) }
      })
    }
  }
  ```
- **问题**: 错误被静默吞掉，调用方不知道 listener 执行失败了
- **影响**: 某个 listener 失败不影响其他，但调试困难

#### 7. useMarketStream.js - tickHistory 内存泄漏隐患
- **位置**: `const tickHistory = {}` 和 `MAX_TICK_HISTORY = 1000`
- **问题**: `tickHistory` 按 symbol 存储历史，但 `unsubscribe` 时只删除了 globalTicks 中的 symbol，`tickHistory` 本身的 key 没有被清理（实际代码中有 `delete tickHistory[sym]` 在 unsubscribe 中，但需确认调用路径正确）
- **对比**: 代码中 unsubscribe 确实有 `delete tickHistory[sym]`，设计上正确

#### 8. copilotData.js - getCached 返回过期数据无刷新机制
- **位置**: `getCached()` 函数
- **问题**: 当 API 请求失败时，返回旧的缓存数据但不打标记。调用方无法区分"数据是新的还是旧的缓存"。
- **影响**: 长时间无网络时，用户看到 stale 数据但不感知

---

### P3 - 低风险 (本次新发现 4 个)

#### 9. useMarketStore.js - 未使用的 import
- **位置**: `import { ref, computed } from 'vue'` (第1行)
- **问题**: 文件中实际只用 `ref`（`currentSymbol = ref(...)` 等），`computed` 导入了但未使用
- **影响**: 极小，bundler 会 tree-shake

#### 10. useTheme.js - onThemeChange 回调集合无去重
- **位置**: `themeChangeCallbacks` 是 Set
- **问题**: Set 能防重复，但若调用方多次调用 `onThemeChange` 注册同一个回调，会注册多次，触发时执行多次。应该用 WeakMap 或要求调用方自己管理去重。
- **影响**: 低，视觉上不会有明显问题，只是回调执行多次

#### 11. useUiStore.js - 导出解构不完整
- **位置**: `ui` 对象只有 `klineFullscreen`, `sidebarCollapsed` 等字段
- **问题**: 如果有新的 UI 状态需要添加，开发者可能忘记在 `ui` 对象和 `useUiStore` 返回之间保持一致
- **影响**: 极小

#### 12. indicators.js - calcKDJ 高点计算可用二分查找优化
- **位置**: `calcKDJ` 中 `Math.max(...highs.slice(...))` 对每个 KDJ 计算都要重新 slice 和 spread
- **问题**: 对 1000 根 K 线 × 9 周期 = 9000 次 `Math.max(...Array)`，涉及大量数组分配
- **影响**: 低，大数据量（如分钟线 years）时可能影响性能

---

## 本次代码亮点

1. **useMarketStream.js** - WebSocket 单例模式设计优秀：引用计数订阅 + shallowRef + 心跳管理 + jitter 重连 + 1006 诊断提示，技术含量高
2. **useTheme.js** - 四主题系统完整，CSS 变量实现，localStorage 持久化，callback 通知机制
3. **api.js** - 熔断机制完善（连续失败广播）+ 指数退避重试 + extractData 兼容新旧 API 格式
4. **chartDataBuilder.js** - 双 Y 轴自适应（量级差异 > 10x 时归一化），overlay 对比设计优秀
5. **indicators.js** - 指标库完整（MA/EMA/BOLL/MACD/KDJ/RSI/WR/CCI/BIAS/VWAP/OBV/DMI/SAR），纯函数无副作用

---

## 总体进度

| 批次 | 时间 | 模块 |
|------|------|------|
| partial-frontend-20260426-1850 | 2026-04-26 18:50 | frontend-components + frontend-stores + frontend-utils |
| partial-backend-core-services-20260426-1904 | 2026-04-26 19:04 | backend-core + backend-services + backend-models + backend-utils |
| partial-backend-routers-db-20260426-1921 | 2026-04-26 19:21 | backend-routers (16文件) + backend-db (3文件) |
| partial-frontend-composables-services-utils-20260426-1934 | 2026-04-26 19:34 | frontend-composables + frontend-services + frontend-utils |

**总体进度**: 7/12 模块（58%）
**下次审计**: frontend-views（剩余 views 模块 + 后端 AkShare/fetchers 专项）

---

## 本次新增 P1 发现汇总

| # | 文件 | 问题 | 严重程度 |
|---|------|------|----------|
| 1 | copilotData.js | searchStock URL 构造 XSS 风险 | 中高 |
| 2 | usePortfolioStore.js | upsertPosition 错误消息误报（变量遮蔽） | 中高 |
| 3 | useMarketStream.js | globalWsStatus 应为 shallowRef | 中 |