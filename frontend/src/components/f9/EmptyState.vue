<template>
  <div class="empty-state flex flex-col items-center justify-center py-12" role="status" aria-live="polite">
    <div class="text-4xl mb-4" aria-hidden="true">{{ icon }}</div>
    <div class="text-sm text-terminal-dim mb-2 text-center max-w-md">
      {{ message }}
    </div>
    <div v-if="hint" class="text-xs text-terminal-dim opacity-60 text-center max-w-md">
      {{ hint }}
    </div>
  </div>
</template>

<script setup>
defineProps({
  icon: {
    type: String,
    default: '📭'
  },
  message: {
    type: String,
    default: '暂无数据'
  },
  hint: {
    type: String,
    default: ''
  }
})
</script>

<style scoped>
.empty-state {
  min-height: 200px;
}
</style>
