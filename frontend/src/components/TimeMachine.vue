<template>
  <div class="flex flex-col h-full bg-base">
    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-3 bg-surface border-b border-border-base">
      <div class="flex items-center gap-4">
        <h2 class="text-lg font-semibold text-primary">时光机复盘</h2>
        
        <!-- Symbol Selector -->
        <select
          v-model="symbol"
          :disabled="!!session"
          class="px-3 py-1.5 bg-base rounded-lg border border-border-base text-primary
                 focus:border-primary focus:outline-none text-sm"
        >
          <option value="sh600519">贵州茅台 sh600519</option>
          <option value="sh600036">招商银行 sh600036</option>
          <option value="sh601318">中国平安 sh601318</option>
          <option value="sz000001">平安银行 sz000001</option>
          <option value="sz000858">五粮液 sz000858</option>
        </select>
      </div>
      
      <!-- Date Range -->
      <div class="flex items-center gap-3">
        <input
          v-model="startDate"
          type="date"
          :disabled="!!session"
          class="px-3 py-1.5 bg-base rounded-lg border border-border-base text-primary
                 focus:border-primary focus:outline-none text-sm"
        />
        <span class="text-secondary text-sm">至</span>
        <input
          v-model="endDate"
          type="date"
          :disabled="!!session"
          class="px-3 py-1.5 bg-base rounded-lg border border-border-base text-primary
                 focus:border-primary focus:outline-none text-sm"
        />
        
        <!-- Action Buttons -->
        <button
          v-if="!session"
          @click="handleCreateSession"
          :disabled="loading || !symbol || !startDate || !endDate"
          class="px-4 py-1.5 bg-primary text-white rounded-lg text-sm font-medium
                 hover:bg-primary-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {{ loading ? '加载中...' : '开始复盘' }}
        </button>
        <button
          v-else
          @click="handleEndSession"
          class="px-4 py-1.5 bg-danger text-white rounded-lg text-sm font-medium
                 hover:bg-danger/90 transition-colors"
        >
          结束复盘
        </button>
      </div>
    </div>
    
    <!-- Main Content -->
    <div class="flex-1 flex gap-4 p-4 min-h-0">
      <!-- K-line Chart Area -->
      <div class="flex-1 bg-surface rounded-xl border border-border-base overflow-hidden relative">
        <!-- Empty State -->
        <div
          v-if="!session"
          class="absolute inset-0 flex items-center justify-center"
        >
          <div class="text-center">
            <svg class="w-16 h-16 text-muted mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
                    d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p class="text-secondary text-sm">选择股票和日期范围，开始时光机复盘</p>
          </div>
        </div>
        
        <!-- Loading State -->
        <div
          v-else-if="loading && klineData.length === 0"
          class="absolute inset-0 flex items-center justify-center bg-glass"
        >
          <div class="text-center">
            <div class="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
            <p class="text-secondary text-sm">加载历史数据...</p>
          </div>
        </div>
        
        <!-- Chart -->
        <template v-else-if="session && chartData && !chartData.isEmpty">
          <BaseKLineChart
            :chart-data="chartData"
            :symbol="symbol"
            :sub-charts="['VOL']"
          />
          
          <!-- Playback Controls Overlay -->
          <PlaybackControls
            :status="playbackStatus"
            :current-bar="currentBar"
            :total-bars="totalBars"
            :speed="speed"
            @play="togglePlay"
            @pause="togglePlay"
            @step="stepForward"
            @speed-change="setSpeed"
          />
        </template>
      </div>
      
      <!-- Paper Trading Panel -->
      <PaperTradingPanel
        v-if="session"
        :portfolio="portfolio"
        :trades="trades"
        :current-price="currentPrice"
        @trade="handleTrade"
      />
    </div>
    
    <!-- Progress Bar -->
    <div v-if="session && totalBars > 0" class="px-4 pb-4">
      <div
        class="relative h-2 bg-surface rounded-full overflow-hidden cursor-pointer"
        @click="handleProgressClick"
        ref="progressBar"
      >
        <!-- Progress Fill -->
        <div
          class="absolute left-0 top-0 h-full bg-primary transition-all duration-100"
          :style="{ width: `${progressPct}%` }"
        />
        
        <!-- Draggable Cursor -->
        <div
          class="absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full shadow-md cursor-grab active:cursor-grabbing"
          :style="{ left: `calc(${progressPct}% - 6px)` }"
          @mousedown="startDrag"
          @touchstart="startDrag"
        />
      </div>
      
      <!-- Date Labels -->
      <div class="flex justify-between text-xs text-muted mt-2">
        <span>{{ formatDate(klineData[0]?.date) }}</span>
        <span class="text-primary font-medium">{{ formatDate(currentDate) }}</span>
        <span>{{ formatDate(klineData[totalBars - 1]?.date) }}</span>
      </div>
    </div>
    
    <!-- Error Toast -->
    <div
      v-if="error"
      class="fixed bottom-4 right-4 px-4 py-3 bg-danger text-white rounded-lg shadow-theme-lg z-50"
    >
      {{ error }}
      <button @click="error = null" class="ml-3 opacity-70 hover:opacity-100">✕</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useTimeMachine } from '@/composables/useTimeMachine.js'
import { buildChartData } from '@/utils/chartDataBuilder.js'
import BaseKLineChart from '@/components/BaseKLineChart.vue'
import PlaybackControls from '@/components/timemachine/PlaybackControls.vue'
import PaperTradingPanel from '@/components/timemachine/PaperTradingPanel.vue'

// TimeMachine composable
const {
  session,
  loading,
  error,
  klineData,
  currentBar,
  currentDate,
  currentPrice,
  totalBars,
  playbackStatus,
  speed,
  portfolio,
  trades,
  progressPct,
  createSession,
  stepForward,
  togglePlay,
  setSpeed,
  executeTrade,
  seekTo,
  endSession,
  formatDate
} = useTimeMachine()

// Local state
const symbol = ref('sh600519')
const startDate = ref('')
const endDate = ref('')
const progressBar = ref(null)
const isDragging = ref(false)

// Chart data computed from klineData
const chartData = computed(() => {
  if (!klineData.value || klineData.value.length === 0) {
    return { isEmpty: true }
  }
  
  // Only show visible portion (up to current bar)
  const visibleData = klineData.value.slice(0, currentBar.value + 1)
  
  return buildChartData(visibleData, 'daily', {
    MA: { periods: [5, 10, 20] },
    BOLL: { period: 20, stdDev: 2 }
  })
})

// Initialize dates
onMounted(() => {
  const today = new Date()
  const oneYearAgo = new Date(today)
  oneYearAgo.setFullYear(today.getFullYear() - 1)
  
  endDate.value = today.toISOString().split('T')[0]
  startDate.value = oneYearAgo.toISOString().split('T')[0]
})

// Create session
async function handleCreateSession() {
  if (!symbol.value || !startDate.value || !endDate.value) return
  
  try {
    await createSession(symbol.value, startDate.value, endDate.value, 1000000)
  } catch (e) {
    console.error('Failed to create session:', e)
  }
}

// End session
async function handleEndSession() {
  await endSession()
}

// Handle trade from PaperTradingPanel
async function handleTrade({ action, quantity }) {
  try {
    await executeTrade(action, quantity)
  } catch (e) {
    console.error('Trade failed:', e)
  }
}

// Progress bar click
function handleProgressClick(e) {
  if (!progressBar.value || isDragging.value) return
  
  const rect = progressBar.value.getBoundingClientRect()
  const pct = (e.clientX - rect.left) / rect.width
  const targetBar = Math.floor(pct * totalBars.value)
  
  seekTo(targetBar)
}

// Drag handling
function startDrag(e) {
  e.preventDefault()
  isDragging.value = true
  
  const handleMove = (moveEvent) => {
    if (!progressBar.value) return
    
    const rect = progressBar.value.getBoundingClientRect()
    const clientX = moveEvent.touches ? moveEvent.touches[0].clientX : moveEvent.clientX
    const pct = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width))
    const targetBar = Math.floor(pct * totalBars.value)
    
    seekTo(targetBar)
  }
  
  const handleEnd = () => {
    isDragging.value = false
    document.removeEventListener('mousemove', handleMove)
    document.removeEventListener('mouseup', handleEnd)
    document.removeEventListener('touchmove', handleMove)
    document.removeEventListener('touchend', handleEnd)
  }
  
  document.addEventListener('mousemove', handleMove)
  document.addEventListener('mouseup', handleEnd)
  document.addEventListener('touchmove', handleMove)
  document.addEventListener('touchend', handleEnd)
}
</script>