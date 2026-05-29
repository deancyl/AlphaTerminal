<template>
  <div class="greeks-chart grid grid-cols-2 gap-2 overflow-hidden">
    <div v-if="isEmpty" class="col-span-2 empty-state flex items-center justify-center h-[280px] text-secondary">
      暂无Greeks数据
    </div>
    
    <template v-else>
      <div v-for="greek in greekTypes" :key="greek.name" class="greek-chart">
        <div class="flex items-center gap-1 mb-1">
          <span class="text-xs text-secondary">{{ greek.label }}</span>
          <EducationalTooltip :term="greek.name" />
        </div>
        <div class="chart-container h-[120px]" :ref="el => setChartRef(greek.name, el)"></div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick, markRaw } from 'vue'
import { useElementSize } from '@vueuse/core'
import EducationalTooltip from './EducationalTooltip.vue'
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
const containerSizes = ref({})

function setChartRef(name, el) {
  if (el) {
    chartRefs.value[name] = el
    const { width, height } = useElementSize(el)
    containerSizes.value[name] = { width, height }
  }
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

async function waitForContainer(name, timeout = 5000) {
  const startTime = Date.now()
  while (Date.now() - startTime < timeout) {
    const size = containerSizes.value[name]
    if (size && size.width.value > 0 && size.height.value > 0) {
      return true
    }
    await nextTick()
  }
  return false
}

async function initCharts() {
  for (const greek of greekTypes) {
    const container = chartRefs.value[greek.name]
    if (!container || chartInstances.value[greek.name]) continue

    const ready = await waitForContainer(greek.name)
    if (!ready) {
      console.warn(`[GreeksChart] Container not ready: ${greek.name}`)
      continue
    }

    chartInstances.value[greek.name] = echarts.init(container)
    chartInstances.value[greek.name].setOption(buildGreekOption(greek.name))
  }
}

function updateCharts() {
  greekTypes.forEach(greek => {
    if (chartInstances.value[greek.name] && !chartInstances.value[greek.name].isDisposed()) {
      chartInstances.value[greek.name].setOption(buildGreekOption(greek.name))
    }
  })
}

watch(() => props.greeksData, updateCharts, { deep: true })

onMounted(async () => {
  if (!isEmpty.value) {
    await initCharts()
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