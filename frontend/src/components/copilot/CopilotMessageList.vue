<script setup>
import { ref, watch, nextTick } from 'vue'
import { mdRender } from '../../composables/useCopilotMarkdown.js'
import CopyButton from './CopyButton.vue'

const props = defineProps({
  messages: { type: Array, default: () => [] }
})

const historyEl = ref(null)
defineExpose({ historyEl })

function injectCopyButtons() {
  nextTick(() => {
    if (!historyEl.value) return
    const preElements = historyEl.value.querySelectorAll('pre[data-code]')
    preElements.forEach(pre => {
      if (pre.querySelector('button')) return
      const code = decodeURIComponent(pre.dataset.code || '')
      if (!code) return
      const button = document.createElement('button')
      button.className = 'absolute top-2 right-2 px-2 py-1 rounded text-xs opacity-0 group-hover:opacity-100 transition-opacity duration-200 bg-agent-blue/10 border border-agent-blue/30 hover:bg-agent-blue/20 hover:border-agent-blue/50 focus:outline-none focus:ring-2 focus:ring-agent-blue text-agent-blue'
      button.setAttribute('aria-label', '复制代码')
      button.textContent = '📋 复制'
      button.addEventListener('click', async () => {
        try {
          await navigator.clipboard.writeText(code)
          button.textContent = '✓ 已复制'
          button.className = button.className.replace('text-agent-blue', 'text-bearish border-bearish/30 bg-bearish/10')
          setTimeout(() => {
            button.textContent = '📋 复制'
            button.className = button.className.replace('text-bearish border-bearish/30 bg-bearish/10', 'text-agent-blue')
          }, 2000)
        } catch (err) {
          console.error('Copy failed:', err)
        }
      })
      pre.appendChild(button)
    })
  })
}

watch(() => props.messages, injectCopyButtons, { deep: true })
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

    <div v-for="(msg, i) in messages" :key="i" class="text-sm whitespace-pre-wrap leading-relaxed">
      <!-- User message - minimal style, right aligned -->
      <div v-if="msg.role === 'user'"
           class="mr-4 ml-8 text-right">
        <div class="text-[10px] mb-1 text-agent-blue/70">你</div>
        <div class="text-gray-300">{{ msg.content }}</div>
      </div>

      <!-- AI message - full width, no bubble -->
      <div v-else
           class="mr-4"
           :class="msg.isError ? 'border border-red-500/30 rounded p-3' : ''">
        <div class="text-[10px] mb-1 text-terminal-dim flex items-center gap-1">
          <span>🤖 AlphaTerminal</span>
          <span v-if="msg.fromCache" class="text-[10px] text-bearish">📋 缓存</span>
        </div>
        <div class="copilot-markdown text-gray-200" :class="msg.isError ? 'text-red-300' : ''">
          <span v-html="msg.renderedContent || mdRender(msg.displayedContent)"></span>
          <span v-if="msg.streaming" class="animate-pulse text-agent-blue">▌</span>
        </div>
      </div>
    </div>
  </div>
</template>
