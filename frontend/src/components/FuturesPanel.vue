<template>
  <div class="flex flex-col w-full h-full overflow-hidden bg-[#0a0e17]">
    <!-- 顶部工具栏 -->
    <div class="flex items-center gap-2 px-3 py-1 border-b border-gray-800 shrink-0">
      <!-- 合约代码输入 -->
      <input
        v-model="inputSymbol"
        class="w-20 px-2 py-0.5 text-[11px] rounded bg-gray-800 border border-gray-600 text-gray-200 focus:border-terminal-accent outline-none"
        placeholder="IF0 / RB0"
        @keydown.enter="loadSymbol"
      />
      <button class="px-2 py-0.5 text-[10px] rounded bg-terminal-accent text-white hover:opacity-80" @click="loadSymbol">切换</button>

      <!-- 周期选择 -->
      <div class="flex gap-1 ml-2">
        <button v-for="p in periods" :key="p.value"
          class="px-2 py-0.5 text-[10px] rounded transition"
          :class="period === p.value ? 'bg-terminal-accent text-white' : 'text-gray-500 hover:text-gray-300'"
          @click="period = p.value">{{ p.label }}</button>
      </div>

      <!-- 合约信息 -->
      <div class="flex-1" />
      <span class="text-[11px] font-mono" :class="latestChange >= 0 ? 'text-red-400' : 'text-green-400'">
        {{ latestPrice ?? '--' }}
      </span>
      <span class="text-[10px] font-mono" :class="latestChange >= 0 ? 'text-red-400' : 'text-green-400'">
        {{ latestChange >= 0 ? '+' : '' }}{{ latestChange?.toFixed(2) ?? '--' }}%
      </span>
      <!-- OI 持仓量 -->
      <span class="text-[10px] font-mono text-gray-500">OI: {{ latestHold?.toLocaleString() ?? '--' }}</span>
    </div>

    <!-- 错误状态 -->
    <div v-if="chartError" class="absolute inset-0 z-20 flex items-center justify-center bg-[#0a0e17]/80">
      <div class="text-red-400 text-sm">{{ chartError }}</div>
    </div>

    <!-- K线图 -->
    <div class="flex-1 min-w-0 relative">
      <BaseKLineChart
        ref="klineRef"
        class="w-full h-full"
        :rawData="klineRaw"
        :tick="liveTick"
        :symbol="currentSymbol"
        :type="periodLabel"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, shallowRef, computed, watch, onUnmounted } from 'vue'
import BaseKLineChart from './BaseKLineChart.vue'
import { useMarketStream } from '../composables/useMarketStream.js'

// ── Props ─────────────────────────────────────────────────────
const props = defineProps({
  symbol: { type: String, default: 'IF0' },
})
const emit = defineEmits(['symbol-change'])

// ── State ─────────────────────────────────────────────────────
const inputSymbol  = ref(props.symbol || 'IF0')
const currentSymbol = ref(props.symbol || 'IF0')
const period       = ref('daily')
const histData     = shallowRef([])
const latestPrice  = ref(null)
const latestChange = ref(0)
const latestHold   = ref(null)
const chartError   = ref('')
const klineRef     = ref(null)

// ── WebSocket ─────────────────────────────────────────────────
const { tick: liveTick, connect: wsConnect, disconnect: wsDisconnect } = useMarketStream()

// ── Period ────────────────────────────────────────────────────
const periods = [
  { label: '日',    value: 'daily' },
  { label: '1分',  value: '1min' },
  { label: '5分',  value: '5min' },
  { label: '15分', value: '15min' },
  { label: '30分', value: '30min' },
  { label: '60分', value: '60min' },
]

const periodLabel = computed(() => {
  const m = { daily:'日K', '1min':'1分', '5min':'5分', '15min':'15分', '30min':'30分', '60min':'60分' }
  return m[period.value] || period.value
})

// ── rawData: [[ts, open, close, low, high, vol, hold], ...] ────────
const klineRaw = computed(() =>
  histData.value.map(d => {
    let ts
    if (d.timestamp) {
      ts = d.timestamp
    } else {
      const dateStr = d.date || d.datetime || ''
      const d2 = new Date(dateStr.replace(' ', 'T'))
      ts = isNaN(d2.getTime()) ? 0 : d2.getTime()
    }
    return [ts, d.open, d.close, d.low, d.high, d.volume ?? 0, d.hold ?? null]
  })
)

// ── WS tick → 更新最新K线 + 价格/持仓 ─────────────────────────
// shallowRef 下需整体替换数组以触发 Vue 响应式
watch(liveTick, (t) => {
  if (!t || !histData.value.length) return
  const sym = (t.symbol || '').toLowerCase()
  if (sym !== currentSymbol.value.toLowerCase()) return

  latestPrice.value  = t.price
  latestChange.value = t.chg_pct ?? 0
  latestHold.value   = t.hold ?? null

  // 整体替换（shallowRef 需重新赋值引用才触发响应）
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
      period : period.value,
      limit  : 2000,
    })
    const res = await fetch(`/api/v1/market/futures/${currentSymbol.value}?${params}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    if (data.error) {
      chartError.value = data.error
      return
    }
    histData.value = data.history || []
    if (!histData.value.length) {
      chartError.value = '暂无数据'
      return
    }
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
}

// ── 监听 ──────────────────────────────────────────────────────
watch(period, () => { fetchData() })

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
