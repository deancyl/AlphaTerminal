<template>
  <span
    class="freshness inline-flex items-center gap-1.5"
    :class="statusClass"
    :title="tooltip"
  >
    <span
      class="freshness-dot relative flex items-center justify-center"
      :class="{ 'animate-pulse': freshness.isLive }"
    >
      <span
        class="dot-core w-2 h-2 rounded-full"
        :style="{ backgroundColor: freshness.color }"
      ></span>
      <span
        v-if="freshness.isLive"
        class="dot-ring absolute w-3 h-3 rounded-full animate-ping"
        :style="{ backgroundColor: freshness.color, opacity: 0.4 }"
      ></span>
    </span>
    <span class="freshness-label text-[10px] font-medium tracking-wide">
      {{ freshness.label }}
    </span>
    <span
      v-if="showTime && freshness.ageMs > 0"
      class="freshness-time text-[10px] text-[var(--text-tertiary)]"
    >
      {{ freshness.ageText }}
    </span>
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { getFreshness } from '../utils/freshness.js'

const props = defineProps({
  timestamp: {
    type: [Date, String, Number],
    default: null
  },
  showTime: {
    type: Boolean,
    default: true
  }
})

const freshness = computed(() => getFreshness(props.timestamp))

const statusClass = computed(() => {
  const status = freshness.value.status
  if (status === 'FRESH') return 'text-[var(--color-success)]'
  if (status === 'RECENT') return 'text-[var(--color-warning)]'
  if (status === 'STALE') return 'text-[var(--color-warning)]'
  if (status === 'EXPIRED') return 'text-[var(--color-danger)]'
  return 'text-[var(--text-tertiary)]'
})

const tooltip = computed(() => {
  const f = freshness.value
  if (f.ageMs < 0) return f.label
  return `${f.label} - ${f.ageText}`
})
</script>

<style scoped>
.freshness {
  font-family: var(--font-mono, 'JetBrains Mono', monospace);
}

.freshness-dot {
  position: relative;
}

.dot-core {
  transition: background-color 0.3s ease;
}

.dot-ring {
  animation: ping 1s cubic-bezier(0, 0, 0.2, 1) infinite;
}

@keyframes ping {
  75%, 100% {
    transform: scale(2);
    opacity: 0;
  }
}

.animate-pulse .dot-core {
  animation: pulse-core 2s ease-in-out infinite;
}

@keyframes pulse-core {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.6;
  }
}
</style>