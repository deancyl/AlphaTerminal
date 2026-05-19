/**
 * useCrosshairSync.js - Crosshair synchronization composable
 *
 * Provides synchronized crosshair movement across multiple charts.
 * When user moves crosshair on one chart, all other charts sync to the same date.
 *
 * Features:
 * - Native echarts.connect() for chart grouping (primary)
 * - Manual debounced sync as fallback (100ms)
 * - Active panel tracking to prevent circular updates
 * - Reset functionality for modal close
 */

import { ref, shallowRef } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import { getECharts } from '../utils/lazyEcharts.js'

// Chart group name for echarts.connect()
const CHART_GROUP = 'multi-asset-matrix'

/**
 * Crosshair synchronization composable
 *
 * @returns {Object} Crosshair sync API
 */
export function useCrosshairSync() {
  // Synced date - the date all charts should show
  const syncedDate = ref(null)

  // Active panel index - which panel initiated the current sync
  const activePanel = ref(null)

  // Debounced sync function (100ms delay)
  const debouncedSync = useDebounceFn((date) => {
    syncedDate.value = date
  }, 100)

  /**
   * Handle crosshair move from a panel
   *
   * @param {number} panelIndex - Index of the panel that moved
   * @param {string} date - The date to sync to
   */
  function onCrosshairMove(panelIndex, date) {
    // Only sync if this panel is the active one or no panel is active
    // This prevents circular updates when other charts respond to sync
    if (activePanel.value === null || activePanel.value === panelIndex) {
      activePanel.value = panelIndex
      debouncedSync(date)
    }
  }

  /**
   * Set the active panel (called when user starts interacting with a panel)
   *
   * @param {number} panelIndex - Index of the panel becoming active
   */
  function setActivePanel(panelIndex) {
    activePanel.value = panelIndex
  }

  /**
   * Clear active panel (called when user stops interacting)
   */
  function clearActivePanel() {
    activePanel.value = null
  }

  /**
   * Reset all sync state (called when modal closes)
   */
  function resetSync() {
    syncedDate.value = null
    activePanel.value = null
  }

  return {
    syncedDate,
    activePanel,
    onCrosshairMove,
    setActivePanel,
    clearActivePanel,
    resetSync
  }
}

/**
 * Multi-chart crosshair manager
 * Manages crosshair sync for multiple chart instances
 *
 * @param {number} panelCount - Number of panels to manage
 * @returns {Object} Manager API
 */
export function useMultiChartCrosshair(panelCount = 4) {
  const { syncedDate, activePanel, onCrosshairMove, resetSync } = useCrosshairSync()

  // Store chart instances for dispatching actions
  const chartInstances = shallowRef([])

  /**
   * Register a chart instance
   *
   * @param {number} index - Panel index
   * @param {Object} chart - ECharts instance
   */
  function registerChart(index, chart) {
    if (index >= 0 && index < panelCount) {
      chartInstances.value[index] = chart
    }
  }

  /**
   * Unregister a chart instance
   *
   * @param {number} index - Panel index
   */
  function unregisterChart(index) {
    if (index >= 0 && index < panelCount) {
      chartInstances.value[index] = null
    }
  }

  /**
   * Sync all charts to a specific date
   *
   * @param {string} date - Target date
   * @param {Array} klineDataArrays - Array of kline data for each panel
   */
  function syncAllChartsToDate(date, klineDataArrays) {
    if (!date) return

    chartInstances.value.forEach((chart, index) => {
      if (!chart || chart.isDisposed?.()) return

      const klineData = klineDataArrays[index]
      if (!klineData || !klineData.length) return

      // Find the index for this date
      const dataIndex = klineData.findIndex(d => d.date === date)
      if (dataIndex >= 0) {
        chart.dispatchAction({
          type: 'showTip',
          seriesIndex: 0,
          dataIndex: dataIndex
        })
      }
    })
  }

  /**
   * Hide all tooltips
   */
  function hideAllTips() {
    chartInstances.value.forEach((chart) => {
      if (!chart || chart.isDisposed?.()) return
      chart.dispatchAction({
        type: 'hideTip'
      })
    })
  }

  return {
    syncedDate,
    activePanel,
    chartInstances,
    registerChart,
    unregisterChart,
    onCrosshairMove,
    syncAllChartsToDate,
    hideAllTips,
    resetSync
  }
}

/**
 * Connect charts using native echarts.connect()
 * This enables built-in crosshair synchronization across all charts in the group
 *
 * @param {Array} charts - Array of ECharts instances to connect
 */
export async function connectCharts(charts) {
  if (!charts || !charts.length) return

  try {
    const echarts = await getECharts()

    charts.forEach(chart => {
      if (chart && !chart.isDisposed?.()) {
        chart.group = CHART_GROUP
      }
    })

    echarts.connect(CHART_GROUP)
  } catch (e) {
    console.warn('[useCrosshairSync] Failed to connect charts:', e)
  }
}

/**
 * Disconnect charts from the group
 * Call this when the modal closes to prevent memory leaks
 */
export async function disconnectCharts() {
  try {
    const echarts = await getECharts()
    echarts.disconnect(CHART_GROUP)
  } catch (e) {
    console.warn('[useCrosshairSync] Failed to disconnect charts:', e)
  }
}

/**
 * Get the chart group name
 */
export function getChartGroupName() {
  return CHART_GROUP
}

export default useCrosshairSync