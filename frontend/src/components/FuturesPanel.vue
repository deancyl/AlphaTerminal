<template>
  <div class="flex flex-col w-full h-full overflow-hidden bg-[#0a0e17]">
    <!-- 顶部工具栏 -->
    <div class="flex items-center gap-2 px-3 py-1 border-b border-gray-800 shrink-0">
      <!-- 合约代码输入 -->
      <input
        v-model="inputSymbol"
        class="w-20 px-2 py-0.5 text-[11px] rounded bg-gray-800 border border-gray-600 text-gray-200 focus:border-terminal-accent outline-none"
        placeholder="RB / I / SC"
        @keydown.enter="loadSymbol"
      />
      <button class="px-2 py-0.5 text-[10px] rounded bg-terminal-accent text-white hover:opacity-80" @click="loadSymbol">切换</button>

      <!-- 视图切换：K线 / 期限结构 -->
      <div class="flex gap-1 ml-2 border border-gray-700 rounded">
        <button
          class="px-2 py-0.5 text-[9px] rounded transition"
          :class="viewMode === 'kline' ? 'bg-terminal-accent text-white' : 'text-gray-500 hover:text-gray-300'"
          @click="viewMode = 'kline'"
        >K线图</button>
        <button
          class="px-2 py-0.5 text-[9px] rounded transition"
          :class="viewMode === 'term' ? 'bg-terminal-accent text-white' : 'text-gray-500 hover:text-gray-300'"
          @click="switchToTerm"
        >期限结构</button>
      </div>

      <!-- 周期选择（仅K线模式） -->
      <div v-if="viewMode === 'kline'" class="flex gap-1">
        <button
          v-for="p in periods" :key="p.value"
          class="px-2 py-0.5 text-[10px] rounded transition"
          :class="period === p.value ? 'bg-terminal-accent text-white' : 'text-gray-500 hover:text-gray-300'"
          @click="period = p.value"
        >{{ p.label }}</button>
      </div>

      <!-- 副图选择（仅K线模式） -->
      <div v-if="viewMode === 'kline'" class="flex gap-1">
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

      <!-- 最新价 + OI -->
      <span class="text-[11px] font-mono" :class="latestChange >= 0 ? 'text-red-400' : 'text-green-400'">
        {{ latestPrice ?? '--' }}
      </span>
      <span class="text-[10px] font-mono" :class="latestChange >= 0 ? 'text-red-400' : 'text-green-400'">
        {{ latestChange >= 0 ? '+' : '' }}{{ latestChange?.toFixed(2) ?? '--' }}%
      </span>
      <span class="text-[10px] font-mono text-gray-500">OI: {{ latestHold?.toLocaleString() ?? '--' }}</span>
    </div>

    <!-- 错误状态 -->
    <div v-if="chartError" class="flex-1 flex items-center justify-center">
      <div class="text-red-400 text-sm">{{ chartError }}</div>
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
      />
    </div>
  </div>
</template>

<script setup>
import { ref, shallowRef, computed, watch, onMounted, onUnmounted } from 'vue'
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
const period        = ref('daily')
const histData      = shallowRef([])
const latestPrice   = ref(null)
const latestChange  = ref(0)
const latestHold    = ref(null)
const chartError    = ref('')
const klineRef      = ref(null)

// ── 视图模式 ───────────────────────────────────────────────────
const viewMode         = ref('kline')   // 'kline' | 'term'
const termSymbol       = ref('')         // 品种代码如 RB
const termName         = ref('')         // 中文名如 螺纹钢
const termStructureData = ref([])         // 期限结构数据
const termError        = ref('')

// ── WebSocket ─────────────────────────────────────────────────
const { tick: liveTick, connect: wsConnect, disconnect: wsDisconnect } = useMarketStream()

async function switchToTerm() {
  viewMode.value = 'term'
  await fetchTermStructure()
}

async function fetchTermStructure() {
  const prefix = inputSymbol.value.trim().toUpperCase().replace(/0$/, '')
  if (!prefix) return
  termError.value = ''
  try {
    const res = await fetch(`/api/v1/futures/term_structure?symbol=${prefix}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    if (data.error) { termError.value = data.error; return }
    termSymbol.value = data.symbol
    termName.value   = data.name
    termStructureData.value = data.term_structure || []
  } catch (e) {
    termError.value = `加载失败: ${e.message}`
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

const processedChartData = computed(() =>
  histData.value.length
    ? buildChartData(histData.value, period.value, {}, [])
    : { isEmpty: true }
)

// ── Period ────────────────────────────────────────────────────
const periods = [
  { label: '日',    value: 'daily' },
  { label: '1分',  value: '1min' },
  { label: '5分',  value: '5min' },
  { label: '15分', value: '15min' },
  { label: '30分', value: '30min' },
  { label: '60分', value: '60min' },
]

// ── WS tick → 增量更新 histData（shallowRef + 整体替换）──────────
watch(liveTick, (t) => {
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
})

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
  } catch (e) {
    chartError.value = `加载失败: ${e.message}`
  }
}

function loadSymbol() {
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
watch(activeSubChart, () => {
  if (!histData.value.length) return
  processedChartData.value = buildChartData(histData.value, period.value, {}, [])
})

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
