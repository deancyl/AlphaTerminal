<script setup>
import { ref } from 'vue'
import { mdRender } from '../../composables/useCopilotMarkdown.js'

defineProps({
  messages: { type: Array, default: () => [] }
})

const historyEl = ref(null)
defineExpose({ historyEl })
</script>

<template>
  <div ref="historyEl" class="flex-1 overflow-y-auto p-4 space-y-3">
    <div v-if="messages.length === 0" class="text-center mt-12">
      <div class="text-4xl mb-3">💬</div>
      <p class="text-terminal-dim text-sm">开始一场投研对话</p>
      <div class="mt-4 text-xs text-terminal-dim/70 space-y-1">
        <p>💡 试试：「分析上证指数」</p>
        <p>💡 或：「今日涨停有哪些」</p>
        <p>💡 或：「打开贵州茅台」</p>
      </div>
    </div>

    <div v-for="(msg, i) in messages" :key="i"
         class="rounded-sm p-3 text-sm whitespace-pre-wrap leading-relaxed"
         :class="msg.role === 'user'
           ? 'bg-terminal-accent/10 border border-terminal-accent/30 text-theme-primary ml-8'
           : msg.isError
             ? 'bg-[var(--color-danger-bg)] border border-[var(--color-danger-border)] text-red-300 mr-4'
             : 'bg-terminal-bg border border-theme mr-4'">
      <div class="text-[10px] mb-1.5 flex items-center gap-1"
           :class="msg.role === 'user' ? 'text-terminal-accent' : 'text-terminal-dim'">
        <span>{{ msg.role === 'user' ? '你' : '🤖 AlphaTerminal' }}</span>
        <span v-if="msg.fromCache" class="text-[10px] text-bearish">📋 缓存</span>
      </div>
      <div v-if="msg.role === 'user'" class="text-theme-primary">{{ msg.content }}</div>
      <div v-else class="text-theme-primary copilot-markdown">
        <span v-html="msg.renderedContent || mdRender(msg.displayedContent)"></span>
        <span v-if="msg.streaming" class="animate-pulse text-terminal-accent">▌</span>
      </div>
    </div>
  </div>
</template>
