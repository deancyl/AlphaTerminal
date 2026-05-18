<template>
  <Transition name="slide-down">
    <div
      v-if="showBanner"
      :class="bannerClass"
      class="fixed top-0 left-0 right-0 z-[99997] px-4 py-2 flex items-center justify-center gap-2 shadow-lg border-b backdrop-blur-sm transition-all duration-300"
      role="alert"
      aria-live="polite"
    >
      <div class="flex items-center gap-2">
        <!-- Degraded: Warning icon -->
        <svg v-if="status === 'degraded'" class="w-5 h-5 animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        <!-- Down: Error icon -->
        <svg v-else class="w-5 h-5 animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span class="font-medium text-sm">{{ bannerMessage }}</span>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useDataSourceStatus, onDataSourceStatusChange } from '../composables/useDataSourceStatus.js'

const { status, message } = useDataSourceStatus()

// Track current status locally for reactivity
const currentStatus = ref('ok')

// Only show banner when status is not 'ok'
const showBanner = computed(() => currentStatus.value !== 'ok')

// Banner styling based on status
const bannerClass = computed(() => {
  if (currentStatus.value === 'degraded') {
    return 'bg-yellow-500/90 text-yellow-900 border-yellow-600/50'
  }
  if (currentStatus.value === 'down') {
    return 'bg-red-500/90 text-red-900 border-red-600/50'
  }
  return ''
})

// Banner message based on status
const bannerMessage = computed(() => {
  if (currentStatus.value === 'degraded') {
    return '数据源降级，已切换备用数据源'
  }
  if (currentStatus.value === 'down') {
    return '数据源熔断，无可用数据源'
  }
  return ''
})

// Subscribe to status changes
let unsubscribe = null

onMounted(() => {
  // Initialize with current status
  currentStatus.value = status.value
  
  // Subscribe to future changes
  unsubscribe = onDataSourceStatusChange((newStatus) => {
    currentStatus.value = newStatus
  })
})

onUnmounted(() => {
  if (unsubscribe) {
    unsubscribe()
  }
})
</script>

<style scoped>
.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.3s ease-out;
}

.slide-down-enter-from,
.slide-down-leave-to {
  transform: translateY(-100%);
  opacity: 0;
}

.slide-down-enter-to,
.slide-down-leave-from {
  transform: translateY(0);
  opacity: 1;
}
</style>
