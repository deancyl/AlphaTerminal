<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-lg font-bold text-theme-primary">📊 Token 消耗监控</h2>
        <p class="text-xs text-theme-muted mt-1">实时监控 LLM API 调用量、Token 消耗和成本</p>
      </div>
      <div class="flex items-center gap-3">
        <!-- Time Range Selector -->
        <select
          v-model="timeRange"
          class="bg-theme-surface border border-theme rounded-sm px-3 py-2 text-sm text-theme-primary
                 focus:outline-none focus:border-terminal-accent/60 cursor-pointer"
          @change="loadData"
        >
          <option value="today">今日</option>
          <option value="yesterday">昨日</option>
          <option value="week">近7天</option>
          <option value="month">近30天</option>
        </select>
        <button
          class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-sm text-sm hover:bg-terminal-accent/25 transition-colors"
          @click="loadData"
        >
          🔄 刷新
        </button>
      </div>
    </div>

    <!-- WebSocket Connection Indicator -->
    <div class="flex items-center gap-2 text-xs">
      <span
        class="w-2 h-2 rounded-full"
        :class="wsConnected ? 'bg-[var(--color-success)] animate-pulse' : 'bg-[var(--color-danger)]'"
      />
      <span :class="wsConnected ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]'">
        {{ wsConnected ? '● 实时更新已连接' : '○ 实时更新断开' }}
      </span>
    </div>

    <!-- Loading State -->
    <LoadingSpinner v-if="loading" text="加载监控数据..." />

    <!-- Error State -->
    <ErrorDisplay v-else-if="error" :error="error" :retry="loadData" />

    <template v-else>
      <!-- Summary Cards -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div class="p-4 bg-theme-surface rounded-sm border border-theme">
          <div class="text-[10px] text-theme-muted mb-1">总请求</div>
          <div class="text-2xl font-bold text-terminal-accent tabular-nums">
            {{ formatNumber(summary.total_requests) }}
          </div>
          <div class="text-[10px] text-theme-muted mt-1">
            较昨日 {{ formatChange(summary.requests_change) }}
          </div>
        </div>
        <div class="p-4 bg-theme-surface rounded-sm border border-theme">
          <div class="text-[10px] text-theme-muted mb-1">总 Token</div>
          <div class="text-2xl font-bold text-terminal-accent tabular-nums">
            {{ formatTokens(summary.total_tokens) }}
          </div>
          <div class="text-[10px] text-theme-muted mt-1">
            输入 {{ formatTokens(summary.input_tokens) }} / 输出 {{ formatTokens(summary.output_tokens) }}
          </div>
        </div>
        <div class="p-4 bg-theme-surface rounded-sm border border-theme">
          <div class="text-[10px] text-theme-muted mb-1">总成本</div>
          <div class="text-2xl font-bold text-bull tabular-nums">
            ${{ summary.total_cost?.toFixed(4) || '0.0000' }}
          </div>
          <div class="text-[10px] text-theme-muted mt-1">
            预估月成本 ${{ summary.estimated_monthly?.toFixed(2) || '0.00' }}
          </div>
        </div>
        <div class="p-4 bg-theme-surface rounded-sm border border-theme">
          <div class="text-[10px] text-theme-muted mb-1">平均延迟</div>
          <div class="text-2xl font-bold text-theme-primary tabular-nums">
            {{ summary.avg_latency?.toFixed(0) || 0 }}ms
          </div>
          <div class="text-[10px] text-theme-muted mt-1">
            P95 {{ summary.p95_latency?.toFixed(0) || 0 }}ms
          </div>
        </div>
      </div>

      <!-- Charts Row -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <!-- Daily Trend Chart -->
        <div class="bg-theme-surface rounded-sm border border-theme p-4">
          <h3 class="text-sm font-bold text-theme-primary mb-3">📈 每日消耗趋势</h3>
          <div ref="trendChartRef" class="h-64"></div>
        </div>

        <!-- Model Cost Distribution -->
        <div class="bg-theme-surface rounded-sm border border-theme p-4">
          <h3 class="text-sm font-bold text-theme-primary mb-3">🥧 模型成本分布</h3>
          <div ref="pieChartRef" class="h-64"></div>
        </div>
      </div>

      <!-- Model Breakdown Table -->
      <div class="bg-theme-surface rounded-sm border border-theme overflow-hidden">
        <div class="px-4 py-3 border-b border-theme">
          <h3 class="text-sm font-bold text-theme-primary">📋 模型消耗明细</h3>
        </div>
        <div class="overflow-x-auto">
          <table class="theme-table">
            <thead>
              <tr>
                <th class="cursor-pointer hover:bg-theme-hover" @click="sortBy('model_id')">
                  模型
                  <span v-if="sortKey === 'model_id'" class="ml-1">{{ sortOrder === 'asc' ? '↑' : '↓' }}</span>
                </th>
                <th>Provider</th>
                <th class="cursor-pointer hover:bg-theme-hover text-right" @click="sortBy('requests')">
                  请求数
                  <span v-if="sortKey === 'requests'" class="ml-1">{{ sortOrder === 'asc' ? '↑' : '↓' }}</span>
                </th>
                <th class="text-right">输入 Token</th>
                <th class="text-right">输出 Token</th>
                <th class="cursor-pointer hover:bg-theme-hover text-right" @click="sortBy('cost')">
                  成本
                  <span v-if="sortKey === 'cost'" class="ml-1">{{ sortOrder === 'asc' ? '↑' : '↓' }}</span>
                </th>
                <th class="text-right">平均延迟</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="model in sortedModelBreakdown" :key="model.model_id">
                <td class="font-medium">{{ model.model_id }}</td>
                <td class="text-theme-muted">{{ model.provider }}</td>
                <td class="text-right tabular-nums">{{ formatNumber(model.requests) }}</td>
                <td class="text-right tabular-nums text-theme-secondary">{{ formatTokens(model.input_tokens) }}</td>
                <td class="text-right tabular-nums text-theme-secondary">{{ formatTokens(model.output_tokens) }}</td>
                <td class="text-right tabular-nums text-bull">${{ model.cost?.toFixed(4) || '0.0000' }}</td>
                <td class="text-right tabular-nums">{{ model.avg_latency?.toFixed(0) || 0 }}ms</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="modelBreakdown.length === 0" class="p-8 text-center text-theme-muted text-sm">
          暂无数据
        </div>
      </div>

      <!-- Recent Requests Log -->
      <div class="bg-theme-surface rounded-sm border border-theme overflow-hidden">
        <div class="px-4 py-3 border-b border-theme flex items-center justify-between">
          <h3 class="text-sm font-bold text-theme-primary">📝 最近请求记录</h3>
          <span class="text-xs text-theme-muted">显示最近 20 条</span>
        </div>
        <div class="max-h-64 overflow-y-auto">
          <div
            v-for="(req, idx) in recentRequests"
            :key="idx"
            class="px-4 py-2 border-b border-theme-light last:border-b-0 hover:bg-theme-hover transition-colors text-xs"
          >
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-3">
                <span class="text-theme-muted tabular-nums">{{ formatTime(req.timestamp) }}</span>
                <span class="font-medium text-theme-primary">{{ req.model_id }}</span>
                <span class="text-theme-secondary">
                  {{ formatTokens(req.input_tokens) }}→{{ formatTokens(req.output_tokens) }}
                </span>
              </div>
              <div class="flex items-center gap-3">
                <span class="text-bull tabular-nums">${{ req.cost?.toFixed(6) || '0.000000' }}</span>
                <span class="text-theme-muted tabular-nums">{{ req.latency }}ms</span>
              </div>
            </div>
          </div>
          <div v-if="recentRequests.length === 0" class="p-8 text-center text-theme-muted text-sm">
            暂无请求记录
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { apiFetch } from '../../utils/api.js'
import { useECharts } from '../../composables/useECharts.js'
import { getECharts } from '../../utils/lazyEcharts.js'
import LoadingSpinner from '../f9/LoadingSpinner.vue'
import ErrorDisplay from '../f9/ErrorDisplay.vue'

// State
const loading = ref(true)
const error = ref(null)
const timeRange = ref('today')
const wsConnected = ref(false)

// Data
const summary = ref({
  total_requests: 0,
  total_tokens: 0,
  input_tokens: 0,
  output_tokens: 0,
  total_cost: 0,
  estimated_monthly: 0,
  avg_latency: 0,
  p95_latency: 0,
  requests_change: 0,
})

const dailyTrend = ref([])
const modelBreakdown = ref([])
const recentRequests = ref([])

// Sorting
const sortKey = ref('cost')
const sortOrder = ref('desc')

const sortedModelBreakdown = computed(() => {
  const data = [...modelBreakdown.value]
  data.sort((a, b) => {
    const aVal = a[sortKey.value] || 0
    const bVal = b[sortKey.value] || 0
    return sortOrder.value === 'asc' ? aVal - bVal : bVal - aVal
  })
  return data
})

function sortBy(key) {
  if (sortKey.value === key) {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortOrder.value = 'desc'
  }
}

// Chart refs
const trendChartRef = ref(null)
const pieChartRef = ref(null)

// Chart instances
const { initChart: initTrendChart, setOption: setTrendOption, dispose: disposeTrendChart } = useECharts(trendChartRef)
const { initChart: initPieChart, setOption: setPieOption, dispose: disposePieChart } = useECharts(pieChartRef)

// WebSocket
let ws = null

function connectWebSocket() {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${proto}//${window.location.host}/api/v1/admin/tokens/stream`

  try {
    ws = new WebSocket(wsUrl)
    ws.onopen = () => {
      wsConnected.value = true
    }
    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data)
        if (data.type === 'token_update') {
          // Update recent requests
          recentRequests.value.unshift(data.request)
          if (recentRequests.value.length > 20) {
            recentRequests.value.pop()
          }
          // Update summary
          summary.value.total_requests++
          summary.value.total_tokens += data.request.input_tokens + data.request.output_tokens
          summary.value.total_cost += data.request.cost || 0
        }
      } catch {
        // Ignore parse errors
      }
    }
    ws.onerror = () => {
      wsConnected.value = false
    }
    ws.onclose = () => {
      wsConnected.value = false
      // Reconnect after 5 seconds
      setTimeout(connectWebSocket, 5000)
    }
  } catch {
    wsConnected.value = false
  }
}

function disconnectWebSocket() {
  if (ws) {
    ws.close()
    ws = null
  }
}

// Data loading
async function loadData() {
  loading.value = true
  error.value = null
  try {
    const [summaryData, trendData, breakdownData, requestsData] = await Promise.all([
      apiFetch(`/api/v1/admin/tokens/summary?range=${timeRange.value}`),
      apiFetch(`/api/v1/admin/tokens/trend?range=${timeRange.value}`),
      apiFetch(`/api/v1/admin/tokens/breakdown?range=${timeRange.value}`),
      apiFetch(`/api/v1/admin/tokens/recent?limit=20`),
    ])

    summary.value = summaryData || {}
    dailyTrend.value = trendData || []
    modelBreakdown.value = breakdownData || []
    recentRequests.value = requestsData || []

    // Update charts
    await nextTick()
    await updateCharts()
  } catch (e) {
    error.value = e.message || '加载监控数据失败'
  } finally {
    loading.value = false
  }
}

async function updateCharts() {
  const echarts = await getECharts()

  // Get theme colors from CSS variables
  const primaryColor = getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim() || '#0F52BA'
  const bullColor = getComputedStyle(document.documentElement).getPropertyValue('--color-bull').trim() || '#E63946'
  const bearColor = getComputedStyle(document.documentElement).getPropertyValue('--color-bear').trim() || '#1A936F'
  const textColor = getComputedStyle(document.documentElement).getPropertyValue('--text-secondary').trim() || '#C9D1D9'
  const gridColor = getComputedStyle(document.documentElement).getPropertyValue('--chart-grid').trim() || '#1C2333'

  // Trend Chart
  const trendChart = await initTrendChart()
  if (trendChart && dailyTrend.value.length > 0) {
    setTrendOption({
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(30, 30, 30, 0.9)',
        borderColor: '#30363D',
        textStyle: { color: '#F0F6FC' },
      },
      legend: {
        data: ['请求数', 'Token数', '成本'],
        textStyle: { color: textColor },
        top: 0,
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        top: '15%',
        containLabel: true,
      },
      xAxis: {
        type: 'category',
        data: dailyTrend.value.map(d => d.date),
        axisLine: { lineStyle: { color: gridColor } },
        axisLabel: { color: textColor },
      },
      yAxis: [
        {
          type: 'value',
          name: '请求数',
          axisLine: { lineStyle: { color: gridColor } },
          axisLabel: { color: textColor },
          splitLine: { lineStyle: { color: gridColor } },
        },
        {
          type: 'value',
          name: '成本 ($)',
          axisLine: { lineStyle: { color: gridColor } },
          axisLabel: { color: textColor },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: '请求数',
          type: 'bar',
          data: dailyTrend.value.map(d => d.requests),
          itemStyle: { color: primaryColor },
        },
        {
          name: '成本',
          type: 'line',
          yAxisIndex: 1,
          data: dailyTrend.value.map(d => d.cost),
          itemStyle: { color: bullColor },
          smooth: true,
        },
      ],
    })
  }

  // Pie Chart
  const pieChart = await initPieChart()
  if (pieChart && modelBreakdown.value.length > 0) {
    const pieData = modelBreakdown.value.slice(0, 8).map(m => ({
      name: m.model_id,
      value: m.cost || 0,
    }))

    setPieOption({
      tooltip: {
        trigger: 'item',
        backgroundColor: 'rgba(30, 30, 30, 0.9)',
        borderColor: '#30363D',
        textStyle: { color: '#F0F6FC' },
        formatter: '{b}: ${c} ({d}%)',
      },
      legend: {
        type: 'scroll',
        orient: 'vertical',
        right: 10,
        top: 20,
        bottom: 20,
        textStyle: { color: textColor },
      },
      series: [
        {
          type: 'pie',
          radius: ['40%', '70%'],
          center: ['40%', '50%'],
          avoidLabelOverlap: false,
          itemStyle: {
            borderRadius: 4,
            borderColor: 'var(--bg-surface)',
            borderWidth: 2,
          },
          label: {
            show: false,
          },
          emphasis: {
            label: {
              show: true,
              fontSize: 14,
              fontWeight: 'bold',
              color: textColor,
            },
          },
          labelLine: {
            show: false,
          },
          data: pieData,
        },
      ],
      color: [primaryColor, bullColor, bearColor, '#F5A623', '#9B59B6', '#3498DB', '#1ABC9C', '#E74C3C'],
    })
  }
}

// Formatters
function formatNumber(n) {
  if (!n) return '0'
  return n.toLocaleString()
}

function formatTokens(n) {
  if (!n) return '0'
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`
  return n.toString()
}

function formatChange(n) {
  if (!n) return '0%'
  const sign = n > 0 ? '+' : ''
  return `${sign}${n.toFixed(1)}%`
}

function formatTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  return `${(d.getMonth() + 1).toString().padStart(2, '0')}/${d.getDate().toString().padStart(2, '0')} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}

// Lifecycle
onMounted(async () => {
  await loadData()
  connectWebSocket()
})

onBeforeUnmount(() => {
  disconnectWebSocket()
  disposeTrendChart()
  disposePieChart()
})

// Watch for time range changes
watch(timeRange, () => {
  loadData()
})
</script>
