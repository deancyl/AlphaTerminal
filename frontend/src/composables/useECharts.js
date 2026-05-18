/**
 * useECharts.js - Vue composable for memory-safe ECharts usage
 *
 * Provides automatic lifecycle management, built-in resize handling,
 * and memory-safe chart disposal. Use this composable instead of
 * manually managing ECharts instances.
 *
 * @example
 * const { chartRef, initChart, setOption, dispose } = useECharts(containerRef)
 *
 * // In onMounted or setup:
 * initChart({ theme: 'dark' })
 *
 * // Set chart options:
 * setOption({ xAxis: {...}, series: [...] })
 *
 * // Automatic cleanup on component unmount
 */

import { ref, onBeforeUnmount, shallowRef, triggerRef, watch } from 'vue'
import { getECharts } from '../utils/lazyEcharts.js'

/**
 * @typedef {Object} UseEChartsOptions
 * @property {string} [theme='dark'] - Chart theme
 * @property {boolean} [autoResize=true] - Automatically resize on container change
 * @property {number} [resizeDelay=100] - Debounce delay for resize
 * @property {boolean} [lazyInit=false] - Don't initialize until explicitly called
 */

/**
 * Composable for memory-safe ECharts chart management
 *
 * @param {import('vue').Ref<HTMLElement>} containerRef - Ref to chart container element
 * @param {UseEChartsOptions} [options={}] - Configuration options
 * @returns {Object} Chart management API
 */
export function useECharts(containerRef, options = {}) {
  const {
    theme = 'dark',
    autoResize = true,
    resizeDelay = 100,
    lazyInit = false,
  } = options

  // Chart instance - use shallowRef to prevent deep reactivity
  const chartInstance = shallowRef(null)
  const isDisposed = ref(false)
  const isReady = ref(false)

  // ResizeObserver for auto-resize
  let resizeObserver = null
  let resizeTimer = null

  /**
   * Initialize the ECharts instance
   * @param {Object} [initOptions] - Options to pass to echarts.init
   * @returns {Promise<echarts.ECharts|null>} The chart instance or null if failed
   */
  async function initChart(initOptions = {}) {
    if (!containerRef?.value) {
      console.warn('[useECharts] Container element not found')
      return null
    }

    // Dispose existing chart if any
    if (chartInstance.value && !chartInstance.value.isDisposed?.()) {
      chartInstance.value.dispose()
    }

    try {
      const echarts = await getECharts()
      const mergedOptions = { ...initOptions, theme: initOptions.theme || theme }

      chartInstance.value = echarts.init(containerRef.value, mergedOptions.theme, mergedOptions)
      isDisposed.value = false
      isReady.value = true
      triggerRef(chartInstance)

      // Setup auto-resize if enabled
      if (autoResize) {
        setupResizeObserver()
      }

      return chartInstance.value
    } catch (e) {
      console.error('[useECharts] Failed to initialize chart:', e)
      isReady.value = false
      return null
    }
  }

  /**
   * Set chart option
   * @param {Object} option - ECharts option
   * @param {boolean} [notMerge=false] - Whether to not merge with existing option
   */
  function setOption(option, notMerge = false) {
    if (!chartInstance.value || isDisposed.value) {
      console.warn('[useECharts] Cannot setOption: chart is disposed or null')
      return
    }

    try {
      chartInstance.value.setOption(option, notMerge)
    } catch (e) {
      console.error('[useECharts] setOption failed:', e)
    }
  }

  /**
   * Resize the chart
   */
  function resize() {
    if (!chartInstance.value || isDisposed.value) return

    try {
      if (!chartInstance.value.isDisposed?.()) {
        chartInstance.value.resize()
      }
    } catch (e) {
      // Ignore resize errors on disposed charts
    }
  }

  /**
   * Setup ResizeObserver for auto-resize
   */
  function setupResizeObserver() {
    if (!containerRef?.value || !window.ResizeObserver) return

    // Cleanup existing observer
    cleanupResizeObserver()

    const debouncedResize = () => {
      clearTimeout(resizeTimer)
      resizeTimer = setTimeout(() => {
        resize()
      }, resizeDelay)
    }

    resizeObserver = new ResizeObserver(debouncedResize)
    resizeObserver.observe(containerRef.value)
  }

  /**
   * Cleanup ResizeObserver
   */
  function cleanupResizeObserver() {
    if (resizeTimer) {
      clearTimeout(resizeTimer)
      resizeTimer = null
    }

    if (resizeObserver) {
      try {
        resizeObserver.disconnect()
      } catch (e) {
        // Ignore observer disconnect errors
      }
      resizeObserver = null
    }
  }

  /**
   * Dispose the chart and cleanup resources
   */
  function dispose() {
    if (isDisposed.value) return

    // Cleanup ResizeObserver first
    cleanupResizeObserver()

    // Dispose chart
    if (chartInstance.value) {
      try {
        // Check if already disposed before calling dispose
        if (!chartInstance.value.isDisposed?.()) {
          chartInstance.value.dispose()
        }
      } catch (e) {
        // Ignore dispose errors - chart may already be disposed
      }
      chartInstance.value = null
    }

    isDisposed.value = true
    isReady.value = false
    triggerRef(chartInstance)
  }

  /**
   * Update chart data (convenience method)
   * Automatically merges option
   * @param {Object} option - ECharts option with series data
   */
  function updateData(option) {
    setOption(option, false)
  }

  /**
   * Replace chart data (convenience method)
   * Not merges with existing option
   * @param {Object} option - ECharts option with series data
   */
  function replaceData(option) {
    setOption(option, true)
  }

  // Watch for container changes to reinitialize if needed
  watch(containerRef, (newContainer, oldContainer) => {
    if (newContainer && !oldContainer && !lazyInit) {
      initChart()
    }
  })

  // Auto-cleanup on component unmount
  onBeforeUnmount(() => {
    dispose()
  })

  // Return the composable API
  return {
    // State
    chartInstance,
    isReady,
    isDisposed,

    // Methods
    initChart,
    setOption,
    updateData,
    replaceData,
    resize,
    dispose,

    // Utilities
    setupResizeObserver,
    cleanupResizeObserver,
  }
}

/**
 * Create multiple charts managed together
 * Useful for components with multiple charts
 *
 * @param {number} count - Number of charts to create
 * @param {UseEChartsOptions} [options] - Shared options
 * @returns {Object} Manager for multiple charts
 */
export function useMultiECharts(count, options = {}) {
  const charts = Array.from({ length: count }, () => useECharts(ref(null), options))

  function disposeAll() {
    charts.forEach(chart => chart.dispose())
  }

  function resizeAll() {
    charts.forEach(chart => chart.resize())
  }

  return {
    charts,
    disposeAll,
    resizeAll,
  }
}

/**
 * useEChartsChart - Alternative syntax with template ref
 * Use when you want the composable to handle the ref creation
 *
 * @param {UseEChartsOptions} [options] - Configuration options
 * @returns {Object} Same API as useECharts plus containerRef
 *
 * @example
 * const { containerRef, initChart, setOption } = useEChartsChart()
 * // In template: ref="containerRef"
 */
export function useEChartsChart(options = {}) {
  const containerRef = ref(null)

  const chartApi = useECharts(containerRef, options)

  return {
    containerRef,
    ...chartApi,
  }
}

export default useECharts
