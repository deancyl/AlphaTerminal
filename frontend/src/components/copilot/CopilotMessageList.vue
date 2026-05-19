<script setup>
import { ref, watch, nextTick, onUnmounted } from 'vue'
import { mdRender } from '../../composables/useCopilotMarkdown.js'
import { useInlineChartRenderer } from '../../composables/useInlineChartRenderer.js'
import { apiFetchDeduped } from '../../utils/api.js'
import CopyButton from './CopyButton.vue'
import ErrorRetry from './ErrorRetry.vue'

const props = defineProps({
  messages: { type: Array, default: () => [] },
  currentSymbol: { type: String, default: '' }
})

const emit = defineEmits(['retry'])

const historyEl = ref(null)
defineExpose({ historyEl })

const {
  renderMiniChart,
  renderCompareChart,
  renderCandlestickChart,
  disposeAll,
  processPendingCharts
} = useInlineChartRenderer()

async function fetchChartData(config) {
  const { source, symbol, period, metric } = config
  const actualSymbol = symbol || props.currentSymbol || ''
  
  if (!actualSymbol) {
    console.warn('[Copilot] No symbol for chart data fetch')
    return null
  }
  
  try {
    const cacheKey = `chart:${source}:${actualSymbol}:${period}`
    const response = await apiFetchDeduped(
      cacheKey,
      `/api/v1/copilot/chart_data/${source}/${actualSymbol}`,
      { timeoutMs: 10000 }
    )
    
    if (period && response.data) {
      const days = parseInt(period.replace('d', '').replace('y', '365')) || 30
      return response.data.slice(-days)
    }
    
    return response.data
  } catch (e) {
    console.error('[Copilot] Chart data fetch failed:', e)
    return null
  }
}

async function injectCharts() {
  await nextTick()
  if (!historyEl.value) return
  
  const chartContainers = historyEl.value.querySelectorAll('.mini-chart-container')
  
  for (const container of chartContainers) {
    if (container.dataset.rendered) continue
    
    const configStr = container.dataset.chartConfig
    if (!configStr) continue
    
    try {
      const config = JSON.parse(decodeURIComponent(configStr))
      const chartId = container.id
      
      const data = await fetchChartData(config)
      
      if (!data || data.length === 0) {
        container.innerHTML = '<div class="chart-error text-xs text-secondary p-2">暂无图表数据</div>'
        container.dataset.rendered = 'true'
        continue
      }
      
      container.innerHTML = ''
      container.style.width = '100%'
      container.style.height = '120px'
      
      if (config.type === 'compare') {
        renderCompareChart(chartId, data)
      } else if (config.type === 'candlestick') {
        renderCandlestickChart(chartId, data)
      } else {
        renderMiniChart(chartId, data, { type: config.type || 'line' })
      }
      
      container.dataset.rendered = 'true'
    } catch (e) {
      console.error('[Copilot] Chart render error:', e)
      container.innerHTML = '<div class="chart-error text-xs text-secondary p-2">图表渲染失败</div>'
    }
  }
}

function injectCopyButtons() {
  nextTick(() => {
    if (!historyEl.value) return
    const preElements = historyEl.value.querySelectorAll('pre[data-code]')
    preElements.forEach(pre => {
      if (pre.querySelector('button')) return
      const code = decodeURIComponent(pre.dataset.code || '')
      if (!code) return
      const button = document.createElement('button')
      button.className = 'absolute top-2 right-2 px-2 py-1 rounded text-xs opacity-0 group-hover:opacity-100 transition-opacity duration-200 bg-agent-blue/10 border border-agent-blue/30 hover:bg-agent-blue/20 hover:border-agent-blue/50 focus:outline-none focus:ring-2 focus:ring-agent-blue text-agent-blue'
      button.setAttribute('aria-label', '复制代码')
      button.textContent = '📋 复制'
      button.addEventListener('click', async () => {
        try {
          await navigator.clipboard.writeText(code)
          button.textContent = '✓ 已复制'
          button.className = button.className.replace('text-agent-blue', 'text-bearish border-bearish/30 bg-bearish/10')
          setTimeout(() => {
            button.textContent = '📋 复制'
            button.className = button.className.replace('text-bearish border-bearish/30 bg-bearish/10', 'text-agent-blue')
          }, 2000)
        } catch (err) {
          console.error('Copy failed:', err)
        }
      })
      pre.appendChild(button)
    })
  })
}

watch(() => props.messages, () => {
  injectCopyButtons()
  injectCharts()
}, { deep: true })

onUnmounted(() => {
  disposeAll()
})
</script>

<template>
  <div
    ref="historyEl"
    class="flex-1 overflow-y-auto p-4 space-y-3"
    role="log"
    aria-label="对话历史"
    aria-live="polite"
    aria-atomic="false"
  >
    <div v-if="messages.length === 0" class="text-center mt-12" role="status">
      <div class="text-4xl mb-3">💬</div>
      <p class="text-terminal-dim text-sm">开始一场投研对话</p>
      <div class="mt-4 text-xs text-terminal-dim/70 space-y-1">
        <p>💡 试试：「分析上证指数」</p>
        <p>💡 或：「今日涨停有哪些」</p>
        <p>💡 或：「打开贵州茅台」</p>
      </div>
    </div>

    <div
      v-for="(msg, i) in messages"
      :key="i"
      class="text-sm whitespace-pre-wrap leading-relaxed"
      :role="msg.role === 'user' ? 'presentation' : 'article'"
      :aria-label="msg.role === 'user' ? '用户消息' : 'AI回复'"
    >
      <div v-if="msg.role === 'user'"
           class="mr-4 ml-8 text-right">
        <div class="text-[10px] mb-1 text-agent-blue/70">你</div>
        <div class="text-gray-300">{{ msg.content }}</div>
      </div>

      <div v-else
           class="mr-4"
           :class="msg.isError ? 'border border-red-500/30 rounded p-3' : ''">
        <div class="text-[10px] mb-1 text-terminal-dim flex items-center gap-1">
          <span>🤖 AlphaTerminal</span>
          <span v-if="msg.fromCache" class="text-[10px] text-bearish">📋 缓存</span>
        </div>
        <div class="copilot-markdown text-gray-200" :class="msg.isError ? 'text-red-300' : ''">
          <span v-html="msg.renderedContent || mdRender(msg.displayedContent)"></span>
          <span v-if="msg.streaming" class="animate-pulse text-agent-blue">▌</span>
        </div>
        <ErrorRetry
          v-if="msg.isError && msg.errorType"
          :error="msg.error"
          :error-type="msg.errorType"
          :message-index="i"
          @retry="emit('retry', i)"
        />
      </div>
    </div>
  </div>
</template>
