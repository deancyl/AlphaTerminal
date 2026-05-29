/**
 * useOptions Composable
 * 
 * Provides reactive state and computed properties for Options Analysis module.
 * Features:
 * - Chain data fetching with abort controller
 * - ATM (At-The-Money) strike calculation
 * - PCR (Put-Call Ratio) calculation
 * - IV Smile data generation for ECharts
 * - Greeks data aggregation
 * - Auto-refresh mechanism (60s default)
 */

import { ref, shallowRef, computed, onMounted, onUnmounted } from 'vue'
import { apiFetch } from '../utils/api.js'
import { useAbortableRequest } from './useAbortableRequest.js'

/**
 * Options composable for chain data analysis
 * @param {string} initialSymbol - Initial option symbol (default: 'io2506')
 * @param {number} autoRefreshMs - Auto-refresh interval in ms (default: 60000, 0 to disable)
 */
export function useOptions(initialSymbol = 'io2506', autoRefreshMs = 60000) {
  // State
  const symbol = ref(initialSymbol)
  const chainData = shallowRef(null)
  const loading = ref(false)
  const error = ref(null)
  const autoRefreshEnabled = ref(autoRefreshMs > 0)
  const contracts = ref([
    { code: 'io2506', name: '沪深300股指期权2506' },
    { code: 'io2507', name: '沪深300股指期权2507' },
    { code: 'mo2506', name: '中证1000股指期权2506' },
    { code: 'mo2507', name: '中证1000股指期权2507' },
  ])
  
  const { createSignal, complete, abort } = useAbortableRequest()
  
  // ==================== Validation ====================
  
  /**
   * Validate chain data structure
   */
  function validateChainData(data) {
    if (!data || typeof data !== 'object') return false
    // Relax: allow both calls/puts arrays OR chain array
    if (data.calls && Array.isArray(data.calls) && data.puts && Array.isArray(data.puts)) {
      // Standard format: calls/puts arrays
      for (const opt of [...data.calls, ...data.puts]) {
        if (typeof opt !== 'object') return false
        if (opt.strike == null) return false
        if (opt.code == null) return false
      }
      return true
    }
    if (data.chain && Array.isArray(data.chain)) {
      // Alternative format: chain array (each item has call/put)
      for (const row of data.chain) {
        if (typeof row !== 'object') return false
        if (row.strike == null) return false
      }
      return true
    }
    return false
  }
  
  // ==================== Computed Properties ====================
  
  /**
   * ATM Strike - closest strike to underlying spot price
   */
  const atmStrike = computed(() => {
    if (!chainData.value?.underlying_spot) return null
    const spot = chainData.value.underlying_spot
    const allStrikes = new Set()
    chainData.value.calls.forEach(c => {
      if (c.strike != null) allStrikes.add(c.strike)
    })
    chainData.value.puts.forEach(p => {
      if (p.strike != null) allStrikes.add(p.strike)
    })
    const strikes = Array.from(allStrikes).sort((a, b) => a - b)
    if (strikes.length === 0) return null
    return strikes.reduce((prev, curr) => 
      Math.abs(curr - spot) < Math.abs(prev - spot) ? curr : prev
    , strikes[0])
  })
  
  /**
   * Put-Call Ratio (OI-based)
   * PCR < 0.8: Bullish sentiment
   * PCR > 1.2: Bearish sentiment
   */
  const pcr = computed(() => {
    if (!chainData.value) return null
    const totalCallOI = chainData.value.calls.reduce(
      (sum, c) => sum + (c.open_interest || 0), 0
    )
    const totalPutOI = chainData.value.puts.reduce(
      (sum, p) => sum + (p.open_interest || 0), 0
    )
    if (totalCallOI === 0) return null
    return totalPutOI / totalCallOI
  })
  
  /**
   * PCR Sentiment classification
   */
  const pcrSentiment = computed(() => {
    if (pcr.value === null) return 'unknown'
    if (pcr.value < 0.8) return 'bullish'
    if (pcr.value > 1.2) return 'bearish'
    return 'neutral'
  })
  
  /**
   * IV Smile Data for ECharts
   * Format: [strike, ivPercent]
   */
  const ivSmileData = computed(() => {
    if (!chainData.value) return { calls: [], puts: [] }
    return {
      calls: chainData.value.calls
        .filter(c => c.iv != null && c.strike != null)
        .map(c => [c.strike, c.iv * 100])
        .sort((a, b) => a[0] - b[0]),
      puts: chainData.value.puts
        .filter(p => p.iv != null && p.strike != null)
        .map(p => [p.strike, p.iv * 100])
        .sort((a, b) => a[0] - b[0])
    }
  })
  
  /**
   * Greeks Data for Charts
   */
  const greeksData = computed(() => {
    if (!chainData.value) return { delta: [], gamma: [], theta: [], vega: [] }
    const allOptions = [...chainData.value.calls, ...chainData.value.puts]
    return {
      delta: allOptions.filter(o => o.delta != null).map(o => ({
        strike: o.strike,
        isCall: o.is_call,
        value: o.delta
      })),
      gamma: allOptions.filter(o => o.gamma != null).map(o => ({
        strike: o.strike,
        isCall: o.is_call,
        value: o.gamma
      })),
      theta: allOptions.filter(o => o.theta != null).map(o => ({
        strike: o.strike,
        isCall: o.is_call,
        value: o.theta
      })),
      vega: allOptions.filter(o => o.vega != null).map(o => ({
        strike: o.strike,
        isCall: o.is_call,
        value: o.vega
      }))
    }
  })
  
  /**
   * T-Style Chain Rows (Call | Strike | Put)
   * Each row has unique 'id' for VirtualizedTable
   */
  const chainRows = computed(() => {
    if (!chainData.value) return []
    const strikeMap = new Map()
    chainData.value.calls.forEach(c => {
      if (c.strike != null) {
        if (!strikeMap.has(c.strike)) {
          strikeMap.set(c.strike, { id: c.strike.toString(), strike: c.strike, call: null, put: null })
        }
        strikeMap.get(c.strike).call = { ...c, is_call: true }
      }
    })
    chainData.value.puts.forEach(p => {
      if (p.strike != null) {
        if (!strikeMap.has(p.strike)) {
          strikeMap.set(p.strike, { id: p.strike.toString(), strike: p.strike, call: null, put: null })
        }
        strikeMap.get(p.strike).put = { ...p, is_call: false }
      }
    })
    return Array.from(strikeMap.values()).sort((a, b) => a.strike - b.strike)
  })
  
  // ==================== Methods ====================
  
  /**
   * Fetch option chain data
   */
  async function fetchChain() {
    loading.value = true
    error.value = null
    const signal = createSignal()
    
    try {
      const res = await apiFetch(`/api/v1/options/cffex/chain?symbol=${symbol.value}`, {
        timeoutMs: 30000,
        signal
      })
      
      // Validate before assignment
      if (validateChainData(res)) {
        chainData.value = res
      } else {
        error.value = '数据格式异常，请稍后重试'
        console.error('[Options] Invalid chain data structure:', res)
      }
      complete()
    } catch (e) {
      if (e.name === 'AbortError') return // Ignore abort errors
      error.value = e.message?.includes('timeout') 
        ? '数据获取超时，请稍后重试'
        : '获取期权链失败，请稍后重试'
    } finally {
      loading.value = false
    }
  }
  
  /**
   * Fetch available contracts
   */
  async function fetchContracts() {
    try {
      const res = await apiFetch('/api/v1/options/contracts?exchange=CFFEX', {
        timeoutMs: 10000
      })
      if (res?.contracts?.length) {
        contracts.value = res.contracts
      }
    } catch (e) {
      console.warn('[Options] Failed to fetch contracts:', e)
    }
  }
  
  // ==================== Auto-Refresh ====================
  
  let refreshInterval = null
  
  function startAutoRefresh(intervalMs = 60000) {
    stopAutoRefresh()
    if (autoRefreshEnabled.value && intervalMs > 0) {
      refreshInterval = setInterval(fetchChain, intervalMs)
    }
  }
  
  function stopAutoRefresh() {
    if (refreshInterval) {
      clearInterval(refreshInterval)
      refreshInterval = null
    }
  }
  
  function toggleAutoRefresh() {
    autoRefreshEnabled.value = !autoRefreshEnabled.value
    if (autoRefreshEnabled.value) {
      startAutoRefresh(autoRefreshMs)
    } else {
      stopAutoRefresh()
    }
  }
  
  /**
   * Change symbol and refetch
   */
  function changeSymbol(newSymbol) {
    symbol.value = newSymbol
    abort('Symbol changed')
    fetchChain()
  }
  
  // ==================== Lifecycle ====================
  
  onMounted(async () => {
    await fetchContracts()
    await fetchChain()
    if (autoRefreshMs > 0) {
      startAutoRefresh(autoRefreshMs)
    }
  })
  
  onUnmounted(() => {
    stopAutoRefresh()
    abort('Component unmounted')
  })
  
  // ==================== Return ====================
  
  return {
    // State
    symbol,
    chainData,
    loading,
    error,
    autoRefreshEnabled,
    contracts,
    
    // Computed
    atmStrike,
    pcr,
    pcrSentiment,
    ivSmileData,
    greeksData,
    chainRows,
    
    // Methods
    fetchChain,
    fetchContracts,
    startAutoRefresh,
    stopAutoRefresh,
    toggleAutoRefresh,
    changeSymbol
  }
}
