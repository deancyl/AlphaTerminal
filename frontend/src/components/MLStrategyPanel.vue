<template>
  <ErrorBoundary>
    <div class="flex flex-col w-full h-full overflow-hidden">
      <!-- Sub-tab bar -->
      <div class="flex items-center gap-1 px-4 py-2 border-b border-theme-secondary bg-terminal-panel/80 shrink-0">
        <button
          v-for="tab in mlTabs"
          :key="tab.id"
          @click="activeMLTab = tab.id"
          class="px-3 py-1.5 text-xs font-medium rounded-sm transition-all"
          :class="activeMLTab === tab.id
            ? 'bg-terminal-accent/20 text-terminal-accent border-b-2 border-terminal-accent'
            : 'text-theme-secondary hover:text-theme-primary hover:bg-theme-hover'"
          :aria-pressed="activeMLTab === tab.id"
          type="button"
        >
          <span class="mr-1">{{ tab.icon }}</span>
          {{ tab.label }}
        </button>
        <div class="ml-auto text-xs text-theme-muted">
          <span v-if="activeMLTab === 'models'">模型管理：查看和管理ML模型</span>
          <span v-else-if="activeMLTab === 'train'">模型训练：训练新的ML模型</span>
          <span v-else-if="activeMLTab === 'predict'">预测分析：生成交易信号</span>
          <span v-else-if="activeMLTab === 'optimize'">组合优化：资产配置优化</span>
          <span v-else-if="activeMLTab === 'factors'">因子分析：因子暴露分析</span>
        </div>
      </div>

      <!-- Content area -->
      <div class="flex-1 overflow-hidden">
        <MLModelManager v-if="activeMLTab === 'models'" />
        <MLTrainingPanel v-else-if="activeMLTab === 'train'" />
        <MLPredictionPanel v-else-if="activeMLTab === 'predict'" />
        <MLPortfolioOptimizer v-else-if="activeMLTab === 'optimize'" />
        <MLFactorAnalysis v-else-if="activeMLTab === 'factors'" />
      </div>
    </div>
  </ErrorBoundary>
</template>

<script setup>
import { ref } from 'vue'
import ErrorBoundary from './ErrorBoundary.vue'
import MLModelManager from './ml/MLModelManager.vue'
import MLTrainingPanel from './ml/MLTrainingPanel.vue'
import MLPredictionPanel from './ml/MLPredictionPanel.vue'
import MLPortfolioOptimizer from './ml/MLPortfolioOptimizer.vue'
import MLFactorAnalysis from './ml/MLFactorAnalysis.vue'

const mlTabs = [
  { id: 'models', label: '模型管理', icon: '📦' },
  { id: 'train', label: '模型训练', icon: '🎓' },
  { id: 'predict', label: '预测分析', icon: '🔮' },
  { id: 'optimize', label: '组合优化', icon: '⚖️' },
  { id: 'factors', label: '因子分析', icon: '📊' },
]

const activeMLTab = ref('models')
</script>
