<template>
  <nav
    v-if="isMobile"
    class="fixed bottom-0 left-0 right-0 z-[9997] bg-terminal-panel/95 backdrop-blur-md border-t border-theme-secondary/50 safe-area-pb"
  >
    <!-- 更多菜单展开面板 -->
    <div
      v-if="showMore"
      class="absolute bottom-full left-0 right-0 bg-terminal-panel/95 backdrop-blur-md border-t border-theme-secondary/50 p-4 grid grid-cols-4 gap-3 transition-all duration-200"
    >
      <button
        v-for="tab in moreTabs"
        :key="tab.id"
        class="flex flex-col items-center justify-center gap-1 py-2 rounded-sm transition-colors"
        :class="activeId === tab.id ? 'bg-terminal-accent/10 text-terminal-accent' : 'text-terminal-dim hover:bg-theme-hover'"
        @click="handleNavigate(tab.id)"
      >
        <span class="text-xl">{{ tab.icon }}</span>
        <span class="text-xs">{{ tab.label }}</span>
      </button>
    </div>

    <div class="flex items-center justify-around h-14">
      <button
        v-for="tab in mainTabs"
        :key="tab.id"
        class="flex flex-col items-center justify-center gap-0.5 flex-1 h-full min-h-[48px] transition-colors"
        :class="activeId === tab.id ? 'text-terminal-accent' : 'text-terminal-dim'"
        @click="handleNavigate(tab.id)"
      >
        <span class="text-lg">{{ tab.icon }}</span>
        <span class="text-xs font-medium">{{ tab.label }}</span>
      </button>
      <!-- AI 按钮 -->
      <button
        class="flex flex-col items-center justify-center gap-0.5 flex-1 h-full min-h-[48px] transition-colors"
        :class="activeId === 'copilot' ? 'text-terminal-accent' : 'text-terminal-dim'"
        @click="handleNavigate('copilot')"
      >
        <span class="text-lg">🤖</span>
        <span class="text-xs font-medium">AI</span>
      </button>
      <!-- 更多按钮 -->
      <button
        class="flex flex-col items-center justify-center gap-0.5 flex-1 h-full min-h-[48px] transition-colors"
        :class="isMoreActive() || showMore ? 'text-terminal-accent' : 'text-terminal-dim'"
        @click="handleNavigate('more')"
      >
        <span class="text-lg">{{ showMore ? '✕' : '⋮' }}</span>
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
  { id: 'backtest', label: '回测', icon: '🔬' },
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
