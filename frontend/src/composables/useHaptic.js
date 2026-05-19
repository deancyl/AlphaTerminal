/**
 * Haptic Feedback Composable
 * 
 * Provides haptic feedback for mobile devices using the Vibration API.
 * Falls back gracefully on unsupported browsers.
 * 
 * Usage:
 * ```js
 * const { light, medium, heavy, success, error } = useHaptic()
 * 
 * // Light tap for button press
 * light()
 * 
 * // Success feedback for completed action
 * success()
 * 
 * // Error feedback for failed action
 * error()
 * ```
 */
import { ref } from 'vue'

// Shared state for browser support
const isSupported = ref(false)

// Check support on mount (client-side only)
if (typeof window !== 'undefined') {
  isSupported.value = 'vibrate' in navigator
}

/**
 * Haptic feedback patterns (in milliseconds)
 * Based on Material Design haptic guidelines
 */
const HAPTIC_PATTERNS = {
  // Single vibrations
  LIGHT: 10,        // Light tap - button press, toggle
  MEDIUM: 20,       // Medium tap - card selection, navigation
  HEAVY: 30,        // Heavy tap - important action, delete

  // Pattern vibrations
  SUCCESS: [10, 50, 10],           // Double tap - success, completed
  WARNING: [20, 30, 20],           // Two medium taps - warning
  ERROR: [30, 50, 30, 50, 30],     // Triple tap - error, failed
  SELECTION: 5,                    // Very light - item selection
  SELECTION_CHANGE: [5, 10, 5],    // Double light - selection change
}

export function useHaptic() {
  /**
   * Trigger vibration if supported
   * @param {number|number[]} pattern - Duration in ms or pattern array
   */
  function vibrate(pattern) {
    if (isSupported.value && navigator.vibrate) {
      try {
        navigator.vibrate(pattern)
      } catch (e) {
        // Silently fail if vibration throws
        console.debug('[useHaptic] Vibration failed:', e)
      }
    }
  }

  /**
   * Light haptic feedback
   * Use for: Button press, toggle, checkbox
   */
  function light() {
    vibrate(HAPTIC_PATTERNS.LIGHT)
  }

  /**
   * Medium haptic feedback
   * Use for: Card selection, navigation, menu item
   */
  function medium() {
    vibrate(HAPTIC_PATTERNS.MEDIUM)
  }

  /**
   * Heavy haptic feedback
   * Use for: Important actions, delete, destructive actions
   */
  function heavy() {
    vibrate(HAPTIC_PATTERNS.HEAVY)
  }

  /**
   * Success haptic feedback
   * Use for: Completed action, form submitted, trade executed
   */
  function success() {
    vibrate(HAPTIC_PATTERNS.SUCCESS)
  }

  /**
   * Warning haptic feedback
   * Use for: Warning state, attention needed
   */
  function warning() {
    vibrate(HAPTIC_PATTERNS.WARNING)
  }

  /**
   * Error haptic feedback
   * Use for: Failed action, validation error
   */
  function error() {
    vibrate(HAPTIC_PATTERNS.ERROR)
  }

  /**
   * Selection haptic feedback
   * Use for: Item selection, picker change
   */
  function selection() {
    vibrate(HAPTIC_PATTERNS.SELECTION)
  }

  /**
   * Selection change haptic feedback
   * Use for: Multi-selection, range selection
   */
  function selectionChange() {
    vibrate(HAPTIC_PATTERNS.SELECTION_CHANGE)
  }

  /**
   * Custom pattern vibration
   * @param {number|number[]} pattern - Custom pattern
   */
  function custom(pattern) {
    vibrate(pattern)
  }

  /**
   * Stop any ongoing vibration
   */
  function stop() {
    if (isSupported.value && navigator.vibrate) {
      navigator.vibrate(0)
    }
  }

  return {
    // State
    isSupported,

    // Predefined patterns
    light,
    medium,
    heavy,
    success,
    warning,
    error,
    selection,
    selectionChange,

    // Custom
    custom,
    vibrate,
    stop,

    // Patterns for reference
    patterns: HAPTIC_PATTERNS
  }
}

// Export patterns for direct access
export { HAPTIC_PATTERNS }
