/**
 * useTimeMachine — 时光机复盘状态管理
 * API 基础路径: /api/v1/timemachine
 * 功能：历史K线回放 + 模拟交易
 */
import { ref, computed, shallowRef, triggerRef, watch, onUnmounted } from 'vue'
import { apiFetch } from '../utils/api.js'
import { logger } from '../utils/logger.js'
import { TIMEOUTS } from '../utils/constants.js'
import { useToast } from './useToast.js'
import { CircularBuffer } from '../utils/circularBuffer.js'
import { useAbortableRequest } from './useAbortableRequest.js'

const BASE = '/api/v1/timemachine'

// Memory limits for TimeMachine playback
const MAX_KLINE_BARS = 500  // Limit K-line history during playback
const MAX_TRADES = 100      // Limit trade history

// ── 工具函数 ─────────────────────────────────────────────────────
function formatMoney(value) {
  if (value === null || value === undefined) return '¥0.00'
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'CNY',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(value)
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
}

// ── Composable ─────────────────────────────────────────────────────
export function useTimeMachine() {
  // Toast for user feedback
  const toast = useToast()
  
  // P0: AbortController for race condition prevention
  let createSessionRequestId = 0
  let stepForwardRequestId = 0
  let seekToRequestId = 0
  const { createSignal: createSessionSignal } = useAbortableRequest()
  const { createSignal: createStepSignal } = useAbortableRequest()
  const { createSignal: createSeekSignal } = useAbortableRequest()
  
  // Session state
  const session = ref(null)
  const loading = ref(false)
  const error = ref(null)
  
  // Data source status (v0.6.220)
  const dataSource = ref({
    source_type: 'real',
    timestamp: null,
    is_mock: false
  })
  
  // K-line data (use CircularBuffer for memory safety)
  // P0: Use shallowRef + triggerRef for Vue reactivity (CircularBuffer is not reactive)
  const klineBufferWrapper = shallowRef({
    buffer: new CircularBuffer(MAX_KLINE_BARS),
    version: 0
  })
  const currentBar = ref(0)
  
  // Computed for backward compatibility
  const klineData = computed(() => klineBufferWrapper.value.buffer.toArray())
  const totalBars = computed(() => klineBufferWrapper.value.buffer.length)
  
  // Playback state
  const playbackStatus = ref('idle') // 'idle' | 'playing' | 'paused'
  const speed = ref(1)
  let playbackTimer = null
  
  // Portfolio state
  const portfolio = ref({
    cash: 1000000,
    position_value: 0,
    total_value: 1000000,
    pnl_pct: 0,
    shares: 0,
    avg_cost: 0
  })
  
  // Trades history (use CircularBuffer for memory safety)
  const tradesBuffer = new CircularBuffer(MAX_TRADES)
  const trades = computed(() => tradesBuffer.toArray())
  
  // Computed
  const currentDate = computed(() => {
    return klineData.value[currentBar.value]?.date || ''
  })
  
  const currentPrice = computed(() => {
    return klineData.value[currentBar.value]?.close || 0
  })
  
  const visibleKlineData = computed(() => {
    // Only show data up to current bar (historical perspective)
    return klineData.value.slice(0, currentBar.value + 1)
  })
  
  const progressPct = computed(() => {
    if (totalBars.value === 0) return 0
    return (currentBar.value / totalBars.value) * 100
  })
  
  // ── API Actions ──────────────────────────────────────────────────
  
  /**
   * 创建复盘会话
   * @param {string} symbol - 股票代码 (如 sh600519)
   * @param {string} startDate - 开始日期 (YYYY-MM-DD)
   * @param {string} endDate - 结束日期 (YYYY-MM-DD)
   * @param {number} initialCapital - 初始资金
   */
  async function createSession(symbol, startDate, endDate, initialCapital = 1000000) {
    createSessionRequestId++
    const currentRequestId = createSessionRequestId
    
    loading.value = true
    error.value = null
    
    const signal = createSessionSignal()
    try {
      const response = await apiFetch(`${BASE}/session/create`, {
        method: 'POST',
        timeoutMs: TIMEOUTS.API_MACRO, // 30s for data fetching
        body: JSON.stringify({
          symbol,
          start_date: startDate,
          end_date: endDate,
          initial_capital: initialCapital,
          speed: speed.value
        }),
        signal
      })
      
      // Check if request is stale
      if (currentRequestId !== createSessionRequestId) return
      
      session.value = response?.session_id

      klineBufferWrapper.value.buffer.clear()
      const bars = response?.bars || []
      for (const bar of bars) {
        klineBufferWrapper.value.buffer.push(bar)
      }
      klineBufferWrapper.value.version++
      triggerRef(klineBufferWrapper)

      currentBar.value = 0
      playbackStatus.value = 'paused'

      // Update data source status (v0.6.220)
      dataSource.value = {
        source_type: response?.source_type || 'real',
        timestamp: response?.timestamp || new Date().toISOString(),
        is_mock: response?.is_mock || false
      }
      
      portfolio.value = {
        cash: initialCapital,
        position_value: 0,
        total_value: initialCapital,
        pnl_pct: 0,
        shares: 0,
        avg_cost: 0
      }
      
      tradesBuffer.clear()
      
      logger.info('[TimeMachine] Session created:', session.value)
      return response
    } catch (e) {
      if (e.name === 'AbortError') return
      
      const errorMsg = e.message || ''
      if (errorMsg.includes('404') || errorMsg.includes('not found')) {
        error.value = '会话已过期，请重新创建'
        toast.error(error.value)
      } else if (errorMsg.includes('network') || errorMsg.includes('fetch')) {
        error.value = '数据加载失败，请检查网络'
        toast.error(error.value)
      } else {
        error.value = errorMsg || '创建会话失败'
        toast.error(error.value)
      }
      logger.error('[TimeMachine] Create session failed:', e)
      // Don't re-throw - toast.error() already shows user feedback
    } finally {
      loading.value = false
    }
  }
  
  /**
   * 前进 N 根 K 线
   * @param {number} bars - 前进的 K 线数量
   */
  async function stepForward(bars = 1) {
    if (!session.value) return
    
    stepForwardRequestId++
    const currentRequestId = stepForwardRequestId
    
    const signal = createStepSignal()
    try {
      const response = await apiFetch(`${BASE}/session/${session.value}/step`, {
        method: 'POST',
        timeoutMs: TIMEOUTS.API_DEFAULT,
        body: JSON.stringify({ bars }),
        signal
      })
      
      // Check if request is stale
      if (currentRequestId !== stepForwardRequestId) return
      
      currentBar.value = response?.current_bar ?? 0
      portfolio.value = response?.portfolio || portfolio.value
      
      if (response?.new_trades?.length) {
        for (const trade of response.new_trades) {
          tradesBuffer.push(trade)
        }
      }
      
      return response
    } catch (e) {
      if (e.name === 'AbortError') return
      toast.error('前进失败，请重试')
      logger.error('[TimeMachine] Step failed:', e)
    }
  }
  
  /**
   * 播放/暂停切换
   */
  async function togglePlay() {
    if (!session.value) return
    
    const action = playbackStatus.value === 'playing' ? 'pause' : 'play'
    
    try {
      const response = await apiFetch(`${BASE}/session/${session.value}/play`, {
        method: 'POST',
        timeoutMs: TIMEOUTS.API_DEFAULT,
        body: JSON.stringify({ action })
      })
      
      playbackStatus.value = response?.status || 'paused'
      
      // Start local playback timer if playing
      if (playbackStatus.value === 'playing') {
        startPlaybackTimer()
      } else {
        stopPlaybackTimer()
      }
      
      return response
    } catch (e) {
      toast.error('播放控制失败，请重试')
      logger.error('[TimeMachine] Toggle play failed:', e)
    }
  }
  
  /**
   * 设置播放速度
   * @param {number} newSpeed - 速度倍数 (0.5, 1, 2, 5)
   */
  async function setSpeed(newSpeed) {
    if (!session.value) return
    
    speed.value = newSpeed
    
    try {
      const response = await apiFetch(`${BASE}/session/${session.value}/speed`, {
        method: 'POST',
        timeoutMs: TIMEOUTS.API_DEFAULT,
        body: JSON.stringify({ speed: newSpeed })
      })
      
      // Restart timer with new speed
      if (playbackStatus.value === 'playing') {
        stopPlaybackTimer()
        startPlaybackTimer()
      }
      
      return response
    } catch (e) {
      logger.error('[TimeMachine] Set speed failed:', e)
      toast.error('设置速度失败')
    }
  }
  
  /**
   * 执行模拟交易
   * @param {string} action - 'buy' | 'sell'
   * @param {number} quantity - 数量
   */
  async function executeTrade(action, quantity) {
    if (!session.value || quantity <= 0) return
    
    try {
      const response = await apiFetch(`${BASE}/session/${session.value}/trade`, {
        method: 'POST',
        timeoutMs: TIMEOUTS.API_DEFAULT,
        body: JSON.stringify({ action, quantity })
      })
      
      if (response?.success) {
        tradesBuffer.push(response.trade)
        portfolio.value = response?.portfolio || portfolio.value
        
        // Calculate portfolio impact for enhanced feedback
        const trade = response.trade
        const price = trade?.price || 0
        const totalCost = quantity * price
        const proceeds = quantity * price
        
        const newCash = portfolio.value.cash - (action === 'buy' ? totalCost : -proceeds)
        const newPosition = portfolio.value.shares + (action === 'buy' ? quantity : -quantity)
        
        toast.success(
          `交易成功`,
          `${action === 'buy' ? '买入' : '卖出'} ${quantity}股 @ ¥${price.toFixed(2)}\n` +
          `当前持仓: ${newPosition}股 | 可用资金: ¥${newCash.toFixed(2)}`
        )
        logger.info('[TimeMachine] Trade executed:', action, quantity)
      }
      
      return response
    } catch (e) {
      toast.error('交易执行失败，请检查资金或持仓')
      logger.error('[TimeMachine] Trade failed:', e)
    }
  }
  
  /**
   * 跳转到指定进度
   * @param {number} targetBar - 目标 K 线索引
   */
  async function seekTo(targetBar) {
    if (!session.value || targetBar < 0 || targetBar >= totalBars.value) return
    
    seekToRequestId++
    const currentRequestId = seekToRequestId
    
    const signal = createSeekSignal()
    try {
      const response = await apiFetch(`${BASE}/session/${session.value}/seek`, {
        method: 'POST',
        timeoutMs: TIMEOUTS.API_DEFAULT,
        body: JSON.stringify({ target_bar: targetBar }),
        signal
      })
      
      // Check if request is stale
      if (currentRequestId !== seekToRequestId) return
      
      currentBar.value = response?.current_bar ?? 0
      portfolio.value = response?.portfolio || portfolio.value
      
      return response
    } catch (e) {
      if (e.name === 'AbortError') return
      toast.error('跳转失败，请重试')
      logger.error('[TimeMachine] Seek failed:', e)
    }
  }
  
  /**
   * 获取会话状态
   */
  async function getSessionStatus() {
    if (!session.value) return null
    
    try {
      const response = await apiFetch(`${BASE}/session/${session.value}/status`, {
        method: 'GET',
        timeoutMs: TIMEOUTS.API_DEFAULT
      })
      
      return response
    } catch (e) {
      logger.error('[TimeMachine] Get status failed:', e)
      return null
    }
  }
  
  /**
   * 结束会话
   */
  async function endSession() {
    if (!session.value) return
    
    stopPlaybackTimer()
    
    try {
      await apiFetch(`${BASE}/session/${session.value}`, {
        method: 'DELETE',
        timeoutMs: TIMEOUTS.API_DEFAULT
      })
      
      logger.info('[TimeMachine] Session ended:', session.value)
    } catch (e) {
      logger.error('[TimeMachine] End session failed:', e)
    }
    
    // Reset state
    session.value = null
    klineBufferWrapper.value.buffer.clear()
    klineBufferWrapper.value.version++
    triggerRef(klineBufferWrapper)
    currentBar.value = 0
    playbackStatus.value = 'idle'
    tradesBuffer.clear()
    dataSource.value = {
      source_type: 'real',
      timestamp: null,
      is_mock: false
    }
    portfolio.value = {
      cash: 1000000,
      position_value: 0,
      total_value: 1000000,
      pnl_pct: 0,
      shares: 0,
      avg_cost: 0
    }
  }
  
  // ── Local Playback Timer ────────────────────────────────────────
  
  function startPlaybackTimer() {
    if (playbackTimer) return
    
    const interval = Math.max(100, 1000 / speed.value) // Base 1s per bar
    
    playbackTimer = setInterval(async () => {
      if (currentBar.value < totalBars.value - 1) {
        await stepForward(1)
      } else {
        // End of data, auto pause
        playbackStatus.value = 'paused'
        stopPlaybackTimer()
      }
    }, interval)
  }
  
  function stopPlaybackTimer() {
    if (playbackTimer) {
      clearInterval(playbackTimer)
      playbackTimer = null
    }
  }
  
  // ── Cleanup ─────────────────────────────────────────────────────
  
  function clear() {
    klineBufferWrapper.value.buffer.clear()
    klineBufferWrapper.value.version++
    triggerRef(klineBufferWrapper)
    tradesBuffer.clear()
    currentBar.value = 0
    session.value = null
    playbackStatus.value = 'idle'
    stopPlaybackTimer()
    
    // P0: Reset request IDs on clear
    createSessionRequestId = 0
    stepForwardRequestId = 0
    seekToRequestId = 0
  }
  
  onUnmounted(() => {
    stopPlaybackTimer()
    if (session.value) {
      endSession()
    }
    
    // P0: Reset request IDs on unmount
    createSessionRequestId = 0
    stepForwardRequestId = 0
    seekToRequestId = 0
  })
  
  // ── Return ──────────────────────────────────────────────────────
  
  return {
    // State
    session,
    loading,
    error,
    dataSource,
    klineData,
    currentBar,
    currentDate,
    currentPrice,
    visibleKlineData,
    totalBars,
    playbackStatus,
    speed,
    portfolio,
    trades,
    progressPct,
    
    // Actions
    createSession,
    stepForward,
    togglePlay,
    setSpeed,
    executeTrade,
    seekTo,
    getSessionStatus,
    endSession,
    clear,
    
    // Utils
    formatMoney,
    formatDate
  }
}