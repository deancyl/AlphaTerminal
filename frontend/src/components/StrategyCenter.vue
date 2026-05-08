<template>
  <div class="flex flex-col w-full h-full overflow-hidden">
    <!-- 顶部标签栏 -->
    <div class="flex items-center gap-1 px-4 py-2 border-b border-theme-secondary bg-terminal-panel/80 shrink-0">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        @click="activeTab = tab.id"
        class="px-4 py-2 text-sm font-medium rounded-sm transition-all"
        :class="activeTab === tab.id
          ? 'bg-terminal-accent/20 text-terminal-accent border-b-2 border-terminal-accent'
          : 'text-theme-secondary hover:text-theme-primary hover:bg-theme-hover'"
      >
        <span class="mr-1.5">{{ tab.icon }}</span>
        {{ tab.label }}
      </button>
      <div class="ml-auto text-xs text-theme-muted">
        <span v-if="activeTab === 'quick'">快速回测：预设策略一键测试</span>
        <span v-else-if="activeTab === 'advanced'">策略开发：自定义策略代码</span>
      </div>
    </div>

    <!-- 内容区域 -->
    <div class="flex-1 overflow-hidden">
      <!-- 快速回测 -->
      <BacktestDashboard v-if="activeTab === 'quick'" />
      
      <!-- 策略开发 -->
      <StrategyLab v-else-if="activeTab === 'advanced'" />
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import BacktestDashboard from './BacktestDashboard.vue'
import StrategyLab from './StrategyLab.vue'

const tabs = [
  { id: 'quick', label: '快速回测', icon: '🔬' },
  { id: 'advanced', label: '策略开发', icon: '🧪' },
]

const activeTab = ref('quick')
</script>
