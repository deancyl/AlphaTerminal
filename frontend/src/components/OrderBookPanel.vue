<template>
  <div class="order-book-panel">
    <div class="panel-header">
      <span class="title">买卖盘口</span>
      <span class="symbol">{{ symbol }}</span>
    </div>
    
    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else class="book-content">
      <!-- 卖盘 (asks) -->
      <div class="book-section asks">
        <div class="section-title">卖盘</div>
        <div class="book-row header">
          <span>价格</span>
          <span>量</span>
        </div>
        <div 
          v-for="item in reversedAsks" 
          :key="'a'+item.position" 
          class="book-row ask"
        >
          <span class="price bear">{{ formatPrice(item.price) }}</span>
          <span class="volume">{{ formatVol(item.volume) }}</span>
          <div 
            class="volume-bar" 
            :style="{ width: getBarWidth(item.volume, maxVol) + '%' }"
          ></div>
        </div>
      </div>
      
      <!-- 当前价 -->
      <div class="current-price" :class="priceDirection">
        <span class="price">{{ formatPrice(lastPrice) }}</span>
        <span class="direction">{{ priceDirection === 'up' ? '↑' : priceDirection === 'down' ? '↓' : '-' }}</span>
      </div>
      
      <!-- 买盘 (bids) -->
      <div class="book-section bids">
        <div 
          v-for="item in reversedBids" 
          :key="'b'+item.position" 
          class="book-row bid"
        >
          <span class="price bull">{{ formatPrice(item.price) }}</span>
          <span class="volume">{{ formatVol(item.volume) }}</span>
          <div 
            class="volume-bar" 
            :style="{ width: getBarWidth(item.volume, maxVol) + '%' }"
          ></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  symbol: { type: String, required: true }
})

const data = ref(null)
const loading = ref(true)
const error = ref(null)
const lastPrice = ref(0)
const priceDirection = ref('') // 'up', 'down', ''
let prevPrice = 0

const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8002/api/v1'

// 倒序显示（靠近当前价的在前）
const reversedAsks = computed(() => {
  if (!data.value?.asks) return []
  return [...data.value.asks].reverse().slice(0, 5)
})

const reversedBids = computed(() => {
  if (!data.value?.bids) return []
  return data.value.bids.slice(0, 5)
})

const maxVol = computed(() => {
  const all = [...(data.value?.asks || []), ...(data.value?.bids || [])]
  if (!all.length) return 1
  return Math.max(...all.map(v => v.volume))
})

async function fetchOrderBook() {
  if (!props.symbol) return
  
  loading.value = true
  error.value = null
  
  try {
    const resp = await fetch(`${API_BASE}/market/order_book/${props.symbol}`)
    const json = await resp.json()
    
    if (json.code === 0) {
      data.value = json.data
      
      // 指数暂无Level 2数据时显示提示
      if (json.data.note && !json.data.asks?.length && !json.data.bids?.length) {
        error.value = json.data.note
        data.value = null
      }
      
      // 计算价格方向
      const prices = [
        ...(json.data.asks || []).map(a => a.price),
        ...(json.data.bids || []).map(b => b.price)
      ]
      if (prices.length) {
        const newPrice = prices.reduce((a, b) => a + b, 0) / prices.length
        if (newPrice > prevPrice) {
          priceDirection.value = 'up'
        } else if (newPrice < prevPrice) {
          priceDirection.value = 'down'
        } else {
          priceDirection.value = ''
        }
        prevPrice = newPrice
      }
    } else {
      error.value = json.message
    }
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function formatPrice(p) {
  if (!p) return '--'
  return p.toFixed(2)
}

function formatVol(v) {
  if (!v) return '0'
  if (v >= 10000) return (v / 10000).toFixed(1) + 'w'
  if (v >= 1000) return (v / 1000).toFixed(1) + 'k'
  return v
}

function getBarWidth(v, max) {
  if (!max) return 0
  return Math.min(100, (v / max) * 100)
}

// 定时刷新
let refreshTimer = null

watch(() => props.symbol, () => {
  prevPrice = 0
  fetchOrderBook()
})

onMounted(() => {
  fetchOrderBook()
  // 每5秒刷新
  refreshTimer = setInterval(fetchOrderBook, 5000)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<style scoped>
.order-book-panel {
  background: var(--bg-secondary, #1a1a2e);
  border-radius: 8px;
  padding: 12px;
  font-size: 12px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.title {
  font-weight: 600;
  color: var(--text-primary, #fff);
}

.symbol {
  color: var(--text-secondary, #888);
  font-size: 11px;
}

.loading, .error {
  text-align: center;
  padding: 20px;
  color: var(--text-secondary, #888);
}

.error {
  color: #ff6b6b;
}

.book-section {
  margin: 4px 0;
}

.section-title {
  font-size: 10px;
  color: var(--text-secondary, #666);
  margin-bottom: 4px;
}

.book-row {
  display: flex;
  justify-content: space-between;
  padding: 2px 4px;
  position: relative;
}

.book-row.header {
  color: var(--text-secondary, #666);
  font-size: 10px;
}

.price {
  font-family: monospace;
  width: 60px;
}

.volume {
  font-family: monospace;
  width: 40px;
  text-align: right;
}

.bull {
  color: var(--bullish, #26a69a);
}

.bear {
  color: var(--bearish, #ef5350);
}

.volume-bar {
  position: absolute;
  top: 0;
  right: 0;
  height: 100%;
  opacity: 0.15;
  z-index: 0;
}

.ask .volume-bar {
  background: var(--bearish, #ef5350);
}

.bid .volume-bar {
  background: var(--bullish, #26a69a);
}

.current-price {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px;
  background: var(--bg-primary, #16162a);
  border-radius: 4px;
  margin: 4px 0;
}

.current-price .price {
  font-size: 16px;
  font-weight: 600;
  width: auto;
}

.current-price.up .price {
  color: var(--bullish, #26a69a);
}

.current-price.down .price {
  color: var(--bearish, #ef5350);
}

.direction {
  margin-left: 4px;
  font-size: 14px;
}
</style>