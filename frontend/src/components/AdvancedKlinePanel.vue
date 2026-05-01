<template>
  <!-- 全屏 K 线分析面板 -->
  <div class="flex flex-col w-full h-full overflow-hidden">

    <!-- 顶部控制栏 -->
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
      :maDisplays="maDisplays"
      :hoverData="hoverData"
      @period-change="onPeriodChange"
      @adjustment-change="adj => adjustment = adj"
      @yaxis-change="y => yAxisType = y"
      @overlay-change="onOverlayChange"
      @export-png="exportPNG"
    />

    <!-- 主图区 -->
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

      <!-- BaseKLineChart 哑组件（内部全权负责 ECharts 渲染） -->
      <BaseKLineChart
        ref="baseChartRef"
        class="w-full h-full"
        :chart-data="processedChartData"
        :sub-charts="activeSubCharts"
        :tick="liveTick"
        :symbol="currentSymbol"
        @datazoom="onDataZoom"
      />

      <!-- 加载/穿透中遮罩 -->
      <div
        v-if="isLoading || isFetching"
        class="absolute inset-0 z-30 flex flex-col p-4 gap-2"
        style="background: rgba(15,23,42,0.75); backdrop-filter: blur(2px);"
      >
        <div class="flex justify-between mb-2">
          <div class="skeleton h-3 w-32 rounded-sm"></div>
          <div class="skeleton h-3 w-16 rounded-sm"></div>
        </div>
        <div class="flex-1 skeleton rounded-sm"></div>
        <div class="flex gap-2">
          <div class="skeleton h-2 w-12 rounded-sm"></div>
          <div class="skeleton h-2 w-12 rounded-sm"></div>
          <div class="skeleton h-2 w-12 rounded-sm"></div>
        </div>
        <div v-if="isFetching" class="text-theme-tertiary text-[10px] font-mono text-center mt-1">
          📡 首次访问，正在穿透拉取全量历史…
        </div>
      </div>

      <!-- 右键上下文菜单 -->
      <div
        v-if="ctxMenu.visible"
        class="absolute z-50 bg-terminal-panel border border-theme-secondary rounded-sm shadow-sm py-1 min-w-44"
        :style="{ left: ctxMenu.x + 'px', top: ctxMenu.y + 'px' }"
      >
        <button
          class="w-full px-3 py-1.5 text-[11px] text-left text-theme-primary hover:bg-theme-tertiary/60 flex items-center gap-2"
          @click="onDrillDown"
        >
          <span>📊</span><span>查看历史分时</span>
          <span class="text-theme-muted ml-auto text-[10px]">{{ ctxMenu.date || '' }}</span>
        </button>
        <button
          class="w-full px-3 py-1.5 text-[11px] text-left text-theme-primary hover:bg-theme-tertiary/60 flex items-center gap-2"
          @click="ctxMenu.visible = false"
        >取消</button>
      </div>

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

      <!-- 下钻返回按钮 -->
      <button
        v-if="drillDownDate"
        class="absolute top-2 left-1/2 -translate-x-1/2 z-30 px-3 py-1 text-[11px] rounded-sm border border-[var(--color-warning)]/50 bg-[var(--color-warning-bg)] text-[var(--color-warning)] hover:bg-[var(--color-warning-bg)]/80 transition-colors"
        @click="exitDrillDown"
      >← 返回日线</button>
    </div>

    <!-- 副图区（SubChart 独立管理自己的 ECharts 实例） -->
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

    <!-- 区间统计浮窗 -->
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
import { ref, computed, watch, shallowRef, triggerRef, onMounted, onUnmounted, nextTick } from 'vue'
import { useThrottleFn } from '@vueuse/core'
import { logger } from '../utils/logger.js'

import { useMarketStore } from '../stores/market.js'
import { useMarketStream } from '../composables/useMarketStream.js'
import { apiFetch } from '../utils/api.js'
import { buildChartData } from '../utils/chartDataBuilder.js'
import { calcMA } from '../utils/indicators.js'

import QuoteHeader    from './QuoteHeader.vue'
import CommandCenter  from './CommandCenter.vue'
import SubChart       from './SubChart.vue'
import IntervalStats  from './IntervalStats.vue'
import DrawingToolbar from './DrawingToolbar.vue'
import DrawingCanvas  from './DrawingCanvas.vue'
import BaseKLineChart from './BaseKLineChart.vue'

const {
  currentSymbol, currentSymbolName,
  setSymbol, isAShare, isIntradayPeriod,
} = useMarketStore()

// ── Refs ────────────────────────────────────────────────────────
const baseChartRef        = ref(null)
const chartContainerRef   = ref(null)
const drawingCanvasRef    = ref(null)
const isLoading           = ref(false)
const isFetching          = ref(false)
const hasMore             = ref(false)
const loadOffset          = ref(0)

// chartInstance：暴露给 DrawingCanvas 做坐标吸附
const chartInstance = computed(() => baseChartRef.value?.getChartInstance() ?? null)

// ── 核心数据（shallowRef 避免大数组深度劫持）─────────────────────
const histData  = shallowRef([])          // 完整历史 ASC
const overlayData = shallowRef([])        // 叠加标的 {date, close}[]
const liveTick   = shallowRef(null)       // 实时 tick

// chartData 专用 shallowRef，避免每次 histData 变化触发父级深度 diff
const processedChartData = shallowRef({ isEmpty: true })

// ── ETF 代码检测 ────────────────────────────────────────────────
const ETF_PREFIXES = ['51', '15', '16', '56']

function _isEtfCode(sym) {
  if (!sym) return false
  // 去掉 sh/sz/hk 等前缀
  const num = sym.replace(/^(sh|sz|hk|us)/i, '')
  return num.length === 6 && /^\d{6}$/.test(num) && ETF_PREFIXES.some(p => num.startsWith(p))
}

function _etfCode(sym) {
  return sym.replace(/^(sh|sz|hk|us)/i, '')
}

function rebuildChartData() {
  processedChartData.value = histData.value.length
    ? buildChartData(histData.value, period.value, indicatorParams.value, overlayData.value)
    : { isEmpty: true }
}

// visibleHist：视图窗口数据（由 datazoom 决定）
const visibleHist = computed(() => histData.value)

// ── 控制状态 ────────────────────────────────────────────────────
const period          = ref('daily')
const adjustment      = ref('none')
const yAxisType       = ref('linear')
const overlaySymbol   = ref('')
const overlayName     = ref('')
const subChartTab     = ref('VOL')
const indicatorParams = ref({
  MACD: { fast: 12, slow: 26, signal: 9 },
  KDJ:  { n: 9 },
  RSI:  { period: 14 },
  BOLL: { period: 20, stdDev: 2 },
})
const currentQuote    = ref({})
const hoverData       = ref({})
const intervalStats   = ref(null)
const drillDownDate   = ref(null)   // YYYYMMDD，null = 普通模式
const drawingTool     = ref('')
const drawingColor    = ref('#fbbf24')
const magnetMode      = ref(true)
const drawingVisible  = ref(true)
const drawingLocked   = ref(false)
const ctxMenu         = ref({ visible: false, x: 0, y: 0, date: '', idx: -1 })

// ── 派生数据 ────────────────────────────────────────────────────
// activeSubCharts：subChartTab → BaseKLineChart subCharts 数组格式
const activeSubCharts = computed(() => {
  const map = { VOL: ['VOL'], MACD: ['VOL', 'MACD'], KDJ: ['VOL', 'KDJ'], RSI: ['VOL', 'RSI'], BOLL: ['VOL'] }
  return map[subChartTab.value] ?? ['VOL']
})

// MA 最新值（左上角浮显）
const maDisplays = computed(() => {
  const hist = visibleHist.value
  if (!hist.length) return []
  const closes = hist.map(h => h.close)
  const ma5  = calcMA(closes, 5)
  const ma10 = calcMA(closes, 10)
  const ma20 = calcMA(closes, 20)
  const last = hist.length - 1
  return [
    { period: 5,  color: '#ffffff', value: ma5[last]  ?? null },
    { period: 10, color: '#fbbf24', value: ma10[last] ?? null },
    { period: 20, color: '#c084fc', value: ma20[last] ?? null },
  ].filter(m => m.value != null)
})

const symbolName = computed(() => currentSymbolName.value || currentSymbol.value.replace(/^(sh|sz|us|hk|jp)/i, ''))

// 各周期单次拉取上限
const PERIOD_LIMITS = {
  daily: 5000, weekly: 500, monthly: 300,
  minutely: 300, '1min': 300, '5min': 300, '15min': 300, '30min': 300, '60min': 300,
}
const limit = computed(() => PERIOD_LIMITS[period.value] ?? 300)

// ── 实时行情轮询 ────────────────────────────────────────────────
let quotePollingTimer = null

async function fetchLatestQuote() {
  const sym = currentSymbol.value
  if (!sym || drillDownDate.value) return
  try {
    const data = await apiFetch(`/api/v1/market/quote/${sym}`)
    if (!data) return
    const quote = data.data || data
    if (quote.error) return
    currentQuote.value = {
      price:        quote.price,
      change:       quote.change,
      change_pct:   quote.change_pct,
      volume:       quote.volume,
      amount:      quote.amount,
      amplitude:    quote.amplitude,
      turnover_rate: quote.turnover_rate,
    }
    liveTick.value = {
      price:  quote.price,
      volume: quote.volume,
      time:   Date.now(),
    }
  } catch (e) {
    logger.error('[AdvancedKlinePanel] fetchLatestQuote error:', e.message)
  }
}

function startQuotePolling(intervalMs = 30_000) {
  stopQuotePolling()
  fetchLatestQuote()
  quotePollingTimer = setInterval(fetchLatestQuote, intervalMs)
}

function stopQuotePolling() {
  if (quotePollingTimer) {
    clearInterval(quotePollingTimer)
    quotePollingTimer = null
  }
}

// ── 数据获取 ────────────────────────────────────────────────────
async function fetchHistory(append = false) {
  const sym = currentSymbol.value
  if (!sym) return
  isLoading.value = true

  try {
    const params = new URLSearchParams({
      period: drillDownDate.value ? '1min' : period.value,
      limit:  String(limit.value),
      offset: append ? String(loadOffset.value) : '0',
      adjustment: adjustment.value,
    })
    if (drillDownDate.value) params.set('trade_date', drillDownDate.value)

    // ETF 代码路由：场内ETF（51/15/16/56开头）走专用基金API
    const url = _isEtfCode(sym)
      ? `/api/v1/fund/etf/history?code=${_etfCode(sym)}&${params}`
      : `/api/v1/market/history/${sym}?${params}`
    const data = await apiFetch(url)

    // 统一解包: data.history
    const payload = data?.data || data
    isFetching.value = payload?.fetching ?? data?.fetching ?? false

    const items = ((payload?.history || data?.history) || []).map(sanitizeItem)
    const isDesc = items.length >= 2 &&
      new Date(items[0].date).getTime() > new Date(items[items.length - 1].date).getTime()
    const sortedItems = isDesc ? [...items].reverse() : items

    if (append) {
      histData.value = [...sortedItems, ...histData.value]
      loadOffset.value += sortedItems.length
    } else {
      histData.value = sortedItems
      loadOffset.value = sortedItems.length
    }

    hasMore.value = payload?.has_more ?? items.length >= 300

    if (items.length > 0) {
      const last  = items[items.length - 1]
      const prev  = items[items.length - 2]
      currentQuote.value = {
        price:        last.close,
        change:       last.close - (prev?.close || last.close),
        change_pct:   last.change_pct ?? ((last.close - (prev?.close || last.close)) / (prev?.close || 1) * 100),
        volume:       last.volume,
        amount:       last.amount || (last.close * last.volume),
        amplitude:    last.amplitude,
        turnover_rate: last.turnover_rate,
      }
    }

    rebuildChartData()
  } catch (e) {
    logger.warn('[AdvancedKlinePanel] fetchHistory failed:', e)
  } finally {
    isLoading.value = false
  }
}

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

// ── 事件处理 ────────────────────────────────────────────────────
function onSymbolSelect(item) {
  setSymbol(item.symbol, item.name, '#00ff88', item.market)
  period.value = 'daily'
  loadOffset.value = 0
  histData.value = []
  overlayData.value = []
  overlaySymbol.value = ''
  overlayName.value = ''
  processedChartData.value = { isEmpty: true }
  fetchHistory()
}

function onPeriodChange(p) {
  period.value = p
  loadOffset.value = 0
  histData.value = []
  processedChartData.value = { isEmpty: true }
  fetchHistory()
}

function onOverlayChange(payload) {
  const sym  = typeof payload === 'string' ? payload : (payload?.symbol ?? '')
  const name  = typeof payload === 'string' ? '' : (payload?.name ?? sym)
  overlaySymbol.value = sym
  overlayName.value = name
  if (sym) fetchOverlayHistory(sym)
  else { overlayData.value = []; rebuildChartData() }
}

async function fetchOverlayHistory(sym) {
  if (!sym) { overlayData.value = []; return }
  try {
    const params = new URLSearchParams({ period: 'daily', limit: '3000', offset: '0' })
    const data = await apiFetch(`/api/v1/market/history/${sym}?${params}`)
    const raw = (data?.history || data?.data || []).map(r => ({
      date:  r.date || r.time || '',
      close: Number(r.close) || 0,
    })).reverse()
    overlayData.value = raw
    rebuildChartData()
  } catch (e) {
    logger.error('[AdvancedKlinePanel] fetchOverlayHistory error:', e.message)
    overlayData.value = []
  }
}

// DataZoom 事件（BaseKLineChart 向上传递缩放范围）
function onDataZoom({ start, end }) {
  // 懒加载：当左侧边缘 < 5% 时预加载更早数据
  if (start < 5 && hasMore.value && !isLoading.value) {
    fetchHistory(true)
  }
}

// ── 导出 PNG ────────────────────────────────────────────────────
async function exportPNG() {
  const inst = chartInstance.value
  if (!inst) return
  try {
    const chartUrl = inst.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: '#0f172a' })
    const container = chartContainerRef.value
    const w = container.clientWidth  * 2
    const h = container.clientHeight * 2
    const canvas = document.createElement('canvas')
    canvas.width = w; canvas.height = h
    const ctx = canvas.getContext('2d')
    const chartImg = new Image()
    await new Promise((resolve, reject) => { chartImg.onload = resolve; chartImg.onerror = reject; chartImg.src = chartUrl })
    ctx.drawImage(chartImg, 0, 0, w, h)
    if (drawingVisible.value && drawingCanvasRef.value?.$el) {
      const dc = drawingCanvasRef.value.$el.querySelector('canvas')
      if (dc) ctx.drawImage(dc, 0, 0, w, h)
    }
    const a = document.createElement('a')
    a.href = canvas.toDataURL('image/png')
    a.download = `${symbolName.value}_${period.value}_${Date.now()}.png`
    a.click()
  } catch (e) { logger.error('PNG导出失败:', e) }
}

// ── 区间统计 ────────────────────────────────────────────────────
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
        startDate: first.date, endDate: last.date, tradeDays: slice.length,
        changePct,
        maxAmplitude: +((Math.max(...highs) / Math.min(...lows) * 100) - 100).toFixed(2),
        highest: Math.max(...highs), lowest: Math.min(...lows),
        totalVolume: slice.reduce((a, h) => a + (h.volume || 0), 0),
        totalAmount: slice.reduce((a, h) => a + (h.amount || 0), 0),
        totalTurnoverRate: slice.reduce((a, h) => a + (h.turnover_rate || 0), 0),
      }
    }
    rangeStart.value = null
  }
}

// ── 右键菜单 ────────────────────────────────────────────────────
function onChartContextMenu(e) {
  if (drawingTool.value) return
  const rect = chartContainerRef.value.getBoundingClientRect()
  ctxMenu.value = { visible: true, x: e.clientX - rect.left, y: e.clientY - rect.top, date: '', idx: -1 }
  setTimeout(() => window.addEventListener('click', closeCtxMenu, { once: true }), 0)
}

function closeCtxMenu() { ctxMenu.value.visible = false }

function onDrillDown() {
  ctxMenu.value.visible = false
  if (ctxMenu.value.idx < 0 || !ctxMenu.value.date) return
  stopQuotePolling()
  drillDownDate.value = ctxMenu.value.date.replace(/-/g, '')
  period.value = '1min'
  loadOffset.value = 0
  histData.value = []
  processedChartData.value = { isEmpty: true }
  fetchHistory()
}

function exitDrillDown() {
  drillDownDate.value = null
  period.value = 'daily'
  loadOffset.value = 0
  histData.value = []
  processedChartData.value = { isEmpty: true }
  fetchHistory()
  // ⚡ WS 断开时显式重启 HTTP 降级；WS 连接时不需要
  if (wsStatus.value !== 'connected' && !quotePollingTimer) {
    startQuotePolling(30_000)
  }
}

// ── 画线事件（IndexedDB 持久化在 DrawingCanvas 内部处理）──────────
function onShapeDrawn()  {}
function onShapeDeleted() {}
function onShapesCleared() {}

// ── 监听响应 ────────────────────────────────────────────────────
// 指标/周期变化 → 重建图表数据
watch([period, yAxisType, subChartTab, indicatorParams], () => {
  rebuildChartData()
})

watch(currentSymbol, () => {
  fetchHistory()
  // ⚡ WS 状态由独立的 wsStatus watch 控制，symbol 切换本身不需要重启轮询
})

// ── 生命周期 ────────────────────────────────────────────────────
// 使用 WebSocket 实时行情
const { tick, connect: connectStream, disconnect: disconnectStream, connected, wsStatus } = useMarketStream()

// 监听 WebSocket tick 更新（节流 100ms）
const throttledTick = useThrottleFn((t) => {
  if (t && t.price) {
    liveTick.value = { price: t.price, volume: t.volume, time: t.time || Date.now() }
    currentQuote.value = {
      price: t.price, change: t.chg, change_pct: t.chg_pct,
      volume: t.volume, amount: t.amount,
    }
  }
}, 100)

watch(tick, (t) => { throttledTick(t) })

// 切换 symbol 时重新订阅
watch(currentSymbol, (sym) => {
  if (sym) {
    connectStream(sym)
  }
})

// ⚡ WS 断开时自动启用 HTTP 轮询降级；WS 恢复时静默停止
// 防止双重数据总线：WS 工作时 HTTP 轮询不运行
watch(wsStatus, (status) => {
  if (status === 'connected') {
    stopQuotePolling()
  } else if (status === 'disconnected' || status === 'failed') {
    if (!quotePollingTimer) {
      startQuotePolling(30_000)
    }
  }
})

onMounted(() => {
  fetchHistory()
  // 优先使用 WebSocket，回退到 HTTP 轮询（由 wsStatus watch 控制）
  const sym = currentSymbol.value
  if (sym) {
    connectStream(sym)
  }
})

onUnmounted(() => {
  stopQuotePolling()
  disconnectStream()
  const inst = baseChartRef.value?.getChartInstance?.()
  if (inst) {
    console.debug('[ECharts] 🗑️  disposed instance for AdvancedKlinePanel')
    inst.dispose()
  }
})
</script>
