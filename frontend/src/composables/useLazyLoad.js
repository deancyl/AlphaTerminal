/**
 * useLazyLoad - Intersection Observer based lazy loading composable
 * 
 * Delays component initialization until it becomes visible in viewport.
 * Useful for heavy chart components that render off-screen.
 * 
 * @param {Object} options - Configuration options
 * @param {number} options.threshold - Visibility threshold (0-1), default 0.1
 * @param {string} options.rootMargin - Root margin for early loading, default '100px'
 * @param {boolean} options.once - Only trigger once, default true
 * @returns {Object} { isVisible, containerRef, reset }
 */
import { ref, onMounted, onUnmounted } from 'vue'

export function useLazyLoad(options = {}) {
  const {
    threshold = 0.1,
    rootMargin = '100px',
    once = true
  } = options

  const isVisible = ref(false)
  const containerRef = ref(null)
  let observer = null

  function setupObserver() {
    if (!containerRef.value) return

    observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0]
        if (entry.isIntersecting) {
          isVisible.value = true
          if (once && observer) {
            observer.disconnect()
          }
        } else if (!once) {
          isVisible.value = false
        }
      },
      {
        threshold,
        rootMargin
      }
    )

    observer.observe(containerRef.value)
  }

  function reset() {
    isVisible.value = false
    if (observer) {
      observer.disconnect()
    }
    setupObserver()
  }

  onMounted(() => {
    setupObserver()
  })

  onUnmounted(() => {
    if (observer) {
      observer.disconnect()
    }
  })

  return {
    isVisible,
    containerRef,
    reset
  }
}
