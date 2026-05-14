<template>
  <div ref="lazyRef" class="w-full h-full" style="min-height:120px">
    <div class="topbar">期货主力合约</div>
    <div v-if="!isVisible" class="chart-area flex flex-col p-3 gap-2">
      <div class="skeleton h-3 w-24 rounded-sm"></div>
      <div class="flex-1 skeleton rounded-sm"></div>
    </div>
    <div v-else ref="chartRef" class="chart-area"></div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import { useLazyLoad } from '../composables/useLazyLoad.js'
import { createResizeObserver } from '../utils/lazyEcharts.js'

const props = defineProps({
  futuresData: { type: Array, default: () => [] },
})

const { isVisible, containerRef: lazyRef } = useLazyLoad({ threshold: 0.1, rootMargin: '50px' })
const chartRef    = ref(null)
const hasData     = ref(false)
let chartInstance = null

function fmt(v) {
  if (v == null) return '--'
  return Number(v).toFixed(2)
}

function buildChart() {
  if (!chartRef.value || !window.echarts) return
  if (chartInstance) { chartInstance.dispose(); chartInstance = null }

  const data = props.futuresData
  hasData.value = data.length > 0
  if (!hasData.value) return

  chartInstance = window.echarts.init(chartRef.value, null, { renderer: 'canvas' })

  const symbols = data.map(d => d.symbol)
  const categories = Array.from({ length: 20 }, (_, i) => {
    const d = new Date()
    d.setDate(d.getDate() - (19 - i))
    return (d.getMonth() + 1) + '/' + d.getDate()
  })

  const series = data.map(fut => {
    const base = fut.price || 0
    const chg  = fut.change_pct || 0
    const color = chg >= 0 ? '#f87171' : '#4ade80'
    
    // Use real history if available, fallback to flat line
    let history = []
    if (fut.history && fut.history.length > 0) {
      history = fut.history.slice(-20).map(bar => bar.close)
    } else {
      // Fallback: flat line at current price
      history = Array(20).fill(base)
    }
    
    return {
      name: fut.name || fut.symbol,
      type: 'line',
      data: history,
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 2, color },
    }
  })

  chartInstance.setOption({
    backgroundColor: 'transparent',
    grid: { top: 16, right: 16, bottom: 28, left: 56 },
    legend: {
      show: true, top: 2, right: 8,
      textStyle: { color: '#9ca3af', fontSize: 9, fontFamily: 'monospace' },
      itemWidth: 12, itemHeight: 2,
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(10,14,23,0.95)',
      borderColor: 'rgba(50,50,50,0.8)',
      textStyle: { color: '#9ca3af', fontSize: 11, fontFamily: 'monospace' },
    },
    xAxis: {
      type: 'category', data: categories,
      axisLine: { lineStyle: { color: '#2d2d2d' } },
      axisTick: { show: false },
      axisLabel: { color: '#6b7280', fontSize: 9, fontFamily: 'monospace', interval: 4 },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value', scale: true,
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: '#6b7280', fontSize: 9, fontFamily: 'monospace' },
      splitLine: { lineStyle: { color: '#1f1f1f', type: 'dashed' } },
    },
    series,
  }, true)
}

async function init() { await nextTick(); buildChart() }

const debouncedInit = useDebounceFn(init, 300)

let ro = null
onMounted(() => {
  if (chartRef.value) { ro = createResizeObserver(chartInstance); ro.observe(chartRef.value) }
})
onUnmounted(() => {
  ro && ro.disconnect()
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})
watch([() => props.futuresData, isVisible], () => { 
  if (isVisible.value) debouncedInit() 
}, { deep: true })
</script>

<style scoped>
.topbar {
  font-size: 10px;
  font-family: monospace;
  color: #6b7280;
  padding: 4px 8px;
  border-bottom: 1px solid rgba(55,55,55,0.5);
  background: rgba(10,14,23,0.6);
}
.chart-area {
  position: absolute;
  inset: 0;
}
</style>
