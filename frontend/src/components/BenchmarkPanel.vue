<template>
  <div class="flex flex-col w-full h-full overflow-hidden">
    <!-- 顶部控制栏 -->
    <div class="shrink-0 flex items-center gap-2 px-3 py-1.5 border-b border-theme bg-terminal-panel/80">
      <span class="text-[10px] text-theme-muted">基准指数</span>
      <select
        v-model="benchmark"
        class="bg-theme-tertiary/30 border border-theme rounded-sm px-1.5 py-0.5 text-[10px] text-theme-primary"
      >
        <option value="000300">沪深300</option>
        <option value="000001">上证指数</option>
        <option value="399001">深证成指</option>
        <option value="399006">创业板指</option>
      </select>
      <button
        @click="loadBenchmark"
        :disabled="loading"
        class="ml-auto px-3 py-0.5 rounded-sm text-[10px] font-medium transition-colors"
        :class="loading
          ? 'bg-gray-600/40 text-theme-muted cursor-not-allowed'
          : 'bg-[var(--color-info-bg)] text-[var(--color-info)] hover:bg-[var(--color-info-bg)] border border-[var(--color-info-border)]'"
      >{{ loading ? '⏳ 计算中...' : '🔄 刷新' }}</button>
    </div>

    <!-- 主内容区 -->
    <div v-if="comparison" class="flex-1 min-h-0 overflow-y-auto p-2 space-y-3">
      
      <!-- 核心对比指标 -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-2">
        <div class="rounded-sm border border-theme bg-terminal-panel/60 px-3 py-2">
          <div class="text-[10px] text-theme-muted">组合收益</div>
          <div class="text-[14px] font-mono font-bold" :class="comparison.portfolio_return_pct >= 0 ? 'text-bullish' : 'text-bearish'">
            {{ comparison.portfolio_return_pct >= 0 ? '+' : '' }}{{ comparison.portfolio_return_pct }}%
          </div>
        </div>
        
        <div class="rounded-sm border border-theme bg-terminal-panel/60 px-3 py-2">
          <div class="text-[10px] text-theme-muted">基准收益</div>
          <div class="text-[14px] font-mono font-bold" :class="comparison.benchmark_return_pct >= 0 ? 'text-bullish' : 'text-bearish'">
            {{ comparison.benchmark_return_pct >= 0 ? '+' : '' }}{{ comparison.benchmark_return_pct }}%
          </div>
        </div>
        
        <div class="rounded-sm border border-theme bg-terminal-panel/60 px-3 py-2">
          <div class="text-[10px] text-theme-muted">超额收益(Alpha)</div>
          <div class="text-[14px] font-mono font-bold" :class="comparison.excess_return_pct >= 0 ? 'text-bullish' : 'text-bearish'">
            {{ comparison.excess_return_pct >= 0 ? '+' : '' }}{{ comparison.excess_return_pct }}%
          </div>
        </div>
        
        <div class="rounded-sm border border-theme bg-terminal-panel/60 px-3 py-2">
          <div class="text-[10px] text-theme-muted">跟踪误差</div>
          <div class="text-[14px] font-mono font-bold" :class="comparison.tracking_error_pct < 5 ? 'text-bullish' : 'text-bearish'">
            {{ comparison.tracking_error_pct }}%
          </div>
        </div>
      </div>

      <!-- 收益走势对比图 -->
      <div class="rounded-sm border border-theme bg-terminal-panel/40 p-3">
        <div class="text-[10px] text-theme-muted font-bold mb-2">📈 累计收益对比</div>
        <div ref="chartEl" class="w-full h-[200px]"></div>
      </div>

      <!-- 月度收益对比表 -->
      <div v-if="comparison.monthly_returns && comparison.monthly_returns.length > 0" class="rounded-sm border border-theme bg-terminal-panel/40 p-3">
        <div class="text-[10px] text-theme-muted font-bold mb-2">📅 月度收益对比</div>
        <div class="overflow-x-auto">
          <table class="w-full text-[10px]">
            <thead class="bg-terminal-panel sticky top-0">
              <tr class="text-theme-muted border-b border-theme/20">
                <th class="px-2 py-1 text-left">月份</th>
                <th class="px-2 py-1 text-right">组合</th>
                <th class="px-2 py-1 text-right">基准</th>
                <th class="px-2 py-1 text-right">超额</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="m in comparison.monthly_returns"
                :key="m.month"
                class="border-b border-theme/10 hover:bg-theme-tertiary/20"
              >
                <td class="px-2 py-1 text-theme-primary">{{ m.month }}</td>
                <td class="px-2 py-1 text-right font-mono" :class="m.portfolio_return >= 0 ? 'text-bullish' : 'text-bearish'">
                  {{ m.portfolio_return >= 0 ? '+' : '' }}{{ m.portfolio_return }}%
                </td>
                <td class="px-2 py-1 text-right font-mono" :class="m.benchmark_return >= 0 ? 'text-bullish' : 'text-bearish'">
                  {{ m.benchmark_return >= 0 ? '+' : '' }}{{ m.benchmark_return }}%
                </td>
                <td class="px-2 py-1 text-right font-mono font-bold" :class="m.excess_return >= 0 ? 'text-bullish' : 'text-bearish'">
                  {{ m.excess_return >= 0 ? '+' : '' }}{{ m.excess_return }}%
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 统计指标 -->
      <div class="grid grid-cols-2 md:grid-cols-3 gap-2">
        <div class="rounded-sm border border-theme bg-terminal-panel/60 px-3 py-2">
          <div class="text-[10px] text-theme-muted">信息比率</div>
          <div class="text-[14px] font-mono font-bold" :class="comparison.information_ratio >= 0.5 ? 'text-bullish' : 'text-bearish'">
            {{ comparison.information_ratio >= 0 ? '+' : '' }}{{ comparison.information_ratio }}
          </div>
        </div>
        
        <div class="rounded-sm border border-theme bg-terminal-panel/60 px-3 py-2">
          <div class="text-[10px] text-theme-muted">相关系数</div>
          <div class="text-[14px] font-mono font-bold text-theme-primary">{{ comparison.correlation }}</div>
        </div>
        
        <div class="rounded-sm border border-theme bg-terminal-panel/60 px-3 py-2">
          <div class="text-[10px] text-theme-muted">统计天数</div>
          <div class="text-[14px] font-mono font-bold text-theme-primary">{{ comparison.total_days }}天</div>
        </div>
      </div>

      <!-- 指标说明 -->
      <div class="rounded-sm border border-theme bg-terminal-panel/40 px-3 py-2 space-y-1">
        <div class="text-[10px] text-theme-muted font-bold mb-1">📊 指标说明</div>
        <div class="text-[10px] text-theme-muted leading-relaxed">
          <span class="text-theme-primary">超额收益</span>: 组合收益 - 基准收益，>0跑赢市场 |
          <span class="text-theme-primary">跟踪误差</span>: 组合与基准收益差异的波动率，<5%为紧密跟踪 |
          <span class="text-theme-primary">信息比率</span>: 超额收益/跟踪误差，>0.5优秀
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div
      v-else-if="!loading"
      class="flex-1 flex flex-col items-center justify-center text-theme-muted text-[11px] gap-2"
    >
      <span class="text-xl">📊</span>
      <span>{{ errorMsg || '点击"刷新"加载基准对比分析' }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { apiFetch } from '../utils/api.js'
import { logger } from '../utils/logger.js'

const props = defineProps({
  portfolioId: { type: Number, required: true },
})

const benchmark = ref('000300')
const loading = ref(false)
const comparison = ref(null)
const errorMsg = ref('')
const chartEl = ref(null)
let chart = null

async function loadBenchmark() {
  if (loading.value) return
  loading.value = true
  errorMsg.value = ''
  try {
    const resp = await apiFetch(
      `/api/v1/portfolio/${props.portfolioId}/benchmark?benchmark=${benchmark.value}`
    )
    if (resp?.comparison) {
      comparison.value = resp.comparison
      await nextTick()
      renderChart()
    } else if (resp?.message) {
      errorMsg.value = resp.message
      comparison.value = null
    }
  } catch (e) {
    logger.error('[BenchmarkPanel] loadBenchmark error:', e)
    errorMsg.value = '加载失败'
  } finally {
    loading.value = false
  }
}

function renderChart() {
  if (!chartEl.value || !comparison.value?.daily_data?.length) return
  
  if (chart) { chart.dispose(); chart = null }
  
  const data = comparison.value.daily_data
  const dates = data.map(d => d.date)
  const portfolioReturns = data.map(d => (d.portfolio_cum_return * 100).toFixed(2))
  const benchmarkReturns = data.map(d => (d.benchmark_cum_return * 100).toFixed(2))
  const excessReturns = data.map(d => (d.excess_return * 100).toFixed(2))
  
  const upColor = getComputedStyle(document.documentElement).getPropertyValue('--color-up').trim() || '#FF6B6B'
  const downColor = getComputedStyle(document.documentElement).getPropertyValue('--color-down').trim() || '#51CF66'
  const primaryColor = getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim() || '#0F52BA'
  const chartTextColor = getComputedStyle(document.documentElement).getPropertyValue('--chart-text').trim() || '#8B949E'
  
  chart = window.echarts.init(chartEl.value, 'dark')
  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1e2130', borderColor: '#374151',
      textStyle: { color: '#d1d5db', fontSize: 10 },
    },
    legend: {
      data: ['组合', '基准', '超额'],
      textStyle: { color: chartTextColor, fontSize: 10 },
      top: 0
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '15%', containLabel: true },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { color: chartTextColor, fontSize: 9, rotate: 45 }
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: chartTextColor, fontSize: 10, formatter: '{value}%' }
    },
    series: [
      {
        name: '组合',
        type: 'line',
        data: portfolioReturns,
        smooth: true,
        lineStyle: { color: upColor, width: 2 },
        itemStyle: { color: upColor }
      },
      {
        name: '基准',
        type: 'line',
        data: benchmarkReturns,
        smooth: true,
        lineStyle: { color: primaryColor, width: 2 },
        itemStyle: { color: primaryColor }
      },
      {
        name: '超额',
        type: 'line',
        data: excessReturns,
        smooth: true,
        lineStyle: { color: downColor, width: 1, type: 'dashed' },
        itemStyle: { color: downColor }
      }
    ]
  })
}

watch(() => props.portfolioId, () => {
  comparison.value = null
  loadBenchmark()
}, { immediate: true })

onMounted(() => {
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  if (chart) { chart.dispose(); chart = null }
})

function handleResize() {
  chart?.resize()
}
</script>