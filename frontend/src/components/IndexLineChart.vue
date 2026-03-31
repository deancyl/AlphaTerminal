<template>
  <!-- Error Boundary + Fallback UI -->
  <div class="w-full h-full min-h-[120px] relative">
    <div v-if="chartError" class="absolute inset-0 flex flex-col items-center justify-center z-10 bg-terminal-bg/90 rounded">
      <div class="text-2xl mb-2">📊</div>
      <div class="text-terminal-dim text-xs text-center px-4">{{ chartError }}</div>
      <button class="mt-2 px-3 py-1 text-[10px] rounded border border-gray-600 text-terminal-dim hover:border-terminal-accent/40 transition"
              @click="retryChart">重试</button>
    </div>
    <div ref="chartRef" class="w-full h-full"></div>
    <!-- Loading skeleton -->
    <div v-if="isLoading" class="absolute inset-0 flex items-end justify-center pb-4 pointer-events-none">
      <div class="flex gap-1 items-end">
        <div v-for="i in 20" :key="i" class="w-1 bg-terminal-accent/30 rounded-t animate-pulse"
             :style="{ height: `${20 + Math.random() * 60}%` }"></div>
      </div>
    </div>
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

const chartRef    = ref(null)
const chartError  = ref('')
const isLoading   = ref(false)
let chartInstance = null
let resizeObserver = null

// ── Schema 校验：打印原始数据快照（调试用）───────────────────────────
function _debugSnapshot(hist) {
  if (!hist || !hist.length) return
  const first = hist[0]
  const keys  = Object.keys(first)
  console.group(`[IndexLineChart] 📊 ${props.name} 原始数据快照`)
  console.log('字段列表:', keys)
  console.log('第1条:', JSON.stringify(first))
  console.log('OHLC 示例 (raw):', first.open, first.high, first.low, first.close)
  // 验证 high >= low
  if (first.high < first.low) {
    console.warn('⚠️ high < low 检测到! 数值颠倒. high=%s low=%s swap 修正', first.high, first.low)
  }
  console.groupEnd()
}

// ── 数据清洗：修复 high/low 颠倒、过滤无效行 ─────────────────────────
function _sanitize(raw) {
  if (!Array.isArray(raw) || raw.length === 0) return []
  const cleaned = raw.map((r, idx) => {
    let o = Number(r.open)  || 0
    let c = Number(r.close) || Number(r.price) || 0
    let h = Number(r.high) || 0
    let l = Number(r.low)  || 0
    let v = Number(r.volume) || 0
    // 修复: 确保 high >= low
    if (h < l) { const tmp = h; h = l; l = tmp }
    // 过滤: 有效K线必须 o,c,h,l 全部 > 0
    if (o <= 0 || c <= 0 || h <= 0 || l <= 0) {
      return null
    }
    // 修复: high 至少 >= o 和 c
    h = Math.max(h, o, c)
    l = Math.min(l, o, c)
    return {
      date:   r.date   || String(r.timestamp || ''),
      open:   o,
      close:  c,
      high:   h,
      low:    l,
      volume: v,
      change_pct: Number(r.change_pct) || 0,
    }
  }).filter(Boolean)
  console.info(`[IndexLineChart] 数据清洗后: ${cleaned.length}/${raw.length} 条有效`)
  return cleaned
}

// ── 指标计算 ───────────────────────────────────────────────────────
function calcMACD(closes) {
  if (closes.length < 26) return { dif: [], dea: [], macd: [] }
  const ema12 = closes.map((_, i) => i === 0 ? closes[0] : null)
  const ema26 = closes.map((_, i) => i === 0 ? closes[0] : null)
  const k12 = 2 / 13, k26 = 2 / 27
  let e12 = closes[0], e26 = closes[0]
  const dif = [], dea = [], macd = []
  for (let i = 0; i < closes.length; i++) {
    e12 = i === 0 ? closes[0] : closes[i] * k12 + e12 * (1 - k12)
    e26 = i === 0 ? closes[0] : closes[i] * k26 + e26 * (1 - k26)
    dif.push(+e12 - e26)
  }
  let e9 = dif[0]
  for (let i = 0; i < dif.length; i++) {
    e9 = i === 0 ? dif[0] : dif[i] * (2/10) + e9 * (8/10)
    dea.push(e9)
    macd.push(+((dif[i] - e9) * 2).toFixed(3))
  }
  return { dif, dea, macd }
}

function calcBOLL(closes) {
  const period = 20
  const mid = [], upper = [], lower = []
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
    const nk = +(2/3 * pk + 1/3 * rsv).toFixed(2), nd = +(2/3 * pd + 1/3 * nk).toFixed(2)
    k.push(nk); d.push(nd); j.push(+(3 * nk - 2 * nd).toFixed(2))
  }
  return { k, d, j }
}

// ── ECharts Option 构造 ────────────────────────────────────────────
function buildOption(hist, activeIndicators) {
  if (!hist || !hist.length) {
    chartError.value = '暂无历史数据'
    return { backgroundColor: 'transparent', title: { text: '暂无历史数据', left: 'center', top: 'center', textStyle: { color: '#6b7280', fontSize: 12 } } }
  }

  // 数据校验
  const priceRange = { min: Infinity, max: -Infinity }
  hist.forEach(h => {
    if (h.high > priceRange.max) priceRange.max = h.high
    if (h.low  < priceRange.min) priceRange.min = h.low
  })
  const priceSpan = priceRange.max - priceRange.min
  if (priceSpan <= 0 || !isFinite(priceRange.min)) {
    chartError.value = `数据异常: 价格区间 ${priceRange.min}-${priceRange.max}`
    return { backgroundColor: 'transparent' }
  }

  console.info(`[IndexLineChart] Y轴范围: ${priceRange.min.toFixed(2)} ~ ${priceRange.max.toFixed(2)} (跨度 ${priceSpan.toFixed(2)})`)

  // 构造 OHLC 数组
  const times   = hist.map(h => h.date ? h.date.slice(5) : '')
  const ohlc    = hist.map(h => [h.open, h.close, h.low, h.high])  // [开, 收, 低, 高]
  const volumes = hist.map(h => h.volume)
  const changes = hist.map(h => h.change_pct)
  const closes  = hist.map(h => h.close)
  const highs   = hist.map(h => h.high)
  const lows    = hist.map(h => h.low)

  // yAxis min/max 锚定真实数据（避免从0开始压缩）
  const yMin = +(priceRange.min * 0.998).toFixed(2)
  const yMax = +(priceRange.max * 1.002).toFixed(2)

  const hasSub = (activeIndicators || []).length > 0
  const kH   = hasSub ? 58 : 72
  const volH = 15
  const subH = hasSub ? 20 : 0
  const gap  = 3
  const volTop = kH + gap
  const subTop = hasSub ? volTop + volH + gap : kH + volH + gap * 2

  const grid = [
    { top: 5,   height: `${kH}%`,   right: 8, left: 50, bottom: 2 },
    { top: `${volTop}%`, height: `${volH}%`, right: 8, left: 50, bottom: 2 },
  ]
  if (hasSub) grid.push({ top: `${subTop}%`, height: `${subH}%`, right: 8, left: 50, bottom: 2 })

  const series = [
    {
      name: 'K线',
      type: 'candlestick',
      data: ohlc,
      xAxisIndex: 0, yAxisIndex: 0,
      itemStyle: {
        color:      '#ef4444', color0:     '#22c55e',
        borderColor:      '#ef4444', borderColor0: '#22c55e',
      },
    },
    {
      name: '成交量',
      type: 'bar',
      data: ohlc.map((o, i) => ({
        value: volumes[i],
        itemStyle: { color: o[1] >= o[0] ? '#ef444444' : '#22c55e44' },
      })),
      xAxisIndex: 1, yAxisIndex: 1, barMaxWidth: 6,
    },
  ]

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
    {
      type: 'value', scale: true, gridIndex: 0, position: 'left',
      min: yMin, max: yMax,
      axisLine: { show: false },
      axisLabel: { color: '#6b7280', fontSize: 9, formatter: v => v.toFixed(0) },
      splitLine: { lineStyle: { color: '#1f2937', type: 'dashed' } },
    },
    {
      type: 'value', scale: true, gridIndex: 1, position: 'left',
      axisLine: { show: false }, axisLabel: { show: false }, splitLine: { show: false },
    },
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
        { name: 'DIF', type: 'line', data: dif, xAxisIndex: xIdx, yAxisIndex: yIdx,
          smooth: true, symbol: 'none', lineStyle: { color: '#60a5fa', width: 1 } },
        { name: 'DEA', type: 'line', data: dea, xAxisIndex: xIdx, yAxisIndex: yIdx,
          smooth: true, symbol: 'none', lineStyle: { color: '#f87171', width: 1 } },
        { name: 'MACD', type: 'bar',
          data: macd.map(v => ({ value: Math.abs(v), itemStyle: { color: v >= 0 ? '#ef4444' : '#22c55e' } })),
          xAxisIndex: xIdx, yAxisIndex: yIdx, barMaxWidth: 4 },
      )
    }
    if (activeIndicators.includes('BOLL')) {
      const { mid, upper, lower } = calcBOLL(closes)
      series.push(
        { name: 'BOLL', type: 'line', data: ohlc.map((_, i) => [_, i, i, i]), xAxisIndex: 0, yAxisIndex: 0,
          smooth: true, symbol: 'none', lineStyle: { color: '#a78bfa', width: 1, type: 'dashed' }, tooltip: { show: false } },
        { name: 'BOLL-MID', type: 'line', data: mid, xAxisIndex: xIdx, yAxisIndex: yIdx,
          smooth: true, symbol: 'none', lineStyle: { color: '#a78bfa', width: 1 } },
        { name: 'BOLL-UP',  type: 'line', data: upper, xAxisIndex: xIdx, yAxisIndex: yIdx,
          smooth: true, symbol: 'none', lineStyle: { color: '#a78bfa', width: 1 } },
        { name: 'BOLL-LOW', type: 'line', data: lower, xAxisIndex: xIdx, yAxisIndex: yIdx,
          smooth: true, symbol: 'none', lineStyle: { color: '#a78bfa', width: 1 } },
      )
    }
    if (activeIndicators.includes('KDJ')) {
      const { k, d, j } = calcKDJ(highs, lows, closes)
      series.push(
        { name: 'K', type: 'line', data: k, xAxisIndex: xIdx, yAxisIndex: yIdx,
          smooth: true, symbol: 'none', lineStyle: { color: '#f87171', width: 1 } },
        { name: 'D', type: 'line', data: d, xAxisIndex: xIdx, yAxisIndex: yIdx,
          smooth: true, symbol: 'none', lineStyle: { color: '#60a5fa', width: 1 } },
        { name: 'J', type: 'line', data: j, xAxisIndex: xIdx, yAxisIndex: yIdx,
          smooth: true, symbol: 'none', lineStyle: { color: '#fbbf24', width: 1 } },
      )
    }
  }

  chartError.value = ''
  return {
    backgroundColor: 'transparent',
    grid, xAxis, yAxis, series,
    tooltip: {
      trigger: 'axis', type: 'cross',
      axisPointer: { lineStyle: { color: '#374151', width: 1 } },
      backgroundColor: '#1a1e2e', borderColor: '#374151',
      textStyle: { color: '#9ca3af', fontSize: 11 },
      formatter: (params) => {
        const kp = params.find(p => p.seriesName === 'K线')
        if (!kp) return ''
        const idx = kp.dataIndex
        const [o, c, l, h] = ohlc[idx]
        const chg = changes[idx]; const sign = chg >= 0 ? '+' : ''
        const up  = c >= o
        return `<span style="color:#6b7280;font-size:10px">${kp.axisValue}</span><br/>`
          + `<span style="color:#9ca3af;font-size:10px">开</span> <span style="color:#e5e7eb;font-size:11px">${o.toFixed(2)}</span><br/>`
          + `<span style="color:#9ca3af;font-size:10px">高</span> <span style="color:#e5e7eb;font-size:11px">${h.toFixed(2)}</span><br/>`
          + `<span style="color:#9ca3af;font-size:10px">低</span> <span style="color:#e5e7eb;font-size:11px">${l.toFixed(2)}</span><br/>`
          + `<span style="color:#9ca3af;font-size:10px">收</span> <span style="color:${up ? '#22c55e' : '#ef4444'};font-size:11px">${c.toFixed(2)}</span> `
          + `<span style="color:${chg >= 0 ? '#f87171' : '#4ade80'};font-size:10px">${sign}${chg.toFixed(2)}%</span>`
      },
    },
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1, ...(hasSub ? [2] : [])],
        start: 90, end: 100, zoomOnMouseWheel: true },
      { type: 'slider', xAxisIndex: [0, 1, ...(hasSub ? [2] : [])],
        start: 90, end: 100, height: 12, bottom: 1,
        borderColor: '#2d3748', fillerColor: 'rgba(59,130,246,0.12)',
        handleStyle: { color: '#60a5fa', borderColor: '#60a5fa' },
        textStyle: { color: '#6b7280', fontSize: 9 },
        dataBackground: { lineStyle: { color: '#374151' }, areaStyle: { color: 'rgba(59,130,246,0.06)' } },
        selectedDataBackground: { lineStyle: { color: '#60a5fa' }, areaStyle: { color: 'rgba(59,130,246,0.12)' } },
      },
    ],
  }
}

// ── 数据获取 + 渲染 ────────────────────────────────────────────────
async function fetchAndRender() {
  chartError.value = ''
  isLoading.value  = true
  try {
    const res = await fetch(props.url)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    const hist = _sanitize(data.history || [])
    _debugSnapshot(hist)
    if (!chartInstance) {
      chartInstance = window.echarts.init(chartRef.value, null, { renderer: 'canvas' })
    }
    chartInstance.setOption(buildOption(hist, props.indicators || []), { notMerge: true })
  } catch (e) {
    chartError.value = `加载失败: ${e.message}`
    console.error('[IndexLineChart] fetchAndRender error:', e)
  } finally {
    isLoading.value = false
  }
}

function retryChart() { chartError.value = ''; fetchAndRender() }

watch(() => [props.url, props.indicators], () => { fetchAndRender() }, { deep: true })

onMounted(async () => {
  await new Promise(r => setTimeout(r, 0))  // 等 DOM 就绪
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
