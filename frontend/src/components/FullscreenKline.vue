<template>
  <div
    class="flex flex-col w-full h-full overflow-hidden bg-[#0a0e17]"
    @keydown.esc="isFull && emit('close')" tabindex="0"
  >
    <!-- 顶部状态栏 -->
    <div class="flex items-center gap-2 px-3 py-1 border-b border-gray-800 shrink-0">
      <!-- 周期选择 -->
      <div class="flex gap-1">
        <button
          v-for="p in periods" :key="p.value"
          class="px-2 py-0.5 text-[10px] rounded transition"
          :class="period === p.value ? 'bg-terminal-accent text-white' : 'text-gray-500 hover:text-gray-300'"
          @click="period = p.value"
        >{{ p.label }}</button>
      </div>

      <div class="flex-1" />

      <!-- 副图选择 -->
      <div class="flex gap-1">
        <button
          v-for="ind in subChartOptions" :key="ind.key"
          class="px-1.5 py-0.5 text-[9px] rounded border transition"
          :class="activeSubChart === ind.key
            ? 'border-terminal-accent text-terminal-accent'
            : 'border-gray-700 text-gray-600 hover:border-gray-500'"
          @click="activeSubChart = ind.key"
        >{{ ind.label }}</button>
      </div>

      <div class="flex-1" />

      <!-- 画线工具 -->
      <DrawingToolbar
        v-if="isFull"
        :activeTool="drawTool"
        :activeColor="drawColor"
        :magnetMode="magnetMode"
        :visible="drawVisible"
        :locked="drawLocked"
        @tool-change="t => drawTool = t"
        @color-change="c => drawColor = c"
        @magnet-toggle="magnetMode = !magnetMode"
        @visibility-toggle="drawVisible = !drawVisible"
        @lock-toggle="drawLocked = !drawLocked"
        @clear="drawingCanvasRef?.clearAll()"
      />

      <!-- 最新价 -->
      <span class="text-[13px] font-mono font-bold" :class="latestChange >= 0 ? 'text-red-400' : 'text-green-400'">
        {{ latestPrice != null ? latestPrice.toFixed(2) : '--' }}
      </span>
      <span class="text-[11px] font-mono" :class="latestChange >= 0 ? 'text-red-400' : 'text-green-400'">
        {{ latestChange >= 0 ? '+' : '' }}{{ latestChange?.toFixed(2) ?? '--' }}%
      </span>
      <button
        v-if="isFull"
        class="px-3 py-0.5 text-[11px] rounded border border-gray-600 text-gray-500 hover:border-red-500/50 hover:text-red-400 transition"
        @click="emit('close')"
      >✕ 关闭</button>
    </div>

    <!-- 主图区域 -->
    <div class="flex flex-1 min-w-0 relative">
      <!-- 错误状态 -->
      <div
        v-if="chartError"
        class="absolute inset-0 z-20 flex flex-col items-center justify-center bg-[#0a0e17]/90"
      >
        <div class="text-red-400 text-sm">{{ chartError }}</div>
        <button class="mt-2 text-xs text-gray-500 hover:text-gray-300" @click="chartError = ''">关闭</button>
      </div>

      <!-- 统一 BaseKLineChart 哑组件（flex 自然填满剩余空间） -->
      <BaseKLineChart
        ref="baseChartRef"
        class="w-full h-full"
        :chart-data="processedChartData"
        :sub-charts="activeSubCharts"
        :tick="liveTick"
        :symbol="props.symbol"
      />

      <!-- 画线覆盖层 -->
      <DrawingCanvas
        v-if="isFull && drawVisible"
        ref="drawingCanvasRef"
        class="absolute inset-0 z-10"
        :chartInstance="chartInstance"
        :activeTool="drawTool"
        :activeColor="drawColor"
        :magnetMode="magnetMode"
        :symbol="props.symbol"
        @drawn="onShapeDrawn"
        @deleted="onShapeDeleted"
        @cleared="onShapesCleared"
        @range-select="onRangeSelect"
      />

      <!-- 右侧详情面板 -->
      <QuotePanel
        v-if="isFull"
        class="shrink-0"
        :symbol="props.symbol"
        :realtimeData="quoteData"
        :snapshotData="null"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, shallowRef, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import DrawingToolbar from './DrawingToolbar.vue'
import DrawingCanvas  from './DrawingCanvas.vue'
import QuotePanel     from './QuotePanel.vue'
import BaseKLineChart from './BaseKLineChart.vue'
import { buildChartData } from '../utils/chartDataBuilder.js'
import { useMarketStream } from '../composables/useMarketStream.js'

const props = defineProps({
  symbol:  { type: String, required: true },
  isFull:  { type: Boolean, default: false },
})
const emit = defineEmits(['close', 'symbol-change'])

// ── State ──────────────────────────────────────────────────────
const period          = ref('daily')
const chartError      = ref('')
const latestPrice     = ref(null)
const latestChange    = ref(0)
const quoteData       = ref({})
const histData        = shallowRef([])
const processedChartData = shallowRef({ isEmpty: true })

// 副图选项（VOL / MACD / KDJ / RSI）
const subChartOptions = [
  { key: 'VOL',  label: 'VOL' },
  { key: 'MACD', label: 'MACD' },
  { key: 'KDJ',  label: 'KDJ' },
  { key: 'RSI',  label: 'RSI' },
]
const activeSubChart = ref('VOL')

const activeSubCharts = computed(() => {
  if (activeSubChart.value === 'VOL') return ['VOL']
  return ['VOL', activeSubChart.value]
})

// 画线
const drawTool      = ref('')
const drawColor     = ref('#fbbf24')
const magnetMode    = ref(true)
const drawVisible   = ref(true)
const drawLocked    = ref(false)
const drawingCanvasRef = ref(null)

// Refs
const baseChartRef = ref(null)
const chartInstance = computed(() => baseChartRef.value?.getChartInstance() ?? null)

// ── WebSocket ─────────────────────────────────────────────────
const { tick: liveTick, connect: wsConnect, disconnect: wsDisconnect } = useMarketStream()

watch(liveTick, (t) => {
  if (!t || !histData.value.length) return
  const sym = (t.symbol || '').toLowerCase()
  if (sym !== props.symbol?.toLowerCase()) return
  latestPrice.value  = t.price
  latestChange.value = t.chg_pct ?? 0
  const arr = histData.value.slice()
  const last = arr[arr.length - 1]
  if (!last) return
  const price = t.price
  arr[arr.length - 1] = {
    ...last,
    close:  price,
    high:   Math.max(last.high || 0, price),
    low:    Math.min(last.low  || 0, price),
    volume: (last.volume || 0) + (t.volume || 0),
  }
  histData.value = arr
})

// ── 周期 ──────────────────────────────────────────────────────
const periods = [
  { label: '日',   value: 'daily' },
  { label: '周',   value: 'weekly' },
  { label: '月',   value: 'monthly' },
  { label: '5分',  value: '5min' },
  { label: '15分', value: '15min' },
  { label: '30分', value: '30min' },
  { label: '60分', value: '60min' },
]

// ── 数据拉取 ──────────────────────────────────────────────────
async function fetchData() {
  if (!props.symbol) return
  chartError.value = ''
  try {
    const params = new URLSearchParams({
      period:  period.value,
      adjustment: 'none',
      limit:   2000,
      offset:  '0',
    })
    const res = await fetch(`/api/v1/market/history/${props.symbol}?${params}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const raw = await res.json()
    if (!Array.isArray(raw) || raw.length === 0) { chartError.value = '暂无历史数据'; return }
    const sorted = [...raw].sort((a, b) => new Date(a.date) - new Date(b.date))
    histData.value = sorted
    processedChartData.value = buildChartData(sorted, period.value, {}, [])
    const last = sorted[sorted.length - 1]
    latestPrice.value  = last.close ?? last.price
    latestChange.value = last.change_pct ?? 0
  } catch (e) {
    chartError.value = `加载失败: ${e.message}`
  }
}

async function fetchQuoteDetail() {
  if (!props.symbol) return
  try {
    const res = await fetch(`/api/v1/market/quote_detail/${props.symbol}?_t=${Date.now()}`)
    if (!res.ok) return
    quoteData.value = await res.json()
  } catch (e) { console.warn('[FullscreenKline] quote_detail failed:', e.message) }
}

// ── 监听 ──────────────────────────────────────────────────────
watch(period, () => {
  histData.value = []
  processedChartData.value = { isEmpty: true }
  fetchData()
})

watch(() => props.symbol, (sym) => {
  if (!sym) return
  histData.value = []
  processedChartData.value = { isEmpty: true }
  latestPrice.value = null
  latestChange.value = 0
  fetchData()
  fetchQuoteDetail()
  // wsConnect(sym)  // 临时屏蔽：避免浏览器控制台刷 WS 错误，便于肉眼观察 UI
}, { immediate: true })

// 副图变化时重建图表数据
watch(activeSubChart, () => {
  if (!histData.value.length) return
  processedChartData.value = buildChartData(histData.value, period.value, {}, [])
})

// ── 画线事件 ──────────────────────────────────────────────────
function onShapeDrawn()  {}
function onShapeDeleted() {}
function onShapesCleared() {}
function onRangeSelect() {}

// ── 生命周期 ──────────────────────────────────────────────────
onMounted(() => {
  if (props.symbol) {
    fetchData()
    fetchQuoteDetail()
    // wsConnect(props.symbol)  // 临时屏蔽
  }
})

onUnmounted(() => {
  // wsDisconnect()  // 临时屏蔽
  baseChartRef.value?.getChartInstance?.()?.dispose()
})
</script>

<style scoped>
@media (max-width: 900px) {
  :deep(.chart-area) { flex-basis: 100% !important; min-width: 0; width: 100%; height: 45vh; }
}
</style>
