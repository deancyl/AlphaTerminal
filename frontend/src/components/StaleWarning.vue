<template>
  <Transition name="slide-down">
    <div
      v-if="showWarning"
      class="stale-warning flex items-center justify-between gap-3 px-3 py-2 text-xs rounded-sm border"
      :class="warningClass"
      role="alert"
    >
      <div class="flex items-center gap-2">
        <span class="warning-icon">⚠️</span>
        <span class="warning-text">
          <span class="font-medium">{{ freshness.label }}</span>
          <span class="text-[var(--text-tertiary)]"> - 数据已 {{ freshness.ageText }}</span>
        </span>
      </div>
      <button
        v-if="showRefresh"
        class="refresh-btn px-2 py-1 text-[10px] rounded-sm border transition-colors"
        :class="refreshBtnClass"
        @click="$emit('refresh')"
      >
        刷新数据
      </button>
    </div>
  </Transition>
</template>

<script setup>
import { computed } from 'vue'
import { getFreshness } from '../utils/freshness.js'

const props = defineProps({
  timestamp: {
    type: [Date, String, Number],
    default: null
  },
  threshold: {
    type: Number,
    default: 30000
  },
  showRefresh: {
    type: Boolean,
    default: true
  }
})

defineEmits(['refresh'])

const freshness = computed(() => getFreshness(props.timestamp))

const showWarning = computed(() => {
  return freshness.value.ageMs > props.threshold
})

const warningClass = computed(() => {
  const status = freshness.value.status
  if (status === 'EXPIRED') {
    return 'bg-[var(--color-danger-bg)] border-[var(--color-danger-border)] text-[var(--color-danger)]'
  }
  return 'bg-[var(--color-warning-bg)] border-[var(--color-warning-border)] text-[var(--color-warning)]'
})

const refreshBtnClass = computed(() => {
  const status = freshness.value.status
  if (status === 'EXPIRED') {
    return 'border-[var(--color-danger-border)] text-[var(--color-danger)] hover:bg-[var(--color-danger)]/10'
  }
  return 'border-[var(--color-warning-border)] text-[var(--color-warning)] hover:bg-[var(--color-warning)]/10'
})
</script>

<style scoped>
.stale-warning {
  font-family: var(--font-mono, 'JetBrains Mono', monospace);
}

.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.3s ease;
}

.slide-down-enter-from,
.slide-down-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

.refresh-btn {
  cursor: pointer;
  white-space: nowrap;
}
</style>