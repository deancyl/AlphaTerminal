import { ref, watch, onUnmounted } from 'vue'
import { usePageVisibility } from './usePageVisibility.js'

export function useSmartPolling(fetchFn, options = {}) {
  const {
    interval = 30000,
    immediate = true,
    pauseWhenHidden = true
  } = options

  const { isVisible, wasHidden } = usePageVisibility()
  
  const isPolling = ref(false)
  const error = ref(null)
  const lastFetchTime = ref(null)
  
  let intervalId = null

  async function execute() {
    try {
      error.value = null
      await fetchFn()
      lastFetchTime.value = Date.now()
    } catch (e) {
      error.value = e
    }
  }

  function start() {
    if (isPolling.value) return
    
    isPolling.value = true
    
    if (immediate) {
      execute()
    }
    
    intervalId = setInterval(() => {
      if (pauseWhenHidden && !isVisible.value) {
        return
      }
      execute()
    }, interval)
  }

  function stop() {
    isPolling.value = false
    if (intervalId) {
      clearInterval(intervalId)
      intervalId = null
    }
  }

  watch(isVisible, (visible) => {
    if (!isPolling.value) return
    
    if (visible && pauseWhenHidden) {
      execute()
    }
  })

  watch(wasHidden, (wasHiddenValue) => {
    if (wasHiddenValue && isPolling.value && isVisible.value) {
      execute()
    }
  })

  onUnmounted(() => {
    stop()
  })

  return {
    isPolling,
    error,
    lastFetchTime,
    start,
    stop,
    execute
  }
}
