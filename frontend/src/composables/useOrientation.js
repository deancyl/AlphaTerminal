/**
 * useOrientation - Orientation detection composable for mobile devices
 * 
 * Features:
 * - Detects landscape/portrait orientation
 * - Supports both modern Screen Orientation API and legacy fallback
 * - Provides lock/unlock functions for landscape mode
 * - Reactive updates on orientation change
 */
import { ref, onMounted, onUnmounted } from 'vue'

export function useOrientation() {
  const isLandscape = ref(false)
  const isPortrait = ref(true)
  const angle = ref(0)

  function updateOrientation() {
    // Modern API: Screen Orientation
    if (screen.orientation) {
      isLandscape.value = screen.orientation.type.includes('landscape')
      isPortrait.value = !isLandscape.value
      angle.value = screen.orientation.angle || 0
    } 
    // Fallback: matchMedia
    else if (window.matchMedia) {
      isLandscape.value = window.matchMedia('(orientation: landscape)').matches
      isPortrait.value = !isLandscape.value
      angle.value = isLandscape.value ? 90 : 0
    } 
    // Last resort: window dimensions
    else {
      isLandscape.value = window.innerWidth > window.innerHeight
      isPortrait.value = !isLandscape.value
      angle.value = isLandscape.value ? 90 : 0
    }
  }

  /**
   * Lock screen to landscape orientation
   * Note: Only works in fullscreen or standalone mode on most browsers
   */
  async function lockLandscape() {
    if (screen.orientation && screen.orientation.lock) {
      try {
        await screen.orientation.lock('landscape')
        return true
      } catch (e) {
        // Lock failed - typically because not in fullscreen
        console.debug('[useOrientation] Lock failed:', e.message)
        return false
      }
    }
    return false
  }

  /**
   * Lock screen to portrait orientation
   */
  async function lockPortrait() {
    if (screen.orientation && screen.orientation.lock) {
      try {
        await screen.orientation.lock('portrait')
        return true
      } catch (e) {
        console.debug('[useOrientation] Lock failed:', e.message)
        return false
      }
    }
    return false
  }

  /**
   * Unlock screen orientation (return to default)
   */
  function unlockOrientation() {
    if (screen.orientation && screen.orientation.unlock) {
      screen.orientation.unlock()
    }
  }

  onMounted(() => {
    updateOrientation()
    
    // Listen to window resize (covers most orientation changes)
    window.addEventListener('resize', updateOrientation)
    
    // Modern API: Screen Orientation change event
    if (screen.orientation) {
      screen.orientation.addEventListener('change', updateOrientation)
    }
    
    // Legacy: orientationchange event
    window.addEventListener('orientationchange', updateOrientation)
  })

  onUnmounted(() => {
    window.removeEventListener('resize', updateOrientation)
    
    if (screen.orientation) {
      screen.orientation.removeEventListener('change', updateOrientation)
    }
    
    window.removeEventListener('orientationchange', updateOrientation)
  })

  return {
    isLandscape,
    isPortrait,
    angle,
    lockLandscape,
    lockPortrait,
    unlockOrientation,
    updateOrientation
  }
}
