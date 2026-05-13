<template>
  <Transition name="slide-down">
    <div
      v-if="!isOnline"
      class="fixed top-0 left-0 right-0 z-[99998] bg-gradient-to-r from-red-900/95 via-red-800/95 to-red-900/95 text-white px-4 py-2 flex items-center justify-center gap-2 shadow-lg border-b border-red-700/50 backdrop-blur-sm"
      role="alert"
      aria-live="assertive"
    >
      <div class="flex items-center gap-2">
        <svg class="w-5 h-5 animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 5.636a9 9 0 010 12.728m0 0l-2.829-2.829m2.829 2.829L21 21M15.536 8.464a5 5 0 010 7.072m0 0l-2.829-2.829m-4.243 2.829a4.978 4.978 0 01-1.414-2.83m-1.414 5.658a9 9 0 01-2.167-9.238m7.824 2.167a1 1 0 111.414 1.414m-1.414-1.414L3 3m8.293 8.293l1.414 1.414" />
        </svg>
        <span class="font-medium text-sm">网络已断开，请检查连接</span>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { useNetworkStatus } from '../composables/useNetworkStatus.js'

const { isOnline } = useNetworkStatus()
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
