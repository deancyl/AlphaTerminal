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
  yieldCurve: { type: Object, default: null },  // 当前曲线
  curve1m:    { type: Object, default: null },  // 1个月前
  curve1y:    { type: Object, default: null },  // 1年前
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

  // ── 历史曲线数据（1M / 1Y）───────────────────────────────────
  function extractCurve(curve) {
    if (!curve) return []
    return TENOR_ORDER.map(key => curve[key] ?? null)
  }
  const curve1mData = extractCurve(props.curve1m)
  const curve1yData = extractCurve(props.curve1y)
  const has1m = curve1mData.some(v => v != null)
  const has1y = curve1yData.some(v => v != null)

  const series = [
    // 当前曲线（实线 + 面积）
    {
      type: 'line', name: '今日', data: yData, smooth: 0.4, symbol: 'circle', symbolSize: 6,
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
    },
  ]

  if (has1m) {
    series.push({
      type: 'line', name: '1个月前', data: curve1mData, smooth: 0.3, symbol: 'none',
      lineStyle: { color: '#fbbf24', width: 1.5, type: 'dashed', opacity: 0.75 },
    })
  }
  if (has1y) {
    series.push({
      type: 'line', name: '1年前', data: curve1yData, smooth: 0.3, symbol: 'none',
      lineStyle: { color: '#9ca3af', width: 1.2, type: 'dotted', opacity: 0.55 },
    })
  }

  const option = {
    backgroundColor: 'transparent',
    grid: { top: 12, right: 16, bottom: has1m || has1y ? 48 : 28, left: 52 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(10,14,23,0.95)',
      borderColor: 'rgba(50,50,50,0.8)',
      textStyle: { color: '#9ca3af', fontSize: 11, fontFamily: 'monospace' },
      formatter: (params) => {
        const lines = params.map(p =>
          `<span style="color:${p.color};font-family:monospace">${p.marker}${p.seriesName}: ${p.value != null ? p.value.toFixed(4) + '%' : '-'}</span>`
        )
        return `<span style="color:#60a5fa;font-family:monospace">${params[0].name}</span><br/>${lines.join('<br/>')}`
      },
    },
    legend: (has1m || has1y) ? {
      bottom: 4, textStyle: { color: '#6b7280', fontSize: 9, fontFamily: 'monospace' },
      icon: 'roundRect', itemWidth: 12, itemHeight: 2,
    } : { show: false },
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
    series,
  }
  chartInstance.setOption(option, true)
}

async function initChart() {
  await nextTick()
  if (!chartRef.value || !window.echarts) return
  if (chartInstance) {
    chartInstance.clear()
    chartInstance.dispose()
    chartInstance = null
  }
  buildChart()
}

let resizeObserver = null
onMounted(() => {
  initChart()
  if (chartRef.value) {
    resizeObserver = new ResizeObserver(() => chartInstance?.resize())
    resizeObserver.observe(chartRef.value)
  }
})
onUnmounted(() => {
  resizeObserver?.disconnect()
  if (chartInstance) {
    chartInstance.clear()
    chartInstance.dispose()
    chartInstance = null
  }
})
watch([() => props.yieldCurve, () => props.curve1m, () => props.curve1y], () => { initChart() }, { deep: true })
</script>
