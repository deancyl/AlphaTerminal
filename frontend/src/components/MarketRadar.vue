<template>
  <div class="flex flex-col h-full gap-4">
    <div class="flex items-center justify-between px-1">
      <div>
        <h2 class="text-xl font-semibold text-primary">市场温度计</h2>
        <p class="text-xs text-secondary mt-1">市场温度图：方块大小=市值，颜色=涨跌幅（红涨绿跌）</p>
      </div>
      <div class="flex items-center gap-3">
        <!-- P1-5: Data source indicator -->
        <div v-if="dataSource" class="flex items-center gap-2 text-xs text-secondary">
          <span class="px-2 py-1 rounded bg-surface-hover border border-border-base">
            {{ dataSource.name }}
          </span>
          <span :class="dataSource.type === '实时' ? 'text-bull' : 'text-muted'">
            {{ dataSource.type }}
          </span>
        </div>
        <!-- P2-8: Refresh interval selector -->
        <select 
          v-model="selectedRefreshInterval"
          @change="onRefreshIntervalChange"
          class="text-xs bg-surface border border-border-base rounded px-2 py-1 text-primary focus:outline-none focus:border-primary"
          aria-label="刷新间隔"
        >
          <option v-for="opt in refreshIntervalOptions" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
        <span class="text-sm text-secondary">
          更新: {{ formatTime(lastUpdate) }}
        </span>
        <button 
          @click="refresh" 
          :disabled="loading"
          class="theme-btn min-h-[44px] px-4"
          :class="{ 'opacity-50 cursor-not-allowed': loading }"
        >
          {{ loading ? '加载中...' : '刷新' }}
        </button>
      </div>
    </div>
    
    <div v-if="error" class="px-4 py-3 rounded bg-danger-bg border border-danger-border text-danger text-sm flex items-center justify-between">
      <span>{{ error }}</span>
      <button 
        @click="refresh" 
        class="theme-btn px-3 py-1 text-xs"
      >
        重试
      </button>
    </div>
    
    <!-- Desktop: Side-by-side layout -->
    <div v-if="!isMobile" class="flex-1 flex gap-4 min-h-0">
      <div class="flex-1 bg-surface rounded-lg overflow-hidden border border-border-base relative">
        <!-- Treemap chart - always in DOM for ref availability -->
        <div 
          ref="treemapContainer" 
          class="w-full h-full"
          style="min-height: 400px;"
          tabindex="0"
          role="img"
          aria-label="市场温度图，显示各板块市值和涨跌幅分布"
          @keydown.enter="handleTreemapKeyboard"
          @keydown.space.prevent="handleTreemapKeyboard"
        />
        <!-- Skeleton loading overlay -->
        <div v-if="loading && treemapData.length === 0" class="absolute inset-0 z-10 flex items-center justify-center bg-surface">
          <Skeleton class="w-full h-full" />
        </div>
        <!-- Empty state overlay -->
        <div v-else-if="!loading && treemapData.length === 0" class="absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 bg-surface">
          <p class="text-secondary">暂无市场数据</p>
          <button 
            @click="refresh" 
            class="theme-btn px-4 py-2 text-sm"
          >
            重新加载
          </button>
        </div>
      </div>
      
      <div class="w-80 flex-shrink-0 flex flex-col gap-3 overflow-y-auto pr-1">
        <!-- Temperature Gauge -->
        <TemperatureGauge :temperature="temperature" />
        
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
    
    <!-- Mobile: Stacked layout -->
    <div v-else class="flex-1 flex flex-col gap-3 min-h-0 overflow-hidden">
      <!-- Mobile: Temperature Gauge (compact) -->
      <TemperatureGauge :temperature="temperature" />
      
      <!-- Mobile: Treemap (P1-6: Increased height from 250px to 350px) -->
      <div class="bg-surface rounded-lg overflow-hidden border border-border-base relative" style="min-height: 350px; max-height: 45%;">
        <!-- Treemap chart - always in DOM for ref availability -->
        <div 
          ref="treemapContainer" 
          class="w-full h-full"
          tabindex="0"
          role="img"
          aria-label="市场温度图，显示各板块市值和涨跌幅分布"
        />
        <!-- Skeleton loading overlay -->
        <div v-if="loading && treemapData.length === 0" class="absolute inset-0 z-10 flex items-center justify-center bg-surface">
          <Skeleton class="w-full h-full" />
        </div>
        <!-- Empty state overlay -->
        <div v-else-if="!loading && treemapData.length === 0" class="absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 bg-surface">
          <p class="text-secondary">暂无市场数据</p>
          <button 
            @click="refresh" 
            class="theme-btn px-4 py-2 text-sm"
          >
            重新加载
          </button>
        </div>
      </div>
      
      <!-- Mobile: Anomaly cards (scrollable) -->
      <div class="flex-1 flex flex-col gap-2 overflow-y-auto min-h-0">
        <div class="text-xs text-secondary font-medium px-1">异常监测</div>
        <div v-if="anomalies.length === 0 && !loading" class="text-center text-secondary text-sm py-8">
          暂无异常数据
        </div>
        
        <div class="flex flex-col gap-2">
          <AnomalyCard
            v-for="anomaly in anomalies"
            :key="anomaly.type"
            :anomaly="anomaly"
            @stock-click="onStockClick"
          />
        </div>
      </div>
    </div>
    
    <!-- P2-9: Drill-Down Modal -->
    <Teleport to="body">
      <div 
        v-if="showDrillDown" 
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
        @click.self="closeDrillDown"
      >
        <div 
          class="bg-surface rounded-lg border border-border-base shadow-xl max-w-2xl w-full mx-4 max-h-[80vh] overflow-hidden"
          role="dialog"
          aria-modal="true"
          aria-labelledby="drill-down-title"
        >
          <div class="flex items-center justify-between p-4 border-b border-border-base">
            <h3 id="drill-down-title" class="text-lg font-semibold text-primary">
              {{ drillDownSector?.name || '板块详情' }}
            </h3>
            <button 
              @click="closeDrillDown"
              class="text-secondary hover:text-primary transition-colors"
              aria-label="关闭"
            >
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          
          <div class="p-4 overflow-hidden" style="height: calc(80vh - 60px);">
            <div v-if="drillDownLoading" class="flex items-center justify-center py-8">
              <Skeleton class="w-full h-32" />
            </div>
            <div v-else-if="drillDownStocks.length === 0" class="text-center text-secondary py-8">
              暂无股票数据
            </div>
            <VirtualizedTable
              v-else
              :items="drillDownTableItems"
              :columns="drillDownColumns"
              :loading="drillDownLoading"
              item-size="36"
              empty-text="暂无股票数据"
              @row-click="({ item }) => onDrillDownStockClick(item)"
            >
              <template #cell-symbol="{ item }">
                <span class="text-muted">{{ item.symbol }}</span>
              </template>
              <template #cell-name="{ item }">
                <span class="text-primary">{{ item.name }}</span>
              </template>
              <template #cell-value="{ item }">
                <span class="tabular-nums">{{ item.value?.toFixed(2) || '--' }}</span>
              </template>
              <template #cell-change_pct="{ item }">
                <span class="tabular-nums" :class="item.change_pct >= 0 ? 'text-bull' : 'text-bear'">
                  {{ item.change_pct >= 0 ? '+' : '' }}{{ item.change_pct?.toFixed(2) || '--' }}%
                </span>
              </template>
            </VirtualizedTable>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, onDeactivated, onActivated, watch } from 'vue'
import { useBreakpoints, breakpointsTailwind } from '@vueuse/core'
import { useECharts } from '@/composables/useECharts.js'
import { useMarketRadar, REFRESH_INTERVAL_OPTIONS } from '@/composables/useMarketRadar.js'
import { getDynamicThemeColors, getDynamicMarketColors } from '@/utils/echartsTheme.js'
import { onThemeChange } from '@/composables/useTheme.js'
import AnomalyCard from './market/AnomalyCard.vue'
import TemperatureGauge from './market/TemperatureGauge.vue'
import Skeleton from './Skeleton.vue'
import VirtualizedTable from './VirtualizedTable.vue'

// Mobile detection
const breakpoints = useBreakpoints(breakpointsTailwind)
const isMobile = breakpoints.smaller('md') // < 768px

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
  temperature,
  loading,
  error,
  lastUpdate,
  dataSource,
  refreshInterval,
  refresh,
  formatTime,
  setRefreshInterval,
  startAutoRefresh,
  stopAutoRefresh,
} = useMarketRadar()

// P2-8: Refresh interval selector
const refreshIntervalOptions = REFRESH_INTERVAL_OPTIONS
const selectedRefreshInterval = ref(refreshInterval.value)

function onRefreshIntervalChange() {
  setRefreshInterval(selectedRefreshInterval.value)
}

// P2-9: Drill-Down state
const showDrillDown = ref(false)
const drillDownSector = ref(null)
const drillDownStocks = ref([])
const drillDownLoading = ref(false)

function openDrillDown(sector) {
  drillDownSector.value = sector
  drillDownStocks.value = sector.children || []
  showDrillDown.value = true
}

function closeDrillDown() {
  showDrillDown.value = false
  drillDownSector.value = null
}

function onDrillDownStockClick(stock) {
  emit('stock-click', stock)
  closeDrillDown()
}

// VirtualizedTable column config
const drillDownColumns = [
  { key: 'symbol', label: '代码', width: '100px' },
  { key: 'name', label: '名称', width: '120px' },
  { key: 'value', label: '市值(亿)', width: '100px', align: 'right', format: 'price' },
  { key: 'change_pct', label: '涨跌幅', width: '100px', align: 'right' }
]

// Prepare items with id field for VirtualizedTable
const drillDownTableItems = computed(() => 
  drillDownStocks.value.map(stock => ({
    id: stock.symbol,
    ...stock
  }))
)

// ESC key handler for drill-down modal
function handleDrillDownKeydown(e) {
  if (e.key === 'Escape' && showDrillDown.value) {
    showDrillDown.value = false
  }
}

let chartInstance = ref(null) // P0-3: Store chart instance for cleanup

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
            <div style="color: ${themeColors.axisLabel}; font-size: 10px; margin-top: 4px;">点击查看详情</div>
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
      nodeClick: false, // P2-9: Handle click manually for drill-down
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

// P1-7: Keyboard navigation handler
function handleTreemapKeyboard(event) {
  // Future: Implement keyboard navigation for treemap
  console.log('Treemap keyboard event:', event.key)
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
  const chart = await initChart()
  chartInstance.value = chart // P0-3: Store reference
  await refresh()
  
  // Handle treemap click for drill-down and stock selection
  if (chart) {
    chart.on('click', (params) => {
      if (params.data) {
        // P2-9: If it's a sector (has children), open drill-down modal
        if (params.data.children && params.data.children.length > 0) {
          openDrillDown(params.data)
        }
        // If it's a stock (no children), emit stock-click event
        else if (params.data.symbol) {
          emit('stock-click', {
            symbol: params.data.symbol,
            name: params.data.name
          })
        }
      }
    })
  }
  
  // P2-8: Start auto-refresh with persisted interval
  startAutoRefresh()
  
  // ESC key handler for drill-down modal
  window.addEventListener('keydown', handleDrillDownKeydown)
})

onBeforeUnmount(() => {
  // P2-8: Stop auto-refresh
  stopAutoRefresh()
  
  // P0-3: Remove ECharts event listeners to prevent memory leak
  if (chartInstance.value) {
    chartInstance.value.off('click')
  }
  
  // Remove ESC key handler
  window.removeEventListener('keydown', handleDrillDownKeydown)
  
  dispose()
})

// KeepAlive lifecycle hooks
onDeactivated(() => {
  // 1. Stop auto-refresh timer (CRITICAL - prevents background API calls)
  stopAutoRefresh()
  
  // 2. Remove ECharts click listener
  if (chartInstance.value && !chartInstance.value.isDisposed?.()) {
    chartInstance.value.off('click')
  }
})

onActivated(() => {
  // Resume auto-refresh when component becomes visible
  startAutoRefresh()
  
  // Re-attach click listener if needed
  if (chartInstance.value && !chartInstance.value.isDisposed?.()) {
    chartInstance.value.on('click', (params) => {
      if (params.data) {
        // P2-9: If it's a sector (has children), open drill-down modal
        if (params.data.children && params.data.children.length > 0) {
          openDrillDown(params.data)
        }
        // If it's a stock (no children), emit stock-click event
        else if (params.data.symbol) {
          emit('stock-click', {
            symbol: params.data.symbol,
            name: params.data.name
          })
        }
      }
    })
  }
})
</script>
