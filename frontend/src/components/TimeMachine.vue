<template>
  <div class="flex flex-col h-full bg-base" :class="{ 'landscape-immersive': isLandscape && isMobile }">
    <!-- Header (hidden in landscape immersive mode) -->
    <div v-if="!(isLandscape && isMobile)" class="flex items-center justify-between px-4 py-3 bg-surface border-b border-border-base">
      <!-- Desktop: Full header -->
      <div v-if="!isMobile" class="flex items-center gap-4">
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
      
      <!-- Mobile: Compact header -->
      <div v-else class="flex items-center gap-2 flex-1 min-w-0">
        <h2 class="text-base font-semibold text-primary whitespace-nowrap">时光机</h2>
        <select
          v-model="symbol"
          :disabled="!!session"
          class="flex-1 min-w-0 px-2 py-2 bg-base rounded-lg border border-border-base text-primary
                 focus:border-primary focus:outline-none text-xs min-h-[44px]"
        >
          <option value="sh600519">贵州茅台</option>
          <option value="sh600036">招商银行</option>
          <option value="sh601318">中国平安</option>
          <option value="sz000001">平安银行</option>
          <option value="sz000858">五粮液</option>
        </select>
      </div>
      
      <!-- Date Range & Actions -->
      <div v-if="!isMobile" class="flex items-center gap-3">
        <div class="flex flex-col">
          <input
            v-model="startDate"
            type="date"
            :disabled="!!session"
            class="px-3 py-1.5 bg-base rounded-lg border border-border-base text-primary
                   focus:border-primary focus:outline-none text-sm"
          />
        </div>
        <span class="text-secondary text-sm">至</span>
        <div class="flex flex-col">
          <input
            v-model="endDate"
            type="date"
            :disabled="!!session"
            class="px-3 py-1.5 bg-base rounded-lg border border-border-base text-primary
                   focus:border-primary focus:outline-none text-sm"
          />
        </div>
        
        <!-- Date Error Display -->
        <div v-if="dateError" class="text-danger text-xs whitespace-nowrap">
          {{ dateError }}
        </div>
        
        <!-- Data Source Indicator (v0.6.220) -->
        <div v-if="session" class="flex items-center gap-2 text-xs">
          <span :class="dataSourceStatusColor" class="text-sm">●</span>
          <span class="text-theme-muted">{{ dataSourceLabel }}</span>
          <span v-if="dataSourceFreshness && dataSourceFreshness.ageMs > 0" class="text-theme-tertiary">
            {{ dataSourceFreshness.ageText }}
          </span>
          <span v-if="wsStatus === 'connected'" class="text-green-400 ml-2">● 实时</span>
          <span v-else class="text-yellow-500 ml-2">○ 离线</span>
        </div>
        
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
      
      <!-- Mobile: Action buttons only -->
      <div v-else class="flex items-center gap-2">
        <!-- Data Source Indicator (v0.6.220) -->
        <div v-if="session" class="flex items-center gap-1 text-[10px]">
          <span :class="dataSourceStatusColor">●</span>
          <span class="text-theme-muted">{{ dataSourceLabel }}</span>
          <span v-if="dataSourceFreshness && dataSourceFreshness.ageMs > 0" class="text-theme-tertiary">
            {{ dataSourceFreshness.ageText }}
          </span>
          <span v-if="wsStatus === 'connected'" class="text-green-400 ml-1">●</span>
          <span v-else class="text-yellow-500 ml-1">○</span>
        </div>
        <button
          v-if="!session"
          @click="handleCreateSession"
          :disabled="loading || !symbol || !startDate || !endDate"
          class="px-3 py-2 bg-primary text-white rounded-lg text-xs font-medium
                 hover:bg-primary-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed min-h-[44px]"
        >
          {{ loading ? '加载...' : '开始' }}
        </button>
        <template v-else>
          <button
            @click="showTradePanel = true"
            class="px-3 py-2 bg-primary text-white rounded-lg text-xs font-medium min-h-[44px]"
          >
            交易
          </button>
          <button
            @click="handleEndSession"
            class="px-3 py-2 bg-danger text-white rounded-lg text-xs font-medium min-h-[44px]"
          >
            结束
          </button>
        </template>
      </div>
    </div>
    
    <!-- Landscape Immersive Mode: Exit Button -->
    <button
      v-if="isLandscape && isMobile"
      @click="unlockOrientation"
      class="absolute top-2 right-2 z-50 px-3 py-2 bg-surface/80 backdrop-blur rounded-lg text-xs font-medium text-primary border border-border-base min-h-[44px]"
    >
      退出横屏
    </button>
    
    <!-- Mobile: Date Range (shown below header when no session) -->
    <div v-if="isMobile && !session" class="flex flex-col gap-2 px-4 py-2 bg-surface border-b border-border-base">
      <div class="flex items-center gap-2">
        <input
          v-model="startDate"
          type="date"
          :disabled="!!session"
          class="flex-1 px-2 py-2 bg-base rounded-lg border border-border-base text-primary
                 focus:border-primary focus:outline-none text-xs min-h-[44px]"
        />
        <span class="text-secondary text-xs">至</span>
        <input
          v-model="endDate"
          type="date"
          :disabled="!!session"
          class="flex-1 px-2 py-2 bg-base rounded-lg border border-border-base text-primary
                 focus:border-primary focus:outline-none text-xs min-h-[44px]"
        />
      </div>
      <!-- Date Error Display (Mobile) -->
      <div v-if="dateError" class="text-danger text-xs px-1">
        {{ dateError }}
      </div>
    </div>
    
    <!-- Main Content -->
    <div class="flex-1 flex gap-4 p-4 min-h-0" :class="{ 'flex-col': isMobile }">
      <!-- K-line Chart Area -->
      <div class="flex-1 bg-surface rounded-xl border border-border-base overflow-hidden relative">
        <!-- Empty State -->
        <div
          v-if="!session"
          class="absolute inset-0 flex items-center justify-center"
        >
          <div class="text-center max-w-md px-4">
            <svg class="w-16 h-16 text-muted mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
                    d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <h3 class="text-lg font-semibold text-primary mb-2">沉浸式历史复盘</h3>
            <p class="text-secondary text-sm mb-3">在历史行情中练习交易决策，提升实战能力</p>
            <p class="text-xs text-muted">选择股票和日期范围，开始时光机复盘</p>
            <p class="text-xs text-muted mt-1">当前仅支持日线级别复盘</p>
            <div class="mt-4 text-xs text-muted space-y-1">
              <p>⌨️ 快捷键：<span class="text-secondary">空格</span> 播放/暂停 | <span class="text-secondary">←→</span> 单步前进/后退</p>
            </div>
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
            <p class="text-xs text-muted mt-1" v-if="totalBars > 0">{{ currentBar }}/{{ totalBars }} 根K线</p>
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
      
      <!-- Desktop: Paper Trading Panel (side-by-side) -->
      <PaperTradingPanel
        v-if="session && !isMobile"
        :portfolio="portfolio"
        :trades="trades"
        :current-price="currentPrice"
        @trade="handleTrade"
      />
    </div>
    
    <!-- Mobile: Paper Trading Panel (BottomSheet) -->
    <BottomSheet
      v-if="session && isMobile"
      v-model="showTradePanel"
      title="模拟交易"
    >
      <PaperTradingPanel
        :portfolio="portfolio"
        :trades="trades"
        :current-price="currentPrice"
        @trade="handleTrade"
      />
    </BottomSheet>
    
    <!-- Progress Bar -->
    <div v-if="session && totalBars > 0" class="px-4 pb-4">
      <div
        class="relative h-2 bg-surface rounded-full overflow-hidden cursor-pointer"
        :class="{ 'h-3': isMobile }"
        @click="handleProgressClick"
        ref="progressBar"
      >
        <!-- Progress Fill -->
        <div
          class="absolute left-0 top-0 h-full bg-primary transition-all duration-100"
          :style="{ width: `${progressPct}%` }"
        />
        
        <!-- Draggable Cursor (48px touch target on mobile) -->
        <div
          class="absolute top-1/2 -translate-y-1/2 bg-white rounded-full shadow-md cursor-grab active:cursor-grabbing"
          :class="isMobile ? 'w-12 h-12 -translate-y-1/2' : 'w-3 h-3'"
          :style="isMobile ? { left: `calc(${progressPct}% - 24px)` } : { left: `calc(${progressPct}% - 6px)` }"
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
    
    <!-- Error State with Retry -->
    <div
      v-if="error && !session"
      class="fixed inset-0 flex items-center justify-center bg-glass z-50"
    >
      <div class="text-center max-w-md px-4">
        <svg class="w-16 h-16 text-danger mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        
        <h3 class="text-lg font-semibold text-primary mb-2">加载失败</h3>
        <p class="text-secondary text-sm mb-4">{{ error }}</p>
        
        <!-- Retry button with countdown -->
        <button
          v-if="canRetry"
          @click="handleRetry"
          :disabled="loading"
          class="px-6 py-2.5 bg-primary text-white rounded-lg text-sm font-medium
                 hover:bg-primary-hover transition-colors duration-200
                 disabled:opacity-50 disabled:cursor-not-allowed min-h-[44px]"
        >
          <span v-if="loading" class="flex items-center gap-2">
            <div class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
            重试中...
          </span>
          <span v-else>
            重试 (剩余 {{ 3 - retryCount }} 次)
          </span>
        </button>
        
        <!-- Max retries reached -->
        <p v-else class="text-yellow-400 text-sm">
          已达最大重试次数，请稍后手动刷新
        </p>
        
        <!-- Network status indicator -->
        <p v-if="!isOnline" class="text-danger text-xs mt-3">
          ⚠️ 当前处于离线状态
        </p>
      </div>
    </div>
    
    <!-- Error Toast (for non-critical errors during session) -->
    <div
      v-if="error && session"
      class="fixed bottom-4 right-4 px-4 py-3 bg-danger text-white rounded-lg shadow-theme-lg z-50"
    >
      {{ error }}
      <button @click="error = null" class="ml-3 opacity-70 hover:opacity-100">✕</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onDeactivated, onActivated, onUnmounted } from 'vue'
import { useBreakpoints, breakpointsTailwind } from '@vueuse/core'
import { useOrientation } from '@/composables/useOrientation.js'
import { useTimeMachine } from '@/composables/useTimeMachine.js'
import { useTimemachineNetwork } from '@/composables/useTimemachineNetwork.js'
import { useToast } from '@/composables/useToast.js'
import { useMarketStream } from '@/composables/useMarketStream.js'
import { buildChartData } from '@/utils/chartDataBuilder.js'
import { getFreshness } from '@/utils/freshness.js'
import BaseKLineChart from '@/components/BaseKLineChart.vue'
import PlaybackControls from '@/components/timemachine/PlaybackControls.vue'
import PaperTradingPanel from '@/components/timemachine/PaperTradingPanel.vue'
import BottomSheet from '@/components/BottomSheet.vue'

// Mobile detection
const breakpoints = useBreakpoints(breakpointsTailwind)
const isMobile = breakpoints.smaller('md') // < 768px

// Toast notification system
const toast = useToast()

// Orientation detection for landscape immersive mode
const { isLandscape, lockOrientation, unlockOrientation } = useOrientation()

// Mobile-specific state
const showTradePanel = ref(false)

// Date validation state
const dateError = ref(null)

// TimeMachine composable
const {
  session,
  loading,
  error,
  dataSource,
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

// Network status & retry mechanism
const {
  canRetry,
  retryCount,
  retryMessage,
  isOnline,
  incrementRetry,
  resetRetry,
  checkConnectivity
} = useTimemachineNetwork()

// WebSocket stream for real-time updates
const {
  timemachineEvents,
  subscribeTimemachine,
  unsubscribeTimemachine,
  wsStatus
} = useMarketStream()

// Current session ID for WebSocket subscription
const currentSessionId = computed(() => session.value?.id || null)

// Subscribe to session events when session changes
watch(currentSessionId, (newId, oldId) => {
  if (oldId) {
    unsubscribeTimemachine(oldId)
  }
  if (newId) {
    subscribeTimemachine(newId)
  }
}, { immediate: true })

// Handle real-time playback events
watch(() => timemachineEvents.value[currentSessionId.value], (events) => {
  if (!events || events.length === 0) return
  
  const latestEvent = events[events.length - 1]
  
  if (latestEvent.bar_index !== undefined) {
    currentBar.value = latestEvent.bar_index
  }
  
  if (latestEvent.bar) {
    klineData.value.push(latestEvent.bar)
  }
}, { deep: true })

// Cleanup on unmount
onUnmounted(() => {
  if (currentSessionId.value) {
    unsubscribeTimemachine(currentSessionId.value)
  }
})

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

// Data source status indicator (v0.6.220)
const dataSourceStatusColor = computed(() => {
  const type = dataSource.value?.source_type
  if (type === 'real') return 'text-bull'
  if (type === 'cache') return 'text-yellow-500'
  if (type === 'mock') return 'text-bear'
  return 'text-muted'
})

const dataSourceLabel = computed(() => {
  const type = dataSource.value?.source_type
  const labels = {
    real: '实时',
    cache: '缓存',
    mock: '模拟'
  }
  return labels[type] || '未知'
})

const dataSourceFreshness = computed(() => {
  if (!dataSource.value?.timestamp) return null
  return getFreshness(dataSource.value.timestamp)
})

// Initialize dates
onMounted(() => {
  const today = new Date()
  const oneYearAgo = new Date(today)
  oneYearAgo.setFullYear(today.getFullYear() - 1)
  
  endDate.value = today.toISOString().split('T')[0]
  startDate.value = oneYearAgo.toISOString().split('T')[0]
})

// Date range validation
function validateDateRange() {
  const start = new Date(startDate.value)
  const end = new Date(endDate.value)
  const today = new Date()
  today.setHours(23, 59, 59, 999) // End of today
  const minDataDate = new Date('2000-01-01')
  
  // Rule 1: Start before end
  if (start >= end) {
    dateError.value = '开始日期必须早于结束日期'
    toast.error('日期错误', dateError.value)
    return false
  }
  
  // Rule 2: Range <= 2 years
  const diffDays = (end - start) / (1000 * 60 * 60 * 24)
  if (diffDays > 730) {
    dateError.value = '日期范围不能超过2年'
    toast.error('日期错误', dateError.value)
    return false
  }
  
  // Rule 3: End <= today
  if (end > today) {
    dateError.value = '结束日期不能超过今天'
    toast.error('日期错误', dateError.value)
    return false
  }
  
  // Rule 4: Start >= 2000
  if (start < minDataDate) {
    dateError.value = '开始日期不能早于2000年'
    toast.error('日期错误', dateError.value)
    return false
  }
  
  dateError.value = null
  return true
}

// Create session with retry support
async function handleCreateSession() {
  if (!symbol.value || !startDate.value || !endDate.value) return
  
  // Validate date range before creating session
  if (!validateDateRange()) {
    return
  }
  
  // Check network connectivity
  if (!isOnline.value) {
    toast.error('网络错误', '当前处于离线状态，请检查网络连接')
    return
  }
  
  try {
    loading.value = true
    error.value = null
    
    // Reset retry count on new session creation
    resetRetry()
    
    await createSession(symbol.value, startDate.value, endDate.value, 1000000)
    
    // Success toast
    toast.success('创建成功', '复盘会话已创建，开始历史回放')
    
  } catch (e) {
    console.error('Failed to create session:', e)
    
    // User-friendly error messages based on error type
    const errorMsg = e.message || ''
    let userMessage = ''
    
    if (errorMsg.includes('timeout') || errorMsg.includes('TimeoutError')) {
      userMessage = '历史数据加载超时，请尝试缩短日期范围'
    } else if (errorMsg.includes('No data') || errorMsg.includes('Empty') || errorMsg.includes('empty')) {
      userMessage = '该日期范围内无历史数据，请调整日期'
    } else if (errorMsg.includes('network') || errorMsg.includes('fetch') || errorMsg.includes('NetworkError') || errorMsg.includes('ConnectionError')) {
      userMessage = '网络连接失败，请检查网络后重试'
    } else if (errorMsg.includes('coroutine') || errorMsg.includes('Internal Server Error')) {
      userMessage = '服务暂时不可用，请稍后重试'
    } else {
      userMessage = errorMsg || '复盘会话创建失败，请稍后重试'
    }
    
    error.value = userMessage
    
    // Auto retry with exponential backoff (if can retry and not network error)
    if (canRetry.value && !errorMsg.includes('network') && !errorMsg.includes('fetch') && !errorMsg.includes('NetworkError')) {
      const delayMs = 1000 * Math.pow(2, retryCount.value) // 1s, 2s, 4s
      
      toast.info('自动重试', `将在 ${delayMs / 1000}秒后自动重试...`)
      
      setTimeout(async () => {
        if (!canRetry.value) return
        
        incrementRetry()
        await handleRetry()
      }, delayMs)
    } else {
      toast.error('创建失败', userMessage)
    }
  } finally {
    loading.value = false
  }
}

// Manual retry handler
async function handleRetry() {
  if (!canRetry.value || loading.value) return
  
  incrementRetry()
  
  // Check connectivity first
  const connected = await checkConnectivity()
  if (!connected) {
    toast.error('连接失败', '服务仍然不可用，请稍后重试')
    return
  }
  
  // Attempt to create session again
  await handleCreateSession()
}

// End session
async function handleEndSession() {
  await endSession()
}

// Handle trade from PaperTradingPanel
async function handleTrade({ action, quantity }) {
  try {
    await executeTrade(action, quantity)
    toast.success('交易成功', `${action === 'buy' ? '买入' : '卖出'} ${quantity} 股`)
  } catch (e) {
    console.error('Trade failed:', e)
    
    const errorMsg = e.message || ''
    
    if (errorMsg.includes('insufficient')) {
      toast.error('交易失败', '资金不足，无法完成交易')
    } else if (errorMsg.includes('shares')) {
      toast.error('交易失败', '持仓不足，无法卖出')
    } else {
      toast.error('交易失败', errorMsg || '交易执行失败，请重试')
    }
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

// P0: KeepAlive cleanup
onDeactivated(() => {
  // End session to stop playback and free resources
  if (session.value) {
    endSession()
  }
  // Clear error state
  error.value = null
})

onActivated(() => {
  // Re-initialize dates if needed
  if (!startDate.value || !endDate.value) {
    const today = new Date()
    const oneYearAgo = new Date(today)
    oneYearAgo.setFullYear(today.getFullYear() - 1)
    
    endDate.value = today.toISOString().split('T')[0]
    startDate.value = oneYearAgo.toISOString().split('T')[0]
  }
})
</script>

<style scoped>
.landscape-immersive {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 100;
}
</style>