/**
 * useTimeMachine — 时光机复盘状态管理
 * API 基础路径: /api/v1/timemachine
 * 功能：历史K线回放 + 模拟交易
 */
import { ref, computed, shallowRef, watch, onUnmounted } from 'vue'
import { apiFetch } from '../utils/api.js'
import { logger } from '../utils/logger.js'
import { TIMEOUTS } from '../utils/constants.js'
import { useToast } from './useToast.js'

const BASE = '/api/v1/timemachine'

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
  
  // Session state
  const session = ref(null)
  const loading = ref(false)
  const error = ref(null)
  
  // K-line data (use shallowRef for large datasets)
  const klineData = shallowRef([])
  const currentBar = ref(0)
  const totalBars = computed(() => klineData.value.length)
  
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
  const trades = ref([])
  
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
    loading.value = true
    error.value = null
    
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
        })
      })
      
      session.value = response.data.session_id
      klineData.value = response.data.kline_data || response.data.bars || []
      currentBar.value = response.data.current_bar || 0
      playbackStatus.value = 'paused'
      
      portfolio.value = response.data.portfolio || {
        cash: initialCapital,
        position_value: 0,
        total_value: initialCapital,
        pnl_pct: 0,
        shares: 0,
        avg_cost: 0
      }
      trades.value = []
      
      logger.info('[TimeMachine] Session created:', session.value)
      return response.data
    } catch (e) {
      const errorMsg = e.message || ''
      if (errorMsg.includes('404') || errorMsg.includes('not found')) {
        error.value = '会话已过期，请重新创建'
      } else if (errorMsg.includes('network') || errorMsg.includes('fetch')) {
        error.value = '数据加载失败，请检查网络'
      } else {
        error.value = errorMsg || '创建会话失败'
      }
      logger.error('[TimeMachine] Create session failed:', e)
      throw e
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
    
    try {
      const response = await apiFetch(`${BASE}/session/${session.value}/step`, {
        method: 'POST',
        timeoutMs: TIMEOUTS.API_DEFAULT,
        body: JSON.stringify({ bars })
      })
      
      currentBar.value = response.data.current_bar
      portfolio.value = response.data.portfolio
      
      // Add any new trades
      if (response.data.new_trades?.length) {
        trades.value.push(...response.data.new_trades)
      }
      
      return response.data
    } catch (e) {
      logger.error('[TimeMachine] Step failed:', e)
      throw e
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
      
      playbackStatus.value = response.data.status
      
      // Start local playback timer if playing
      if (playbackStatus.value === 'playing') {
        startPlaybackTimer()
      } else {
        stopPlaybackTimer()
      }
      
      return response.data
    } catch (e) {
      logger.error('[TimeMachine] Toggle play failed:', e)
      throw e
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
      
      return response.data
    } catch (e) {
      logger.error('[TimeMachine] Set speed failed:', e)
      throw e
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
      
      if (response.data.success) {
        trades.value.push(response.data.trade)
        portfolio.value = response.data.portfolio
        toast.success(`交易成功: ${action === 'buy' ? '买入' : '卖出'} ${quantity}股`)
        logger.info('[TimeMachine] Trade executed:', action, quantity)
      }
      
      return response.data
    } catch (e) {
      logger.error('[TimeMachine] Trade failed:', e)
      throw e
    }
  }
  
  /**
   * 跳转到指定进度
   * @param {number} targetBar - 目标 K 线索引
   */
  async function seekTo(targetBar) {
    if (!session.value || targetBar < 0 || targetBar >= totalBars.value) return
    
    try {
      const response = await apiFetch(`${BASE}/session/${session.value}/seek`, {
        method: 'POST',
        timeoutMs: TIMEOUTS.API_DEFAULT,
        body: JSON.stringify({ target_bar: targetBar })
      })
      
      currentBar.value = response.data.current_bar
      portfolio.value = response.data.portfolio
      
      return response.data
    } catch (e) {
      logger.error('[TimeMachine] Seek failed:', e)
      throw e
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
      
      return response.data
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
    klineData.value = []
    currentBar.value = 0
    playbackStatus.value = 'idle'
    trades.value = []
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
  
  onUnmounted(() => {
    stopPlaybackTimer()
    if (session.value) {
      endSession()
    }
  })
  
  // ── Return ──────────────────────────────────────────────────────
  
  return {
    // State
    session,
    loading,
    error,
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
    
    // Utils
    formatMoney,
    formatDate
  }
}