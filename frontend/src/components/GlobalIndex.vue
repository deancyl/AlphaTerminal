<template>
  <div class="h-full flex flex-col bg-terminal-bg overflow-hidden">
    <!-- 顶部标题栏 -->
    <div class="flex items-center justify-between px-4 py-2 border-b border-theme-secondary shrink-0">
      <div class="flex items-center gap-3">
        <span class="text-lg font-bold text-terminal-accent">🌍 全球指数</span>
        <span class="text-xs text-terminal-dim">全球主要市场指数监控</span>
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

    <!-- 分类标签 -->
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
      
      <!-- Data Grid -->
      <div 
        v-else 
        ref="indexGrid"
        class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3"
        tabindex="0"
        @keydown="handleKeydown"
      >
        <div
          v-for="(index, idx) in filteredIndexes"
          :key="index.symbol"
          :data-index="idx"
          class="bg-terminal-panel rounded-sm border p-4 transition cursor-pointer"
          :class="focusedIndex === idx 
            ? 'border-terminal-accent ring-1 ring-terminal-accent/30' 
            : 'border-theme-secondary hover:border-terminal-accent/30'"
          @click="selectIndex(index)"
          @mouseenter="focusedIndex = idx"
        >
          <div class="flex items-center justify-between mb-2">
            <div class="flex items-center gap-2">
              <span class="text-lg">{{ index.flag }}</span>
              <div>
                <div class="text-sm font-bold text-theme-primary">{{ index.name }}</div>
                <div class="text-[10px] text-theme-muted">{{ index.symbol }}</div>
              </div>
            </div>
            <div class="text-right">
              <div class="text-lg font-mono font-bold" :class="index.change_pct >= 0 ? 'text-bullish' : 'text-bearish'">
                {{ index.price?.toFixed(2) || '--' }}
              </div>
              <div class="text-xs font-mono" :class="index.change_pct >= 0 ? 'text-bullish' : 'text-bearish'">
                {{ index.change_pct >= 0 ? '+' : '' }}{{ index.change_pct?.toFixed(2) || '0.00' }}%
              </div>
            </div>
          </div>
          
          <!-- 迷你走势图 -->
          <div class="h-16 w-full">
            <svg viewBox="0 0 100 40" class="w-full h-full" preserveAspectRatio="none">
              <polyline
                :points="getSparkline(index.sparkline)"
                fill="none"
                :stroke="index.change_pct >= 0 ? 'var(--color-up)' : 'var(--color-down)'"
                stroke-width="1.5"
              />
            </svg>
          </div>
          
          <div class="flex justify-between mt-2 text-[10px] text-theme-muted">
            <span>开盘: {{ index.open?.toFixed(2) || '--' }}</span>
            <span>最高: {{ index.high?.toFixed(2) || '--' }}</span>
            <span>最低: {{ index.low?.toFixed(2) || '--' }}</span>
          </div>
        </div>
      </div>

      <!-- 选中指数的详细图表 -->
      <div v-if="selectedIndex" class="mt-4 rounded-sm border border-theme bg-terminal-panel p-4">
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center gap-2">
            <span class="text-xl">{{ selectedIndex.flag }}</span>
            <span class="text-lg font-bold text-terminal-accent">{{ selectedIndex.name }}</span>
          </div>
          <button class="text-theme-muted hover:text-terminal-accent" @click="selectedIndex = null">✕</button>
        </div>
        <div ref="detailChart" class="w-full h-[300px]"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { apiFetch } from '../utils/api.js'
import { logger } from '../utils/logger.js'
import LoadingSpinner from './f9/LoadingSpinner.vue'
import ErrorDisplay from './f9/ErrorDisplay.vue'
import EmptyState from './f9/EmptyState.vue'

const loading = ref(false)
const error = ref('')
const activeRegion = ref('all')
const selectedIndex = ref(null)
const detailChart = ref(null)
const indexGrid = ref(null)
const focusedIndex = ref(0)
let chart = null

const regions = [
  { id: 'all', name: '全部' },
  { id: 'americas', name: '美洲' },
  { id: 'europe', name: '欧洲' },
  { id: 'asia', name: '亚太' },
]

// 后端市场代码 → 前端区域映射
const marketRegionMap = {
  'US': 'americas',
  'HK': 'asia',
  'JP': 'asia',
}

// 全球主要指数列表（后端支持: SPX, DJI, IXIC, N225, HSI）
// 扩展支持更多全球指数
const allIndexes = ref([
  // 美洲
  { symbol: 'SPX', name: '标普500', flag: '🇺🇸', region: 'americas', price: 4200.00, change_pct: 0.85, open: 4165.00, high: 4210.00, low: 4160.00, sparkline: generateSparkline(4200, 0.85) },
  { symbol: 'IXIC', name: '纳斯达克', flag: '🇺🇸', region: 'americas', price: 14500.00, change_pct: 1.20, open: 14320.00, high: 14580.00, low: 14300.00, sparkline: generateSparkline(14500, 1.20) },
  { symbol: 'DJI', name: '道琼斯', flag: '🇺🇸', region: 'americas', price: 33500.00, change_pct: 0.45, open: 33350.00, high: 33600.00, low: 33300.00, sparkline: generateSparkline(33500, 0.45) },
  { symbol: 'RUT', name: '罗素2000', flag: '🇺🇸', region: 'americas', price: 1980.00, change_pct: 0.65, open: 1965.00, high: 1990.00, low: 1960.00, sparkline: generateSparkline(1980, 0.65) },
  { symbol: 'VIX', name: '波动率指数', flag: '🇺🇸', region: 'americas', price: 18.50, change_pct: -2.30, open: 19.00, high: 19.50, low: 18.20, sparkline: generateSparkline(18.50, -2.30) },
  { symbol: 'TSX', name: '多伦多综指', flag: '🇨🇦', region: 'americas', price: 21500.00, change_pct: 0.35, open: 21420.00, high: 21550.00, low: 21400.00, sparkline: generateSparkline(21500, 0.35) },
  { symbol: 'IBOV', name: '巴西博维斯帕', flag: '🇧🇷', region: 'americas', price: 125000.00, change_pct: 0.80, open: 124000.00, high: 125500.00, low: 123800.00, sparkline: generateSparkline(125000, 0.80) },
  
  // 欧洲
  { symbol: 'UKX', name: '富时100', flag: '🇬🇧', region: 'europe', price: 7800.00, change_pct: 0.30, open: 7775.00, high: 7820.00, low: 7760.00, sparkline: generateSparkline(7800, 0.30) },
  { symbol: 'DAX', name: '德国DAX', flag: '🇩🇪', region: 'europe', price: 16500.00, change_pct: 0.65, open: 16390.00, high: 16580.00, low: 16350.00, sparkline: generateSparkline(16500, 0.65) },
  { symbol: 'CAC', name: '法国CAC40', flag: '🇫🇷', region: 'europe', price: 7400.00, change_pct: 0.50, open: 7360.00, high: 7430.00, low: 7350.00, sparkline: generateSparkline(7400, 0.50) },
  { symbol: 'SMI', name: '瑞士SMI', flag: '🇨🇭', region: 'europe', price: 11200.00, change_pct: 0.25, open: 11170.00, high: 11230.00, low: 11150.00, sparkline: generateSparkline(11200, 0.25) },
  { symbol: 'IBEX', name: '西班牙IBEX35', flag: '🇪🇸', region: 'europe', price: 11500.00, change_pct: 0.40, open: 11450.00, high: 11550.00, low: 11420.00, sparkline: generateSparkline(11500, 0.40) },
  { symbol: 'FTSEMIB', name: '意大利富时MIB', flag: '🇮🇹', region: 'europe', price: 34500.00, change_pct: 0.55, open: 34300.00, high: 34600.00, low: 34250.00, sparkline: generateSparkline(34500, 0.55) },
  { symbol: 'AEX', name: '荷兰AEX', flag: '🇳🇱', region: 'europe', price: 780.00, change_pct: 0.35, open: 777.00, high: 785.00, low: 775.00, sparkline: generateSparkline(780, 0.35) },
  
  // 亚太
  { symbol: 'N225', name: '日经225', flag: '🇯🇵', region: 'asia', price: 32500.00, change_pct: 1.50, open: 32000.00, high: 32600.00, low: 31950.00, sparkline: generateSparkline(32500, 1.50) },
  { symbol: 'HSI', name: '恒生指数', flag: '🇭🇰', region: 'asia', price: 18500.00, change_pct: -0.80, open: 18650.00, high: 18700.00, low: 18450.00, sparkline: generateSparkline(18500, -0.80) },
  { symbol: 'SSEC', name: '上证指数', flag: '🇨🇳', region: 'asia', price: 3150.00, change_pct: 0.45, open: 3135.00, high: 3165.00, low: 3130.00, sparkline: generateSparkline(3150, 0.45) },
  { symbol: 'SZSE', name: '深证成指', flag: '🇨🇳', region: 'asia', price: 10500.00, change_pct: 0.65, open: 10430.00, high: 10550.00, low: 10420.00, sparkline: generateSparkline(10500, 0.65) },
  { symbol: 'CSI300', name: '沪深300', flag: '🇨🇳', region: 'asia', price: 3850.00, change_pct: 0.55, open: 3830.00, high: 3870.00, low: 3825.00, sparkline: generateSparkline(3850, 0.55) },
  { symbol: 'KS11', name: '韩国KOSPI', flag: '🇰🇷', region: 'asia', price: 2650.00, change_pct: 0.75, open: 2630.00, high: 2665.00, low: 2625.00, sparkline: generateSparkline(2650, 0.75) },
  { symbol: 'TWII', name: '台湾加权', flag: '🇹🇼', region: 'asia', price: 18500.00, change_pct: 0.40, open: 18430.00, high: 18550.00, low: 18420.00, sparkline: generateSparkline(18500, 0.40) },
  { symbol: 'AXJO', name: '澳洲标普200', flag: '🇦🇺', region: 'asia', price: 7600.00, change_pct: 0.30, open: 7580.00, high: 7630.00, low: 7570.00, sparkline: generateSparkline(7600, 0.30) },
  { symbol: 'NSEI', name: '印度NIFTY50', flag: '🇮🇳', region: 'asia', price: 22500.00, change_pct: 0.85, open: 22300.00, high: 22550.00, low: 22280.00, sparkline: generateSparkline(22500, 0.85) },
  { symbol: 'BSESN', name: '印度孟买SENSEX', flag: '🇮🇳', region: 'asia', price: 74000.00, change_pct: 0.80, open: 73500.00, high: 74200.00, low: 73400.00, sparkline: generateSparkline(74000, 0.80) },
  { symbol: 'STI', name: '新加坡海峡时报', flag: '🇸🇬', region: 'asia', price: 3350.00, change_pct: 0.25, open: 3340.00, high: 3365.00, low: 3335.00, sparkline: generateSparkline(3350, 0.25) },
  { symbol: 'JKSE', name: '印尼雅加达综指', flag: '🇮🇩', region: 'asia', price: 7200.00, change_pct: 0.45, open: 7170.00, high: 7230.00, low: 7160.00, sparkline: generateSparkline(7200, 0.45) },
  { symbol: 'SET', name: '泰国SET指数', flag: '🇹🇭', region: 'asia', price: 1380.00, change_pct: 0.35, open: 1375.00, high: 1390.00, low: 1372.00, sparkline: generateSparkline(1380, 0.35) },
])

const filteredIndexes = computed(() => {
  if (activeRegion.value === 'all') return allIndexes.value
  return allIndexes.value.filter(idx => idx.region === activeRegion.value)
})

// Reset focus when region changes
watch(activeRegion, () => {
  focusedIndex.value = 0
  nextTick(() => indexGrid.value?.focus())
})

// 生成模拟走势图数据
function generateSparkline(basePrice, changePct) {
  const points = []
  const volatility = Math.abs(changePct) * 0.5
  let current = basePrice * (1 - changePct / 100 * 0.5)
  
  for (let i = 0; i < 20; i++) {
    const change = (Math.random() - 0.5) * volatility * 2
    current = current * (1 + change / 100)
    points.push(current)
  }
  
  // 确保最后一个点接近实际价格
  points[points.length - 1] = basePrice
  return points
}

// 生成SVG路径
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

function selectIndex(index) {
  selectedIndex.value = index
  nextTick(() => renderDetailChart())
}

function renderDetailChart() {
  if (!detailChart.value || !selectedIndex.value) return
  
  if (chart) { chart.dispose(); chart = null }
  
  const index = selectedIndex.value
  const data = index.sparkline
  const dates = Array.from({ length: data.length }, (_, i) => {
    const d = new Date()
    d.setDate(d.getDate() - (data.length - 1 - i))
    return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
  })
  
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
}

async function refreshAll() {
  loading.value = true
  error.value = ''
  try {
    // 尝试从API获取实时数据
    const data = await apiFetch('/api/v1/market/global')
    if (data?.global) {
      // 更新已有数据
      data.global.forEach(update => {
        const idx = allIndexes.value.find(i => i.symbol === update.symbol)
        if (idx) {
          Object.assign(idx, {
            price: update.price,
            change_pct: update.change_pct,
            volume: update.volume,
            status: update.status,
          })
          idx.sparkline = generateSparkline(update.price, update.change_pct)
        }
      })
    }
  } catch (e) {
    logger.warn('[GlobalIndex] API fetch failed, using mock data:', e.message)
    error.value = '获取全球指数数据失败，显示模拟数据'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  refreshAll()
  window.addEventListener('resize', handleResize)
  // Focus grid for keyboard navigation
  nextTick(() => indexGrid.value?.focus())
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  if (chart) {
    chart.dispose()
    chart = null
  }
})

function handleResize() {
  chart?.resize()
}

// Keyboard navigation
function handleKeydown(e) {
  const total = filteredIndexes.value.length
  if (total === 0) return
  
  // Get grid columns based on viewport
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
  nextTick(() => {
    const el = indexGrid.value?.querySelector(`[data-index="${focusedIndex.value}"]`)
    el?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  })
}
</script>