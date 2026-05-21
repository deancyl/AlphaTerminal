<template>
  <div class="iv-smile-chart h-[200px] w-full" ref="chartContainer">
    <div v-if="isEmpty" class="empty-state flex items-center justify-center h-full text-secondary">
      暂无IV数据
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, markRaw } from 'vue'
import * as echarts from 'echarts'
import { useECharts } from '../../composables/useECharts.js'

const props = defineProps({
  ivSmileData: { type: Object, default: () => ({ calls: [], puts: [] }) },
  atmStrike: { type: Number, default: null }
})

const chartContainer = ref(null)
const { initChart, setOption, dispose } = useECharts(chartContainer)

const isEmpty = computed(() => 
  props.ivSmileData.calls.length === 0 && props.ivSmileData.puts.length === 0
)

function buildOption() {
  return markRaw({
    grid: { left: 50, right: 20, top: 20, bottom: 30 },
    xAxis: {
      type: 'value',
      name: '行权价',
      nameLocation: 'middle',
      nameGap: 25,
      axisLabel: { color: '#9ca3af', fontSize: 10 }
    },
    yAxis: {
      type: 'value',
      name: 'IV (%)',
      nameLocation: 'middle',
      nameGap: 35,
      axisLabel: { color: '#9ca3af', fontSize: 10, formatter: '{value}%' }
    },
    series: [
      {
        name: 'Call IV',
        type: 'line',
        data: props.ivSmileData.calls,
        lineStyle: { color: '#ef4444', width: 2 },
        itemStyle: { color: '#ef4444' },
        smooth: true,
        symbol: 'none'
      },
      {
        name: 'Put IV',
        type: 'line',
        data: props.ivSmileData.puts,
        lineStyle: { color: '#22c55e', width: 2 },
        itemStyle: { color: '#22c55e' },
        smooth: true,
        symbol: 'none'
      }
    ],
    markLine: props.atmStrike ? markRaw({
      data: [{ xAxis: props.atmStrike }],
      lineStyle: { color: '#fbbf24', type: 'dashed' },
      label: { formatter: 'ATM', color: '#fbbf24' }
    }) : undefined,
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        if (!params || params.length === 0) return ''
        const strike = params[0]?.data?.[0] || params[0]?.axisValue
        return `行权价: ${strike}<br/>` + 
          params.map(p => `${p.seriesName}: ${p.data?.[1]?.toFixed(1)}%`).join('<br/>')
      }
    }
  })
}

watch([() => props.ivSmileData, () => props.atmStrike], () => {
  if (!isEmpty.value) {
    setOption(buildOption())
  }
}, { deep: true })

onMounted(async () => {
  if (!isEmpty.value) {
    const chart = await initChart()
    if (chart) setOption(buildOption())
  }
})

onUnmounted(() => dispose())
</script>

<style scoped>
.text-secondary {
  color: var(--text-secondary, #9ca3af);
}
</style>