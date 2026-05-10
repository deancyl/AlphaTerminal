<template>
  <div class="info-card bg-terminal-panel rounded-lg border border-theme-secondary p-3">
    <div class="text-xs text-terminal-dim mb-1">{{ title }}</div>
    <div class="flex items-baseline gap-1">
      <span class="text-lg font-bold font-mono text-terminal-primary">{{ displayValue }}</span>
      <span v-if="unit" class="text-xs text-terminal-secondary">{{ unit }}</span>
    </div>
    <div v-if="change != null" class="mt-1 flex items-center gap-1">
      <span
        class="text-xs font-mono"
        :class="change >= 0 ? 'text-bullish' : 'text-bearish'"
      >
        {{ change >= 0 ? '+' : '' }}{{ change.toFixed(2) }}%
      </span>
      <span
        v-if="change !== 0"
        class="text-xs"
        :class="change >= 0 ? 'text-bullish' : 'text-bearish'"
      >
        {{ change >= 0 ? '↑' : '↓' }}
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { formatNumber, formatMoney } from '../../utils/formatters.js'

const props = defineProps({
  title: {
    type: String,
    required: true
  },
  value: {
    type: [Number, String],
    default: null
  },
  unit: {
    type: String,
    default: ''
  },
  change: {
    type: Number,
    default: null
  },
  format: {
    type: String,
    default: 'number' // 'number' | 'money' | 'percentage' | 'text'
  }
})

const displayValue = computed(() => {
  if (props.value == null) return '--'
  
  if (typeof props.value === 'string') return props.value
  
  switch (props.format) {
    case 'number':
      return formatNumber(props.value)
    case 'money':
      return formatMoney(props.value)
    case 'percentage':
      return `${props.value.toFixed(2)}%`
    default:
      return props.value
  }
})
</script>

<style scoped>
.info-card {
  transition: all 0.2s ease;
}

.info-card:hover {
  border-color: var(--color-accent, #3b82f6);
}
</style>
