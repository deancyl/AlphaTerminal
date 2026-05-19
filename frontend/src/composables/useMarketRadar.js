/**
 * useMarketRadar.js - Composable for Market Heat Radar API
 * 
 * Provides treemap data and anomaly detection for market visualization
 */

import { ref, shallowRef } from 'vue'
import { apiFetchDeduped } from '@/utils/api.js'
import { logger } from '@/utils/logger.js'

/**
 * Market Radar composable for treemap and anomaly data
 * @returns {Object} Market Radar API methods and state
 */
export function useMarketRadar() {
  // Use shallowRef for large datasets to prevent deep reactivity overhead
  const treemapData = shallowRef([])
  const anomalies = shallowRef([])
  const loading = ref(false)
  const error = ref(null)
  const lastUpdate = ref(null)
  
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
      error.value = null
      
      logger.info('[MarketRadar] Treemap data loaded:', treemapData.value.length, 'items')
    } catch (e) {
      logger.error('[MarketRadar] Failed to fetch treemap:', e)
      error.value = e.message || '加载失败'
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
   * Refresh all data
   * @returns {Promise<void>}
   */
  async function refresh() {
    loading.value = true
    error.value = null
    
    try {
      await Promise.all([fetchTreemap(), fetchAnomalies()])
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
  
  return {
    // State
    treemapData,
    anomalies,
    loading,
    error,
    lastUpdate,
    
    // Methods
    fetchTreemap,
    fetchAnomalies,
    refresh,
    formatTime,
  }
}

export default useMarketRadar
