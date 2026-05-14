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

    <div v-for="(msg, i) in messages" :key="i" class="rounded-sm p-3 text-sm whitespace-pre-wrap leading-relaxed">
      <!-- User message - right aligned -->
      <div v-if="msg.role === 'user'"
           class="bg-agent-blue/10 border border-agent-blue/30 rounded px-3 py-2 mr-4 ml-8 text-right">
        <div class="text-[10px] mb-1 text-agent-blue">你</div>
        <div class="text-theme-primary">{{ msg.content }}</div>
      </div>

      <!-- AI message - full width, no bubble -->
      <div v-else
           class="bg-transparent mr-4"
           :class="msg.isError ? 'border border-red-500/30' : ''">
        <div class="text-[10px] mb-1 text-terminal-dim flex items-center gap-1">
          <span>🤖 AlphaTerminal</span>
          <span v-if="msg.fromCache" class="text-[10px] text-bearish">📋 缓存</span>
        </div>
        <div class="copilot-markdown" :class="msg.isError ? 'text-red-300' : 'text-theme-primary'">
          <span v-html="msg.renderedContent || mdRender(msg.displayedContent)"></span>
          <span v-if="msg.streaming" class="animate-pulse text-agent-blue">▌</span>
        </div>
      </div>
    </div>
  </div>
</template>
