<template>
  <div ref="chartEl" class="w-full h-full"></div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as echarts from 'echarts/core'
import { CandlestickChart, LineChart, BarChart } from 'echarts/charts'
import {
  GridComponent, TooltipComponent, DataZoomComponent,
  MarkLineComponent, VisualMapComponent
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  CandlestickChart, LineChart, BarChart,
  GridComponent, TooltipComponent, DataZoomComponent,
  MarkLineComponent, VisualMapComponent, CanvasRenderer,
])

const props = defineProps({
  rawData: { type: Array, default: () => [] },
  tick:    { type: Object, default: null },
  symbol:  { type: String, default: '' },
  type:    { type: String, default: 'daily' },
})

const chartEl = ref(null)
let chart = null
let _ro = null

// rawData: [[ts, open, close, low, high, vol], ...]
function ohlc2kline(raw) {
  return raw.map(d => [d[0], d[1], d[4], d[3], d[2]])
}

function buildMA(closes, n) {
  return closes.map((_, i) => {
    if (i < n - 1) return '-'
    const avg = closes.slice(i - n + 1, i + 1).reduce((a, b) => a + b, 0) / n
    return +avg.toFixed(2)
  })
}

function buildOption(raw, tickSym, tick) {
  const kData = ohlc2kline(raw)
  const closes = raw.map(d => d[2])
  const volumes = raw.map(d => ({
    value: d[5] || 0,
    itemStyle: { color: d[2] >= d[1] ? '#ef232a' : '#14b143' },
  }))
  const ma5  = buildMA(closes, 5)
  const ma10 = buildMA(closes, 10)
  const ma20 = buildMA(closes, 20)

  // tick incremental update
  let finalData = kData
  if (tick && tickSym === props.symbol && tick.price > 0) {
    const last = kData[kData.length - 1]
    if (last) {
      last[4] = tick.price
      last[2] = Math.max(last[2], tick.price)
      last[3] = Math.min(last[3], tick.price)
      finalData = [...kData]
    }
  }

  return {
    backgroundColor: 'transparent',
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross', crossStyle: { color: '#555' } },
      backgroundColor: '#1e2130', borderColor: '#374151',
      textStyle: { color: '#d1d5db', fontSize: 11 },
    },
    legend: { show: false },
    grid: [
      { top: 8, bottom: '35%', left: 48, right: 8 },
      { top: '68%', bottom: 30, left: 48, right: 8 },
    ],
    xAxis: [
      {
        type: 'category', gridIndex: 0, data: finalData.map(d => d[0]),
        axisLabel: {
          color: '#6b7280', fontSize: 9,
          formatter: v => {
            const d = new Date(v)
            return `${d.getMonth() + 1}/${d.getDate()}`
          },
        },
        splitLine: { show: false },
      },
      {
        type: 'category', gridIndex: 1, data: finalData.map(d => d[0]),
        axisLabel: { show: false }, splitLine: { show: false },
      },
    ],
    yAxis: [
      {
        scale: true, gridIndex: 0, position: 'left',
        axisLabel: { color: '#6b7280', fontSize: 9 },
        splitLine: { lineStyle: { color: '#1f2937' } },
      },
      {
        scale: true, gridIndex: 1, position: 'left',
        axisLabel: {
          color: '#6b7280', fontSize: 9,
          formatter: v => {
            if (v >= 1e8) return (v / 1e8).toFixed(0) + '亿'
            if (v >= 1e4) return (v / 1e4).toFixed(0) + '万'
            return v
          },
        },
        splitLine: { lineStyle: { color: '#1f2937' } },
      },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 70, end: 100 },
      {
        type: 'slider', xAxisIndex: [0, 1], start: 70, end: 100,
        bottom: 4, height: 16,
        borderColor: '#374151', fillerColor: 'rgba(96,165,250,0.1)',
        handleStyle: { color: '#60a5fa' },
        textStyle: { color: '#6b7280', fontSize: 9 },
      },
    ],
    series: [
      {
        name: 'K线', type: 'candlestick', data: finalData,
        xAxisIndex: 0, yAxisIndex: 0,
        itemStyle: {
          color: '#ef232a', color0: '#14b143',
          borderColor: '#ef232a', borderColor0: '#14b143',
        },
        barMaxWidth: 8,
      },
      {
        name: 'MA5', type: 'line', data: ma5,
        xAxisIndex: 0, yAxisIndex: 0,
        smooth: true, symbol: 'none',
        lineStyle: { color: '#ffffff', width: 1 },
      },
      {
        name: 'MA10', type: 'line', data: ma10,
        xAxisIndex: 0, yAxisIndex: 0,
        smooth: true, symbol: 'none',
        lineStyle: { color: '#fbbf24', width: 1 },
      },
      {
        name: 'MA20', type: 'line', data: ma20,
        xAxisIndex: 0, yAxisIndex: 0,
        smooth: true, symbol: 'none',
        lineStyle: { color: '#c084fc', width: 1 },
      },
      {
        name: 'VOL', type: 'bar', data: volumes,
        xAxisIndex: 1, yAxisIndex: 1, barMaxWidth: 8,
      },
    ],
  }
}

function applyTickFast(raw, tickSym, tick) {
  if (!chart || !tick || tickSym !== props.symbol) return
  const last = raw[raw.length - 1]
  if (!last) return
  last[4] = tick.price
  last[2] = Math.max(last[2], tick.price)
  last[3] = Math.min(last[3], tick.price)
  last[5] = (last[5] || 0) + (tick.volume || 0)
  const kData = ohlc2kline(raw)
  chart.setOption({ series: [{ name: 'K线', data: kData }] }, false)
}

onMounted(async () => {
  await nextTick()
  chart = echarts.init(chartEl.value, 'dark')
  chart.setOption(buildOption(props.rawData, props.symbol, props.tick))
  _ro = new ResizeObserver(() => chart?.resize())
  if (chartEl.value) _ro.observe(chartEl.value)
})

onBeforeUnmount(() => {
  _ro?.disconnect()
  chart?.dispose()
})

watch(() => props.rawData, (newData) => {
  if (!chart) return
  chart.setOption(buildOption(newData, props.symbol, props.tick))
}, { deep: true })

watch(() => props.tick, (t) => {
  if (!chart || !props.rawData.length) return
  applyTickFast(props.rawData, props.symbol, t)
})

defineExpose({ getChartInstance: () => chart })
</script>
