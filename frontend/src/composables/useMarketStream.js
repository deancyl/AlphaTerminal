/**
 * useMarketStream — WebSocket 实时行情 hook（单例模式）
 * 
 * 所有调用方共享同一个 WebSocket 连接。
 * 只有当最后一个组件 unmount 时才真正关闭连接。
 * 跨组件的订阅自动合并去重。
 * 
 * 改进:
 * - 添加数据淘汰机制，防止内存无限增长
 * - 优化重连策略，指数退避 + 最大重试次数
 * - 添加连接状态监控
 * 
 * 用法:
 *   const { tick, connect, disconnect, connected } = useMarketStream()
 *   connect('600519')
 *   watch(tick, t => { if (t) applyTick(t) })
 */
import { ref, computed, onUnmounted } from 'vue'
import { logger } from '../utils/logger.js'

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

// 全局 tick 字典（按 symbol 索引，避免不必要更新）
const globalTicks = ref({})
const globalConnected = ref(false)
const globalError = ref(null)
const globalReconnecting = ref(false)

// 当前已订阅的符号集合（去重）
const subscribedSyms = new Set()

// 数据历史限制（防止内存泄漏）
const MAX_TICK_HISTORY = 1000
const tickHistory = []

// ── 内部函数 ──────────────────────────────────────────────────

function _newConnection() {
  if (_ws) return

  globalReconnecting.value = true
  const url = `${WS_BASE}/ws/market`
  
  try {
    _ws = new WebSocket(url)
  } catch (e) {
    logger.error('[MarketStream] WebSocket 创建失败:', e)
    _scheduleRetry()
    return
  }

  _ws.onopen = () => {
    globalConnected.value = true
    globalError.value = null
    globalReconnecting.value = false
    _retryDelay = 2000
    _retryCount = 0
    _doSubscribe()
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
      
      // 按 symbol 更新（而不是单一 globalTick）
      globalTicks.value[sym] = data
    } catch (e) {
      logger.warn('[MarketStream] parse error:', e)
    }
  }

  _ws.onerror = (e) => {
    logger.error('[MarketStream] WS 错误:', e)
    globalError.value = 'WS 连接错误'
    globalConnected.value = false
  }

  _ws.onclose = (e) => {
    logger.log('[MarketStream] 连接关闭:', e.code, e.reason)
    globalConnected.value = false
    globalReconnecting.value = false
    _ws = null
    
    // 1000 = 正常关闭，不重连
    // 1006 = abnormal closure，需要重连
    if (e.code !== 1000 && subscribedSyms.size > 0) {
      if (_retryCount < _MAX_RETRIES) {
        _scheduleRetry()
      } else {
        globalError.value = '连接失败次数过多，请刷新页面重试'
        logger.error('[MarketStream] 达到最大重试次数，停止重连')
      }
    }
  }
}

function _doSubscribe() {
  if (!_ws || _ws.readyState !== WebSocket.OPEN) return
  const syms = [...subscribedSyms]
  if (!syms.length) return
  try {
    _ws.send(JSON.stringify({ action: 'subscribe', symbols: syms }))
  } catch (e) {
    logger.warn('[MarketStream] subscribe failed:', e)
  }
}

function _scheduleRetry() {
  if (_retryCount >= _MAX_RETRIES) return
  
  clearTimeout(_retryTimer)
  globalReconnecting.value = true
  _retryCount++
  
  logger.log(`[MarketStream] ${(_retryDelay/1000).toFixed(1)}秒后第${_retryCount}次重连...`)
  
  _retryTimer = setTimeout(() => {
    if (subscribedSyms.size > 0) _newConnection()
  }, _retryDelay)
  
  _retryDelay = Math.min(_retryDelay * 1.5, _MAX_DELAY)
}

// ── 导出给组件的 hook ──────────────────────────────────────────

export function useMarketStream(initialSymbol = '') {
  const localSymbol = ref(initialSymbol)

  // 组件 mount 时注册
  _connectedCount.value++
  if (initialSymbol) {
    subscribedSyms.add(initialSymbol)
    if (!_ws && globalConnected.value === false) {
      _newConnection()
    } else if (_ws && _ws.readyState === WebSocket.OPEN) {
      _doSubscribe()
    }
  }

  function connect(symOrList) {
    // 取消待执行的断开，避免闪断
    cancelPendingDisconnect()
    
    const syms = Array.isArray(symOrList) ? symOrList : [symOrList]
    syms.forEach(s => {
      if (s) {
        subscribedSyms.add(s)
        localSymbol.value = s
      }
    })
    if (!_ws) {
      _newConnection()
    } else if (_ws.readyState === WebSocket.OPEN) {
      _doSubscribe()
    }
  }

  let _disconnectTimer = null

function disconnect() {
    _connectedCount.value = Math.max(0, _connectedCount.value - 1)
    if (_connectedCount.value <= 0) {
      // 延迟 200ms 关闭，避免路由切换时的闪断
      if (_disconnectTimer) clearTimeout(_disconnectTimer)
      _disconnectTimer = setTimeout(() => {
        if (_connectedCount.value <= 0 && _ws) {
          clearTimeout(_retryTimer)
          _ws.onclose = null
          _ws.onerror = null
          _ws.close(1000, 'all_disconnected')
          _ws = null
          globalConnected.value = false
          globalReconnecting.value = false
          subscribedSyms.clear()
          tickHistory.length = 0
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

  // 30 秒心跳
  let _hbActive = false
  function _startHeartbeat() {
    if (_hbActive) return
    _hbActive = true
    setInterval(() => {
      if (_ws && _ws.readyState === WebSocket.OPEN) {
        try { _ws.send(JSON.stringify({ action: 'ping' })) } catch (_) {}
      }
    }, 30_000)
  }
  _startHeartbeat()

  onUnmounted(disconnect)

  return {
    // 直接返回当前 symbol 的 tick（推荐用法）
    tick: computed(() => localSymbol.value ? globalTicks.value[localSymbol.value] : null),
    // 保留全局 tick 字典（高级用法）
    ticks: globalTicks,
    connected: globalConnected,
    reconnecting: globalReconnecting,
    error: globalError,
    symbol: localSymbol,
    connect,
    disconnect,
    // 获取连接统计
    getStats: () => ({
      subscribedCount: subscribedSyms.size,
      historyCount: tickHistory[localSymbol.value]?.length || 0,
      retryCount: _retryCount,
      connectionCount: _connectedCount.value
    })
  }
}
