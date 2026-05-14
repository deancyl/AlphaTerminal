<template>
  <div class="flex flex-col w-full h-full overflow-hidden bg-[var(--bg-primary)]">
    <!-- 顶部工具栏 -->
    <div class="flex items-center gap-2 px-3 py-1 border-b border-theme-secondary shrink-0">
      <!-- 合约代码输入 -->
      <div class="flex flex-col">
        <input
          v-model="inputSymbol"
          class="w-20 px-2 py-0.5 text-[11px] rounded-sm bg-theme-secondary border text-theme-primary focus:border-terminal-accent outline-none"
          :class="symbolError ? 'border-red-500' : 'border-theme-secondary'"
          placeholder="RB / I / SC"
          @input="validateSymbol(inputSymbol)"
          @keydown.enter="loadSymbol"
        />
        <span v-if="symbolError" class="text-[9px] text-red-500 mt-0.5 leading-none">{{ symbolError }}</span>
      </div>
      <button class="px-2 py-0.5 text-[10px] rounded-sm bg-terminal-accent text-theme-primary hover:opacity-80" @click="loadSymbol">切换</button>

      <!-- 视图切换：K线 / 期限结构 -->
      <div class="flex gap-1 ml-2 border border-theme rounded-sm">
        <button
          class="px-2 py-0.5 text-[10px] rounded-sm transition"
          :class="viewMode === 'kline' ? 'bg-terminal-accent text-theme-primary' : 'text-theme-tertiary hover:text-theme-primary'"
          @click="viewMode = 'kline'"
        >K线图</button>
        <button
          class="px-2 py-0.5 text-[10px] rounded-sm transition"
          :class="viewMode === 'term' ? 'bg-terminal-accent text-theme-primary' : 'text-theme-tertiary hover:text-theme-primary'"
          @click="switchToTerm"
        >期限结构</button>
      </div>

      <!-- 期限结构刷新按钮 -->
      <button 
        v-if="viewMode === 'term'"
        @click="refreshTermStructure"
        class="px-2 py-0.5 text-[10px] rounded-sm border border-theme-secondary hover:border-terminal-accent"
        :disabled="termLoading"
      >
        <span v-if="termLoading">⟳</span>
        <span v-else>↻</span>
      </button>

      <!-- 周期选择（仅K线模式） -->
      <div v-if="viewMode === 'kline'" class="flex gap-1">
        <button
          v-for="p in periods" :key="p.value"
          class="px-2 py-0.5 text-[10px] rounded-sm transition"
          :class="period === p.value ? 'bg-terminal-accent text-theme-primary' : 'text-theme-tertiary hover:text-theme-primary'"
          @click="period = p.value"
        >{{ p.label }}</button>
      </div>

      <!-- 副图选择（仅K线模式） -->
      <div v-if="viewMode === 'kline'" class="flex gap-1">
        <button
          v-for="ind in subChartOptions" :key="ind.key"
          class="px-1.5 py-0.5 text-[10px] rounded-sm border transition"
          :class="activeSubChart === ind.key
            ? 'border-terminal-accent text-terminal-accent'
            : 'border-theme text-theme-muted hover:border-theme-secondary'"
          @click="activeSubChart = ind.key"
        >{{ ind.label }}</button>
      </div>

      <div class="flex-1" />

      <!-- 最新价 + OI -->
      <span class="text-[11px] font-mono" :class="latestChange >= 0 ? 'text-bullish' : 'text-bearish'">
        {{ latestPrice ?? '--' }}
      </span>
      <span class="text-[10px] font-mono" :class="latestChange >= 0 ? 'text-bullish' : 'text-bearish'">
        {{ latestChange >= 0 ? '+' : '' }}{{ latestChange?.toFixed(2) ?? '--' }}%
      </span>
      <span class="text-[10px] font-mono text-theme-tertiary">OI: {{ latestHold?.toLocaleString() ?? '--' }}</span>
      <span v-if="wsStatus === 'polling'" class="text-[10px] text-yellow-500">
        HTTP模式
      </span>
    </div>

    <!-- 错误状态 -->
    <div v-if="chartError" class="flex-1 flex items-center justify-center">
      <div class="text-bullish text-sm">{{ chartError }}</div>
    </div>

    <!-- K线图 -->
    <div v-else-if="viewMode === 'kline'" class="flex-1 min-w-0 relative">
      <BaseKLineChart
        ref="klineRef"
        class="w-full h-full"
        :chart-data="processedChartData"
        :sub-charts="activeSubCharts"
        :tick="liveTick"
        :symbol="currentSymbol"
      />
    </div>

    <!-- 期限结构图 -->
    <div v-else-if="viewMode === 'term'" class="flex-1 min-w-0 relative">
      <TermStructureChart
        :symbol="termSymbol"
        :name="termName"
        :data="termStructureData"
        :isLoading="termLoading"
        :hasError="!!termError"
        @refresh="refreshTermStructure"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, shallowRef, computed, watch, onMounted, onUnmounted } from 'vue'
import { useThrottleFn } from '@vueuse/core'
import BaseKLineChart from './BaseKLineChart.vue'
import TermStructureChart from './TermStructureChart.vue'
import { buildChartData } from '../utils/chartDataBuilder.js'
import { useMarketStream } from '../composables/useMarketStream.js'

const props = defineProps({
  symbol: { type: String, default: 'IF0' },
})
const emit = defineEmits(['symbol-change'])

// ── State ─────────────────────────────────────────────────────
const inputSymbol   = ref(props.symbol || 'IF0')
const currentSymbol = ref(props.symbol || 'IF0')
const symbolError   = ref('')
const period        = ref('daily')
const histData      = shallowRef([])
const latestPrice   = ref(null)
const latestChange  = ref(0)
const latestHold    = ref(null)
const chartError    = ref('')
const klineRef      = ref(null)

// ── 视图模式 ───────────────────────────────────────────────────
const viewMode         = ref('kline')   // 'kline' | 'term'
const termSymbol       = ref('')
const termName         = ref('')
const termStructureData = ref([])
const termError        = ref('')
const termLoading      = ref(false)

// ── WebSocket ─────────────────────────────────────────────────
const { tick: liveTick, connect: wsConnect, disconnect: wsDisconnect, wsStatus } = useMarketStream()

async function switchToTerm() {
  viewMode.value = 'term'
  await fetchTermStructure()
}

function refreshTermStructure() {
  termError.value = ''
  fetchTermStructure()
}

async function fetchTermStructure() {
  const prefix = inputSymbol.value.trim().toUpperCase().replace(/0$/, '')
  if (!prefix) return
  termError.value = ''
  termLoading.value = true
  try {
    const res = await fetch(`/api/v1/futures/term_structure?symbol=${prefix}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    if (data.code !== 0 && data.code !== undefined) {
      termError.value = data.message || '加载失败'
      return
    }
    termSymbol.value = data.data?.symbol || ''
    termName.value   = data.data?.name || ''
    termStructureData.value = data.data?.term_structure || []
  } catch (e) {
    termError.value = `加载失败: ${e.message}`
  } finally {
    termLoading.value = false
  }
}

// ── 图表数据（统一结构化格式）────────────────────────────────────
const subChartOptions = [
  { key: 'VOL',  label: 'VOL' },
  { key: 'D_OI', label: 'ΔOI' },
  { key: 'MACD', label: 'MACD' },
]
const activeSubChart = ref('D_OI')   // 期货默认显示 ΔOI

const activeSubCharts = computed(() => {
  if (activeSubChart.value === 'VOL') return ['VOL']
  return ['VOL', activeSubChart.value]
})

// Chart data ref (async worker-based calculation)
const processedChartData = ref({ isEmpty: true })

// Rebuild chart data using Web Worker
async function rebuildChartData() {
  if (!histData.value.length) {
    processedChartData.value = { isEmpty: true }
    return
  }
  // Use Web Worker for heavy indicator calculations (off-main-thread)
  processedChartData.value = await buildChartData(
    histData.value,
    period.value,
    {},
    [],
    { useWorker: true, timeout: 10000 }
  )
}

// ── Period ────────────────────────────────────────────────────
const periods = [
  { label: '日',    value: 'daily' },
  { label: '1分',  value: '1min' },
  { label: '5分',  value: '5min' },
  { label: '15分', value: '15min' },
  { label: '30分', value: '30min' },
  { label: '60分', value: '60min' },
]

// ── WS tick → 增量更新 histData（节流 150ms）──────────────────
const handleTickUpdate = useThrottleFn((t) => {
  if (!t || !histData.value.length) return
  const sym = (t.symbol || '').toLowerCase()
  if (sym !== currentSymbol.value.toLowerCase()) return
  latestPrice.value  = t.price
  latestChange.value = t.chg_pct ?? 0
  latestHold.value   = t.hold ?? null
  const arr = histData.value.slice()
  const last = arr[arr.length - 1]
  if (!last) return
  const price = t.price
  arr[arr.length - 1] = {
    ...last,
    close:  price,
    high:   Math.max(last.high  || 0, price),
    low:    Math.min(last.low   || 0, price),
    volume: (last.volume || 0) + (t.volume || 0),
    hold:   t.hold != null ? t.hold : last.hold,
  }
  histData.value = arr
  // Rebuild chart data after tick update (debounced by throttle)
  rebuildChartData()
}, 150)

watch(liveTick, (t) => { handleTickUpdate(t) })

// ── 数据拉取 ─────────────────────────────────────────────────
async function fetchData() {
  if (!currentSymbol.value) return
  chartError.value = ''
  try {
    const params = new URLSearchParams({
      symbol: currentSymbol.value,
      period:  period.value,
      limit:   2000,
    })
    const res = await fetch(`/api/v1/market/futures/${currentSymbol.value}?${params}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    if (data.error) { chartError.value = data.error; return }
    histData.value = data.history || []
    if (!histData.value.length) { chartError.value = '暂无数据'; return }
    const last = histData.value[histData.value.length - 1]
    latestPrice.value  = last.close
    latestChange.value = 0
    latestHold.value   = last.hold ?? null
    // Rebuild chart data using Web Worker
    rebuildChartData()
  } catch (e) {
    chartError.value = `加载失败: ${e.message}`
  }
}

// ── Symbol Validation ─────────────────────────────────────────
function validateSymbol(value) {
  const trimmed = (value || '').trim().toUpperCase()
  // Valid futures symbols: 1-2 uppercase letters, optional digit
  // Examples: RB, I, IF, IF0, SC, AU, CU
  const valid = /^[A-Z]{1,3}[0-9]?$/.test(trimmed)
  if (!valid && trimmed) {
    symbolError.value = '请输入有效的期货代码（如 RB、IF0）'
    return false
  }
  symbolError.value = ''
  return true
}

function loadSymbol() {
  if (!validateSymbol(inputSymbol.value)) return
  const s = inputSymbol.value.trim().toUpperCase()
  if (!s) return
  currentSymbol.value = s
  histData.value = []
  latestPrice.value = null
  emit('symbol-change', { symbol: s })
  wsDisconnect()
  wsConnect(s)
  fetchData()
  if (viewMode.value === 'term') fetchTermStructure()
}

// ── 监听 ──────────────────────────────────────────────────────
watch(period, () => { fetchData() })
// activeSubChart 的变化会通过 activeSubCharts computed 传递给子组件

watch(() => props.symbol, (s) => {
  if (!s) return
  inputSymbol.value = s
  currentSymbol.value = s
  wsConnect(s)
  fetchData()
}, { immediate: true })

// ── 生命周期 ─────────────────────────────────────────────────
onUnmounted(() => { wsDisconnect() })
</script>
