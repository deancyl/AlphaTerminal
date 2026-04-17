<template>
  <div ref="chartEl" class="w-full h-full"></div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  // 格式: [{ date, open, high, low, close, volume }, ...]
  hist: { type: Array, default: () => [] },
  // 格式: [{ entry_date, entry_price, exit_date, exit_price, pnl, pnl_pct, type }, ...]
  trades: { type: Array, default: () => [] },
  symbol: { type: String, default: '' },
})

const chartEl = ref(null)
let chart = null
let ro = null

// ── 构建 ECharts Option ─────────────────────────────────────────
function buildOption() {
  const hist = props.hist
  if (!hist || hist.length === 0) return {}

  const times = hist.map(h => h.date || h.time || '')
  const klineData = hist.map(h => [h.open, h.close, h.low, h.high])
  const volumes = hist.map(h => h.volume || 0)

  // ── 构建 markPoints（买卖信号）───────────────────────────────
  // 建立 date → index 映射
  const dateIdx = {}
  hist.forEach((h, i) => { dateIdx[h.date || h.time] = i })

  const buyPoints = []   // 金叉买入 → 向上红色箭头
  const sellPoints = []  // 死叉卖出 → 向下绿色箭头

  props.trades.forEach(trade => {
    if (trade.type !== 'long') return

    // 买入信号：entry_date 位置
    const entryIdx = dateIdx[trade.entry_date]
    if (entryIdx != null) {
      buyPoints.push({
        coord: [entryIdx, hist[entryIdx].low],
        value: hist[entryIdx].close,
        symbol: 'arrowUp',
        symbolSize: [12, 12],
        itemStyle: { color: '#ef232a', borderColor: '#ef232a' },
      })
    }

    // 卖出信号：exit_date 位置
    const exitIdx = dateIdx[trade.exit_date]
    if (exitIdx != null) {
      const pnlColor = (trade.pnl || 0) >= 0 ? '#14b143' : '#ef232a'
      sellPoints.push({
        coord: [exitIdx, hist[exitIdx].high],
        value: hist[exitIdx].close,
        symbol: 'arrowDown',
        symbolSize: [12, 12],
        itemStyle: { color: pnlColor, borderColor: pnlColor },
      })
    }
  })

  const closes = hist.map(h => h.close)
  const yMin = +(Math.min(...closes) * 0.997).toFixed(2)
  const yMax = +(Math.max(...closes) * 1.003).toFixed(2)

  // ── 副图：资金曲线 ──────────────────────────────────────────
  const equityMap = {}
  if (props.trades?.length) {
    let equity = 100000  // fallback
    for (const t of props.trades) {
      if (t.pnl != null) {
        equity += t.pnl
        if (t.exit_date) equityMap[t.exit_date] = equity
      }
    }
  }
  const equityData = hist.map((h, i) => {
    const v = equityMap[h.date || h.time]
    return [i, v != null ? v : null]
  })

  return {
    backgroundColor: 'transparent',
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross', crossStyle: { color: '#555' } },
      backgroundColor: '#1e2130', borderColor: '#374151',
      textStyle: { color: '#d1d5db', fontSize: 11 },
    },
    legend: {
      show: true,
      bottom: 0,
      textStyle: { color: '#9ca3af', fontSize: 10 },
      data: ['K线', '买入', '卖出', '资金曲线'],
    },
    grid: [
      { top: 10, height: '55%', left: 55, right: 8 },
      { top: '68%', height: '20%', left: 55, right: 8 },
    ],
    xAxis: [
      {
        type: 'category', data: times, gridIndex: 0,
        axisLabel: { show: false },
        axisLine: { lineStyle: { color: '#374151' } },
      },
      {
        type: 'category', data: times, gridIndex: 1,
        axisLabel: { show: true, fontSize: 9, color: '#6b7280' },
        axisLine: { lineStyle: { color: '#374151' } },
      },
    ],
    yAxis: [
      {
        type: 'value', gridIndex: 0, scale: true,
        min: yMin, max: yMax,
        splitLine: { lineStyle: { color: '#1f2937' } },
        axisLabel: { color: '#6b7280', fontSize: 9 },
      },
      {
        type: 'value', gridIndex: 1,
        splitLine: { show: false },
        axisLabel: { color: '#6b7280', fontSize: 9, formatter: (v) => v >= 1e6 ? (v / 1e6).toFixed(1) + 'M' : v.toFixed(0) },
      },
    ],
    series: [
      // 主图 K 线
      {
        name: 'K线', type: 'candlestick', data: klineData,
        xAxisIndex: 0, yAxisIndex: 0,
        itemStyle: {
          color: '#ef232a', color0: '#14b143',
          borderColor: '#ef232a', borderColor0: '#14b143',
        },
        barMaxWidth: 8,
        markPoint: {
          symbol: 'pin',
          symbolSize: [20, 20],
          data: [
            ...buyPoints.map(p => ({ ...p, name: '买入' })),
            ...sellPoints.map(p => ({ ...p, name: '卖出' })),
          ],
          label: { color: '#fff', fontSize: 9 },
          tooltip: {
            formatter: (p) => {
              const side = p.data.name
              const price = p.data.value
              const date = times[p.data.coord[0]]
              return `<b>${side}</b><br/>${date}<br/>价: ${price?.toFixed(2)}`
            }
          },
        },
      },
      // 副图：资金曲线
      {
        name: '资金曲线', type: 'line',
        data: equityData,
        xAxisIndex: 1, yAxisIndex: 1,
        symbol: 'none',
        lineStyle: { color: '#60a5fa', width: 1.5 },
        tooltip: {
          formatter: (p) => `资金曲线<br/>${times[p.dataIndex] || ''}: ${p.value?.[1]?.toFixed(2) ?? '-'}`
        },
      },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 60, end: 100 },
      {
        type: 'slider', xAxisIndex: [0, 1],
        bottom: 0, height: 16,
        borderColor: '#374151', fillerColor: 'rgba(96,165,250,0.1)',
        handleStyle: { color: '#60a5fa' },
        textStyle: { color: '#6b7280', fontSize: 9 },
      },
    ],
  }
}

// ── 生命周期 ────────────────────────────────────────────────────
onMounted(() => {
  ro = new ResizeObserver((entries) => {
    if (!chartEl.value) return
    const { width, height } = entries[0].contentRect
    if (width <= 0 || height <= 0) return
    if (!chart) {
      chart = window.echarts.init(chartEl.value, 'dark')
      chart.setOption(buildOption())
    } else {
      chart.resize()
    }
  })
  if (chartEl.value) ro.observe(chartEl.value)
})

onBeforeUnmount(() => {
  ro?.disconnect()
  chart?.dispose()
  chart = null
})

watch([() => props.hist, () => props.trades], () => {
  if (!chart) return
  chart.setOption(buildOption(), true)
}, { deep: false })

defineExpose({ getChartInstance: () => chart })
</script>
