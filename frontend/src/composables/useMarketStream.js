/**
 * useMarketStream — WebSocket 实时行情 hook（单例模式）
 *
 * 所有调用方共享同一个 WebSocket 连接。
 * 只有当最后一个组件 unmount 时才真正关闭连接。
 * 跨组件的订阅自动合并去重。
 *
 * 用法:
 *   const { tick, connect, disconnect, connected } = useMarketStream()
 *   connect('600519')
 *   watch(tick, t => { if (t) applyTick(t) })
 */
import { ref, onUnmounted } from 'vue'

const WS_BASE = import.meta.env.VITE_WS_BASE || ''   // 相对路径，生产由 Nginx 代理

// ── 模块级单例状态（所有组件共享）───────────────────────────────
let _ws        = null
let _retryTimer = null
let _retryDelay = 2000
const _MAX_DELAY = 30000
const _connectedCount = ref(0)

// 全局 tick 和状态，所有组件实例读写同一份
const globalTick     = ref(null)
const globalConnected = ref(false)
const globalError   = ref(null)

// 当前已订阅的符号集合（去重）
const subscribedSyms = new Set()

// 当前待订阅的符号（下次 connect 时生效）
let pendingSyms = []

// ── 内部函数 ──────────────────────────────────────────────────

function _newConnection() {
  if (_ws) return  // 已在连接中或已连接

  const url = `${WS_BASE}/ws/market`
  _ws = new WebSocket(url)

  _ws.onopen = () => {
    globalConnected.value = true
    globalError.value = null
    _retryDelay = 2000
    _doSubscribe()
  }

  _ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      if (data.type === 'pong' || data.type === 'subscribed') return
      globalTick.value = data
    } catch (e) {
      console.warn('[MarketStream] parse error:', e)
    }
  }

  _ws.onerror = () => {
    globalError.value = 'WS 连接错误'
    globalConnected.value = false
  }

  _ws.onclose = (e) => {
    globalConnected.value = false
    _ws = null
    // 1006 = abnormal closure（通常是代理未配置），停止刷屏重试
    if (e.code !== 1000 && e.code !== 1006 && subscribedSyms.size > 0) {
      _scheduleRetry()
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
    console.warn('[MarketStream] subscribe failed:', e)
  }
}

function _scheduleRetry() {
  clearTimeout(_retryTimer)
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
      pendingSyms.push(initialSymbol)
      _newConnection()
    } else if (_ws && _ws.readyState === WebSocket.OPEN) {
      _doSubscribe()
    }
  }

  function connect(symOrList) {
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

  function disconnect() {
    _connectedCount.value = Math.max(0, _connectedCount.value - 1)
    // 只有最后一个组件离开时才关闭连接
    if (_connectedCount.value <= 0) {
      clearTimeout(_retryTimer)
      if (_ws) {
        _ws.onclose = null
        _ws.onerror = null
        _ws.close(1000, 'all_disconnected')
        _ws = null
      }
      globalConnected.value = false
      subscribedSyms.clear()
    }
  }

  // 30 秒心跳（只发一次，不重复建 timer）
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
    // 代理到全局状态（所有组件实例共享）
    tick:      globalTick,
    connected: globalConnected,
    error:     globalError,
    // 组件私有
    symbol:    localSymbol,
    connect,
    disconnect,
  }
}
