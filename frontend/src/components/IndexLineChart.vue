<template>
  <div ref="chartRef" class="w-full h-full min-h-[120px]"></div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'

const props = defineProps({
  symbol:   { type: String, default: '000001' },
  name:     { type: String, default: '上证指数' },
  color:    { type: String, default: '#00ff88' },
  url:      { type: String, default: '/api/v1/market/history/000001' },
})

const chartRef = ref(null)
let chartInstance = null
let resizeObserver = null

async function fetchHistory() {
  try {
    const res = await fetch(props.url)
    if (!res.ok) return []
    const data = await res.json()
    return (data.history || []).map(r => ({
      time:  new Date(r.timestamp * 1000).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' }),
      price: r.price,
      chg:  r.change_pct,
    }))
  } catch {
    return []
  }
}

function buildOption(history) {
  const times = history.map(h => h.time)
  const prices = history.map(h => h.price)
  const changes = history.map(h => h.chg)

  return {
    backgroundColor: 'transparent',
    grid: { top: 8, right: 8, bottom: 24, left: 50, containLabel: false },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1a1e2e',
      borderColor: '#374151',
      textStyle: { color: '#9ca3af', fontSize: 11 },
      formatter: (params) => {
        const p = params[0]
        const chg = changes[p.dataIndex]
        const sign = chg >= 0 ? '+' : ''
        return `<span style="color:#6b7280;font-size:10px">${p.axisValue}</span><br/>`
          + `<span style="color:#e5e7eb;font-size:12px">${p.value.toFixed(2)}</span>`
          + `<span style="color:${chg >= 0 ? '#f87171' : '#4ade80'};font-size:11px;margin-left:6px">${sign}${chg?.toFixed(2) ?? '--'}%</span>`
      },
    },
    xAxis: {
      type: 'category', data: times,
      axisLine: { lineStyle: { color: '#2d3748' } },
      axisLabel: { color: '#6b7280', fontSize: 9, interval: Math.max(0, Math.floor(times.length / 5) - 1) },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      position: 'left',
      axisLine: { show: false },
      axisLabel: { color: '#6b7280', fontSize: 9, formatter: v => v.toFixed(0) },
      splitLine: { lineStyle: { color: '#1f2937', type: 'dashed' } },
    },
    series: [{
      type: 'line',
      data: prices,
      smooth: true,
      symbol: 'none',
      lineStyle: { color: props.color, width: 1.5 },
      areaStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: props.color + '30' },
            { offset: 1, color: props.color + '00' },
          ],
        },
      },
    }],
  }
}

async function initChart() {
  if (!chartRef.value || typeof window === 'undefined' || !window.echarts) return

  const history = await fetchHistory()
  chartInstance = window.echarts.init(chartRef.value, null, { renderer: 'canvas' })
  chartInstance.setOption(buildOption(history.length ? history : [{ time: '暂无数据', price: 0, chg: 0 }]))

  // 监听 gridstack 缩放事件触发 resize
  resizeObserver = new ResizeObserver(() => {
    chartInstance?.resize()
  })
  resizeObserver.observe(chartRef.value)
}

onMounted(initChart)

onUnmounted(() => {
  resizeObserver?.disconnect()
  chartInstance?.dispose()
  chartInstance = null
})
</script>
