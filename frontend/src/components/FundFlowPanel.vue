<script setup>
import { ref, onMounted, onUnmounted, shallowRef, nextTick } from 'vue'
import * as echarts from 'echarts'
import { useResizeObserver } from '@vueuse/core'
import { apiFetch } from '../utils/api.js'
import { logger } from '../utils/logger.js'

const chartRef = ref(null)
const chartInstance = shallowRef(null)
const isLoading = ref(true)
const hasData = ref(false)
let timer = null

const renderChart = (dataList) => {
  if (!chartRef.value || !dataList.length) return
  if (!chartInstance.value) {
    chartInstance.value = echarts.init(chartRef.value, 'dark')
  }
  const dates = dataList.map(item => item.date)
  const values = dataList.map(item => (item.main_net || 0) / 100000000)
  const option = {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { top: '15%', right: '5%', bottom: '15%', left: '15%' },
    xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 9, color: '#94a3b8' } },
    yAxis: { type: 'value', axisLabel: { fontSize: 9, color: '#94a3b8' }, splitLine: { lineStyle: { color: '#334155' } } },
    series: [{
      name: '主力净额(亿)',
      type: 'bar',
      data: values,
      itemStyle: { color: (p) => p.value > 0 ? '#ef4444' : '#22c55e' }
    }]
  }
  chartInstance.value.setOption(option)
  chartInstance.value.resize()
}

const loadData = async () => {
  try {
    const res = await apiFetch('/api/v1/market/fund_flow')
    const items = res?.items || res?.data?.items || (Array.isArray(res) ? res : [])
    if (items.length > 0) {
      hasData.value = true
      await nextTick()
      renderChart(items)
    } else {
      hasData.value = false
    }
  } catch (e) {
    logger.error('[FundFlow] Fetch failed', e)
    hasData.value = false
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
  loadData()
  timer = setInterval(loadData, 300000)
  useResizeObserver(chartRef, (entries) => {
    if (chartInstance.value && entries[0].contentRect.width > 0) chartInstance.value.resize()
  })
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
  if (chartInstance.value) chartInstance.value.dispose()
})
</script>

<template>
  <div class="flex flex-col h-full bg-terminal-panel">
    <div class="p-2 text-xs font-bold text-theme-accent border-b border-theme-secondary shrink-0">资金流向 (近30日)</div>
    <div v-if="isLoading" class="flex-1 flex items-center justify-center text-xs text-theme-muted">📡 数据加载中...</div>
    <div v-else-if="!hasData" class="flex-1 flex items-center justify-center text-xs text-red-400">⚠️ 接口数据为空</div>
    <div v-else ref="chartRef" class="flex-1 w-full min-h-[150px]"></div>
  </div>
</template>