<template>
  <div class="flex flex-col h-full gap-4">
    <div class="flex items-center justify-between px-1">
      <h2 class="text-xl font-semibold text-primary">市场温度计</h2>
      <div class="flex items-center gap-3">
        <span class="text-sm text-secondary">
          更新: {{ formatTime(lastUpdate) }}
        </span>
        <button 
          @click="refresh" 
          :disabled="loading"
          class="theme-btn"
          :class="{ 'opacity-50 cursor-not-allowed': loading }"
        >
          {{ loading ? '加载中...' : '刷新' }}
        </button>
      </div>
    </div>
    
    <div v-if="error" class="px-4 py-3 rounded bg-danger-bg border border-danger-border text-danger text-sm">
      {{ error }}
    </div>
    
    <div class="flex-1 flex gap-4 min-h-0">
      <div class="flex-1 bg-surface rounded-lg overflow-hidden border border-border-base">
        <div 
          ref="treemapContainer" 
          class="w-full h-full"
          style="min-height: 400px;"
        />
      </div>
      
      <div class="w-80 flex-shrink-0 flex flex-col gap-3 overflow-y-auto pr-1">
        <div v-if="anomalies.length === 0 && !loading" class="text-center text-secondary text-sm py-8">
          暂无异常数据
        </div>
        
        <AnomalyCard
          v-for="anomaly in anomalies"
          :key="anomaly.type"
          :anomaly="anomaly"
          @stock-click="onStockClick"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useECharts } from '@/composables/useECharts.js'
import { useMarketRadar } from '@/composables/useMarketRadar.js'
import { getDynamicThemeColors, getDynamicMarketColors } from '@/utils/echartsTheme.js'
import { onThemeChange } from '@/composables/useTheme.js'
import AnomalyCard from './market/AnomalyCard.vue'

const emit = defineEmits(['stock-click'])

const treemapContainer = ref(null)
const { initChart, setOption, dispose, isReady } = useECharts(treemapContainer, {
  theme: 'dark',
  autoResize: true,
  resizeDelay: 100
})

const {
  treemapData,
  anomalies,
  loading,
  error,
  lastUpdate,
  refresh,
  formatTime
} = useMarketRadar()

let refreshTimer = null

const treemapOption = computed(() => {
  const themeColors = getDynamicThemeColors()
  const marketColors = getDynamicMarketColors()
  
  return {
    backgroundColor: 'transparent',
    tooltip: {
      backgroundColor: themeColors.tooltipBg,
      borderColor: themeColors.tooltipBorder,
      borderWidth: 1,
      padding: [8, 12],
      textStyle: {
        color: themeColors.tooltipText,
        fontSize: 11,
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace'
      },
      extraCssText: 'backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px); border-radius: 6px;',
      formatter: (info) => {
        const data = info.data
        if (!data) return ''
        
        if (data.children) {
          const changeClass = data.change_pct >= 0 ? 'color: ' + marketColors.UP : 'color: ' + marketColors.DOWN
          const changeSign = data.change_pct >= 0 ? '+' : ''
          return `
            <div style="font-weight: 600; margin-bottom: 4px;">${data.name}</div>
            <div style="color: ${themeColors.axisLabel};">市值: ${(data.value / 10000).toFixed(0)}万亿</div>
            <div style="${changeClass}">${changeSign}${data.change_pct?.toFixed(2) || '0.00'}%</div>
          `
        } else {
          const changeClass = data.change_pct >= 0 ? 'color: ' + marketColors.UP : 'color: ' + marketColors.DOWN
          const changeSign = data.change_pct >= 0 ? '+' : ''
          return `
            <div style="font-weight: 600; margin-bottom: 4px;">${data.name}</div>
            <div style="color: ${themeColors.axisLabel};">代码: ${data.symbol}</div>
            <div style="color: ${themeColors.axisLabel};">市值: ${(data.value / 10000).toFixed(0)}万亿</div>
            <div style="${changeClass}">${changeSign}${data.change_pct?.toFixed(2) || '0.00'}%</div>
          `
        }
      }
    },
    series: [{
      type: 'treemap',
      data: treemapData.value,
      roam: false,
      nodeClick: 'link',
      breadcrumb: {
        show: true,
        itemStyle: {
          color: themeColors.primary,
          borderColor: themeColors.primary,
          textStyle: {
            color: themeColors.textInverse
          }
        }
      },
      label: {
        show: true,
        formatter: '{b}',
        fontSize: 11,
        color: themeColors.textPrimary
      },
      upperLabel: {
        show: true,
        height: 30,
        color: themeColors.textPrimary,
        fontSize: 12,
        fontWeight: 'bold'
      },
      itemStyle: {
        borderColor: themeColors.bgBase,
        borderWidth: 1,
        gapWidth: 1
      },
      levels: [
        {
          itemStyle: {
            borderColor: themeColors.borderBase,
            borderWidth: 2,
            gapWidth: 2
          },
          label: {
            fontSize: 13,
            fontWeight: 'bold'
          }
        },
        {
          colorSaturation: [0.35, 0.5],
          itemStyle: {
            borderColorSaturation: 0.6,
            gapWidth: 1
          }
        }
      ]
    }],
    visualMap: {
      show: false,
      min: -10,
      max: 10,
      inRange: {
        color: [marketColors.DOWN, '#fbbf24', marketColors.UP]
      }
    }
  }
})

function onStockClick(stock) {
  emit('stock-click', stock)
}

function updateChart() {
  if (isReady.value && treemapData.value.length > 0) {
    setOption(treemapOption.value, true)
  }
}

watch([treemapData, isReady], () => {
  updateChart()
}, { deep: true })

onThemeChange(() => {
  updateChart()
})

onMounted(async () => {
  await initChart()
  await refresh()
  
  refreshTimer = setInterval(() => {
    refresh()
  }, 60000)
})

onBeforeUnmount(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
  dispose()
})
</script>