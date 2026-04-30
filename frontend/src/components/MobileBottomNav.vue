<template>
  <nav
    v-if="isMobile"
    class="fixed bottom-0 left-0 right-0 z-[9997] bg-terminal-panel/95 backdrop-blur-md border-t border-theme-secondary safe-area-pb"
  >
    <div class="flex items-center justify-around h-14">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        class="flex flex-col items-center justify-center gap-0.5 flex-1 h-full transition-colors"
        :class="activeId === tab.id ? 'text-terminal-accent' : 'text-terminal-dim'"
        @click="$emit('navigate', tab.id)"
      >
        <span class="text-lg">{{ tab.icon }}</span>
        <span class="text-[10px] font-medium">{{ tab.label }}</span>
      </button>
    </div>
  </nav>
</template>

<script setup>
import { useBreakpoints, breakpointsTailwind } from '@vueuse/core'

const props = defineProps({
  activeId: { type: String, default: 'stock' }
})

const emit = defineEmits(['navigate'])

const breakpoints = useBreakpoints(breakpointsTailwind)
const isMobile = breakpoints.smaller('md')

const tabs = [
  { id: 'stock', label: '行情', icon: '📊' },
  { id: 'fund', label: '基金', icon: '📈' },
  { id: 'bond', label: '债券', icon: '📉' },
  { id: 'futures', label: '期货', icon: '🛢️' },
  { id: 'copilot', label: 'AI', icon: '🤖' },
]
</script>

<style scoped>
.safe-area-pb {
  padding-bottom: env(safe-area-inset-bottom, 0px);
}
</style>