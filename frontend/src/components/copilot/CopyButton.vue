<script setup>
import { ref } from 'vue'

const props = defineProps({
  code: { type: String, required: true }
})

const copied = ref(false)

const handleCopy = async () => {
  try {
    await navigator.clipboard.writeText(props.code)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch (err) {
    console.error('Copy failed:', err)
  }
}
</script>

<template>
  <button
    class="absolute top-2 right-2 px-2 py-1 rounded text-xs
           opacity-0 group-hover:opacity-100 transition-opacity duration-200
           bg-agent-blue/10 border border-agent-blue/30
           hover:bg-agent-blue/20 hover:border-agent-blue/50
           focus:outline-none focus:ring-2 focus:ring-agent-blue"
    :class="copied ? 'text-bearish border-bearish/30 bg-bearish/10' : 'text-agent-blue'"
    @click="handleCopy"
    aria-label="复制代码"
  >
    <span v-if="copied">✓ 已复制</span>
    <span v-else>📋 复制</span>
  </button>
</template>
