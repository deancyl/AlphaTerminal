<template>
  <nav
    v-if="isMobile"
    class="fixed bottom-0 left-0 right-0 z-[9997] bg-terminal-panel border-t border-theme-secondary/50 safe-area-pb"
    role="navigation"
    aria-label="移动端主导航"
  >
    <!-- 更多菜单展开面板 -->
    <div
      v-if="showMore"
      class="absolute bottom-full left-0 right-0 bg-terminal-panel border-t border-theme-secondary/50 p-4 grid grid-cols-4 gap-3 transition-all duration-200"
      role="menu"
      aria-label="更多导航选项"
    >
      <button
        v-for="tab in moreTabs"
        :key="tab.id"
        class="flex flex-col items-center justify-center gap-1 py-3 rounded-sm transition-colors min-h-[48px] min-w-[48px]"
        :class="activeId === tab.id ? 'bg-terminal-accent/10 text-terminal-accent' : 'text-terminal-dim hover:bg-theme-hover'"
        @click="handleNavigate(tab.id)"
        role="menuitem"
        :aria-label="tab.label"
        :aria-current="activeId === tab.id ? 'page' : undefined"
        type="button"
      >
        <span class="text-xl" aria-hidden="true">{{ tab.icon }}</span>
        <span class="text-xs">{{ tab.label }}</span>
      </button>
    </div>

    <div class="flex items-center justify-around h-14" role="menubar">
      <button
        v-for="tab in mainTabs"
        :key="tab.id"
        class="flex flex-col items-center justify-center gap-0.5 flex-1 h-full min-h-[48px] transition-colors"
        :class="activeId === tab.id ? 'text-terminal-accent' : 'text-terminal-dim'"
        @click="handleNavigate(tab.id)"
        role="menuitem"
        :aria-label="tab.label"
        :aria-current="activeId === tab.id ? 'page' : undefined"
        type="button"
      >
        <span class="text-lg" aria-hidden="true">{{ tab.icon }}</span>
        <span class="text-xs font-medium">{{ tab.label }}</span>
      </button>
      <!-- AI 按钮 -->
      <button
        class="flex flex-col items-center justify-center gap-0.5 flex-1 h-full min-h-[48px] transition-colors"
        :class="activeId === 'copilot' ? 'text-terminal-accent' : 'text-terminal-dim'"
        @click="handleNavigate('copilot')"
        role="menuitem"
        aria-label="AI助手"
        :aria-current="activeId === 'copilot' ? 'page' : undefined"
        type="button"
      >
        <span class="text-lg" aria-hidden="true">🤖</span>
        <span class="text-xs font-medium">AI</span>
      </button>
      <!-- 更多按钮 -->
      <button
        class="flex flex-col items-center justify-center gap-0.5 flex-1 h-full min-h-[48px] transition-colors"
        :class="isMoreActive() || showMore ? 'text-terminal-accent' : 'text-terminal-dim'"
        @click="handleNavigate('more')"
        role="menuitem"
        :aria-label="showMore ? '收起更多菜单' : '展开更多菜单'"
        :aria-expanded="showMore"
        :aria-current="isMoreActive() ? 'page' : undefined"
        type="button"
      >
        <span class="text-lg" aria-hidden="true">{{ showMore ? '✕' : '⋮' }}</span>
        <span class="text-xs font-medium">{{ showMore ? '收起' : '更多' }}</span>
      </button>
    </div>
  </nav>
</template>

<script setup>
import { ref } from 'vue'
import { useBreakpoints, breakpointsTailwind } from '@vueuse/core'

const props = defineProps({
  activeId: { type: String, default: 'stock' }
})

const emit = defineEmits(['navigate'])

const breakpoints = useBreakpoints(breakpointsTailwind)
const isMobile = breakpoints.smaller('md')
const showMore = ref(false)

const mainTabs = [
  { id: 'stock', label: '行情', icon: '📊' },
  { id: 'fund', label: '基金', icon: '📈' },
  { id: 'bond', label: '债券', icon: '📉' },
  { id: 'futures', label: '期货', icon: '🛢️' },
]

const moreTabs = [
  { id: 'portfolio', label: '组合', icon: '💰' },
  { id: 'macro', label: '宏观', icon: '🌍' },
  { id: 'options', label: '期权', icon: '⚡' },
  { id: 'global-index', label: '全球', icon: '🌐' },
  { id: 'strategy-center', label: '策略', icon: '🎯' },
  { id: 'admin', label: '设置', icon: '⚙️' },
]

function handleNavigate(id) {
  if (id === 'more') {
    showMore.value = !showMore.value
    return
  }
  showMore.value = false
  emit('navigate', id)
}

function isMoreActive() {
  return moreTabs.some(t => t.id === props.activeId)
}
</script>

<style scoped>
.safe-area-pb {
  padding-bottom: env(safe-area-inset-bottom, 0px);
}
</style>
