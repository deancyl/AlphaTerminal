<template>
  <div class="performance-panel">
    <!-- Header -->
    <div class="panel-header">
      <h2 class="text-xl font-bold text-theme-primary">📊 性能监控</h2>
      <p class="text-sm text-theme-muted mt-1">API响应时间 + 请求统计</p>
    </div>

    <!-- Error State -->
    <ErrorDisplay v-if="error" :error="error" :retry="fetchMetrics" />

    <!-- Loading State -->
    <LoadingSpinner v-else-if="loading" text="加载性能指标..." />

    <!-- Main Content -->
    <div v-else class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <!-- Response Time Overview -->
      <div class="bg-surface rounded-lg border border-theme p-4">
        <h3 class="text-lg font-semibold text-theme-primary mb-3">响应时间概览</h3>
        
        <div class="grid grid-cols-3 gap-3">
          <div class="stat-card">
            <div class="text-sm text-theme-muted">平均响应</div>
            <div class="text-2xl font-bold text-theme-primary">{{ formatMs(metrics.avgResponseTime) }}</div>
          </div>
          <div class="stat-card">
            <div class="text-sm text-theme-muted">P95响应</div>
            <div class="text-2xl font-bold" :class="getLatencyClass(metrics.p95ResponseTime)">
              {{ formatMs(metrics.p95ResponseTime) }}
            </div>
          </div>
          <div class="stat-card">
            <div class="text-sm text-theme-muted">P99响应</div>
            <div class="text-2xl font-bold" :class="getLatencyClass(metrics.p99ResponseTime)">
              {{ formatMs(metrics.p99ResponseTime) }}
            </div>
          </div>
        </div>

        <!-- Response Time Distribution Chart -->
        <div ref="latencyChartRef" class="mt-4 h-[200px]" />
      </div>

      <!-- Request Statistics -->
      <div class="bg-surface rounded-lg border border-theme p-4">
        <h3 class="text-lg font-semibold text-theme-primary mb-3">请求统计</h3>
        
        <div class="grid grid-cols-2 gap-3">
          <div class="stat-card">
            <div class="text-sm text-theme-muted">总请求数</div>
            <div class="text-2xl font-bold text-theme-primary">{{ formatNumber(metrics.totalRequests) }}</div>
          </div>
          <div class="stat-card">
            <div class="text-sm text-theme-muted">成功率</div>
            <div class="text-2xl font-bold text-[var(--color-success)]">
              {{ formatPercent(metrics.successRate) }}
            </div>
          </div>
          <div class="stat-card">
            <div class="text-sm text-theme-muted">错误率</div>
            <div class="text-2xl font-bold" :class="metrics.errorRate > 5 ? 'text-[var(--color-bull)]' : 'text-theme-secondary'">
              {{ formatPercent(metrics.errorRate) }}
            </div>
          </div>
          <div class="stat-card">
            <div class="text-sm text-theme-muted">缓存命中率</div>
            <div class="text-2xl font-bold text-[var(--color-info)]">
              {{ formatPercent(metrics.cacheHitRate) }}
            </div>
          </div>
        </div>

        <!-- Request Rate Chart -->
        <div ref="requestChartRef" class="mt-4 h-[200px]" />
      </div>

      <!-- Top Endpoints -->
      <div class="bg-surface rounded-lg border border-theme p-4 lg:col-span-2">
        <h3 class="text-lg font-semibold text-theme-primary mb-3">热门端点 (Top 10)</h3>
        
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-theme">
                <th class="text-left py-2 text-theme-muted">端点</th>
                <th class="text-right py-2 text-theme-muted">请求次数</th>
                <th class="text-right py-2 text-theme-muted">平均响应</th>
                <th class="text-right py-2 text-theme-muted">P95响应</th>
                <th class="text-right py-2 text-theme-muted">错误率</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="endpoint in topEndpoints" :key="endpoint.name" class="border-b border-theme-light">
                <td class="py-2 text-theme-primary">{{ endpoint.name }}</td>
                <td class="py-2 text-right text-theme-secondary">{{ formatNumber(endpoint.requests) }}</td>
                <td class="py-2 text-right">{{ formatMs(endpoint.avgLatency) }}</td>
                <td class="py-2 text-right" :class="getLatencyClass(endpoint.p95Latency)">
                  {{ formatMs(endpoint.p95Latency) }}
                </td>
                <td class="py-2 text-right" :class="endpoint.errorRate > 5 ? 'text-[var(--color-bull)]' : 'text-[var(--color-success)]'">
                  {{ formatPercent(endpoint.errorRate) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Refresh Controls -->
    <div class="mt-4 flex items-center gap-4">
      <button
        class="px-4 py-2 bg-terminal-accent text-white rounded hover:bg-terminal-accent/80 transition-colors"
        @click="fetchMetrics"
      >
        🔄 刷新数据
      </button>
      <select
        v-model="selectedHours"
        class="px-3 py-2 border border-theme rounded bg-terminal-panel text-theme-primary"
        @change="fetchMetrics"
      >
        <option value="1">最近1小时</option>
        <option value="6">最近6小时</option>
        <option value="24">最近24小时</option>
        <option value="168">最近7天</option>
      </select>
      <div class="text-sm text-theme-muted">
        数据保留: {{ metrics.retentionDays }}天
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import * as echarts from 'echarts'
import { apiFetch } from '@/utils/api.js'
import LoadingSpinner from '@/components/f9/LoadingSpinner.vue'
import ErrorDisplay from '@/components/f9/ErrorDisplay.vue'
import { getDynamicThemeColors } from '@/utils/echartsTheme.js'

// State
const loading = ref(true)
const error = ref(null)
const metrics = ref({
  avgResponseTime: 0,
  p95ResponseTime: 0,
  p99ResponseTime: 0,
  totalRequests: 0,
  successRate: 100,
  errorRate: 0,
  cacheHitRate: 0,
  retentionDays: 7
})
const topEndpoints = ref([])
const selectedHours = ref(24)

// Chart refs
const latencyChartRef = ref(null)
const requestChartRef = ref(null)
let latencyChart = null
let requestChart = null

// Fetch metrics from API
async function fetchMetrics() {
  loading.value = true
  error.value = null
  
  try {
    const response = await apiFetch(`/api/v1/admin/performance/metrics?hours=${selectedHours.value}`, {
      timeoutMs: 10000
    })
    
    if (response.code === 0 && response.data) {
      processData(response.data)
    } else {
      throw new Error(response.message || 'Failed to fetch metrics')
    }
  } catch (e) {
    error.value = { message: e.message || '加载失败', retry: fetchMetrics }
  } finally {
    loading.value = false
  }
}

// Process API response
function processData(data) {
  if (data.stats) {
    metrics.value = {
      avgResponseTime: data.stats.avg_latency_ms || 0,
      p95ResponseTime: data.stats.p95_latency_ms || 0,
      p99ResponseTime: data.stats.p99_latency_ms || 0,
      totalRequests: data.stats.total_requests || 0,
      successRate: data.stats.success_rate || 100,
      errorRate: data.stats.error_rate || 0,
      cacheHitRate: data.stats.cache_hit_rate || 0,
      retentionDays: data.retention_days || 7
    }
  }
  
  if (data.history && data.history.length > 0) {
    updateLatencyChart(data.history)
    updateRequestChart(data.history)
  }
  
  if (data.stats && data.stats.endpoints) {
    topEndpoints.value = data.stats.endpoints.slice(0, 10)
  }
}

// Initialize charts
function initCharts() {
  const themeColors = getDynamicThemeColors()
  
  if (latencyChartRef.value) {
    latencyChart = echarts.init(latencyChartRef.value)
    latencyChart.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: {
        type: 'category',
        data: [],
        axisLabel: { color: themeColors.textSecondary }
      },
      yAxis: {
        type: 'value',
        name: '响应时间(ms)',
        axisLabel: { color: themeColors.textSecondary }
      },
      series: [{
        name: '响应时间',
        type: 'line',
        smooth: true,
        data: [],
        lineStyle: { color: themeColors.primary },
        itemStyle: { color: themeColors.primary }
      }]
    })
  }
  
  if (requestChartRef.value) {
    requestChart = echarts.init(requestChartRef.value)
    requestChart.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: {
        type: 'category',
        data: [],
        axisLabel: { color: themeColors.textSecondary }
      },
      yAxis: {
        type: 'value',
        name: '请求次数',
        axisLabel: { color: themeColors.textSecondary }
      },
      series: [{
        name: '请求次数',
        type: 'bar',
        data: [],
        itemStyle: { color: themeColors.info }
      }]
    })
  }
}

// Update latency chart
function updateLatencyChart(history) {
  if (!latencyChart) return
  
  const times = history.map(h => new Date(h.timestamp).toLocaleTimeString())
  const values = history.map(h => h.response_time_ms)
  
  latencyChart.setOption({
    xAxis: { data: times },
    series: [{ data: values }]
  })
}

// Update request chart
function updateRequestChart(history) {
  if (!requestChart) return
  
  // Aggregate by hour
  const hourCounts = {}
  history.forEach(h => {
    const hour = new Date(h.timestamp).toLocaleDateString() + ' ' + new Date(h.timestamp).getHours() + ':00'
    hourCounts[hour] = (hourCounts[hour] || 0) + 1
  })
  
  const times = Object.keys(hourCounts).slice(-24)
  const values = times.map(t => hourCounts[t])
  
  requestChart.setOption({
    xAxis: { data: times },
    series: [{ data: values }]
  })
}

// Utility functions
function formatMs(ms) {
  if (!ms) return '0ms'
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

function formatNumber(num) {
  if (!num) return '0'
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`
  return num.toString()
}

function formatPercent(pct) {
  if (!pct) return '0%'
  return `${pct.toFixed(1)}%`
}

function getLatencyClass(ms) {
  if (!ms) return 'text-theme-secondary'
  if (ms < 100) return 'text-[var(--color-success)]'
  if (ms < 500) return 'text-[var(--color-info)]'
  if (ms < 1000) return 'text-[var(--color-warning)]'
  return 'text-[var(--color-bull)]'
}

// Resize handler
function handleResize() {
  if (latencyChart) latencyChart.resize()
  if (requestChart) requestChart.resize()
}

// Lifecycle
onMounted(async () => {
  initCharts()
  await fetchMetrics()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  if (latencyChart) {
    latencyChart.dispose()
    latencyChart = null
  }
  if (requestChart) {
    requestChart.dispose()
    requestChart = null
  }
})
</script>

<style scoped>
.performance-panel {
  min-height: 400px;
}

.panel-header {
  border-bottom: 1px solid var(--border-base);
  padding-bottom: 1rem;
  margin-bottom: 1rem;
}

.stat-card {
  background: var(--bg-surface-hover);
  padding: 0.75rem;
  border-radius: 0.5rem;
  border: 1px solid var(--border-light);
}
</style>