<template>
  <span
    :class="colorClass"
    :title="tooltip"
    class="inline-flex items-center gap-1 text-xs"
  >
    <span>{{ freshness.icon }}</span>
    <span>{{ freshness.ageText }}</span>
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { getFreshness } from '../utils/freshness.js'

const props = defineProps({
  timestamp: {
    type: [Date, String, Number],
    default: null
  }
})

const freshness = computed(() => getFreshness(props.timestamp))

const colorClass = computed(() => {
  const status = freshness.value.status
  if (status === 'FRESH') return 'text-green-500'
  if (status === 'RECENT') return 'text-yellow-500'
  if (status === 'STALE') return 'text-orange-500'
  if (status === 'EXPIRED') return 'text-red-500'
  return 'text-gray-500'
})

const tooltip = computed(() => {
  const f = freshness.value
  return `${f.label} - ${f.ageText}`
})
</script>
