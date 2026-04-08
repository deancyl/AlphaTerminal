<template>
  <div class="fullscreen-kline" @keydown.esc="emit('close')" tabindex="0">
    <!-- 顶部工具栏 -->
    <header class="kline-header">
      <div class="header-left">
        <span class="symbol-name">{{ props.name || props.symbol }}</span>
        <span class="symbol-code">{{ props.symbol }}</span>
      </div>
      
      <div class="header-center">
        <!-- 周期选择 -->
        <div class="period-selector">
          <button
            v-for="p in periods"
            :key="p.value"
            :class="['period-btn', { active: period === p.value }]"
            @click="period = p.value"
          >
            {{ p.label }}
          </button>
        </div>
        
        <!-- 副图选择 -->
        <div class="indicator-selector">
          <button
            v-for="ind in subChartOptions"
            :key="ind.key"
            :class="['indicator-btn', { active: activeSubChart === ind.key }]"
            @click="activeSubChart = ind.key"
          >
            {{ ind.label }}
          </button>
        </div>
      </div>
      
      <div class="header-right">
        <span class="latest-price" :class="priceColor">{{ latestPriceText }}</span>
        <span class="latest-change" :class="priceColor">{{ latestChangeText }}</span>
        <button class="close-btn" @click="emit('close')">✕ 关闭</button>
      </div>
    </header>

    <!-- 主体区域 -->
    <div class="kline-body">
      <!-- 左侧图表区 -->
      <div class="chart-container">
        <!-- 加载状态 -->
        <div v-if="loading" class="loading-overlay">
          <div class="loading-text">加载中...</div>
        </div>
        
        <!-- 错误状态 -->
        <div v-else-if="chartError" class="error-overlay">
          <div class="error-text">{{ chartError }}</div>
          <button class="error-close" @click="chartError = ''">关闭</button>
        </div>
        
        <!-- ECharts 容器 -->
        <div ref="chartEl" class="chart-wrapper"></div>
      </div>
      
      <!-- 右侧信息面板 -->
      <QuotePanel
        :symbol="props.symbol"
        :name="props.name"
        :realtimeData="quoteData"
        :latestCandle="latestCandle"
        class="quote-panel-wrapper"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts/core'
import { CandlestickChart, LineChart, BarChart } from 'echarts/charts'
import {
  GridComponent, TooltipComponent, DataZoomComponent,
  MarkLineComponent, VisualMapComponent, LegendComponent
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import QuotePanel from './QuotePanel.vue'

// 注册 ECharts 组件
echarts.use([
  CandlestickChart, LineChart, BarChart,
  GridComponent, TooltipComponent, DataZoomComponent,
  MarkLineComponent, VisualMapComponent, LegendComponent,
  CanvasRenderer,
])

const props = defineProps({
  symbol: { type: String, required: true },
  name:   { type: String, default: '' },
})

const emit = defineEmits(['close', 'symbol-change'])

// 状态
const period = ref('daily')
const loading = ref(false)
const chartError = ref('')
const histData = ref([])
const quoteData = ref({})
const latestPrice = ref(null)
const latestChange = ref(0)

// 图表实例
const chartEl = ref(null)
let chart = null

// 周期选项
const periods = [
  { label: '日K', value: 'daily' },
  { label: '周K', value: 'weekly' },
  { label: '月K', value: 'monthly' },
  { label: '5分', value: '5min' },
  { label: '15分', value: '15min' },
  { label: '30分', value: '30min' },
  { label: '60分', value: '60min' },
]

// 副图选项
const subChartOptions = [
  { key: 'VOL', label: '成交量' },
  { key: 'MACD', label: 'MACD' },
  { key: 'KDJ', label: 'KDJ' },
  { key: 'RSI', label: 'RSI' },
]
const activeSubChart = ref('VOL')

// 计算属性
const priceColor = computed(() => {
  if (latestChange.value > 0) return 'price-up'
  if (latestChange.value < 0) return 'price-down'
  return 'price-flat'
})

const latestCandle = computed(() => {
  if (histData.value.length === 0) return null
  return histData.value[histData.value.length - 1]
})

const latestPriceText = computed(() => {
  if (latestPrice.value == null) return '--'
  return latestPrice.value.toFixed(2)
})

const latestChangeText = computed(() => {
  if (latestChange.value == null) return '--'
  const sign = latestChange.value >= 0 ? '+' : ''
  return `${sign}${latestChange.value.toFixed(2)}%`
})

// 格式化函数
function formatPrice(val) {
  if (val == null || isNaN(val)) return '--'
  return Number(val).toFixed(2)
}

function formatVolume(val) {
  if (val == null || isNaN(val)) return '--'
  if (val >= 1e8) return (val / 1e8).toFixed(2) + '亿'
  if (val >= 1e4) return (val / 1e4).toFixed(2) + '万'
  return val.toString()
}

// 获取历史数据
async function fetchData() {
  if (!props.symbol) return
  
  loading.value = true
  chartError.value = ''
  
  try {
    const params = new URLSearchParams({
      period: period.value,
      limit: '500',
      offset: '0',
    })
    
    const res = await fetch(`/api/v1/market/history/${props.symbol}?${params}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    
    const data = await res.json()
    const historyArray = data.history || data
    
    if (!Array.isArray(historyArray) || historyArray.length === 0) {
      chartError.value = '暂无历史数据'
      histData.value = []
      return
    }
    
    // 按日期排序
    histData.value = historyArray.sort((a, b) => 
      new Date(a.date) - new Date(b.date)
    )
    
    // 更新最新价格
    const last = histData.value[histData.value.length - 1]
    latestPrice.value = last.close ?? last.price
    latestChange.value = last.change_pct ?? 0
    
    // 渲染图表
    renderChart()
    
  } catch (e) {
    chartError.value = `加载失败: ${e.message}`
    console.error('[FullscreenKline] fetchData error:', e)
  } finally {
    loading.value = false
  }
}

// 获取实时行情
async function fetchQuote() {
  if (!props.symbol) return
  
  try {
    const res = await fetch(`/api/v1/market/quote_detail/${props.symbol}?_t=${Date.now()}`)
    if (res.ok) {
      quoteData.value = await res.json()
    }
  } catch (e) {
    console.warn('[FullscreenKline] fetchQuote error:', e.message)
  }
}

// 渲染图表
function renderChart() {
  if (!chartEl.value || histData.value.length === 0) return
  
  // 初始化图表
  if (!chart) {
    chart = echarts.init(chartEl.value)
    window.addEventListener('resize', handleResize)
  }
  
  const data = histData.value
  const dates = data.map(d => d.date)
  const klineData = data.map(d => [d.open, d.close, d.low, d.high])
  const volumes = data.map(d => d.volume)
  
  // 计算 MA
  const ma5 = calcMA(data, 5)
  const ma10 = calcMA(data, 10)
  const ma20 = calcMA(data, 20)
  
  const option = {
    backgroundColor: 'transparent',
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: 'rgba(10, 14, 23, 0.9)',
      borderColor: '#374151',
      textStyle: { color: '#e5e7eb', fontSize: 11 },
    },
    grid: [
      { left: 60, right: 20, top: 30, height: '55%' },
      { left: 60, right: 20, top: '68%', height: '25%' },
    ],
    xAxis: [
      {
        type: 'category',
        data: dates,
        gridIndex: 0,
        axisLabel: { show: false },
        axisLine: { lineStyle: { color: '#374151' } },
      },
      {
        type: 'category',
        data: dates,
        gridIndex: 1,
        axisLabel: { color: '#6b7280', fontSize: 10 },
        axisLine: { lineStyle: { color: '#374151' } },
      },
    ],
    yAxis: [
      {
        type: 'value',
        gridIndex: 0,
        scale: true,
        splitLine: { lineStyle: { color: '#1f2937' } },
        axisLabel: { color: '#6b7280', fontSize: 10 },
      },
      {
        type: 'value',
        gridIndex: 1,
        splitLine: { show: false },
        axisLabel: { color: '#6b7280', fontSize: 10 },
      },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 50, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1], show: true, bottom: 10, height: 20 },
    ],
    series: [
      // K线
      {
        name: 'K线',
        type: 'candlestick',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: klineData,
        itemStyle: {
          color: '#ef232a',
          color0: '#14b143',
          borderColor: '#ef232a',
          borderColor0: '#14b143',
        },
      },
      // MA5
      {
        name: 'MA5',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: ma5,
        smooth: true,
        lineStyle: { color: '#fbbf24', width: 1 },
        symbol: 'none',
      },
      // MA10
      {
        name: 'MA10',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: ma10,
        smooth: true,
        lineStyle: { color: '#60a5fa', width: 1 },
        symbol: 'none',
      },
      // MA20
      {
        name: 'MA20',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: ma20,
        smooth: true,
        lineStyle: { color: '#c084fc', width: 1 },
        symbol: 'none',
      },
      // 成交量
      {
        name: '成交量',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumes,
        itemStyle: {
          color: (params) => {
            const idx = params.dataIndex
            return data[idx].close >= data[idx].open ? '#ef232a' : '#14b143'
          },
        },
      },
    ],
  }
  
  chart.setOption(option, true)
}

// 计算移动平均线
function calcMA(data, period) {
  const result = []
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      result.push('-')
      continue
    }
    let sum = 0
    for (let j = 0; j < period; j++) {
      sum += data[i - j].close
    }
    result.push((sum / period).toFixed(2))
  }
  return result
}

// 窗口大小变化处理
function handleResize() {
  chart?.resize()
}

// 监听周期变化
watch(period, () => {
  fetchData()
})

// 监听 symbol 变化
watch(() => props.symbol, (newSym) => {
  if (newSym) {
    fetchData()
    fetchQuote()
  }
}, { immediate: true })

// 生命周期
onMounted(() => {
  if (props.symbol) {
    fetchData()
    fetchQuote()
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
  chart = null
})
</script>

<style scoped>
.fullscreen-kline {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: #0a0e17;
  display: flex;
  flex-direction: column;
  z-index: 99999;
}

/* 顶部工具栏 */
.kline-header {
  height: 48px;
  background: #111827;
  border-bottom: 1px solid #374151;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 150px;
}

.symbol-name {
  font-size: 14px;
  font-weight: 600;
  color: #f3f4f6;
}

.symbol-code {
  font-size: 11px;
  color: #6b7280;
  font-family: monospace;
}

.header-center {
  display: flex;
  align-items: center;
  gap: 16px;
  flex: 1;
  justify-content: center;
}

.period-selector,
.indicator-selector {
  display: flex;
  gap: 4px;
}

.period-btn,
.indicator-btn {
  padding: 4px 10px;
  font-size: 12px;
  border: 1px solid #374151;
  background: transparent;
  color: #9ca3af;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.period-btn:hover,
.indicator-btn:hover {
  border-color: #6b7280;
  color: #e5e7eb;
}

.period-btn.active,
.indicator-btn.active {
  background: #2563eb;
  border-color: #2563eb;
  color: white;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 200px;
  justify-content: flex-end;
}

.latest-price {
  font-size: 16px;
  font-weight: 700;
  font-family: monospace;
}

.latest-change {
  font-size: 13px;
  font-family: monospace;
}

.price-up { color: #ef4444; }
.price-down { color: #22c55e; }
.price-flat { color: #9ca3af; }

.close-btn {
  padding: 6px 14px;
  font-size: 12px;
  border: 1px solid #4b5563;
  background: transparent;
  color: #9ca3af;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.close-btn:hover {
  border-color: #ef4444;
  color: #ef4444;
}

/* 主体区域 */
.kline-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* 图表容器 */
.chart-container {
  flex: 1;
  position: relative;
  min-width: 0;
}

.chart-wrapper {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
}

/* 加载和错误遮罩 */
.loading-overlay,
.error-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(10, 14, 23, 0.9);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 10;
}

.loading-text,
.error-text {
  font-size: 14px;
  color: #9ca3af;
}

.error-close {
  margin-top: 12px;
  padding: 6px 16px;
  font-size: 12px;
  border: 1px solid #4b5563;
  background: transparent;
  color: #9ca3af;
  border-radius: 4px;
  cursor: pointer;
}

.error-close:hover {
  border-color: #6b7280;
  color: #e5e7eb;
}

/* 右侧 QuotePanel 包装器 */
.quote-panel-wrapper {
  width: 300px;
  flex-shrink: 0;
  background: #111827;
  border-left: 1px solid #374151;
}

/* 响应式 */
@media (max-width: 768px) {
  .quote-panel-wrapper {
    display: none;
  }
  
  .header-center {
    flex-direction: column;
    gap: 8px;
  }
  
  .symbol-code {
    display: none;
  }
}
</style>
