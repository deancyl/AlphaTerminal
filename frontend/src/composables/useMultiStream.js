/**
 * useMultiStream — 多股票 WebSocket 订阅 hook
 * 一个 WS 连接，接收所有订阅股票的实时 tick
 *
 * 用法:
 *   const { tickMap, connect, disconnect } = useMultiStream()
 *   connect(['600519', '000858'])
 *   watch(tickMap, (m) => { if (m.get('600519')) updatePnL(...) })
 */
import { ref, onUnmounted } from 'vue'

const WS_BASE = import.meta.env.VITE_WS_BASE || `ws://${location.host}`

export function useMultiStream() {
  const tickMap = ref(new Map())   // symbol -> tick
  const connected = ref(false)
  const error     = ref(null)
  const symbols   = ref([])

  let ws          = null
  let retryTimer  = null
  let retryDelay  = 2000
  const MAX_DELAY = 30000

  function connect(symList) {
    symbols.value = symList || []
    _createConnection()
  }

  function _createConnection() {
    if (ws) { ws.onclose = null; ws.close(); ws = null }
    clearTimeout(retryTimer)

    // 订阅所有股票的路径: /ws/market/all?symbols=600519,000858
    const syms = symbols.value.join(',')
    const url  = `${WS_BASE}/ws/market/all${syms ? '?symbols=' + syms : ''}`
    try {
      ws = new WebSocket(url)
    } catch (e) {
      error.value = `创建失败: ${e.message}`
      _scheduleRetry()
      return
    }

    ws.onopen = () => {
      connected.value = true
      error.value    = null
      retryDelay     = 2000
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data === 'pong' || data.type === 'heartbeat') return
        // data: { symbol: "600519", price: 1680, chg_pct: 1.23, ... }
        if (data.symbol) {
          tickMap.value = new Map(tickMap.value).set(data.symbol, data)
        }
      } catch (e) {
        console.warn('[MultiStream] parse error:', e)
      }
    }

    ws.onerror = () => {
      error.value = '连接错误'
      connected.value = false
    }

    ws.onclose = (e) => {
      connected.value = false
      if (e.code !== 1000) _scheduleRetry()
    }
  }

  function _scheduleRetry() {
    clearTimeout(retryTimer)
    retryTimer = setTimeout(_createConnection, retryDelay)
    retryDelay = Math.min(retryDelay * 1.5, MAX_DELAY)
  }

  function disconnect() {
    clearTimeout(retryTimer)
    if (ws) { ws.onclose = null; ws.onerror = null; ws.close(1000); ws = null }
    connected.value = false
    tickMap.value  = new Map()
  }

  onUnmounted(disconnect)

  // 30 秒心跳保活
  let hbTimer = setInterval(() => {
    if (ws && ws.readyState === WebSocket.OPEN) ws.send('ping')
  }, 30_000)
  onUnmounted(() => clearInterval(hbTimer))

  return { tickMap, connected, error, connect, disconnect }
}
