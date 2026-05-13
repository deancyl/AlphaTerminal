<template>
  <div class="space-y-4">
    <h2 class="text-lg font-bold text-terminal-accent">融资融券</h2>

    <LoadingSpinner v-if="loading" text="加载融资融券数据..." />

    <ErrorDisplay
      v-else-if="error"
      :error="error"
      :retry="onRetry"
    />

    <div v-else-if="!data" class="text-center py-8 text-terminal-dim">
      请输入股票代码查看融资融券
    </div>

    <div v-else class="space-y-4">
      <!-- 当前融资融券数据卡片 -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <!-- 融资余额 -->
        <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
          <h3 class="text-sm font-bold text-terminal-primary mb-3">融资余额</h3>
          <div class="space-y-2">
            <div>
              <div class="text-xs text-terminal-dim">融资余额</div>
              <div class="text-xl font-bold text-bullish">
                {{ formatMoney(data.current.financing_balance * 10000) }}
              </div>
            </div>
            <div class="grid grid-cols-2 gap-2 text-xs">
              <div>
                <div class="text-terminal-dim">融资买入</div>
                <div class="text-bullish">{{ formatMoney(data.current.financing_buy * 10000) }}</div>
              </div>
              <div>
                <div class="text-terminal-dim">融资偿还</div>
                <div class="text-bearish">{{ formatMoney(data.current.financing_repay * 10000) }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- 融券余额 -->
        <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
          <h3 class="text-sm font-bold text-terminal-primary mb-3">融券余额</h3>
          <div class="space-y-2">
            <div>
              <div class="text-xs text-terminal-dim">融券余额</div>
              <div class="text-xl font-bold text-bearish">
                {{ formatMoney(data.current.lending_balance * 10000) }}
              </div>
            </div>
            <div class="grid grid-cols-2 gap-2 text-xs">
              <div>
                <div class="text-terminal-dim">融券卖出</div>
                <div class="text-bearish">{{ formatVolume(data.current.lending_sell) }}</div>
              </div>
              <div>
                <div class="text-terminal-dim">融券偿还</div>
                <div class="text-bullish">{{ formatVolume(data.current.lending_repay) }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- 融资融券余额 -->
        <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
          <h3 class="text-sm font-bold text-terminal-primary mb-3">融资融券余额</h3>
          <div class="space-y-2">
            <div>
              <div class="text-xs text-terminal-dim">总余额</div>
              <div class="text-xl font-bold text-terminal-accent">
                {{ formatMoney(data.current.total_balance * 10000) }}
              </div>
            </div>
            <div class="text-xs text-terminal-dim">
              更新日期: {{ data.current.date }}
            </div>
          </div>
        </div>
      </div>

      <!-- 30天趋势图 -->
      <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
        <h3 class="text-sm font-bold text-terminal-primary mb-3">30日融资融券趋势</h3>
        <div ref="chartRef" style="height: 400px;"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { getECharts, initChart } from '../../utils/lazyEcharts.js'
import { useStockDetail } from '../../composables/useStockDetail'
import LoadingSpinner from '../f9/LoadingSpinner.vue'
import ErrorDisplay from '../f9/ErrorDisplay.vue'

const props = defineProps({
  data: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' }
})

const emit = defineEmits(['retry'])

const { formatMoney, formatVolume } = useStockDetail()

const chartRef = ref(null)
let chartInstance = null

async function renderChart() {
  if (!chartRef.value || !props.data) return

  if (chartInstance) {
    chartInstance.dispose()
  }

  chartInstance = await initChart(chartRef.value)

  const trend = props.data.trend || []
  const dates = trend.map(d => d.date)
  const financingBalances = trend.map(d => d.financing_balance)
  const lendingBalances = trend.map(d => d.lending_balance)
  const totalBalances = trend.map(d => d.total_balance)

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      },
      backgroundColor: 'rgba(15, 23, 42, 0.9)',
      borderColor: '#3b82f6',
      textStyle: {
        color: '#e2e8f0'
      }
    },
    legend: {
      data: ['融资余额', '融券余额', '总余额'],
      textStyle: {
        color: '#94a3b8'
      },
      top: 10
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: {
        lineStyle: {
          color: '#475569'
        }
      },
      axisLabel: {
        color: '#94a3b8',
        rotate: 45
      }
    },
    yAxis: {
      type: 'value',
      axisLine: {
        lineStyle: {
          color: '#475569'
        }
      },
      axisLabel: {
        color: '#94a3b8',
        formatter: function(value) {
          if (value >= 10000) {
            return (value / 10000).toFixed(0) + '万'
          }
          return value
        }
      },
      splitLine: {
        lineStyle: {
          color: '#334155'
        }
      }
    },
    series: [
      {
        name: '融资余额',
        type: 'bar',
        data: financingBalances,
        itemStyle: {
          color: '#ef4444'
        }
      },
      {
        name: '融券余额',
        type: 'bar',
        data: lendingBalances,
        itemStyle: {
          color: '#22c55e'
        }
      },
      {
        name: '总余额',
        type: 'line',
        data: totalBalances,
        smooth: true,
        lineStyle: {
          color: '#3b82f6',
          width: 2
        },
        itemStyle: {
          color: '#3b82f6'
        },
        symbol: 'circle',
        symbolSize: 6
      }
    ]
  }

  chartInstance.setOption(option)
}

watch(() => props.data, () => {
  nextTick(() => {
    renderChart()
  })
}, { immediate: true })

onMounted(() => {
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
})

function handleResize() {
  chartInstance?.resize()
}

function onRetry() {
  emit('retry')
}
</script>
