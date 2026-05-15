<template>
  <div class="p-4 border-b border-theme-secondary shrink-0" role="banner" aria-label="Copilot 头部">
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-terminal-accent font-bold text-base flex items-center gap-2">
          🧠 AlphaTerminal Copilot
        </h2>
        <p class="text-terminal-dim text-xs mt-0.5">智能投研助手 · 数据驱动分析</p>
      </div>
    </div>
    <div v-if="sessionId" class="flex items-center justify-between mt-2 pt-2 border-t border-theme-secondary/50">
      <span class="text-[10px] text-theme-muted">
        Session: {{ sessionId.slice(0, 8) }}...
      </span>
      <button
        class="text-[10px] text-terminal-accent hover:text-terminal-accent/80 transition-colors"
        @click="$emit('new-conversation')"
        aria-label="开始新对话"
        role="button"
      >
        新对话
      </button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  sessionId: { type: String, default: '' }
})

defineEmits(['new-conversation'])
</script>
