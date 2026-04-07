/**
 * useMarketStream — WebSocket 实时行情 hook
 * 替代 setInterval 轮询，实现毫秒级价格更新
 *
 * 用法:
 *   const { tick, connect, disconnect } = useMarketStream('600519')
 *   watch(tick, (t) => { /* 更新最后一根K线 *\/ })
 */
import { ref, onUnmounted } from 'vue'

const WS_BASE = import.meta.env.VITE_WS_BASE || `ws://${location.host}`

export function useMarketStream(initialSymbol = '') {
  const symbol    = ref(initialSymbol)
  const tick      = ref(null)      // 最新 tick 数据
  const connected = ref(false)
  const error     = ref(null)

  let ws        = null
  let retryTimer = null
  let retryDelay = 2000  // 重连延迟（毫秒）
  const MAX_DELAY = 30000

  function connect(sym) {
    if (sym) symbol.value = sym
    if (!symbol.value) return
    _createConnection()
  }

  function _createConnection() {
    if (ws) {
      ws.onclose = null
      ws.onerror = null
      ws.close()
      ws = null
    }
    clearTimeout(retryTimer)

    const url = `${WS_BASE}/ws/market/${symbol.value}`
    try {
      ws = new WebSocket(url)
    } catch (e) {
      error.value = `WebSocket 创建失败: ${e.message}`
      _scheduleRetry()
      return
    }

    ws.onopen = () => {
      connected.value = true
      error.value    = null
      retryDelay     = 2000  // 重置延迟
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data === 'pong') return   // 心跳响应
        tick.value = data
      } catch (e) {
        console.warn('[MarketStream] parse error:', e)
      }
    }

    ws.onerror = () => {
      error.value = 'WebSocket 连接错误'
      connected.value = false
    }

    ws.onclose = (event) => {
      connected.value = false
      ws = null
      // 非正常关闭（code != 1000）则重连
      if (event.code !== 1000) {
        _scheduleRetry()
      }
    }
  }

  function _scheduleRetry() {
    clearTimeout(retryTimer)
    retryTimer = setTimeout(() => {
      if (symbol.value) _createConnection()
    }, retryDelay)
    // 指数退避，避免频繁重连
    retryDelay = Math.min(retryDelay * 1.5, MAX_DELAY)
  }

  function disconnect() {
    clearTimeout(retryTimer)
    if (ws) {
      ws.onclose = null
      ws.onerror = null
      ws.close(1000, 'user_disconnect')
      ws = null
    }
    connected.value = false
    tick.value = null
  }

  // 心跳保活（每 50 秒发一次 ping）
  let heartbeatTimer = null
  function _startHeartbeat() {
    heartbeatTimer = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send('ping')
      }
    }, 50_000)
  }

  function _stopHeartbeat() {
    clearInterval(heartbeatTimer)
    heartbeatTimer = null
  }

  onUnmounted(() => {
    disconnect()
    _stopHeartbeat()
  })

  return {
    symbol,
    tick,          // ref: 最新 tick 数据
    connected,    // ref: 是否已连接
    error,         // ref: 错误信息
    connect,       // (symbol?) => void
    disconnect,    // () => void
  }
}
