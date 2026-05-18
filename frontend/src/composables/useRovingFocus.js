/**
 * useRovingFocus.js — Roving Tabindex Pattern for Grid Navigation
 * 
 * Implements WCAG 2.1 compliant keyboard navigation:
 * - Arrow keys (up/down/left/right) for grid navigation
 * - Home/End keys for first/last item
 * - Only one element has tabindex="0" at a time (roving tabindex)
 * - Enter/Space triggers click action
 * 
 * @see https://www.w3.org/WAI/ARIA/apg/patterns/grid/
 */
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'

/**
 * Creates a roving focus manager for grid-based navigation
 * 
 * @param {Object} options
 * @param {import('vue').Ref<HTMLElement|null>} options.containerRef - Reference to the grid container
 * @param {import('vue').Ref<any[]>} options.items - Reactive array of items to navigate
 * @param {number} [options.columns=2] - Number of columns in the grid
 * @param {Function} [options.onSelect] - Callback when item is selected (Enter/Space)
 * @param {string} [options.itemSelector='[data-wind-card]'] - Selector for focusable items
 */
export function useRovingFocus(options) {
  const {
    containerRef,
    items,
    columns = 2,
    onSelect,
    itemSelector = '[data-wind-card]'
  } = options

  // Current focused index (0-based)
  const currentIndex = ref(0)
  
  // Track if we're in keyboard navigation mode
  const isKeyboardMode = ref(false)

  /**
   * Get all focusable card elements in the container
   */
  function getCardElements() {
    if (!containerRef.value) return []
    return Array.from(containerRef.value.querySelectorAll(itemSelector))
  }

  /**
   * Update tabindex on all cards - only current card has tabindex="0"
   */
  function updateTabindices() {
    const cards = getCardElements()
    cards.forEach((card, index) => {
      if (index === currentIndex.value) {
        card.setAttribute('tabindex', '0')
      } else {
        card.setAttribute('tabindex', '-1')
      }
    })
  }

  /**
   * Focus the card at the given index
   */
  async function focusCard(index) {
    const cards = getCardElements()
    if (index < 0 || index >= cards.length) return
    
    currentIndex.value = index
    await nextTick()
    updateTabindices()
    
    const card = cards[index]
    if (card) {
      card.focus()
    }
  }

  /**
   * Get the total number of items
   */
  const itemCount = computed(() => items.value?.length || 0)

  /**
   * Calculate new index for arrow key navigation
   */
  function getNewIndex(key) {
    const total = itemCount.value
    if (total === 0) return 0
    
    const current = currentIndex.value
    const cols = columns
    const rows = Math.ceil(total / cols)
    const currentRow = Math.floor(current / cols)
    const currentCol = current % cols

    switch (key) {
      case 'ArrowRight': {
        // Move right, wrap to next row if at end
        const next = current + 1
        return next >= total ? 0 : next
      }
      
      case 'ArrowLeft': {
        // Move left, wrap to previous row if at start
        const prev = current - 1
        return prev < 0 ? total - 1 : prev
      }
      
      case 'ArrowDown': {
        // Move down one row
        const nextRow = currentRow + 1
        if (nextRow >= rows) {
          // At last row, go to first row same column
          return currentCol
        }
        const downIndex = current + cols
        // Check if target position exists (might be in last row with fewer items)
        return downIndex >= total ? currentCol : downIndex
      }
      
      case 'ArrowUp': {
        // Move up one row
        const prevRow = currentRow - 1
        if (prevRow < 0) {
          // At first row, go to last row same column
          const lastRowStart = (rows - 1) * cols
          const targetIndex = lastRowStart + currentCol
          // Check if target exists in last row
          return targetIndex >= total ? lastRowStart : targetIndex
        }
        return current - cols
      }
      
      case 'Home': {
        // Go to first item
        return 0
      }
      
      case 'End': {
        // Go to last item
        return total - 1
      }
      
      default:
        return current
    }
  }

  /**
   * Handle keyboard events on the grid container
   */
  function handleKeydown(event) {
    const navigationKeys = ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Home', 'End']
    
    if (!navigationKeys.includes(event.key) && event.key !== 'Enter' && event.key !== ' ') {
      return
    }

    // Enter/Space triggers selection
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      if (onSelect && items.value[currentIndex.value]) {
        onSelect(items.value[currentIndex.value])
      }
      return
    }

    // Navigation keys
    if (navigationKeys.includes(event.key)) {
      event.preventDefault()
      isKeyboardMode.value = true
      
      const newIndex = getNewIndex(event.key)
      focusCard(newIndex)
    }
  }

  /**
   * Handle click on a card - update focus index
   */
  function handleCardClick(index) {
    currentIndex.value = index
    isKeyboardMode.value = false
    updateTabindices()
  }

  /**
   * Handle focus entering the grid
   */
  function handleFocusIn(event) {
    const cards = getCardElements()
    const targetIndex = cards.indexOf(event.target)
    
    if (targetIndex !== -1 && targetIndex !== currentIndex.value) {
      currentIndex.value = targetIndex
      updateTabindices()
    }
  }

  /**
   * Handle mouse click to exit keyboard mode
   */
  function handleMouseDown() {
    isKeyboardMode.value = false
  }

  /**
   * Reset focus to first item
   */
  function reset() {
    currentIndex.value = 0
    updateTabindices()
  }

  /**
   * Focus the grid (first focusable item)
   */
  async function focus() {
    await nextTick()
    const cards = getCardElements()
    if (cards.length > 0) {
      cards[0].focus()
    }
  }

  // Set up event listeners
  onMounted(() => {
    if (containerRef.value) {
      containerRef.value.addEventListener('keydown', handleKeydown)
      containerRef.value.addEventListener('focusin', handleFocusIn)
      containerRef.value.addEventListener('mousedown', handleMouseDown)
    }
    updateTabindices()
  })

  // Clean up event listeners
  onUnmounted(() => {
    if (containerRef.value) {
      containerRef.value.removeEventListener('keydown', handleKeydown)
      containerRef.value.removeEventListener('focusin', handleFocusIn)
      containerRef.value.removeEventListener('mousedown', handleMouseDown)
    }
  })

  return {
    currentIndex,
    isKeyboardMode,
    itemCount,
    focusCard,
    reset,
    focus,
    handleCardClick,
    handleKeydown,
    updateTabindices,
    getCardProps: (index) => ({
      'data-wind-card': '',
      'tabindex': index === currentIndex.value ? '0' : '-1',
      'role': 'button',
      'aria-label': items.value[index]?.name || `Card ${index + 1}`
    })
  }
}
