<template>
  <div class="bg-surface rounded-lg border border-theme-secondary p-4 h-full flex flex-col" role="region" aria-label="外汇K线图">
    <div class="flex items-center justify-between mb-4 flex-shrink-0">
      <div class="flex items-center gap-2">
        <h3 class="text-sm font-bold text-terminal-accent">📈 {{ symbol }} K线走势</h3>
        <span v-if="lastUpdate" class="text-xs text-terminal-dim font-mono tabular-nums">{{ lastUpdate }}</span>
      </div>
      <div class="flex items-center gap-2">
        <select 
          v-model="selectedPeriod" 
          class="px-2 py-1 bg-terminal-bg border border-theme-secondary rounded-sm text-terminal-primary text-xs focus:outline-none focus:border-terminal-accent"
          @change="handlePeriodChange"
        >
          <option value="daily">日K</option>
          <option value="weekly">周K</option>
          <option value="monthly">月K</option>
        </select>
        <button 
          @click="handleRefresh"
          class="px-3 py-1.5 rounded-sm text-xs bg-terminal-accent/20 text-terminal-accent hover:bg-terminal-accent/30 transition disabled:opacity-50"
          :disabled="loading"
          type="button"
          aria-label="刷新K线数据"
        >
          {{ loading ? '...' : '刷新' }}
        </button>
      </div>
    </div>
    
    <div v-if="error" class="mb-3 p-2 bg-bearish/10 border border-bearish/30 rounded-sm flex items-center gap-2 flex-shrink-0">
      <span class="text-bearish text-xs">⚠️ {{ error }}</span>
      <button 
        @click="handleRefresh"
        class="px-2 py-0.5 bg-bearish/20 text-bearish rounded-sm text-xs hover:bg-bearish/30 transition"
        type="button"
      >
        重试
      </button>
    </div>
    
    <div v-if="loading && !chartData" class="flex-1 flex flex-col items-center justify-center gap-2">
      <div class="animate-pulse w-full h-8 bg-terminal-bg/30 rounded mb-2"></div>
      <div class="animate-pulse w-3/4 h-32 bg-terminal-bg/30 rounded"></div>
      <div class="animate-pulse w-1/2 h-4 bg-terminal-bg/30 rounded"></div>
    </div>
    
    <div v-else-if="chartData && !chartData.isEmpty" class="flex-1 min-h-0">
      <BaseKLineChart 
        :chart-data="chartData"
        :sub-charts="[]"
        :symbol="symbol"
      />
    </div>
    
    <div v-else class="flex-1 flex flex-col items-center justify-center text-terminal-dim">
      <span class="text-2xl mb-2">📈</span>
      <p class="text-xs">暂无K线数据</p>
      <button 
        v-if="!loading"
        @click="handleRefresh"
        class="mt-2 px-3 py-1.5 rounded-sm text-xs bg-terminal-accent/20 text-terminal-accent hover:bg-terminal-accent/30 transition"
        type="button"
      >
        加载数据
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed, onMounted } from 'vue'
import BaseKLineChart from '../BaseKLineChart.vue'
import { buildChartData } from '../../utils/chartDataBuilder.js'

const props = defineProps({
  symbol: {
    type: String,
    default: 'USDCNH'
  },
  apiData: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  },
  error: {
    type: String,
    default: null
  },
  lastUpdate: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['refresh'])

const selectedPeriod = ref('daily')

// Transform API data to chartData format
const chartData = computed(() => {
  if (!props.apiData || props.apiData.length === 0) {
    return { isEmpty: true }
  }
  
  // Transform forex history data to OHLCV format
  const ohlcvData = props.apiData.map(item => ({
    time: item.date || item.time,
    open: item.open,
    high: item.high,
    low: item.low,
    close: item.close,
    volume: 0, // Forex has no meaningful volume
    amplitude: item.amplitude || 0 // Use amplitude instead of volume for forex
  }))
  
  // Build chart data using existing builder (without volume subchart)
  const result = buildChartData(ohlcvData, 'daily', {}, [], { 
    useWorker: true,
    timeout: 10000,
    ma: true, 
    boll: false, 
    macd: false, 
    kdj: false, 
    rsi: false 
  })
  
  return result
})

function handleRefresh() {
  emit('refresh')
}

function handlePeriodChange() {
  emit('refresh', selectedPeriod.value)
}

// Watch for symbol changes
watch(() => props.symbol, () => {
  selectedPeriod.value = 'daily'
})
</script>

<style scoped>
.bg-surface {
  background: var(--bg-surface, #1e1e1e);
}

.bg-terminal-bg {
  background: var(--bg-base, #121212);
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
