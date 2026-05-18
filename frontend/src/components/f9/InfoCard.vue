<template>
  <div class="info-card bg-terminal-card border border-terminal-border rounded-lg p-3 hover:bg-zinc-800/50 transition-colors">
    <div class="text-xs text-gray-500 uppercase tracking-wider mb-1">{{ title }}</div>
    <div class="flex items-baseline gap-1">
      <span class="text-lg font-bold font-mono text-gray-200 tabular-nums">{{ displayValue }}</span>
      <span v-if="unit" class="text-xs text-gray-500">{{ unit }}</span>
    </div>
    <div v-if="change != null" class="mt-1 flex items-center gap-1">
      <span
        class="text-xs font-mono tabular-nums"
        :class="change >= 0 ? 'text-market-up' : 'text-market-down'"
      >
        {{ change >= 0 ? '+' : '' }}{{ change.toFixed(2) }}%
      </span>
      <span
        v-if="change !== 0"
        class="text-xs"
        :class="change >= 0 ? 'text-market-up' : 'text-market-down'"
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
  border-color: #3f3f46;
}
</style>
