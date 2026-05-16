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
import { acquireLock, releaseLock } from '../utils/connectionLock.js'
import { TIMEOUTS } from '../utils/constants.js'
import { CircularBuffer } from '../utils/circularBuffer.js'
import { useNetworkStatus, isNetworkOnline } from './useNetworkStatus.js'

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
let _retryDelay = TIMEOUTS.WS_RECONNECT_BASE
const _MAX_DELAY = TIMEOUTS.WS_RECONNECT_MAX
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
const globalLastConnectedAt = ref(null)
const globalConnectionAttempts = ref(0)
const globalLatency = ref(null) // WebSocket latency in ms

// HTTP polling fallback state
const globalPollingStatus = ref(false)
const POLLING_INTERVAL = 5000  // 5 seconds
let _pollingTimer = null

// ── P0-2: Subscription Queue (防止 WS 未就绪时订阅丢失) ────────────────────────────────
// 当 WS 未连接时，订阅请求存入队列，连接就绪后批量发送
const _pendingSubscriptions = new Set()
const _MAX_PENDING_QUEUE = 500  // 防止内存泄漏

// ── P0-1: Network Status Awareness (网络状态感知) ────────────────────────────────
// 追踪网络状态，网络恢复后自动重连
const globalNetworkOnline = ref(navigator.onLine)
let _networkOnlineHandler = null
let _networkOfflineHandler = null
let _networkListenerRegistered = false

function _registerNetworkListeners() {
  if (_networkListenerRegistered) return
  _networkOnlineHandler = () => {
    globalNetworkOnline.value = true
    logger.log('[MarketStream] 网络已恢复，尝试重连...')
    // 网络恢复后立即重连（如果有待订阅的符号）
    if (subscribedSymRefCount.size > 0 && !_ws && _connectionState === ConnectionState.IDLE) {
      _newConnection()
    }
  }
  _networkOfflineHandler = () => {
    globalNetworkOnline.value = false
    logger.warn('[MarketStream] 网络已断开，暂停重连')
    // 网络断开时停止重连计时器
    if (_retryTimer) {
      clearTimeout(_retryTimer)
      _retryTimer = null
    }
  }
  window.addEventListener('online', _networkOnlineHandler)
  window.addEventListener('offline', _networkOfflineHandler)
  _networkListenerRegistered = true
}

function _unregisterNetworkListeners() {
  if (!_networkListenerRegistered) return
  window.removeEventListener('online', _networkOnlineHandler)
  window.removeEventListener('offline', _networkOfflineHandler)
  _networkOnlineHandler = null
  _networkOfflineHandler = null
  _networkListenerRegistered = false
}

// ── Connection State Machine (Race Condition Fix) ────────────────────────────────
// States: IDLE, CONNECTING, CONNECTED, DISCONNECTING, RECONNECTING, POLLING (HTTP fallback)
const ConnectionState = {
  IDLE: 'idle',
  CONNECTING: 'connecting',
  CONNECTED: 'connected',
  DISCONNECTING: 'disconnecting',
  RECONNECTING: 'reconnecting',
  POLLING: 'polling'
}

// Valid state transitions map
// POLLING is a fallback state when WS fails repeatedly (retry >= 2)
const VALID_TRANSITIONS = {
  [ConnectionState.IDLE]: [ConnectionState.CONNECTING, ConnectionState.RECONNECTING],
  [ConnectionState.CONNECTING]: [ConnectionState.CONNECTED, ConnectionState.IDLE, ConnectionState.DISCONNECTING, ConnectionState.POLLING],
  [ConnectionState.CONNECTED]: [ConnectionState.DISCONNECTING, ConnectionState.RECONNECTING],
  [ConnectionState.DISCONNECTING]: [ConnectionState.IDLE, ConnectionState.CONNECTED, ConnectionState.POLLING],
  [ConnectionState.RECONNECTING]: [ConnectionState.CONNECTED, ConnectionState.IDLE, ConnectionState.DISCONNECTING, ConnectionState.POLLING],
  [ConnectionState.POLLING]: [ConnectionState.CONNECTING, ConnectionState.CONNECTED, ConnectionState.IDLE]
}

// Single source of truth for connection state
let _connectionState = ConnectionState.IDLE

// Note: Operation locking is handled by connectionLock.js (acquireLock/releaseLock)
// The previous _operationLock/_withLock implementation was never used and has been removed
// to avoid confusion and potential deadlocks from dual lock systems.

/**
 * Atomic state transition with validation
 * @param {string} from - Expected current state
 * @param {string} to - Target state
 * @returns {boolean} - Whether transition succeeded
 */
function _transitionState(from, to) {
  if (_connectionState !== from) {
    logger.warn(`[MarketStream] Invalid state transition: expected ${from}, current is ${_connectionState}, target ${to}`)
    return false
  }
  
  if (!VALID_TRANSITIONS[from]?.includes(to)) {
    logger.warn(`[MarketStream] Forbidden state transition: ${from} → ${to}`)
    return false
  }
  
  const oldState = _connectionState
  _connectionState = to
  globalWsStatus.value = to
  logger.log(`[MarketStream] State transition: ${oldState} → ${to}`)
  return true
}

/**
 * Try to transition state (no validation of current state)
 * @param {string} to - Target state
 * @returns {boolean} - Whether transition succeeded
 */
function _tryTransitionTo(to) {
  const from = _connectionState
  if (!VALID_TRANSITIONS[from]?.includes(to)) {
    logger.warn(`[MarketStream] Forbidden state transition: ${from} → ${to}`)
    return false
  }
  
  _connectionState = to
  globalWsStatus.value = to
  logger.log(`[MarketStream] State transition: ${from} → ${to}`)
  return true
}

// ── Race Condition Prevention (Wave 2 Fix) ────────────────────────────────
// Data version counter: Each update increments this, allowing us to detect stale updates
let _dataVersion = 0
// WS priority: WS updates always have higher priority than HTTP polling
const WS_PRIORITY = 100
const HTTP_PRIORITY = 1
// Status transition debounce: Prevent rapid status changes causing flicker
let _statusDebounceTimer = null
const STATUS_DEBOUNCE_MS = 500

// 当前已订阅的符号集合（引用计数 Map：key=symbol, value=refcount）
const subscribedSymRefCount = new Map()

// 数据历史限制（使用 CircularBuffer 避免 shift() 的 O(n) 性能开销）
const MAX_TICK_HISTORY = 1000
const tickHistory = {}

const TICK_THROTTLE_MS = 50
let _lastTickTime = 0
let _pendingTick = null

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

function _setStatusDebounced(newStatus) {
  if (_statusDebounceTimer) {
    clearTimeout(_statusDebounceTimer)
  }
  _statusDebounceTimer = setTimeout(() => {
    globalWsStatus.value = newStatus
    _statusDebounceTimer = null
  }, STATUS_DEBOUNCE_MS)
}

function _newConnection() {
  // State machine check: only allow connection from IDLE or RECONNECTING
  if (_connectionState !== ConnectionState.IDLE && _connectionState !== ConnectionState.RECONNECTING) {
    logger.warn(`[MarketStream] _newConnection rejected: current state is ${_connectionState}`)
    return
  }
  
  if (_ws) {
    logger.warn('[MarketStream] _newConnection rejected: connection already exists')
    return
  }
  
  if (!acquireLock()) {
    logger.warn('[MarketStream] _newConnection rejected: connection lock not acquired')
    return
  }

  // Transition to CONNECTING
  if (!_tryTransitionTo(ConnectionState.CONNECTING)) {
    releaseLock()
    return
  }
  
  globalError.value = null
  globalConnectionAttempts.value++
  const url = `${WS_BASE}/ws/market`

  try {
    _ws = new WebSocket(url)
  } catch (e) {
    releaseLock()
    logger.error('[MarketStream] WebSocket 创建失败:', e)
    _tryTransitionTo(ConnectionState.IDLE)
    globalError.value = 'WebSocket 创建失败'
    _scheduleRetry()
    return
  }

  _ws.onopen = () => {
    releaseLock()
    _transitionState(ConnectionState.CONNECTING, ConnectionState.CONNECTED)
    globalError.value = null
    globalLastConnectedAt.value = Date.now()
    globalConnectionAttempts.value = 0
    _retryDelay = TIMEOUTS.WS_RECONNECT_BASE
    _retryCount = 0
    _lastMessageTime = Date.now()
    _startHealthCheck()
    _registerNetworkListeners()
    if (globalPollingStatus.value) {
      _stopPolling()
    }
    const activeSyms = [...subscribedSymRefCount.keys()]
    if (activeSyms.length) _doSubscribe(activeSyms)
    _flushPendingSubscriptions()
  }

  _ws.onmessage = (event) => {
    _lastMessageTime = Date.now()
    _missedPongs = 0
    try {
      const data = JSON.parse(event.data)

      if (data.type === 'ping') {
        _ws.send(JSON.stringify({ type: 'pong' }))
        return
      }

      if (data.type === 'pong') {
        if (_pingSentTime > 0) {
          globalLatency.value = Date.now() - _pingSentTime
          _pingSentTime = 0
        }
        return
      }

      if (data.type === 'subscribed' || data.type === 'unsubscribed') return

      const sym = data.symbol
      if (!sym) return

      _dataVersion++
      const currentVersion = _dataVersion

      if (!tickHistory[sym]) tickHistory[sym] = new CircularBuffer(MAX_TICK_HISTORY)
      tickHistory[sym].push({ ...data, _version: currentVersion, _priority: WS_PRIORITY })

      // Use Object.assign for better memory performance (avoid spread operator creating new objects)
      globalTicks.value[sym] = Object.assign({}, data, { _version: currentVersion, _priority: WS_PRIORITY })
      _tickDirty = true

      const now = Date.now()
      if (now - _lastTickTime >= TICK_THROTTLE_MS) {
        _lastTickTime = now
        queueMicrotask(_notifyTick)
      } else if (!_pendingTick) {
        _pendingTick = setTimeout(() => {
          _pendingTick = null
          _lastTickTime = Date.now()
          queueMicrotask(_notifyTick)
        }, TICK_THROTTLE_MS - (now - _lastTickTime))
      }

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
    releaseLock()
    logger.error('[MarketStream] WS 错误:', e)
    globalError.value = 'WS 连接错误'
    // onerror 之后必触发 onclose，状态由 onclose 设置
  }

  _ws.onclose = (e) => {
    releaseLock()
    logger.log('[MarketStream] 连接关闭:', e.code, e.reason)

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
    
    // Transition to IDLE
    _transitionState(_connectionState, ConnectionState.IDLE)
    _ws = null
    _stopHealthCheck()

    if (e.code !== 1000 && subscribedSymRefCount.size > 0) {
      if (_retryCount < _MAX_RETRIES) {
        _scheduleRetry()
      } else {
        globalError.value = '连接失败次数过多，请刷新页面重试'
        logger.error('[MarketStream] 达到最大重试次数，停止重连')
      }
      if (_retryCount >= 2 && !globalPollingStatus.value) {
        logger.warn('[MarketStream] Starting HTTP polling fallback (retry >= 2)')
        _startPolling([...subscribedSymRefCount.keys()])
      }
    }
  }
}

function _doSubscribe(syms) {
  if (!syms || !syms.length) return
  const cleanSyms = syms.filter(s => s && String(s) !== 'undefined' && String(s).trim() !== '')
  if (!cleanSyms.length) return

  // P0-2: 如果 WS 未就绪，存入队列等待连接后发送
  if (!_ws || _ws.readyState !== WebSocket.OPEN) {
    for (const sym of cleanSyms) {
      if (_pendingSubscriptions.size < _MAX_PENDING_QUEUE) {
        _pendingSubscriptions.add(sym)
      }
    }
    logger.log(`[MarketStream] WS 未就绪，${cleanSyms.length} 个订阅已入队（队列: ${_pendingSubscriptions.size}）`)
    return
  }

  try {
    const payload = { action: 'subscribe', symbols: cleanSyms }
    if (import.meta.env.DEV) console.debug('[MarketStream] 发送订阅:', JSON.stringify(payload))
    _ws.send(JSON.stringify(payload))
  } catch (e) {
    logger.warn('[MarketStream] subscribe failed:', e)
  }
}

function _flushPendingSubscriptions() {
  if (_pendingSubscriptions.size === 0) return
  const syms = [..._pendingSubscriptions]
  _pendingSubscriptions.clear()
  if (syms.length > 0 && _ws && _ws.readyState === WebSocket.OPEN) {
    logger.log(`[MarketStream] 刷新待处理订阅: ${syms.length} 个`)
    _doSubscribe(syms)
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
  
  // Transition to RECONNECTING
  if (!_tryTransitionTo(ConnectionState.RECONNECTING)) {
    logger.warn('[MarketStream] _scheduleRetry rejected: cannot transition to RECONNECTING')
    return
  }
  
  clearTimeout(_retryTimer)
  _retryCount++

  // jitter: 实际延迟 = base * (0.5 + random)，即 ±50%
  const jitter = _retryDelay * (0.5 + Math.random())
  logger.log(`[MarketStream] ${(jitter / 1000).toFixed(1)}s后第${_retryCount}次重连（jitter ±50%）...`)

  _retryTimer = setTimeout(() => {
    if (!globalNetworkOnline.value) {
      logger.warn('[MarketStream] 网络离线，跳过重连')
      _tryTransitionTo(ConnectionState.IDLE)
      return
    }
    if (subscribedSymRefCount.size > 0 && !_ws && _connectionState === ConnectionState.RECONNECTING) {
      _newConnection()
    }
  }, jitter)

  _retryDelay = Math.min(_retryDelay * 1.5, _MAX_DELAY)
}

// ── 心跳管理（setinterval 句柄必须保存，disconnect 时清理）────────
let _heartbeatTimer = null
let _lastMessageTime = 0
let _healthCheckTimer = null
let _pingSentTime = 0
let _missedPongs = 0

const HEARTBEAT_INTERVAL = TIMEOUTS.WS_HEARTBEAT_INTERVAL
const PONG_TIMEOUT = TIMEOUTS.WS_PONG_TIMEOUT
const MAX_MISSED_PONGS = TIMEOUTS.WS_MAX_MISSED_PONGS

function _startHeartbeat() {
  if (_heartbeatTimer) return
  _heartbeatTimer = setInterval(() => {
    if (_ws && _ws.readyState === WebSocket.OPEN) {
      _missedPongs++
      if (_missedPongs >= MAX_MISSED_PONGS) {
        logger.warn(`[MarketStream] 连续${_missedPongs}次未收到pong，强制重连`)
        _ws.onclose = null
        _ws.onerror = null
        _ws.close(1006, 'pong_timeout')
        _ws = null
        _stopHeartbeat()
        _stopHealthCheck()
        if (subscribedSymRefCount.size > 0 && _retryCount < _MAX_RETRIES) {
          _scheduleRetry()
        }
        return
      }
      try {
        _pingSentTime = Date.now()
        _ws.send(JSON.stringify({ type: 'ping' }))
      } catch (_) {
      }
    }
  }, HEARTBEAT_INTERVAL)
}

function _stopHeartbeat() {
  if (_heartbeatTimer) {
    clearInterval(_heartbeatTimer)
    _heartbeatTimer = null
  }
}

function _restartHeartbeat() {
  _stopHeartbeat()
  _startHeartbeat()
}

function _startHealthCheck() {
  if (_healthCheckTimer) return
  _healthCheckTimer = setInterval(() => {
    if (_lastMessageTime && Date.now() - _lastMessageTime > PONG_TIMEOUT + HEARTBEAT_INTERVAL) {
      logger.warn('[MarketStream] 连接超时，强制重连')
      if (_ws) {
        _ws.onclose = null
        _ws.onerror = null
        _ws.close(1006, 'health_check_timeout')
        _ws = null
      }
      _stopHealthCheck()
      if (subscribedSymRefCount.size > 0 && _retryCount < _MAX_RETRIES) {
        _scheduleRetry()
      }
    }
  }, TIMEOUTS.WS_HEALTH_CHECK_INTERVAL)
}

function _stopHealthCheck() {
  if (_healthCheckTimer) {
    clearInterval(_healthCheckTimer)
    _healthCheckTimer = null
  }
}

function _startPolling(symbols) {
  if (globalPollingStatus.value) return
  
  if (!_tryTransitionTo(ConnectionState.POLLING)) {
    logger.warn('[MarketStream] Cannot transition to POLLING state')
    return
  }
  
  globalPollingStatus.value = true

  _pollingTimer = setInterval(async () => {
    try {
      const res = await fetch('/api/v1/futures/commodities')
      const data = await res.json()
      if (data.data?.commodities) {
        _dataVersion++
        const currentVersion = _dataVersion
        for (const item of data.data.commodities) {
          const existing = globalTicks.value[item.symbol]
          if (existing && existing._priority >= WS_PRIORITY) {
            continue
          }
          globalTicks.value[item.symbol] = Object.assign({}, {
              symbol: item.symbol,
              price: item.price,
              change_pct: item.change_pct,
              _version: currentVersion,
              _priority: HTTP_PRIORITY,
            })
        }
        triggerRef(globalTicks)
      }
    } catch (e) {
      logger.warn('[Polling] failed:', e)
    }
  }, POLLING_INTERVAL)
}

function _stopPolling() {
  if (_pollingTimer) {
    clearInterval(_pollingTimer)
    _pollingTimer = null
  }
  globalPollingStatus.value = false
}

// ── 导出给组件的 hook ──────────────────────────────────────────

export function useMarketStream(initialSymbol = '') {
  const localSymbol = ref(initialSymbol)

  _connectedCount.value++
  if (initialSymbol) {
    subscribedSymRefCount.set(initialSymbol, (subscribedSymRefCount.get(initialSymbol) || 0) + 1)
    if (!_ws && _connectionState === ConnectionState.IDLE) {
      _newConnection()
    } else if (_ws && _ws.readyState === WebSocket.OPEN) {
      _doSubscribe([initialSymbol])
    }
  }

  function connect(symOrList) {
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

    // State machine check: only connect if IDLE or DISCONNECTED
    if (!_ws) {
      if (_connectionState === ConnectionState.IDLE) {
        _newConnection()
      } else {
        logger.warn(`[MarketStream] connect() rejected: current state is ${_connectionState}`)
      }
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
        // 清理 globalTicks 中的该 symbol（直接删除属性，避免创建新对象）
        delete globalTicks.value[sym]
        _tickDirty = true
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
      if (_pendingTick) clearTimeout(_pendingTick)
      _pendingTick = null
      _disconnectTimer = setTimeout(() => {
        // State machine check: only disconnect if CONNECTED or RECONNECTING
        if (_connectedCount.value <= 0 && _ws) {
          if (_connectionState !== ConnectionState.CONNECTED && 
              _connectionState !== ConnectionState.RECONNECTING) {
            logger.warn(`[MarketStream] disconnect() rejected: current state is ${_connectionState}`)
            return
          }
          
          // Transition to DISCONNECTING
          if (!_tryTransitionTo(ConnectionState.DISCONNECTING)) {
            logger.warn('[MarketStream] disconnect() failed to transition to DISCONNECTING')
            return
          }
          
          _stopHeartbeat()
          clearTimeout(_retryTimer)
          if (_pendingTick) clearTimeout(_pendingTick)
          _pendingTick = null
          _ws.onclose = null
          _ws.onerror = null
          _ws.close(1000, 'all_disconnected')
          _ws = null
          _unregisterNetworkListeners()
          
          // Transition to IDLE
          _transitionState(ConnectionState.DISCONNECTING, ConnectionState.IDLE)
          
          subscribedSymRefCount.clear()
          Object.keys(tickHistory).forEach(k => delete tickHistory[k])
          globalTicks.value = {}
          _retryCount = 0
          _retryDelay = TIMEOUTS.WS_RECONNECT_BASE
          _stopPolling()
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

  function manualReconnect() {
    // Force disconnect regardless of state
    if (_ws) {
      _stopHeartbeat()
      clearTimeout(_retryTimer)
      _ws.onclose = null
      _ws.onerror = null
      _ws.close(1000, 'manual_reconnect')
      _ws = null
    }
    
    // Reset state to IDLE
    _connectionState = ConnectionState.IDLE
    globalWsStatus.value = ConnectionState.IDLE
    _retryCount = 0
    _retryDelay = TIMEOUTS.WS_RECONNECT_BASE
    
    // Start new connection
    _newConnection()
  }

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
    tick: computed(() => localSymbol.value ? globalTicks.value[localSymbol.value] : null),
    ticks: globalTicks,
    wsStatus: globalWsStatus,
    connected: computed(() => _connectionState === ConnectionState.CONNECTED),
    reconnecting: computed(() => _connectionState === ConnectionState.CONNECTING || _connectionState === ConnectionState.RECONNECTING),
    error: globalError,
    symbol: localSymbol,
    connect,
    disconnect,
    unsubscribe,
    manualReconnect,
    lastConnectedAt: globalLastConnectedAt,
    connectionAttempts: globalConnectionAttempts,
    latency: globalLatency,
    isPolling: globalPollingStatus,
    connectionState: computed(() => _connectionState),
    getStats: () => ({
      subscribedCount: subscribedSymRefCount.size,
      historyCount: tickHistory[localSymbol.value]?.length || 0,
      retryCount: _retryCount,
      connectionCount: _connectedCount.value,
      wsStatus: globalWsStatus.value,
      connectionState: _connectionState,
      lastConnectedAt: globalLastConnectedAt.value,
      connectionAttempts: globalConnectionAttempts.value,
      latency: globalLatency.value,
      isPolling: globalPollingStatus.value,
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
