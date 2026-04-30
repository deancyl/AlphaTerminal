<template>
  <div class="flex flex-col w-full h-full overflow-hidden">

    <!-- 顶部栏 -->
    <div class="shrink-0 flex items-center justify-between px-2 py-1 border-b border-theme bg-terminal-panel/80">
      <span class="text-[10px] text-cyan-400 font-bold">📊 买卖盘口</span>
      <div class="flex items-center gap-1">
        <input
          v-model="localSymbol"
          @keyup.enter="changeSymbol"
          class="bg-theme-tertiary/30 border border-theme rounded px-1.5 py-0.5 text-[9px] text-theme-primary w-20 focus:outline-none focus:border-cyan-400/60"
          placeholder="sh600519"
        />
        <span class="text-[8px] text-theme-muted">5档</span>
        <span class="text-[8px] text-theme-muted">{{ lastUpdateTime }}</span>
      </div>
    </div>

    <!-- 盘口主体 -->
    <div v-if="data && (data.asks?.length || data.bids?.length)" class="flex-1 min-h-0 flex flex-col justify-between">

      <!-- 委比 / 委差 -->
      <div class="flex items-center gap-2 px-2 py-0.5 bg-terminal-panel/40 text-[9px]">
        <span class="text-theme-muted">委比</span>
        <span class="font-mono" :class="weibi >= 0 ? 'text-bullish' : 'text-bearish'">
          {{ weibi >= 0 ? '+' : '' }}{{ weibi?.toFixed(2) }}%
        </span>
        <span class="text-theme-muted ml-1">委差</span>
        <span class="font-mono" :class="weicha >= 0 ? 'text-bullish' : 'text-bearish'">
          {{ weicha >= 0 ? '+' : '' }}{{ weicha?.toFixed(0) }}
        </span>
      </div>

      <!-- 卖盘 5 档（价格从高到低排列） -->
      <div class="flex-1 flex flex-col justify-content-end">
        <div class="grid grid-cols-3 gap-0.5 px-1 py-0.5 text-[8px] text-theme-muted border-b border-theme/20">
          <span class="text-left">卖盘</span>
          <span class="text-right">价格</span>
          <span class="text-right">挂单量</span>
        </div>
        <div
          v-for="(ask, i) in displayAsks"
          :key="'a' + i"
          class="relative grid grid-cols-3 gap-0.5 px-1 py-px text-[9px] cursor-default hover:bg-theme-tertiary/20 transition-colors"
        >
          <!-- 深度条：右侧延伸，绿色=卖盘压力（绿色背景） -->
          <div
            class="absolute inset-y-0 right-0 bg-bearish/10 rounded-l transition-all"
            :style="{ width: getDepthWidth(ask.volume, maxAskVol) + '%' }"
          ></div>
          <!-- 档位标签 -->
          <span class="text-theme-muted relative z-10">{{ 5 - i }}</span>
          <!-- 价格 -->
          <span class="text-right font-mono text-bearish relative z-10">{{ formatPrice(ask.price) }}</span>
          <!-- 挂单量 + 深度条叠加 -->
          <div class="relative z-10 flex items-center justify-end gap-0.5">
            <div
              class="absolute right-0 top-0 bottom-0 bg-bearish/20 rounded-l"
              :style="{ width: getDepthWidth(ask.volume, maxAskVol) + '%' }"
            ></div>
            <span class="font-mono text-theme-primary relative z-10">{{ formatVol(ask.volume) }}</span>
          </div>
        </div>
      </div>

      <!-- 当前价分隔线 -->
      <div
        class="flex items-center justify-center py-1 mx-1 my-0.5 rounded border"
        :class="priceDir === 'up' ? 'border-bullish/40 bg-bullish/5' : priceDir === 'down' ? 'border-bearish/40 bg-bearish/5' : 'border-theme/30'"
      >
        <span
          class="font-mono font-bold text-[13px]"
          :class="priceDir === 'up' ? 'text-bullish' : priceDir === 'down' ? 'text-bearish' : 'text-theme-primary'"
        >{{ formatPrice(midPrice) }}</span>
        <span v-if="priceDir !== ''" class="ml-1 text-[10px]">{{ priceDir === 'up' ? '▲' : '▼' }}</span>
      </div>

      <!-- 买盘 5 档 -->
      <div class="flex-1 flex flex-col">
        <div
          v-for="(bid, i) in displayBids"
          :key="'b' + i"
          class="relative grid grid-cols-3 gap-0.5 px-1 py-px text-[9px] cursor-default hover:bg-theme-tertiary/20 transition-colors"
        >
          <!-- 深度条：右侧延伸，红色=买盘支撑（红色背景） -->
          <div
            class="absolute inset-y-0 right-0 bg-bullish/10 rounded-l transition-all"
            :style="{ width: getDepthWidth(bid.volume, maxBidVol) + '%' }"
          ></div>
          <span class="text-theme-muted relative z-10">{{ i + 1 }}</span>
          <span class="text-right font-mono text-bullish relative z-10">{{ formatPrice(bid.price) }}</span>
          <div class="relative z-10 flex items-center justify-end gap-0.5">
            <div
              class="absolute right-0 top-0 bottom-0 bg-bullish/20 rounded-l"
              :style="{ width: getDepthWidth(bid.volume, maxBidVol) + '%' }"
            ></div>
            <span class="font-mono text-theme-primary relative z-10">{{ formatVol(bid.volume) }}</span>
          </div>
        </div>
      </div>

      <!-- 盘口统计数据 -->
      <div class="flex items-center justify-between px-2 py-0.5 border-t border-theme/20 text-[8px] text-theme-muted">
        <span>卖 {{ data.asks?.length || 0 }} 档 / 买 {{ data.bids?.length || 0 }} 档</span>
        <span :class="totalBidVol >= totalAskVol ? 'text-bullish' : 'text-bearish'">
          {{ totalBidVol >= totalAskVol ? '买强' : '卖强' }}
          ({{ Math.abs(weibi ?? 0).toFixed(1) }}%)
        </span>
      </div>
    </div>

    <!-- 空状态 / 错误 -->
    <div v-else-if="error" class="flex-1 flex flex-col items-center justify-center text-bearish text-[10px] gap-1">
      <span>⚠️ {{ error }}</span>
    </div>
    <div v-else-if="loading" class="flex-1 p-2 space-y-1">
      <div class="flex justify-between items-center mb-1">
        <div class="skeleton h-3 w-16 rounded"></div>
        <div class="skeleton h-3 w-12 rounded"></div>
      </div>
      <div v-for="n in 5" :key="n" class="flex justify-between">
        <div class="skeleton h-3 w-10 rounded"></div>
        <div class="skeleton h-3 w-12 rounded"></div>
        <div class="skeleton h-3 w-10 rounded"></div>
      </div>
      <div class="skeleton h-px my-1"></div>
      <div v-for="n in 5" :key="n" class="flex justify-between">
        <div class="skeleton h-3 w-10 rounded"></div>
        <div class="skeleton h-3 w-12 rounded"></div>
        <div class="skeleton h-3 w-10 rounded"></div>
      </div>
    </div>
    <div v-else class="flex-1 flex flex-col items-center justify-center text-theme-muted text-[10px] gap-1">
      <span>📭 暂无盘口数据</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { apiFetch } from '../utils/api.js'

const props = defineProps({
  symbol: { type: String, default: 'sh600519' },
})

const localSymbol = ref(props.symbol)
const data        = ref(null)
const loading     = ref(false)
const error        = ref(null)
const lastUpdateTime = ref('')
const priceDir     = ref('')    // 'up' | 'down' | ''
const midPrice     = ref(0)
let prevPrice      = 0
let refreshTimer   = null

// ── 盘口数据 ───────────────────────────────────────────────────
const displayAsks = computed(() =>
  [...(data.value?.asks || [])].reverse().slice(0, 5)
)
const displayBids = computed(() =>
  (data.value?.bids || []).slice(0, 5)
)

const maxAskVol = computed(() => {
  const vols = displayAsks.value.map(a => a.volume)
  return vols.length ? Math.max(...vols) : 1
})
const maxBidVol = computed(() => {
  const vols = displayBids.value.map(b => b.volume)
  return vols.length ? Math.max(...vols) : 1
})
const maxVol = computed(() => Math.max(maxAskVol.value, maxBidVol.value))

const totalAskVol = computed(() =>
  displayAsks.value.reduce((s, a) => s + (a.volume || 0), 0)
)
const totalBidVol = computed(() =>
  displayBids.value.reduce((s, b) => s + (b.volume || 0), 0)
)

// 委比 = (买入委托总量 - 卖出委托总量) / (买入委托总量 + 卖出委托总量) * 100
const weibi = computed(() => {
  const buy = totalBidVol.value
  const sell = totalAskVol.value
  const total = buy + sell
  if (!total) return 0
  return (buy - sell) / total * 100
})

// 委差 = 买入总量 - 卖出总量
const weicha = computed(() => totalBidVol.value - totalAskVol.value)

// ── 工具函数 ───────────────────────────────────────────────────
function formatPrice(p) {
  if (!p) return '--'
  return p.toFixed(2)
}

function formatVol(v) {
  if (!v) return '0'
  if (v >= 1e8) return (v / 1e8).toFixed(1) + '亿'
  if (v >= 1e4) return (v / 1e4).toFixed(1) + 'w'
  if (v >= 1e3) return (v / 1e3).toFixed(1) + 'k'
  return v.toFixed(0)
}

// 深度条宽度：相对于最大挂单量，max=100%
function getDepthWidth(vol, max) {
  if (!max) return 0
  return Math.min(100, (vol / max) * 100)
}

function changeSymbol() {
  const s = localSymbol.value.trim()
  if (s) emit('update:symbol', s)
}

const emit = defineEmits(['update:symbol'])

// ── 数据获取 ──────────────────────────────────────────────────
async function fetchOrderBook() {
  const sym = localSymbol.value.trim() || props.symbol
  try {
    const json = await apiFetch(`/api/v1/market/order_book/${sym}`, { timeoutMs: 8000 })
    if (json?.code !== 0) {
      error.value = json?.message || '获取失败'
      data.value = null
      return
    }
    data.value = json.data || json
    error.value = null

    // 计算中间价 & 价格方向
    const asks = data.value.asks || []
    const bids = data.value.bids || []
    const allPrices = asks.map(a => a.price).concat(bids.map(b => b.price)).filter(p => p > 0)
    if (allPrices.length) {
      const mp = allPrices.reduce((a, b) => a + b, 0) / allPrices.length
      if (mp > prevPrice)  priceDir.value = 'up'
      else if (mp < prevPrice) priceDir.value = 'down'
      else priceDir.value = ''
      prevPrice = mp
      midPrice.value = mp
    }
    lastUpdateTime.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
  } catch (e) {
    error.value = e.message
    data.value = null
  } finally {
    loading.value = false
  }
}

// ── 生命周期 ───────────────────────────────────────────────────
watch(() => props.symbol, (s) => {
  localSymbol.value = s
  prevPrice = 0
  priceDir.value = ''
  fetchOrderBook()
}, { immediate: false })

onMounted(() => {
  fetchOrderBook()
  // 3 秒轮询（盘口高频场景）
  refreshTimer = setInterval(fetchOrderBook, 3000)
})

onBeforeUnmount(() => {
  if (refreshTimer) clearInterval(refreshTimer)
  refreshTimer = null
})
</script>
