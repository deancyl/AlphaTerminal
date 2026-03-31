<template>
  <div class="w-full h-full min-h-[120px] relative">
    <div v-if="chartError" class="absolute inset-0 z-10 flex flex-col items-center justify-center bg-terminal-bg/90 rounded">
      <div class="text-2xl mb-2">📊</div>
      <div class="text-terminal-dim text-xs text-center px-4">{{ chartError }}</div>
      <button class="mt-2 px-3 py-1 text-[10px] rounded border border-gray-600 text-terminal-dim hover:border-terminal-accent/40 transition" @click="retryChart">重试</button>
    </div>
    <div v-if="isLoading" class="absolute inset-0 flex items-end justify-center pb-4 pointer-events-none">
      <div class="flex gap-1 items-end opacity-40">
        <div v-for="i in 24" :key="i" class="w-1 bg-terminal-accent rounded-t animate-pulse" :style="{ height: `${30 + ((i * 37) % 60)}%` }"></div>
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

// ─────────────────────────────────────────────────────────────────
// A股配色常量
const UP   = '#ef232a'   // 涨（收 >= 开）
const DOWN = '#14b143'   // 跌（收 < 开）

// ─────────────────────────────────────────────────────────────────
// 数据清洗：保留全部原始字段，修复 high<low 问题
// ─────────────────────────────────────────────────────────────────
function _sanitize(raw) {
  // 金融数据神圣不可侵犯：前端只做类型转换，不修改任何数值
  if (!Array.isArray(raw) || !raw.length) return []
  return raw.map(r => ({
    date:       r.date   || String(r.timestamp || ''),
    open:       Number(r.open)  || 0,
    close:      Number(r.close) || 0,
    high:       Number(r.high)  || 0,
    low:        Number(r.low)   || 0,
    volume:     Number(r.volume) || 0,
    change_pct: Number(r.change_pct) || 0,
  }))
}

// ─────────────────────────────────────────────────────────────────
// 指标计算
// ─────────────────────────────────────────────────────────────────

// MA 简单移动平均
function calcMA(data, n) {
  return data.map((_, i) => {
    if (i < n - 1) return null
    const slice = data.slice(i - n + 1, i + 1)
    return +(slice.reduce((a, b) => a + b, 0) / n).toFixed(3)
  })
}

// EMA 指数移动平均
function calcEMA(data, n) {
  const k = 2 / (n + 1)
  const result = []
  let ema = data[0]
  for (let i = 0; i < data.length; i++) {
    ema = i === 0 ? data[0] : data[i] * k + ema * (1 - k)
    result.push(+ema.toFixed(4))
  }
  return result
}

// BOLL (20, 2) — 叠加在主图 gridIndex: 0
function calcBOLL(closes) {
  const period = 20
  const mid = [], upper = [], lower = []
  for (let i = 0; i < closes.length; i++) {
    if (i < period - 1) { mid.push('-'); upper.push('-'); lower.push('-'); continue }
    const slice = closes.slice(i - period + 1, i + 1)
    const mean  = slice.reduce((a, b) => a + b, 0) / period
    const std   = Math.sqrt(slice.reduce((a, b) => a + (b - mean) ** 2, 0) / period)
    mid.push(+mean.toFixed(3))
    upper.push(+(mean + 2 * std).toFixed(3))
    lower.push(+(mean - 2 * std).toFixed(3))
  }
  return { mid, upper, lower }
}

// MACD (12, 26, 9) — 副图 gridIndex: 2
function calcMACD(closes) {
  const ema12 = calcEMA(closes, 12)
  const ema26 = calcEMA(closes, 26)
  const dif   = ema12.map((v, i) => +(v - ema26[i]).toFixed(4))
  const dea   = calcEMA(dif, 9)
  const macd  = dif.map((v, i) => +((v - dea[i]) * 2).toFixed(4))
  return { dif, dea, macd }
}

// KDJ (9, 3, 3) — 副图 gridIndex: 2
function calcKDJ(closes, highs, lows, n = 9) {
  const k = [], d = [], j = []
  for (let i = 0; i < closes.length; i++) {
    if (i < n - 1) { k.push('-'); d.push('-'); j.push('-'); continue }
    const rh = Math.max(...highs.slice(i - n + 1, i + 1))
    const rl = Math.min(...lows.slice(i - n + 1, i + 1))
    const rsv = rh === rl ? 50 : (closes[i] - rl) / (rh - rl) * 100
    const pk  = k[i - 1] !== '-' ? k[i - 1] : 50
    const pd  = d[i - 1] !== '-' ? d[i - 1] : 50
    const nk  = +(2/3 * pk + 1/3 * rsv).toFixed(2)
    const nd  = +(2/3 * pd + 1/3 * nk).toFixed(2)
    k.push(nk); d.push(nd); j.push(+(3 * nk - 2 * nd).toFixed(2))
  }
  return { k, d, j }
}

// W&R (10) — 副图 gridIndex: 2
function calcWR(closes, highs, lows, n = 10) {
  return closes.map((_, i) => {
    if (i < n - 1) return null
    const rh = Math.max(...highs.slice(i - n + 1, i + 1))
    const rl = Math.min(...lows.slice(i - n + 1, i + 1))
    if (rh === rl) return 0
    return +((rh - closes[i]) / (rh - rl) * -100).toFixed(2)
  })
}

// ─────────────────────────────────────────────────────────────────
// 构建 K 线图（主图叠加 BOLL/MA + 固定成交量 + 互斥指标副图）
// ─────────────────────────────────────────────────────────────────
function buildKLineOption(hist, activeIndicators) {
  const times   = hist.map(h => h.date ? h.date.slice(5) : '')
  const closes  = hist.map(h => h.close)
  const highs   = hist.map(h => h.high)
  const lows    = hist.map(h => h.low)
  const volumes = hist.map(h => h.volume)
  const changes = hist.map(h => h.change_pct)

  // Y轴锚定真实价格区间
  const yMin = +(Math.min(...closes) * 0.997).toFixed(2)
  const yMax = +(Math.max(...closes) * 1.003).toFixed(2)

  // 当前激活的副图指标（互斥，取第一个）
  const subInd = ['MACD', 'KDJ', 'WR'].find(i => (activeIndicators || []).includes(i)) || null
  const showBOLL = (activeIndicators || []).includes('BOLL')

  // 布局参数
  const volH  = 12                         // 成交量占%
  const subH  = subInd ? 18 : 0            // 指标副图占%（无副图则隐藏）
  const kH    = 100 - volH - subH - 2      // K线主图（留2%间隙）
  const volTop = kH + 1
  const subTop = subInd ? volTop + volH + 1 : volTop + volH

  const grid = [
    { top: 5,   height: `${kH}%`,   right: 8, left: 50, bottom: 0 },
    { top: `${volTop}%`,  height: `${volH}%`,  right: 8, left: 50, bottom: 0 },
  ]
  if (subInd) grid.push({ top: `${subTop}%`, height: `${subH}%`, right: 8, left: 50, bottom: 0 })

  // ── series[0]: K线烛台 ────────────────────────────────────────
  const kSeries = {
    name: 'K线', type: 'candlestick',
    // ECharts candlestick: [open, close, lowest, highest]
    // A股: color(涨=红), color0(跌=绿)
    data: hist.map(h => {
      if (Number(h.close) < Number(h.open)) {
        console.warn(`[KLine DIAG] DOWN! O=${Number(h.open)} C=${Number(h.close)} L=${Number(h.low)} H=${Number(h.high)}`)
      }
      return [Number(h.open), Number(h.close), Number(h.low), Number(h.high)]
    }),
    xAxisIndex: 0, yAxisIndex: 0,
    itemStyle: {
      color:     UP,   color0:     DOWN,
      borderColor:     UP,   borderColor0:     DOWN,
    },
    // Task 2: Y轴最新价虚线标尺
    markLine: {
      silent: true,
      symbol: 'none',
      lineStyle: { color: '#fbbf24', width: 1, type: 'dashed' },
      data: [
        {
          yAxis: hist[hist.length - 1]?.close,
          label: {
            position: 'insideEndTop',
            formatter: () => hist[hist.length - 1]?.close?.toFixed(2),
            backgroundColor: '#fbbf24',
            color: '#000',
            fontSize: 10,
            padding: [2, 4],
            borderRadius: 2,
          },
        },
      ],
    },
  }

  // ── series[1..3]: MA 均线（叠加主图） ──────────────────────────
  const maSeries = [
    { name: 'MA5',  data: calcMA(closes, 5),  color: '#ffffff', width: 1 },
    { name: 'MA10', data: calcMA(closes, 10), color: '#fbbf24', width: 1 },
    { name: 'MA20', data: calcMA(closes, 20), color: '#c084fc', width: 1 },
  ].map(cfg => ({
    ...cfg, type: 'line', xAxisIndex: 0, yAxisIndex: 0,
    smooth: true, symbol: 'none',
    lineStyle: { color: cfg.color, width: cfg.width },
    tooltip: { show: true },
  }))

  // ── series[4]: BOLL（叠加主图，与MA同 yAxisIndex:0） ──────────
  const bollSeries = showBOLL ? (() => {
    const { mid, upper, lower } = calcBOLL(closes)
    return [
      { name: 'BOLL-M', data: mid,   color: '#a78bfa', width: 1, type: 'line', smooth: true, symbol: 'none',
        xAxisIndex: 0, yAxisIndex: 0, lineStyle: { color: '#a78bfa', width: 1.2 } },
      { name: 'BOLL-U', data: upper, color: '#a78bfa', width: 1, type: 'line', smooth: true, symbol: 'none',
        xAxisIndex: 0, yAxisIndex: 0, lineStyle: { color: '#a78bfa', width: 1, type: 'dashed' } },
      { name: 'BOLL-L', data: lower, color: '#a78bfa', width: 1, type: 'line', smooth: true, symbol: 'none',
        xAxisIndex: 0, yAxisIndex: 0, lineStyle: { color: '#a78bfa', width: 1, type: 'dashed' } },
    ]
  })() : []

  // ── series[5]: 成交量（固定 gridIndex:1，颜色跟随K线阴阳） ──────
  const volSeries = {
    name: '成交量', type: 'bar',
    data: hist.map((h, i) => ({
      value: h.volume,
      itemStyle: {
        color: h.close >= h.open
          ? UP + Math.min(80, Math.round(0.7 * 100)).toString(16).padStart(2,'0')
          : DOWN + Math.min(80, Math.round(0.7 * 100)).toString(16).padStart(2,'0'),
      },
    })),
    xAxisIndex: 1, yAxisIndex: 1, barMaxWidth: 6,
  }

  const series = [kSeries, ...maSeries, ...bollSeries, volSeries]

  // ── 副图指标（gridIndex:2，xAxisIndex:2） ───────────────────────
  if (subInd) {
    const xIdx = 2, yIdx = 2
    if (subInd === 'MACD') {
      const { dif, dea, macd } = calcMACD(closes)
      series.push(
        { name: 'DIF', type: 'line', data: dif, xAxisIndex: xIdx, yAxisIndex: yIdx,
          smooth: true, symbol: 'none', lineStyle: { color: '#60a5fa', width: 1.2 } },
        { name: 'DEA', type: 'line', data: dea, xAxisIndex: xIdx, yAxisIndex: yIdx,
          smooth: true, symbol: 'none', lineStyle: { color: '#f87171', width: 1.2 } },
        { name: 'MACD', type: 'bar',
          data: macd.map(v => ({ value: Math.abs(v), itemStyle: { color: v >= 0 ? UP : DOWN } })),
          xAxisIndex: xIdx, yAxisIndex: yIdx, barMaxWidth: 4 },
      )
    }
    if (subInd === 'KDJ') {
      const { k, d, j } = calcKDJ(closes, highs, lows)
      series.push(
        { name: 'K', type: 'line', data: k, xAxisIndex: xIdx, yAxisIndex: yIdx,
          smooth: true, symbol: 'none', lineStyle: { color: '#f87171', width: 1.2 } },
        { name: 'D', type: 'line', data: d, xAxisIndex: xIdx, yAxisIndex: yIdx,
          smooth: true, symbol: 'none', lineStyle: { color: '#60a5fa', width: 1.2 } },
        { name: 'J', type: 'line', data: j, xAxisIndex: xIdx, yAxisIndex: yIdx,
          smooth: true, symbol: 'none', lineStyle: { color: '#fbbf24', width: 1.2 } },
      )
    }
    if (subInd === 'WR') {
      const wr = calcWR(closes, highs, lows)
      series.push(
        { name: 'W&R', type: 'line',
          data: wr.map(v => v == null ? '-' : v),
          xAxisIndex: xIdx, yAxisIndex: yIdx,
          smooth: true, symbol: 'none',
          lineStyle: { color: '#fb923c', width: 1.2 },
          markLine: {
            silent: true, symbol: 'none',
            lineStyle: { color: '#4b5563', type: 'dashed', width: 1 },
            data: [{ yAxis: -20 }, { yAxis: -80 }],
            label: { show: true, formatter: '{c}', fontSize: 8, color: '#6b7280' },
          } },
      )
    }
  }

  // ── X轴（各区域共享时间轴） ───────────────────────────────────
  const xAxisBase = {
    type: 'category', data: times, boundaryGap: true,
    axisLine: { lineStyle: { color: '#2d3748' } },
    splitLine: { show: false },
  }
  const xAxis = [
    { ...xAxisBase, gridIndex: 0,
      axisLabel: { color: '#6b7280', fontSize: 9, interval: Math.max(0, Math.floor(times.length / 5) - 1) } },
    { ...xAxisBase, gridIndex: 1, axisLabel: { show: false } },
  ]
  if (subInd) xAxis.push({ ...xAxisBase, gridIndex: 2, axisLabel: { show: false } })

  // ── Y轴 ────────────────────────────────────────────────────────
  const yAxis = [
    { type: 'value', scale: true, gridIndex: 0, position: 'left',
      min: yMin, max: yMax,
      axisLine: { show: false },
      axisLabel: { color: '#6b7280', fontSize: 9, formatter: v => v.toFixed(0) },
      splitLine: { lineStyle: { color: '#1f2937', type: 'dashed' } } },
    { type: 'value', scale: true, gridIndex: 1, position: 'left',
      axisLine: { show: false }, axisLabel: { show: false }, splitLine: { show: false } },
  ]
  if (subInd) yAxis.push({ type: 'value', scale: true, gridIndex: 2, position: 'left',
    axisLine: { show: false },
    axisLabel: { color: '#6b7280', fontSize: 9 },
    splitLine: { lineStyle: { color: '#1f2937', type: 'dashed' } },
    max: subInd === 'WR' ? 0 : 'auto', min: subInd === 'WR' ? -100 : 'auto',
  })

  return {
    backgroundColor: 'transparent',
    grid, xAxis, yAxis, series,
    tooltip: {
      trigger: 'axis', type: 'cross',
      axisPointer: {
        type: 'cross',
        lineStyle: { color: '#9ca3af', width: 1, type: 'dashed' },
        crossStyle: { color: '#9ca3af', width: 1 },
      },
      backgroundColor: 'rgba(26,30,46,0.96)', borderColor: '#4b5563',
      textStyle: { color: '#9ca3af', fontSize: 11 },
      formatter(params) {
        const kp = params.find(p => p.seriesName === 'K线')
        if (!kp) return ''
        const idx  = kp.dataIndex
        const h   = hist[idx]
        const o   = h.open, c = h.close, l = h.low, hi = h.high
        const chg = h.change_pct; const sign = chg >= 0 ? '+' : ''
        const col = c >= o ? UP : DOWN
        const vol = (h.volume / 1e8).toFixed(2)
        return `<span style="color:#6b7280;font-size:10px">${kp.axisValue}</span><br/>`
          + `<span style="color:#9ca3af;font-size:10px">开</span> <span style="color:#e5e7eb;font-size:11px">${o.toFixed(2)}</span><br/>`
          + `<span style="color:#9ca3af;font-size:10px">高</span> <span style="color:#e5e7eb;font-size:11px">${hi.toFixed(2)}</span><br/>`
          + `<span style="color:#9ca3af;font-size:10px">低</span> <span style="color:#e5e7eb;font-size:11px">${l.toFixed(2)}</span><br/>`
          + `<span style="color:#9ca3af;font-size:10px">收</span> <span style="color:${col};font-size:11px">${c.toFixed(2)}</span> `
          + `<span style="color:${chg >= 0 ? UP : DOWN};font-size:10px">${sign}${chg.toFixed(2)}%</span><br/>`
          + `<span style="color:#9ca3af;font-size:10px">量</span> <span style="color:#9ca3af;font-size:11px">${vol}亿</span>`
      },
    },
    // DataZoom: 同时控制所有分图 x 轴
    dataZoom: [
      { type: 'inside', xAxisIndex: [...Array(xAxis.length).keys()], start: 90, end: 100, zoomOnMouseWheel: true },
      { type: 'slider', xAxisIndex: [0], start: 90, end: 100, height: 10, bottom: 1,
        borderColor: '#2d3748', fillerColor: 'rgba(59,130,246,0.10)',
        handleStyle: { color: '#60a5fa', borderColor: '#60a5fa' },
        textStyle: { color: '#6b7280', fontSize: 9 },
        dataBackground: { lineStyle: { color: '#374151' }, areaStyle: { color: 'rgba(59,130,246,0.06)' } } },
    ],
  }
}

// ─────────────────────────────────────────────────────────────────
// 分时图
// ─────────────────────────────────────────────────────────────────
function buildLineOption(hist, activeIndicators) {
  const times  = hist.map(h => h.time ? h.time.slice(11, 16) : (h.date || ''))
  const prices  = hist.map(h => h.price)
  const changes = hist.map(h => h.change_pct || 0)

  // 均价线
  const avg = []
  let sum = 0
  for (let i = 0; i < prices.length; i++) { sum += prices[i]; avg.push(+(sum / (i + 1)).toFixed(3)) }

  const upCount = prices.filter((p, i) => i > 0 && p > prices[i - 1]).length
  const lineColor = upCount >= prices.length / 2 ? UP : DOWN

  const kH   = 75; const volH = 25
  const volTop = kH

  const series = [
    { name: '价格', type: 'line', data: prices, smooth: 0.3, symbol: 'none',
      lineStyle: { color: lineColor, width: 1.5 },
      areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [{ offset: 0, color: lineColor + '30' }, { offset: 1, color: lineColor + '00' }] } } },
    { name: '均价', type: 'line', data: avg, smooth: 0.3, symbol: 'none',
      lineStyle: { color: '#fbbf24', width: 1, type: 'dashed' } },
  ]

  return {
    backgroundColor: 'transparent',
    grid: [
      { top: 5, height: `${kH}%`,  right: 8, left: 50, bottom: 0 },
      { top: `${volTop}%`, height: `${volH}%`, right: 8, left: 50, bottom: 0 },
    ],
    xAxis: [
      { type: 'category', data: times, boundaryGap: false, gridIndex: 0,
        axisLine: { lineStyle: { color: '#2d3748' } },
        axisLabel: { color: '#6b7280', fontSize: 9, interval: Math.max(0, Math.floor(times.length / 6) - 1) },
        splitLine: { show: false } },
      { type: 'category', data: times, boundaryGap: false, gridIndex: 1,
        axisLine: { lineStyle: { color: '#2d3748' } },
        axisLabel: { show: false }, splitLine: { show: false } },
    ],
    yAxis: [
      { type: 'value', scale: true, gridIndex: 0, position: 'left',
        axisLine: { show: false },
        axisLabel: { color: '#6b7280', fontSize: 9, formatter: v => v.toFixed(2) },
        splitLine: { lineStyle: { color: '#1f2937', type: 'dashed' } } },
      { type: 'value', scale: true, gridIndex: 1, position: 'left',
        axisLine: { show: false }, axisLabel: { show: false }, splitLine: { show: false } },
    ],
    series,
    tooltip: {
      trigger: 'axis', type: 'cross', axisPointer: { lineStyle: { color: '#374151' } },
      backgroundColor: '#1a1e2e', borderColor: '#374151', textStyle: { color: '#9ca3af', fontSize: 11 },
      formatter: (params) => {
        const p = params[0]
        if (!p) return ''
        const idx = p.dataIndex
        const chg = changes[idx]; const sign = chg >= 0 ? '+' : ''
        const a   = avg[idx]
        return `<span style="color:#6b7280;font-size:10px">${p.axisValue}</span><br/>`
          + `<span style="color:#9ca3af;font-size:10px">价</span> <span style="color:${lineColor};font-size:11px">${(prices[idx] || 0).toFixed(3)}</span><br/>`
          + `<span style="color:#9ca3af;font-size:10px">均</span> <span style="color:#fbbf24;font-size:11px">${a.toFixed(3)}</span><br/>`
          + `<span style="color:${chg >= 0 ? UP : DOWN};font-size:10px">${sign}${chg.toFixed(2)}%</span>`
      },
    },
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 90, end: 100, zoomOnMouseWheel: true },
      { type: 'slider', xAxisIndex: [0], start: 90, end: 100, height: 10, bottom: 1,
        borderColor: '#2d3748', fillerColor: 'rgba(59,130,246,0.10)',
        handleStyle: { color: '#60a5fa', borderColor: '#60a5fa' },
        textStyle: { color: '#6b7280', fontSize: 9 },
        dataBackground: { lineStyle: { color: '#374151' }, areaStyle: { color: 'rgba(59,130,246,0.06)' } } },
    ],
  }
}

// ─────────────────────────────────────────────────────────────────
// 统一入口
// ─────────────────────────────────────────────────────────────────
function buildOption(raw, activeIndicators, chartType) {
  const hist = _sanitize(raw)
  if (!hist || !hist.length) {
    chartError.value = '暂无历史数据'
    return { backgroundColor: 'transparent', title: { text: '暂无历史数据', left: 'center', top: 'center', textStyle: { color: '#6b7280', fontSize: 12 } } }
  }
  chartError.value = ''
  if (chartType === 'line') return buildLineOption(hist, activeIndicators)
  return buildKLineOption(hist, activeIndicators)
}

// ─────────────────────────────────────────────────────────────────
// 渲染循环
// ─────────────────────────────────────────────────────────────────
async function fetchAndRender() {
  chartError.value = ''; isLoading.value = true
  try {
    const res = await fetch(props.url + `&_t=${Date.now()}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data    = await res.json()
    const chartType = data.chart_type || 'candlestick'
    const hist    = _sanitize(data.history || [])
    console.info(`[KLine] ${props.url} chartType=${chartType} hist=${hist.length} first={O:${hist[0]?.open} C:${hist[0]?.close}}`)
    if (!chartInstance) chartInstance = window.echarts.init(chartRef.value, null, { renderer: 'canvas' })
    chartInstance.clear()
    chartInstance.setOption(buildOption(hist, props.indicators || [], chartType), { notMerge: true })
  } catch (e) {
    chartError.value = `加载失败: ${e.message}`
    console.error('[KLine]', e)
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
