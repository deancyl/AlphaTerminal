<template>
  <div class="h-full flex flex-col bg-terminal-bg overflow-hidden">
    <!-- 顶部标题栏 -->
    <div class="flex items-center justify-between px-4 py-2 border-b border-theme-secondary shrink-0">
      <div class="flex items-center gap-3">
        <span class="text-lg font-bold text-terminal-accent">🌍 全球指数</span>
        <span class="text-xs text-terminal-dim">全球主要市场指数监控</span>
        <span v-if="mockCount > 0" class="text-xs text-yellow-500">
          ({{ mockCount }}个模拟数据)
        </span>
      </div>
      <div class="flex items-center gap-2">
        <button 
          class="px-3 py-1.5 rounded-sm text-xs bg-terminal-accent/20 text-terminal-accent hover:bg-terminal-accent/30 transition"
          @click="refreshAll"
          :disabled="loading"
        >
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
      </div>
    </div>

    <!-- 区域树形导航 -->
    <div class="flex gap-2 px-4 py-2 border-b border-theme-secondary shrink-0">
      <button
        v-for="region in regions"
        :key="region.id"
        class="text-xs px-3 py-1 rounded-sm border transition"
        :class="activeRegion === region.id
          ? 'bg-terminal-accent/20 border-terminal-accent/50 text-terminal-accent'
          : 'bg-terminal-bg border-theme-secondary text-theme-tertiary hover:text-theme-primary'"
        @click="activeRegion = region.id"
      >
        {{ region.name }}
        <span class="ml-1 text-[10px] opacity-70">({{ getRegionCount(region.id) }})</span>
      </button>
    </div>

    <!-- 指数卡片网格 -->
    <div class="flex-1 overflow-y-auto p-4">
      <!-- Loading State -->
      <LoadingSpinner v-if="loading && allIndexes.length === 0" text="加载全球指数数据..." />
      
      <!-- Error State -->
      <ErrorDisplay 
        v-else-if="error && allIndexes.length === 0" 
        :error="error" 
        :retry="refreshAll" 
      />
      
      <!-- Empty State -->
      <EmptyState 
        v-else-if="!loading && filteredIndexes.length === 0" 
        icon="🌍" 
        message="暂无指数数据" 
        hint="请检查网络连接或稍后重试" 
      />
      
      <!-- P1-8: Virtual scrolling for performance with 20+ indices -->
      <VirtualizedTable
        v-else
        ref="indexTable"
        :items="filteredIndexes"
        :columns="indexColumns"
        :item-size="100"
        :selected-id="selectedIndex?.symbol"
        @row-click="handleRowClick"
        @keydown="handleKeydown"
      >
        <template #cell-flag="{ item }">
          <span class="text-lg">{{ item.flag }}</span>
        </template>
        <template #cell-name="{ item }">
          <div>
            <div class="text-sm font-bold text-theme-primary">
              {{ item.name }}
              <span v-if="item.is_mock" class="text-[10px] text-yellow-500 ml-1">(模拟)</span>
            </div>
            <div class="text-[10px] text-theme-muted">{{ item.symbol }}</div>
          </div>
        </template>
        <template #cell-price="{ item }">
          <div class="text-right">
            <div class="text-lg font-mono font-bold" :class="item.change_pct >= 0 ? 'text-bullish' : 'text-bearish'">
              {{ item.price?.toFixed(2) || '--' }}
            </div>
            <div class="text-xs font-mono" :class="item.change_pct >= 0 ? 'text-bullish' : 'text-bearish'">
              {{ item.change_pct >= 0 ? '+' : '' }}{{ item.change_pct?.toFixed(2) || '0.00' }}%
            </div>
          </div>
        </template>
        <!-- P2-10: Error state UI for sparkline -->
        <template #cell-sparkline="{ item }">
          <div class="h-16 w-full flex items-center justify-center">
            <!-- Error state -->
            <div v-if="item.sparklineError" class="flex flex-col items-center gap-1">
              <p class="text-[10px] text-red-400">{{ item.sparklineError?.message || '加载失败' }}</p>
              <button
                class="text-[10px] px-2 py-0.5 rounded bg-red-500/20 text-red-400 hover:bg-red-500/30 transition"
                @click.stop="retrySparkline(item)"
              >
                重试
              </button>
            </div>
            <!-- Success state -->
            <svg v-else viewBox="0 0 100 40" class="w-full h-full" preserveAspectRatio="none">
              <polyline
                v-if="item.sparkline && item.sparkline.length > 1"
                :points="getSparkline(item.sparkline)"
                fill="none"
                :stroke="item.change_pct >= 0 ? 'var(--color-up)' : 'var(--color-down)'"
                stroke-width="1.5"
              />
              <text v-else x="50" y="20" text-anchor="middle" fill="#666" font-size="10">加载中...</text>
            </svg>
          </div>
        </template>
        <template #cell-details="{ item }">
          <div class="flex justify-between text-[10px] text-theme-muted">
            <span>开: {{ item.open?.toFixed(2) || '--' }}</span>
            <span>高: {{ item.high?.toFixed(2) || '--' }}</span>
            <span>低: {{ item.low?.toFixed(2) || '--' }}</span>
          </div>
        </template>
      </VirtualizedTable>

      <!-- 选中指数的详细图表 -->
      <div v-if="selectedIndex" class="mt-4 rounded-sm border border-theme bg-terminal-panel p-4">
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center gap-2">
            <span class="text-xl">{{ selectedIndex.flag }}</span>
            <span class="text-lg font-bold text-terminal-accent">{{ selectedIndex.name }}</span>
            <span class="text-xs text-theme-muted">({{ selectedIndex.symbol }})</span>
          </div>
          <button class="text-theme-muted hover:text-terminal-accent" @click="selectedIndex = null">✕</button>
        </div>
        <div ref="detailChart" class="w-full h-[300px]"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, shallowRef, computed, onMounted, onBeforeUnmount, onActivated, onDeactivated, nextTick, watch } from 'vue'
import { apiFetch } from '../utils/api.js'
import { logger } from '../utils/logger.js'
import LoadingSpinner from './f9/LoadingSpinner.vue'
import ErrorDisplay from './f9/ErrorDisplay.vue'
import EmptyState from './f9/EmptyState.vue'
import VirtualizedTable from './VirtualizedTable.vue'

const loading = ref(false)
const error = ref('')
const activeRegion = ref('all')
const selectedIndex = ref(null)
const detailChart = ref(null)
const indexTable = ref(null)
const focusedIndex = ref(0)
let chart = null
let abortController = null // AbortController for request cancellation

// P1-8: VirtualizedTable columns for performance with 20+ indices
const indexColumns = [
  { key: 'flag', label: '地区', width: '50px', sortable: false },
  { key: 'name', label: '指数', width: '150px', sortable: true },
  { key: 'price', label: '价格/涨跌', width: '120px', align: 'right', sortable: true },
  { key: 'sparkline', label: '走势', width: '100px', sortable: false },
  { key: 'details', label: 'OHLC', width: '120px', sortable: false }
]

// localStorage cache key and TTL (5 minutes)
// CACHE_VERSION: Increment when data format changes to invalidate old cache
const CACHE_KEY = 'alphaterminal_global_indexes'
const CACHE_VERSION = 3  // v3: include sparklines in cache
const CACHE_TTL = 5 * 60 * 1000

const regions = [
  { id: 'all', name: '全部' },
  { id: 'Americas', name: '美洲' },
  { id: 'Europe', name: '欧洲' },
  { id: 'Asia-Pacific', name: '亚太' },
]

// P0-4: Use shallowRef for large data arrays to prevent deep reactivity overhead
const allIndexes = shallowRef([])
const regionData = shallowRef({})

const mockCount = computed(() => allIndexes.value.filter(i => i.is_mock).length)

const filteredIndexes = computed(() => {
  if (activeRegion.value === 'all') return allIndexes.value
  return allIndexes.value.filter(idx => {
    const symbolRegion = Object.entries(regionData.value).find(([_, symbols]) => 
      symbols.includes(idx.symbol)
    )?.[0]
    return symbolRegion === activeRegion.value
  })
})

function getRegionCount(regionId) {
  if (regionId === 'all') return allIndexes.value.length
  return regionData.value[regionId]?.length || 0
}

watch(activeRegion, () => {
  focusedIndex.value = 0
  nextTick(() => indexTable.value?.focus())
})

function getSparkline(data) {
  if (!data || data.length < 2) return ''
  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1
  
  return data.map((val, i) => {
    const x = (i / (data.length - 1)) * 100
    const y = 40 - ((val - min) / range) * 35 - 2.5
    return `${x},${y}`
  }).join(' ')
}

// P2-10: Retry sparkline fetch for individual index
async function retrySparkline(index) {
  if (!index || index.is_mock) return
  
  // Clear error state
  index.sparklineError = null
  
  try {
    const sparkResp = await apiFetch(`/api/v1/market/global/sparkline?symbol=${index.symbol}&days=20`, {
      timeoutMs: 5000
    })
    index.sparkline = sparkResp?.data?.data || []
  } catch (e) {
    index.sparklineError = {
      message: '数据加载失败',
      error: e
    }
    index.sparkline = []
  }
}

async function selectIndex(index) {
  selectedIndex.value = index
  await nextTick()
  await new Promise(resolve => requestAnimationFrame(resolve))
  await new Promise(resolve => requestAnimationFrame(resolve))
  await renderDetailChart()
}

// P1-8: VirtualizedTable row click handler
function handleRowClick(item) {
  if (item) {
    selectIndex(item)
  }
}

async function renderDetailChart() {
  if (!detailChart.value || !selectedIndex.value) return
  
  if (chart) { chart.dispose(); chart = null }
  
  const index = selectedIndex.value
  
  try {
    const resp = await apiFetch(`/api/v1/market/global/kline?symbol=${index.symbol}&period=daily&limit=60`)
    const klines = resp?.data || []
    
    if (!klines.length) {
      logger.warn(`[GlobalIndex] No kline data for ${index.symbol}`)
      return
    }
    
    const data = klines.map(k => k.close)
    const dates = klines.map(k => k.date)
    
    const primaryColor = getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim() || '#0F52BA'
    const chartTextColor = getComputedStyle(document.documentElement).getPropertyValue('--chart-text').trim() || '#8B949E'
    
    chart = window.echarts.init(detailChart.value, 'dark')
    chart.setOption({
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#1e2130', borderColor: '#374151',
        textStyle: { color: '#d1d5db', fontSize: 10 },
      },
      grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
      xAxis: {
        type: 'category',
        data: dates,
        axisLabel: { color: chartTextColor, fontSize: 10 }
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: chartTextColor, fontSize: 10 }
      },
      series: [{
        type: 'line',
        data: data.map(d => d.toFixed(2)),
        smooth: true,
        lineStyle: { color: primaryColor, width: 2 },
        itemStyle: { color: primaryColor },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: primaryColor + '4D' },
              { offset: 1, color: primaryColor + '0D' }
            ]
          }
        }
      }]
    })
    chart.resize()
  } catch (e) {
    logger.error(`[GlobalIndex] Failed to render chart: ${e.message}`)
  }
}

// Load from localStorage cache
function loadFromCache() {
  try {
    const cached = localStorage.getItem(CACHE_KEY)
    if (cached) {
      const { data, timestamp, regions: cachedRegions, version } = JSON.parse(cached)
      // Invalidate cache if version mismatch or data is empty
      if (version !== CACHE_VERSION) {
        logger.info('[GlobalIndex] Cache version mismatch, invalidating')
        localStorage.removeItem(CACHE_KEY)
        return false
      }
      if (Date.now() - timestamp < CACHE_TTL && data && data.length > 0) {
        allIndexes.value = data
        regionData.value = cachedRegions || {}
        logger.info('[GlobalIndex] Loaded from cache:', data.length, 'indexes')
        return true
      }
    }
  } catch (e) {
    logger.warn('[GlobalIndex] Cache load error:', e.message)
  }
  return false
}

// Save to localStorage cache
function saveToCache(data, regions) {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify({
      data,
      regions,
      timestamp: Date.now(),
      version: CACHE_VERSION
    }))
  } catch (e) {
    logger.warn('[GlobalIndex] Cache save error:', e.message)
  }
}

async function refreshAll() {
  // Cancel previous request
  if (abortController) {
    abortController.abort()
  }
  abortController = new AbortController()
  
  loading.value = true
  error.value = ''
  try {
    const data = await apiFetch('/api/v1/market/global', { 
      timeoutMs: 8000, // 8 second timeout
      signal: abortController.signal 
    })
    if (data?.global) {
      // Create a copy of the data to modify
      const indexes = [...data.global]
      regionData.value = data.regions || {}
      
      // Fetch sparklines for each index
      const sparklinePromises = indexes.map(async (idx) => {
        if (!idx.is_mock) {
          try {
            const sparkResp = await apiFetch(`/api/v1/market/global/sparkline?symbol=${idx.symbol}&days=20`, {
              timeoutMs: 5000,
              signal: abortController.signal
            })
            idx.sparkline = sparkResp?.data?.data || []
          } catch (e) {
            if (e.name !== 'AbortError') {
              idx.sparkline = []
            }
          }
        } else {
          idx.sparkline = generateMockSparkline(idx.price, idx.change_pct)
        }
      })
      
      await Promise.all(sparklinePromises)
      
      // Assign the modified array to trigger reactivity
      allIndexes.value = indexes
      
      // Save to cache WITH sparklines for offline fallback
      saveToCache(indexes, data.regions || {})
    }
  } catch (e) {
    if (e.name === 'AbortError') {
      logger.info('[GlobalIndex] Request aborted')
      return
    }
    logger.warn('[GlobalIndex] API fetch failed:', e.message)
    
    // Try to load from cache on error
    if (!loadFromCache()) {
      error.value = '获取全球指数数据失败，请检查网络连接'
    }
  } finally {
    loading.value = false
    abortController = null
  }
}

function generateMockSparkline(basePrice, changePct) {
  const points = []
  const volatility = Math.abs(changePct) * 0.5
  let current = basePrice * (1 - changePct / 100 * 0.5)
  
  for (let i = 0; i < 20; i++) {
    const change = (Math.random() - 0.5) * volatility * 2
    current = current * (1 + change / 100)
    points.push(current)
  }
  
  points[points.length - 1] = basePrice
  return points
}

onMounted(() => {
  // Try to load from cache first for instant display
  if (!loadFromCache()) {
    refreshAll()
  } else {
    // Refresh in background after showing cached data
    setTimeout(() => refreshAll(), 1000)
  }
  window.addEventListener('resize', handleResize)
  nextTick(() => indexTable.value?.focus())
})

onBeforeUnmount(() => {
  // Cancel pending requests
  if (abortController) {
    abortController.abort()
    abortController = null
  }
  window.removeEventListener('resize', handleResize)
  if (chart) {
    chart.dispose()
    chart = null
  }
})

// v0.6.70: KeepAlive lifecycle - prevent white screen on tab switch
onDeactivated(() => {
  if (abortController) {
    abortController.abort()
    abortController = null
  }
  window.removeEventListener('resize', handleResize)
  if (chart) {
    chart.dispose()
    chart = null
  }
})

onActivated(() => {
  window.addEventListener('resize', handleResize)
  window.dispatchEvent(new Event('resize'))
  if (!loadFromCache()) {
    refreshAll()
  }
})

function handleResize() {
  chart?.resize()
}

function handleKeydown(e) {
  const total = filteredIndexes.value.length
  if (total === 0) return
  
  const cols = window.innerWidth >= 1024 ? 3 : window.innerWidth >= 768 ? 2 : 1
  
  switch (e.key) {
    case 'ArrowDown':
      e.preventDefault()
      focusedIndex.value = Math.min(focusedIndex.value + cols, total - 1)
      scrollToFocused()
      break
    case 'ArrowUp':
      e.preventDefault()
      focusedIndex.value = Math.max(focusedIndex.value - cols, 0)
      scrollToFocused()
      break
    case 'ArrowRight':
      e.preventDefault()
      focusedIndex.value = Math.min(focusedIndex.value + 1, total - 1)
      scrollToFocused()
      break
    case 'ArrowLeft':
      e.preventDefault()
      focusedIndex.value = Math.max(focusedIndex.value - 1, 0)
      scrollToFocused()
      break
    case 'Enter':
    case ' ':
      e.preventDefault()
      if (filteredIndexes.value[focusedIndex.value]) {
        selectIndex(filteredIndexes.value[focusedIndex.value])
      }
      break
    case 'Escape':
      selectedIndex.value = null
      break
  }
}

function scrollToFocused() {
  // P1-8: VirtualizedTable handles scrolling internally
  // This function is kept for compatibility but no longer needed
}
</script>
