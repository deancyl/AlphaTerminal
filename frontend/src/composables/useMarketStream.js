/**
 * useMarketStream — WebSocket 实时行情 hook（单例模式）
 *
 * 所有调用方共享同一个 WebSocket 连接。
 * 只有当最后一个组件 unmount 时才真正关闭连接。
 * 跨组件的订阅自动合并去重。
 *
 * 性能优化（v0.5.52-task4）：
 * - globalTicks 改用 shallowRef：避免 Vue 对 tick 对象做深度 proxy
 * - tick 更新时手动 triggerRef：精确控制渲染时机，杜绝无意义重渲染
 * - 心跳 setInterval 保存句柄，disconnect 时 clearInterval 防止内存泄漏
 * - 重连添加 jitter（±25%），防止惊群效应
 * - 暴露 wsStatus：组件可据此决定是否启用 HTTP 轮询降级
 *
 * 用法:
 *   const { tick, connect, disconnect, wsStatus } = useMarketStream()
 *   watch(tick, t => { if (t) applyTick(t) })
 *   // HTTP 降级示例：
 *   watch(wsStatus, (s) => { s === 'disconnected' ? startPolling() : stopPolling() })
 */
import { ref, computed, watch, onUnmounted, shallowRef, triggerRef } from 'vue'
import { logger } from '../utils/logger.js'
import { checkPriceAlerts, sendNotification, recordAlertTrigger } from './useNotifications.js'

// WebSocket 基础 URL 配置
// 开发环境：如果 VITE_WS_BASE 为空，使用相对路径（Vite proxy 处理）
// 生产环境 HTTPS：如果页面是 HTTPS 且 VITE_WS_BASE 为空，需要明确使用 wss://
let WS_BASE = import.meta.env.VITE_WS_BASE || ''

// 自动检测协议：HTTPS 页面需要 WSS，但 Vite dev server 只支持 WS
// 在生产 HTTPS 环境中，如果 VITE_WS_BASE 为空，使用绝对路径
if (!WS_BASE && typeof window !== 'undefined') {
  const isHttps = window.location.protocol === 'https:'
  if (isHttps) {
    // 生产 HTTPS：使用 wss:// 绝对路径
    // 注意：这需要 Nginx 或其他代理将 wss:// 转发到后端的 ws://
    WS_BASE = `wss://${window.location.host}`
  }
  // HTTP 页面保持空字符串（相对路径，Vite proxy 处理）
}

// ── 模块级单例状态（所有组件共享）───────────────────────────────
let _ws = null
let _retryTimer = null
let _retryDelay = 2000
const _MAX_DELAY = 30000
const _MAX_RETRIES = 10  // 最大重试次数
let _retryCount = 0      // 当前重试计数
const _connectedCount = ref(0)

// 全局 tick 字典（按 symbol 索引）
// ⚡ 改用 shallowRef：只追踪 tick 对象引用的替换，不追踪内部字段的深度响应式
const globalTicks = shallowRef({})
// 手动触发更新的标记（shallowRef 需要显式 triggerRef）
let _tickDirty = false

// WS 连接状态：'idle' | 'connecting' | 'connected' | 'disconnected' | 'failed'
const globalWsStatus = ref('idle')
const globalError = ref(null)

// 当前已订阅的符号集合（引用计数 Map：key=symbol, value=refcount）
const subscribedSymRefCount = new Map()

// 数据历史限制（防止内存泄漏），按 symbol 分开统计
const MAX_TICK_HISTORY = 1000
const tickHistory = {}

// ── 内部函数 ──────────────────────────────────────────────────

/**
 * 触发 tick 的 shallowRef 更新（仅在 symbol 实际变化时调用）
 * 通过标记位批量合并：同一 event loop 内的多次 tick 更新只触发一次 triggerRef
 */
function _notifyTick() {
  if (_tickDirty) {
    _tickDirty = false
    triggerRef(globalTicks)
  }
}

function _newConnection() {
  if (_ws) return

  globalWsStatus.value = 'connecting'
  globalError.value = null
  const url = `${WS_BASE}/ws/market`

  try {
    _ws = new WebSocket(url)
  } catch (e) {
    logger.error('[MarketStream] WebSocket 创建失败:', e)
    globalWsStatus.value = 'failed'
    globalError.value = 'WebSocket 创建失败'
    _scheduleRetry()
    return
  }

  _ws.onopen = () => {
    globalWsStatus.value = 'connected'
    globalError.value = null
    _retryDelay = 2000
    _retryCount = 0
    // 重连时重新订阅所有仍有引用的 symbol
    const activeSyms = [...subscribedSymRefCount.keys()]
    if (activeSyms.length) _doSubscribe(activeSyms)
  }

  _ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      if (data.type === 'pong' || data.type === 'subscribed') return

      const sym = data.symbol
      if (!sym) return

      // 数据淘汰机制（按 symbol 分开）
      if (!tickHistory[sym]) tickHistory[sym] = []
      tickHistory[sym].push(data)
      if (tickHistory[sym].length > MAX_TICK_HISTORY) {
        tickHistory[sym].shift()
      }

      // ⚡ shallowRef 更新策略：直接替换 symbol 的 tick 对象引用，
      // 这样 globalTicks.value 整体引用不变，只有被替换的 symbol 被更新
      // triggerRef 标记由 _notifyTick 在 microtask 中批量触发
      globalTicks.value = {
        ...globalTicks.value,
        [sym]: data,
      }
      _tickDirty = true
      // 在 microtask 中统一触发（合并同一 event loop 内的多次更新）
      queueMicrotask(_notifyTick)
      
      // 检查价格预警
      if (data.price) {
        const triggered = checkPriceAlerts(sym, data.price)
        for (const { rule, price } of triggered) {
          const title = `🔔 ${rule.symbol} 价格预警`
          const body = `${formatAlertCondition(rule)}\n当前价格: ¥${price}`
          sendNotification(title, { body })
          recordAlertTrigger(rule, price)
        }
      }
    } catch (e) {
      logger.warn('[MarketStream] parse error:', e)
    }
  }

  _ws.onerror = (e) => {
    logger.error('[MarketStream] WS 错误:', e)
    globalError.value = 'WS 连接错误'
    globalWsStatus.value = 'connected' // onerror 之后必触发 onclose，不单独设置
  }

  _ws.onclose = (e) => {
    logger.log('[MarketStream] 连接关闭:', e.code, e.reason)
    const wasConnected = globalWsStatus.value === 'connected'

    // ── 1006 专项诊断：HTTPS 反向代理 WebSocket 握手失败 ─────────────────────────
    if (e.code === 1006 && location.protocol === 'https:') {
      console.error(
        '%c[MarketStream] ⚠️ 1006 异常关闭（疑似反向代理拦截 WS 握手）',
        'color:#f59e0b;font-weight:bold',
        '\n排查建议：',
        '\n  1. Lucky666 (Web服务) → 子规则目标地址填 http://内网IP:端口，勿覆盖 Connection/Upgrade 头',
        '\n  2. Cloudflare → Network → WebSockets 必须打开',
        '\n  3. 确认代理层配置了: proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade";',
        '\n  4. 或在前端 .env 中设 VITE_WS_BASE=http://内网IP:端口（绕过代理直连，仅限内网）'
      )
    }
    globalWsStatus.value = 'disconnected'
    _ws = null

    // 1000 = 正常关闭（disconnect 调用），不重连
    // 1006 = abnormal closure，需要重连
    if (e.code !== 1000 && subscribedSymRefCount.size > 0) {
      if (_retryCount < _MAX_RETRIES) {
        _scheduleRetry()
      } else {
        globalWsStatus.value = 'failed'
        globalError.value = '连接失败次数过多，请刷新页面重试'
        logger.error('[MarketStream] 达到最大重试次数，停止重连')
      }
    }
  }
}

function _doSubscribe(syms) {
  if (!_ws || _ws.readyState !== WebSocket.OPEN) return
  if (!syms || !syms.length) return
  // ── 防空：过滤掉 undefined / 空字符串 / 'undefined' 字符串 ──
  const cleanSyms = syms.filter(s => s && String(s) !== 'undefined' && String(s).trim() !== '')
  if (!cleanSyms.length) return
  try {
    const payload = { action: 'subscribe', symbols: cleanSyms }
    if (import.meta.env.DEV) console.debug('[MarketStream] 发送订阅:', JSON.stringify(payload))
    _ws.send(JSON.stringify(payload))
  } catch (e) {
    logger.warn('[MarketStream] subscribe failed:', e)
  }
}

function _doUnsubscribe(syms) {
  if (!_ws || _ws.readyState !== WebSocket.OPEN) return
  if (!syms || !syms.length) return
  try {
    _ws.send(JSON.stringify({ action: 'unsubscribe', symbols: syms }))
  } catch (e) {
    logger.warn('[MarketStream] unsubscribe failed:', e)
  }
}

/**
 * 指数退避重连（带 jitter ±25%，防止惊群效应）
 */
function _scheduleRetry() {
  if (_retryCount >= _MAX_RETRIES) return

  clearTimeout(_retryTimer)
  globalWsStatus.value = 'connecting'
  _retryCount++

  // jitter: 实际延迟 = base * (0.75 + random * 0.5)，即 ±25%
  const jitter = _retryDelay * (0.75 + Math.random() * 0.5)
  logger.log(`[MarketStream] ${(jitter / 1000).toFixed(1)}s后第${_retryCount}次重连（jitter ±25%）...`)

  _retryTimer = setTimeout(() => {
    if (subscribedSymRefCount.size > 0 && !_ws) _newConnection()
  }, jitter)

  _retryDelay = Math.min(_retryDelay * 1.5, _MAX_DELAY)
}

// ── 心跳管理（setInterval 句柄必须保存，disconnect 时清理）────────
let _heartbeatTimer = null

function _startHeartbeat() {
  if (_heartbeatTimer) return
  _heartbeatTimer = setInterval(() => {
    if (_ws && _ws.readyState === WebSocket.OPEN) {
      try {
        _ws.send(JSON.stringify({ action: 'ping' }))
      } catch (_) {
        // WS 已在 closing 状态，静默忽略
      }
    }
  }, 30_000)
}

function _stopHeartbeat() {
  if (_heartbeatTimer) {
    clearInterval(_heartbeatTimer)
    _heartbeatTimer = null
  }
}

// ── 导出给组件的 hook ──────────────────────────────────────────

export function useMarketStream(initialSymbol = '') {
  const localSymbol = ref(initialSymbol)

  // 组件 mount 时注册（使用引用计数）
  _connectedCount.value++
  if (initialSymbol) {
    subscribedSymRefCount.set(initialSymbol, (subscribedSymRefCount.get(initialSymbol) || 0) + 1)
    if (!_ws && globalWsStatus.value === 'idle') {
      _newConnection()
    } else if (_ws && _ws.readyState === WebSocket.OPEN) {
      _doSubscribe([initialSymbol])
    }
  }

  function connect(symOrList) {
    // ── 防空：空值/undefined 直接忽略 ──
    if (!symOrList || String(symOrList) === 'undefined') return

    cancelPendingDisconnect()

    const syms = Array.isArray(symOrList) ? symOrList : [symOrList]
    const newSyms = []

    syms.forEach(s => {
      if (!s) return
      const currentCount = subscribedSymRefCount.get(s) || 0
      subscribedSymRefCount.set(s, currentCount + 1)
      localSymbol.value = s
      if (currentCount === 0) {
        newSyms.push(s)
      }
    })

    if (!_ws) {
      _newConnection()
    } else if (_ws.readyState === WebSocket.OPEN) {
      if (newSyms.length) _doSubscribe(newSyms)
    }
  }

  /**
   * 精准取消订阅（引用计数版本）
   */
  function unsubscribe(symOrList) {
    const syms = Array.isArray(symOrList) ? symOrList : [symOrList]
    const symsToDrop = []

    syms.forEach(sym => {
      if (!sym) return
      const count = subscribedSymRefCount.get(sym) || 0
      if (count > 1) {
        subscribedSymRefCount.set(sym, count - 1)
      } else if (count === 1) {
        subscribedSymRefCount.delete(sym)
        symsToDrop.push(sym)
        // 清理 globalTicks 中的该 symbol（替换引用，触发 shallowRef 更新）
        const next = { ...globalTicks.value }
        delete next[sym]
        globalTicks.value = next
        delete tickHistory[sym]
      }
    })

    if (symsToDrop.length && _ws && _ws.readyState === WebSocket.OPEN) {
      _doUnsubscribe(symsToDrop)
    }
  }

  let _disconnectTimer = null

  function disconnect() {
    _connectedCount.value = Math.max(0, _connectedCount.value - 1)
    if (_connectedCount.value <= 0) {
      if (_disconnectTimer) clearTimeout(_disconnectTimer)
      _disconnectTimer = setTimeout(() => {
        if (_connectedCount.value <= 0 && _ws) {
          _stopHeartbeat()   // ⚡ 断开时清理心跳
          clearTimeout(_retryTimer)
          _ws.onclose = null
          _ws.onerror = null
          _ws.close(1000, 'all_disconnected')
          _ws = null
          globalWsStatus.value = 'idle'
          subscribedSymRefCount.clear()
          Object.keys(tickHistory).forEach(k => delete tickHistory[k])
          globalTicks.value = {}
          _retryCount = 0
          _retryDelay = 2000
        }
      }, 200)
    }
  }

  function cancelPendingDisconnect() {
    if (_disconnectTimer) {
      clearTimeout(_disconnectTimer)
      _disconnectTimer = null
    }
  }

  // 启动心跳
  _startHeartbeat()

  // 自动 unsubscribe 旧 symbol（组件切换股票时）
  let _prevSymbol = initialSymbol
  watch(localSymbol, (newSym, oldSym) => {
    if (oldSym && oldSym !== newSym && oldSym === _prevSymbol) {
      unsubscribe(oldSym)
    }
    _prevSymbol = newSym
  })

  // 组件卸载时
  onUnmounted(() => {
    if (localSymbol.value) {
      unsubscribe(localSymbol.value)
    }
    disconnect()
  })

  return {
    // 当前 symbol 的 tick（shallowRef，仅引用变化时触发）
    tick: computed(() => localSymbol.value ? globalTicks.value[localSymbol.value] : null),
    // 完整 tick 字典（高级用法）
    ticks: globalTicks,
    // WS 连接状态：'idle' | 'connecting' | 'connected' | 'disconnected' | 'failed'
    // ⚡ 组件应 watch 此状态实现 HTTP 轮询降级
    wsStatus: globalWsStatus,
    // 已废弃，保留兼容：优先用 wsStatus
    connected: computed(() => globalWsStatus.value === 'connected'),
    reconnecting: computed(() => globalWsStatus.value === 'connecting'),
    error: globalError,
    symbol: localSymbol,
    connect,
    disconnect,
    unsubscribe,
    getStats: () => ({
      subscribedCount: subscribedSymRefCount.size,
      historyCount: tickHistory[localSymbol.value]?.length || 0,
      retryCount: _retryCount,
      connectionCount: _connectedCount.value,
      wsStatus: globalWsStatus.value,
    }),
  }
}

// 格式化预警条件文本
function formatAlertCondition(rule) {
  const conditionMap = {
    'above': '高于',
    'below': '低于',
    'equals': '等于'
  }
  return `价格${conditionMap[rule.condition] || rule.condition} ¥${rule.targetPrice}`
}
