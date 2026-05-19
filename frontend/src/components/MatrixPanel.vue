<template>
  <div
    class="bg-surface rounded-lg overflow-hidden flex flex-col border border-border-base transition-colors"
    :class="{ 'ring-1 ring-primary': isActive }"
  >
    <header class="flex items-center justify-between px-3 py-2 border-b border-border-base shrink-0">
      <div class="flex items-center gap-2">
        <span
          class="w-2 h-2 rounded-full"
          :style="{ backgroundColor: panel.color }"
        />
        <div>
          <span class="font-medium text-sm text-primary">{{ panel.name }}</span>
          <span class="text-xs text-muted ml-1">{{ panel.description }}</span>
        </div>
      </div>
      <span class="text-xs text-muted font-data">{{ panel.subtitle }}</span>
    </header>
    <div class="flex-1 min-h-0">
      <SyncedKLineChart
        :symbol="panel.symbol"
        :synced-date="syncedDate"
        :panel-index="panelIndex"
        :line-color="panel.color"
        @crosshair-move="$emit('crosshair-move', $event)"
        @chart-ready="$emit('chart-ready', $event)"
      />
    </div>
  </div>
</template>

<script setup>
import SyncedKLineChart from './SyncedKLineChart.vue'

defineProps({
  panel: {
    type: Object,
    required: true
  },
  panelIndex: { type: Number, default: 0 },
  syncedDate: { type: String, default: null },
  isActive: { type: Boolean, default: false }
})

defineEmits(['crosshair-move', 'chart-ready'])
</script>