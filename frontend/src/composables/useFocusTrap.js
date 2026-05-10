/**
 * Focus Trap Composable for Modal Accessibility
 * 
 * Implements WAI-ARIA focus trap pattern:
 * - Tab cycles within modal only
 * - Escape key closes modal
 * - Focus returns to trigger element on close
 * 
 * @param {Object} options
 * @param {import('vue').Ref<boolean>} options.isActive - Whether the modal is visible
 * @param {import('vue').Ref<HTMLElement|null>} options.containerRef - Reference to modal container
 * @param {Function} options.onClose - Callback when Escape is pressed
 * @param {import('vue').Ref<HTMLElement|null>} [options.triggerRef] - Element that triggered the modal (for focus return)
 */
import { onMounted, onUnmounted, watch, nextTick } from 'vue'

export function useFocusTrap(options) {
  const { isActive, containerRef, onClose, triggerRef } = options
  
  let lastFocusedElement = null
  let firstFocusableElement = null
  let lastFocusableElement = null

  // Get all focusable elements within container
  function getFocusableElements(container) {
    if (!container) return []
    
    const selector = [
      'a[href]',
      'button:not([disabled])',
      'input:not([disabled])',
      'select:not([disabled])',
      'textarea:not([disabled])',
      '[tabindex]:not([tabindex="-1"])'
    ].join(', ')
    
    return Array.from(container.querySelectorAll(selector))
      .filter(el => el.offsetParent !== null) // Filter out hidden elements
  }

  // Update first/last focusable elements
  function updateFocusableElements() {
    if (!containerRef.value) return
    
    const focusableElements = getFocusableElements(containerRef.value)
    
    if (focusableElements.length > 0) {
      firstFocusableElement = focusableElements[0]
      lastFocusableElement = focusableElements[focusableElements.length - 1]
    } else {
      firstFocusableElement = null
      lastFocusableElement = null
    }
  }

  // Handle Tab key to trap focus within modal
  function handleKeyDown(event) {
    if (!isActive.value || event.key !== 'Tab') return
    
    updateFocusableElements()
    
    if (!firstFocusableElement || !lastFocusableElement) {
      event.preventDefault()
      return
    }

    if (event.shiftKey) {
      // Shift+Tab: moving backwards
      if (document.activeElement === firstFocusableElement) {
        event.preventDefault()
        lastFocusableElement.focus()
      }
    } else {
      // Tab: moving forwards
      if (document.activeElement === lastFocusableElement) {
        event.preventDefault()
        firstFocusableElement.focus()
      }
    }
  }

  // Handle Escape key to close modal
  function handleEscape(event) {
    if (!isActive.value || event.key !== 'Escape') return
    if (onClose) onClose()
  }

  // Trap focus when modal opens
  async function trapFocus() {
    await nextTick()
    
    // Store the currently focused element (trigger)
    lastFocusedElement = document.activeElement
    
    updateFocusableElements()
    
    // Focus the first focusable element or the container itself
    if (firstFocusableElement) {
      firstFocusableElement.focus()
    } else if (containerRef.value) {
      // If no focusable elements, make container focusable and focus it
      containerRef.value.setAttribute('tabindex', '-1')
      containerRef.value.focus()
    }
  }

  // Restore focus when modal closes
  function restoreFocus() {
    // Return focus to the trigger element or the last focused element
    const elementToFocus = triggerRef?.value || lastFocusedElement
    if (elementToFocus && typeof elementToFocus.focus === 'function') {
      elementToFocus.focus()
    }
    lastFocusedElement = null
  }

  // Watch for modal visibility changes
  watch(isActive, async (active) => {
    if (active) {
      await trapFocus()
    } else {
      restoreFocus()
    }
  })

  // Add event listeners
  onMounted(() => {
    document.addEventListener('keydown', handleKeyDown)
    document.addEventListener('keydown', handleEscape)
    
    // If modal is already active on mount, trap focus
    if (isActive.value) {
      trapFocus()
    }
  })

  // Cleanup event listeners
  onUnmounted(() => {
    document.removeEventListener('keydown', handleKeyDown)
    document.removeEventListener('keydown', handleEscape)
  })

  return {
    updateFocusableElements,
    trapFocus,
    restoreFocus
  }
}
