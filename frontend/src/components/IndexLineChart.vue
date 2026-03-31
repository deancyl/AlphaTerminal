<template>
  <div class="w-full h-full min-h-[120px] relative">
    <!-- Error overlay -->
    <div v-if="chartError" class="absolute inset-0 z-10 flex flex-col items-center justify-center bg-terminal-bg/90 rounded">
      <div class="text-2xl mb-2">📊</div>
      <div class="text-terminal-dim text-xs text-center px-4">{{ chartError }}</div>
      <button class="mt-2 px-3 py-1 text-[10px] rounded border border-gray-600 text-terminal-dim hover:border-terminal-accent/40 transition"
              @click="retryChart">重试</button>
    </div>
    <!-- Loading skeleton -->
    <div v-if="isLoading" class="absolute inset-0 flex items-end justify-center pb-4 pointer-events-none">
      <div class="flex gap-1 items-end opacity-40">
        <div v-for="i in 24" :key="i" class="w-1 bg-terminal-accent rounded-t animate-pulse"
             :style="{ height: `${30 + ((i * 37) % 60)}%` }"></div>
      </div>
    </div>
    <div ref="chartRef" class="w-full h-full"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'

const props = defineProps({
  symbol:     { type: String, default: '000001' },
  name:       { type: String, default: '上证指数' },
  color:      { type: String, default: '#00ff88' },
  url:        { type: String, default: '/api/v1/market/history/000001' },
  indicators: { type: Array,  default: () => [] },
})

const chartRef     = ref(null)
const chartError   = ref('')
const isLoading    = ref(false)
let   chartInstance = null
let   resizeObserver = null

// ── 数据清洗 ───────────────────────────────────────────────────
function _sanitize(raw, chartType) {
  if (!Array.isArray(raw) || !raw.length) return []
  if (chartType === 'line') {
    // 分时数据: { time, date, price, volume, change_pct }
    return raw.filter(r => Number(r.price) > 0)
      .map(r => ({
        time:       r.time  || String(r.timestamp || ''),
        date:       r.date  || '',
        price:      Number(r.price) || 0,
        volume:     Number(r.volume) || 0,
        change_pct: Number(r.change_pct) || 0,
      }))
  }
  // K线数据: { open, high, low, close, volume }
  let ok = 0, zero = 0
  const cleaned = raw.map(r => {
    let o = Number(r.open)  || 0
    let c = Number(r.close) || 0
    let h = Number(r.high) || 0
    let l = Number(r.low)  || 0
    let v = Number(r.volume) || 0
    if (h < l) { const t = h; h = l; l = t }
    if (o <= 0 || c <= 0 || h <= 0 || l <= 0) { zero++; return null }
    h = Math.max(h, o, c); l = Math.min(l, o, c)
    ok++
    return { date: r.date || String(r.timestamp || ''), open: o, close: c, high: h, low: l, volume: v, change_pct: Number(r.change_pct) || 0 }
  }).filter(Boolean)
  if (zero > 0) console.warn(`[IndexLineChart] _sanitize: ${ok} ok, ${zero} zero-dropped`)
  return cleaned
}

// ── 指标计算 ───────────────────────────────────────────────────
function calcMACD(closes) {
  if (closes.length < 26) return { dif: [], dea: [], macd: [] }
  let e12 = closes[0], e26 = closes[0], e9 = 0
  const dif = [], dea = [], macd = []
  for (let i = 0; i < closes.length; i++) {
    e12 = i === 0 ? closes[0] : closes[i] * (2/13) + e12 * (11/13)
    e26 = i === 0 ? closes[0] : closes[i] * (2/27) + e26 * (25/27)
    dif.push(e12 - e26)
  }
  e9 = dif[0]
  for (let i = 0; i < dif.length; i++) {
    e9 = i === 0 ? dif[0] : dif[i] * (2/10) + e9 * (8/10)
    dea.push(e9); macd.push(+((dif[i] - e9) * 2).toFixed(3))
  }
  return { dif, dea, macd }
}

function calcBOLL(closes) {
  const period = 20, mid = [], upper = [], lower = []
  for (let i = 0; i < closes.length; i++) {
    if (i < period - 1) { mid.push(null); upper.push(null); lower.push(null); continue }
    const slice = closes.slice(i - period + 1, i + 1)
    const mean  = slice.reduce((a, b) => a + b, 0) / period
    const std   = Math.sqrt(slice.reduce((a, b) => a + (b - mean) ** 2, 0) / period)
    mid.push(+mean.toFixed(3)); upper.push(+(mean + 2 * std).toFixed(3)); lower.push(+(mean - 2 * std).toFixed(3))
  }
  return { mid, upper, lower }
}

function calcKDJ(highs, lows, closes, n = 9) {
  const k = [], d = [], j = []
  for (let i = 0; i < closes.length; i++) {
    if (i < n - 1) { k.push(null); d.push(null); j.push(null); continue }
    const rh = Math.max(...highs.slice(i - n + 1, i + 1))
    const rl = Math.min(...lows.slice(i - n + 1, i + 1))
    const rsv = rh === rl ? 50 : (closes[i] - rl) / (rh - rl) * 100
    const pk = k[i - 1] ?? 50, pd = d[i - 1] ?? 50
    const nk = +(2/3 * pk + 1/3 * rsv).toFixed(2)
    const nd = +(2/3 * pd + 1/3 * nk).toFixed(2)
    k.push(nk); d.push(nd); j.push(+(3 * nk - 2 * nd).toFixed(2))
  }
  return { k, d, j }
}

// ── 分时图 Option (line) ───────────────────────────────────────
function _buildLineChart(hist, activeIndicators) {
  const times  = hist.map(h => h.time ? h.time.slice(11, 16) : (h.date || ''))
  const prices  = hist.map(h => h.price)
  const changes = hist.map(h => h.change_pct || 0)
  // 均价 = cumulative_average
  const avg = []
  let sum = 0
  for (let i = 0; i < prices.length; i++) { sum += prices[i]; avg.push(+(sum / (i + 1)).toFixed(3)) }
  const upCount = prices.filter((p, i) => i > 0 && p > prices[i - 1]).length
  const lineColor = upCount >= prices.length / 2 ? '#ef4444' : '#22c55e'

  const series = [
    {
      name: '价格',
      type: 'line',
      data: prices,
      smooth: 0.3,
      symbol: 'none',
      lineStyle: { color: lineColor, width: 1.5 },
      areaStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: lineColor + '30' },
            { offset: 1, color: lineColor + '00' },
          ],
        },
      },
    },
    {
      name: '均价',
      type: 'line',
      data: avg,
      smooth: 0.3,
      symbol: 'none',
      lineStyle: { color: '#fbbf24', width: 1, type: 'dashed' },
    },
  ]

  const hasSub = (activeIndicators || []).length > 0
  const kH   = hasSub ? 60 : 75
  const subH = hasSub ? 20 : 0
  const volH = hasSub ? 0  : 25
  const gap  = 3
  const volTop = kH + gap
  const subTop = hasSub ? volTop + volH + gap : kH + volH + gap * 2

  const grid = [
    { top: 5, height: `${kH}%`,  right: 8, left: 50, bottom: 2 },
  ]
  if (volH > 0) grid.push({ top: `${volTop}%`, height: `${volH}%`, right: 8, left: 50, bottom: 2 })
  if (hasSub) grid.push({ top: `${subTop}%`, height: `${subH}%`, right: 8, left: 50, bottom: 2 })

  const xAxis = [{ type: 'category', data: times, boundaryGap: false,
    axisLine: { lineStyle: { color: '#2d3748' } },
    axisLabel: { color: '#6b7280', fontSize: 9, interval: Math.max(0, Math.floor(times.length / 6) - 1) },
    splitLine: { show: false } }]

  const yAxis = [{ type: 'value', scale: true, position: 'left',
    axisLine: { show: false },
    axisLabel: { color: '#6b7280', fontSize: 9, formatter: v => v.toFixed(2) },
    splitLine: { lineStyle: { color: '#1f2937', type: 'dashed' } } }]

  const volSeries = volH > 0 ? [{
    name: '成交量', type: 'bar',
    data: hist.map((h, i) => ({ value: h.volume, itemStyle: { color: prices[i] >= (prices[i - 1] ?? prices[i]) ? '#ef444444' : '#22c55e44' } })),
    xAxisIndex: 1, yAxisIndex: 1, barMaxWidth: 3,
  }] : []

  // 副图指标（复用 K 线逻辑）
  if (hasSub) {
    const closes = prices
    const highs  = prices.map((_, i) => i > 0 ? Math.max(...prices.slice(Math.max(0, i - 5), i + 1)) : prices[i])
    const lows   = prices.map((_, i) => i > 0 ? Math.min(...prices.slice(Math.max(0, i - 5), i + 1)) : prices[i])
    xAxis.push({ type: 'category', data: times, boundaryGap: false,
      gridIndex: 1, axisLine: { lineStyle: { color: '#2d3748' } },
      axisLabel: { show: false }, splitLine: { show: false } })
    yAxis.push({ type: 'value', scale: true, gridIndex: 1, position: 'left',
      axisLine: { show: false }, axisLabel: { show: false }, splitLine: { show: false } })
    const subSeries = []
    if (activeIndicators.includes('MACD')) {
      const { dif, dea, macd } = calcMACD(closes)
      subSeries.push(
        { name: 'DIF', type: 'line', data: dif, xAxisIndex: 1, yAxisIndex: 1, smooth: true, symbol: 'none', lineStyle: { color: '#60a5fa', width: 1 } },
        { name: 'DEA', type: 'line', data: dea, xAxisIndex: 1, yAxisIndex: 1, smooth: true, symbol: 'none', lineStyle: { color: '#f87171', width: 1 } },
        { name: 'MACD', type: 'bar', data: macd.map(v => ({ value: Math.abs(v), itemStyle: { color: v >= 0 ? '#ef4444' : '#22c55e' } })), xAxisIndex: 1, yAxisIndex: 1, barMaxWidth: 4 },
      )
    }
    if (activeIndicators.includes('KDJ')) {
      const { k, d, j } = calcKDJ(highs, lows, closes)
      subSeries.push(
        { name: 'K', type: 'line', data: k, xAxisIndex: 1, yAxisIndex: 1, smooth: true, symbol: 'none', lineStyle: { color: '#f87171', width: 1 } },
        { name: 'D', type: 'line', data: d, xAxisIndex: 1, yAxisIndex: 1, smooth: true, symbol: 'none', lineStyle: { color: '#60a5fa', width: 1 } },
        { name: 'J', type: 'line', data: j, xAxisIndex: 1, yAxisIndex: 1, smooth: true, symbol: 'none', lineStyle: { color: '#fbbf24', width: 1 } },
      )
    }
    if (activeIndicators.includes('BOLL')) {
      const { mid, upper, lower } = calcBOLL(closes)
      subSeries.push(
        { name: 'BOLL-MID', type: 'line', data: mid, xAxisIndex: 1, yAxisIndex: 1, smooth: true, symbol: 'none', lineStyle: { color: '#a78bfa', width: 1 } },
        { name: 'BOLL-UP',  type: 'line', data: upper, xAxisIndex: 1, yAxisIndex: 1, smooth: true, symbol: 'none', lineStyle: { color: '#a78bfa', width: 1 } },
        { name: 'BOLL-LOW', type: 'line', data: lower, xAxisIndex: 1, yAxisIndex: 1, smooth: true, symbol: 'none', lineStyle: { color: '#a78bfa', width: 1 } },
      )
    }
    series.push(...subSeries)
  }

  return {
    backgroundColor: 'transparent', grid, xAxis, yAxis, series,
    tooltip: {
      trigger: 'axis', type: 'cross',
      axisPointer: { lineStyle: { color: '#374151' } },
      backgroundColor: '#1a1e2e', borderColor: '#374151', textStyle: { color: '#9ca3af', fontSize: 11 },
      formatter: (params) => {
        const p = params[0]
        if (!p) return ''
        const idx  = p.dataIndex
        const pr   = prices[idx] ?? 0
        const a    = avg[idx] ?? 0
        const chg  = changes[idx]; const sign = chg >= 0 ? '+' : ''
        const col  = pr >= (prices[idx - 1] ?? pr) ? '#22c55e' : '#ef4444'
        return `<span style="color:#6b7280;font-size:10px">${p.axisValue}</span><br/>`
          + `<span style="color:#9ca3af;font-size:10px">价</span> <span style="color:${col};font-size:11px">${pr.toFixed(3)}</span><br/>`
          + `<span style="color:#9ca3af;font-size:10px">均</span> <span style="color:#fbbf24;font-size:11px">${a.toFixed(3)}</span><br/>`
          + `<span style="color:${chg >= 0 ? '#f87171' : '#4ade80'};font-size:10px">${sign}${chg.toFixed(2)}%</span>`
      },
    },
    dataZoom: [
      { type: 'inside', xAxisIndex: 0, start: 90, end: 100, zoomOnMouseWheel: true },
      { type: 'slider', xAxisIndex: 0, start: 90, end: 100, height: 10, bottom: 1,
        borderColor: '#2d3748', fillerColor: 'rgba(59,130,246,0.12)',
        handleStyle: { color: '#60a5fa', borderColor: '#60a5fa' },
        textStyle: { color: '#6b7280', fontSize: 9 },
        dataBackground: { lineStyle: { color: '#374151' }, areaStyle: { color: 'rgba(59,130,246,0.06)' } } },
    ],
  }
}

// ── 均线计算 ─────────────────────────────────────────────────────
function calculateMA(dayCount, closes) {
  const ma = []
  for (let i = 0; i < closes.length; i++) {
    if (i < dayCount - 1) { ma.push('-'); continue }
    const slice = closes.slice(i - dayCount + 1, i + 1)
    ma.push(+(slice.reduce((a, b) => a + b, 0) / dayCount).toFixed(3))
  }
  return ma
}

// ── K线烛台 Option (candlestick) ─────────────────────────────────
function _buildCandleChart(hist, activeIndicators) {
  const times   = hist.map(h => h.date ? h.date.slice(5) : '')
  // OHLC: [open, close, low, high]  注意这里顺序与 ECharts 烛台协议一致
  const ohlc    = hist.map(h => [h.open, h.close, h.low, h.high])
  const volumes = hist.map(h => h.volume || 0)
  const changes = hist.map(h => h.change_pct || 0)
  const closes  = hist.map(h => h.close)
  const highs   = hist.map(h => h.high)
  const lows    = hist.map(h => h.low)

  // A股配色: 涨(收>=开)=红 #ef232a, 跌(收<开)=绿 #14b143
  const UP_COLOR   = '#ef232a'
  const DOWN_COLOR = '#14b143'

  // Y轴锚定
  const priceMin = +(Math.min(...closes) * 0.998).toFixed(2)
  const priceMax = +(Math.max(...closes) * 1.002).toFixed(2)

  const hasSub = (activeIndicators || []).length > 0
  const kH   = hasSub ? 58 : 72
  const volH = 15; const subH = hasSub ? 20 : 0
  const gap = 3
  const volTop = kH + gap
  const subTop = hasSub ? volTop + volH + gap : kH + volH + gap * 2
  const grid = [
    { top: 5, height: `${kH}%`,  right: 8, left: 50, bottom: 2 },
    { top: `${volTop}%`, height: `${volH}%`, right: 8, left: 50, bottom: 2 },
  ]
  if (hasSub) grid.push({ top: `${subTop}%`, height: `${subH}%`, right: 8, left: 50, bottom: 2 })

  // 均线序列
  const ma5  = calculateMA(5,  closes)
  const ma10 = calculateMA(10, closes)
  const ma20 = calculateMA(20, closes)

  const series = [
    // ── K线烛台: A股红涨绿跌 ───────────────────────────────────────
    { name: 'K线', type: 'candlestick', data: ohlc, xAxisIndex: 0, yAxisIndex: 0,
      itemStyle: {
        color:      UP_COLOR,       // 涨（收>=开）
        color0:     DOWN_COLOR,     // 跌（收<开）
        borderColor:      UP_COLOR,
        borderColor0:     DOWN_COLOR,
      } },
    // ── 成交量: 颜色跟随K线阴阳 ───────────────────────────────────
    { name: '成交量', type: 'bar',
      data: ohlc.map((o, i) => ({
        value: volumes[i],
        itemStyle: { color: o[1] >= o[0] ? UP_COLOR + '88' : DOWN_COLOR + '88' },
      })),
      xAxisIndex: 1, yAxisIndex: 1, barMaxWidth: 6 },
    // ── MA5 ────────────────────────────────────────────────────
    { name: 'MA5',  type: 'line', data: ma5,  xAxisIndex: 0, yAxisIndex: 0,
      smooth: true, symbol: 'none', lineStyle: { color: '#ffffff', width: 1.2 },
      tooltip: { show: true } },
    // ── MA10 ──────────────────────────────────────────────────
    { name: 'MA10', type: 'line', data: ma10, xAxisIndex: 0, yAxisIndex: 0,
      smooth: true, symbol: 'none', lineStyle: { color: '#fbbf24', width: 1.2 },
      tooltip: { show: true } },
    // ── MA20 ──────────────────────────────────────────────────
    { name: 'MA20', type: 'line', data: ma20, xAxisIndex: 0, yAxisIndex: 0,
      smooth: true, symbol: 'none', lineStyle: { color: '#c084fc', width: 1.2 },
      tooltip: { show: true } },
  ]

  // 重新构造成交量序列（OHLC索引问题修复）
  series[1].data = ohlc.map((o, i) => ({
    value: volumes[i],
    itemStyle: { color: o[1] >= o[0] ? UP_COLOR + '88' : DOWN_COLOR + '88' },
  }))

  const xAxis = [
    { type: 'category', data: times, gridIndex: 0, boundaryGap: true,
      axisLine: { lineStyle: { color: '#2d3748' } },
      axisLabel: { color: '#6b7280', fontSize: 9, interval: Math.max(0, Math.floor(times.length / 5) - 1) },
      splitLine: { show: false } },
    { type: 'category', data: times, gridIndex: 1, boundaryGap: true,
      axisLine: { lineStyle: { color: '#2d3748' } },
      axisLabel: { show: false }, splitLine: { show: false } },
  ]

  const yAxis = [
    { type: 'value', scale: true, gridIndex: 0, position: 'left', min: priceMin, max: priceMax,
      axisLine: { show: false },
      axisLabel: { color: '#6b7280', fontSize: 9, formatter: v => v.toFixed(0) },
      splitLine: { lineStyle: { color: '#1f2937', type: 'dashed' } } },
    { type: 'value', scale: true, gridIndex: 1, position: 'left',
      axisLine: { show: false }, axisLabel: { show: false }, splitLine: { show: false } },
  ]

  if (hasSub) {
    const xIdx = 2, yIdx = 2
    xAxis.push({ type: 'category', data: times, gridIndex: xIdx, boundaryGap: true,
      axisLine: { lineStyle: { color: '#2d3748' } },
      axisLabel: { show: false }, splitLine: { show: false } })
    yAxis.push({ type: 'value', scale: true, gridIndex: xIdx, position: 'left',
      axisLine: { show: false }, axisLabel: { show: false }, splitLine: { show: false } })

    if (activeIndicators.includes('MACD')) {
      const { dif, dea, macd } = calcMACD(closes)
      series.push(
        { name: 'DIF', type: 'line', data: dif, xAxisIndex: xIdx, yAxisIndex: yIdx, smooth: true, symbol: 'none', lineStyle: { color: '#60a5fa', width: 1 } },
        { name: 'DEA', type: 'line', data: dea, xAxisIndex: xIdx, yAxisIndex: yIdx, smooth: true, symbol: 'none', lineStyle: { color: '#f87171', width: 1 } },
        { name: 'MACD', type: 'bar', data: macd.map(v => ({ value: Math.abs(v), itemStyle: { color: v >= 0 ? '#ef4444' : '#22c55e' } })), xAxisIndex: xIdx, yAxisIndex: yIdx, barMaxWidth: 4 },
      )
    }
    if (activeIndicators.includes('BOLL')) {
      const { mid, upper, lower } = calcBOLL(closes)
      series.push(
        { name: 'BOLL', type: 'line', data: ohlc.map((_, i) => [_, i, i, i]), xAxisIndex: 0, yAxisIndex: 0,
          smooth: true, symbol: 'none', lineStyle: { color: '#a78bfa', width: 1, type: 'dashed' }, tooltip: { show: false } },
        { name: 'BOLL-MID', type: 'line', data: mid, xAxisIndex: xIdx, yAxisIndex: yIdx, smooth: true, symbol: 'none', lineStyle: { color: '#a78bfa', width: 1 } },
        { name: 'BOLL-UP',  type: 'line', data: upper, xAxisIndex: xIdx, yAxisIndex: yIdx, smooth: true, symbol: 'none', lineStyle: { color: '#a78bfa', width: 1 } },
        { name: 'BOLL-LOW', type: 'line', data: lower, xAxisIndex: xIdx, yAxisIndex: yIdx, smooth: true, symbol: 'none', lineStyle: { color: '#a78bfa', width: 1 } },
      )
    }
    if (activeIndicators.includes('KDJ')) {
      const { k, d, j } = calcKDJ(highs, lows, closes)
      series.push(
        { name: 'K', type: 'line', data: k, xAxisIndex: xIdx, yAxisIndex: yIdx, smooth: true, symbol: 'none', lineStyle: { color: '#f87171', width: 1 } },
        { name: 'D', type: 'line', data: d, xAxisIndex: xIdx, yAxisIndex: yIdx, smooth: true, symbol: 'none', lineStyle: { color: '#60a5fa', width: 1 } },
        { name: 'J', type: 'line', data: j, xAxisIndex: xIdx, yAxisIndex: yIdx, smooth: true, symbol: 'none', lineStyle: { color: '#fbbf24', width: 1 } },
      )
    }
  }

  return {
    backgroundColor: 'transparent', grid, xAxis, yAxis, series,
    tooltip: {
      trigger: 'axis', type: 'cross', axisPointer: { lineStyle: { color: '#374151' } },
      backgroundColor: '#1a1e2e', borderColor: '#374151', textStyle: { color: '#9ca3af', fontSize: 11 },
      formatter: (params) => {
        const kp = params.find(p => p.seriesName === 'K线')
        if (!kp) return ''
        const idx = kp.dataIndex
        const [o, c, l, h] = ohlc[idx]
        const chg = changes[idx]; const sign = chg >= 0 ? '+' : ''
        const col = c >= o ? UP_COLOR : DOWN_COLOR
        return `<span style="color:#6b7280;font-size:10px">${kp.axisValue}</span><br/>`
          + `<span style="color:#9ca3af;font-size:10px">开</span> <span style="color:#e5e7eb;font-size:11px">${o.toFixed(2)}</span><br/>`
          + `<span style="color:#9ca3af;font-size:10px">高</span> <span style="color:#e5e7eb;font-size:11px">${h.toFixed(2)}</span><br/>`
          + `<span style="color:#9ca3af;font-size:10px">低</span> <span style="color:#e5e7eb;font-size:11px">${l.toFixed(2)}</span><br/>`
          + `<span style="color:#9ca3af;font-size:10px">收</span> <span style="color:${col};font-size:11px">${c.toFixed(2)}</span> `
          + `<span style="color:${chg >= 0 ? UP_COLOR : DOWN_COLOR};font-size:10px">${sign}${chg.toFixed(2)}%</span>`
      },
    },
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1, ...(hasSub ? [2] : [])], start: 90, end: 100, zoomOnMouseWheel: true },
      { type: 'slider', xAxisIndex: [0, 1, ...(hasSub ? [2] : [])], start: 90, end: 100, height: 10, bottom: 1,
        borderColor: '#2d3748', fillerColor: 'rgba(59,130,246,0.12)',
        handleStyle: { color: '#60a5fa', borderColor: '#60a5fa' },
        textStyle: { color: '#6b7280', fontSize: 9 },
        dataBackground: { lineStyle: { color: '#374151' }, areaStyle: { color: 'rgba(59,130,246,0.06)' } },
        selectedDataBackground: { lineStyle: { color: '#60a5fa' }, areaStyle: { color: 'rgba(59,130,246,0.12)' } } },
    ],
  }
}

// ── 统一入口 ────────────────────────────────────────────────────
function buildOption(hist, activeIndicators, chartType) {
  if (!hist || !hist.length) {
    chartError.value = '暂无历史数据'
    return { backgroundColor: 'transparent', title: { text: '暂无历史数据', left: 'center', top: 'center', textStyle: { color: '#6b7280', fontSize: 12 } } }
  }
  chartError.value = ''
  if (chartType === 'line') return _buildLineChart(hist, activeIndicators)
  return _buildCandleChart(hist, activeIndicators)
}

// ── 核心渲染 ────────────────────────────────────────────────────
async function fetchAndRender() {
  chartError.value = ''; isLoading.value = true
  try {
    const res = await fetch(props.url)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    const chartType = data.chart_type || 'candlestick'
    const hist = _sanitize(data.history || [], chartType)
    console.info(`[IndexLineChart] ${props.url} → chartType=${chartType}, hist=${hist.length}`)
    if (!chartInstance) chartInstance = window.echarts.init(chartRef.value, null, { renderer: 'canvas' })
    chartInstance.setOption(buildOption(hist, props.indicators || [], chartType), { notMerge: true })
  } catch (e) {
    chartError.value = `加载失败: ${e.message}`
    console.error('[IndexLineChart]', e)
  } finally {
    isLoading.value = false
  }
}

function retryChart() { chartError.value = ''; fetchAndRender() }

watch(() => [props.url, props.indicators], () => { fetchAndRender() }, { deep: true })

onMounted(async () => {
  await new Promise(r => setTimeout(r, 0))
  if (chartRef.value && window.echarts) {
    chartInstance = window.echarts.init(chartRef.value, null, { renderer: 'canvas' })
    resizeObserver = new ResizeObserver(() => chartInstance?.resize())
    resizeObserver.observe(chartRef.value)
    fetchAndRender()
  }
})

onUnmounted(() => {
  resizeObserver?.disconnect()
  chartInstance?.dispose()
  chartInstance = null
})
</script>
