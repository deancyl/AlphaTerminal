import { computed } from 'vue'

/**
 * Composable for price/value indicator styling
 * Returns appropriate color classes based on positive/negative values
 * 
 * @param {Ref<number>|number} value - The value to check (reactive or static)
 * @returns {Object} - Computed color classes
 */
export function usePriceIndicator(value) {
  const colorClass = computed(() => {
    const val = typeof value === 'object' ? value.value : value
    if (val == null || val === 0) return 'text-gray-400'
    return val > 0 ? 'text-market-up' : 'text-market-down'
  })
  
  const bgColorClass = computed(() => {
    const val = typeof value === 'object' ? value.value : value
    if (val == null || val === 0) return 'bg-gray-500/10'
    return val > 0 ? 'bg-market-up/10' : 'bg-market-down/10'
  })
  
  const borderColorClass = computed(() => {
    const val = typeof value === 'object' ? value.value : value
    if (val == null || val === 0) return 'border-gray-500/30'
    return val > 0 ? 'border-market-up/30' : 'border-market-down/30'
  })
  
  const arrow = computed(() => {
    const val = typeof value === 'object' ? value.value : value
    if (val == null || val === 0) return ''
    return val > 0 ? '↑' : '↓'
  })
  
  const sign = computed(() => {
    const val = typeof value === 'object' ? value.value : value
    if (val == null || val === 0) return ''
    return val > 0 ? '+' : ''
  })
  
  return {
    colorClass,
    bgColorClass,
    borderColorClass,
    arrow,
    sign
  }
}

/**
 * Get price indicator classes for a static value
 * @param {number} value - The value to check
 * @returns {Object} - Color classes
 */
export function getPriceIndicatorClasses(value) {
  if (value == null || value === 0) {
    return {
      colorClass: 'text-gray-400',
      bgColorClass: 'bg-gray-500/10',
      borderColorClass: 'border-gray-500/30',
      arrow: '',
      sign: ''
    }
  }
  
  const isPositive = value > 0
  return {
    colorClass: isPositive ? 'text-market-up' : 'text-market-down',
    bgColorClass: isPositive ? 'bg-market-up/10' : 'bg-market-down/10',
    borderColorClass: isPositive ? 'border-market-up/30' : 'border-market-down/30',
    arrow: isPositive ? '↑' : '↓',
    sign: isPositive ? '+' : ''
  }
}

/**
 * Format a percentage change with sign and appropriate styling
 * @param {number} value - The percentage value
 * @param {number} decimals - Number of decimal places (default: 2)
 * @returns {string} - Formatted string with sign
 */
export function formatChange(value, decimals = 2) {
  if (value == null) return '--'
  const sign = value >= 0 ? '+' : ''
  return `${sign}${value.toFixed(decimals)}%`
}
