/**
 * useSwipe.js — Mobile swipe gesture detection composable
 * 
 * Detects horizontal swipe gestures for view navigation on mobile devices.
 * 
 * Features:
 * - Swipe left/right detection with configurable threshold
 * - Maximum duration constraint to distinguish from drag
 * - Only active on mobile viewports (< 768px)
 * - Visual feedback callbacks for swipe progress
 * 
 * Usage:
 * const { onSwipeLeft, onSwipeRight, swipeProgress } = useSwipe({
 *   onSwipeLeft: () => nextView(),
 *   onSwipeRight: () => prevView(),
 *   threshold: 50,
 *   maxDuration: 300
 * })
 */
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useBreakpoints, breakpointsTailwind } from '@vueuse/core'

export function useSwipe(options = {}) {
  const {
    onSwipeLeft = () => {},
    onSwipeRight = () => {},
    onSwipeStart = () => {},
    onSwipeMove = () => {},
    onSwipeEnd = () => {},
    threshold = 50,        // Minimum distance in px to trigger swipe
    maxDuration = 300,     // Maximum duration in ms for swipe gesture
    enabled = true
  } = options

  // Mobile detection using Tailwind breakpoints
  const breakpoints = useBreakpoints(breakpointsTailwind)
  const isMobile = breakpoints.smaller('md')  // < 768px

  // Touch state
  const touchStartX = ref(0)
  const touchStartY = ref(0)
  const touchStartTime = ref(0)
  const isSwiping = ref(false)
  const swipeOffset = ref(0)

  // Computed swipe progress (-1 to 1, negative = left, positive = right)
  const swipeProgress = computed(() => {
    if (!isSwiping.value) return 0
    return swipeOffset.value / (threshold * 2)  // Normalize to -1..1 range
  })

  function handleTouchStart(event) {
    // Only handle on mobile and when enabled
    if (!isMobile.value || !enabled) return

    const touch = event.touches[0]
    touchStartX.value = touch.clientX
    touchStartY.value = touch.clientY
    touchStartTime.value = Date.now()
    isSwiping.value = true
    swipeOffset.value = 0

    onSwipeStart({ x: touchStartX.value, y: touchStartY.value })
  }

  function handleTouchMove(event) {
    // Only handle on mobile and when enabled
    if (!isMobile.value || !enabled || !isSwiping.value) return

    const touch = event.touches[0]
    const deltaX = touch.clientX - touchStartX.value
    const deltaY = touch.clientY - touchStartY.value

    // Check if this is a horizontal swipe (not vertical scroll)
    // If vertical movement is greater, ignore horizontal swipe
    if (Math.abs(deltaY) > Math.abs(deltaX) * 1.5) {
      return
    }

    // Prevent default to stop scroll during horizontal swipe
    // Only prevent if horizontal movement is significant
    if (Math.abs(deltaX) > 10) {
      event.preventDefault()
    }

    swipeOffset.value = deltaX
    onSwipeMove({ 
      offset: deltaX, 
      progress: swipeProgress.value,
      direction: deltaX < 0 ? 'left' : 'right'
    })
  }

  function handleTouchEnd(event) {
    // Only handle on mobile and when enabled
    if (!isMobile.value || !enabled || !isSwiping.value) return

    const duration = Date.now() - touchStartTime.value
    const deltaX = swipeOffset.value

    // Determine if this was a valid swipe
    const isValidSwipe = 
      Math.abs(deltaX) >= threshold &&  // Met minimum distance
      duration <= maxDuration             // Within time limit

    if (isValidSwipe) {
      if (deltaX < 0) {
        // Swipe left → next view
        onSwipeLeft()
      } else {
        // Swipe right → previous view
        onSwipeRight()
      }
    }

    // Reset state
    isSwiping.value = false
    swipeOffset.value = 0

    onSwipeEnd({ 
      wasValid: isValidSwipe, 
      direction: deltaX < 0 ? 'left' : 'right',
      distance: Math.abs(deltaX),
      duration
    })
  }

  // Attach event listeners
  onMounted(() => {
    // Use passive: false to allow preventDefault in touchmove
    document.addEventListener('touchstart', handleTouchStart, { passive: true })
    document.addEventListener('touchmove', handleTouchMove, { passive: false })
    document.addEventListener('touchend', handleTouchEnd, { passive: true })
  })

  onUnmounted(() => {
    document.removeEventListener('touchstart', handleTouchStart)
    document.removeEventListener('touchmove', handleTouchMove)
    document.removeEventListener('touchend', handleTouchEnd)
  })

  return {
    isMobile,
    isSwiping,
    swipeOffset,
    swipeProgress,
    // Expose for testing/debugging
    threshold,
    maxDuration
  }
}
