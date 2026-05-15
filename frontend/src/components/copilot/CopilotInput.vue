<template>
  <div class="p-4 border-t border-agent-blue/20 shrink-0">
    <div class="relative">
      <textarea
        ref="textareaRef"
        :value="inputText"
        @input="handleInput"
        class="w-full bg-terminal-bg border border-agent-blue/30 rounded-sm px-3 py-2.5 pr-12
               text-sm text-theme-primary resize-none focus:outline-none focus:border-agent-blue/60
               placeholder:text-theme-muted font-mono leading-relaxed overflow-y-auto"
        style="min-height: 60px; max-height: 150px;"
        placeholder="输入命令或问题... (Shift+Enter 换行)"
        :disabled="isLoading"
        @keydown.enter.exact.prevent="$emit('send')"
        aria-label="输入您的问题"
        aria-describedby="input-hint"
        :aria-busy="isLoading"
        role="textbox"
      ></textarea>
      <span id="input-hint" class="sr-only">按 Enter 发送，Shift+Enter 换行</span>
      <button
        class="absolute right-2 bottom-2 w-8 h-8 rounded-sm flex items-center justify-center transition-all duration-200"
        :class="isLoading || !inputText.trim()
          ? 'bg-terminal-bg text-terminal-dim/30 cursor-not-allowed ring-0'
          : 'bg-terminal-accent/20 text-agent-blue hover:bg-agent-blue/30 ring-2 ring-agent-blue ring-offset-2 ring-offset-terminal-bg shadow-lg shadow-agent-blue/30 hover:shadow-agent-blue/50'"
        :disabled="isLoading || !inputText.trim()"
        @click="$emit('send')"
        :aria-label="isLoading ? '发送中...' : '发送消息'"
        :aria-disabled="isLoading || !inputText.trim()">
        <svg v-if="!isLoading" xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M22 2L11 13M22 2L15 22l-4-9-9-4 20-7z"/>
        </svg>
        <span v-else class="w-4 h-4 border-2 border-agent-blue/40 border-t-agent-blue rounded-full animate-spin"></span>
      </button>
    </div>
    <!-- Streaming progress indicator -->
    <div v-if="isLoading" class="flex items-center gap-2 mt-2 text-xs text-theme-muted">
      <span class="animate-pulse">●</span>
      <span v-if="streamingProgress === 0">连接中...</span>
      <span v-else-if="streamingProgress > 0 && streamingProgress < 100">
        生成中... {{ streamingProgress }} 字符
      </span>
      <span v-else-if="showTimeoutWarning" class="text-yellow-500">
        ⚠ 响应较慢，请稍候...
      </span>
    </div>
    <div class="flex justify-between mt-1.5 text-[10px] text-theme-muted">
      <span>Enter 发送 · Shift+Enter 换行</span>
      <span>{{ messageCount }} 条对话</span>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'

const props = defineProps({
  inputText: { type: String, default: '' },
  isLoading: { type: Boolean, default: false },
  messageCount: { type: Number, default: 0 },
  streamingProgress: { type: Number, default: 0 },
  showTimeoutWarning: { type: Boolean, default: false }
})

const emit = defineEmits(['send', 'update:inputText'])

const textareaRef = ref(null)

function handleInput(e) {
  emit('update:inputText', e.target.value)
  autoResize()
}

function autoResize() {
  const textarea = textareaRef.value
  if (!textarea) return
  textarea.style.height = 'auto'
  const newHeight = Math.min(textarea.scrollHeight, 150)
  textarea.style.height = newHeight + 'px'
}

watch(() => props.inputText, () => {
  nextTick(autoResize)
})
</script>
