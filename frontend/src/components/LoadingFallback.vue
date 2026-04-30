<template>
  <div class="loading-fallback">
    <div class="loading-spinner" />
    <p class="loading-text">{{ text }}</p>
  </div>
</template>

<script setup>
defineProps({
  text: { type: String, default: '加载中...' },
})
</script>

<style scoped>
.loading-fallback {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  gap: 12px;
}

.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--border-primary);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-text {
  color: var(--text-muted);
  font-size: 14px;
}
</style>
