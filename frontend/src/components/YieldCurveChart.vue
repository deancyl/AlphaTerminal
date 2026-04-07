<template>
  <div class="w-full h-full relative flex flex-col" style="min-height:120px">
    <div class="shrink-0 flex items-center gap-3 px-1 py-1 border-b border-gray-700 bg-terminal-bg/60">
      <span class="text-[10px] font-mono text-terminal-dim">国债收益率曲线</span>
      <span class="text-[10px] font-mono text-gray-500">|</span>
      <span class="text-[10px] font-mono text-terminal-dim">{{ updateTime || '...' }}</span>
    </div>
    <div class="flex-1 relative min-h-0">
      <div ref="chartRef" class="absolute inset-0"></div>
      <div v-if="!hasData" class="absolute inset-0 z-10 flex items-center justify-center">
        <span class="text-terminal-dim text-xs">暂无数据</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'

const props = defineProps({
  yieldCurve: { type: Object, default: null },
  updateTime: { type: String, default: '' },
})

const chartRef = ref(null)
const hasData  = ref(false)
let chartInstance = null

const TENOR_ORDER  = ['3月','6月','1年','3年','5年','7年','10年','30年']
const TENOR_LABELS = ['3M','6M','1Y','3Y','5Y','7Y','10Y','30Y']

function buildChart() {
  if (!chartRef.value || !window.echarts) return
  if (chartInstance) { chartInstance.dispose(); chartInstance = null }

  const tenors = props.yieldCurve || {}
  const xData = []
  const yData = []
  for (const key of TENOR_ORDER) {
    if (tenors[key] != null) {
      xData.push(TENOR_LABELS[TENOR_ORDER.indexOf(key)])
      yData.push(tenors[key])
    }
  }
  hasData.value = yData.length > 0
  if (!hasData.value) return

  chartInstance = window.echarts.init(chartRef.value, null, { renderer: 'canvas' })

  const option = {
    backgroundColor: 'transparent',
    grid: { top: 12, right: 16, bottom: 28, left: 52 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(10,14,23,0.95)',
      borderColor: 'rgba(50,50,50,0.8)',
      textStyle: { color: '#9ca3af', fontSize: 11, fontFamily: 'monospace' },
      formatter: (params) => {
        const p = params[0]
        return `<span style="color:#60a5fa;font-family:monospace">${p.name}</span><br/>收益率: <span style="color:#f3f4f6">${p.value}%</span>`
      },
    },
    xAxis: {
      type: 'category', data: xData,
      axisLine: { lineStyle: { color: '#2d2d2d' } },
      axisTick: { show: false },
      axisLabel: { color: '#6b7280', fontSize: 10, fontFamily: 'monospace' },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value', scale: true,
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: '#6b7280', fontSize: 10, fontFamily: 'monospace', formatter: v => v + '%' },
      splitLine: { lineStyle: { color: '#1f1f1f', type: 'dashed' } },
    },
    series: [{
      type: 'line', data: yData, smooth: 0.4, symbol: 'circle', symbolSize: 6,
      lineStyle: { color: '#60a5fa', width: 2 },
      itemStyle: { color: '#60a5fa', borderWidth: 2, borderColor: '#0a0e17' },
      areaStyle: {
        color: new window.echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(96,165,250,0.25)' },
          { offset: 1, color: 'rgba(96,165,250,0.02)' },
        ]),
      },
      label: {
        show: yData.length < 10, position: 'top', distance: 4,
        color: '#9ca3af', fontSize: 9, fontFamily: 'monospace',
        formatter: v => (v.value != null ? v.value.toFixed(3) + '%' : ''),
      },
    }],
  }
  chartInstance.setOption(option, true)
}

async function initChart() { await nextTick(); buildChart() }

let resizeObserver = null
onMounted(() => {
  initChart()
  if (chartRef.value) {
    resizeObserver = new ResizeObserver(() => chartInstance?.resize())
    resizeObserver.observe(chartRef.value)
  }
})
onUnmounted(() => { resizeObserver?.disconnect(); chartInstance?.dispose() })
watch(() => props.yieldCurve, () => { initChart() }, { deep: true })
</script>
