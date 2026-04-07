<template>
  <div
    class="flex flex-col w-full h-full overflow-hidden bg-[#0a0e17]"
    @keydown.esc="isFull && emit('close')" tabindex="0"
  >
    <!-- 顶部状态栏 -->
    <div class="flex items-center gap-2 px-3 py-1 border-b border-gray-800 shrink-0">
      <!-- 周期选择 -->
      <div class="flex gap-1">
        <button v-for="p in periods" :key="p.value"
          class="px-2 py-0.5 text-[10px] rounded transition"
          :class="period === p.value ? 'bg-terminal-accent text-white' : 'text-gray-500 hover:text-gray-300'"
          @click="period = p.value">{{ p.label }}</button>
      </div>
      <div class="flex-1" />
      <!-- 指标选择 -->
      <div class="flex gap-1">
        <button v-for="ind in ['MA','BOLL','MACD','KDJ','RSI','WR']" :key="ind"
          class="px-1.5 py-0.5 text-[9px] rounded border transition"
          :class="activeIndicators.includes(ind)
            ? 'border-terminal-accent text-terminal-accent'
            : 'border-gray-700 text-gray-600 hover:border-gray-500'"
          @click="toggleIndicator(ind)">{{ ind }}</button>
      </div>
      <div class="flex-1" />
      <!-- 画线工具 -->
      <DrawingToolbar v-if="isFull" v-model:tool="drawTool" v-model:color="drawColor" v-model:locked="drawLocked" />
      <!-- 最新价 -->
      <span class="text-[13px] font-mono font-bold" :class="latestChange >= 0 ? 'text-red-400' : 'text-green-400'">
        {{ latestPrice != null ? latestPrice.toFixed(2) : '--' }}
      </span>
      <span class="text-[11px] font-mono" :class="latestChange >= 0 ? 'text-red-400' : 'text-green-400'">
        {{ latestChange >= 0 ? '+' : '' }}{{ latestChange?.toFixed(2) ?? '--' }}%
      </span>
      <button v-if="isFull" class="px-3 py-0.5 text-[11px] rounded border border-gray-600 text-gray-500 hover:border-red-500/50 hover:text-red-400 transition" @click="emit('close')">✕ 关闭</button>
    </div>

    <!-- 主图区域 -->
    <div class="flex flex-1 min-w-0 relative">
      <!-- 错误状态 -->
      <div v-if="chartError" class="absolute inset-0 z-20 flex flex-col items-center justify-center bg-[#0a0e17]/90">
        <div class="text-red-400 text-sm">{{ chartError }}</div>
        <button class="mt-2 text-xs text-gray-500 hover:text-gray-300" @click="chartError = ''">关闭</button>
      </div>

      <!-- K线图 BaseKLineChart -->
      <BaseKLineChart
        ref="klineRef"
        class="flex-1 min-w-0"
        :rawData="klineRaw"
        :tick="liveTick"
        :symbol="props.symbol"
        :type="periodLabel"
      />

      <!-- 画线覆盖层（isFull 模式） -->
      <DrawingCanvas
        v-if="isFull && drawVisible"
        class="absolute inset-0 z-10"
        :chartInstance="drawingChartInstance"
        :activeTool="drawTool"
        :activeColor="drawColor"
        :locked="drawLocked"
      />

      <!-- 右侧详情面板 -->
      <QuotePanel v-if="isFull" class="shrink-0"
        :symbol="props.symbol"
        :realtimeData="quoteData"
        :snapshotData="null"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import DrawingToolbar from './DrawingToolbar.vue'
import DrawingCanvas  from './DrawingCanvas.vue'
import QuotePanel     from './QuotePanel.vue'
import BaseKLineChart from './BaseKLineChart.vue'
import { useMarketStream } from '../composables/useMarketStream.js'
import { calcMA, calcBOLL, calcEMA, calcMACD, calcKDJ } from '../utils/indicators.js'

const props = defineProps({
  symbol:   { type: String, required: true },
  isFull:   { type: Boolean, default: false },
  showVol:  { type: Boolean, default: true },
})
const emit = defineEmits(['close', 'symbol-change'])

// ── 状态 ──────────────────────────────────────────────────────
const period         = ref('daily')
const activeIndicators = ref([])
const isLoading = ref(false), chartError = ref('')
const latestPrice = ref(null), latestChange = ref(0)
const quoteData   = ref({})
const histData    = ref([])      // 原始历史数据 [{date, open, close, low, high, volume}, ...]
const drawTool = ref(''), drawColor = ref('#fbbf24'), magnetMode = ref(true)
const drawVisible = ref(true), drawLocked = ref(false)
const drawingCanvasRef = ref(null)
const klineRef = ref(null)

// ── WebSocket 实时 tick ───────────────────────────────────────
const { tick: liveTick, connect: wsConnect, disconnect: wsDisconnect } = useMarketStream()

watch(() => props.symbol, (sym) => {
  if (!sym) return
  histData.value = []
  latestPrice.value = null
  latestChange.value = 0
  fetchData()
  fetchQuoteDetail()
  wsConnect(sym)
}, { immediate: true })

// ── Computed ───────────────────────────────────────────────────
const klineRaw = computed(() =>
  histData.value.map(d => [new Date(d.date).getTime(), d.open, d.close, d.low, d.high, d.volume ?? 0])
)

const periodLabel = computed(() => {
  const map = { daily:'日K', weekly:'周K', monthly:'月K', minutely:'分时', '1min':'1分', '5min':'5分', '15min':'15分', '30min':'30分', '60min':'60分' }
  return map[period.value] || period.value
})

// ── 指标 ──────────────────────────────────────────────────────
const allIndicators = [
  { key: 'MA',   label: 'MA' },
  { key: 'BOLL', label: 'BOLL' },
  { key: 'MACD', label: 'MACD' },
  { key: 'KDJ', label: 'KDJ' },
  { key: 'RSI', label: 'RSI' },
  { key: 'WR',  label: 'WR' },
]

// ── 周期 ──────────────────────────────────────────────────────
const periods = [
  { label: '日', value: 'daily' },
  { label: '周', value: 'weekly' },
  { label: '月', value: 'monthly' },
  { label: '5分', value: '5min' },
  { label: '15分', value: '15min' },
  { label: '30分', value: '30min' },
  { label: '60分', value: '60min' },
]

// ── DrawingCanvas chart 实例桥接 ─────────────────────────────
const drawingChartInstance = ref(null)

watch(klineRef, async (ref) => {
  if (!ref) return
  // 等待 BaseKLineChart 内部 chart 实例可用
  await nextTick()
  drawingChartInstance.value = ref.getChartInstance()
}, { flush: 'post' })

// ── 数据拉取 ──────────────────────────────────────────────────
async function fetchData() {
  if (!props.symbol) return
  isLoading.value = true
  chartError.value = ''
  try {
    const params = new URLSearchParams({
      symbol: props.symbol,
      period : period.value,
      adjust : 'none',
      limit  : 2000,
    })
    const res = await fetch(`/api/v1/market/klinedata/${props.symbol}?${params}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const raw = await res.json()
    if (!Array.isArray(raw) || raw.length === 0) { chartError.value = '暂无历史数据'; return }
    // 排序：原始数据可能是任意顺序
    const sorted = [...raw].sort((a, b) => new Date(a.date) - new Date(b.date))
    histData.value = sorted
    // 更新头部价格
    const last = sorted[sorted.length - 1]
    latestPrice.value  = last.close ?? last.price
    latestChange.value = last.change_pct ?? 0
  } catch (e) {
    chartError.value = `加载失败: ${e.message}`
  } finally {
    isLoading.value = false
  }
}

async function fetchQuoteDetail() {
  if (!props.symbol) return
  try {
    const res = await fetch(`/api/v1/market/quote_detail/${props.symbol}?_t=${Date.now()}`)
    if (!res.ok) return
    quoteData.value = await res.json()
  } catch (e) {
    console.warn('[FullscreenKline] quote_detail failed:', e.message)
  }
}

function toggleIndicator(key) {
  const arr = activeIndicators.value
  const idx = arr.indexOf(key)
  if (idx >= 0) arr.splice(idx, 1)
  else arr.push(key)
}

// ── 周期切换重拉数据 ─────────────────────────────────────────
watch(period, () => {
  histData.value = []
  latestPrice.value = null
  fetchData()
})

// ── 生命周期 ──────────────────────────────────────────────────
onMounted(() => {
  window.addEventListener('resize', onResize)
  if (props.symbol) {
    fetchData()
    fetchQuoteDetail()
    wsConnect(props.symbol)
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  wsDisconnect()
})

function onResize() { windowWidth.value = window.innerWidth }
const windowWidth = ref(typeof window !== 'undefined' ? window.innerWidth : 1200)
</script>

<style scoped>
@media (max-width: 900px) {
  :deep(.chart-area) { flex-basis: 100% !important; min-width: 0; width: 100%; height: 45vh; }
}
</style>
