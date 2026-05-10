<template>
  <div class="error-display flex flex-col items-center justify-center py-12">
    <div class="text-4xl mb-4">⚠️</div>
    <div class="text-sm text-terminal-dim mb-4 text-center max-w-md">
      {{ error || '加载失败，请稍后重试' }}
    </div>
    <button
      v-if="retry"
      class="px-4 py-2 text-sm rounded border border-terminal-accent text-terminal-accent hover:bg-terminal-accent hover:text-white transition"
      @click="handleRetry"
    >
      重试
    </button>
  </div>
</template>

<script setup>
const props = defineProps({
  error: {
    type: String,
    default: ''
  },
  retry: {
    type: Function,
    default: null
  }
})

function handleRetry() {
  if (props.retry) {
    props.retry()
  }
}
</script>

<style scoped>
.error-display {
  min-height: 200px;
}
</style>
