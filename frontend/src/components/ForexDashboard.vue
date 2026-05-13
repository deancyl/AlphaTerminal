<template>
  <div class="h-full flex flex-col bg-terminal-bg overflow-hidden" role="region" aria-label="外汇行情面板">
    <!-- 顶部标题栏 -->
    <div class="flex-shrink-0 flex items-center justify-between px-4 py-3 border-b border-theme-secondary">
      <div class="flex items-center gap-3">
        <span class="text-lg font-bold text-terminal-accent" role="heading" aria-level="2">💱 外汇行情</span>
        <span class="text-xs text-terminal-dim hidden sm:inline">主要货币对</span>
      </div>
      <div class="flex items-center gap-2">
        <span v-if="lastUpdate" class="text-xs text-terminal-dim hidden md:inline" aria-live="polite">
          更新于 {{ formatTime(lastUpdate) }}
        </span>
        <button 
          class="px-4 py-2 rounded-sm text-xs bg-terminal-accent/20 text-terminal-accent hover:bg-terminal-accent/30 transition disabled:opacity-50"
          style="min-width: 44px; min-height: 44px;"
          @click="fetchData"
          :disabled="loading"
          aria-label="刷新外汇数据"
          aria-busy="loading"
        >
          {{ loading ? '...' : '刷新' }}
        </button>
      </div>
    </div>

    <!-- 主内容区域 -->
    <div class="flex-1 overflow-y-auto p-3 md:p-4">
      <!-- 错误提示 -->
      <div v-if="error" class="bg-bearish/10 border border-bearish/30 rounded-lg p-4 flex items-center justify-between mb-4">
        <div class="flex items-center gap-2">
          <span class="text-bearish">⚠️</span>
          <span class="text-sm text-bearish">{{ error }}</span>
        </div>
        <button 
          @click="fetchData" 
          class="px-3 py-1 bg-bearish/20 text-bearish rounded-sm text-xs hover:bg-bearish/30 transition"
        >
          重试
        </button>
      </div>

      <!-- 骨架加载器 -->
      <div v-if="loading && !forexData.length && !error" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        <div v-for="i in 6" :key="i" class="bg-terminal-panel rounded-lg border border-theme-secondary p-4 animate-pulse">
          <div class="flex items-center justify-between mb-3">
            <div class="h-4 w-20 bg-terminal-bg/50 rounded"></div>
            <div class="h-3 w-12 bg-terminal-bg/50 rounded"></div>
          </div>
          <div class="h-8 w-24 bg-terminal-bg/50 rounded mb-2"></div>
          <div class="h-3 w-16 bg-terminal-bg/50 rounded"></div>
        </div>
      </div>

      <!-- 外汇卡片网格 -->
      <div v-else-if="forexData.length > 0" class="space-y-4">
        <!-- 货币转换器 -->
        <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
          <h3 class="text-sm font-bold text-terminal-accent mb-3">💱 货币转换</h3>
          <div class="flex flex-col sm:flex-row gap-2 items-stretch sm:items-center">
            <input 
              type="number" 
              v-model.number="convertAmount" 
              class="flex-1 sm:flex-none sm:w-28 px-3 py-2 bg-terminal-bg border border-theme-secondary rounded-sm text-terminal-primary text-sm focus:outline-none focus:border-terminal-accent"
              style="min-height: 44px;"
              placeholder="金额"
              min="0"
              step="0.01"
            />
            <select 
              v-model="fromCurrency" 
              class="flex-1 sm:flex-none px-3 py-2 bg-terminal-bg border border-theme-secondary rounded-sm text-terminal-primary text-sm focus:outline-none focus:border-terminal-accent"
              style="min-height: 44px;"
            >
              <option v-for="c in currencies" :key="c" :value="c">{{ c }}</option>
            </select>
            <div class="flex items-center justify-center">
              <SwapButton @swap="swapCurrencies" />
            </div>
            <select 
              v-model="toCurrency" 
              class="flex-1 sm:flex-none px-3 py-2 bg-terminal-bg border border-theme-secondary rounded-sm text-terminal-primary text-sm focus:outline-none focus:border-terminal-accent"
              style="min-height: 44px;"
            >
              <option v-for="c in currencies" :key="c" :value="c">{{ c }}</option>
            </select>
            <button 
              @click="convert" 
              class="px-4 py-2 rounded-sm text-sm bg-terminal-accent/20 text-terminal-accent hover:bg-terminal-accent/30 transition disabled:opacity-50"
              style="min-width: 44px; min-height: 44px;"
              :disabled="converting"
            >
              {{ converting ? '...' : '转换' }}
            </button>
          </div>
          <div v-if="convertResult !== null" class="mt-3 text-lg font-bold text-terminal-primary">
            {{ convertAmount }} {{ fromCurrency }} = <span class="text-terminal-accent">{{ convertResult.toFixed(4) }}</span> {{ toCurrency }}
          </div>
          <div v-if="convertError" class="mt-2 text-xs text-bearish">{{ convertError }}</div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          <div 
            v-for="(item, index) in forexData" 
            :key="index"
            class="bg-terminal-panel rounded-lg border border-theme-secondary p-4 hover:border-terminal-accent/50 transition-colors cursor-pointer"
            :class="{ 'ring-2 ring-terminal-accent': selectedPair === item.symbol }"
            @click="selectPair(item)"
          >
            <div class="flex items-center justify-between mb-2">
              <span class="text-sm font-bold text-terminal-accent">{{ item.name }}</span>
              <span class="text-[10px] text-terminal-dim">{{ item.date || '--' }}</span>
            </div>
            <div class="flex items-baseline gap-2 mb-2">
              <span class="text-2xl font-bold text-terminal-primary">{{ formatPrice(item.middle_rate || item.buy_rate) }}</span>
              <span class="text-xs text-terminal-dim">CNY</span>
            </div>
            <div class="flex items-center gap-2">
              <span 
                class="text-sm font-medium"
                :class="getChangeClass(item.change_pct)"
              >
                {{ item.change_pct >= 0 ? '+' : '' }}{{ item.change_pct?.toFixed(4) || '0.00' }}%
              </span>
              <span class="text-[10px] text-terminal-dim">较昨日</span>
            </div>
            <div class="mt-2 text-[10px] text-terminal-dim flex justify-between">
              <span>买入: {{ item.buy_rate?.toFixed(4) || '--' }}</span>
              <span>卖出: {{ item.sell_rate?.toFixed(4) || '--' }}</span>
            </div>
          </div>
        </div>

        <!-- 趋势图 -->
        <div v-if="selectedPair" class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
          <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-3 gap-2">
            <h3 class="text-sm font-bold text-terminal-accent">📈 {{ getPairName(selectedPair) }} 趋势</h3>
            <div class="flex items-center gap-2">
              <!-- 时间范围选择器 -->
              <div class="flex gap-1">
                <button 
                  v-for="range in [7, 30, 90, 365]" 
                  :key="range"
                  :class="['px-3 py-2 rounded-sm text-xs transition', selectedDays === range ? 'bg-terminal-accent text-white' : 'bg-terminal-bg/50 text-terminal-dim hover:bg-terminal-accent/20']"
                  style="min-width: 44px; min-height: 44px;"
                  @click="selectedDays = range; fetchHistory()"
                >
                  {{ range }}天
                </button>
              </div>
            </div>
          </div>
          
          <!-- 图表类型切换 -->
          <div class="flex gap-2 mb-3">
            <button 
              :class="['px-4 py-2 rounded-sm text-xs transition', chartType === 'line' ? 'bg-terminal-accent text-white' : 'bg-terminal-bg/50 text-terminal-dim hover:bg-terminal-accent/20']"
              style="min-width: 44px; min-height: 44px;"
              @click="chartType = 'line'; drawChartFromData()"
            >
              折线图
            </button>
            <button 
              :class="['px-4 py-2 rounded-sm text-xs transition', chartType === 'candlestick' ? 'bg-terminal-accent text-white' : 'bg-terminal-bg/50 text-terminal-dim hover:bg-terminal-accent/20']"
              style="min-width: 44px; min-height: 44px;"
              @click="chartType = 'candlestick'; drawChartFromData()"
            >
              K线图
            </button>
          </div>
          
          <div ref="trendChartRef" class="h-[200px] sm:h-[250px]"></div>
        </div>

        <!-- 货币对比视图 -->
        <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
          <h3 class="text-sm font-bold text-terminal-accent mb-3">📊 货币对比</h3>
          <div class="flex flex-col sm:flex-row gap-2 items-stretch sm:items-center mb-3">
            <select 
              v-model="compareCurrency1" 
              class="flex-1 sm:flex-none px-3 py-2 bg-terminal-bg border border-theme-secondary rounded-sm text-terminal-primary text-sm focus:outline-none focus:border-terminal-accent"
              style="min-height: 44px;"
            >
              <option v-for="c in currencies" :key="c" :value="c">{{ c }}</option>
            </select>
            <span class="text-terminal-dim text-center">vs</span>
            <select 
              v-model="compareCurrency2" 
              class="flex-1 sm:flex-none px-3 py-2 bg-terminal-bg border border-theme-secondary rounded-sm text-terminal-primary text-sm focus:outline-none focus:border-terminal-accent"
              style="min-height: 44px;"
            >
              <option v-for="c in currencies" :key="c" :value="c">{{ c }}</option>
            </select>
            <button 
              @click="fetchComparison" 
              class="px-4 py-2 rounded-sm text-sm bg-terminal-accent/20 text-terminal-accent hover:bg-terminal-accent/30 transition disabled:opacity-50"
              style="min-width: 44px; min-height: 44px;"
              :disabled="comparing"
            >
              {{ comparing ? '...' : '对比' }}
            </button>
          </div>
          <div ref="comparisonChartRef" class="h-[200px] sm:h-[250px]"></div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-else-if="!error" class="flex flex-col items-center justify-center h-full text-terminal-dim">
        <span class="text-4xl mb-4">💱</span>
        <p class="text-sm">暂无外汇数据</p>
        <button @click="fetchData" class="mt-4 px-4 py-2 rounded-sm text-xs bg-terminal-accent/20 text-terminal-accent hover:bg-terminal-accent/30">
          刷新数据
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { apiFetch } from '../utils/api.js'
import { useApiError } from '../composables/useApiError.js'
import SwapButton from './mobile/SwapButton.vue'

const { handleError } = useApiError({ showToast: false })

const loading = ref(false)
const error = ref(null)
const lastUpdate = ref(null)
const forexData = ref([])
const selectedPair = ref(null)
const trendChartRef = ref(null)
const comparisonChartRef = ref(null)
let trendChartInstance = null
let comparisonChartInstance = null

// Currency converter
const convertAmount = ref(100)
const fromCurrency = ref('USD')
const toCurrency = ref('CNY')
const convertResult = ref(null)
const convertError = ref(null)
const converting = ref(false)
const currencies = ['USD', 'EUR', 'GBP', 'JPY', 'HKD', 'AUD', 'CNY']

// Time range selector
const selectedDays = ref(30)
const timeRanges = [7, 30, 90, 365]

// Chart type toggle
const chartType = ref('line')

// Comparison view
const compareCurrency1 = ref('USD')
const compareCurrency2 = ref('EUR')
const comparing = ref(false)
const comparisonData1 = ref([])
const comparisonData2 = ref([])

// History data cache
const currentHistory = ref([])

const pairNames = {
  'USD/CNY': '美元/人民币',
  'EUR/CNY': '欧元/人民币',
  'GBP/CNY': '英镑/人民币',
  'JPY/CNY': '日元/人民币',
  'HKD/CNY': '港币/人民币',
  'AUD/CNY': '澳元/人民币',
}

async function fetchData() {
  loading.value = true
  error.value = null
  
  try {
    const res = await apiFetch('/api/v1/forex/quotes', { timeoutMs: 30000 })
    
    if (res?.quotes) {
      forexData.value = res.quotes
      lastUpdate.value = new Date().toISOString()
      
      if (!selectedPair.value && forexData.value.length > 0) {
        selectedPair.value = forexData.value[0].symbol
        await nextTick()
        await fetchHistory()
      }
    }
  } catch (e) {
    const { userMessage } = handleError(e, { context: '外汇数据' })
    error.value = userMessage || '获取外汇数据失败'
  } finally {
    loading.value = false
  }
}

async function fetchHistory() {
  if (!selectedPair.value) return
  
  try {
    const res = await apiFetch(`/api/v1/forex/history/${selectedPair.value.replace('/', '')}?days=${selectedDays.value}`, { timeoutMs: 30000 })
    
    if (res?.history) {
      currentHistory.value = res.history
      await nextTick()
      drawChartFromData()
    }
  } catch (e) {
    handleError(e, { context: '外汇历史数据', silent: true })
  }
}

async function fetchComparison() {
  if (compareCurrency1.value === compareCurrency2.value) return
  
  comparing.value = true
  try {
    // Fetch both currencies in parallel
    const [res1, res2] = await Promise.all([
      apiFetch(`/api/v1/forex/history/${compareCurrency1.value}CNY?days=${selectedDays.value}`, { timeoutMs: 30000 }),
      apiFetch(`/api/v1/forex/history/${compareCurrency2.value}CNY?days=${selectedDays.value}`, { timeoutMs: 30000 })
    ])
    
    comparisonData1.value = res1?.history || []
    comparisonData2.value = res2?.history || []
    
    await nextTick()
    drawComparisonChart()
  } catch (e) {
    handleError(e, { context: '外汇对比数据', silent: true })
  } finally {
    comparing.value = false
  }
}

async function selectPair(pair) {
  selectedPair.value = pair.symbol
  await fetchHistory()
}

async function convert() {
  if (!convertAmount.value || convertAmount.value <= 0) {
    convertError.value = '请输入有效金额'
    convertResult.value = null
    return
  }
  
  if (fromCurrency.value === toCurrency.value) {
    convertResult.value = convertAmount.value
    convertError.value = null
    return
  }
  
  converting.value = true
  convertError.value = null
  
  try {
    const res = await apiFetch(`/api/v1/forex/convert?amount=${convertAmount.value}&from_currency=${fromCurrency.value}&to_currency=${toCurrency.value}`, { timeoutMs: 30000 })
    
    if (res?.result !== undefined) {
      convertResult.value = res.result
      convertError.value = null
    }
  } catch (e) {
    const { userMessage } = handleError(e, { context: '货币转换', silent: true })
    convertError.value = userMessage || '转换失败'
    convertResult.value = null
  } finally {
    converting.value = false
  }
}

function swapCurrencies() {
  const temp = fromCurrency.value
  fromCurrency.value = toCurrency.value
  toCurrency.value = temp
  // Re-convert if there's a result
  if (convertResult.value !== null) {
    convert()
  }
}

function getPairName(symbol) {
  return pairNames[symbol] || symbol
}

function getChartColors() {
  return {
    primary: getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim() || '#0F52BA',
    secondary: '#50C878',
    text: getComputedStyle(document.documentElement).getPropertyValue('--chart-text').trim() || '#8B949E',
  }
}

function drawChartFromData() {
  const echarts = window.echarts
  if (!echarts || !trendChartRef.value) return
  
  if (!trendChartInstance) {
    trendChartInstance = echarts.init(trendChartRef.value)
  }
  
  const colors = getChartColors()
  const history = currentHistory.value
  
  if (!history || history.length === 0) return
  
  const dates = history.map(d => d.date)
  
  if (chartType.value === 'candlestick') {
    // For candlestick, we need OHLC data - generate from rate
    const ohlcData = history.map(d => {
      const base = d.rate || 0
      const variation = base * 0.002 // small variation for visual
      return [base - variation, base + variation, base - variation, base + variation]
    })
    
    trendChartInstance.setOption({
      tooltip: { 
        trigger: 'axis',
        backgroundColor: 'rgba(15, 23, 42, 0.95)',
        borderColor: colors.primary,
        textStyle: { color: '#E5E7EB', fontSize: 12 },
        formatter: (params) => {
          const data = params[0]
          return `${data.name}<br/>开: <strong>${data.value[0].toFixed(4)}</strong><br/>高: <strong>${data.value[1].toFixed(4)}</strong><br/>低: <strong>${data.value[2].toFixed(4)}</strong><br/>收: <strong>${data.value[3].toFixed(4)}</strong>`
        }
      },
      grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
      xAxis: { 
        type: 'category', 
        data: dates,
        axisLabel: { color: colors.text, fontSize: 10, rotate: 45 },
        axisLine: { lineStyle: { color: colors.text + '40' } }
      },
      yAxis: { 
        type: 'value',
        axisLabel: { color: colors.text, fontSize: 10 },
        axisLine: { lineStyle: { color: colors.text + '40' } },
        splitLine: { lineStyle: { color: colors.text + '20' } }
      },
      series: [{
        name: 'K线',
        type: 'candlestick',
        data: ohlcData,
        itemStyle: { color: '#50C878', color0: '#FF6B6B', borderColor: '#50C878', borderColor0: '#FF6B6B' }
      }]
    })
  } else {
    // Line chart
    trendChartInstance.setOption({
      tooltip: { 
        trigger: 'axis',
        backgroundColor: 'rgba(15, 23, 42, 0.95)',
        borderColor: colors.primary,
        textStyle: { color: '#E5E7EB', fontSize: 12 },
        formatter: (params) => {
          const data = params[0]
          return `${data.name}<br/>汇率: <strong>${data.value}</strong>`
        }
      },
      grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
      xAxis: { 
        type: 'category', 
        data: dates,
        axisLabel: { color: colors.text, fontSize: 10, rotate: 45 },
        axisLine: { lineStyle: { color: colors.text + '40' } }
      },
      yAxis: { 
        type: 'value',
        axisLabel: { color: colors.text, fontSize: 10 },
        axisLine: { lineStyle: { color: colors.text + '40' } },
        splitLine: { lineStyle: { color: colors.text + '20' } }
      },
      series: [{
        name: getPairName(selectedPair.value),
        type: 'line',
        data: history.map(d => d.rate),
        smooth: true,
        symbol: 'circle',
        symbolSize: 4,
        lineStyle: { color: colors.primary, width: 2 },
        itemStyle: { color: colors.primary },
        areaStyle: { 
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: colors.primary + '40' },
              { offset: 1, color: colors.primary + '10' }
            ]
          }
        }
      }]
    })
  }
}

function drawComparisonChart() {
  const echarts = window.echarts
  if (!echarts || !comparisonChartRef.value) return
  
  if (!comparisonChartInstance) {
    comparisonChartInstance = echarts.init(comparisonChartRef.value)
  }
  
  const colors = getChartColors()
  
  if (comparisonData1.value.length === 0 && comparisonData2.value.length === 0) return
  
  // Use dates from first dataset
  const dates = comparisonData1.value.map(d => d.date)
  
  comparisonChartInstance.setOption({
    tooltip: { 
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      borderColor: colors.primary,
      textStyle: { color: '#E5E7EB', fontSize: 12 },
      formatter: (params) => {
        let result = params[0].name + '<br/>'
        params.forEach(p => {
          result += `${p.seriesName}: <strong>${p.value?.toFixed(4) || '--'}</strong><br/>`
        })
        return result
      }
    },
    legend: { 
      data: [`${compareCurrency1.value}/CNY`, `${compareCurrency2.value}/CNY`],
      top: 0,
      textStyle: { color: colors.text }
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '15%', containLabel: true },
    xAxis: { 
      type: 'category', 
      data: dates,
      axisLabel: { color: colors.text, fontSize: 10, rotate: 45 },
      axisLine: { lineStyle: { color: colors.text + '40' } }
    },
    yAxis: [
      {
        type: 'value',
        name: `${compareCurrency1.value}/CNY`,
        nameTextStyle: { color: colors.primary, fontSize: 10 },
        position: 'left',
        axisLabel: { color: colors.text, fontSize: 10 },
        axisLine: { lineStyle: { color: colors.primary } },
        splitLine: { lineStyle: { color: colors.text + '20' } }
      },
      {
        type: 'value',
        name: `${compareCurrency2.value}/CNY`,
        nameTextStyle: { color: colors.secondary, fontSize: 10 },
        position: 'right',
        axisLabel: { color: colors.text, fontSize: 10 },
        axisLine: { lineStyle: { color: colors.secondary } },
        splitLine: { show: false }
      }
    ],
    series: [
      {
        name: `${compareCurrency1.value}/CNY`,
        type: 'line',
        yAxisIndex: 0,
        data: comparisonData1.value.map(d => d.rate),
        smooth: true,
        symbol: 'circle',
        symbolSize: 4,
        lineStyle: { color: colors.primary, width: 2 },
        itemStyle: { color: colors.primary }
      },
      {
        name: `${compareCurrency2.value}/CNY`,
        type: 'line',
        yAxisIndex: 1,
        data: comparisonData2.value.map(d => d.rate),
        smooth: true,
        symbol: 'circle',
        symbolSize: 4,
        lineStyle: { color: colors.secondary, width: 2 },
        itemStyle: { color: colors.secondary }
      }
    ]
  })
}

function formatPrice(val) {
  if (val === null || val === undefined) return '--'
  if (val >= 100) return val.toFixed(2)
  if (val >= 10) return val.toFixed(3)
  return val.toFixed(4)
}

function formatTime(isoString) {
  if (!isoString) return ''
  const date = new Date(isoString)
  return date.toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function getChangeClass(val) {
  if (val === null || val === undefined) return 'text-terminal-dim'
  return val >= 0 ? 'text-bullish' : 'text-bearish'
}

let resizeTimer = null
function handleResize() {
  clearTimeout(resizeTimer)
  resizeTimer = setTimeout(() => {
    trendChartInstance?.resize()
    comparisonChartInstance?.resize()
  }, 150)
}

onMounted(async () => {
  await fetchData()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  clearTimeout(resizeTimer)
  trendChartInstance?.dispose()
  comparisonChartInstance?.dispose()
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.bg-base-200 {
  background: var(--bg-secondary, #1a1f2e);
}

.bg-terminal-panel {
  background: var(--bg-secondary, #1a1f2e);
}

.bg-terminal-bg {
  background: var(--bg-primary, #0f1419);
}

.text-terminal-accent {
  color: var(--color-primary, #0F52BA);
}

.text-terminal-primary {
  color: var(--text-primary, #E5E7EB);
}

.text-terminal-dim {
  color: var(--text-secondary, #8B949E);
}

.text-bullish {
  color: var(--color-up, #FF6B6B);
}

.text-bearish {
  color: var(--color-down, #51CF66);
}

.border-theme-secondary {
  border-color: var(--border-color, #2d3748);
}

.ring-terminal-accent {
  --tw-ring-color: var(--color-primary, #0F52BA);
}

.bg-bearish\/10 {
  background: rgba(255, 107, 107, 0.1);
}

.bg-bearish\/20 {
  background: rgba(255, 107, 107, 0.2);
}

.border-bearish\/30 {
  border-color: rgba(255, 107, 107, 0.3);
}
</style>
