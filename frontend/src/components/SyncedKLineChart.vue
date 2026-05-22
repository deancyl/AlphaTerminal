<template>
  <div class="relative w-full h-full">
    <!-- Loading skeleton -->
    <div v-if="loading" class="absolute inset-0">
      <Skeleton height="100%" />
    </div>
    
    <!-- Error state -->
    <div v-else-if="error" class="absolute inset-0 flex items-center justify-center p-4">
      <ErrorDisplay 
        :error="error"
        :retry="fetchKline"
      />
    </div>
    
    <!-- Chart -->
    <div 
      v-else
      ref="chartContainer" 
      class="w-full h-full"
    />
  </div>
</template>

<script setup>
import { ref, shallowRef, watch, onMounted, onUnmounted, onDeactivated, nextTick } from 'vue'
import { useECharts } from '@/composables/useECharts.js'
import { apiFetchDeduped } from '@/utils/api.js'
import { getDynamicThemeColors, getDynamicMarketColors } from '@/utils/echartsTheme.js'
import { getSymbolType } from '@/utils/symbols.js'
import { normalizeHistoryData, buildHistoryEndpoint, getTimeoutForAssetType } from '@/utils/historyNormalizer.js'
import Skeleton from '@/components/Skeleton.vue'
import ErrorDisplay from '@/components/f9/ErrorDisplay.vue'

const props = defineProps({
  symbol: { type: String, required: true },
  syncedDate: { type: String, default: null },
  panelIndex: { type: Number, default: 0 },
  lineColor: { type: String, default: null }
})

const emit = defineEmits(['crosshair-move', 'chart-ready', 'chart-error'])

const chartContainer = ref(null)
const { chartInstance, initChart, setOption, dispose, isReady } = useECharts(chartContainer, {
  autoResize: true,
  resizeDelay: 50
})

const klineData = shallowRef([])
const loading = ref(true)
const error = ref(null)
const pendingEmit = ref(null)

async function fetchKline() {
  loading.value = true
  error.value = null

  try {
    const assetType = getSymbolType(props.symbol)
    const endpoint = buildHistoryEndpoint(props.symbol, assetType, { limit: 100 })
    const timeout = getTimeoutForAssetType(assetType)
    
    const response = await apiFetchDeduped(
      `matrix:kline:${props.symbol}:${assetType}`,
      endpoint,
      { timeoutMs: timeout, debounce: 100 }
    )

    klineData.value = normalizeHistoryData(response, assetType)
    
    if (!klineData.value.length) {
      error.value = '暂无数据'
      loading.value = false
      emit('chart-error', { index: props.panelIndex })
      return
    }
    
    loading.value = false
  } catch (e) {
    console.error(`[SyncedKLineChart] Failed to fetch ${props.symbol}:`, e)
    error.value = '暂无数据'
    loading.value = false
    emit('chart-error', { index: props.panelIndex })
  }
}

function buildOption() {
  if (!klineData.value.length) return {}

  const themeColors = getDynamicThemeColors()
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
      sampling: 'lttb',
      progressiveThreshold: 3000,
      progressive: 200
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

        if (!pendingEmit.value) {
          pendingEmit.value = item.date
          requestAnimationFrame(() => {
            if (pendingEmit.value) {
              emit('crosshair-move', pendingEmit.value)
              pendingEmit.value = null
            }
          })
        } else {
          pendingEmit.value = item.date
        }

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
  
  if (error.value || !klineData.value.length) {
    return
  }
  
  await nextTick()
  
  const chart = await initChart()
  if (chart) {
    setOption(buildOption())
    emit('chart-ready', { index: props.panelIndex, chart })
  } else {
    emit('chart-error', { index: props.panelIndex })
  }
})

onDeactivated(() => {
  dispose()
})

onUnmounted(() => {
  dispose()
})
</script>