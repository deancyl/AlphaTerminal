import { onUnmounted } from 'vue'

const logger = {
  error: (...args) => console.error('[ChartManager]', ...args),
  warn: (...args) => console.warn('[ChartManager]', ...args),
  info: (...args) => console.info('[ChartManager]', ...args),
}

class ChartManager {
  constructor() {
    this.charts = new Map()
    this.observers = new Map()
    this.debouncers = new Map()
  }

  register(id, chartInstance, domElement, options = {}) {
    const { resizeDelay = 100, autoResize = true } = options

    if (this.charts.has(id)) {
      this.dispose(id)
    }

    this.charts.set(id, chartInstance)

    if (autoResize && domElement) {
      this.setupResizeObserver(id, chartInstance, domElement, resizeDelay)
    }

    return chartInstance
  }

  setupResizeObserver(id, chartInstance, domElement, delay) {
    if (!window.ResizeObserver) {
      logger.warn('ResizeObserver not available')
      return
    }

    let resizeTimer = null
    const debouncedResize = () => {
      clearTimeout(resizeTimer)
      resizeTimer = setTimeout(() => {
        try {
          if (chartInstance && !chartInstance.isDisposed?.()) {
            chartInstance.resize()
          }
        } catch (e) {
          // Ignore resize errors on disposed charts
        }
      }, delay)
    }

    const observer = new ResizeObserver(debouncedResize)
    observer.observe(domElement)

    this.observers.set(id, observer)
    this.debouncers.set(id, resizeTimer)
  }

  get(id) {
    return this.charts.get(id)
  }

  has(id) {
    return this.charts.has(id)
  }

  isDisposed(id) {
    const chart = this.charts.get(id)
    if (!chart) return true
    return chart.isDisposed?.() ?? false
  }

  resize(id) {
    const chart = this.charts.get(id)
    if (chart && !chart.isDisposed?.()) {
      try {
        chart.resize()
      } catch (e) {
        logger.warn(`Resize failed for ${id}:`, e.message)
      }
    }
  }

  resizeAll() {
    this.charts.forEach((_, id) => {
      this.resize(id)
    })
  }

  setOption(id, option, notMerge = false) {
    const chart = this.charts.get(id)
    if (chart && !chart.isDisposed?.()) {
      try {
        chart.setOption(option, notMerge)
      } catch (e) {
        logger.error(`setOption failed for ${id}:`, e.message)
      }
    }
  }

  dispose(id) {
    const observer = this.observers.get(id)
    if (observer) {
      try {
        observer.disconnect()
      } catch (e) {
        // Ignore disconnect errors
      }
      this.observers.delete(id)
    }

    const timer = this.debouncers.get(id)
    if (timer) {
      clearTimeout(timer)
      this.debouncers.delete(id)
    }

    const chart = this.charts.get(id)
    if (chart) {
      try {
        if (!chart.isDisposed?.()) {
          chart.dispose()
        }
      } catch (e) {
        // Ignore dispose errors
      }
      this.charts.delete(id)
    }
  }

  disposeAll() {
    this.observers.forEach((observer) => {
      try {
        observer.disconnect()
      } catch (e) {
        // Ignore disconnect errors
      }
    })
    this.observers.clear()

    this.debouncers.forEach((timer) => {
      clearTimeout(timer)
    })
    this.debouncers.clear()

    this.charts.forEach((chart) => {
      try {
        if (!chart.isDisposed?.()) {
          chart.dispose()
        }
      } catch (e) {
        // Ignore dispose errors
      }
    })
    this.charts.clear()
  }

  getStats() {
    return {
      chartCount: this.charts.size,
      observerCount: this.observers.size,
      ids: Array.from(this.charts.keys()),
    }
  }
}

export function createChartManager() {
  return new ChartManager()
}

export function safeDispose(chartInstance) {
  if (!chartInstance) return

  try {
    if (!chartInstance.isDisposed?.()) {
      chartInstance.dispose()
    }
  } catch (e) {
    // Ignore dispose errors
  }
}

export function safeResize(chartInstance) {
  if (!chartInstance) return

  try {
    if (!chartInstance.isDisposed?.()) {
      chartInstance.resize()
    }
  } catch (e) {
    // Ignore resize errors
  }
}

export function safeSetOption(chartInstance, option, notMerge = false) {
  if (!chartInstance) return

  try {
    if (!chartInstance.isDisposed?.()) {
      chartInstance.setOption(option, notMerge)
    }
  } catch (e) {
    // Ignore setOption errors
  }
}

export function initChart(echarts, domElement, theme, opts) {
  if (!echarts || !domElement) {
    logger.warn('Cannot init chart: missing echarts or domElement')
    return null
  }

  try {
    return echarts.init(domElement, theme, opts)
  } catch (e) {
    logger.error('Failed to init chart:', e.message)
    return null
  }
}

export function reinitChartIfNeeded(chartInstance, domElement, echarts) {
  if (!domElement) return { needsReinit: false, chart: chartInstance }

  if (!chartInstance) {
    return { needsReinit: true, chart: echarts.init(domElement) }
  }

  try {
    const currentDom = chartInstance.getDom?.()
    if (currentDom !== domElement) {
      safeDispose(chartInstance)
      return { needsReinit: true, chart: echarts.init(domElement) }
    }
  } catch (e) {
    return { needsReinit: true, chart: echarts.init(domElement) }
  }

  return { needsReinit: false, chart: chartInstance }
}

export const globalChartManager = new ChartManager()

export function useChartManager() {
  const manager = new ChartManager()

  onUnmounted(() => {
    manager.disposeAll()
  })

  return manager
}

export function useChartResizeObserver(chartRef, chartInstance, delay = 100) {
  let observer = null
  let resizeTimer = null

  const setup = () => {
    if (!chartRef?.value || !chartInstance?.value) return

    const debouncedResize = () => {
      clearTimeout(resizeTimer)
      resizeTimer = setTimeout(() => {
        safeResize(chartInstance.value)
      }, delay)
    }

    observer = new ResizeObserver(debouncedResize)
    observer.observe(chartRef.value)
  }

  const cleanup = () => {
    if (resizeTimer) {
      clearTimeout(resizeTimer)
      resizeTimer = null
    }
    if (observer) {
      try {
        observer.disconnect()
      } catch (e) {
        // Ignore disconnect errors
      }
      observer = null
    }
  }

  onUnmounted(() => {
    cleanup()
  })

  return { setup, cleanup }
}
