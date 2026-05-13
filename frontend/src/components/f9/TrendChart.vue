<!--
  TrendChart.vue - ECharts Trend Chart Wrapper Component
  
  A reusable chart component for displaying time-series data with line or bar visualization.
  Automatically adapts to theme changes and supports responsive resizing.
  
  USAGE EXAMPLE:
  ```vue
  <TrendChart
    :data="[
      { date: '2024-01', value: 100 },
      { date: '2024-02', value: 120 },
      { date: '2024-03', value: 95 }
    ]"
    type="line"
    title="Revenue Trend"
    color="#3b82f6"
    :showArea="true"
  />
  ```
  
  PROPS:
  - data: Array of data points. Each point should have:
    * date (or time): String - X-axis label (e.g., '2024-01-01')
    * value (or close): Number - Y-axis value
  - type: 'line' | 'bar' - Chart type (default: 'line')
  - title: String - Chart title displayed above the chart
  - color: String - Custom color (hex format). If empty, uses theme accent color
  - showArea: Boolean - For line charts, show filled area gradient (default: true)
  
  FEATURES:
  - Theme-aware: Automatically updates colors on theme change
  - Responsive: Uses ResizeObserver to handle container size changes
  - Lazy loading: ECharts loaded on-demand via lazyEcharts.js
  - Gradient area: Line charts show gradient fill from color to transparent
  - Smart axis labels: X-axis labels auto-adjust based on data density
-->
<template>
  <div class="trend-chart w-full h-full min-h-[200px] relative">
    <div v-if="title" class="text-sm font-bold text-terminal-primary mb-2 px-2">
      {{ title }}
    </div>
    <div ref="chartRef" class="w-full h-full"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { getChartColors, onThemeChange } from '../../composables/useTheme.js'
import { getECharts, initChart, createResizeObserver } from '../../utils/lazyEcharts.js'

/**
 * Component props definition
 * @property {Array} data - Time-series data points [{ date/time, value/close }, ...]
 * @property {string} type - Chart type: 'line' or 'bar'
 * @property {string} title - Chart title text
 * @property {string} color - Custom color (hex), empty = theme color
 * @property {boolean} showArea - Show gradient area fill for line charts
 */
const props = defineProps({
  data: {
    type: Array,
    default: () => []
    // Format: [{ date: '2024-01-01', value: 100 }, ...]
  },
  type: {
    type: String,
    default: 'line' // 'line' | 'bar'
  },
  title: {
    type: String,
    default: ''
  },
  color: {
    type: String,
    default: '' // Custom color, or use theme color
  },
  showArea: {
    type: Boolean,
    default: true
  }
})

// DOM reference for chart container
const chartRef = ref(null)
// ECharts instance (not reactive for performance)
let chartInstance = null
// ResizeObserver for responsive chart
let resizeObserver = null

/**
 * Build ECharts configuration object
 * Creates complete chart options based on props and theme colors
 * 
 * @returns {Object|null} ECharts option object, or null if no data
 */
function buildOption() {
  // Get current theme colors
  const tc = getChartColors()
  // Use custom color or fallback to theme accent
  const chartColor = props.color || tc.accentPrimary
  
  // Return null if no data to display
  if (!props.data || props.data.length === 0) {
    return null
  }

  // Extract dates and values from data
  // Supports both 'date'/'time' and 'value'/'close' property names
  const dates = props.data.map(d => d.date || d.time || '')
  const values = props.data.map(d => d.value || d.close || 0)

  // Base series configuration
  const series = {
    name: props.title || '数据',
    type: props.type,
    data: values,
    smooth: props.type === 'line' ? 0.3 : false, // Smooth line for line charts
    symbol: 'none', // Hide data point markers
    lineStyle: {
      color: chartColor,
      width: 2
    }
  }

  // Add gradient area fill for line charts
  // Creates a vertical gradient from color (40% opacity) to transparent
  if (props.type === 'line' && props.showArea) {
    series.areaStyle = {
      color: {
        type: 'linear',
        x: 0,
        y: 0,
        x2: 0,
        y2: 1,
        colorStops: [
          { offset: 0, color: chartColor + '40' },  // 25% opacity at top
          { offset: 1, color: chartColor + '00' }   // 0% opacity at bottom
        ]
      }
    }
  }

  // Bar chart specific styling
  // Semi-transparent fill with solid border
  if (props.type === 'bar') {
    series.itemStyle = {
      color: chartColor + '80',  // 50% opacity fill
      borderColor: chartColor,
      borderWidth: 1
    }
    series.barMaxWidth = 20  // Prevent bars from being too wide
  }

  // Return complete ECharts configuration
  return {
    backgroundColor: 'transparent',
    // Chart grid with padding for labels
    grid: {
      top: 10,
      right: 10,
      bottom: 30,
      left: 50
    },
    // X-axis configuration (category/time axis)
    xAxis: {
      type: 'category',
      data: dates,
      boundaryGap: props.type === 'bar', // Center bars, align lines to ticks
      axisLine: {
        lineStyle: { color: tc.borderPrimary }
      },
      axisLabel: {
        color: tc.chartText,
        fontSize: 10,
        // Show ~6 labels regardless of data density
        interval: Math.max(0, Math.floor(dates.length / 6) - 1)
      },
      splitLine: { show: false }
    },
    // Y-axis configuration (value axis)
    yAxis: {
      type: 'value',
      scale: true, // Auto-scale to data range
      axisLine: { show: false },
      axisLabel: {
        color: tc.chartText,
        fontSize: 10,
        formatter: v => v.toFixed(1) // 1 decimal place
      },
      splitLine: {
        lineStyle: {
          color: tc.chartGrid,
          type: 'dashed'
        }
      }
    },
    series: [series],
    // Tooltip configuration
    tooltip: {
      trigger: 'axis', // Show tooltip for entire axis
      backgroundColor: tc.tooltipBg,
      borderColor: tc.borderPrimary,
      textStyle: {
        color: tc.textSecondary,
        fontSize: 11
      },
      // Custom tooltip formatter
      formatter: (params) => {
        if (!params || !params[0]) return ''
        const p = params[0]
        return `<span style="color:${tc.chartText};font-size:10px">${p.axisValue}</span><br/>
                <span style="color:${chartColor};font-size:11px">${p.value.toFixed(2)}</span>`
      }
    }
  }
}

/**
 * Render or update the chart
 * Initializes ECharts instance if needed and applies new options
 */
async function renderChart() {
  if (!chartRef.value) return

  const option = buildOption()
  // Clear chart if no data
  if (!option) {
    if (chartInstance) {
      chartInstance.clear()
    }
    return
  }

  // Initialize chart instance on first render
  if (!chartInstance) {
    chartInstance = await initChart(chartRef.value)
  }

  // Apply new options (notMerge: true = replace all options)
  chartInstance.clear()
  chartInstance.setOption(option, { notMerge: true })
}

// Watch for prop changes and re-render
// Deep watch to detect array/object mutations
watch(() => [props.data, props.type, props.color], () => {
  renderChart()
}, { deep: true })

// Theme change subscription (cleaned up on unmount)
let unsubscribeTheme = null

/**
 * Lifecycle: Mount
 * - Initialize chart instance
 * - Set up ResizeObserver for responsive resizing
 * - Subscribe to theme changes
 */
onMounted(async () => {
  if (chartRef.value) {
    chartInstance = await initChart(chartRef.value)
    resizeObserver = createResizeObserver(chartInstance)
    resizeObserver.observe(chartRef.value)
    renderChart()
  }
  // Re-render chart when theme changes
  unsubscribeTheme = onThemeChange(() => {
    renderChart()
  })
})

/**
 * Lifecycle: Unmount
 * - Disconnect ResizeObserver
 * - Dispose ECharts instance to prevent memory leaks
 * - Unsubscribe from theme changes
 */
onUnmounted(() => {
  resizeObserver?.disconnect()
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
  unsubscribeTheme?.()
  unsubscribeTheme = null
})
</script>

<style scoped>
.trend-chart {
  background: transparent;
}
</style>
