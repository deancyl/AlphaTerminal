<template>
  <div class="w-full h-full min-h-[120px] relative flex flex-col">

    <!-- ── Task 3: 顶部动态 Hover Bar ─────────────────────────────── -->
    <div class="shrink-0 flex flex-col border-b border-theme bg-theme/60">
      <div class="px-2 py-1 flex items-center justify-between">
        <span class="text-[11px] font-bold text-theme-primary tracking-wider">{{ currentName }}</span>
        <!-- 移动端全屏按钮 -->
        <button
          class="md:hidden ml-auto mr-1 px-1.5 py-0.5 text-[10px] rounded border border-terminal-accent/30 text-terminal-accent hover:bg-terminal-accent/10 transition-colors"
          title="横屏全屏"
          @click="useUiStore().openKlineFullscreen({ symbol: symbol || props.symbol, name: name || props.name })"
        >⛶ 全屏</button>
        <span v-if="isLoading" class="text-[10px] font-mono text-theme-tertiary animate-pulse">加载中…</span>
      </div>
      <div class="flex items-center gap-3 px-2 py-1">
        <span class="text-[13px] font-mono font-medium"
              :class="hoverBar.change_pct >= 0 ? 'text-bullish' : 'text-bearish'">
          {{ hoverBar.price != null ? hoverBar.price.toFixed(2) : '--' }}
        </span>
        <span class="text-[11px] font-mono" :class="hoverBar.change_pct >= 0 ? 'text-bullish' : 'text-bearish'">
          {{ hoverBar.change_pct >= 0 ? '+' : '' }}{{ hoverBar.change_pct?.toFixed(2) ?? '--' }}%
        </span>
        <span class="text-[10px] font-mono text-theme-secondary ml-auto">
          {{ hoverBar.time || '--' }}
        </span>
      </div>
      <template v-if="hoverBar.open != null">
        <div class="flex items-center gap-2 px-2 pb-1">
          <span class="text-[10px] font-mono text-theme-tertiary">开<span class="text-theme-primary ml-1">{{ hoverBar.open?.toFixed(2) }}</span></span>
          <span class="text-[10px] font-mono text-theme-tertiary">高<span class="text-bullish ml-1">{{ hoverBar.high?.toFixed(2) }}</span></span>
          <span class="text-[10px] font-mono text-theme-tertiary">低<span class="text-bearish ml-1">{{ hoverBar.low?.toFixed(2) }}</span></span>
          <span class="text-[10px] font-mono text-theme-tertiary">收<span class="text-theme-primary ml-1">{{ hoverBar.close?.toFixed(2) }}</span></span>
          <span class="text-[10px] font-mono text-theme-tertiary ml-auto">
            量<span class="text-theme-primary ml-1">{{ hoverBar.volume != null ? (hoverBar.volume >= 1e8 ? (hoverBar.volume / 1e8).toFixed(2) + '亿股' : (hoverBar.volume / 1e4).toFixed(2) + '万股') : '--' }}</span>
          </span>
        </div>
      </template>
    </div>

    <!-- ── Chart Area ─────────────────────────────────────────── -->
    <div class="flex-1 relative min-h-0">
      <div v-if="chartError" class="absolute inset-0 z-10 flex flex-col items-center justify-center bg-theme/90 rounded">
        <div class="text-2xl mb-2">📊</div>
        <div class="text-theme-tertiary text-xs text-center px-4">{{ chartError }}</div>
        <button class="mt-2 px-3 py-1 text-[10px] rounded border border-theme text-theme-tertiary hover:border-theme-accent transition" @click="retryChart">重试</button>
      </div>
      <div v-if="isLoading" class="absolute inset-0 flex items-end justify-center pb-4 pointer-events-none">
        <div class="flex gap-1 items-end opacity-40">
          <div v-for="i in 24" :key="i" class="w-1 bg-theme-accent rounded-t animate-pulse" :style="{ height: `${30 + ((i * 37) % 60)}%` }"></div>
        </div>
      </div>
      <div ref="chartRef" class="w-full h-full"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import { apiFetch } from '../utils/api.js'
import { logger } from '../utils/logger.js'
import { getChartColors, onThemeChange } from '../composables/useTheme.js'
import { useUiStore } from '../composables/useUiStore.js'

const props = defineProps({
  symbol:     { type: String, default: '000001' },
  name:       { type: String, default: '上证指数' },
  color:      { type: String, default: '#00ff88' },
  url:        { type: String, default: '/api/v1/market/history/000001' },
  indicators: { type: Array,  default: () => [] },
  // 叠加标的
  overlaySymbol: { type: String, default: '' },
  overlayName:   { type: String, default: '' },
})

const chartRef     = ref(null)
const chartError   = ref('')
const isLoading    = ref(false)
const chartType    = ref('candlestick')
const currentName  = ref('指标图表')

let   chartInstance = null
let   resizeObserver = null
const hoverBar      = ref({})   // Task 3: 动态 OHLCV 数据

// ─────────────────────────────────────────────────────────────────
// A股配色常量（从主题系统中读取）
// ─────────────────────────────────────────────────────────────────
function getUpDown() {
  const tc = getChartColors()
  return { UP: tc.bullish, DOWN: tc.bearish }
}

// ─────────────────────────────────────────────────────────────────
// 数据清洗
// ─────────────────────────────────────────────────────────────────
function _sanitize(raw, isMinute = false) {
  if (!Array.isArray(raw) || !raw.length) return []
  return raw.map(r => ({
    // 分钟数据用 time 字段，日线数据用 date 字段
    date:       isMinute ? (r.time ? r.time.split(' ')[0] : '') : (r.date || String(r.timestamp || '')),
    time:       r.time || r.date || String(r.timestamp || ''),
    open:       Number(r.open)  || 0,
    close:      Number(r.close) || 0,
    high:       Number(r.high)  || 0,
    low:        Number(r.low)   || 0,
    volume:     Number(r.volume) || 0,
    price:      Number(r.price != null ? r.price : r.close) || 0,
    change_pct: Number(r.change_pct) || 0,
  }))
}

// ─────────────────────────────────────────────────────────────────
// 指标计算
// ─────────────────────────────────────────────────────────────────
function calcMA(data, n) {
  return data.map((_, i) => {
    if (i < n - 1) return null
    const slice = data.slice(i - n + 1, i + 1)
    return +(slice.reduce((a, b) => a + b, 0) / n).toFixed(3)
  })
}

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

function calcBOLL(closes) {
  const period = 20, mid = [], upper = [], lower = []
  for (let i = 0; i < closes.length; i++) {
    if (i < period - 1) { mid.push('-'); upper.push('-'); lower.push('-'); continue }
    const slice = closes.slice(i - period + 1, i + 1)
    const mean  = slice.reduce((a, b) => a + b, 0) / period
    const std   = Math.sqrt(slice.reduce((a, b) => a + (b - mean) ** 2, 0) / period)
    mid.push(+mean.toFixed(3)); upper.push(+(mean + 2 * std).toFixed(3)); lower.push(+(mean - 2 * std).toFixed(3))
  }
  return { mid, upper, lower }
}

function calcMACD(closes) {
  const ema12 = calcEMA(closes, 12)
  const ema26 = calcEMA(closes, 26)
  const dif   = ema12.map((v, i) => +(v - ema26[i]).toFixed(4))
  const dea   = calcEMA(dif, 9)
  const macd  = dif.map((v, i) => +((v - dea[i]) * 2).toFixed(4))
  return { dif, dea, macd }
}

function calcKDJ(closes, highs, lows, n = 9) {
  const k = [], d = [], j = []
  for (let i = 0; i < closes.length; i++) {
    if (i < n - 1) { k.push('-'); d.push('-'); j.push('-'); continue }
    const rh = Math.max(...highs.slice(i - n + 1, i + 1))
    const rl = Math.min(...lows.slice(i - n + 1, i + 1))
    const rsv = rh === rl ? 50 : (closes[i] - rl) / (rh - rl) * 100
    const pk = k[i - 1] !== '-' ? k[i - 1] : 50
    const pd = d[i - 1] !== '-' ? d[i - 1] : 50
    const nk = +(2/3 * pk + 1/3 * rsv).toFixed(2)
    const nd = +(2/3 * pd + 1/3 * nk).toFixed(2)
    k.push(nk); d.push(nd); j.push(+(3 * nk - 2 * nd).toFixed(2))
  }
  return { k, d, j }
}

function calcWR(closes, highs, lows, n = 10) {
  return closes.map((_, i) => {
    if (i < n - 1) return null
    const rh = Math.max(...highs.slice(i - n + 1, i + 1))
    const rl = Math.min(...lows.slice(i - n + 1, i + 1))
    if (rh === rl) return 0
    return +((rh - closes[i]) / (rh - rl) * -100).toFixed(2)
  })
}

function calcRSI(closes, period = 14) {
  const result = []
  for (let i = 0; i < closes.length; i++) {
    if (i < period) { result.push('-'); continue }
    let gain = 0, loss = 0
    for (let j = 1; j <= period; j++) {
      const change = closes[i - j + 1] - closes[i - j]
      if (change > 0) gain += change
      else loss -= change
    }
    const rs = loss === 0 ? 100 : gain / loss
    result.push((100 - 100 / (1 + rs)).toFixed(2))
  }
  return result
}

function calcOBV(closes, volumes) {
  const result = [0]
  for (let i = 1; i < closes.length; i++) {
    const change = closes[i] - closes[i - 1]
    const vol = change > 0 ? Number(volumes[i]) : change < 0 ? -Number(volumes[i]) : 0
    result.push(result[i - 1] + vol)
  }
  return result
}

function calcDMI(highs, lows, closes, period = 14) {
  const pdi = [], mdi = [], adx = []
  const tr = [], plusDM = [], minusDM = []
  for (let i = 1; i < closes.length; i++) {
    const highDiff = highs[i] - highs[i - 1]
    const lowDiff = lows[i - 1] - lows[i]
    plusDM.push(highDiff > lowDiff && highDiff > 0 ? highDiff : 0)
    minusDM.push(lowDiff > highDiff && lowDiff > 0 ? lowDiff : 0)
    tr.push(Math.max(highs[i] - lows[i], Math.abs(highs[i] - closes[i - 1]), Math.abs(lows[i] - closes[i - 1])))
  }
  for (let i = 0; i < closes.length; i++) {
    if (i < period) { pdi.push('-'); mdi.push('-'); adx.push('-'); continue }
    let trSum = 0, plusDMSum = 0, minusDMSum = 0
    for (let j = 0; j < period; j++) {
      trSum += tr[i - j - 1] || 0
      plusDMSum += plusDM[i - j - 1] || 0
      minusDMSum += minusDM[i - j - 1] || 0
    }
    const pdiVal = trSum > 0 ? (plusDMSum / trSum * 100).toFixed(2) : '0'
    const mdiVal = trSum > 0 ? (minusDMSum / trSum * 100).toFixed(2) : '0'
    pdi.push(pdiVal); mdi.push(mdiVal)
    const dx = Math.abs(parseFloat(pdiVal) - parseFloat(mdiVal)) / (parseFloat(pdiVal) + parseFloat(mdiVal)) * 100
    const dxVal = isNaN(dx) ? 0 : dx.toFixed(2)
    if (i === period) adx.push(dxVal)
    else adx.push(((parseFloat(adx[i - 1]) * (period - 1) + parseFloat(dxVal)) / period).toFixed(2))
  }
  return { pdi, mdi, adx }
}

// ─────────────────────────────────────────────────────────────────
// K线图（Task 2: 60%主图 / 20%成交量 比例）
// ─────────────────────────────────────────────────────────────────
function buildKLineOption(hist) {
  const { UP, DOWN } = getUpDown()
  const tc = getChartColors()
  // 日K: YYYY-MM-DD / 分钟K: YYYY-MM-DD HH:mm（全局统一完整日期格式）
  const times   = hist.map(h => {
    if (h.time && h.time.length >= 16) return h.time.slice(0, 16)   // YYYY-MM-DD HH:mm
    if (h.date) return h.date.slice(0, 10)                           // YYYY-MM-DD
    return ''
  })
  const closes  = hist.map(h => h.close)
  const highs   = hist.map(h => h.high)
  const lows    = hist.map(h => h.low)
  const volumes = hist.map(h => h.volume)

  const yMin = +(Math.min(...closes) * 0.997).toFixed(2)
  const yMax = +(Math.max(...closes) * 1.003).toFixed(2)

  const subInd = ['MACD', 'KDJ', 'WR', 'RSI', 'OBV', 'DMI'].find(i => (props.indicators || []).includes(i)) || null
  const showBOLL = (props.indicators || []).includes('BOLL')

  // Task 2: 主图 60% + 成交量 20% + 副图 20%（精确像素比例）
  const mainH  = 60   // %
  const volH   = 20   // %
  const subH   = subInd ? 17 : 0  // %
  const mainTop = 2   // %
  const volTop = mainTop + mainH + 1  // = 63%
  const subTop  = subInd ? volTop + volH + 1 : 0

  const grid = [
    { top: `${mainTop}%`,  height: `${mainH}%`,  right: 8, left: 55, bottom: 0 },
    { top: `${volTop}%`,   height: `${volH}%`,  right: 8, left: 55, bottom: 0 },
  ]
  if (subInd) grid.push({ top: `${subTop}%`, height: `${subH}%`, right: 8, left: 55, bottom: 0 })

  // ── series[0]: K线烛台
  const kSeries = {
    name: 'K线', type: 'candlestick',
    data: hist.map(h => [Number(h.open), Number(h.close), Number(h.low), Number(h.high)]),
    xAxisIndex: 0, yAxisIndex: 0,
    itemStyle: { color: UP, color0: DOWN, borderColor: UP, borderColor0: DOWN },
    markLine: {
      silent: true, symbol: 'none',
      lineStyle: { color: tc.ma5, width: 1, type: 'dashed' },
      data: [{ yAxis: hist[hist.length - 1]?.close }],
    },
  }

  // ── MA 均线
  const maSeries = [
    { name: 'MA5',  data: calcMA(closes, 5),  color: tc.textPrimary, width: 1 },
    { name: 'MA10', data: calcMA(closes, 10), color: tc.ma5, width: 1 },
    { name: 'MA20', data: calcMA(closes, 20), color: tc.ma20, width: 1 },
  ].map(cfg => ({
    ...cfg, type: 'line', xAxisIndex: 0, yAxisIndex: 0,
    smooth: true, symbol: 'none',
    lineStyle: { color: cfg.color, width: cfg.width }, tooltip: { show: true },
  }))

  // ── BOLL
  const bollSeries = showBOLL ? (() => {
    const { mid, upper, lower } = calcBOLL(closes)
    return [
      { name: 'BOLL-M', data: mid,   color: tc.ma20, width: 1.2, type: 'line', smooth: true, symbol: 'none',
        xAxisIndex: 0, yAxisIndex: 0, lineStyle: { color: tc.ma20, width: 1.2 } },
      { name: 'BOLL-U', data: upper, color: '#a78bfa', width: 1, type: 'line', smooth: true, symbol: 'none',
        xAxisIndex: 0, yAxisIndex: 0, lineStyle: { color: tc.ma20, width: 1, type: 'dashed' } },
      { name: 'BOLL-L', data: lower, color: '#a78bfa', width: 1, type: 'line', smooth: true, symbol: 'none',
        xAxisIndex: 0, yAxisIndex: 0, lineStyle: { color: tc.ma20, width: 1, type: 'dashed' } },
    ]
  })() : []

  // ── 成交量（固定 20% 高度）
  const volSeries = {
    name: '成交量', type: 'bar',
    data: hist.map(h => ({
      value: h.volume,
      itemStyle: {
        color: h.close >= h.open
          ? UP + '33'
          : DOWN + '33',
      },
    })),
    xAxisIndex: 1, yAxisIndex: 1, barMaxWidth: 6,
  }

  const series = [kSeries, ...maSeries, ...bollSeries, volSeries]

  // ── 副图指标
  if (subInd) {
    const xIdx = 2, yIdx = 2
    if (subInd === 'MACD') {
      const { dif, dea, macd } = calcMACD(closes)
      series.push(
        { name: 'DIF', type: 'line', data: dif, xAxisIndex: xIdx, yAxisIndex: yIdx,
          smooth: true, symbol: 'none', lineStyle: { color: tc.ma10, width: 1.2 } },
        { name: 'DEA', type: 'line', data: dea, xAxisIndex: xIdx, yAxisIndex: yIdx,
          smooth: true, symbol: 'none', lineStyle: { color: tc.bullishLight, width: 1.2 } },
        { name: 'MACD', type: 'bar',
          data: macd.map(v => ({ value: Math.abs(v), itemStyle: { color: v >= 0 ? UP : DOWN } })),
          xAxisIndex: xIdx, yAxisIndex: yIdx, barMaxWidth: 4 },
      )
    }
    if (subInd === 'KDJ') {
      const { k, d, j } = calcKDJ(closes, highs, lows)
      series.push(
        { name: 'K', type: 'line', data: k, xAxisIndex: xIdx, yAxisIndex: yIdx,
          smooth: true, symbol: 'none', lineStyle: { color: tc.bullishLight, width: 1.2 } },
        { name: 'D', type: 'line', data: d, xAxisIndex: xIdx, yAxisIndex: yIdx,
          smooth: true, symbol: 'none', lineStyle: { color: tc.ma10, width: 1.2 } },
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
          lineStyle: { color: tc.ma5, width: 1.2 },
          markLine: { silent: true, symbol: 'none', lineStyle: { color: tc.borderPrimary, type: 'dashed', width: 1 },
            data: [{ yAxis: -20 }, { yAxis: -80 }],
            label: { show: true, formatter: '{c}', fontSize: 8, color: tc.chartText } } },
      )
    }
    if (subInd === 'RSI') {
      const rsi = calcRSI(closes)
      series.push(
        { name: 'RSI', type: 'line',
          data: rsi.map(v => v == null ? '-' : v),
          xAxisIndex: xIdx, yAxisIndex: yIdx,
          smooth: true, symbol: 'none',
          lineStyle: { color: '#f472b6', width: 1.2 },
          markLine: { silent: true, symbol: 'none', lineStyle: { color: tc.borderPrimary, type: 'dashed', width: 1 },
            data: [{ yAxis: 70 }, { yAxis: 30 }],
            label: { show: true, formatter: '{c}', fontSize: 8, color: tc.chartText } } },
      )
    }
    if (subInd === 'OBV') {
      const obv = calcOBV(closes, volumes)
      series.push(
        { name: 'OBV', type: 'line',
          data: obv.map(v => v == null ? '-' : v),
          xAxisIndex: xIdx, yAxisIndex: yIdx,
          smooth: true, symbol: 'none',
          lineStyle: { color: '#22d3ee', width: 1.2 },
          markLine: { silent: true, symbol: 'none', lineStyle: { color: tc.borderPrimary, type: 'dashed', width: 1 },
            data: [{ yAxis: 0 }], label: { show: true, formatter: '{c}', fontSize: 8, color: tc.chartText } } },
      )
    }
    if (subInd === 'DMI') {
      const { pdi, mdi, adx } = calcDMI(highs, lows, closes)
      // PDI (+DI)
      series.push(
        { name: 'DMI+', type: 'line',
          data: pdi.map(v => v == null ? '-' : v),
          xAxisIndex: xIdx, yAxisIndex: yIdx,
          smooth: true, symbol: 'none',
          lineStyle: { color: '#22c55e', width: 1.2 } },
      )
      // MDI (-DI)
      series.push(
        { name: 'DMI-', type: 'line',
          data: mdi.map(v => v == null ? '-' : v),
          xAxisIndex: xIdx, yAxisIndex: yIdx,
          smooth: true, symbol: 'none',
          lineStyle: { color: '#ef4444', width: 1.2 } },
      )
      // ADX
      series.push(
        { name: 'ADX', type: 'line',
          data: adx.map(v => v == null ? '-' : v),
          xAxisIndex: xIdx, yAxisIndex: yIdx,
          smooth: true, symbol: 'none',
          lineStyle: { color: '#f59e0b', width: 1, type: 'dashed' },
          markLine: { silent: true, symbol: 'none', lineStyle: { color: tc.borderPrimary, type: 'dotted', width: 1 },
            data: [{ yAxis: 25 }], label: { show: true, formatter: 'ADX=25', fontSize: 8, color: tc.chartText } } },
      )
    }
  }

  // ── X轴
  const xAxisBase = {
    type: 'category', data: times, boundaryGap: true,
    axisLine: { lineStyle: { color: tc.borderPrimary } }, splitLine: { show: false },
  }
  const xAxis = [
    { ...xAxisBase, gridIndex: 0,
      axisLabel: { color: tc.chartText, fontSize: 9, interval: Math.max(0, Math.floor(times.length / 5) - 1) } },
    { ...xAxisBase, gridIndex: 1, axisLabel: { show: false } },
  ]
  if (subInd) xAxis.push({ ...xAxisBase, gridIndex: 2, axisLabel: { show: false } })

  // ── Y轴（主图动态 min/max）
  const yAxis = [
    { type: 'value', scale: true, gridIndex: 0, position: 'left',
      min: yMin, max: yMax,
      axisLine: { show: false },
      axisLabel: { color: tc.chartText, fontSize: 9, formatter: v => v.toFixed(0) },
      splitLine: { lineStyle: { color: tc.chartGrid, type: 'dashed' } } },
    { type: 'value', scale: true, gridIndex: 1, position: 'left',
      axisLine: { show: false }, axisLabel: { show: false }, splitLine: { show: false } },
  ]
  if (subInd) yAxis.push({ type: 'value', scale: true, gridIndex: 2, position: 'left',
    axisLine: { show: false },
    axisLabel: { color: tc.chartText, fontSize: 9 },
    splitLine: { lineStyle: { color: tc.chartGrid, type: 'dashed' } },
    max: subInd === 'WR' ? 0 : 'auto', min: subInd === 'WR' ? -100 : 'auto',
  })

  return {
    backgroundColor: 'transparent', grid, xAxis, yAxis, series,
    tooltip: {
      trigger: 'axis', type: 'cross',
      axisPointer: { type: 'cross', lineStyle: { color: tc.textSecondary, width: 1, type: 'dashed' }, crossStyle: { color: tc.textSecondary, width: 1 } },
      backgroundColor: tc.tooltipBg, borderColor: tc.borderPrimary,
      textStyle: { color: tc.textSecondary, fontSize: 11 },
      formatter(params) {
        const kp = params.find(p => p.seriesName === 'K线')
        if (!kp) return ''
        const idx = kp.dataIndex, h = hist[idx]
        const o = h.open, c = h.close, l = h.low, hi = h.high
        const chg = h.change_pct; const sign = chg >= 0 ? '+' : ''
        const col = c >= o ? UP : DOWN
        const vol = (h.volume / 1e8).toFixed(2)
        return `<span style="color:${tc.chartText};font-size:10px">${kp.axisValue}</span><br/>`
          + `<span style="color:${tc.textSecondary};font-size:10px">开</span> <span style="color:${tc.textPrimary};font-size:11px">${o.toFixed(2)}</span><br/>`
          + `<span style="color:${tc.textSecondary};font-size:10px">高</span> <span style="color:${tc.textPrimary};font-size:11px">${hi.toFixed(2)}</span><br/>`
          + `<span style="color:${tc.textSecondary};font-size:10px">低</span> <span style="color:${tc.textPrimary};font-size:11px">${l.toFixed(2)}</span><br/>`
          + `<span style="color:${tc.textSecondary};font-size:10px">收</span> <span style="color:${col};font-size:11px">${c.toFixed(2)}</span> <span style="color:${chg>=0?UP:DOWN};font-size:10px">${sign}${chg.toFixed(2)}%</span><br/>`
          + `<span style="color:${tc.textSecondary};font-size:10px">量</span> <span style="color:${tc.textSecondary};font-size:11px">${vol}亿</span>`
      },
    },
    dataZoom: [
      { type: 'inside', xAxisIndex: [...Array(xAxis.length).keys()], start: 70, end: 100, zoomOnMouseWheel: true },
      { type: 'slider', xAxisIndex: [0], start: 90, end: 100, height: 10, bottom: 1,
        borderColor: tc.borderPrimary, fillerColor: tc.isLight ? 'rgba(24,144,255,0.15)' : 'rgba(59,130,246,0.15)',
        handleStyle: { color: tc.accentPrimary, borderColor: tc.accentPrimary },
        textStyle: { color: tc.chartText, fontSize: 9 },
        dataBackground: { lineStyle: { color: tc.borderPrimary }, areaStyle: { color: tc.isLight ? 'rgba(24,144,255,0.08)' : 'rgba(59,130,246,0.08)' } } },
    ],
  }
}

// ─────────────────────────────────────────────────────────────────
// 分时图（Task 1: 动态Y轴min/max + areaStyle）
// ─────────────────────────────────────────────────────────────────
function buildLineOption(hist) {
  const { UP, DOWN } = getUpDown()
  const tc = getChartColors()
  const times   = hist.map(h => {
    if (h.time && h.time.length >= 16) return h.time.slice(0, 16)   // YYYY-MM-DD HH:mm
    if (h.date) return h.date.slice(0, 10)                           // YYYY-MM-DD
    return ''
  })
  const prices  = hist.map(h => Number(h.price != null ? h.price : h.close))
  const volumes = hist.map(h => Number(h.volume))
  const changes = hist.map(h => Number(h.change_pct || 0))
  const highs   = hist.map(h => Number(h.high || h.price || h.close))
  const lows   = hist.map(h => Number(h.low || h.price || h.close))

  // Task 1: 动态 Y 轴 min/max（1% 边距，绝不从 0 开始）
  const rawMin  = Math.min(...prices, ...lows)
  const rawMax  = Math.max(...prices, ...highs)
  const pad     = (rawMax - rawMin) * 0.01
  const yMin    = +(rawMin - pad).toFixed(2)
  const yMax    = +(rawMax + pad).toFixed(2)

  // 均价线
  // Task 1: 分时均价线 —— 使用累计成交额/成交量（VWAP）而非算术平均
  const avg = []
  let cumPriceVol = 0
  let cumVolume = 0
  for (let i = 0; i < prices.length; i++) {
    cumVolume += volumes[i]
    cumPriceVol += prices[i] * volumes[i]
    avg.push(cumVolume > 0 ? +(cumPriceVol / cumVolume).toFixed(3) : prices[i])
  }

  const upCount  = prices.filter((p, i) => i > 0 && p > prices[i - 1]).length
  const lineColor = upCount >= prices.length / 2 ? UP : DOWN

  const mainH  = 75  // %
  const volH  = 22  // %
  const mainTop = 2  // %
  const volTop  = mainTop + mainH + 1  // = 78%

  // Task 2: 分时图也用相同的比例
  const series = [
    { name: '价格', type: 'line', data: prices, smooth: 0.3, symbol: 'none',
      lineStyle: { color: lineColor, width: 1.5 },
      areaStyle: {
        color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: lineColor + '28' },
            { offset: 1, color: lineColor + '00' },
          ],
        },
      } },
    { name: '均价', type: 'line', data: avg, smooth: 0.3, symbol: 'none',
      lineStyle: { color: tc.ma5, width: 1, type: 'dashed' } },
  ]

  // 分时成交量（底部柱状）
  const volSeries = {
    name: '成交量', type: 'bar',
    data: volumes.map(v => ({ value: v, itemStyle: { color: lineColor + '33' } })),
    xAxisIndex: 1, yAxisIndex: 1, barMaxWidth: 4,
  }
  series.push(volSeries)

  return {
    backgroundColor: 'transparent',
    grid: [
      { top: `${mainTop}%`, height: `${mainH}%`,  right: 8, left: 55, bottom: 0 },
      { top: `${volTop}%`,  height: `${volH}%`,   right: 8, left: 55, bottom: 0 },
    ],
    xAxis: [
      { type: 'category', data: times, boundaryGap: false, gridIndex: 0,
        axisLine: { lineStyle: { color: tc.borderPrimary } },
        axisLabel: { color: tc.chartText, fontSize: 9, interval: Math.max(0, Math.floor(times.length / 6) - 1) },
        splitLine: { show: false } },
      { type: 'category', data: times, boundaryGap: false, gridIndex: 1,
        axisLine: { lineStyle: { color: tc.borderPrimary } },
        axisLabel: { show: false }, splitLine: { show: false } },
    ],
    yAxis: [
      { type: 'value', scale: true, gridIndex: 0, position: 'left',
        min: yMin, max: yMax,   // Task 1: 动态范围，不从 0 开始
        axisLine: { show: false },
        axisLabel: { color: tc.chartText, fontSize: 9, formatter: v => v.toFixed(2) },
        splitLine: { lineStyle: { color: tc.chartGrid, type: 'dashed' } } },
      { type: 'value', scale: true, gridIndex: 1, position: 'left',
        axisLine: { show: false }, axisLabel: { show: false }, splitLine: { show: false } },
    ],
    series,
    tooltip: {
      trigger: 'axis', type: 'cross',
      axisPointer: { lineStyle: { color: tc.borderPrimary } },
      backgroundColor: tc.tooltipBg, borderColor: tc.borderPrimary, textStyle: { color: tc.textSecondary, fontSize: 11 },
      formatter: (params) => {
        const p = params[0]
        if (!p) return ''
        const idx = p.dataIndex
        const chg = changes[idx]; const sign = chg >= 0 ? '+' : ''
        const a = avg[idx]
        const vol = (volumes[idx] / 1e8).toFixed(2)
        return `<span style="color:${tc.chartText};font-size:10px">${p.axisValue}</span><br/>`
          + `<span style="color:${tc.textSecondary};font-size:10px">价</span> <span style="color:${lineColor};font-size:11px">${(prices[idx] || 0).toFixed(3)}</span><br/>`
          + `<span style="color:${tc.textSecondary};font-size:10px">均</span> <span style="color:${tc.ma5};font-size:11px">${a.toFixed(3)}</span><br/>`
          + `<span style="color:${chg >= 0 ? UP : DOWN};font-size:10px">${sign}${chg.toFixed(2)}%</span> <span style="color:${tc.chartText};font-size:10px">量 ${vol}亿</span>`
      },
    },
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 70, end: 100, zoomOnMouseWheel: true },
      { type: 'slider', xAxisIndex: [0], start: 90, end: 100, height: 10, bottom: 1,
        borderColor: tc.borderPrimary, fillerColor: tc.isLight ? 'rgba(24,144,255,0.15)' : 'rgba(59,130,246,0.15)',
        handleStyle: { color: tc.accentPrimary, borderColor: tc.accentPrimary },
        textStyle: { color: tc.chartText, fontSize: 9 },
        dataBackground: { lineStyle: { color: tc.borderPrimary }, areaStyle: { color: tc.isLight ? 'rgba(24,144,255,0.08)' : 'rgba(59,130,246,0.08)' } } },
    ],
  }
}

// ─────────────────────────────────────────────────────────────────
// 统一入口
// ─────────────────────────────────────────────────────────────────
function buildOption(raw, type) {
  const hist = _sanitize(raw)
  if (!hist || !hist.length) return null
  if (type === 'line') return buildLineOption(hist)
  return buildKLineOption(hist)
}

// ─────────────────────────────────────────────────────────────────
// Hover Bar 事件绑定（Task 3）
// ─────────────────────────────────────────────────────────────────
function bindHoverEvents() {
  if (!chartInstance) return

  // 先解绑，避免重复注册累积
  chartInstance.off('mousemove')
  chartInstance.getZr().off('mouseleave')
  chartInstance.getZr().off('mouseenter')

  // mousemove → 实时更新顶部 OHLCV 栏
  chartInstance.on('mousemove', function (params) {
    if (!params.dataIndex && params.dataIndex !== 0) return
    const idx = params.dataIndex
    const raw = chartInstance.getOption()
    const seriesData = raw.series

    if (chartType.value === 'line') {
      // 分时：series[0]=价格, series[1]=均价, series[2]=成交量
      const priceData = seriesData[0]?.data?.[idx]
      const volData   = seriesData[2]?.data?.[idx]
      const times     = raw.xAxis?.[0]?.data || []
      const histRaw = _sanitize(raw._rawHist || [])
      const h = histRaw[idx] || {}
      hoverBar.value = {
        price: priceData != null ? Number(priceData) : null,
        time:  times[idx] || '',
        open:  h.open ?? null,
        high:  h.high ?? null,
        low:   h.low ?? null,
        close: h.close ?? null,
        volume: h.volume ?? null,
        change_pct: h.change_pct != null ? Number(h.change_pct) : null,
      }
    } else {
      // K线：series[0]=K线烛台 [open, close, low, high]
      const candleData = seriesData[0]?.data?.[idx]
      const volData    = seriesData[3]?.data?.[idx]
      const times      = raw.xAxis?.[0]?.data || []
      const histRaw = _sanitize(raw._rawHist || [])
      const h = histRaw[idx] || {}
      hoverBar.value = {
        price: candleData ? Number(candleData[1]) : null,
        time:  times[idx] || '',
        open:  candleData ? Number(candleData[0]) : null,
        high:  candleData ? Number(candleData[3]) : null,
        low:   candleData ? Number(candleData[2]) : null,
        close: candleData ? Number(candleData[1]) : null,
        volume: volData?.value ?? h.volume ?? null,
        change_pct: h.change_pct != null ? Number(h.change_pct) : null,
      }
    }
  })

  // 鼠标离开图表 → 取消进入事件、启动5秒定时器（超时后回填最新数据）
  chartInstance.getZr().on('mouseleave', () => {
    _cancelLeaveTimer()
    _startLeaveTimer()
  })

  // 鼠标进入图表 → 取消5秒定时器（停止回填，用户正在浏览）
  chartInstance.getZr().on('mouseenter', () => {
    _cancelLeaveTimer()
  })
}

// ─────────────────────────────────────────────────────────────────
// 回填 hoverBar 为最新一根（初始化 / 切换周期后）
// ─────────────────────────────────────────────────────────────────
function fillHoverBarLatest(hist) {
  if (!hist || !hist.length) { hoverBar.value = {}; return }
  const h = hist[hist.length - 1]
  hoverBar.value = {
    price:      h.price  ?? h.close ?? null,
    time:       h.time   ?? h.date  ?? '',
    open:       h.open   ?? null,
    high:       h.high   ?? null,
    low:        h.low    ?? null,
    close:      h.close  ?? null,
    volume:     h.volume ?? null,
    change_pct: h.change_pct != null ? Number(h.change_pct) : null,
  }
}

// 暂存最近一次渲染用的 raw hist（用于 mouseleave 回填）
let lastHistRaw = []

// ─────────────────────────────────────────────────────────────────
// 5秒定时器：鼠标离开图表5秒后自动回填最新数据
// ─────────────────────────────────────────────────────────────────
let _leaveTimer = null

function _startLeaveTimer() {
  clearTimeout(_leaveTimer)
  _leaveTimer = setTimeout(() => {
    const sanitized = _sanitize(lastHistRaw)
    fillHoverBarLatest(sanitized)
  }, 5000)
}

function _cancelLeaveTimer() {
  clearTimeout(_leaveTimer)
  _leaveTimer = null
}

// ─────────────────────────────────────────────────────────────────
// 渲染循环
// ─────────────────────────────────────────────────────────────────
async function fetchAndRender() {
  chartError.value = ''; isLoading.value = true
  try {
    // Guard: if symbol prop is undefined/null, use a fallback URL
    const safeSymbol = (props.symbol && props.symbol !== 'undefined') ? props.symbol : 'sh000001'
    const fullUrl = `/api/v1/market/history/${safeSymbol}?period=${props.period || 'daily'}&_t=${Date.now()}`
    const d = await apiFetch(fullUrl)
    const type = d?.chart_type || 'candlestick'
    chartType.value = type
    // 分钟数据需要特殊处理
    const isMinute = type === 'line' || props.url.includes('minutely') || props.url.includes('period=1m') || props.url.includes('period=5m')
    // 统一解包: apiFetch 已自动解包 data，但需兼容直接返回 history 的情况
    const hist = _sanitize(d?.data?.history || d?.history || d || [], isMinute)

    // 将 raw hist 塞给 option，方便 hover 时访问
    // 确保数据按时间正序（左边=最旧，右边=最新）
    // API 返回 ASC（从旧到新），直接使用；如 API 返回 DESC 则需要 reverse()
    const isDesc = hist.length >= 2 && new Date(hist[0].date) > new Date(hist[hist.length - 1].date)
    const sortedHist = isDesc ? [...hist].reverse() : hist
    const opt = buildOption(sortedHist, type)

    // 空数据：设置错误提示，不渲染空图表
    if (!opt) {
      chartError.value = '暂无历史数据'
      if (chartInstance) chartInstance.clear()
      return
    }

    chartError.value = ''
    opt._rawHist = d?.data?.history || d?.history || d || []

    currentName.value = props.name || '指标图表'

    if (!chartInstance) {
      chartInstance = window.echarts.init(chartRef.value, null, { renderer: 'canvas' })
    }

    // 每次渲染后重新绑定事件（clear() 会清除所有事件监听）
    bindHoverEvents()

    chartInstance.clear()
    chartInstance.setOption(opt, { notMerge: true })

    // 回填最新一根数据到 hover bar（保证刷新后默认显示）
    lastHistRaw = d?.data?.history || d?.history || d || []
    fillHoverBarLatest(_sanitize(lastHistRaw, isMinute))
  } catch (e) {
    chartError.value = `加载失败: ${e.message}`
    logger.error('[KLine]', e)
  } finally {
    isLoading.value = false
  }
}
const debouncedFetch = useDebounceFn(fetchAndRender, 300)

function retryChart() { chartError.value = ''; fetchAndRender() }

// props.symbol 变化时立即重置名称（不等数据加载）
watch(() => props.symbol, (sym) => {
  logger.log('[KLine] watch: props.symbol changed', { sym, props: { name: props.name, symbol: props.symbol } })
  // symbol 变化时：先清空旧图表（立即响应），等数据回来再显示
  chartInstance?.clear()
  currentName.value = props.name || '指标图表'
  debouncedFetch()
})
// 指标 watch（独立，不与 symbol watch 联动，防止 symbol+indicators 同时变化触发两次）
watch(() => props.indicators, () => { fetchAndRender() }, { deep: true })

let unsubscribeTheme = null

onMounted(async () => {
  await new Promise(r => setTimeout(r, 0))
  if (chartRef.value && window.echarts) {
    chartInstance = window.echarts.init(chartRef.value, null, { renderer: 'canvas' })
    resizeObserver = new ResizeObserver(() => chartInstance?.resize())
    resizeObserver.observe(chartRef.value)
    bindHoverEvents()
    fetchAndRender()
  }
  unsubscribeTheme = onThemeChange(() => {
    fetchAndRender()
  })
})

onUnmounted(() => {
  resizeObserver?.disconnect()
  chartInstance?.dispose()
  chartInstance = null
  unsubscribeTheme?.()
  unsubscribeTheme = null
})
</script>
