/**
 * usePullToRefresh.js — Mobile pull-to-refresh gesture composable
 * 
 * Usage:
 *   import { usePullToRefresh } from './composables/usePullToRefresh.js'
 *   const { pullDistance, isRefreshing, pullIndicatorStyle, containerRef } = usePullToRefresh(onRefresh)
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useBreakpoints, breakpointsTailwind } from '@vueuse/core'

const PULL_THRESHOLD = 80
const MAX_PULL_DISTANCE = 120
const REFRESH_DURATION = 1500

/**
 * Pull-to-refresh composable
 * @param {Function} onRefresh - Async refresh callback
 * @param {Object} options - Configuration options
 * @param {number} options.threshold - Trigger threshold (default 80px)
 * @param {number} options.maxDistance - Max pull distance (default 120px)
 * @returns {Object} Pull-to-refresh state and methods
 */
export function usePullToRefresh(onRefresh, options = {}) {
  const { threshold = PULL_THRESHOLD, maxDistance = MAX_PULL_DISTANCE } = options

  const pullDistance = ref(0)
  const isRefreshing = ref(false)
  const isPulling = ref(false)
  const startY = ref(0)
  const containerRef = ref(null)

  const breakpoints = useBreakpoints(breakpointsTailwind)
  const isMobile = breakpoints.smaller('md')

  const pullIndicatorStyle = computed(() => {
    const distance = Math.min(pullDistance.value, maxDistance)
    const progress = Math.min(distance / threshold, 1)
    
    return {
      transform: `translateY(${distance}px)`,
      opacity: progress,
      transition: isPulling.value ? 'none' : 'transform 0.2s ease-out, opacity 0.2s ease-out',
    }
  })

  const canRefresh = computed(() => pullDistance.value >= threshold)

  function handleTouchStart(e) {
    if (!isMobile.value || isRefreshing.value) return
    
    const container = e.currentTarget
    const scrollTop = container.scrollTop || 0
    
    if (scrollTop <= 0) {
      isPulling.value = true
      startY.value = e.touches[0].clientY
    }
  }

  function handleTouchMove(e) {
    if (!isPulling.value || isRefreshing.value) return

    const currentY = e.touches[0].clientY
    const deltaY = currentY - startY.value

    if (deltaY > 0) {
      if (deltaY > 10) {
        e.preventDefault()
      }
      
      const dampenedDistance = deltaY * 0.5
      pullDistance.value = Math.min(dampenedDistance, maxDistance)
    } else {
      pullDistance.value = 0
    }
  }

  function handleTouchEnd() {
    if (!isPulling.value) return

    isPulling.value = false

    if (canRefresh.value && !isRefreshing.value) {
      triggerRefresh()
    } else {
      pullDistance.value = 0
    }
  }

  async function triggerRefresh() {
    if (isRefreshing.value) return

    isRefreshing.value = true
    const startTime = Date.now()

    try {
      if (typeof onRefresh === 'function') {
        await onRefresh()
      }
    } catch (error) {
      console.error('[PullToRefresh] Refresh failed:', error)
    } finally {
      const elapsed = Date.now() - startTime
      const remaining = Math.max(0, REFRESH_DURATION - elapsed)

      setTimeout(() => {
        isRefreshing.value = false
        pullDistance.value = 0
      }, remaining)
    }
  }

  function manualRefresh() {
    if (!isRefreshing.value) {
      triggerRefresh()
    }
  }

  function bindEvents(container) {
    if (!container) return

    container.addEventListener('touchstart', handleTouchStart, { passive: true })
    container.addEventListener('touchmove', handleTouchMove, { passive: false })
    container.addEventListener('touchend', handleTouchEnd, { passive: true })
  }

  function unbindEvents(container) {
    if (!container) return

    container.removeEventListener('touchstart', handleTouchStart)
    container.removeEventListener('touchmove', handleTouchMove)
    container.removeEventListener('touchend', handleTouchEnd)
  }

  onMounted(() => {
    if (isMobile.value && containerRef.value) {
      bindEvents(containerRef.value)
    }
  })

  onUnmounted(() => {
    if (containerRef.value) {
      unbindEvents(containerRef.value)
    }
  })

  return {
    pullDistance,
    isRefreshing,
    isPulling,
    canRefresh,
    pullIndicatorStyle,
    containerRef,
    triggerRefresh: manualRefresh,
    bindEvents,
    unbindEvents,
  }
}
