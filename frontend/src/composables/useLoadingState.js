/**
 * useLoadingState - Reusable loading state composable
 * 
 * Features:
 * - isLoading ref for tracking loading state
 * - error ref for storing error messages
 * - Timeout support (default 30s)
 * - Automatic cleanup on unmount
 */
import { ref, onUnmounted } from 'vue'

export function useLoadingState(timeoutMs = 30000) {
  const isLoading = ref(false)
  const error = ref(null)
  let timeoutId = null

  function startLoading() {
    isLoading.value = true
    error.value = null
    
    // Clear any existing timeout
    if (timeoutId) {
      clearTimeout(timeoutId)
    }
    
    // Set timeout
    timeoutId = setTimeout(() => {
      if (isLoading.value) {
        error.value = '请求超时'
        isLoading.value = false
      }
    }, timeoutMs)
  }

  function stopLoading(err = null) {
    // Clear timeout
    if (timeoutId) {
      clearTimeout(timeoutId)
      timeoutId = null
    }
    
    isLoading.value = false
    if (err) {
      error.value = err
    }
  }

  // Cleanup on unmount
  onUnmounted(() => {
    if (timeoutId) {
      clearTimeout(timeoutId)
      timeoutId = null
    }
  })

  return {
    isLoading,
    error,
    startLoading,
    stopLoading
  }
}
