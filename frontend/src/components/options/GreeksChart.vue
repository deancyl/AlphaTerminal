<template>
  <div class="greeks-chart grid grid-cols-2 gap-2 h-[300px]">
    <div v-if="isEmpty" class="col-span-2 empty-state flex items-center justify-center text-secondary">
      暂无Greeks数据
    </div>
    
    <div v-else v-for="greek in greekTypes" :key="greek.name" class="greek-chart">
      <div class="text-xs text-secondary mb-1">{{ greek.label }}</div>
      <div class="chart-container h-[120px]" :ref="el => setChartRef(greek.name, el)"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, markRaw } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  greeksData: { type: Object, default: () => ({ delta: [], gamma: [], theta: [], vega: [] }) },
  atmStrike: { type: Number, default: null }
})

const greekTypes = [
  { name: 'delta', label: 'Delta' },
  { name: 'gamma', label: 'Gamma' },
  { name: 'theta', label: 'Theta' },
  { name: 'vega', label: 'Vega' }
]

const chartRefs = ref({})
const chartInstances = ref({})

function setChartRef(name, el) {
  if (el) chartRefs.value[name] = el
}

const isEmpty = computed(() => 
  Object.values(props.greeksData).every(arr => arr.length === 0)
)

function buildGreekOption(greekName) {
  const data = props.greeksData[greekName] || []
  const callData = data.filter(d => d.isCall).map(d => [d.strike, d.value])
  const putData = data.filter(d => !d.isCall).map(d => [d.strike, d.value])
  
  return markRaw({
    grid: { left: 40, right: 10, top: 10, bottom: 20 },
    xAxis: {
      type: 'value',
      axisLabel: { color: '#9ca3af', fontSize: 10 }
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#9ca3af', fontSize: 10 }
    },
    series: [
      {
        name: 'Call',
        type: 'line',
        data: callData,
        lineStyle: { color: '#ef4444', width: 1 },
        itemStyle: { color: '#ef4444' },
        symbol: 'none'
      },
      {
        name: 'Put',
        type: 'line',
        data: putData,
        lineStyle: { color: '#22c55e', width: 1 },
        itemStyle: { color: '#22c55e' },
        symbol: 'none'
      }
    ],
    markLine: props.atmStrike ? markRaw({
      data: [{ xAxis: props.atmStrike }],
      lineStyle: { color: '#fbbf24', type: 'dashed', width: 1 }
    }) : undefined
  })
}

function initCharts() {
  greekTypes.forEach(greek => {
    const container = chartRefs.value[greek.name]
    if (container && !chartInstances.value[greek.name]) {
      chartInstances.value[greek.name] = echarts.init(container)
      chartInstances.value[greek.name].setOption(buildGreekOption(greek.name))
    }
  })
}

function updateCharts() {
  greekTypes.forEach(greek => {
    if (chartInstances.value[greek.name] && !chartInstances.value[greek.name].isDisposed()) {
      chartInstances.value[greek.name].setOption(buildGreekOption(greek.name))
    }
  })
}

watch(() => props.greeksData, updateCharts, { deep: true })

onMounted(() => {
  if (!isEmpty.value) {
    setTimeout(initCharts, 100)
  }
})

onUnmounted(() => {
  Object.values(chartInstances.value).forEach(chart => {
    if (chart && !chart.isDisposed()) chart.dispose()
  })
})
</script>

<style scoped>
.text-secondary {
  color: var(--text-secondary, #9ca3af);
}
</style>