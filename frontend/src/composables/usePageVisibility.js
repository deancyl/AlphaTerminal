import { ref, onMounted, onUnmounted } from 'vue'

export function usePageVisibility() {
  const isVisible = ref(document.visibilityState === 'visible')
  const wasHidden = ref(false)
  const lastChangeTime = ref(Date.now())

  let wasHiddenTimeout = null

  function handleVisibilityChange() {
    const nowVisible = document.visibilityState === 'visible'
    const wasVisible = isVisible.value

    isVisible.value = nowVisible
    lastChangeTime.value = Date.now()

    if (nowVisible && !wasVisible) {
      wasHidden.value = true
      if (wasHiddenTimeout) {
        clearTimeout(wasHiddenTimeout)
      }
      wasHiddenTimeout = setTimeout(() => {
        wasHidden.value = false
      }, 100)
    }
  }

  onMounted(() => {
    document.addEventListener('visibilitychange', handleVisibilityChange)
  })

  onUnmounted(() => {
    document.removeEventListener('visibilitychange', handleVisibilityChange)
    if (wasHiddenTimeout) {
      clearTimeout(wasHiddenTimeout)
    }
  })

  return {
    isVisible,
    wasHidden,
    lastChangeTime
  }
}
