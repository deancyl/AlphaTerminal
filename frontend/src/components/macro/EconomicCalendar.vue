<template>
  <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-3 md:p-4">
    <div class="flex flex-col md:flex-row md:items-center justify-between gap-3 mb-4">
      <h3 class="text-sm font-bold text-terminal-accent">📅 经济数据日历</h3>
      
      <div class="flex flex-wrap items-center gap-2">
        <select 
          v-model="selectedCountry"
          class="px-2 py-1 rounded-sm text-xs bg-terminal-bg border border-theme-secondary text-terminal-primary focus:border-terminal-accent focus:outline-none"
          @change="fetchCalendar"
        >
          <option value="">全部国家</option>
          <option value="CN">中国</option>
          <option value="US">美国</option>
          <option value="EU">欧元区</option>
          <option value="JP">日本</option>
        </select>
        
        <select 
          v-model="selectedImportance"
          class="px-2 py-1 rounded-sm text-xs bg-terminal-bg border border-theme-secondary text-terminal-primary focus:border-terminal-accent focus:outline-none"
          @change="fetchCalendar"
        >
          <option value="">全部重要性</option>
          <option value="high">高</option>
          <option value="medium">中</option>
          <option value="low">低</option>
        </select>
        
        <span class="text-[10px] text-terminal-dim/70">{{ calendarItems.length }}项</span>
      </div>
    </div>
    
    <div v-if="loading" class="space-y-2">
      <div v-for="i in 5" :key="i" class="animate-pulse">
        <div class="h-12 bg-terminal-bg/50 rounded-md"></div>
      </div>
    </div>
    
    <div v-else-if="error" class="text-center py-8 text-terminal-dim text-sm">
      <p class="mb-2">{{ error }}</p>
      <button 
        class="px-3 py-1.5 rounded-sm text-xs bg-terminal-accent/20 text-terminal-accent hover:bg-terminal-accent/30 transition"
        @click="fetchCalendar"
      >
        重试
      </button>
    </div>
    
    <div v-else-if="calendarItems.length > 0" class="space-y-2 max-h-[400px] overflow-y-auto">
      <div 
        v-for="(item, index) in calendarItems" 
        :key="`${item.indicator}-${index}`"
        class="flex flex-col md:flex-row md:items-center justify-between py-2 px-3 rounded-md hover:bg-terminal-bg/30 transition-colors gap-2"
        :class="index < calendarItems.length - 1 ? 'border-b border-theme/10' : ''"
      >
        <div class="flex items-center gap-2 md:gap-3">
          <span 
            class="text-[10px] px-2 py-0.5 rounded-full font-medium shrink-0"
            :class="getImportanceClass(item.importance)"
          >
            {{ getImportanceLabel(item.importance) }}
          </span>
          
          <span 
            class="text-[10px] px-1.5 py-0.5 rounded text-terminal-dim shrink-0"
            :class="getCountryClass(item.country)"
          >
            {{ item.country }}
          </span>
          
          <span class="text-sm text-terminal-primary font-medium">{{ item.name }}</span>
        </div>
        
        <div class="flex items-center gap-2 md:gap-4 text-xs">
          <span class="text-[10px] text-terminal-dim w-20 shrink-0">
            {{ item.date || '待定' }}
          </span>
          
          <div v-if="item.status === 'released'" class="flex items-center gap-2">
            <div class="flex items-center gap-1">
              <span class="text-[10px] text-terminal-dim">预测:</span>
              <span class="text-xs font-mono text-terminal-dim">
                {{ formatValue(item.forecast) }}{{ item.unit }}
              </span>
            </div>
            
            <div class="flex items-center gap-1">
              <span class="text-[10px] text-terminal-dim">实际:</span>
              <span 
                class="text-sm font-mono font-bold"
                :class="getDeviationColor(item.deviation)"
              >
                {{ formatValue(item.actual) }}{{ item.unit }}
              </span>
            </div>
            
            <div v-if="item.deviation !== null" class="flex items-center gap-1">
              <span 
                class="text-xs font-mono font-bold px-1.5 py-0.5 rounded"
                :class="getDeviationBackground(item.deviation)"
              >
                {{ item.deviation > 0 ? '+' : '' }}{{ item.deviation.toFixed(1) }}%
              </span>
            </div>
          </div>
          
          <span 
            v-else
            class="text-[10px] px-2 py-0.5 rounded-full bg-terminal-dim/20 text-terminal-dim"
          >
            待发布
          </span>
        </div>
      </div>
    </div>
    
    <div v-else class="text-center py-8 text-terminal-dim text-sm">
      暂无数据
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { apiFetch } from '../../utils/api.js'

const props = defineProps({
  initialCountry: {
    type: String,
    default: ''
  },
  initialImportance: {
    type: String,
    default: ''
  }
})

const selectedCountry = ref(props.initialCountry)
const selectedImportance = ref(props.initialImportance)
const calendarItems = ref([])
const loading = ref(false)
const error = ref(null)

let abortController = null

async function fetchCalendar() {
  if (abortController) {
    abortController.abort()
  }
  
  abortController = new AbortController()
  loading.value = true
  error.value = null
  
  try {
    const params = new URLSearchParams()
    if (selectedCountry.value) params.append('country', selectedCountry.value)
    if (selectedImportance.value) params.append('importance', selectedImportance.value)
    
    const url = `/api/v1/macro/calendar?${params.toString()}`
    const response = await apiFetch(url, { timeoutMs: 30000, signal: abortController.signal })
    
    if (response && response.data && response.data.calendar) {
      calendarItems.value = response.data.calendar
    }
  } catch (err) {
    if (err.name !== 'AbortError') {
      error.value = '加载失败，请稍后重试'
      console.error('[EconomicCalendar] Fetch error:', err)
    }
  } finally {
    loading.value = false
  }
}

function formatValue(value) {
  if (value === null || value === undefined) return '-'
  return typeof value === 'number' ? value.toFixed(2) : value
}

function getImportanceClass(importance) {
  return {
    'bg-red-500/20 text-red-400': importance === 'high',
    'bg-yellow-500/20 text-yellow-400': importance === 'medium',
    'bg-green-500/20 text-green-400': importance === 'low'
  }
}

function getImportanceLabel(importance) {
  return {
    'high': '高',
    'medium': '中',
    'low': '低'
  }[importance] || importance
}

function getCountryClass(country) {
  return {
    'bg-red-500/10 text-red-300': country === 'CN',
    'bg-blue-500/10 text-blue-300': country === 'US',
    'bg-purple-500/10 text-purple-300': country === 'EU',
    'bg-pink-500/10 text-pink-300': country === 'JP'
  }
}

function getDeviationColor(deviation) {
  if (deviation === null) return 'text-terminal-primary'
  if (Math.abs(deviation) < 5) return 'text-terminal-primary'
  return deviation > 0 ? 'text-bullish' : 'text-bearish'
}

function getDeviationBackground(deviation) {
  if (deviation === null) return ''
  if (Math.abs(deviation) < 5) return 'bg-terminal-dim/20 text-terminal-dim'
  return deviation > 0 
    ? 'bg-bullish/20 text-bullish' 
    : 'bg-bearish/20 text-bearish'
}

onMounted(() => {
  fetchCalendar()
})

onUnmounted(() => {
  if (abortController) {
    abortController.abort()
  }
})

defineExpose({
  refresh: fetchCalendar
})
</script>
