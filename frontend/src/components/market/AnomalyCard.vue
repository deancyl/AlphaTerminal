<template>
  <div 
    class="bg-surface rounded-lg p-4 border border-border-base transition-all"
    :class="{ 'hover:border-border-hover': true }"
  >
    <div class="flex items-center justify-between mb-3">
      <h4 class="font-semibold text-primary">{{ anomaly.title }}</h4>
      <span class="text-xs text-secondary px-2 py-1 rounded bg-surface-hover">TOP 5</span>
    </div>
    
    <div class="space-y-2">
      <div
        v-for="(stock, index) in anomaly.stocks"
        :key="stock.symbol"
        class="flex items-center justify-between p-2 rounded hover:bg-surface-hover cursor-pointer transition-colors"
        tabindex="0"
        @click="$emit('stock-click', stock)"
        @keydown.enter="$emit('stock-click', stock)"
        @keydown.space.prevent="$emit('stock-click', stock)"
      >
        <div class="flex items-center gap-2">
          <span class="text-xs text-muted w-4 tabular-nums">{{ index + 1 }}</span>
          <span class="font-medium text-primary">{{ stock.name }}</span>
          <span class="text-xs text-muted">{{ stock.symbol }}</span>
        </div>
        <span 
          :class="getValueClass(stock.value)" 
          class="font-data text-sm tabular-nums"
        >
          {{ formatValue(stock.value, anomaly.type) }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  anomaly: {
    type: Object,
    required: true,
    validator: (val) => {
      return val.title && val.type && Array.isArray(val.stocks)
    }
  }
})

defineEmits(['stock-click'])

function getValueClass(value) {
  if (value > 0) return 'text-bull'
  if (value < 0) return 'text-bear'
  return 'text-primary'
}

function formatValue(value, type) {
  if (value === null || value === undefined) return '--'
  
  switch (type) {
    case 'volatility':
      return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`
    case 'capital_outflow':
      return `${value >= 0 ? '+' : ''}${value.toFixed(2)}亿`
    case 'institution_research':
      return `${value}次`
    case 'new_high':
      return `${value.toFixed(1)}周`
    case 'volume_surge':
      return `${value.toFixed(1)}倍`
    case 'limit_up':
      return `${value.toFixed(2)}%`
    case 'limit_down':
      return `${value.toFixed(2)}%`
    case 'turnover_rate':
      return `${value.toFixed(2)}%`
    default:
      return typeof value === 'number' ? value.toFixed(2) : String(value)
  }
}
</script>