<template>
  <div class="space-y-4">
    <h2 class="text-lg font-bold text-terminal-accent">同业比较</h2>

    <div v-if="loading" class="text-center py-8 text-terminal-dim">
      加载中...
    </div>

    <div v-else-if="error" class="text-center py-8 text-red-400">
      {{ error }}
    </div>

    <div v-else-if="!data" class="text-center py-8 text-terminal-dim">
      请输入股票代码查询同业比较数据
    </div>

    <div v-else class="space-y-4">
      <!-- 行业信息 -->
      <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
        <div class="text-xs text-terminal-dim mb-1">所属行业</div>
        <div class="text-lg font-bold text-terminal-accent">{{ data.industry || '--' }}</div>
      </div>

      <!-- 同业对比表格 -->
      <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
        <h3 class="text-sm font-bold text-terminal-primary mb-3">同业对比</h3>
        <div v-if="!data.peers?.length" class="text-center py-4 text-terminal-dim">
          暂无同业数据
        </div>
        <div v-else class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-theme-secondary">
                <th class="text-left py-2 px-3 text-terminal-dim font-normal">股票代码</th>
                <th class="text-left py-2 px-3 text-terminal-dim font-normal">股票名称</th>
                <th class="text-right py-2 px-3 text-terminal-dim font-normal">ROE(%)</th>
                <th class="text-right py-2 px-3 text-terminal-dim font-normal">PE</th>
                <th class="text-right py-2 px-3 text-terminal-dim font-normal">PB</th>
                <th class="text-right py-2 px-3 text-terminal-dim font-normal">营收增长(%)</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(peer, idx) in data.peers"
                :key="peer.symbol"
                class="border-b border-theme-secondary/50 hover:bg-theme-hover"
                :class="{ 'bg-terminal-accent/10': peer.symbol === currentSymbol }"
              >
                <td class="py-2 px-3 text-terminal-secondary">{{ peer.symbol }}</td>
                <td class="py-2 px-3 text-terminal-primary font-medium">{{ peer.name }}</td>
                <td class="py-2 px-3 text-right" :class="getMetricClass(peer.roe, 'roe')">
                  {{ formatMetric(peer.roe) }}
                </td>
                <td class="py-2 px-3 text-right" :class="getMetricClass(peer.pe, 'pe')">
                  {{ formatMetric(peer.pe) }}
                </td>
                <td class="py-2 px-3 text-right" :class="getMetricClass(peer.pb, 'pb')">
                  {{ formatMetric(peer.pb) }}
                </td>
                <td class="py-2 px-3 text-right" :class="getMetricClass(peer.revenue_growth, 'growth')">
                  {{ formatMetric(peer.revenue_growth) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 雷达图 -->
      <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-4">
        <h3 class="text-sm font-bold text-terminal-primary mb-3">当前股票 vs 行业平均</h3>
        <div ref="radarChartRef" class="w-full h-80"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { useStockDetail } from '../../composables/useStockDetail'

const props = defineProps({
  data: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
  currentSymbol: { type: String, default: '' }
})

const { formatMetric, getMetricClass } = useStockDetail()

const radarChartRef = ref(null)
let radarChartInstance = null

function renderRadarChart() {
  if (!radarChartRef.value || !props.data?.peers) return
  
  if (radarChartInstance) {
    radarChartInstance.dispose()
  }
  
  radarChartInstance = echarts.init(radarChartRef.value)
  
  const peers = props.data.peers
  const currentStock = peers.find(p => p.symbol === props.currentSymbol)
  
  if (!currentStock) {
    return
  }
  
  const validPeers = peers.filter(p => 
    p.roe !== null && p.pe !== null && p.pb !== null && p.revenue_growth !== null
  )
  
  const avgRoe = validPeers.reduce((sum, p) => sum + p.roe, 0) / validPeers.length
  const avgPe = validPeers.reduce((sum, p) => sum + p.pe, 0) / validPeers.length
  const avgPb = validPeers.reduce((sum, p) => sum + p.pb, 0) / validPeers.length
  const avgGrowth = validPeers.reduce((sum, p) => sum + p.revenue_growth, 0) / validPeers.length
  
  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(15, 23, 42, 0.9)',
      borderColor: '#3b82f6',
      textStyle: { color: '#e2e8f0' }
    },
    legend: {
      data: ['当前股票', '行业平均'],
      textStyle: { color: '#94a3b8' },
      top: 10
    },
    radar: {
      indicator: [
        { name: 'ROE', max: Math.max(currentStock.roe || 0, avgRoe) * 1.2 },
        { name: 'PE', max: Math.max(currentStock.pe || 0, avgPe) * 1.2 },
        { name: 'PB', max: Math.max(currentStock.pb || 0, avgPb) * 1.2 },
        { name: '营收增长', max: Math.max(Math.abs(currentStock.revenue_growth || 0), Math.abs(avgGrowth)) * 1.2 }
      ],
      center: ['50%', '55%'],
      radius: '65%',
      axisName: {
        color: '#94a3b8',
        fontSize: 12
      },
      splitLine: {
        lineStyle: { color: '#334155' }
      },
      splitArea: {
        areaStyle: { color: ['rgba(59, 130, 246, 0.05)', 'rgba(59, 130, 246, 0.1)'] }
      },
      axisLine: {
        lineStyle: { color: '#475569' }
      }
    },
    series: [{
      type: 'radar',
      data: [
        {
          value: [
            currentStock.roe || 0,
            currentStock.pe || 0,
            currentStock.pb || 0,
            currentStock.revenue_growth || 0
          ],
          name: '当前股票',
          lineStyle: { color: '#3b82f6', width: 2 },
          areaStyle: { color: 'rgba(59, 130, 246, 0.3)' },
          itemStyle: { color: '#3b82f6' }
        },
        {
          value: [avgRoe, avgPe, avgPb, avgGrowth],
          name: '行业平均',
          lineStyle: { color: '#10b981', width: 2, type: 'dashed' },
          areaStyle: { color: 'rgba(16, 185, 129, 0.2)' },
          itemStyle: { color: '#10b981' }
        }
      ]
    }]
  }
  
  radarChartInstance.setOption(option)
}

watch(() => props.data, () => {
  nextTick(() => {
    renderRadarChart()
  })
}, { immediate: true })

onMounted(() => {
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  radarChartInstance?.dispose()
})

function handleResize() {
  radarChartInstance?.resize()
}
</script>
