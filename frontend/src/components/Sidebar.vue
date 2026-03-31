<template>
  <!-- 侧边栏：展开时 w-56，收起时 w-0，DOM 保留（状态不丢） -->
  <aside
    class="flex-shrink-0 flex flex-col bg-terminal-panel border-r border-gray-800 transition-all duration-300 ease-in-out overflow-hidden"
    :style="{ width: isOpen ? '224px' : '0px' }"
  >
    <!-- 顶部：Logo + 收起按钮 -->
    <div class="flex items-center justify-between px-3 h-12 border-b border-gray-800 shrink-0">
      <span class="text-terminal-accent font-bold text-sm whitespace-nowrap">AlphaTerminal</span>
      <button
        class="w-6 h-6 flex items-center justify-center rounded text-terminal-dim hover:text-terminal-accent transition-colors"
        @click="$emit('close')"
        title="收起侧边栏"
      >
        <span class="text-sm">☰</span>
      </button>
    </div>

    <!-- 导航列表 -->
    <nav class="flex-1 overflow-y-auto py-2">

      <!-- 一级分类标题 -->
      <div class="px-3 py-1.5 text-[10px] text-terminal-dim uppercase tracking-wider">📂 市场行情</div>

      <!-- 股票行情：默认选中 -->
      <button
        v-for="item in navItems"
        :key="item.id"
        class="w-full flex items-center gap-2.5 px-3 py-2 text-sm transition-colors"
        :class="activeId === item.id
          ? 'bg-terminal-accent/10 text-terminal-accent border-r-2 border-terminal-accent'
          : 'text-gray-400 hover:bg-white/5 hover:text-gray-200 border-r-2 border-transparent'"
        @click="handleClick(item)"
      >
        <span class="text-base">{{ item.icon }}</span>
        <span class="whitespace-nowrap text-xs">{{ item.label }}</span>
      </button>

    </nav>

    <!-- 底部版本信息 -->
    <div class="px-3 py-2 border-t border-gray-800 shrink-0">
      <span class="text-[9px] text-terminal-dim">Beta 0.2.3 · Phase 5</span>
    </div>
  </aside>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  isOpen:  { type: Boolean, default: false },
  activeId: { type: String, default: 'stock' },
})
const emit = defineEmits(['navigate', 'close'])

const navItems = [
  { id: 'stock',   label: '股票行情', icon: '📊' },
  { id: 'bond',    label: '债券行情', icon: '📉' },
  { id: 'futures', label: '期货行情', icon: '🛢️' },
]

function handleClick(item) {
  emit('navigate', item.id)
}
</script>
