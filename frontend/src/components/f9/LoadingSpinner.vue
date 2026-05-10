<template>
  <div class="loading-spinner flex flex-col items-center justify-center py-12" role="status" aria-live="polite" aria-label="加载中">
    <div class="relative w-12 h-12 mb-4" aria-hidden="true">
      <div class="absolute inset-0 border-4 border-theme-secondary rounded-full"></div>
      <div class="absolute inset-0 border-4 border-terminal-accent border-t-transparent rounded-full animate-spin"></div>
    </div>
    <div class="text-sm text-terminal-dim">{{ text }}</div>
  </div>
</template>

<script setup>
defineProps({
  text: {
    type: String,
    default: '加载中...'
  }
})
</script>

<style scoped>
.loading-spinner {
  min-height: 200px;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.animate-spin {
  animation: spin 1s linear infinite;
}
</style>
