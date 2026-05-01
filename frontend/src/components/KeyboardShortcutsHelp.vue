<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="fixed inset-0 z-[100001] flex items-center justify-center bg-black/60 backdrop-blur-sm"
      @click="$emit('close')"
    >
      <div
        class="bg-terminal-panel border border-theme-secondary rounded-xl shadow-2xl max-w-2xl w-full mx-4 max-h-[80vh] flex flex-col"
        @click.stop
      >
        <!-- 标题 -->
        <div class="flex items-center justify-between px-6 py-4 border-b border-theme-secondary">
          <div class="flex items-center gap-2">
            <span class="text-lg">⌨️</span>
            <span class="text-base font-bold text-terminal-accent">键盘快捷键</span>
          </div>
          <button
            class="w-8 h-8 flex items-center justify-center rounded hover:bg-theme-hover text-terminal-dim hover:text-terminal-primary transition"
            @click="$emit('close')"
          >
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- 快捷键列表 -->
        <div class="flex-1 overflow-y-auto p-6">
          <div class="space-y-6">
            <!-- 按分类显示快捷键 -->
            <div v-for="category in categories" :key="category">
              <h3 class="text-sm font-bold text-terminal-primary mb-3">{{ category }}</h3>
              <div class="space-y-2">
                <div v-for="s in getShortcutsByCategory(category)" :key="s.key + s.ctrl + s.shift" 
                     class="flex items-center justify-between py-2 px-3 rounded bg-terminal-bg/50">
                  <span class="text-sm text-terminal-secondary">{{ s.description }}</span>
                  <div class="flex items-center gap-1">
                    <span v-if="s.ctrl" class="px-2 py-0.5 rounded bg-theme-secondary text-xs text-terminal-dim">Ctrl</span>
                    <span v-if="s.shift" class="px-2 py-0.5 rounded bg-theme-secondary text-xs text-terminal-dim">Shift</span>
                    <span v-if="s.alt" class="px-2 py-0.5 rounded bg-theme-secondary text-xs text-terminal-dim">Alt</span>
                    <span class="px-2 py-0.5 rounded bg-theme-secondary text-xs text-terminal-dim font-mono">{{ formatKey(s.key) }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 底部提示 -->
        <div class="px-6 py-3 border-t border-theme-secondary text-xs text-terminal-dim">
          提示：在输入框中快捷键会被忽略，但 Escape 和 Ctrl+K 始终可用
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed } from 'vue'
import { SHORTCUTS } from '../composables/useKeyboardShortcuts.js'

const props = defineProps({
  visible: { type: Boolean, default: false }
})

defineEmits(['close'])

// 获取所有分类
const categories = computed(() => {
  const cats = new Set()
  SHORTCUTS.forEach(s => {
    if (s.category) cats.add(s.category)
  })
  return Array.from(cats)
})

// 按分类获取快捷键
function getShortcutsByCategory(category) {
  return SHORTCUTS.filter(s => s.category === category)
}

function formatKey(key) {
  const map = {
    'escape': 'Esc',
    '/': '/',
    '?': '?',
    ',': ',',
    'k': 'K',
    'd': 'D',
    'f1': 'F1',
    'f5': 'F5',
    'f6': 'F6',
    'f9': 'F9',
    'f11': 'F11',
  }
  return map[key.toLowerCase()] || key.toUpperCase()
}
</script>