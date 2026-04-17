<template>
  <div class="flex flex-col h-full bg-terminal-bg text-terminal-fg font-mono">
    <div class="px-2 py-1 text-xs font-bold text-theme-accent border-b border-theme-secondary shrink-0">
      资金流向 (近30日主力净额)
    </div>

    <div v-if="isLoading" class="flex-1 flex items-center justify-center text-xs text-theme-muted">
      📡 加载中...
    </div>
    <div v-else-if="!hasData" class="flex-1 flex items-center justify-center text-xs text-red-400">
      ⚠️ 暂无资金流向数据
    </div>
    <div v-else ref="chartRef" class="flex-1 w-full min-h-[200px]"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, shallowRef, nextTick } from 'vue'
import * as echarts from 'echarts'
import { useResizeObserver } from '@vueuse/core'
import { apiFetch } from '../utils/api.js'

const chartRef = ref(null)
const chartInstance = shallowRef(null)
const isLoading = ref(true)
const hasData = ref(false)
let timer = null

const renderChart = (dataList) => {
  if (!chartRef.value) return
  if (!chartInstance.value) {
    chartInstance.value = echarts.init(chartRef.value, 'dark')
  }

  const dates = dataList.map(item => item.date)
  const values = dataList.map(item => item.main_net / 100000000) // 转换为亿元

  const option = {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', formatter: '{b}<br/>主力净额: {c} 亿元' },
    grid: { top: 30, right: 10, bottom: 20, left: 50 },
    xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 9, color: '#94a3b8' } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: '#334155', type: 'dashed' } }, axisLabel: { fontSize: 9, color: '#94a3b8' } },
    series: [{
      type: 'bar',
      data: values,
      itemStyle: {
        color: (params) => params.value > 0 ? '#ef4444' : '#22c55e' // A股红涨绿跌
      }
    }]
  }
  chartInstance.value.setOption(option)
}

const loadData = async () => {
  try {
    const res = await apiFetch('/api/v1/market/fund_flow')
    // 兼容不同的返回包裹层
    const items = res?.items || res?.data?.items || res || []
    if (Array.isArray(items) && items.length > 0) {
      hasData.value = true
      await nextTick()
      renderChart(items)
    } else {
      hasData.value = false
    }
  } catch (e) {
    console.error('FundFlow fetch error:', e)
    hasData.value = false
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
  loadData()
  timer = setInterval(loadData, 5 * 60 * 1000)

  useResizeObserver(chartRef, (entries) => {
    const { width, height } = entries[0].contentRect
    if (width > 0 && height > 0 && chartInstance.value) {
      chartInstance.value.resize()
    }
  })
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
  if (chartInstance.value) chartInstance.value.dispose()
})
</script>