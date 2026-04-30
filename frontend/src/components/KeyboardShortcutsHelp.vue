<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="fixed inset-0 z-[100001] flex items-center justify-center bg-black/60 backdrop-blur-sm"
      @click="$emit('close')"
    >
      <div
        class="bg-terminal-panel border border-theme-secondary rounded-sm shadow-sm max-w-2xl w-full mx-4 max-h-[80vh] flex flex-col"
        @click.stop
      >
        <!-- 标题 -->
        <div class="flex items-center justify-between px-6 py-4 border-b border-theme-secondary">
          <div class="flex items-center gap-2">
            <span class="text-lg">⌨️</span>
            <span class="text-base font-bold text-terminal-accent">键盘快捷键</span>
          </div>
          <button
            class="w-8 h-8 flex items-center justify-center rounded-sm hover:bg-theme-hover text-terminal-dim hover:text-terminal-primary transition"
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
            <!-- 视图切换 -->
            <div>
              <h3 class="text-sm font-bold text-terminal-primary mb-3">视图导航</h3>
              <div class="space-y-2">
                <div v-for="s in viewShortcuts" :key="s.key" class="flex items-center justify-between py-2 px-3 rounded-sm bg-terminal-bg/50">
                  <span class="text-sm text-terminal-secondary">{{ s.description }}</span>
                  <div class="flex items-center gap-1">
                    <span v-if="s.ctrl" class="px-2 py-0.5 rounded-sm bg-theme-secondary text-xs text-terminal-dim">Ctrl</span>
                    <span class="px-2 py-0.5 rounded-sm bg-theme-secondary text-xs text-terminal-dim font-mono">{{ formatKey(s.key) }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- 功能操作 -->
            <div>
              <h3 class="text-sm font-bold text-terminal-primary mb-3">功能操作</h3>
              <div class="space-y-2">
                <div v-for="s in funcShortcuts" :key="s.key" class="flex items-center justify-between py-2 px-3 rounded-sm bg-terminal-bg/50">
                  <span class="text-sm text-terminal-secondary">{{ s.description }}</span>
                  <div class="flex items-center gap-1">
                    <span v-if="s.ctrl" class="px-2 py-0.5 rounded-sm bg-theme-secondary text-xs text-terminal-dim">Ctrl</span>
                    <span v-if="s.shift" class="px-2 py-0.5 rounded-sm bg-theme-secondary text-xs text-terminal-dim">Shift</span>
                    <span class="px-2 py-0.5 rounded-sm bg-theme-secondary text-xs text-terminal-dim font-mono">{{ formatKey(s.key) }}</span>
                  </div>
                </div>
                <!-- F9深度资料（全屏K线中可用） -->
                <div v-if="f9Shortcut" class="flex items-center justify-between py-2 px-3 rounded-sm bg-terminal-bg/50">
                  <span class="text-sm text-terminal-secondary">{{ f9Shortcut.description }}（全屏K线中）</span>
                  <div class="flex items-center gap-1">
                    <span class="px-2 py-0.5 rounded-sm bg-theme-secondary text-xs text-terminal-dim font-mono">{{ formatKey(f9Shortcut.key) }}</span>
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

const viewShortcuts = computed(() => 
  SHORTCUTS.filter(s => s.action === 'view')
)

const funcShortcuts = computed(() => 
  SHORTCUTS.filter(s => ['search', 'escape', 'fullscreen', 'help'].includes(s.action))
)

// F9深度资料需要特殊处理，确保显示在功能列表中
const f9Shortcut = computed(() => 
  SHORTCUTS.find(s => s.key === 'f9')
)

function formatKey(key) {
  const map = {
    'escape': 'Esc',
    '/': '/',
    'k': 'K',
    'b': 'B',
    'f': 'F',
    'p': 'P',
    'm': 'M',
    'r': 'R',
    '?': '?',
    'f6': 'F6',
    'f9': 'F9',
  }
  return map[key] || key.toUpperCase()
}
</script>