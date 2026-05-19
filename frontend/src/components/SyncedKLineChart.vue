<template>
  <div class="relative w-full h-full">
    <div ref="chartContainer" class="w-full h-full" />
    <div v-if="loading" class="absolute inset-0 flex items-center justify-center bg-surface/50">
      <div class="skeleton w-3/4 h-3/4 rounded" />
    </div>
    <div v-else-if="error" class="absolute inset-0 flex items-center justify-center">
      <span class="text-sm text-muted">{{ error }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, shallowRef, watch, onMounted, onUnmounted } from 'vue'
import { useECharts } from '@/composables/useECharts.js'
import { apiFetchDeduped } from '@/utils/api.js'
import { getDynamicThemeColors, getDynamicMarketColors } from '@/utils/echartsTheme.js'

const props = defineProps({
  symbol: { type: String, required: true },
  syncedDate: { type: String, default: null },
  panelIndex: { type: Number, default: 0 },
  lineColor: { type: String, default: null }
})

const emit = defineEmits(['crosshair-move', 'chart-ready'])

const chartContainer = ref(null)
const { chartInstance, initChart, setOption, dispose, isReady } = useECharts(chartContainer, {
  autoResize: true,
  resizeDelay: 50
})

const klineData = shallowRef([])
const loading = ref(true)
const error = ref(null)

async function fetchKline() {
  loading.value = true
  error.value = null

  try {
    const response = await apiFetchDeduped(
      `matrix:kline:${props.symbol}`,
      `/api/v1/market/history/${props.symbol}`,
      { timeoutMs: 10000, debounce: 100 }
    )

    klineData.value = response?.data?.history || response?.history || []
    loading.value = false
  } catch (e) {
    error.value = '加载失败'
    loading.value = false
  }
}

function buildOption() {
  if (!klineData.value.length) return {}

  const themeColors = getDynamicThemeColors()
  const marketColors = getDynamicMarketColors()
  const lineColor = props.lineColor || themeColors.primary || '#3b82f6'

  const dates = klineData.value.map(d => d.date)
  const closes = klineData.value.map(d => d.close)

  return {
    animation: false,
    backgroundColor: 'transparent',
    grid: {
      left: 50,
      right: 20,
      top: 20,
      bottom: 30
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { lineStyle: { color: 'var(--border-base)' } },
      axisLabel: {
        show: true,
        color: 'var(--text-muted)',
        fontSize: 10,
        interval: Math.floor(dates.length / 5)
      },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      splitLine: {
        lineStyle: { color: 'var(--border-light)', type: 'dashed' }
      },
      axisLine: { show: false },
      axisLabel: {
        color: 'var(--text-muted)',
        fontSize: 10,
        formatter: (val) => val.toFixed(2)
      }
    },
    series: [{
      type: 'line',
      data: closes,
      smooth: true,
      symbol: 'none',
      lineStyle: { color: lineColor, width: 2 },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: `${lineColor}40` },
            { offset: 1, color: `${lineColor}05` }
          ]
        }
      },
      sampling: 'lttb'
    }],
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'var(--bg-surface)',
      borderColor: 'var(--border-base)',
      borderWidth: 1,
      textStyle: { color: 'var(--text-primary)', fontSize: 12 },
      formatter: (params) => {
        if (!params || !params[0]) return ''
        const idx = params[0].dataIndex
        const item = klineData.value[idx]
        if (!item) return ''

        emit('crosshair-move', item.date)

        const change = item.close - item.open
        const changePct = ((change / item.open) * 100).toFixed(2)
        const color = change >= 0 ? 'var(--color-bull)' : 'var(--color-bear)'

        return `
          <div class="font-data">
            <div class="text-secondary text-xs mb-1">${item.date}</div>
            <div class="text-lg font-medium">${item.close?.toFixed(2)}</div>
            <div style="color: ${color}" class="text-sm">
              ${change >= 0 ? '+' : ''}${changePct}%
            </div>
          </div>
        `
      }
    },
    axisPointer: {
      lineStyle: { color: 'var(--color-primary)', width: 1, type: 'dashed' }
    }
  }
}

watch(() => props.syncedDate, (date) => {
  if (!date || !chartInstance.value || !isReady.value) return

  const idx = klineData.value.findIndex(d => d.date === date)
  if (idx >= 0) {
    chartInstance.value.dispatchAction({
      type: 'showTip',
      seriesIndex: 0,
      dataIndex: idx
    })
  }
})

onMounted(async () => {
  await fetchKline()
  const chart = await initChart()
  if (chart && klineData.value.length) {
    setOption(buildOption())
    emit('chart-ready', { index: props.panelIndex, chart })
  }
})

onUnmounted(() => {
  dispose()
})
</script>
