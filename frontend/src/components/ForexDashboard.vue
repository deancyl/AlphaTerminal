<template>
  <div class="h-full flex flex-col bg-terminal-bg overflow-hidden" role="region" aria-label="外汇行情面板">
    <div class="flex-shrink-0 flex items-center justify-between px-4 py-3 border-b border-theme-secondary">
      <div class="flex items-center gap-3">
        <span class="text-lg font-bold text-terminal-accent" role="heading" aria-level="2">💱 外汇行情</span>
        <span class="text-xs text-terminal-dim hidden sm:inline">实时汇率 · 交叉矩阵 · K线走势</span>
      </div>
      <div class="flex items-center gap-2">
        <span v-if="isPolling" class="text-xs text-success animate-pulse">自动刷新中</span>
        <span class="text-xs text-terminal-dim font-mono tabular-nums">{{ currentTime }}</span>
        <button 
          class="px-3 py-1.5 rounded-sm text-xs bg-terminal-accent/20 text-terminal-accent hover:bg-terminal-accent/30 transition disabled:opacity-50"
          @click="refreshAll"
          :disabled="loading"
          type="button"
        >
          {{ loading ? '...' : '刷新' }}
        </button>
      </div>
    </div>

    <!-- Offline Mode Banner -->
    <div
      v-if="isOfflineMode"
      class="mx-3 md:mx-4 mt-3 bg-yellow-500/20 border border-yellow-500/50 rounded-lg p-3 flex items-center justify-between"
      role="alert"
      aria-live="polite"
    >
      <div class="flex items-center gap-2">
        <span class="text-yellow-400 text-sm">⚠️ 离线模式 - 数据可能不是最新</span>
        <span class="text-xs text-yellow-400/70">(网络连接异常)</span>
      </div>
      <button
        @click="resetCircuitBreaker"
        class="px-3 py-1.5 text-xs bg-yellow-600 hover:bg-yellow-500 text-white rounded transition"
        :disabled="converting"
        type="button"
      >
        {{ converting ? '重置中...' : '重置连接' }}
      </button>
    </div>

    <div class="flex-1 overflow-y-auto p-3 md:p-4 space-y-4">
      <ForexQuotePanel 
        :quotes="quotes"
        :loading="loadingQuotes"
        :error="quotesError"
        :last-update="lastQuotesUpdate"
        :selected-symbol="selectedSymbol"
        @select="handleSelectQuote"
        @retry="fetchQuotes"
      />
      
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 min-h-[400px]">
        <CrossRateMatrix 
          :currencies="currencies"
          :matrix="matrix"
          :loading="loadingMatrix"
          :error="matrixError"
          :last-update="lastMatrixUpdate"
          @retry="fetchMatrix"
        />
        
        <ForexKLineChart 
          :symbol="selectedSymbol || 'USDCNH'"
          :api-data="klineData"
          :loading="loadingKline"
          :error="klineError"
          :last-update="lastKlineUpdate"
          @refresh="fetchKline"
        />
      </div>
      
      <div class="bg-surface rounded-lg border border-theme-secondary p-4" aria-live="polite" aria-atomic="true">
        <h3 class="text-sm font-bold text-terminal-accent mb-3">🔄 货币转换器</h3>
        <div class="flex flex-wrap items-center gap-2">
          <input 
            type="number" 
            v-model.number="convertAmount" 
            class="w-28 px-3 py-2 bg-terminal-bg border border-theme-secondary rounded-sm text-terminal-primary text-sm font-mono tabular-nums focus:outline-none focus:border-terminal-accent"
            placeholder="金额"
            min="0"
            step="0.01"
          />
          <select 
            v-model="fromCurrency" 
            class="px-3 py-2 bg-terminal-bg border border-theme-secondary rounded-sm text-terminal-primary text-sm focus:outline-none focus:border-terminal-accent"
          >
            <option v-for="c in currencies" :key="c" :value="c">{{ c }}</option>
          </select>
          <button 
            @click="swapCurrencies" 
            class="px-2 py-2 bg-terminal-bg border border-theme-secondary rounded-sm text-terminal-dim hover:text-terminal-accent transition"
            type="button"
            aria-label="交换货币"
          >
            ⇄
          </button>
          <select 
            v-model="toCurrency" 
            class="px-3 py-2 bg-terminal-bg border border-theme-secondary rounded-sm text-terminal-primary text-sm focus:outline-none focus:border-terminal-accent"
          >
            <option v-for="c in currencies" :key="c" :value="c">{{ c }}</option>
          </select>
          <button 
            @click="convert" 
            class="px-4 py-2 rounded-sm text-sm bg-terminal-accent/20 text-terminal-accent hover:bg-terminal-accent/30 transition disabled:opacity-50"
            :disabled="converting"
            type="button"
          >
            {{ converting ? '...' : '转换' }}
          </button>
        </div>
        <div v-if="convertResult !== null" class="mt-3 text-lg font-bold text-terminal-primary font-mono tabular-nums" aria-live="polite" aria-atomic="true">
          {{ convertAmount }} {{ fromCurrency }} = <span class="text-terminal-accent">{{ convertResult.toFixed(6) }}</span> {{ toCurrency }}
        </div>
        <div v-if="convertError" class="mt-2 text-xs text-bearish">{{ convertError }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, computed, onWatcherCleanup } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import { apiFetch } from '../utils/api.js'
import { useSmartPolling } from '../composables/useSmartPolling.js'
import { classifyForexError } from '../utils/forexErrors.js'
import ForexQuotePanel from './forex/ForexQuotePanel.vue'
import CrossRateMatrix from './forex/CrossRateMatrix.vue'
import ForexKLineChart from './forex/ForexKLineChart.vue'

const loading = ref(true)
const loadingQuotes = ref(true)
const loadingMatrix = ref(true)
const loadingKline = ref(false)

const quotesError = ref(null)
const matrixError = ref(null)
const klineError = ref(null)

const lastQuotesUpdate = ref('')
const lastMatrixUpdate = ref('')
const lastKlineUpdate = ref('')

const currentTime = ref('')
const selectedSymbol = ref('USDCNH')

const currencies = ['USD', 'EUR', 'GBP', 'JPY', 'CNY', 'AUD', 'CAD', 'CHF']

const quotes = ref([])
const matrix = ref([])
const klineData = ref([])

const cachedQuotes = ref([])
const cachedMatrix = ref([])
const cachedKlineData = ref([])

const convertAmount = ref(100)
const fromCurrency = ref('USD')
const toCurrency = ref('CNY')
const convertResult = ref(null)
const convertError = ref(null)
const converting = ref(false)

const circuitBreakerStatus = ref(null)
const isOfflineMode = computed(() =>
  circuitBreakerStatus.value?.is_open === true && quotes.value.length === 0
)

const FOREX_TIMEOUT = 30000

// 请求版本跟踪 - 防止竞态条件
let quotesRequestId = 0
let matrixRequestId = 0
let klineRequestId = 0

function formatTimeNow() {
  return new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

async function fetchQuotes() {
  const requestId = ++quotesRequestId
  loadingQuotes.value = true
  quotesError.value = null
  
  const startTime = Date.now()
  
  try {
    const res = await apiFetch('/api/v1/forex/spot', { timeoutMs: FOREX_TIMEOUT })
    
    // 只接受最新请求的响应
    if (requestId !== quotesRequestId) return
    
    if (res?.quotes) {
      circuitBreakerStatus.value = res.circuit_breaker
      cachedQuotes.value = res.quotes
      quotes.value = res.quotes
      lastQuotesUpdate.value = formatTimeNow()
    }
  } catch (e) {
    if (requestId !== quotesRequestId) return
    const classified = classifyForexError(e)
    quotesError.value = classified.message
    
    if (cachedQuotes.value.length > 0) {
      quotes.value = cachedQuotes.value
    }
  } finally {
    if (requestId === quotesRequestId) {
      const elapsed = Date.now() - startTime
      const minLoading = 500 - elapsed
      if (minLoading > 0) {
        await new Promise(r => setTimeout(r, minLoading))
      }
      loadingQuotes.value = false
      loading.value = loadingQuotes.value || loadingMatrix.value
    }
  }
}

async function fetchMatrix() {
  const requestId = ++matrixRequestId
  loadingMatrix.value = true
  matrixError.value = null
  
  const startTime = Date.now()
  
  try {
    const res = await apiFetch('/api/v1/forex/matrix', { timeoutMs: FOREX_TIMEOUT })
    
    // 只接受最新请求的响应
    if (requestId !== matrixRequestId) return
    
    if (res?.matrix) {
      cachedMatrix.value = res.matrix
      matrix.value = res.matrix
      lastMatrixUpdate.value = formatTimeNow()
    }
  } catch (e) {
    if (requestId !== matrixRequestId) return
    const classified = classifyForexError(e)
    matrixError.value = classified.message
    
    if (cachedMatrix.value.length > 0) {
      matrix.value = cachedMatrix.value
    }
  } finally {
    if (requestId === matrixRequestId) {
      const elapsed = Date.now() - startTime
      const minLoading = 500 - elapsed
      if (minLoading > 0) {
        await new Promise(r => setTimeout(r, minLoading))
      }
      loadingMatrix.value = false
      loading.value = loadingQuotes.value || loadingMatrix.value
    }
  }
}

async function fetchKline() {
  if (!selectedSymbol.value) return

  const requestId = ++klineRequestId
  loadingKline.value = true
  klineError.value = null

  try {
    const symbol = selectedSymbol.value.replace('/', '')
    const res = await apiFetch(`/api/v1/forex/history/${symbol}?limit=100`, { timeoutMs: FOREX_TIMEOUT })

    // 只接受最新请求的响应
    if (requestId !== klineRequestId) return

    if (res?.data) {
      cachedKlineData.value = res.data
      klineData.value = res.data
      lastKlineUpdate.value = formatTimeNow()
    }
} catch (e) {
    if (requestId !== klineRequestId) return
    const classified = classifyForexError(e)
    klineError.value = classified.message
    
    if (cachedKlineData.value.length > 0) {
      klineData.value = cachedKlineData.value
    }
  } finally {
    if (requestId === klineRequestId) {
      loadingKline.value = false
    }
  }
}

const debouncedFetchKline = useDebounceFn(fetchKline, 300)

function refreshAll() {
  fetchQuotes()
  fetchMatrix()
  fetchKline()
}

function handleSelectQuote(quote) {
  selectedSymbol.value = quote.symbol
}

function swapCurrencies() {
  const temp = fromCurrency.value
  fromCurrency.value = toCurrency.value
  toCurrency.value = temp
}

async function convert() {
  if (fromCurrency.value === toCurrency.value) {
    convertResult.value = convertAmount.value
    return
  }
  
  converting.value = true
  convertError.value = null
  
  try {
    const res = await apiFetch('/api/v1/forex/cross-rate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        from_currency: fromCurrency.value,
        to_currency: toCurrency.value,
        amount: convertAmount.value
      }),
      timeoutMs: FOREX_TIMEOUT
    })
    
    if (res?.result !== undefined) {
      convertResult.value = res.result
    }
  } catch (e) {
    const classified = classifyForexError(e)
    convertError.value = classified.message
    convertResult.value = null
  } finally {
    converting.value = false
  }
}

async function resetCircuitBreaker() {
  converting.value = true  // reuse existing loading state
  try {
    await apiFetch('/api/v1/forex/circuit_breaker/reset', { method: 'POST' })
    await fetchQuotes()
    await fetchMatrix()
  } catch (e) {
    quotesError.value = "重置连接失败，请稍后重试"
  } finally {
    converting.value = false
  }
}

function updateTime() {
  currentTime.value = new Date().toLocaleTimeString('zh-CN')
}

const { start: startPolling, stop: stopPolling, isPolling } = useSmartPolling(
  async () => {
    await fetchQuotes()
    await fetchMatrix()
  },
  { interval: 5 * 60 * 1000, immediate: false, pauseWhenHidden: true }
)

let timeInterval = null

onMounted(async () => {
  updateTime()
  timeInterval = setInterval(updateTime, 1000)
  
  await Promise.all([fetchQuotes(), fetchMatrix()])
  await fetchKline()
  
  startPolling()
})

onUnmounted(() => {
  stopPolling()
  if (timeInterval) {
    clearInterval(timeInterval)
  }
})

watch(selectedSymbol, () => {
  debouncedFetchKline()
})
</script>

<style scoped>
.bg-terminal-bg {
  background: var(--bg-base, #121212);
}

.bg-surface {
  background: var(--bg-surface, #1e1e1e);
}

.text-terminal-accent {
  color: var(--color-primary, #0F52BA);
}

.text-terminal-primary {
  color: var(--text-primary, #F0F6FC);
}

.text-terminal-dim {
  color: var(--text-secondary, #C9D1D9);
}

.text-success {
  color: var(--color-bull, #E63946);
}

.text-bearish {
  color: var(--color-bear, #1A936F);
}

.border-theme-secondary {
  border-color: var(--border-base, #30363D);
}

.font-mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.tabular-nums {
  font-variant-numeric: tabular-nums;
}

.animate-pulse {
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
</style>
