<template>
  <ErrorBoundary>
    <div class="flex flex-col w-full h-full overflow-hidden">
      <div class="flex items-center gap-1 px-4 py-2 border-b border-theme-secondary bg-terminal-panel/80 shrink-0">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          @click="handleTabChange(tab.id)"
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
          <span v-else-if="activeTab === 'advanced'">策略开发：可视化构建或自定义代码</span>
          <span v-else-if="activeTab === 'ml'">ML策略：使用机器学习模型进行预测和组合优化</span>
          <span v-else-if="activeTab === 'attribution'">多因子归因：拖拽因子组合进行归因分析</span>
        </div>
      </div>

      <div class="flex-1 overflow-hidden">
        <BacktestDashboard v-if="activeTab === 'quick'" />
        <StrategyLab v-else-if="activeTab === 'advanced'" />
        <MLStrategyPanel v-else-if="activeTab === 'ml'" />
        <FactorSandbox v-else-if="activeTab === 'attribution'" />
      </div>
    </div>
  </ErrorBoundary>
</template>

<script setup>
import { ref } from 'vue'
import ErrorBoundary from './ErrorBoundary.vue'
import BacktestDashboard from './BacktestDashboard.vue'
import StrategyLab from './StrategyLab.vue'
import MLStrategyPanel from './MLStrategyPanel.vue'
import FactorSandbox from './attribution/FactorSandbox.vue'

const tabs = [
  { id: 'quick', label: '快速回测', icon: '🔬' },
  { id: 'advanced', label: '策略开发', icon: '🧪' },
  { id: 'ml', label: 'ML策略', icon: '🤖' },
  { id: 'attribution', label: '因子归因', icon: '📊' },
]

const activeTab = ref('quick')

const handleTabChange = (tabId) => {
  activeTab.value = tabId
}
</script>
