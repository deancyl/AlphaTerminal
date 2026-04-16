<template>
  <div class="simple-quote-panel">
    <div class="panel-header">
      <span class="title">实时报价</span>
      <input 
        v-model="localSymbol" 
        @keyup.enter="changeSymbol"
        placeholder="输入股票代码如 sh600519"
        class="symbol-input"
      />
    </div>
    
    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else class="quote-content">
      <div class="symbol-info">
        <span class="symbol">{{ symbol }}</span>
        <span class="status" :class="marketStatus">{{ statusText }}</span>
      </div>
      
      <div class="price-display" :class="priceDirection">
        <span class="current-price">{{ formatPrice(data?.price || 0) }}</span>
        <span class="change">{{ formatChange(data?.change_pct || 0) }}</span>
      </div>
      
      <div class="quote-details">
        <div class="detail-row">
          <span class="label">今开</span>
          <span class="value">{{ formatPrice(data?.open || 0) }}</span>
        </div>
        <div class="detail-row">
          <span class="label">最高</span>
          <span class="value">{{ formatPrice(data?.high || 0) }}</span>
        </div>
        <div class="detail-row">
          <span class="label">最低</span>
          <span class="value">{{ formatPrice(data?.low || 0) }}</span>
        </div>
        <div class="detail-row">
          <span class="label">昨收</span>
          <span class="value">{{ formatPrice(data?.prev_close || 0) }}</span>
        </div>
        <div class="detail-row">
          <span class="label">成交量</span>
          <span class="value">{{ formatVol(data?.volume || 0) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { apiFetch } from '../utils/api.js'
import { logger } from '../utils/logger.js'

const props = defineProps({
  symbol: { type: String, required: true }
})

const emit = defineEmits(['update:symbol'])

const data = ref(null)
const loading = ref(true)
const error = ref(null)
const localSymbol = ref(props.symbol)
const lastPrice = ref(0)
const priceDirection = ref('') // 'up', 'down', ''
let prevPrice = 0
let timer = null

const marketStatus = computed(() => {
  const pct = data.value?.change_pct || 0
  if (pct > 0) return 'up'
  if (pct < 0) return 'down'
  return 'flat'
})

const statusText = computed(() => {
  if (!data.value) return '加载中'
  if (data.value.price === 0) return '休市中'
  return '交易中'
})

function formatPrice(p) {
  if (!p || p === 0) return '--'
  return p.toFixed(2)
}

function formatChange(pct) {
  if (!pct && pct !== 0) return '--'
  const sign = pct > 0 ? '+' : ''
  return `${sign}${pct.toFixed(2)}%`
}

function formatVol(v) {
  if (!v) return '--'
  if (v >= 100000000) return (v / 100000000).toFixed(2) + '亿'
  if (v >= 10000) return (v / 10000).toFixed(2) + '万'
  return v.toString()
}

function changeSymbol() {
  const s = localSymbol.value.trim()
  if (s) {
    emit('update:symbol', s)
  }
}

async function fetchQuote() {
  if (!props.symbol) return
  
  loading.value = true
  error.value = null
  
  try {
    const json = await apiFetch(`/api/v1/market/quote_detail/${props.symbol}`)
    
    if (json) {
      data.value = json
      
      // 检测价格方向
      if (json.price > prevPrice) {
        priceDirection.value = 'up'
      } else if (json.price < prevPrice) {
        priceDirection.value = 'down'
      } else {
        priceDirection.value = ''
      }
      prevPrice = json.price
      lastPrice.value = json.price
    }
  } catch (e) {
    logger.error('[SimpleQuote] fetch error:', e)
    error.value = e.message || '获取数据失败'
  } finally {
    loading.value = false
  }
}

// 轮询获取数据
function startPolling() {
  fetchQuote()
  timer = setInterval(fetchQuote, 5000) // 5秒刷新
}

function stopPolling() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

watch(() => props.symbol, (newSymbol) => {
  localSymbol.value = newSymbol
  stopPolling()
  startPolling()
})

onMounted(startPolling)
onUnmounted(stopPolling)
</script>

<style scoped>
.simple-quote-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 12px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.title {
  font-weight: bold;
  color: var(--text-primary);
}

.symbol-input {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  width: 140px;
}

.loading, .error {
  text-align: center;
  padding: 20px;
  color: var(--text-secondary);
}

.error {
  color: #ef4444;
}

.quote-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.symbol-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.symbol {
  font-size: 14px;
  font-weight: bold;
  color: var(--text-primary);
}

.status {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--bg-tertiary);
}

.status.up {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}

.status.down {
  background: rgba(34, 197, 94, 0.2);
  color: #22c55e;
}

.price-display {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 16px;
  background: var(--bg-secondary);
  border-radius: 8px;
  justify-content: center;
}

.current-price {
  font-size: 28px;
  font-weight: bold;
  font-family: 'Courier New', monospace;
}

.price-display.up .current-price {
  color: #ef4444;
}

.price-display.down .current-price {
  color: #22c55e;
}

.change {
  font-size: 14px;
}

.price-display.up .change {
  color: #ef4444;
}

.price-display.down .change {
  color: #22c55e;
}

.quote-details {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  padding: 6px 8px;
  background: var(--bg-tertiary);
  border-radius: 4px;
  font-size: 12px;
}

.label {
  color: var(--text-secondary);
}

.value {
  color: var(--text-primary);
  font-family: 'Courier New', monospace;
}
</style>