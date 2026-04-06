<template>
  <div class="index-chart-root flex flex-col bg-[#0a0e17]">
    <!-- 顶部紧凑控制栏：复用 ChartToolbar，统一状态驱动 -->
    <ChartToolbar
      :symbol="symbol"
      :period="currentPeriod"
      @period-change="onPeriodChange"
      @indicator-change="onIndicatorChange"
      @fullscreen="toggleFullscreen"
    />

    <!-- 主图表区域：占满所有剩余空间 -->
    <div class="flex flex-1 min-h-0 relative">
      <!-- 左侧画线工具栏 -->
      <DrawingToolbar
        :active-tool="activeTool"
        @tool-select="onToolSelect"
      />

      <!-- 中央图表 + 悬浮 OHLC 数据板 -->
      <div class="flex-1 min-w-0 relative" ref="chartWrapRef">
        <!-- 图表画布 -->
        <div ref="chartRef" class="w-full h-full" />

        <!-- 悬浮 OHLC 数据板（左上角） -->
        <div
          v-if="lastCandle"
          class="absolute top-2 left-2 z-10 flex gap-4 text-xs bg-[#0d1117]/90 border border-[#1e2a3a] rounded px-3 py-1.5 pointer-events-none"
        >
          <span class="text-[#8b949e]">开<span class="ml-1 font-mono" :class="priceTextClass">{{ lastCandle.open.toFixed(2) }}</span></span>
          <span class="text-[#8b949e]">高<span class="ml-1 font-mono text-[#f0883e]">{{ lastCandle.high.toFixed(2) }}</span></span>
          <span class="text-[#8b949e]">低<span class="ml-1 font-mono text-[#3fb950]">{{ lastCandle.low.toFixed(2) }}</span></span>
          <span class="text-[#8b949e]">收<span class="ml-1 font-mono" :class="priceTextClass">{{ lastCandle.close.toFixed(2) }}</span></span>
          <span class="text-[#8b949e]">量<span class="ml-1 font-mono text-[#8b949e]">{{ formatVolume(lastCandle.volume) }}</span></span>
          <span class="ml-1 font-mono" :class="changePctClass">{{ changePctStr }}</span>
        </div>

        <!-- 加载动画 -->
        <div v-if="loading" class="absolute inset-0 flex items-center justify-center bg-[#0a0e17]/70 z-20">
          <div class="flex flex-col items-center gap-2">
            <div class="w-8 h-8 border-2 border-[#58a6ff] border-t-transparent rounded-full animate-spin" />
            <span class="text-xs text-[#8b949e]">{{ loadingMsg }}</span>
          </div>
        </div>

        <!-- 错误提示 -->
        <div v-if="chartError" class="absolute bottom-2 left-2 z-10 text-xs text-red-400 bg-red-900/30 border border-red-800/50 rounded px-2 py-1">
          {{ chartError }}
        </div>

        <!-- 全屏退出按钮 -->
        <button
          v-if="isFullscreen"
          @click="toggleFullscreen"
          class="absolute top-2 right-2 z-30 w-7 h-7 flex items-center justify-center rounded bg-[#21262d] hover:bg-[#30363d] text-[#8b949e] hover:text-white text-xs border border-[#30363d]"
        >✕</button>
      </div>

      <!-- 右侧副图指标（KDJ/RSI/MACD 迷你图） -->
      <div v-if="activeIndicator !== 'none'" class="w-32 border-l border-[#1e2a3a] flex flex-col">
        <div class="px-2 py-1 text-[10px] text-[#58a6ff] border-b border-[#1e2a3a] uppercase tracking-wide">
          {{ activeIndicator }}
        </div>
        <div ref="indicatorRef" class="flex-1 min-h-0" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useMarketStore } from '../composables/useMarketStore.js'
import ChartToolbar from './ChartToolbar.vue'
import DrawingToolbar from './DrawingToolbar.vue'

// ── Store ──────────────────────────────────────────────────────────────────
const marketStore = useMarketStore()

// ── Props ────────────────────────────────────────────────────────────────────
const props = defineProps({
  symbol: { type: String, default: 'sh000001' },
  period: { type: String, default: 'daily' },
  // 透传指标参数（可选）
  indicator: { type: String, default: 'MACD' },
})

// ── Refs ────────────────────────────────────────────────────────────────────
const chartRef    = ref(null)
const chartWrapRef = ref(null)
const indicatorRef = ref(null)

// ── 状态 ────────────────────────────────────────────────────────────────────
const isFullscreen   = ref(false)
const activeTool     = ref(null)          // 当前选中的画线工具
const activeIndicator = ref(props.indicator || 'MACD')
const currentPeriod  = ref(props.period || 'daily')

const loading    = ref(false)
const loadingMsg = ref('加载中...')
const chartError = ref('')
const rawData   = ref([])                // 原始 K 线数据

// ── 图表引擎实例 ────────────────────────────────────────────────────────────
let chartInstance   = null
let candleSeries   = null
let volumeSeries   = null
let indChartInst   = null
let indSeries      = null
let resizeObserver = null

// ── 计算属性 ────────────────────────────────────────────────────────────────
const lastCandle = computed(() => rawData.value.length ? rawData.value[rawData.value.length - 1] : null)

const isUp = computed(() => lastCandle.value ? lastCandle.value.close >= lastCandle.value.open : true)
const priceTextClass  = computed(() => isUp.value ? 'text-[#f0883e]' : 'text-[#3fb950]')
const changePctClass  = computed(() => {
  if (!lastCandle.value) return 'text-[#8b949e]'
  const pct = lastCandle.value.change_pct ?? 0
  return pct >= 0 ? 'text-[#f0883e]' : 'text-[#3fb950]'
})
const changePctStr = computed(() => {
  if (!lastCandle.value) return ''
  const pct = lastCandle.value.change_pct ?? 0
  return (pct >= 0 ? '▲' : '▼') + Math.abs(pct).toFixed(2) + '%'
})

// ── 工具方法 ────────────────────────────────────────────────────────────────
function formatVolume(v) {
  if (!v && v !== 0) return '--'
  if (v >= 1e8) return (v / 1e8).toFixed(2) + '亿'
  if (v >= 1e4) return (v / 1e4).toFixed(2) + '万'
  return v.toFixed(0)
}

// ── 数据获取 ────────────────────────────────────────────────────────────────
async function fetchKlineData() {
  loading.value = true
  chartError.value = ''
  loadingMsg.value = '正在从云端拉取历史数据...'
  try {
    const resp = await fetch(`/api/v1/market/history/${props.symbol}?period=${currentPeriod.value}&limit=2500`)
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const json = await resp.json()
    if (json.code !== 200 || !json.data?.length) {
      throw new Error(json.msg || '无数据')
    }
    rawData.value = json.data
    loadingMsg.value = '数据加载完成，正在渲染...'
    await renderChart()
    if (activeIndicator.value !== 'none') await renderIndicator()
  } catch (e) {
    chartError.value = '图表加载失败: ' + e.message
    console.error('[IndexChart] fetchKlineData error:', e)
  } finally {
    loading.value = false
    loadingMsg.value = '加载中...'
  }
}

// ── TradingView Lightweight Charts 渲染 ────────────────────────────────────
async function renderChart() {
  await nextTick()
  if (!chartRef.value || !rawData.value.length) return

  // 动态 import（前端已安装 lightweight-charts）
  const { createChart, ColorType, CrosshairMode } = await import('lightweight-charts')

  // 复用已有实例或新建
  if (!chartInstance) {
    chartInstance = createChart(chartRef.value, {
      width:  chartRef.value.clientWidth,
      height: chartRef.value.clientHeight,
      layout: {
        background: { type: ColorType.Solid, color: '#0a0e17' },
        textColor: '#8b949e',
        fontSize: 11,
      },
      grid: {
        vertLines: { color: '#1e2a3a', style: 1 },
        horzLines: { color: '#1e2a3a', style: 1 },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: '#58a6ff', width: 1, style: 0, labelBackgroundColor: '#58a6ff' },
        horzLine: { color: '#58a6ff', width: 1, style: 0, labelBackgroundColor: '#58a6ff' },
      },
      rightPriceScale: {
        borderColor: '#1e2a3a',
        scaleMargins: { top: 0.1, bottom: 0.25 },
      },
      timeScale: {
        borderColor: '#1e2a3a',
        timeVisible: currentPeriod.value === 'minute',
        secondsVisible: false,
        rightOffset: 3,
        barSpacing: 8,
        tickMarkFormatter: (time) => {
          const d = new Date(time * 1000)
          if (currentPeriod.value === 'minute') {
            return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
          }
          return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit' })
        },
      },
      handleScale:  { mouseWheel: true, pinch: true, },
      handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
    })

    // 十字光标格式化
    chartInstance.applyOptions({
      crosshair: {
        vertLine: {
          labelBackgroundColor: '#58a6ff',
          formatter: (price) => price.toFixed(2),
        },
        horzLine: {
          labelBackgroundColor: '#58a6ff',
        },
      },
    })

    // 主图 K 线
    candleSeries = chartInstance.addCandlestickSeries({
      upColor:          '#f0883e',
      downColor:        '#3fb950',
      borderUpColor:    '#f0883e',
      borderDownColor:  '#3fb950',
      wickUpColor:      '#f0883e',
      wickDownColor:    '#3fb950',
    })

    // 副图成交量（柱状）
    volumeSeries = chartInstance.addHistogramSeries({
      priceFormat:     { type: 'volume' },
      priceScaleId:    'volume',
      color:           '#58a6ff',
    })
    chartInstance.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    })

    // 监听 resize
    resizeObserver = new ResizeObserver(() => {
      if (chartInstance && chartRef.value) {
        chartInstance.applyOptions({
          width:  chartRef.value.clientWidth,
          height: chartRef.value.clientHeight,
        })
      }
    })
    resizeObserver.observe(chartRef.value)
  }

  // 转换数据格式
  const candleData = rawData.value.map(d => ({
    time:  d.timestamp ?? Math.floor(new Date(d.date || d.time).getTime() / 1000),
    open:  d.open,
    high:  d.high,
    low:   d.low,
    close: d.close,
  }))

  const volumeData = rawData.value.map(d => ({
    time:  d.timestamp ?? Math.floor(new Date(d.date || d.time).getTime() / 1000),
    open:  d.open,
    high:  d.high,
    low:   d.low,
    close: d.close,
    value: d.volume ?? 0,
    color: (d.close ?? 0) >= (d.open ?? 0) ? 'rgba(240,136,62,0.5)' : 'rgba(63,185,80,0.5)',
  }))

  candleSeries.setData(candleData)
  volumeSeries.setData(volumeData)
  chartInstance.timeScale().fitContent()
}

// ── 副图指标渲染 ────────────────────────────────────────────────────────────
async function renderIndicator() {
  if (!indicatorRef.value || activeIndicator.value === 'none' || !rawData.value.length) return
  await nextTick()
  const { createChart, ColorType } = await import('lightweight-charts')

  if (!indChartInst) {
    indChartInst = createChart(indicatorRef.value, {
      width:  indicatorRef.value.clientWidth || 120,
      height: indicatorRef.value.clientHeight || 200,
      layout: { background: { type: ColorType.Solid, color: '#0a0e17' }, textColor: '#8b949e', fontSize: 10 },
      grid:   { vertLines: { color: '#1e2a3a' }, horzLines: { color: '#1e2a3a' } },
      rightPriceScale: { borderColor: '#1e2a3a' },
      timeScale: { visible: false },
      handleScroll: false,
      handleScale: false,
    })
    indSeries = indChartInst.addLineSeries({ color: '#58a6ff', lineWidth: 1 })
  }

  // 简单 KDJ 计算示例
  const closes = rawData.value.map(d => d.close)
  const kdjData = computeKDJ(closes)
  indSeries.setData(kdjData.map((v, i) => ({
    time:  rawData.value[i].timestamp ?? Math.floor(new Date(rawData.value[i].date || rawData.value[i].time).getTime() / 1000),
    value: v,
  })))
  indChartInst.timeScale().fitContent()
}

// 简单 KDJ 计算（9日周期）
function computeKDJ(closes, n = 9) {
  if (closes.length < n) return closes.map(() => null)
  const k = new Array(closes.length).fill(50)
  const d = new Array(closes.length).fill(50)
  const j = new Array(closes.length)
  for (let i = n - 1; i < closes.length; i++) {
    const slice = closes.slice(i - n + 1, i + 1)
    const h = Math.max(...slice)
    const l = Math.min(...slice)
    const rsv = h === l ? 50 : (closes[i] - l) / (h - l) * 100
    k[i] = (2 / 3) * (k[i - 1] || 50) + (1 / 3) * rsv
    d[i] = (2 / 3) * (d[i - 1] || 50) + (1 / 3) * k[i]
    j[i] = 3 * k[i] - 2 * d[i]
  }
  return j
}

// ── 事件处理 ────────────────────────────────────────────────────────────────
function onPeriodChange(period) {
  currentPeriod.value = period
  fetchKlineData()
}

function onIndicatorChange(ind) {
  activeIndicator.value = ind
  renderIndicator()
}

function onToolSelect(tool) {
  activeTool.value = activeTool.value === tool ? null : tool
  // 后续：接入图表引擎的模式切换（拖拽 ↔ 画线）
  if (chartInstance) {
    if (activeTool.value) {
      chartInstance.applyOptions({ handleScroll: false, handleScale: false })
    } else {
      chartInstance.applyOptions({ handleScroll: true, handleScale: true })
    }
  }
}

function toggleFullscreen() {
  isFullscreen.value = !isFullscreen.value
  nextTick(() => {
    if (chartInstance) {
      setTimeout(() => {
        if (chartRef.value) {
          chartInstance.applyOptions({
            width:  chartRef.value.clientWidth,
            height: chartRef.value.clientHeight,
          })
        }
      }, 50)
    }
  })
}

// ── 监听 symbol 变化，重新拉取 ────────────────────────────────────────────────
watch(() => props.symbol, (sym) => {
  if (sym) fetchKlineData()
}, { immediate: false })

watch(() => props.period, (p) => {
  if (p) { currentPeriod.value = p; fetchKlineData() }
})

// ── 生命周期 ────────────────────────────────────────────────────────────────
onMounted(() => {
  fetchKlineData()
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  chartInstance?.remove()
  indChartInst?.remove()
  chartInstance  = null
  indChartInst   = null
  candleSeries   = null
  volumeSeries   = null
  indSeries      = null
})
</script>

<style scoped>
.index-chart-root {
  width: 100%;
  height: 100%;
  overflow: hidden;
  /* 全屏模式：占满整个视口 */
}
.index-chart-root.fullscreen {
  position: fixed;
  inset: 0;
  z-index: 9999;
}
</style>
