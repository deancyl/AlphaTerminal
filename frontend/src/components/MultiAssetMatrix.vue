<template>
  <Teleport to="body">
    <Transition name="matrix-modal">
      <div
        v-if="show"
        class="fixed inset-0 z-[var(--z-modal)] bg-base flex flex-col"
        role="dialog"
        aria-modal="true"
        aria-labelledby="matrix-title"
      >
        <header class="flex items-center justify-between px-4 py-3 border-b border-border-base shrink-0">
          <h2 id="matrix-title" class="text-lg font-semibold text-primary">多品种联动矩阵</h2>
          <div class="flex items-center gap-3">
            <span v-if="!isMobile" class="text-xs text-muted px-2 py-1 rounded bg-surface-hover">F8 · ESC关闭</span>
            <button
              @click="close"
              class="w-8 h-8 flex items-center justify-center rounded hover:bg-surface-hover transition-colors min-w-[44px] min-h-[44px]"
              aria-label="关闭矩阵"
            >
              <svg class="w-5 h-5 text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </header>

        <!-- Panel relationship guidance -->
        <div class="px-4 py-2 bg-surface-hover/50 border-b border-border-base">
          <div class="flex items-start gap-2">
            <span class="text-sm">📊</span>
            <div class="text-xs text-muted">
              <p class="font-medium text-secondary mb-1">四屏联动分析</p>
              <p>观察四大资产的相关性：股市上涨+国债下跌=风险偏好上升；期货升水=看涨预期；汇率贬值=资本外流压力</p>
            </div>
          </div>
        </div>

        <!-- Desktop: 2x2 Grid -->
        <div v-if="!isMobile" class="flex-1 grid grid-cols-2 grid-rows-2 gap-1 p-1 min-h-0 overflow-hidden">
          <MatrixPanel
            v-for="(panel, idx) in panels"
            :key="panel.symbol"
            :panel="panel"
            :panel-index="idx"
            :synced-date="syncedDate"
            :is-active="activePanel === idx"
            @crosshair-move="onCrosshairMove(idx, $event)"
            @chart-ready="registerChart(idx, $event.chart)"
            @chart-error="handleChartError(idx)"
          />
        </div>

        <!-- Mobile: Single panel with swipe navigation -->
        <div v-else class="flex-1 flex flex-col min-h-0 overflow-hidden">
          <!-- Mobile: Panel tabs -->
          <div class="flex items-center gap-1 px-2 py-2 border-b border-border-base overflow-x-auto">
            <button
              v-for="(panel, idx) in panels"
              :key="panel.symbol"
              @click="currentPanelIndex = idx"
              class="px-3 py-2 rounded-lg text-xs font-medium whitespace-nowrap transition-colors min-h-[44px]"
              :class="currentPanelIndex === idx 
                ? 'bg-primary text-white' 
                : 'bg-surface text-secondary hover:bg-surface-hover'"
            >
              {{ panel.name }}
            </button>
          </div>

          <!-- Mobile: Current panel -->
          <div class="flex-1 min-h-0 overflow-hidden">
            <MatrixPanel
              :key="currentPanel.symbol"
              :panel="currentPanel"
              :panel-index="currentPanelIndex"
              :synced-date="syncedDate"
              :is-active="true"
              :disable-crosshair-sync="true"
              @crosshair-move="onCrosshairMove(currentPanelIndex, $event)"
              @chart-ready="registerChart(currentPanelIndex, $event.chart)"
              @chart-error="handleChartError(currentPanelIndex)"
            />
          </div>

          <!-- Mobile: Navigation buttons -->
          <div class="flex items-center justify-between px-4 py-3 border-t border-border-base">
            <button
              @click="prevPanel"
              :disabled="currentPanelIndex === 0"
              class="flex items-center gap-2 px-4 py-2 rounded-lg bg-surface text-secondary
                     hover:bg-surface-hover disabled:opacity-30 disabled:cursor-not-allowed min-h-[44px]"
            >
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
              </svg>
              <span class="text-sm">上一个</span>
            </button>
            
            <span class="text-sm text-muted">
              {{ currentPanelIndex + 1 }} / {{ panels.length }}
            </span>
            
            <button
              @click="nextPanel"
              :disabled="currentPanelIndex === panels.length - 1"
              class="flex items-center gap-2 px-4 py-2 rounded-lg bg-surface text-secondary
                     hover:bg-surface-hover disabled:opacity-30 disabled:cursor-not-allowed min-h-[44px]"
            >
              <span class="text-sm">下一个</span>
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>
        </div>

        <footer class="flex items-center justify-between px-4 py-2 border-t border-border-base shrink-0">
          <div class="flex items-center gap-2">
            <span class="text-sm text-secondary">同步时间:</span>
            <span class="font-data text-sm text-primary tabular-nums">
              {{ syncedDate || '--' }}
            </span>
          </div>
          
          <Tooltip 
            content="在任一图表移动鼠标，其他图表会自动同步显示相同日期的数据"
            position="top"
          >
            <div class="flex items-center gap-1 text-xs text-muted cursor-help">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>十字光标联动</span>
            </div>
          </Tooltip>
        </footer>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, shallowRef, defineAsyncComponent, computed, watch, onDeactivated } from 'vue'
import { useBreakpoints, breakpointsTailwind } from '@vueuse/core'
import { useCrosshairSync, connectCharts, disconnectCharts } from '@/composables/useCrosshairSync.js'
import Tooltip from '@/components/Tooltip.vue'

const MatrixPanel = defineAsyncComponent(() => import('./MatrixPanel.vue'))

// Mobile detection
const breakpoints = useBreakpoints(breakpointsTailwind)
const isMobile = breakpoints.smaller('md') // < 768px

// Mobile: Current panel index for swipe navigation
const currentPanelIndex = ref(0)

const props = defineProps({
  show: { type: Boolean, default: false }
})

const emit = defineEmits(['close'])

const panels = ref([
  { symbol: 'sh000001', name: '上证指数', subtitle: 'sh000001', color: '#3b82f6', description: 'A股市场风向标' },
  { symbol: 'bond10y', name: '十年期国债', subtitle: 'bond10y', color: '#10b981', description: '无风险利率基准' },
  { symbol: 'IF', name: '沪深300期货', subtitle: 'IF', color: '#f59e0b', description: '股指期货主力合约' },
  { symbol: 'USDCNY', name: '人民币汇率', subtitle: 'USDCNY', color: '#8b5cf6', description: '美元兑人民币即期汇率' }
])

// Mobile: Current panel
const currentPanel = computed(() => panels.value[currentPanelIndex.value])

const { syncedDate, activePanel, onCrosshairMove, resetSync } = useCrosshairSync()
const chartInstances = shallowRef([])

// Loading and error tracking
const loadingCount = ref(0)
const failedCount = ref(0)
const chartsConnected = ref(false)

function registerChart(idx, chart) {
  chartInstances.value[idx] = chart
  loadingCount.value++

  // Connect charts when all 4 are ready (desktop only)
  if (!isMobile.value && loadingCount.value === 4 && !chartsConnected.value) {
    connectCharts(chartInstances.value)
    chartsConnected.value = true
  }
}

function handleChartError(idx) {
  failedCount.value++
}

function retryAll() {
  loadingCount.value = 0
  failedCount.value = 0
  chartInstances.value = []
  chartsConnected.value = false
  // Force re-render by toggling show
  emit('close')
  setTimeout(() => {
    // Parent will re-open
  }, 100)
}

// Mobile: Swipe navigation
function prevPanel() {
  currentPanelIndex.value = Math.max(0, currentPanelIndex.value - 1)
}

function nextPanel() {
  currentPanelIndex.value = Math.min(panels.value.length - 1, currentPanelIndex.value + 1)
}

function close() {
  chartInstances.value.forEach(chart => {
    if (chart && !chart.isDisposed?.()) {
      chart.dispatchAction({ type: 'hideTip' })
    }
  })
  disconnectCharts()
  chartsConnected.value = false
  resetSync()
  emit('close')
}

// KeepAlive cleanup - called when component is deactivated (tab switch, modal close, etc.)
onDeactivated(() => {
  disconnectCharts()
  chartsConnected.value = false
  chartInstances.value.forEach(chart => {
    if (chart && !chart.isDisposed?.()) {
      chart.dispose()
    }
  })
  chartInstances.value = []
  resetSync()
})

// Watch show prop to handle cleanup when modal closes
watch(() => props.show, (newShow) => {
  if (!newShow) {
    disconnectCharts()
    chartsConnected.value = false
  }
})
</script>

<style scoped>
.matrix-modal-enter-active,
.matrix-modal-leave-active {
  transition: opacity var(--duration-normal) var(--easing-default);
}

.matrix-modal-enter-from,
.matrix-modal-leave-to {
  opacity: 0;
}
</style>