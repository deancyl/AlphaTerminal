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
            <span class="text-xs text-muted px-2 py-1 rounded bg-surface-hover">F8 · ESC关闭</span>
            <button
              @click="close"
              class="w-8 h-8 flex items-center justify-center rounded hover:bg-surface-hover transition-colors"
              aria-label="关闭矩阵"
            >
              <svg class="w-5 h-5 text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </header>

        <div class="flex-1 grid grid-cols-2 grid-rows-2 gap-1 p-1 min-h-0 overflow-hidden">
          <MatrixPanel
            v-for="(panel, idx) in panels"
            :key="panel.symbol"
            :panel="panel"
            :panel-index="idx"
            :synced-date="syncedDate"
            :is-active="activePanel === idx"
            @crosshair-move="onCrosshairMove(idx, $event)"
            @chart-ready="registerChart(idx, $event.chart)"
          />
        </div>

        <footer class="flex items-center justify-center px-4 py-2 border-t border-border-base shrink-0">
          <span class="text-sm text-secondary">同步时间:</span>
          <span class="font-data text-sm text-primary ml-2 tabular-nums">
            {{ syncedDate || '移动十字光标以同步' }}
          </span>
        </footer>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, shallowRef, defineAsyncComponent } from 'vue'
import { useCrosshairSync } from '@/composables/useCrosshairSync.js'

const MatrixPanel = defineAsyncComponent(() => import('./MatrixPanel.vue'))

const props = defineProps({
  show: { type: Boolean, default: false }
})

const emit = defineEmits(['close'])

const panels = ref([
  { symbol: 'sh000001', name: '上证指数', subtitle: 'sh000001', color: '#3b82f6' },
  { symbol: 'bond10y', name: '十年期国债', subtitle: 'bond10y', color: '#10b981' },
  { symbol: 'IF', name: '沪深300期货', subtitle: 'IF', color: '#f59e0b' },
  { symbol: 'USDCNY', name: '人民币汇率', subtitle: 'USDCNY', color: '#8b5cf6' }
])

const { syncedDate, activePanel, onCrosshairMove, resetSync } = useCrosshairSync()
const chartInstances = shallowRef([])

function registerChart(idx, chart) {
  chartInstances.value[idx] = chart
}

function close() {
  chartInstances.value.forEach(chart => {
    if (chart && !chart.isDisposed?.()) {
      chart.dispatchAction({ type: 'hideTip' })
    }
  })
  resetSync()
  emit('close')
}
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