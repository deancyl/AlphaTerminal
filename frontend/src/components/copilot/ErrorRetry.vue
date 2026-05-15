<template>
  <div
    v-if="error || errorType"
    class="p-4 bg-red-500/10 border border-red-500/30 rounded-lg"
    role="alert"
    aria-live="assertive"
  >
    <p class="text-red-400 text-sm mb-2">{{ errorMessage }}</p>
    <button
      @click="$emit('retry')"
      class="px-3 py-1 bg-red-500/20 hover:bg-red-500/30 
             border border-red-500/40 rounded text-red-300 text-sm
             transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-red-500/50"
      aria-label="重试"
    >
      🔄 重试
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  error: { type: String, default: '' },
  errorType: { type: String, default: 'generic' }
})

defineEmits(['retry'])

// Map error types to user-friendly messages
const errorMessages = {
  network: '网络连接失败，请检查网络后重试',
  timeout: '请求超时，请稍后重试',
  rate_limit: '请求过于频繁，请稍后再试',
  server: '服务器暂时无法响应，请稍后重试',
  generic: '发生错误，请重试'
}

const errorMessage = computed(() => {
  if (props.error) return props.error
  return errorMessages[props.errorType] || errorMessages.generic
})
</script>
