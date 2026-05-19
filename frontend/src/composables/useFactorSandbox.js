/**
 * Factor Sandbox Composable
 * 
 * Provides state management and API integration for the Factor Sandbox
 * stock screening feature.
 * 
 * API Endpoints:
 * - GET /api/v1/factor_sandbox/factors - List all factors
 * - GET /api/v1/factor_sandbox/factors/screening - List screening factors
 * - POST /api/v1/factor_sandbox/screen - Screen stocks with factor filters
 * - POST /api/v1/factor_sandbox/backtest_preview - Quick backtest preview
 */

import { ref, computed, shallowRef } from 'vue'
import { apiFetch, apiFetchDeduped } from '@/utils/api.js'
import { logger } from '@/utils/logger.js'
import { TIMEOUTS } from '@/utils/constants.js'

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

/**
 * @typedef {Object} Factor
 * @property {string} id - Factor ID
 * @property {string} name - Factor display name
 * @property {string} category - Factor category (technical, sentiment, fund_flow, etc.)
 * @property {string} description - Factor description
 * @property {string} unit - Factor unit
 * @property {Object} params - Default parameters
 */

/**
 * @typedef {Object} FactorCategory
 * @property {string} id - Category ID
 * @property {string} name - Category display name
 * @property {string} icon - Category icon
 */

/**
 * @typedef {Object} ScreenedStock
 * @property {string} symbol - Stock symbol
 * @property {string} name - Stock name
 * @property {number} score - Composite score
 * @property {Object} factor_values - Factor values
 */

/**
 * @typedef {Object} BacktestPreview
 * @property {string} symbol - Stock symbol
 * @property {number} start_price - Start price
 * @property {number} end_price - End price
 * @property {number} total_return_pct - Total return percentage
 * @property {number} max_drawdown_pct - Max drawdown percentage
 * @property {number} volatility_pct - Volatility percentage
 * @property {number} trading_days - Number of trading days
 */

// ─────────────────────────────────────────────────────────────────────────────
// Composable
// ─────────────────────────────────────────────────────────────────────────────

export function useFactorSandbox() {
  // ── State ─────────────────────────────────────────────────────────────────
  
  /** @type {import('vue').Ref<Factor[]>} */
  const factors = shallowRef([])
  
  /** @type {import('vue').Ref<FactorCategory[]>} */
  const categories = shallowRef([])
  
  /** @type {import('vue').Ref<Factor[]>} */
  const selectedFactors = ref([])
  
  /** @type {import('vue').Ref<ScreenedStock[]>} */
  const screenedStocks = shallowRef([])
  
  /** @type {import('vue').Ref<BacktestPreview[]>} */
  const backtestPreviews = shallowRef([])
  
  const loading = ref(false)
  const screeningLoading = ref(false)
  const backtestLoading = ref(false)
  const error = ref(null)
  
  const universe = ref('hs300')
  const limit = ref(50)
  
  // ── Computed ───────────────────────────────────────────────────────────────
  
  /** Group factors by category */
  const factorsByCategory = computed(() => {
    const grouped = {}
    for (const factor of factors.value) {
      const cat = factor.category || 'other'
      if (!grouped[cat]) {
        grouped[cat] = []
      }
      grouped[cat].push(factor)
    }
    return grouped
  })
  
  /** Check if a factor is selected */
  const isFactorSelected = computed(() => {
    const selectedIds = new Set(selectedFactors.value.map(f => f.id))
    return (factorId) => selectedIds.has(factorId)
  })
  
  // ── Methods ────────────────────────────────────────────────────────────────
  
  /**
   * Fetch all available factors
   */
  async function fetchFactors() {
    try {
      const response = await apiFetchDeduped(
        'factor_sandbox:factors',
        '/api/v1/factor_sandbox/factors',
        { timeoutMs: TIMEOUTS.API_DEFAULT }
      )
      
      factors.value = response?.factors || []
      
      // Extract unique categories from factors
      const categoryMap = new Map()
      for (const factor of factors.value) {
        if (factor.category && !categoryMap.has(factor.category)) {
          categoryMap.set(factor.category, {
            id: factor.category,
            name: getCategoryName(factor.category),
            icon: getCategoryIcon(factor.category),
          })
        }
      }
      categories.value = Array.from(categoryMap.values())
      
      return factors.value
    } catch (e) {
      logger.error('[useFactorSandbox] Fetch factors error:', e)
      error.value = e.message
      return []
    }
  }
  
  /**
   * Fetch screening-specific factors
   */
  async function fetchScreeningFactors() {
    try {
      const response = await apiFetchDeduped(
        'factor_sandbox:screening_factors',
        '/api/v1/factor_sandbox/factors/screening',
        { timeoutMs: TIMEOUTS.API_DEFAULT }
      )
      
      factors.value = response?.factors || []
      categories.value = response?.categories || []
      
      return factors.value
    } catch (e) {
      logger.error('[useFactorSandbox] Fetch screening factors error:', e)
      error.value = e.message
      return []
    }
  }
  
  /**
   * Add a factor to selection
   * @param {Factor} factor
   */
  function addFactor(factor) {
    if (!isFactorSelected.value(factor.id)) {
      selectedFactors.value.push({ ...factor, params: factor.params || {} })
    }
  }
  
  /**
   * Remove a factor from selection
   * @param {string} factorId
   */
  function removeFactor(factorId) {
    const idx = selectedFactors.value.findIndex(f => f.id === factorId)
    if (idx >= 0) {
      selectedFactors.value.splice(idx, 1)
    }
  }
  
  /**
   * Toggle factor selection
   * @param {Factor} factor
   */
  function toggleFactor(factor) {
    if (isFactorSelected.value(factor.id)) {
      removeFactor(factor.id)
    } else {
      addFactor(factor)
    }
  }
  
  /**
   * Clear all selected factors
   */
  function clearSelectedFactors() {
    selectedFactors.value = []
  }
  
  /**
   * Reorder selected factors
   * @param {number} fromIndex
   * @param {number} toIndex
   */
  function reorderFactors(fromIndex, toIndex) {
    const [removed] = selectedFactors.value.splice(fromIndex, 1)
    selectedFactors.value.splice(toIndex, 0, removed)
  }
  
  /**
   * Run stock screening with selected factors
   */
  async function runScreening() {
    if (screeningLoading.value || selectedFactors.value.length === 0) return
    
    screeningLoading.value = true
    error.value = null
    screenedStocks.value = []
    
    try {
      const response = await apiFetch('/api/v1/factor_sandbox/screen', {
        method: 'POST',
        timeoutMs: 35000, // Backend has 30s timeout
        body: JSON.stringify({
          factors: selectedFactors.value.map(f => ({
            id: f.id,
            params: f.params || {},
          })),
          universe: universe.value,
          limit: limit.value,
        }),
      })
      
      screenedStocks.value = response?.stocks || []
      return screenedStocks.value
    } catch (e) {
      logger.error('[useFactorSandbox] Screening error:', e)
      error.value = e.message
      return []
    } finally {
      screeningLoading.value = false
    }
  }
  
  /**
   * Get backtest preview for selected stocks
   * @param {string[]} symbols
   * @param {string} startDate
   * @param {string} endDate
   */
  async function getBacktestPreview(symbols, startDate, endDate) {
    if (backtestLoading.value || symbols.length === 0) return
    
    backtestLoading.value = true
    
    try {
      const response = await apiFetch('/api/v1/factor_sandbox/backtest_preview', {
        method: 'POST',
        timeoutMs: 35000,
        body: JSON.stringify({
          symbols,
          start_date: startDate,
          end_date: endDate,
        }),
      })
      
      backtestPreviews.value = response?.results || []
      return backtestPreviews.value
    } catch (e) {
      logger.error('[useFactorSandbox] Backtest preview error:', e)
      return []
    } finally {
      backtestLoading.value = false
    }
  }
  
  /**
   * Clear screening results
   */
  function clearResults() {
    screenedStocks.value = []
    backtestPreviews.value = []
  }
  
  // ── Helpers ────────────────────────────────────────────────────────────────
  
  function getCategoryName(categoryId) {
    const names = {
      value: '价值因子',
      growth: '成长因子',
      quality: '质量因子',
      momentum: '动量因子',
      technical: '技术信号',
      sentiment: '市场情绪',
      fund_flow: '资金流向',
      volatility: '波动率因子',
      other: '其他因子',
    }
    return names[categoryId] || categoryId
  }
  
  function getCategoryIcon(categoryId) {
    const icons = {
      value: '💰',
      growth: '📈',
      quality: '⭐',
      momentum: '🚀',
      technical: '📊',
      sentiment: '🧠',
      fund_flow: '💵',
      volatility: '📉',
      other: '📌',
    }
    return icons[categoryId] || '📌'
  }
  
  return {
    // State
    factors,
    categories,
    selectedFactors,
    screenedStocks,
    backtestPreviews,
    loading,
    screeningLoading,
    backtestLoading,
    error,
    universe,
    limit,
    
    // Computed
    factorsByCategory,
    isFactorSelected,
    
    // Methods
    fetchFactors,
    fetchScreeningFactors,
    addFactor,
    removeFactor,
    toggleFactor,
    clearSelectedFactors,
    reorderFactors,
    runScreening,
    getBacktestPreview,
    clearResults,
  }
}
