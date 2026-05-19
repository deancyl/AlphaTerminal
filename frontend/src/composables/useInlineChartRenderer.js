/**
 * Inline Chart Renderer for Copilot Markdown
 * Renders mini ECharts in markdown stream with proper lifecycle management
 */
import { ref, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { getDynamicThemeColors } from '../utils/echartsTheme.js'

/**
 * Composable for rendering mini charts in markdown
 * @returns {Object} { renderMiniChart, renderCompareChart, disposeAll, disposeChart }
 */
export function useInlineChartRenderer() {
  const chartInstances = ref(new Map())
  const pendingCharts = ref(new Map())

  /**
   * Get chart colors from theme
   */
  function getChartColors() {
    return getDynamicThemeColors()
  }

  /**
   * Render a mini line/area chart
   * @param {string} containerId - DOM element ID
   * @param {Array} data - Array of {date, value} objects
   * @param {Object} options - { type: 'line'|'bar', color: string }
   */
  function renderMiniChart(containerId, data, options = {}) {
    if (!data || data.length === 0) return

    nextTick(() => {
      const container = document.getElementById(containerId)
      if (!container) {
        // Store for later rendering when DOM is ready
        pendingCharts.value.set(containerId, { data, options, type: 'mini' })
        return
      }

      // Clean up existing instance
      disposeChart(containerId)

      const colors = getChartColors()
      const chart = echarts.init(container, null, {
        renderer: 'canvas',
        useDirtyRect: true
      })

      const chartType = options.type || 'line'
      const lineColor = options.color || colors.primary
      const areaColor = options.areaColor || `${lineColor}33`

      const option = {
        animation: false,
        grid: {
          left: 2,
          right: 2,
          top: 2,
          bottom: 2,
          containLabel: false
        },
        xAxis: {
          type: 'category',
          show: false,
          data: data.map(d => d.date || d.label || '')
        },
        yAxis: {
          type: 'value',
          show: false,
          scale: true
        },
        series: [{
          type: chartType,
          data: data.map(d => d.value ?? d.close ?? d.price ?? 0),
          smooth: chartType === 'line',
          symbol: 'none',
          lineStyle: chartType === 'line' ? {
            color: lineColor,
            width: 2
          } : undefined,
          areaStyle: chartType === 'line' ? {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: areaColor },
                { offset: 1, color: 'transparent' }
              ]
            }
          } : undefined,
          itemStyle: chartType === 'bar' ? {
            color: lineColor,
            borderRadius: [2, 2, 0, 0]
          } : undefined,
          barWidth: chartType === 'bar' ? '60%' : undefined
        }]
      }

      chart.setOption(option)
      chartInstances.value.set(containerId, chart)
    })
  }

  /**
   * Render a comparison chart (multiple series)
   * @param {string} containerId - DOM element ID
   * @param {Object} data - { series: [{ name, data: [{date, value}] }], colors: string[] }
   */
  function renderCompareChart(containerId, data) {
    if (!data || !data.series || data.series.length === 0) return

    nextTick(() => {
      const container = document.getElementById(containerId)
      if (!container) {
        pendingCharts.value.set(containerId, { data, type: 'compare' })
        return
      }

      disposeChart(containerId)

      const colors = getChartThemeColors()
      const chart = echarts.init(container, null, {
        renderer: 'canvas',
        useDirtyRect: true
      })

      const seriesColors = data.colors || [colors.primary, colors.bull, colors.bear, '#a855f7', '#f59e0b']

      const series = data.series.map((s, i) => ({
        name: s.name || `Series ${i + 1}`,
        type: 'line',
        data: s.data.map(d => d.value ?? d.close ?? 0),
        smooth: true,
        symbol: 'none',
        lineStyle: {
          color: seriesColors[i % seriesColors.length],
          width: 2
        }
      }))

      const option = {
        animation: false,
        grid: {
          left: 2,
          right: 2,
          top: 20,
          bottom: 2,
          containLabel: false
        },
        legend: {
          show: true,
          top: 0,
          right: 0,
          textStyle: {
            color: colors.axisLabel,
            fontSize: 10
          },
          itemWidth: 12,
          itemHeight: 8
        },
        xAxis: {
          type: 'category',
          show: false,
          data: data.series[0]?.data?.map(d => d.date || '') || []
        },
        yAxis: {
          type: 'value',
          show: false,
          scale: true
        },
        series
      }

      chart.setOption(option)
      chartInstances.value.set(containerId, chart)
    })
  }

  /**
   * Render a candlestick mini chart
   * @param {string} containerId - DOM element ID
   * @param {Array} data - Array of {date, open, high, low, close}
   */
  function renderCandlestickChart(containerId, data) {
    if (!data || data.length === 0) return

    nextTick(() => {
      const container = document.getElementById(containerId)
      if (!container) {
        pendingCharts.value.set(containerId, { data, type: 'candlestick' })
        return
      }

      disposeChart(containerId)

      const colors = getChartColors()
      const chart = echarts.init(container, null, {
        renderer: 'canvas',
        useDirtyRect: true
      })

      const option = {
        animation: false,
        grid: {
          left: 2,
          right: 2,
          top: 2,
          bottom: 2,
          containLabel: false
        },
        xAxis: {
          type: 'category',
          show: false,
          data: data.map(d => d.date || '')
        },
        yAxis: {
          type: 'value',
          show: false,
          scale: true
        },
        series: [{
          type: 'candlestick',
          data: data.map(d => [d.open, d.close, d.low, d.high]),
          itemStyle: {
            color: colors.bull,
            color0: colors.bear,
            borderColor: colors.bull,
            borderColor0: colors.bear
          }
        }]
      }

      chart.setOption(option)
      chartInstances.value.set(containerId, chart)
    })
  }

  /**
   * Dispose a single chart
   * @param {string} containerId - Chart container ID
   */
  function disposeChart(containerId) {
    const chart = chartInstances.value.get(containerId)
    if (chart) {
      try {
        if (!chart.isDisposed()) {
          chart.dispose()
        }
      } catch (e) {
        // Ignore disposal errors
      }
      chartInstances.value.delete(containerId)
    }
    pendingCharts.value.delete(containerId)
  }

  /**
   * Dispose all charts
   */
  function disposeAll() {
    chartInstances.value.forEach((chart) => {
      try {
        if (!chart.isDisposed()) {
          chart.dispose()
        }
      } catch (e) {
      }
    })
    chartInstances.value.clear()
    pendingCharts.value.clear()
  }

  /**
   * Process pending charts (call after DOM updates)
   */
  function processPendingCharts() {
    nextTick(() => {
      pendingCharts.value.forEach((item, containerId) => {
        const container = document.getElementById(containerId)
        if (container) {
          if (item.type === 'mini') {
            renderMiniChart(containerId, item.data, item.options)
          } else if (item.type === 'compare') {
            renderCompareChart(containerId, item.data)
          } else if (item.type === 'candlestick') {
            renderCandlestickChart(containerId, item.data)
          }
        }
      })
    })
  }

  /**
   * Resize all charts
   */
  function resizeAll() {
    chartInstances.value.forEach(chart => {
      try {
        if (!chart.isDisposed()) {
          chart.resize()
        }
      } catch (e) {
        // Ignore resize errors
      }
    })
  }

  // Cleanup on unmount
  onUnmounted(() => {
    disposeAll()
  })

  return {
    renderMiniChart,
    renderCompareChart,
    renderCandlestickChart,
    disposeChart,
    disposeAll,
    processPendingCharts,
    resizeAll
  }
}

/**
 * Parse chart block parameters from markdown
 * @param {string} info - Block info string (e.g., 'chart {type="line" data="kline:sh600519:30d"}')
 * @returns {Object} { type, data, options }
 */
export function parseChartParams(info) {
  const params = { type: 'line', data: '', options: {} }

  // Match: chart {type="line" data="kline:sh600519:30d"}
  const match = info.match(/chart(?:-compare)?(?:-candle)?\s*\{([^}]+)\}/)
  if (!match) return params

  const paramStr = match[1]

  // Parse key="value" pairs
  const pairRegex = /(\w+)="([^"]+)"/g
  let pairMatch
  while ((pairMatch = pairRegex.exec(paramStr)) !== null) {
    const [, key, value] = pairMatch
    if (key === 'type') {
      params.type = value
    } else if (key === 'data') {
      params.data = value
    } else {
      params.options[key] = value
    }
  }

  // Detect chart type from block name
  if (info.startsWith('chart-compare')) {
    params.type = 'compare'
  } else if (info.startsWith('chart-candle')) {
    params.type = 'candlestick'
  }

  return params
}

/**
 * Parse data source string (e.g., "kline:sh600519:30d")
 * @param {string} dataStr - Data source string
 * @returns {Object} { source, symbol, period, metric }
 */
export function parseDataSource(dataStr) {
  if (!dataStr) return { source: '', symbol: '', period: '30d', metric: '' }

  const parts = dataStr.split(':')
  const result = {
    source: parts[0] || '',
    symbol: parts[1] || '',
    period: parts[2] || '30d',
    metric: parts[3] || ''
  }

  return result
}

/**
 * Generate unique chart ID
 * @param {number} index - Block index
 * @returns {string} Unique chart ID
 */
export function generateChartId(index) {
  return `chart-${index}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

/**
 * Get chart theme colors (helper for compare charts)
 */
function getChartThemeColors() {
  return getDynamicThemeColors()
}
