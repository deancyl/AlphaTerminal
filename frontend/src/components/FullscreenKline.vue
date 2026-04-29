<template>
  <div class="fullscreen-kline" @keydown="handleKeydown" tabindex="0">
    <!-- 顶部工具栏 -->
    <header class="kline-header">
      <div class="header-left">
        <span class="symbol-name">{{ props.name || props.symbol || '--' }}</span>
        <span class="symbol-code">{{ props.symbol ?? '--' }}</span>
      </div>

      <!-- 工具栏：横向滚动，不换行 -->
      <div class="header-center flex-nowrap overflow-x-auto scrollbar-hide shrink-0 max-w-full">
        <!-- 横屏按钮：仅移动端显示，最左侧 -->
        <button class="md:hidden shrink-0 text-[10px] bg-theme-secondary/20 px-2 py-1 rounded mr-2" @click="toggleMobileLandscape" title="横屏（仅安卓）">🔄 横屏</button>
        <!-- 周期选择 -->
        <div class="period-selector flex-nowrap shrink-0">
          <button
            v-for="p in periods"
            :key="p.value"
            :class="['period-btn shrink-0', { active: period === p.value }]"
            @click="period = p.value"
          >
            {{ p.label }}
          </button>
        </div>

        <!-- 副图选择 -->
        <div class="indicator-selector flex-nowrap shrink-0">
          <button
            v-for="ind in subChartOptions"
            :key="ind.key"
            :class="['indicator-btn shrink-0', { active: activeSubChart === ind.key }]"
            @click="activeSubChart = ind.key"
          >
            {{ ind.label }}
          </button>
        </div>
      </div>

      <div class="header-right shrink-0 flex items-center gap-2">
        <span class="latest-price" :class="priceColor">{{ latestPriceText }}</span>
        <span class="latest-change" :class="priceColor">{{ latestChangeText }}</span>
        <button 
          class="text-xs px-2 py-1 rounded bg-terminal-accent/20 text-terminal-accent hover:bg-terminal-accent/30 transition"
          @click="showDetail = true"
          title="F9 深度资料"
        >
          📋 F9
        </button>
        <button class="close-btn" @click="emit('close')">✕ 关闭</button>
      </div>
    </header>

    <!-- 主体区域 -->
    <div class="kline-body">
      <!-- 左侧图表区 -->
      <div class="chart-container">
        <!-- 加载状态 -->
        <div v-if="loading" class="loading-overlay">
          <div class="loading-text">加载中...</div>
        </div>

        <!-- 错误状态 -->
        <div v-else-if="chartError" class="error-overlay">
          <div class="error-text">{{ chartError }}</div>
          <button class="error-close" @click="chartError = ''">关闭</button>
        </div>

        <!-- ECharts 容器 -->
        <div ref="chartEl" class="chart-wrapper"></div>

        <!-- 十字指针覆盖层 -->
        <CrosshairOverlay
          v-if="!loading && !chartError"
          ref="crosshairRef"
          :chart-instance="chart"
          :data="histData"
          :visible="crosshairState.visible"
          :locked="drawingStore.isDrawing || drawingStore.locked"
          :show-labels="crosshairState.showLabels"
          :show-tooltip="crosshairState.showTooltip"
          class="crosshair-overlay"
          @candle-hover="onCandleHover"
        />

        <!-- 画线 Canvas 覆盖层 -->
        <DrawingCanvas
          v-if="!isMobile && drawingStore.visible"
          ref="drawingCanvasRef"
          :chart-instance="chart"
          :active-tool="drawingStore.activeTool"
          :active-color="drawingStore.activeColor"
          :magnet-mode="drawingStore.magnetMode"
          :locked="drawingStore.locked"
          :symbol="props.symbol"
          :period="period"
          class="drawing-canvas"
          @drawn="onShapeDrawn"
          @deleted="onShapeDeleted"
          @cleared="onShapesCleared"
        />

        <!-- 画线工具栏 -->
        <DrawingToolbar
          v-if="!isMobile"
          :active-color="drawingStore.activeColor"
          :magnet-mode="drawingStore.magnetMode"
          :visible="drawingStore.visible"
          :locked="drawingStore.locked"
          class="drawing-toolbar"
          @tool-change="drawingStore.toggleTool"
          @color-change="drawingStore.setColor"
          @magnet-toggle="drawingStore.toggleMagnet"
          @visibility-toggle="drawingStore.toggleVisible"
          @lock-toggle="drawingStore.toggleLocked"
          @clear="onClearDrawings"
        />
      </div>

      <!-- 右侧信息面板 -->
      <QuotePanel
        :symbol="props.symbol"
        :name="props.name"
        :realtimeData="quoteData"
        :latestCandle="latestCandle"
        class="quote-panel-wrapper"
      />
    </div>

    <!-- F9 深度资料面板 -->
    <Teleport to="body">
      <Transition
        enter-active-class="transition-opacity duration-200 ease-out"
        enter-from-class="opacity-0"
        enter-to-class="opacity-100"
        leave-active-class="transition-opacity duration-150 ease-in"
        leave-from-class="opacity-100"
        leave-to-class="opacity-0"
      >
        <div
          v-if="showDetail"
          class="fixed inset-0 z-[100000] bg-terminal-bg"
        >
          <StockDetail
            :symbol="props.symbol"
            :name="props.name"
            @close="showDetail = false"
          />
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, onBeforeUnmount, nextTick } from 'vue'
import { useBreakpoints, breakpointsTailwind, useThrottleFn } from '@vueuse/core'
import { apiFetch } from '../utils/api.js'
import { logger } from '../utils/logger.js'
import { useMarketStream } from '../composables/useMarketStream.js'
// echarts 从 CDN 加载 via window.echarts
import { useDrawingStore } from '../stores/drawing.js'
import { getChartColors, onThemeChange } from '../composables/useTheme.js'
import QuotePanel from './QuotePanel.vue'
import DrawingCanvas from './DrawingCanvas.vue'
import DrawingToolbar from './DrawingToolbar.vue'
import CrosshairOverlay from './CrosshairOverlay.vue'
import StockDetail from './StockDetail.vue'



const props = defineProps({
  symbol: { type: String, required: true },
  name:   { type: String, default: '' },
  type:   { type: String, default: '' },   // 补充缺失的 type prop，修复 Vue warn
})

const emit = defineEmits(['close', 'symbol-change'])

const toggleMobileLandscape = async () => {
  try {
    if (!document.fullscreenElement) {
      await document.documentElement.requestFullscreen()
      await screen.orientation?.lock('landscape')
    } else {
      await document.exitFullscreen()
      screen.orientation?.unlock()
    }
    // 全屏切换完成后触发图表重绘
    setTimeout(handleResize, 150)
  } catch (e) {
    console.warn('横屏切换失败(可能是iOS限制):', e)
    alert('当前设备或浏览器不支持强制横屏，请手动旋转手机。')
  }
}

// ── 移动端断点侦听（sprint 2-2 性能降级）────────────────────────────────────
// useBreakpoints(breakpointsTailwind) 返回 Breakpoints 对象，直接调用 .smaller() 方法
// 不需要也不应该加 .value（该对象本身已是响应式的）
const breakpoints = useBreakpoints(breakpointsTailwind)
const isMobile = computed(() => {
  try {
    return breakpoints.smaller('md').value
  } catch (_) {
    return false  // 防御：初始化阶段 breakpoints 未就绪时返回 false
  }
})

// ── 全屏黑屏修复：确保 DOM 有真实像素尺寸后再 init ECharts ──────────────────
async function waitForDimensions(el, timeout = 1000) {
  const start = performance.now()
  while (el && (el.clientWidth === 0 || el.clientHeight === 0)) {
    if (performance.now() - start > timeout) break
    await new Promise(r => requestAnimationFrame(r))
  }
}

// Pinia Store
const drawingStore = useDrawingStore()

// 状态
const period = ref('daily')
const loading = ref(false)
const chartError = ref('')
const histData = ref([])
const quoteData = ref({})
const latestPrice = ref(null)
const latestChange = ref(0)

// 图表实例
const chartEl = ref(null)
let chart = null
let refreshTimer = null  // F1修复: K线自动刷新定时器

// 十字指针状态
const crosshairRef = ref(null)
const crosshairState = ref({
  visible: true,
  showLabels: true,
  showTooltip: true,
})
const hoveredCandle = ref(null)

// 画线相关
const drawingCanvasRef = ref(null)

// 周期选项
const periods = [
  { label: '日K', value: 'daily' },
  { label: '周K', value: 'weekly' },
  { label: '月K', value: 'monthly' },
  { label: '5分', value: '5min' },
  { label: '15分', value: '15min' },
  { label: '30分', value: '30min' },
  { label: '60分', value: '60min' },
]

// 副图选项
const subChartOptions = [
  { key: 'VOL', label: '成交量' },
  { key: 'MACD', label: 'MACD' },
  { key: 'KDJ', label: 'KDJ' },
  { key: 'RSI', label: 'RSI' },
  { key: 'BOLL', label: '布林带' },
  { key: 'OBV', label: 'OBV' },
  { key: 'DMI', label: 'DMI' },
  { key: 'CCI', label: 'CCI' },
]
const activeSubChart = ref('VOL')
const showDetail = ref(false)

// 移动端降维：强制只保留 VOL，避免多重指标导致 Canvas 重绘卡顿
watch(isMobile, (mobile) => {
  if (mobile) activeSubChart.value = 'VOL'
})

// 计算属性
const priceColor = computed(() => {
  if (latestChange.value > 0) return 'price-up'
  if (latestChange.value < 0) return 'price-down'
  return 'price-flat'
})

const latestCandle = computed(() => {
  if (histData.value.length === 0) return null
  return histData.value[histData.value.length - 1]
})

const latestPriceText = computed(() => {
  if (latestPrice.value == null) return '--'
  return latestPrice.value.toFixed(2)
})

const latestChangeText = computed(() => {
  if (latestChange.value == null) return '--'
  const sign = latestChange.value >= 0 ? '+' : ''
  return `${sign}${latestChange.value.toFixed(2)}%`
})

function onCandleHover(candle) {
  hoveredCandle.value = candle
}

// 画线工具事件处理
function onClearDrawings() {
  drawingCanvasRef.value?.clearAll()
}

function onShapeDrawn(shape) {
  logger.log('[FullscreenKline] Shape drawn:', shape)
}

function onShapeDeleted(id) {
  logger.log('[FullscreenKline] Shape deleted:', id)
}

function onShapesCleared() {
  logger.log('[FullscreenKline] All shapes cleared')
}

// 键盘快捷键
function handleKeydown(e) {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return

  const toolMap = {
    't': 'trend', 'T': 'trend',
    'l': 'line', 'L': 'line',
    'r': 'ray', 'R': 'ray',
    's': 'segment', 'S': 'segment',
    'h': 'hray', 'H': 'hray',
    'c': 'channel', 'C': 'channel',
    'f': 'fib', 'F': 'fib',
    'q': 'rect', 'Q': 'rect',
    'a': 'text', 'A': 'text',
  }

  if (toolMap[e.key]) {
    e.preventDefault()
    const tool = toolMap[e.key]
    drawingStore.toggleTool(tool)
    return
  }

  if (e.key === 'Delete' || e.key === 'Backspace') {
    drawingCanvasRef.value?.deleteSelected()
    return
  }

  if (e.key === 'Escape') {
    drawingStore.setTool('')
    return
  }

  if (e.key === 'm' || e.key === 'M') {
    drawingStore.toggleMagnet()
    return
  }

  if (e.key === 'v' || e.key === 'V') {
    drawingStore.toggleVisible()
    return
  }
}

// 修复F5: window 级别快捷键（Esc 关闭全屏，焦点丢失时也能响应）
function handleWindowKeydown(e) {
  // F9: 打开深度资料面板（仅在FullscreenKline中）
  if (e.key === 'F9' || e.key === 'f9') {
    e.preventDefault()
    showDetail.value = true
    return
  }
  
  if (e.key === 'Escape') {
    // 如果StockDetail打开，先关闭它
    if (showDetail.value) {
      showDetail.value = false
      return
    }
    emit('close')
  }
}

// 获取历史数据
async function fetchData() {
  if (!props.symbol) return
  loading.value = true
  chartError.value = ''

  try {
    const params = new URLSearchParams({
      period: period.value,
      limit: '500',
      offset: '0',
    })

    // 修复: 使用 apiFetch 兼容统一响应格式 {code, message, data}
    const d = await apiFetch(`/api/v1/market/history/${props.symbol}?${params}`)
    const historyArray = d?.history || d || []

    if (!Array.isArray(historyArray) || historyArray.length === 0) {
      chartError.value = '暂无历史数据'
      histData.value = []
      return
    }

    histData.value = historyArray.sort((a, b) => new Date(a.date) - new Date(b.date))

    const last = histData.value[histData.value.length - 1]
    latestPrice.value = last.close ?? last.price
    latestChange.value = last.change_pct ?? 0

    // ── 全屏黑屏修复：nextTick 确保 DOM 已挂载，再等物理尺寸，再渲染 ──
    await nextTick()
    await waitForDimensions(chartEl.value)
    renderChart()

  } catch (e) {
    chartError.value = `加载失败: ${e.message}`
    logger.error('[FullscreenKline] fetchData error:', e)
  } finally {
    loading.value = false
  }
}

// 获取实时行情
async function fetchQuote() {
  if (!props.symbol) return
  try {
    // 修复: 使用正确的实时行情端点
    const d = await apiFetch(`/api/v1/market/quote_detail/${props.symbol}?_t=${Date.now()}`)
    if (d) quoteData.value = d.data || d
  } catch (e) {
    logger.warn('[FullscreenKline] fetchQuote error:', e.message)
  }
}

// 渲染图表
async function renderChart() {
  if (!chartEl.value || histData.value.length === 0) return

  // ── 全屏黑屏修复：等 DOM 拿到真实尺寸后再 init ──────────────────────
  await nextTick()
  await waitForDimensions(chartEl.value)
  if (!chartEl.value) return

  if (!chart) {
    chart = window.echarts.init(chartEl.value)
    // 初始化 ResizeObserver（替换全局 window.resize）
    if (chartEl.value) {
      const ro = new ResizeObserver((entries) => {
        const { width, height } = entries[0].contentRect
        if (width > 0 && height > 0) {
          console.debug(`[ECharts] 📐 resize fullscreenKline @ ${width.toFixed(0)}×${height.toFixed(0)}`)
          chart?.resize()
        }
      })
      ro.observe(chartEl.value)
      // 清理时通过 onBeforeUnmount 处理
      _fullscreenRO = ro
    }
  }

  const tc = getChartColors()

  const data = histData.value
  const dates = data.map(d => d.date)
  const klineData = data.map(d => [d.open, d.close, d.low, d.high])

  const ma5 = calcMA(data, 5)
  const ma10 = calcMA(data, 10)
  const ma20 = calcMA(data, 20)
  const ma60 = calcMA(data, 60)

  const subChartData = calcSubChartData(data, activeSubChart.value, tc)

  const option = {
    backgroundColor: 'transparent',
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: tc.tooltipBg,
      borderColor: tc.tooltipBorder,
      textStyle: { color: tc.tooltipText, fontSize: 11 },
    },
    legend: {
      data: ['K线', 'MA5', 'MA10', 'MA20', 'MA60', ...subChartData.legend],
      textStyle: { color: tc.textSecondary, fontSize: 10 },
      top: 5,
      left: 60,
    },
    grid: [
      { left: 60, right: 20, top: 40, height: '52%' },
      { left: 60, right: 20, top: '68%', height: '24%' },
    ],
    xAxis: [
      { type: 'category', data: dates, gridIndex: 0, axisLabel: { show: false }, axisLine: { lineStyle: { color: tc.borderPrimary } } },
      { type: 'category', data: dates, gridIndex: 1, axisLabel: { color: tc.chartText, fontSize: 10 }, axisLine: { lineStyle: { color: tc.borderPrimary } } },
    ],
    yAxis: [
      { type: 'value', gridIndex: 0, scale: true, splitLine: { lineStyle: { color: tc.chartGrid } }, axisLabel: { color: tc.chartText, fontSize: 10 } },
      { type: 'value', gridIndex: 1, scale: subChartData.scale, splitLine: { lineStyle: { color: tc.chartGrid, type: 'dashed' } }, axisLabel: { color: tc.chartText, fontSize: 10 } },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 50, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1], show: true, bottom: 8, height: 18,
        borderColor: tc.borderPrimary,
        fillerColor: tc.isLight ? 'rgba(24,144,255,0.15)' : 'rgba(59,130,246,0.15)',
        handleStyle: { color: tc.accentPrimary, borderColor: tc.accentPrimary },
        textStyle: { color: tc.chartText, fontSize: 9 },
        dataBackground: { lineStyle: { color: tc.borderPrimary }, areaStyle: { color: tc.isLight ? 'rgba(24,144,255,0.08)' : 'rgba(59,130,246,0.08)' } }
      },
    ],
    series: [
      { name: 'K线', type: 'candlestick', xAxisIndex: 0, yAxisIndex: 0, data: klineData, itemStyle: { color: tc.bullish, color0: tc.bearish, borderColor: tc.bullish, borderColor0: tc.bearish } },
      { name: 'MA5', type: 'line', xAxisIndex: 0, yAxisIndex: 0, data: ma5, smooth: true, lineStyle: { color: tc.ma5, width: 1 }, symbol: 'none' },
      { name: 'MA10', type: 'line', xAxisIndex: 0, yAxisIndex: 0, data: ma10, smooth: true, lineStyle: { color: tc.ma10, width: 1 }, symbol: 'none' },
      { name: 'MA20', type: 'line', xAxisIndex: 0, yAxisIndex: 0, data: ma20, smooth: true, lineStyle: { color: tc.ma20, width: 1 }, symbol: 'none' },
      { name: 'MA60', type: 'line', xAxisIndex: 0, yAxisIndex: 0, data: ma60, smooth: true, lineStyle: { color: tc.ma60, width: 1 }, symbol: 'none' },
      ...subChartData.series,
    ],
  }

  chart.setOption(option, true)
}

// 计算副图指标数据
function calcSubChartData(data, indicator, tc) {
  const closes = data.map(d => d.close)
  const volumes = data.map(d => d.volume)

  switch (indicator) {
    case 'VOL':
      return {
        legend: ['成交量'],
        scale: false,
        series: [{
          name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: volumes,
          itemStyle: { color: (params) => data[params.dataIndex].close >= data[params.dataIndex].open ? tc.bullish : tc.bearish },
        }]
      }
    case 'MACD':
      const macd = calcMACD(closes)
      return {
        legend: ['DIF', 'DEA', 'MACD'], scale: true,
        series: [
          { name: 'DIF', type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: macd.dif, lineStyle: { color: tc.ma5, width: 1 }, symbol: 'none' },
          { name: 'DEA', type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: macd.dea, lineStyle: { color: tc.ma10, width: 1 }, symbol: 'none' },
          { name: 'MACD', type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: macd.macd, itemStyle: { color: (p) => p.value >= 0 ? tc.bullish : tc.bearish } },
        ]
      }
    case 'KDJ':
      const kdj = calcKDJ(data)
      return {
        legend: ['K', 'D', 'J'], scale: true,
        series: [
          { name: 'K', type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: kdj.k, lineStyle: { color: tc.ma5, width: 1 }, symbol: 'none' },
          { name: 'D', type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: kdj.d, lineStyle: { color: tc.ma10, width: 1 }, symbol: 'none' },
          { name: 'J', type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: kdj.j, lineStyle: { color: tc.ma60, width: 1 }, symbol: 'none' },
        ]
      }
    case 'RSI':
      return {
        legend: ['RSI6', 'RSI12', 'RSI24'], scale: true,
        series: [
          { name: 'RSI6', type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: calcRSI(closes, 6), lineStyle: { color: tc.ma5, width: 1 }, symbol: 'none' },
          { name: 'RSI12', type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: calcRSI(closes, 12), lineStyle: { color: tc.ma10, width: 1 }, symbol: 'none' },
          { name: 'RSI24', type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: calcRSI(closes, 24), lineStyle: { color: tc.ma20, width: 1 }, symbol: 'none' },
        ]
      }
    case 'BOLL':
      const boll = calcBOLL(closes)
      return {
        legend: ['MID', 'UP', 'LOW'], scale: true,
        series: [
          { name: 'MID', type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: boll.mid, lineStyle: { color: tc.ma5, width: 1.2 }, symbol: 'none' },
          { name: 'UP', type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: boll.up, lineStyle: { color: tc.bullish, width: 1 }, symbol: 'none' },
          { name: 'LOW', type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: boll.low, lineStyle: { color: tc.bearish, width: 1 }, symbol: 'none' },
        ]
      }
    case 'OBV':
      const obv = calcOBV(data)
      return {
        legend: ['OBV', 'MA30'], scale: true,
        series: [
          { name: 'OBV', type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: obv, lineStyle: { color: tc.ma5, width: 1 }, symbol: 'none' },
          { name: 'MA30', type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: calcMA(obv.map(v => ({ close: v })), 30), lineStyle: { color: tc.ma10, width: 1 }, symbol: 'none' },
        ]
      }
    case 'DMI':
      const dmi = calcDMI(data)
      return {
        legend: ['PDI', 'MDI', 'ADX'], scale: true,
        series: [
          { name: 'PDI', type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: dmi.pdi, lineStyle: { color: tc.bullish, width: 1 }, symbol: 'none' },
          { name: 'MDI', type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: dmi.mdi, lineStyle: { color: tc.bearish, width: 1 }, symbol: 'none' },
          { name: 'ADX', type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: dmi.adx, lineStyle: { color: tc.ma10, width: 1 }, symbol: 'none' },
        ]
      }
    case 'CCI':
      return {
        legend: ['CCI'], scale: true,
        series: [{ name: 'CCI', type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: calcCCI(data), lineStyle: { color: tc.ma5, width: 1 }, symbol: 'none' }]
      }
    default:
      return { legend: [], scale: false, series: [] }
  }
}

function calcMA(data, period) {
  const result = []
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) { result.push('-'); continue }
    let sum = 0
    for (let j = 0; j < period; j++) sum += data[i - j].close ?? data[i - j]
    result.push((sum / period).toFixed(2))
  }
  return result
}

function calcEMA(data, period) {
  const k = 2 / (period + 1)
  const result = []
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) result.push('-')
    else if (i === period - 1) { let sum = 0; for (let j = 0; j < period; j++) sum += data[i - j]; result.push((sum / period).toFixed(2)) }
    else { const ema = data[i] * k + parseFloat(result[i - 1]) * (1 - k); result.push(ema.toFixed(2)) }
  }
  return result
}

function calcMACD(closes, fast = 12, slow = 26, signal = 9) {
  const emaFast = calcEMA(closes, fast)
  const emaSlow = calcEMA(closes, slow)
  const dif = emaFast.map((v, i) => v === '-' || emaSlow[i] === '-' ? '-' : (parseFloat(v) - parseFloat(emaSlow[i])).toFixed(2))
  const dea = calcEMA(dif.filter(v => v !== '-').map(v => parseFloat(v)), signal)
  const fullDea = new Array(dif.filter(v => v === '-').length).fill('-').concat(dea)
  const macd = dif.map((v, i) => v === '-' || fullDea[i] === '-' ? '-' : ((parseFloat(v) - parseFloat(fullDea[i])) * 2).toFixed(2))
  return { dif, dea: fullDea, macd }
}

function calcKDJ(data, n = 9) {
  const k = [], d = [], j = []
  for (let i = 0; i < data.length; i++) {
    if (i < n - 1) { k.push('-'); d.push('-'); j.push('-'); continue }
    let low = data[i].low, high = data[i].high
    for (let x = 1; x < n; x++) { low = Math.min(low, data[i - x].low); high = Math.max(high, data[i - x].high) }
    const rsv = high === low ? 0 : (data[i].close - low) / (high - low) * 100
    if (i === n - 1) { k.push(rsv.toFixed(2)); d.push(rsv.toFixed(2)) }
    else {
      const kVal = (2 / 3 * parseFloat(k[i - 1]) + 1 / 3 * rsv).toFixed(2)
      const dVal = (2 / 3 * parseFloat(d[i - 1]) + 1 / 3 * parseFloat(kVal)).toFixed(2)
      k.push(kVal); d.push(dVal)
    }
    j.push((3 * parseFloat(k[i]) - 2 * parseFloat(d[i])).toFixed(2))
  }
  return { k, d, j }
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

function calcBOLL(closes, period = 20, multiplier = 2) {
  const mid = calcMA(closes.map(c => ({ close: c })), period)
  const up = [], low = []
  for (let i = 0; i < closes.length; i++) {
    if (i < period - 1) { up.push('-'); low.push('-'); continue }
    let sum = 0
    for (let j = 0; j < period; j++) sum += Math.pow(closes[i - j] - parseFloat(mid[i]), 2)
    const std = Math.sqrt(sum / period)
    up.push((parseFloat(mid[i]) + multiplier * std).toFixed(2))
    low.push((parseFloat(mid[i]) - multiplier * std).toFixed(2))
  }
  return { mid, up, low }
}

function calcOBV(data) {
  const result = [0]
  for (let i = 1; i < data.length; i++) {
    const change = data[i].close - data[i - 1].close
    const vol = change > 0 ? data[i].volume : change < 0 ? -data[i].volume : 0
    result.push(result[i - 1] + vol)
  }
  return result.map(v => v / 1e6)
}

function calcDMI(data, period = 14) {
  const pdi = [], mdi = [], adx = []
  const tr = [], plusDM = [], minusDM = []
  for (let i = 1; i < data.length; i++) {
    const highDiff = data[i].high - data[i - 1].high
    const lowDiff = data[i - 1].low - data[i].low
    plusDM.push(highDiff > lowDiff && highDiff > 0 ? highDiff : 0)
    minusDM.push(lowDiff > highDiff && lowDiff > 0 ? lowDiff : 0)
    tr.push(Math.max(data[i].high - data[i].low, Math.abs(data[i].high - data[i - 1].close), Math.abs(data[i].low - data[i - 1].close)))
  }
  for (let i = 0; i < data.length; i++) {
    if (i < period) { pdi.push('-'); mdi.push('-'); adx.push('-'); continue }
    let trSum = 0, plusDMSum = 0, minusDMSum = 0
    for (let j = 0; j < period; j++) { trSum += tr[i - j - 1]; plusDMSum += plusDM[i - j - 1]; minusDMSum += minusDM[i - j - 1] }
    pdi.push((plusDMSum / trSum * 100).toFixed(2))
    mdi.push((minusDMSum / trSum * 100).toFixed(2))
    const dx = (Math.abs(parseFloat(pdi[i]) - parseFloat(mdi[i])) / (parseFloat(pdi[i]) + parseFloat(mdi[i])) * 100).toFixed(2)
    if (i === period) adx.push(dx)
    else adx.push(((parseFloat(adx[i - 1]) * (period - 1) + parseFloat(dx)) / period).toFixed(2))
  }
  return { pdi, mdi, adx }
}

function calcCCI(data, period = 14) {
  const result = []
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) { result.push('-'); continue }
    let tpSum = 0
    for (let j = 0; j < period; j++) tpSum += (data[i - j].high + data[i - j].low + data[i - j].close) / 3
    const sma = tpSum / period
    let mdSum = 0
    for (let j = 0; j < period; j++) mdSum += Math.abs((data[i - j].high + data[i - j].low + data[i - j].close) / 3 - sma)
    const md = mdSum / period
    const tp = (data[i].high + data[i].low + data[i].close) / 3
    result.push(md === 0 ? '0' : ((tp - sma) / (0.015 * md)).toFixed(2))
  }
  return result
}

function handleResize() {
  chart?.resize()
}

let _fullscreenRO = null
let unsubscribeTheme = null

watch(activeSubChart, () => renderChart())
watch(period, () => fetchData())
// 使用 WebSocket 实时行情
const { tick, connect: connectStream, disconnect: disconnectStream, wsStatus } = useMarketStream()

// 节流处理 WebSocket tick，避免频繁重绘
const throttledTick = useThrottleFn((t) => {
  if (t && t.price) {
    latestPrice.value = t.price
  }
}, 100)

watch(tick, (t) => { throttledTick(t) })

// ⚡ WS 断开时自动启用 HTTP 轮询降级；WS 恢复时静默停止轮询
// 防止双重数据总线：WS 工作时 HTTP 轮询不运行
watch(wsStatus, (status) => {
  if (status === 'connected') {
    // WS 已恢复，停止 HTTP 轮询
    if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null }
  } else if (status === 'disconnected' || status === 'failed') {
    // WS 断开且仍有订阅对象，启动 HTTP 降级轮询
    if (!refreshTimer && props.symbol) {
      refreshTimer = setInterval(() => {
        if (props.symbol) { fetchData(); fetchQuote() }
      }, 30_000)
    }
  }
})

watch(() => props.symbol, (newSym) => { 
  if (newSym) { fetchData(); fetchQuote(); connectStream(newSym) } 
  else { console.warn('[FullscreenKline] symbol 变空，关闭全屏'); emit('close') }
}, { immediate: true })

onMounted(async () => { 
  // ── 防空：symbol 为空时打印警告，emit close 关闭全屏容器 ──
  if (!props.symbol) {
    console.warn('[FullscreenKline] 收到空的 symbol，取消加载并关闭全屏')
    emit('close')
    return
  }
  fetchData(); fetchQuote(); connectStream(props.symbol)
  // 修复F5: 注册 window 级别键盘事件（Esc 关闭全屏 / 快捷键切换画线工具）
  window.addEventListener('keydown', handleWindowKeydown)
  
  // 主题变化自动重绘
  unsubscribeTheme = onThemeChange(() => {
    renderChart()
  })

  // ⚡ HTTP 轮询已移至 wsStatus watch：WS connected 时不运行，仅作降级方案

  // ── 全屏黑屏修复：全屏进入 Teleport 到 body 后，强制等待布局稳定再 resize ──
  await nextTick()
  await new Promise(r => requestAnimationFrame(r))   // 等 CSS paint 完成
  chart?.resize()
})

// 修复F3: onBeforeUnmount 确保 ECharts 在组件卸载前立即释放（比 onUnmounted 更可靠）
onBeforeUnmount(() => {
  if (chart) {
    console.debug(`[ECharts] 🗑️  disposed instance for fullscreenKline: ${props.symbol}`)
    chart.dispose()
    chart = null
  }
  // F1修复: 清理自动刷新定时器
  if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null }
  disconnectStream()
  window.removeEventListener('keydown', handleWindowKeydown)
  unsubscribeTheme?.()
  unsubscribeTheme = null
  _fullscreenRO?.disconnect()
  _fullscreenRO = null
})

onUnmounted(() => { 
  // 双重保险：onUnmounted 也清理一次
  if (chart) {
    chart.dispose()
    chart = null
  }
})
</script>

<style>
.fullscreen-kline { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: var(--bg-primary); display: flex; flex-direction: column; z-index: 99999; outline: none; }

.kline-header { height: 48px; background: var(--panel-bg); border-bottom: 1px solid var(--border-primary); display: flex; align-items: center; justify-content: space-between; padding: 0 16px; flex-shrink: 0; }
.header-left { display: flex; align-items: center; gap: 8px; min-width: 150px; }
.symbol-name { font-size: 14px; font-weight: 600; color: var(--text-primary); }
.symbol-code { font-size: 11px; color: var(--text-tertiary); font-family: monospace; }
.header-center { display: flex; align-items: center; gap: 16px; flex: 1; justify-content: center; }
.period-selector, .indicator-selector { display: flex; gap: 4px; }
.period-btn, .indicator-btn { padding: 4px 10px; font-size: 12px; border: 1px solid var(--border-primary); background: transparent; color: var(--text-secondary); border-radius: 4px; cursor: pointer; transition: all 0.2s; }
.period-btn:hover, .indicator-btn:hover { border-color: var(--border-hover); color: var(--text-primary); }
.period-btn.active, .indicator-btn.active { background: var(--accent-primary); border-color: var(--accent-primary); color: var(--bg-primary); }
.header-right { display: flex; align-items: center; gap: 12px; min-width: 200px; justify-content: flex-end; }
.latest-price { font-size: 16px; font-weight: 700; font-family: monospace; }
.latest-change { font-size: 13px; font-family: monospace; }
.price-up { color: var(--bullish); }
.price-down { color: var(--bearish); }
.price-flat { color: var(--text-tertiary); }
.close-btn { padding: 6px 14px; font-size: 12px; border: 1px solid var(--border-hover); background: transparent; color: var(--text-secondary); border-radius: 4px; cursor: pointer; transition: all 0.2s; }
.close-btn:hover { border-color: var(--status-error); color: var(--status-error); }

.kline-body { flex: 1; display: flex; overflow: hidden; }
.chart-container { flex: 1; position: relative; min-width: 0; }
.chart-wrapper { position: absolute; top: 0; left: 0; right: 0; bottom: 0; }

.loading-overlay, .error-overlay { position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: var(--bg-primary); display: flex; flex-direction: column; align-items: center; justify-content: center; z-index: 10; opacity: 0.95; }
.loading-text, .error-text { font-size: 14px; color: var(--text-secondary); }
.error-close { margin-top: 12px; padding: 6px 16px; font-size: 12px; border: 1px solid var(--border-hover); background: transparent; color: var(--text-secondary); border-radius: 4px; cursor: pointer; }
.error-close:hover { border-color: var(--border-hover); color: var(--text-primary); }

.drawing-canvas { position: absolute; top: 48px; left: 0; right: 0; bottom: 0; z-index: 5; }
.drawing-toolbar { position: absolute; top: 56px; left: 12px; z-index: 10; }
.crosshair-overlay { position: absolute; top: 48px; left: 0; right: 0; bottom: 0; z-index: 6; }
.crosshair-overlay { position: absolute; top: 48px; left: 0; right: 0; bottom: 0; z-index: 6; }

.quote-panel-wrapper { width: 300px; flex-shrink: 0; height: 100%; overflow: hidden; }
.quote-panel-wrapper :deep(.quote-panel) { height: 100% !important; max-width: none !important; min-width: auto !important; }

@media (max-width: 768px) {
  .quote-panel-wrapper { display: none; }
  .header-center { flex-direction: column; gap: 8px; }
  .symbol-code { display: none; }
}
</style>
