<template>
  <div v-if="hasError" class="widget-error-boundary flex flex-col items-center justify-center py-8" role="alert" aria-live="assertive">
    <div class="text-3xl mb-3" aria-hidden="true">⚠️</div>
    <div class="text-sm text-terminal-dim mb-3 text-center max-w-sm">
      {{ friendlyMessage }}
    </div>
    <button
      v-if="onRetry"
      class="px-3 py-1.5 text-xs rounded border border-terminal-accent text-terminal-accent hover:bg-terminal-accent hover:text-white transition"
      @click="handleRetry"
      aria-label="重试加载"
      type="button"
    >
      重试
    </button>
  </div>
  <slot v-else />
</template>

<script setup>
import { ref, onErrorCaptured } from 'vue'

const props = defineProps({
  widgetName: {
    type: String,
    required: true
  },
  onRetry: {
    type: Function,
    default: null
  }
})

const hasError = ref(false)
const errorMessage = ref('')

const widgetMessages = {
  'market-overview': '市场概览加载失败',
  'news-feed': '新闻快讯加载失败',
  'quote-panel': '行情面板加载失败',
  'kline-chart': 'K线图表加载失败',
  'bond-dashboard': '债券看板加载失败',
  'futures-panel': '期货面板加载失败',
  'portfolio': '投资组合加载失败',
  'backtest': '回测实验室加载失败',
  'sentiment': '市场情绪加载失败',
  'fund-flow': '资金流向加载失败',
  'stock-screener': '条件选股加载失败',
  'f9-detail': 'F9深度资料加载失败'
}

const friendlyMessage = ref('')

onErrorCaptured((err, instance, info) => {
  hasError.value = true
  errorMessage.value = err.message || '未知错误'
  friendlyMessage.value = widgetMessages[props.widgetName] || `${props.widgetName} 加载失败`
  console.error(`[WidgetErrorBoundary] ${props.widgetName} error:`, err, info)
  return false
})

function handleRetry() {
  hasError.value = false
  errorMessage.value = ''
  friendlyMessage.value = ''
  if (props.onRetry) {
    props.onRetry()
  }
}
</script>

<style scoped>
.widget-error-boundary {
  min-height: 150px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 4px;
}
</style>
