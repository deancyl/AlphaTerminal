<template>
  <div class="p-4 border-t border-theme-secondary shrink-0">
    <div class="relative">
      <textarea
        :value="inputText"
        @input="$emit('update:inputText', $event.target.value)"
        class="w-full bg-terminal-bg border border-theme rounded-sm px-3 py-2.5 pr-12
               text-sm text-theme-primary resize-none focus:outline-none focus:border-terminal-accent/60
               placeholder:text-terminal-dim/50"
        rows="3" placeholder="输入命令或问题... (Shift+Enter 换行)"
        :disabled="isLoading" @keydown.enter.exact.prevent="$emit('send')">
      </textarea>
      <button
        class="absolute right-2 bottom-2 w-8 h-8 rounded-sm flex items-center justify-center transition-colors"
        :class="isLoading || !inputText.trim()
          ? 'bg-terminal-bg text-terminal-dim/30 cursor-not-allowed'
          : 'bg-terminal-accent/20 text-terminal-accent hover:bg-terminal-accent/30'"
        :disabled="isLoading || !inputText.trim()" @click="$emit('send')">
        <svg v-if="!isLoading" xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M22 2L11 13M22 2L15 22l-4-9-9-4 20-7z"/>
        </svg>
        <span v-else class="w-4 h-4 border-2 border-terminal-accent/40 border-t-terminal-accent rounded-full animate-spin"></span>
      </button>
    </div>
    <div class="flex justify-between mt-1.5 text-[10px] text-terminal-dim/50">
      <span>Enter 发送 · Shift+Enter 换行</span>
      <span>{{ messageCount }} 条对话</span>
    </div>
  </div>
</template>

<script setup>
defineProps({
  inputText: { type: String, default: '' },
  isLoading: { type: Boolean, default: false },
  messageCount: { type: Number, default: 0 }
})

defineEmits(['send', 'update:inputText'])
</script>
