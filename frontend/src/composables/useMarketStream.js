/**
 * useMarketStream — WebSocket 实时行情 hook
 *
 * 用法:
 *   const { tick, connect, disconnect, connected } = useMarketStream()
 *   connect('600519')     // 订阅单只股票
 *   connect(['600519','000858']) // 批量订阅
 *   watch(tick, (t) => { if (t) applyTick(t) })
 *
 * 协议: 连接 /ws/market → 发送 {"action":"subscribe","symbols":[...]}
 *       服务端推送: {"symbol":"600519","price":1680.5,...}
 */
import { ref, onUnmounted } from 'vue'

const WS_BASE = import.meta.env.VITE_WS_BASE || `ws://${location.host}`

export function useMarketStream(initialSymbol = '') {
  const symbol    = ref(initialSymbol)
  const tick      = ref(null)       // 最新 tick
  const connected = ref(false)
  const error     = ref(null)

  let ws         = null
  let retryTimer  = null
  let retryDelay  = 2000
  const MAX_DELAY = 30000

  function connect(symOrList, onReconnect = null) {
    if (symOrList) {
      symbol.value = Array.isArray(symOrList) ? symOrList[0] : symOrList
    }
    _createConnection(symOrList, onReconnect)
  }

  function _createConnection(symOrList, onReconnect) {
    if (ws) { ws.onclose = null; ws.onerror = null; ws.close(); ws = null }
    clearTimeout(retryTimer)

    const url = `${WS_BASE}/ws/market`
    try {
      ws = new WebSocket(url)
    } catch (e) {
      error.value = `创建失败: ${e.message}`
      _scheduleRetry()
      return
    }

    ws.onopen = async () => {
      connected.value = true
      error.value     = null
      retryDelay      = 2000
      // 发送订阅指令
      const syms = Array.isArray(symOrList) ? symOrList : [symOrList]
      try {
        ws.send(JSON.stringify({ action: 'subscribe', symbols: syms }))
      } catch (e) {
        console.warn('[MarketStream] subscribe send failed:', e)
      }
      if (onReconnect) onReconnect()
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'pong' || data.type === 'subscribed') return
        tick.value = data
      } catch (e) {
        console.warn('[MarketStream] parse error:', e)
      }
    }

    ws.onerror = () => {
      error.value    = '连接错误'
      connected.value = false
    }

    ws.onclose = (e) => {
      connected.value = false
      if (e.code !== 1000) _scheduleRetry()
    }
  }

  function _scheduleRetry() {
    clearTimeout(retryTimer)
    retryTimer = setTimeout(() => {
      if (symbol.value) _createConnection(symbol.value)
    }, retryDelay)
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
    tick.value      = null
  }

  // 30 秒心跳
  let hbTimer = setInterval(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ action: 'ping' }))
    }
  }, 30_000)

  onUnmounted(() => {
    disconnect()
    clearInterval(hbTimer)
  })

  return { symbol, tick, connected, error, connect, disconnect }
}
