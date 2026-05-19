/**
 * SSE Progress Composable for Factor Sandbox
 * 
 * Provides EventSource-based streaming for real-time screening progress.
 * Handles connection lifecycle, error recovery, and cleanup.
 */

import { ref, shallowRef, onUnmounted } from 'vue'
import { logger } from '@/utils/logger.js'

export function useSSEProgress() {
  const progress = ref(0)
  const total = ref(0)
  const currentStock = ref('')
  const passedCount = ref(0)
  const isStreaming = ref(false)
  const error = ref(null)
  const results = shallowRef([])
  
  let eventSource = null
  
  function startStreaming(url) {
    if (eventSource) {
      stopStreaming()
    }
    
    progress.value = 0
    total.value = 0
    currentStock.value = ''
    passedCount.value = 0
    isStreaming.value = true
    error.value = null
    results.value = []
    
    eventSource = new EventSource(url)
    
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        
        if (data.done) {
          if (data.error) {
            error.value = data.error
          } else {
            results.value = data.results || []
          }
          stopStreaming()
        } else {
          progress.value = data.progress || 0
          total.value = data.total || 0
          currentStock.value = data.current_stock || ''
          passedCount.value = data.found || 0
        }
      } catch (e) {
        logger.error('[useSSEProgress] Parse error:', e)
      }
    }
    
    eventSource.onerror = (event) => {
      logger.error('[useSSEProgress] Connection error:', event)
      error.value = '筛选连接失败，请检查网络'
      stopStreaming()
    }
    
    eventSource.onopen = () => {
      logger.info('[useSSEProgress] Connection opened')
    }
  }
  
  function stopStreaming() {
    if (eventSource) {
      eventSource.close()
      eventSource = null
    }
    isStreaming.value = false
  }
  
  function getProgressPercent() {
    if (total.value === 0) return 0
    return Math.round((progress.value / total.value) * 100)
  }
  
  onUnmounted(() => {
    stopStreaming()
  })
  
  return {
    progress,
    total,
    currentStock,
    passedCount,
    isStreaming,
    error,
    results,
    startStreaming,
    stopStreaming,
    getProgressPercent,
  }
}