import { ref } from 'vue'

/**
 * Safe ECharts operations with error boundary
 * Provides validation and error handling for chart operations
 */
export function useEChartsErrorBoundary() {
  const errorState = ref(null)

  /**
   * Safe setOption with error catching
   * @param {Object} chart - ECharts instance
   * @param {Object} option - Chart option configuration
   * @param {string} chartId - Chart identifier for logging
   * @returns {boolean} - Whether operation succeeded
   */
  function safeSetOption(chart, option, chartId) {
    if (!chart) {
      console.warn(`[ECharts] Chart ${chartId} is null`)
      return false
    }
    if (chart.isDisposed && chart.isDisposed()) {
      console.warn(`[ECharts] Chart ${chartId} is disposed`)
      return false
    }
    try {
      chart.setOption(option, { notMerge: true })
      errorState.value = null
      return true
    } catch (e) {
      console.error(`[ECharts] ${chartId} setOption error:`, e.message)
      errorState.value = { chartId, error: e.message }
      return false
    }
  }

  /**
   * Check if data is valid for chart rendering
   * @param {Array} data - Data array to validate
   * @param {Array} requiredFields - Fields that must have at least one non-null value
   * @returns {Object} - { valid: boolean, reason?: string }
   */
  function validateChartData(data, requiredFields = []) {
    if (!data) {
      return { valid: false, reason: 'null' }
    }
    if (!Array.isArray(data)) {
      return { valid: false, reason: 'not_array' }
    }
    if (data.length === 0) {
      return { valid: false, reason: 'empty' }
    }
    for (const field of requiredFields) {
      const hasValidValue = data.some(d => d && d[field] !== null && d[field] !== undefined)
      if (!hasValidValue) {
        return { valid: false, reason: `missing_${field}` }
      }
    }
    return { valid: true }
  }

  /**
   * Display empty state message in chart container
   * @param {HTMLElement} container - Chart container element
   * @param {string} message - Message to display
   * @param {Function} retryFn - Optional retry function to call
   */
  function showChartEmptyState(container, message, retryFn) {
    if (!container) return
    
    const retryButton = retryFn ? `
      <button 
        class="mt-2 px-3 py-1 bg-terminal-accent/20 text-terminal-accent rounded text-xs hover:bg-terminal-accent/30 transition"
        id="chart-empty-retry-${Date.now()}"
      >
        刷新数据
      </button>
    ` : ''
    
    container.innerHTML = `
      <div class="flex flex-col items-center justify-center h-full">
        <span class="text-terminal-dim text-sm">${message}</span>
        ${retryButton}
      </div>
    `
    
    // Attach retry handler
    if (retryFn) {
      const retryBtn = container.querySelector('[id^="chart-empty-retry"]')
      if (retryBtn) {
        retryBtn.addEventListener('click', retryFn)
      }
    }
  }

  /**
   * Display error state with retry button in chart container
   * @param {HTMLElement} container - Chart container element
   * @param {string} message - Error message to display
   * @param {Function} retryFn - Retry function to call
   */
  function showChartErrorState(container, message, retryFn) {
    if (!container) return
    const retryId = `retry-${Date.now()}`
    container.innerHTML = `
      <div class="flex flex-col items-center justify-center h-full">
        <span class="text-warning text-sm">⚠️ ${message}</span>
        <button 
          id="${retryId}"
          class="mt-2 px-3 py-1 bg-terminal-accent/20 text-terminal-accent rounded text-xs hover:bg-terminal-accent/30 transition"
        >
          重试
        </button>
      </div>
    `
    const retryBtn = document.getElementById(retryId)
    if (retryBtn && retryFn) {
      retryBtn.addEventListener('click', retryFn)
    }
  }

  /**
   * Clear error state
   */
  function clearError() {
    errorState.value = null
  }

  return {
    safeSetOption,
    validateChartData,
    showChartEmptyState,
    showChartErrorState,
    errorState,
    clearError
  }
}
