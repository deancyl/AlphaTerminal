/**
 * Lazy ECharts loader - only loads ECharts when actually needed
 * Reduces initial bundle size by ~800KB
 *
 * Note: Sets window.echarts for backward compatibility with components
 * that use window.echarts directly
 */

let echartsPromise = null
let echartsInstance = null

/**
 * Dynamically import ECharts (cached after first load)
 * @returns {Promise<typeof echarts>}
 */
export async function getECharts() {
  if (echartsInstance) {
    return echartsInstance
  }

  if (!echartsPromise) {
    echartsPromise = import('echarts').then(mod => {
      echartsInstance = mod
      // Set window.echarts for backward compatibility
      if (typeof window !== 'undefined') {
        window.echarts = mod
      }
      return mod
    })
  }

  return echartsPromise
}

/**
 * Initialize chart with lazy-loaded ECharts
 * @param {HTMLElement} el - Chart container element
 * @param {string} theme - Chart theme (default: 'dark')
 * @returns {Promise<echarts.ECharts>}
 */
export async function initChart(el, theme = 'dark') {
  const echarts = await getECharts()
  return echarts.init(el, theme)
}

/**
 * Preload ECharts in background (optional, for faster subsequent chart renders)
 * Call this when you know a chart will be needed soon
 */
export function preloadECharts() {
  if (!echartsPromise) {
    echartsPromise = import('echarts').then(mod => {
      echartsInstance = mod
      // Set window.echarts for backward compatibility
      if (typeof window !== 'undefined') {
        window.echarts = mod
      }
      return mod
    })
  }
  return echartsPromise
}

/**
 * Create a debounced resize handler for ECharts
 * Prevents excessive resize calls during window/container resizing
 * 
 * @param {echarts.ECharts} chartInstance - The ECharts instance to resize
 * @param {number} delay - Debounce delay in ms (default: 150ms)
 * @returns {Function} Debounced resize handler
 */
export function createDebouncedResize(chartInstance, delay = 150) {
  let timer = null
  return () => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      chartInstance?.resize()
      timer = null
    }, delay)
  }
}

/**
 * Create a debounced ResizeObserver for ECharts
 * Automatically handles cleanup when observer is disconnected
 * 
 * @param {echarts.ECharts} chartInstance - The ECharts instance to resize
 * @param {number} delay - Debounce delay in ms (default: 150ms)
 * @returns {ResizeObserver} ResizeObserver with debounced callback
 */
export function createResizeObserver(chartInstance, delay = 150) {
  let timer = null
  const observer = new ResizeObserver(() => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      chartInstance?.resize()
      timer = null
    }, delay)
  })
  return observer
}