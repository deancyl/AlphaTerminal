<template>
  <div class="space-y-4">
    <h2 class="text-lg font-bold text-terminal-accent">机构持股</h2>
    
    <div v-if="loading" class="text-center py-8 text-terminal-dim">
      加载中...
    </div>
    
    <div v-else-if="error" class="text-center py-8 text-red-400">
      {{ error }}
    </div>
    
    <div v-else-if="!data" class="text-center py-8 text-terminal-dim">
      请输入股票代码查询
    </div>
    
    <div v-else class="space-y-4">
      <!-- 汇总卡片 -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
          <div class="text-xs text-terminal-dim mb-1">当前季度</div>
          <div class="text-lg font-bold text-terminal-primary">{{ data.quarter || '--' }}</div>
        </div>
        <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
          <div class="text-xs text-terminal-dim mb-1">机构数量</div>
          <div class="text-lg font-bold text-terminal-accent">{{ data.current?.length || 0 }}</div>
        </div>
        <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
          <div class="text-xs text-terminal-dim mb-1">总持股比例</div>
          <div class="text-lg font-bold text-terminal-primary">
            {{ data.trend?.length > 0 ? (data.trend[data.trend.length - 1]?.total_pct || 0).toFixed(2) + '%' : '--' }}
          </div>
        </div>
        <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
          <div class="text-xs text-terminal-dim mb-1">趋势变化</div>
          <div class="text-lg font-bold" :class="trendClass">
            {{ trendText }}
          </div>
        </div>
      </div>
      
      <!-- 饼图：前10大机构持股分布 -->
      <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
        <h3 class="text-sm font-bold text-terminal-primary mb-3">前10大机构持股分布</h3>
        <div ref="pieChartRef" class="w-full h-64"></div>
      </div>
      
      <!-- 持股明细表格 -->
      <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
        <h3 class="text-sm font-bold text-terminal-primary mb-3">持股明细</h3>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-theme-secondary">
                <th class="text-left py-2 px-3 text-terminal-dim font-normal">序号</th>
                <th class="text-left py-2 px-3 text-terminal-dim font-normal">机构名称</th>
                <th class="text-right py-2 px-3 text-terminal-dim font-normal">持股数量(股)</th>
                <th class="text-right py-2 px-3 text-terminal-dim font-normal">持股比例(%)</th>
                <th class="text-right py-2 px-3 text-terminal-dim font-normal">较上期变化</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(holder, index) in topHolders" :key="index" class="border-b border-theme-secondary/50 hover:bg-theme-hover">
                <td class="py-2 px-3 text-terminal-secondary">{{ index + 1 }}</td>
                <td class="py-2 px-3 text-terminal-primary">{{ holder['股东名称'] || holder['机构名称'] || '--' }}</td>
                <td class="py-2 px-3 text-right text-terminal-secondary">{{ formatHolderShares(holder['持股数量']) }}</td>
                <td class="py-2 px-3 text-right text-terminal-secondary">{{ formatHolderPct(holder['持股比例']) }}</td>
                <td class="py-2 px-3 text-right" :class="getChangeClass(holder['增减'])">{{ holder['增减'] || '--' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      
      <!-- 趋势折线图 -->
      <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
        <h3 class="text-sm font-bold text-terminal-primary mb-3">近8季度机构持股趋势</h3>
        <div ref="trendChartRef" class="w-full h-64"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { useStockDetail } from '../../composables/useStockDetail'

const props = defineProps({
  data: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' }
})

const { formatHolderShares, formatHolderPct, getChangeClass } = useStockDetail()

const pieChartRef = ref(null)
const trendChartRef = ref(null)
let pieChartInstance = null
let trendChartInstance = null

const topHolders = computed(() => {
  if (!props.data?.current) return []
  return props.data.current.slice(0, 10)
})

const trendClass = computed(() => {
  if (!props.data?.trend || props.data.trend.length < 2) return 'text-terminal-dim'
  const trend = props.data.trend
  const last = trend[trend.length - 1]?.total_pct || 0
  const prev = trend[trend.length - 2]?.total_pct || 0
  return last >= prev ? 'text-bullish' : 'text-bearish'
})

const trendText = computed(() => {
  if (!props.data?.trend || props.data.trend.length < 2) return '--'
  const trend = props.data.trend
  const last = trend[trend.length - 1]?.total_pct || 0
  const prev = trend[trend.length - 2]?.total_pct || 0
  const diff = last - prev
  return diff >= 0 ? `+${diff.toFixed(2)}%` : `${diff.toFixed(2)}%`
})

function renderPieChart() {
  if (!pieChartRef.value || !props.data?.current) return
  
  if (pieChartInstance) {
    pieChartInstance.dispose()
  }
  
  pieChartInstance = echarts.init(pieChartRef.value)
  
  const holders = props.data.current.slice(0, 10)
  const pieData = holders.map(h => ({
    name: h['股东名称'] || h['机构名称'] || '未知',
    value: parseFloat(h['持股比例']) || 0
  }))
  
  const option = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c}% ({d}%)'
    },
    legend: {
      type: 'scroll',
      orient: 'vertical',
      right: 10,
      top: 20,
      bottom: 20,
      textStyle: {
        color: '#9ca3af',
        fontSize: 11
      }
    },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['40%', '50%'],
      avoidLabelOverlap: false,
      itemStyle: {
        borderRadius: 4,
        borderColor: '#1f2937',
        borderWidth: 2
      },
      label: {
        show: false
      },
      emphasis: {
        label: {
          show: true,
          fontSize: 12,
          fontWeight: 'bold',
          color: '#f3f4f6'
        }
      },
      labelLine: {
        show: false
      },
      data: pieData
    }],
    color: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1']
  }
  
  pieChartInstance.setOption(option)
}

function renderTrendChart() {
  if (!trendChartRef.value || !props.data?.trend) return
  
  if (trendChartInstance) {
    trendChartInstance.dispose()
  }
  
  trendChartInstance = echarts.init(trendChartRef.value)
  
  const trend = props.data.trend
  const quarters = trend.map(t => `${t.year}Q${t.quarter_num}`)
  const counts = trend.map(t => t.count)
  const pcts = trend.map(t => t.total_pct)
  
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross'
      }
    },
    legend: {
      data: ['机构数量', '持股比例(%)'],
      textStyle: {
        color: '#9ca3af'
      }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: quarters,
      axisLabel: {
        color: '#9ca3af',
        fontSize: 11
      },
      axisLine: {
        lineStyle: {
          color: '#374151'
        }
      }
    },
    yAxis: [
      {
        type: 'value',
        name: '机构数量',
        axisLabel: {
          color: '#9ca3af'
        },
        axisLine: {
          lineStyle: {
            color: '#374151'
          }
        },
        splitLine: {
          lineStyle: {
            color: '#374151',
            type: 'dashed'
          }
        }
      },
      {
        type: 'value',
        name: '持股比例(%)',
        axisLabel: {
          color: '#9ca3af'
        },
        axisLine: {
          lineStyle: {
            color: '#374151'
          }
        },
        splitLine: {
          show: false
        }
      }
    ],
    series: [
      {
        name: '机构数量',
        type: 'bar',
        data: counts,
        itemStyle: {
          color: '#3b82f6'
        }
      },
      {
        name: '持股比例(%)',
        type: 'line',
        yAxisIndex: 1,
        data: pcts,
        smooth: true,
        lineStyle: {
          color: '#10b981',
          width: 2
        },
        itemStyle: {
          color: '#10b981'
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(16, 185, 129, 0.3)' },
              { offset: 1, color: 'rgba(16, 185, 129, 0.05)' }
            ]
          }
        }
      }
    ]
  }
  
  trendChartInstance.setOption(option)
}

watch(() => props.data, () => {
  nextTick(() => {
    renderPieChart()
    renderTrendChart()
  })
}, { immediate: true })

onMounted(() => {
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  pieChartInstance?.dispose()
  trendChartInstance?.dispose()
})

function handleResize() {
  pieChartInstance?.resize()
  trendChartInstance?.resize()
}
</script>
