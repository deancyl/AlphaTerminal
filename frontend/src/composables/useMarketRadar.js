/**
 * useMarketRadar.js - Composable for Market Heat Radar API
 * 
 * Provides treemap data and anomaly detection for market visualization
 * 
 * Features:
 * - P1-5: Data source tracking with name, type, and timestamp
 * - P2-8: Configurable refresh interval with localStorage persistence
 */

import { ref, shallowRef, watch, onMounted, onBeforeUnmount } from 'vue'
import { apiFetchDeduped } from '@/utils/api.js'
import { logger } from '@/utils/logger.js'

// P2-8: Refresh interval options (in milliseconds)
export const REFRESH_INTERVAL_OPTIONS = [
  { label: '30秒', value: 30000 },
  { label: '60秒', value: 60000 },
  { label: '2分钟', value: 120000 },
  { label: '5分钟', value: 300000 },
  { label: '关闭', value: 0 },
]

// P2-8: localStorage key for refresh interval
const STORAGE_KEY_REFRESH_INTERVAL = 'market_radar_refresh_interval'

/**
 * Get refresh interval from localStorage
 * @returns {number} Refresh interval in milliseconds
 */
function getStoredRefreshInterval() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY_REFRESH_INTERVAL)
    if (stored) {
      const parsed = parseInt(stored, 10)
      // Validate that it's a valid option
      if (REFRESH_INTERVAL_OPTIONS.some(opt => opt.value === parsed)) {
        return parsed
      }
    }
  } catch (e) {
    logger.warn('[MarketRadar] Failed to read localStorage:', e)
  }
  return 60000 // Default: 60 seconds
}

/**
 * Save refresh interval to localStorage
 * @param {number} interval - Refresh interval in milliseconds
 */
function saveRefreshInterval(interval) {
  try {
    localStorage.setItem(STORAGE_KEY_REFRESH_INTERVAL, String(interval))
  } catch (e) {
    logger.warn('[MarketRadar] Failed to save localStorage:', e)
  }
}

/**
 * Market Radar composable for treemap and anomaly data
 * @returns {Object} Market Radar API methods and state
 */
export function useMarketRadar() {
  // Use shallowRef for large datasets to prevent deep reactivity overhead
  const treemapData = shallowRef([])
  const anomalies = shallowRef([])
  const temperature = ref({
    score: 50,
    label: '中性',
    color: '#fbbf24',
    limit_up: 0,
    limit_down: 0,
    advance: 0,
    decline: 0,
    total: 0,
    timestamp: null
  })
  const loading = ref(false)
  const error = ref(null)
  const lastUpdate = ref(null)
  const dataSource = ref(null) // P1-5: Data source status
  
  // P2-8: Refresh interval state
  const refreshInterval = ref(getStoredRefreshInterval())
  let refreshTimer = null
  
  /**
   * Fetch treemap data for market visualization
   * @param {string} level - 'sector' or 'stock' aggregation level
   * @returns {Promise<void>}
   */
  async function fetchTreemap(level = 'sector') {
    try {
      const response = await apiFetchDeduped(
        `market_radar:treemap:${level}`,
        `/api/v1/market_radar/treemap?level=${level}`,
        { timeoutMs: 15000 }
      )
      
      treemapData.value = response?.data || []
      lastUpdate.value = response?.last_update || new Date().toISOString()
      
      // P1-5: Extract data source information
      if (response?.source_detail) {
        dataSource.value = {
          name: response.source_detail.name || '未知',
          type: response.source_detail.type || '缓存',
          api: response.source_detail.api || '',
          timestamp: response.last_update
        }
      } else if (response?.data_source) {
        // Fallback for simpler data_source field
        dataSource.value = {
          name: response.data_source === 'akshare' ? '东方财富' : '缓存',
          type: response.data_source === 'akshare' ? '实时' : '缓存',
          timestamp: response.last_update
        }
      }
      
      error.value = null
      
      logger.info('[MarketRadar] Treemap data loaded:', treemapData.value.length, 'items')
    } catch (e) {
      logger.error('[MarketRadar] Failed to fetch treemap:', e)
      error.value = e.message || '加载失败'
      dataSource.value = null
      throw e
    }
  }
  
  /**
   * Fetch anomaly alerts
   * @returns {Promise<void>}
   */
  async function fetchAnomalies() {
    try {
      const response = await apiFetchDeduped(
        'market_radar:anomalies',
        '/api/v1/market_radar/anomalies',
        { timeoutMs: 15000 }
      )
      
      anomalies.value = response?.anomalies || []
      error.value = null
      
      logger.info('[MarketRadar] Anomalies loaded:', anomalies.value.length, 'types')
    } catch (e) {
      logger.error('[MarketRadar] Failed to fetch anomalies:', e)
      error.value = e.message || '加载失败'
      throw e
    }
  }
  
  /**
   * Fetch market temperature data
   * @returns {Promise<void>}
   */
  async function fetchTemperature() {
    try {
      const response = await apiFetchDeduped(
        'market_radar:temperature',
        '/api/v1/market_radar/temperature',
        { timeoutMs: 10000 }
      )
      
      if (response) {
        temperature.value = {
          score: response.score ?? 50,
          label: response.label || '中性',
          color: response.color || '#fbbf24',
          limit_up: response.limit_up ?? 0,
          limit_down: response.limit_down ?? 0,
          advance: response.advance ?? 0,
          decline: response.decline ?? 0,
          total: response.total ?? 0,
          timestamp: response.timestamp
        }
      }
      
      logger.info('[MarketRadar] Temperature loaded:', temperature.value.score)
    } catch (e) {
      logger.error('[MarketRadar] Failed to fetch temperature:', e)
      throw e
    }
  }
  
  /**
   * Refresh all data
   * @returns {Promise<void>}
   */
  async function refresh() {
    loading.value = true
    error.value = null
    
    try {
      await Promise.all([fetchTreemap(), fetchAnomalies(), fetchTemperature()])
    } catch (e) {
      // Error already set in individual fetch methods
      logger.error('[MarketRadar] Refresh failed:', e)
    } finally {
      loading.value = false
    }
  }
  
  /**
   * Format timestamp for display
   * @param {string} timestamp - ISO timestamp
   * @returns {string} Formatted time string
   */
  function formatTime(timestamp) {
    if (!timestamp) return '--'
    try {
      const date = new Date(timestamp)
      return date.toLocaleTimeString('zh-CN', { 
        hour: '2-digit', 
        minute: '2-digit',
        second: '2-digit'
      })
    } catch {
      return '--'
    }
  }
  
  /**
   * P2-8: Set refresh interval and persist to localStorage
   * @param {number} interval - Refresh interval in milliseconds
   */
  function setRefreshInterval(interval) {
    refreshInterval.value = interval
    saveRefreshInterval(interval)
    
    // Restart timer with new interval
    stopAutoRefresh()
    if (interval > 0) {
      startAutoRefresh()
    }
    
    logger.info('[MarketRadar] Refresh interval set to:', interval, 'ms')
  }
  
  /**
   * P2-8: Start auto-refresh timer
   */
  function startAutoRefresh() {
    if (refreshTimer) {
      clearInterval(refreshTimer)
    }
    
    if (refreshInterval.value > 0) {
      refreshTimer = setInterval(() => {
        refresh()
      }, refreshInterval.value)
    }
  }
  
  /**
   * P2-8: Stop auto-refresh timer
   */
  function stopAutoRefresh() {
    if (refreshTimer) {
      clearInterval(refreshTimer)
      refreshTimer = null
    }
  }
  
  // P2-8: Watch for interval changes
  watch(refreshInterval, (newInterval) => {
    saveRefreshInterval(newInterval)
  })
  
  return {
    // State
    treemapData,
    anomalies,
    temperature,
    loading,
    error,
    lastUpdate,
    dataSource, // P1-5: Expose data source
    refreshInterval, // P2-8: Expose refresh interval
    
    // Methods
    fetchTreemap,
    fetchAnomalies,
    fetchTemperature,
    refresh,
    formatTime,
    setRefreshInterval, // P2-8: Set refresh interval
    startAutoRefresh, // P2-8: Start timer
    stopAutoRefresh, // P2-8: Stop timer
  }
}

export default useMarketRadar
