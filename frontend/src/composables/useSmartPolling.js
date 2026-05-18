import { ref, watch, onUnmounted } from 'vue'
import { usePageVisibility } from './usePageVisibility.js'

/**
 * Smart polling with Visibility API integration
 * - Pauses when tab is hidden
 * - Resumes when tab becomes visible
 * - Exponential backoff on failures
 * 
 * @param {Function} fetchFn - Async function to execute
 * @param {Object} options - Configuration options
 * @param {number} options.interval - Base polling interval in ms (default: 5 minutes)
 * @param {number} options.maxBackoff - Maximum backoff interval in ms (default: 30 minutes)
 * @param {boolean} options.immediate - Execute immediately on start (default: true)
 * @param {boolean} options.pauseWhenHidden - Pause when tab is hidden (default: true)
 */
export function useSmartPolling(fetchFn, options = {}) {
  const {
    interval = 5 * 60 * 1000, // 5 minutes default
    maxBackoff = 30 * 60 * 1000, // 30 minutes max
    immediate = true,
    pauseWhenHidden = true
  } = options

  const { isVisible, wasHidden } = usePageVisibility()

  const isPolling = ref(false)
  const error = ref(null)
  const lastRefresh = ref(null)
  const nextRefresh = ref(null)
  const errorCount = ref(0)

  let timerId = null
  let currentInterval = interval

  /**
   * Calculate exponential backoff interval
   * Formula: interval * 2^errorCount, capped at maxBackoff
   */
  function calculateBackoff() {
    return Math.min(interval * Math.pow(2, errorCount.value), maxBackoff)
  }

  /**
   * Execute the fetch function with error handling
   */
  async function executeFetch() {
    try {
      error.value = null
      await fetchFn()
      // Reset on success
      errorCount.value = 0
      currentInterval = interval
      lastRefresh.value = new Date()
    } catch (e) {
      errorCount.value++
      currentInterval = calculateBackoff()
      error.value = e
      console.warn('[SmartPolling] Fetch failed, backoff:', currentInterval, 'ms, errors:', errorCount.value)
    }
    scheduleNext()
  }

  /**
   * Schedule the next fetch
   */
  function scheduleNext() {
    if (timerId) clearTimeout(timerId)
    nextRefresh.value = new Date(Date.now() + currentInterval)
    timerId = setTimeout(executeFetch, currentInterval)
  }

  /**
   * Start polling
   */
  function start() {
    if (isPolling.value) return

    isPolling.value = true
    errorCount.value = 0
    currentInterval = interval

    if (immediate) {
      executeFetch()
    } else {
      scheduleNext()
    }
  }

  /**
   * Stop polling
   */
  function stop() {
    isPolling.value = false
    if (timerId) {
      clearTimeout(timerId)
      timerId = null
    }
  }

  /**
   * Force immediate refresh (resets backoff)
   */
  function refreshNow() {
    errorCount.value = 0
    currentInterval = interval
    if (timerId) clearTimeout(timerId)
    executeFetch()
  }

  // Visibility API integration - pause when hidden
  watch(isVisible, (visible) => {
    if (!isPolling.value) return

    if (!visible && pauseWhenHidden) {
      // Tab hidden - pause polling
      if (timerId) {
        clearTimeout(timerId)
        timerId = null
      }
    } else if (visible && pauseWhenHidden) {
      // Tab visible - resume polling
      scheduleNext()
    }
  })

  // Refresh when tab becomes visible after being hidden
  watch(wasHidden, (wasHiddenValue) => {
    if (wasHiddenValue && isPolling.value && isVisible.value) {
      // Tab was hidden and is now visible - refresh immediately
      refreshNow()
    }
  })

  onUnmounted(() => {
    stop()
  })

  return {
    isPolling,
    error,
    lastRefresh,
    nextRefresh,
    errorCount,
    start,
    stop,
    refreshNow,
    execute: executeFetch
  }
}
