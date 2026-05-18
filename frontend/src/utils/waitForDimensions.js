/**
 * Wait for element to have non-zero dimensions
 * 
 * This utility solves the "black screen on fullscreen" issue by ensuring
 * the container element has valid dimensions before initializing charts.
 * 
 * @param {HTMLElement} el - Element to wait for
 * @param {number} timeout - Maximum wait time in ms (default 1000)
 * @param {Object} options - Additional options
 * @param {number} options.minWidth - Minimum width to wait for (default 100)
 * @param {number} options.minHeight - Minimum height to wait for (default 100)
 * @returns {Promise<{success: boolean, width: number, height: number}>}
 * 
 * @example
 * // Basic usage
 * const result = await waitForDimensions(containerRef.value)
 * if (!result.success) {
 *   console.warn('Using fallback dimensions')
 * }
 * chart.resize(result.width, result.height)
 * 
 * @example
 * // With custom timeout and minimum dimensions
 * const result = await waitForDimensions(el, 2000, { minWidth: 200, minHeight: 150 })
 * 
 * @example
 * // In Vue component
 * const containerRef = ref(null)
 * onMounted(async () => {
 *   const { success, width, height } = await waitForDimensions(containerRef.value)
 *   if (width > 0 && height > 0) {
 *     initChart(width, height)
 *   }
 * })
 */
export async function waitForDimensions(el, timeout = 1000, options = {}) {
  const { minWidth = 100, minHeight = 100 } = options
  const start = performance.now()
  
  if (!el) {
    console.warn('[waitForDimensions] Element is null/undefined, using fallback dimensions')
    return {
      success: false,
      width: minWidth,
      height: minHeight
    }
  }
  
  while (el.clientWidth < minWidth || el.clientHeight < minHeight) {
    if (performance.now() - start > timeout) {
      const currentWidth = el.clientWidth || 0
      const currentHeight = el.clientHeight || 0
      console.warn(
        `[waitForDimensions] Timeout after ${timeout}ms, ` +
        `dimensions: ${currentWidth}x${currentHeight}, ` +
        `falling back to ${minWidth}x${minHeight}`
      )
      return {
        success: false,
        width: currentWidth || minWidth,
        height: currentHeight || minHeight
      }
    }
    
    await new Promise(resolve => requestAnimationFrame(resolve))
  }
  
  return {
    success: true,
    width: el.clientWidth,
    height: el.clientHeight
  }
}

/**
 * Synchronous version for cases where async is not possible
 * Returns current dimensions or fallback if invalid
 * 
 * @param {HTMLElement} el - Element to check
 * @param {Object} options - Additional options
 * @param {number} options.minWidth - Minimum width (default 100)
 * @param {number} options.minHeight - Minimum height (default 100)
 * @returns {{valid: boolean, width: number, height: number}}
 */
export function getDimensionsOrFallback(el, options = {}) {
  const { minWidth = 100, minHeight = 100 } = options
  
  if (!el) {
    return { valid: false, width: minWidth, height: minHeight }
  }
  
  const width = el.clientWidth || 0
  const height = el.clientHeight || 0
  const valid = width >= minWidth && height >= minHeight
  
  return {
    valid,
    width: valid ? width : minWidth,
    height: valid ? height : minHeight
  }
}
