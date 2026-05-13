<script setup>
const props = defineProps({
  ctxMarket: Boolean,
  ctxRates: Boolean,
  ctxNews: Boolean,
  ctxPortfolio: Boolean,
  ctxHistorical: Boolean,
  selectedProvider: String,
  selectedModel: String,
  providers: { type: Array, default: () => [] },
  currentModels: { type: Array, default: () => [] },
  portfolioList: { type: Array, default: () => [] },
  isLoadingPortfolio: Boolean,
  selectedPortfolioId: [String, Number]
})

const emit = defineEmits([
  'update:ctxMarket', 'update:ctxRates', 'update:ctxNews',
  'update:ctxPortfolio', 'update:ctxHistorical',
  'update:selectedProvider', 'update:selectedModel',
  'update:selectedPortfolioId'
])
</script>

<template>
  <!-- 上下文勾选框 -->
  <div class="px-4 py-2 border-b border-theme-secondary flex flex-wrap gap-3 text-xs shrink-0">
    <label class="flex items-center gap-1.5 cursor-pointer select-none" title="勾选后，AI将获取实时大盘指数数据作为对话上下文">
      <input type="checkbox" :checked="ctxMarket" @change="emit('update:ctxMarket', $event.target.checked)"
             class="accent-terminal-accent w-3 h-3 rounded-sm">
      <span :class="ctxMarket ? 'text-terminal-accent' : 'text-terminal-dim'">大盘</span>
    </label>
    <label class="flex items-center gap-1.5 cursor-pointer select-none" title="勾选后，AI将获取国债收益率曲线作为对话上下文">
      <input type="checkbox" :checked="ctxRates" @change="emit('update:ctxRates', $event.target.checked)"
             class="accent-terminal-accent w-3 h-3 rounded-sm">
      <span :class="ctxRates ? 'text-terminal-accent' : 'text-terminal-dim'">利率</span>
    </label>
    <label class="flex items-center gap-1.5 cursor-pointer select-none" title="勾选后，AI将获取最新5条市场快讯作为对话上下文">
      <input type="checkbox" :checked="ctxNews" @change="emit('update:ctxNews', $event.target.checked)"
             class="accent-terminal-accent w-3 h-3 rounded-sm">
      <span :class="ctxNews ? 'text-terminal-accent' : 'text-terminal-dim'">快讯</span>
    </label>
    <label class="flex items-center gap-1.5 cursor-pointer select-none" title="勾选后，AI将获取您的投资组合数据作为对话上下文">
      <input type="checkbox" :checked="ctxPortfolio" @change="emit('update:ctxPortfolio', $event.target.checked)"
             class="accent-terminal-accent w-3 h-3 rounded-sm">
      <span :class="ctxPortfolio ? 'text-terminal-accent' : 'text-terminal-dim'">组合</span>
    </label>
    <label class="flex items-center gap-1.5 cursor-pointer select-none" title="勾选后，AI将获取历史K线数据作为对话上下文">
      <input type="checkbox" :checked="ctxHistorical" @change="emit('update:ctxHistorical', $event.target.checked)"
             class="accent-terminal-accent w-3 h-3 rounded-sm">
      <span :class="ctxHistorical ? 'text-terminal-accent' : 'text-terminal-dim'">历史</span>
    </label>
    <span class="text-[10px] text-terminal-dim/50 ml-auto self-center">💡 勾选可将数据加入AI上下文</span>
  </div>

  <!-- Provider 选择 -->
  <div class="px-4 py-2 border-b border-theme-secondary flex items-center gap-2 shrink-0">
    <span class="text-[10px] text-terminal-dim shrink-0">🤖 模型</span>
    <select :value="selectedProvider" @change="emit('update:selectedProvider', $event.target.value)"
            class="flex-1 bg-terminal-bg border border-theme rounded-sm px-2 py-1 text-[11px]
                   text-theme-primary focus:outline-none focus:border-terminal-accent/60 cursor-pointer">
      <option v-for="p in providers" :key="p.id" :value="p.id">{{ p.label }}</option>
    </select>
    <select :value="selectedModel" @change="emit('update:selectedModel', $event.target.value)"
            class="flex-1 bg-terminal-bg border border-theme rounded-sm px-2 py-1 text-[11px]
                   text-theme-primary focus:outline-none focus:border-terminal-accent/60 cursor-pointer">
      <option v-for="m in currentModels" :key="m.value" :value="m.value">{{ m.label }}</option>
    </select>
  </div>

  <!-- 投资组合选择器 -->
  <div v-if="ctxPortfolio"
       class="px-4 py-2 border-b border-theme-secondary flex items-center gap-2 shrink-0">
    <span class="text-[10px] text-terminal-dim shrink-0">💼 组合</span>
    <select v-if="isLoadingPortfolio"
            class="flex-1 bg-terminal-bg border border-theme rounded-sm px-2 py-1 text-[11px]
                   text-theme-dim cursor-wait">
      <option>加载中...</option>
    </select>
    <select v-else-if="portfolioList.length > 0" :value="selectedPortfolioId" @change="emit('update:selectedPortfolioId', $event.target.value)"
            class="flex-1 bg-terminal-bg border border-theme rounded-sm px-2 py-1 text-[11px]
                   text-theme-primary focus:outline-none focus:border-terminal-accent/60 cursor-pointer">
      <option v-for="p in portfolioList" :key="p.id" :value="p.id">{{ p.name }}</option>
    </select>
    <span v-else class="flex-1 text-[11px] text-terminal-dim">暂无可用组合</span>
  </div>
</template>
