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
import * as echarts from 'echarts'

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

const chartRef = ref(null)
let chartInstance = null
let resizeObserver = null

function buildOption() {
  const tc = getChartColors()
  const chartColor = props.color || tc.accentPrimary
  
  if (!props.data || props.data.length === 0) {
    return null
  }

  const dates = props.data.map(d => d.date || d.time || '')
  const values = props.data.map(d => d.value || d.close || 0)

  const series = {
    name: props.title || '数据',
    type: props.type,
    data: values,
    smooth: props.type === 'line' ? 0.3 : false,
    symbol: 'none',
    lineStyle: {
      color: chartColor,
      width: 2
    }
  }

  // Line chart with area
  if (props.type === 'line' && props.showArea) {
    series.areaStyle = {
      color: {
        type: 'linear',
        x: 0,
        y: 0,
        x2: 0,
        y2: 1,
        colorStops: [
          { offset: 0, color: chartColor + '40' },
          { offset: 1, color: chartColor + '00' }
        ]
      }
    }
  }

  // Bar chart colors
  if (props.type === 'bar') {
    series.itemStyle = {
      color: chartColor + '80',
      borderColor: chartColor,
      borderWidth: 1
    }
    series.barMaxWidth = 20
  }

  return {
    backgroundColor: 'transparent',
    grid: {
      top: 10,
      right: 10,
      bottom: 30,
      left: 50
    },
    xAxis: {
      type: 'category',
      data: dates,
      boundaryGap: props.type === 'bar',
      axisLine: {
        lineStyle: { color: tc.borderPrimary }
      },
      axisLabel: {
        color: tc.chartText,
        fontSize: 10,
        interval: Math.max(0, Math.floor(dates.length / 6) - 1)
      },
      splitLine: { show: false }
    },
    yAxis: {
      type: 'value',
      scale: true,
      axisLine: { show: false },
      axisLabel: {
        color: tc.chartText,
        fontSize: 10,
        formatter: v => v.toFixed(1)
      },
      splitLine: {
        lineStyle: {
          color: tc.chartGrid,
          type: 'dashed'
        }
      }
    },
    series: [series],
    tooltip: {
      trigger: 'axis',
      backgroundColor: tc.tooltipBg,
      borderColor: tc.borderPrimary,
      textStyle: {
        color: tc.textSecondary,
        fontSize: 11
      },
      formatter: (params) => {
        if (!params || !params[0]) return ''
        const p = params[0]
        return `<span style="color:${tc.chartText};font-size:10px">${p.axisValue}</span><br/>
                <span style="color:${chartColor};font-size:11px">${p.value.toFixed(2)}</span>`
      }
    }
  }
}

function renderChart() {
  if (!chartRef.value) return

  const option = buildOption()
  if (!option) {
    if (chartInstance) {
      chartInstance.clear()
    }
    return
  }

  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value, null, { renderer: 'canvas' })
  }

  chartInstance.clear()
  chartInstance.setOption(option, { notMerge: true })
}

watch(() => [props.data, props.type, props.color], () => {
  renderChart()
}, { deep: true })

let unsubscribeTheme = null

onMounted(() => {
  if (chartRef.value) {
    chartInstance = echarts.init(chartRef.value, null, { renderer: 'canvas' })
    resizeObserver = new ResizeObserver(() => chartInstance?.resize())
    resizeObserver.observe(chartRef.value)
    renderChart()
  }
  unsubscribeTheme = onThemeChange(() => {
    renderChart()
  })
})

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
