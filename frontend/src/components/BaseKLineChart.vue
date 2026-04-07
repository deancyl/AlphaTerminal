<template>
  <!--
    BaseKLineChart — 纯渲染层组件
    接收 props: rawData, tick, type, symbol
    只做 ECharts 渲染，不处理数据拉取
  -->
  <div ref="chartEl" class="w-full h-full" />
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts/core'
import { LineChart, BarChart, CandlestickChart } from 'echarts/charts'
import {
  GridComponent, TooltipComponent, DataZoomComponent,
  MarkLineComponent, VisualMapComponent
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([LineChart, BarChart, CandlestickChart, GridComponent,
             TooltipComponent, DataZoomComponent, MarkLineComponent,
             VisualMapComponent, CanvasRenderer])

const props = defineProps({
  rawData:    { type: Array,  default: () => [] },   // [[ts, open, close, low, high, vol], ...]
  tick:       { type: Object, default: null },       // { symbol, price, chg_pct, volume }
  type:       { type: String, default: '日K' },
  symbol:     { type: String, default: '' },
})

const chartEl = ref(null)
let chart = null

// ── 工具 ────────────────────────────────────────────────────
function ohlc2kline(raw) {
  // raw: [[ts, open, close, low, high, vol], ...]
  return raw.map(d => [d[0], d[1], d[4], d[3], d[2]])  // [ts, open, high, low, close]
}
function buildMA(closes, n) {
  return closes.map((_, i) => {
    if (i < n - 1) return '-'
    const avg = closes.slice(i - n + 1, i + 1).reduce((a, b) => a + b, 0) / n
    return +avg.toFixed(2)
  })
}

// ── Option Builder ─────────────────────────────────────────────
function buildOption(raw, tickSym, tickData) {
  const kData = ohlc2kline(raw)
  const closes = raw.map(d => d[2])
  const volumes = raw.map(d => ({ value: d[5] || 0, itemStyle: { color: d[2] >= d[1] ? '#ef232a' : '#14b143' } }))
  const ma5  = buildMA(closes, 5)
  const ma10  = buildMA(closes, 10)
  const ma20  = buildMA(closes, 20)

  // 更新最后一根 K 线（如果有 tick）
  let finalData = kData
  if (tickData && tickSym === props.symbol) {
    const last = kData[kData.length - 1]
    if (last && tickData.price > 0) {
      last[4] = tickData.price                        // close
      last[2] = Math.max(last[2], tickData.price)    // high
      last[3] = Math.min(last[3], tickData.price)    // low
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
      formatter: (params) => {
        if (!params.length || params[0].value === '-') return ''
        const p = params[0]
        const d = new Date(p.axisValue)
        const ds = `${d.getFullYear()}-${(d.getMonth()+1).toString().padStart(2,'0')}-${d.getDate().toString().padStart(2,'0')} ${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')}`
        const o = p.value[1], h = p.value[2], l = p.value[3], c = p.value[4]
        return `<div style="font-size:10px">${ds}<br/>`
          + `开:${o} 收:${c}<br/>高:${h} 低:${l}</div>`
      }
    },
    legend: { show: false },
    grid: [
      { top: 8, bottom: '35%', left: 48, right: 8 },
      { top: '68%', bottom: 30, left: 48, right: 8 },
    ],
    xAxis: [
      { type: 'category', gridIndex: 0, data: finalData.map(d => d[0]),
        axisLabel: { show: true, color: '#6b7280', fontSize: 9, formatter: v => {
          const d = new Date(v); return `${d.getMonth()+1}/${d.getDate()}`
        }},
        splitLine: { show: false } },
      { type: 'category', gridIndex: 1, data: finalData.map(d => d[0]),
        axisLabel: { show: false }, splitLine: { show: false } },
    ],
    yAxis: [
      { scale: true, gridIndex: 0, position: 'left',
        axisLabel: { color: '#6b7280', fontSize: 9 },
        splitLine: { lineStyle: { color: '#1f2937' } } },
      { scale: true, gridIndex: 1, position: 'left',
        axisLabel: { color: '#6b7280', fontSize: 9,
          formatter: v => { if (v >= 1e8) return (v/1e8).toFixed(0)+'亿'; if (v >= 1e4) return (v/1e4).toFixed(0)+'万'; return v } },
        splitLine: { lineStyle: { color: '#1f2937' } } },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 70, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1], start: 70, end: 100, bottom: 4, height: 16,
        borderColor: '#374151', fillerColor: 'rgba(96,165,250,0.1)',
        handleStyle: { color: '#60a5fa' }, textStyle: { color: '#6b7280', fontSize: 9 } },
    ],
    series: [
      {
        name: 'K线', type: 'candlestick', data: finalData, xAxisIndex: 0, yAxisIndex: 0,
        itemStyle: { color: '#ef232a', color0: '#14b143', borderColor: '#ef232a', borderColor0: '#14b143' },
        barMaxWidth: 8,
      },
      {
        name: 'MA5', type: 'line', data: ma5, xAxisIndex: 0, yAxisIndex: 0,
        smooth: true, symbol: 'none', lineStyle: { color: '#ffffff', width: 1 },
      },
      {
        name: 'MA10', type: 'line', data: ma10, xAxisIndex: 0, yAxisIndex: 0,
        smooth: true, symbol: 'none', lineStyle: { color: '#fbbf24', width: 1 },
      },
      {
        name: 'MA20', type: 'line', data: ma20, xAxisIndex: 0, yAxisIndex: 0,
        smooth: true, symbol: 'none', lineStyle: { color: '#c084fc', width: 1 },
      },
      {
        name: 'VOL', type: 'bar', data: volumes, xAxisIndex: 1, yAxisIndex: 1,
        barMaxWidth: 8,
      },
    ],
  }
}

// ── 增量更新（不重建 option）──────────────────────────────────
function applyTickFast(raw, tickSym, tick) {
  if (!chart || !tick || tickSym !== props.symbol) return
  const last = raw[raw.length - 1]
  if (!last) return
  last[4] = tick.price                         // close
  last[2] = Math.max(last[2], tick.price)      // high
  last[3] = Math.min(last[3], tick.price)       // low
  last[5] = (last[5] || 0) + (tick.volume || 0)
  const kData = ohlc2kline(raw)
  chart.setOption({ series: [{ name:'K线', data: kData }] }, false)
}

// ── 生命周期 ─────────────────────────────────────────────────
onMounted(async () => {
  await nextTick()
  chart = echarts.init(chartEl.value, 'dark')
  chart.setOption(buildOption(props.rawData, props.symbol, props.tick))
  window.addEventListener('resize', () => chart?.resize())
})

onUnmounted(() => {
  window.removeEventListener('resize', () => chart?.resize())
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

watch(() => props.symbol, (s) => {
  if (!chart || !props.rawData.length) return
  chart.setOption(buildOption(props.rawData, s, props.tick))
})
</parameter>
