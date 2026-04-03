<template>
  <!-- 全屏 K 线分析面板 -->
  <div class="flex flex-col w-full h-full overflow-hidden">

    <!-- 顶部控制栏：数据盘口+图表控制台 -->
    <QuoteHeader
      :name="symbolName"
      :symbol="currentSymbol"
      :quote="currentQuote"
      :period="period"
      :adjustment="adjustment"
      :yAxisType="yAxisType"
      :overlaySymbol="overlaySymbol"
      :overlayName="overlayName"
      :visibleHist="visibleHist"
      :fullHist="histData"
      @period-change="onPeriodChange"
      @adjustment-change="adj => adjustment = adj"
      @yaxis-change="y => yAxisType = y"
      @overlay-change="onOverlayChange"
      @export-png="exportPNG"
    />

    <!-- 主图区（flex-1，绑定 ResizeObserver） -->
    <div class="flex-1 min-h-0 relative" ref="chartContainerRef">
      <!-- 画线工具栏（左侧） -->
      <div class="absolute left-0 top-0 bottom-0 z-20 flex items-center">
        <DrawingToolbar
          :activeTool="drawingTool"
          :activeColor="drawingColor"
          :magnetMode="magnetMode"
          :visible="drawingVisible"
          :locked="drawingLocked"
          @tool-change="t => drawingTool = t"
          @color-change="c => drawingColor = c"
          @magnet-toggle="magnetMode = !magnetMode"
          @visibility-toggle="drawingVisible = !drawingVisible"
          @lock-toggle="drawingLocked = !drawingLocked"
          @clear="drawingCanvasRef?.clearAll()"
        />
      </div>

      <!-- ECharts 主图表 -->
      <div ref="chartRef" class="w-full h-full"></div>

      <!-- 画线 Canvas 覆盖层 -->
      <DrawingCanvas
        v-if="drawingVisible"
        ref="drawingCanvasRef"
        :chartInstance="chartInstance"
        :activeTool="drawingTool"
        :activeColor="drawingColor"
        :magnetMode="magnetMode"
        :symbol="currentSymbol"
        class="z-10"
        @drawn="onShapeDrawn"
        @deleted="onShapeDeleted"
        @cleared="onShapesCleared"
        @range-select="onRangeSelect"
      />

      <!-- 十字光标信息浮层（右上角） -->
      <CrosshairInfo
        v-if="hoverData && Object.keys(hoverData).length"
        :data="hoverData"
        class="absolute top-2 right-2 z-20 pointer-events-none"
      />
    </div>

    <!-- 副图区（固定高度） -->
    <SubChart
      :hist="histData"
      :activeTab="subChartTab"
      :indicatorParams="indicatorParams"
      class="shrink-0"
      style="height: 180px;"
      @tab-change="t => subChartTab = t"
      @params-change="p => indicatorParams = { ...indicatorParams, ...p }"
    />

    <!-- 左下角命令中心 -->
    <div class="absolute bottom-4 left-4 z-20">
      <CommandCenter @select="onSymbolSelect" />
    </div>

    <!-- 区间统计浮窗（条件渲染） -->
    <IntervalStats
      v-if="intervalStats"
      :stats="intervalStats"
      class="absolute top-1/2 left-1/2 z-30"
      style="transform: translate(-50%, -50%);"
      @close="intervalStats = null"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts/core'
import { CandlestickChart, LineChart, BarChart } from 'echarts/charts'
import {
  GridComponent, TooltipComponent, LegendComponent,
  DataZoomComponent, MarkLineComponent, MarkAreaComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { useMarketStore } from '../composables/useMarketStore.js'

import QuoteHeader    from './QuoteHeader.vue'
import CommandCenter  from './CommandCenter.vue'
import SubChart       from './SubChart.vue'
import CrosshairInfo  from './CrosshairInfo.vue'
import IntervalStats  from './IntervalStats.vue'
import DrawingToolbar from './DrawingToolbar.vue'
import DrawingCanvas  from './DrawingCanvas.vue'

import { calcMA, calcBOLL, calcMACD, calcKDJ, calcRSI } from '../utils/indicators.js'
import { normalizeSymbol, buildXAxisLabels } from '../utils/symbols.js'
import { UP, DOWN } from '../utils/indicators.js'

echarts.use([
  CandlestickChart, LineChart, BarChart,
  GridComponent, TooltipComponent, LegendComponent,
  DataZoomComponent, MarkLineComponent, MarkAreaComponent,
  CanvasRenderer,
])

const {
  currentSymbol, currentSymbolName,
  setSymbol, isAShare, isIntradayPeriod,
} = useMarketStore()

// ── 状态 ──────────────────────────────────────────────────────
const period         = ref('daily')    // daily | weekly | monthly | minutely | 1min | 5min | ...
const adjustment     = ref('none')     // none | qfq | hfq
const yAxisType      = ref('linear')   // linear | log
const overlaySymbol   = ref('')
const overlayName     = ref('')
const subChartTab    = ref('VOL')       // VOL | MACD | KDJ | RSI | BOLL
const indicatorParams = ref({ MACD: { fast: 12, slow: 26, signal: 9 }, KDJ: { n: 9 }, RSI: { period: 14 }, BOLL: { period: 20, stdDev: 2 } })
const currentQuote    = ref({})         // 实时快照
const hoverData       = ref({})         // 十字光标数据
const intervalStats   = ref(null)       // 区间统计结果
const histData        = ref([])         // 全部历史数据
const visibleHist     = ref([])         // 当前可视范围数据
const chartRef        = ref(null)
const chartContainerRef = ref(null)
const isLoading       = ref(false)
const chartError      = ref('')
const hasMore         = ref(false)
const loadOffset      = ref(0)         // 懒加载偏移量

let chartInstance = null
let resizeObserver = null
const drawingCanvasRef = ref(null)

// 画线状态
const drawingTool     = ref('')
const drawingColor    = ref('#fbbf24')
const magnetMode     = ref(true)
const drawingVisible  = ref(true)
const drawingLocked   = ref(false)

// ── 标的信息 ──────────────────────────────────────────────────
const symbolName = computed(() => currentSymbolName.value || currentSymbol.value.replace(/^(sh|sz|us|hk|jp)/i, ''))

// ── 指标参数 ──────────────────────────────────────────────────
function calcMA5()  { return calcMA(visibleHist.value.map(h => h.close), 5) }
function calcMA10() { return calcMA(visibleHist.value.map(h => h.close), 10) }
function calcMA20() { return calcMA(visibleHist.value.map(h => h.close), 20) }
function calcBOLLLocal() { return calcBOLL(visibleHist.value.map(h => h.close), indicatorParams.value.BOLL?.period || 20, indicatorParams.value.BOLL?.stdDev || 2) }
function calcMACDLocal() {
  const p = indicatorParams.value.MACD || {}
  return calcMACD(visibleHist.value.map(h => h.close), p.fast || 12, p.slow || 26, p.signal || 9)
}
function calcKDJLocal() {
  const p = indicatorParams.value.KDJ || {}
  return calcKDJ(
    visibleHist.value.map(h => h.close),
    visibleHist.value.map(h => h.high),
    visibleHist.value.map(h => h.low),
    p.n || 9
  )
}
function calcRSILocal() {
  const p = indicatorParams.value.RSI || {}
  return calcRSI(visibleHist.value.map(h => h.close), p.period || 14)
}

// ── 数据获取 ──────────────────────────────────────────────────
async function fetchHistory(append = false) {
  const sym = currentSymbol.value
  if (!sym) return
  isLoading.value = true
  chartError.value = ''

  try {
    const params = new URLSearchParams({
      period: period.value,
      limit: 300,
      offset: append ? String(loadOffset.value) : '0',
      adjustment: adjustment.value,
    })
    const url = `/api/v1/market/history/${sym}?${params}`
    const res = await fetch(url)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    const items = (data.history || []).map(sanitizeItem)

    if (append) {
      histData.value = [...items.reverse(), ...histData.value]  // 向前追加（更早的数据在前面）
      loadOffset.value += items.length
    } else {
      histData.value = items
      loadOffset.value = items.length
    }

    visibleHist.value = histData.value
    hasMore.value = data.has_more ?? items.length >= 300

    // 更新快照（最新一根）
    if (items.length > 0) {
      const last = items[items.length - 1]
      currentQuote.value = {
        price:        last.close,
        change:       last.close - (items[items.length - 2]?.close || last.close),
        change_pct:   last.change_pct ?? ((last.close - (items[items.length - 2]?.close || last.close)) / (items[items.length - 2]?.close || 1) * 100),
        volume:       last.volume,
        amount:       last.amount || (last.close * last.volume),
        amplitude:    last.amplitude,
        turnover_rate: last.turnover_rate,
      }
    }
  } catch (e) {
    chartError.value = '数据加载失败：' + e.message
  } finally {
    isLoading.value = false
  }
}

// ── 数据清洗 ──────────────────────────────────────────────────
function sanitizeItem(r) {
  return {
    date:       r.date || r.time || '',
    time:       r.time || '',
    open:       Number(r.open)  || 0,
    close:      Number(r.close) || 0,
    high:       Number(r.high)  || 0,
    low:        Number(r.low)   || 0,
    volume:     Number(r.volume) || 0,
    amount:     Number(r.amount) || 0,
    change_pct: Number(r.change_pct) || 0,
    amplitude:  Number(r.amplitude) || 0,
    turnover_rate: Number(r.turnover_rate) || 0,
  }
}

// ── 事件处理 ───────────────────────────────────────────────────
function onSymbolSelect(item) {
  setSymbol(item.symbol, item.name, '#00ff88', item.market)
  period.value = 'daily'
  loadOffset.value = 0
  histData.value = []
  visibleHist.value = []
  fetchHistory()
}

function onPeriodChange(p) {
  period.value = p
  loadOffset.value = 0
  histData.value = []
  visibleHist.value = []
  fetchHistory()
}

function onOverlayChange(sym) {
  overlaySymbol.value = sym
  overlayName.value = ''
  // TODO: 获取 overlay 名称
  if (sym) fetchOverlayHistory(sym)
}

async function fetchOverlayHistory(sym) {
  // TODO: 实现叠加标的的历史数据获取
}

// ── ECharts 配置 ──────────────────────────────────────────────
function buildOption() {
  const hist = visibleHist.value
  if (!hist.length) return {}

  const times   = buildXAxisLabels(hist, period.value)
  const closes  = hist.map(h => h.close)
  const highs   = hist.map(h => h.high)
  const lows    = hist.map(h => h.low)
  const volumes = hist.map(h => h.volume)

  const yMin = +(Math.min(...closes) * 0.997).toFixed(2)
  const yMax = +(Math.max(...closes) * 1.003).toFixed(2)

  const subInd = subChartTab.value
  const showVOL  = subInd === 'VOL'
  const showMACD = subInd === 'MACD'
  const showKDJ  = subInd === 'KDJ'
  const showRSI  = subInd === 'RSI'
  const showBOLL = subInd === 'BOLL'

  const mainH = 62, volH = 20, indH = 15
  const mainTop = 2
  const volTop  = mainTop + mainH + 1
  const indTop  = volTop + volH + 1

  const grid = [
    { top: `${mainTop}%`, height: `${mainH}%`, right: 60, left: 55, bottom: 0 },
    { top: `${volTop}%`,  height: `${volH}%`,  right: 60, left: 55, bottom: 0 },
  ]
  if (subInd !== 'VOL') grid.push({ top: `${indTop}%`, height: `${indH}%`, right: 60, left: 55, bottom: 0 })

  const xAxis = [
    { gridIndex: 0, type: 'category', data: times, boundaryGap: true, axisLine: { lineStyle: { color: '#374151' } }, splitLine: { show: false } },
    { gridIndex: 1, type: 'category', data: times, boundaryGap: true, axisLine: { lineStyle: { color: '#374151' } }, splitLine: { show: false }, axisLabel: { show: false } },
  ]
  if (subInd !== 'VOL') xAxis.push({ gridIndex: 2, type: 'category', data: times, boundaryGap: true, axisLine: { lineStyle: { color: '#374151' } }, splitLine: { show: false }, axisLabel: { show: false } })

  const yAxis = [
    { gridIndex: 0, type: yAxisType.value, min: yMin, max: yMax, axisLine: { lineStyle: { color: '#374151' } }, splitLine: { lineStyle: { color: '#1f2937' } }, scale: true },
    { gridIndex: 1, type: 'value', axisLine: { lineStyle: { color: '#374151' } }, splitLine: { show: false }, axisLabel: { formatter: v => (v / 1e8).toFixed(0) + '亿' } },
  ]
  if (subInd !== 'VOL') yAxis.push({ gridIndex: 2, type: 'value', axisLine: { lineStyle: { color: '#374151' } }, splitLine: { show: false } })

  // ── K线烛台 ───────────────────────────────────────────────
  const kSeries = {
    name: 'K线', type: 'candlestick',
    data: hist.map(h => [h.open, h.close, h.low, h.high]),
    xAxisIndex: 0, yAxisIndex: 0,
    itemStyle: { color: UP, color0: DOWN, borderColor: UP, borderColor0: DOWN },
  }

  // ── MA 均线 ────────────────────────────────────────────────
  const ma5  = calcMA5()
  const ma10 = calcMA10()
  const ma20 = calcMA20()
  const maSeries = [
    { name: 'MA5',  data: ma5,  color: '#ffffff', width: 1 },
    { name: 'MA10', data: ma10, color: '#fbbf24', width: 1 },
    { name: 'MA20', data: ma20, color: '#c084fc', width: 1 },
  ].map(cfg => ({
    ...cfg, type: 'line', xAxisIndex: 0, yAxisIndex: 0,
    smooth: false, symbol: 'none',
    lineStyle: { color: cfg.color, width: cfg.width },
  }))

  // ── BOLL ────────────────────────────────────────────────────
  const bollSeries = showBOLL ? (() => {
    const { mid, upper, lower } = calcBOLLLocal()
    return [
      { name: 'BOLL-M', data: mid,   color: '#a78bfa', width: 1.2, type: 'line', smooth: false, symbol: 'none', xAxisIndex: 0, yAxisIndex: 0,
        lineStyle: { color: '#a78bfa', width: 1.2 } },
      { name: 'BOLL-U', data: upper, color: '#a78bfa', width: 1, type: 'line', smooth: false, symbol: 'none', xAxisIndex: 0, yAxisIndex: 0,
        lineStyle: { color: '#a78bfa', width: 1, type: 'dashed' } },
      { name: 'BOLL-L', data: lower, color: '#a78bfa', width: 1, type: 'line', smooth: false, symbol: 'none', xAxisIndex: 0, yAxisIndex: 0,
        lineStyle: { color: '#a78bfa', width: 1, type: 'dashed' } },
    ]
  })() : []

  // ── 成交量 ─────────────────────────────────────────────────
  const volSeries = {
    name: 'VOL', type: 'bar',
    data: hist.map(h => ({ value: h.volume, itemStyle: { color: h.close >= h.open ? UP + '44' : DOWN + '44' } })),
    xAxisIndex: 1, yAxisIndex: 1, barMaxWidth: 6,
  }

  // ── 副图指标 ───────────────────────────────────────────────
  const subSeries = []
  if (showMACD) {
    const { dif, dea, macd } = calcMACDLocal()
    subSeries.push(
      { name: 'DIF', type: 'line', data: dif, xAxisIndex: 2, yAxisIndex: 2, smooth: false, symbol: 'none', lineStyle: { color: '#60a5fa', width: 1.2 } },
      { name: 'DEA', type: 'line', data: dea, xAxisIndex: 2, yAxisIndex: 2, smooth: false, symbol: 'none', lineStyle: { color: '#f87171', width: 1.2 } },
      { name: 'MACD', type: 'bar',
        data: macd.map(v => ({ value: Math.abs(v), itemStyle: { color: v >= 0 ? UP : DOWN } })),
        xAxisIndex: 2, yAxisIndex: 2, barMaxWidth: 4 },
    )
  }
  if (showKDJ) {
    const { k, d, j } = calcKDJLocal()
    subSeries.push(
      { name: 'K', type: 'line', data: k, xAxisIndex: 2, yAxisIndex: 2, smooth: false, symbol: 'none', lineStyle: { color: '#f87171', width: 1.2 } },
      { name: 'D', type: 'line', data: d, xAxisIndex: 2, yAxisIndex: 2, smooth: false, symbol: 'none', lineStyle: { color: '#60a5fa', width: 1.2 } },
      { name: 'J', type: 'line', data: j, xAxisIndex: 2, yAxisIndex: 2, smooth: false, symbol: 'none', lineStyle: { color: '#fbbf24', width: 1.2 } },
    )
  }
  if (showRSI) {
    const rsi = calcRSILocal()
    subSeries.push(
      { name: 'RSI', type: 'line', data: rsi, xAxisIndex: 2, yAxisIndex: 2, smooth: false, symbol: 'none',
        lineStyle: { color: '#34d399', width: 1.5 } },
    )
  }

  const series = [kSeries, ...maSeries, ...bollSeries, volSeries, ...subSeries]

  // ── DataZoom（缩放+平移）────────────────────────────────────
  const dataZoom = [
    { type: 'inside', xAxisIndex: [0, 1, 2], start: 70, end: 100 },
    {
      type: 'slider', xAxisIndex: [0, 1, 2], start: 70, end: 100,
      bottom: 4, height: 18,
      borderColor: '#374151', backgroundColor: '#1f2937',
      dataBackground: { lineStyle: { color: '#4b5563' }, areaStyle: { color: '#1f2937' } },
      selectedDataBackground: { lineStyle: { color: '#60a5fa' }, areaStyle: { color: '#1e3a5f' } },
      fillerColor: 'rgba(96, 165, 250, 0.1)',
      handleStyle: { color: '#60a5fa', borderColor: '#60a5fa' },
      textStyle: { color: '#9ca3af', fontSize: 9 },
    },
  ]

  return { grid, xAxis, yAxis, series, dataZoom }
}

// ── 渲染图表 ───────────────────────────────────────────────────
function renderChart() {
  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value, null, { renderer: 'canvas' })

    // 十字光标 tooltip
    chartInstance.getZr().on('mousemove', (params) => {
      const point = [params.offsetX, params.offsetY]
      const converted = chartInstance.convertFromPixel({ gridIndex: 0 }, point)
      if (converted && visibleHist.value[converted[0]] !== undefined) {
        const h = visibleHist.value[converted[0]]
        hoverData.value = {
          date:   h.date,
          time:   h.time,
          open:   h.open,
          high:   h.high,
          low:    h.low,
          close:  h.close,
          volume: h.volume,
          change_pct: h.change_pct,
        }
      }
    })

    chartInstance.getZr().on('mouseleave', () => { hoverData.value = {} })

    // 缩放时更新 visibleHist
    chartInstance.on('datazoom', (params) => {
      const zr = chartInstance.getOption().dataZoom?.[0]
      if (zr) {
        const start = Math.round((zr.start || 0) / 100 * visibleHist.value.length)
        const end   = Math.round((zr.end || 100) / 100 * visibleHist.value.length)
        // 懒加载：当 start < 5% 时加载更早数据
        if (start < visibleHist.value.length * 0.05 && hasMore.value && !isLoading.value) {
          fetchHistory(true)
        }
      }
    })
  }

  chartInstance.setOption(buildOption(), { notMerge: false })
}

// ── ResizeObserver ─────────────────────────────────────────────
function setupResizeObserver() {
  resizeObserver = new ResizeObserver(() => {
    chartInstance?.resize()
  })
  resizeObserver.observe(chartContainerRef.value)
}

// ── 导出 PNG ───────────────────────────────────────────────────
function exportPNG() {
  if (!chartInstance) return
  const url = chartInstance.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: '#0f172a' })
  const a = document.createElement('a')
  a.href = url
  a.download = `${symbolName.value}_${period.value}.png`
  a.click()
}

// ── 区间统计（右键框选）────────────────────────────────────────
const rangeStart = ref(null)

function onRangeSelect({ idx }) {
  if (!rangeStart.value) {
    rangeStart.value = { idx }
  } else {
    const start = Math.min(rangeStart.value.idx, idx)
    const end   = Math.max(rangeStart.value.idx, idx)
    const slice = histData.value.slice(start, end + 1)
    if (slice.length > 1) {
      const first = slice[0], last = slice[slice.length - 1]
      const changePct = +((last.close - first.close) / (first.close || 1) * 100).toFixed(2)
      const highs = slice.map(h => h.high)
      const lows  = slice.map(h => h.low)
      intervalStats.value = {
        startDate: first.date,
        endDate:   last.date,
        tradeDays: slice.length,
        changePct,
        maxAmplitude: +((Math.max(...highs) / Math.min(...lows) * 100) - 100).toFixed(2),
        highest:   Math.max(...highs),
        lowest:    Math.min(...lows),
        totalVolume: slice.reduce((a, h) => a + (h.volume || 0), 0),
        totalAmount: slice.reduce((a, h) => a + (h.amount || 0), 0),
        totalTurnoverRate: slice.reduce((a, h) => a + (h.turnover_rate || 0), 0),
      }
    }
    rangeStart.value = null
  }
}

// ── 画线事件（IndexedDB 自动持久化，此处可扩展日志）─────────────
function onShapeDrawn() {}
function onShapeDeleted() {}
function onShapesCleared() {}

// ── 生命周期 ───────────────────────────────────────────────────
onMounted(() => {
  setupResizeObserver()
  fetchHistory()
})

onUnmounted(() => {
  resizeObserver?.disconnect()
  chartInstance?.dispose()
})

// ── 监听响应 ───────────────────────────────────────────────────
watch(currentSymbol, () => { fetchHistory() })
watch([period, yAxisType, subChartTab, indicatorParams], () => renderChart() )
watch(histData, () => nextTick(renderChart))
</script>
