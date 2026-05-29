<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-lg font-bold text-theme-primary">💰 LLM 成本归因分析</h2>
        <p class="text-xs text-theme-muted mt-1">可视化 Token 消耗在不同工作流间的分布</p>
      </div>
      <div class="flex items-center gap-3">
        <input
          v-model="startDate"
          type="date"
          class="bg-theme-surface border border-theme rounded-sm px-3 py-2 text-sm text-theme-primary"
        >
        <span class="text-theme-muted">至</span>
        <input
          v-model="endDate"
          type="date"
          class="bg-theme-surface border border-theme rounded-sm px-3 py-2 text-sm text-theme-primary"
        >
        <button
          class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-sm text-sm hover:bg-terminal-accent/25 transition-colors"
          @click="loadAllData"
        >
          🔄 刷新
        </button>
      </div>
    </div>

    <LoadingSpinner v-if="loading" text="加载成本归因数据..." />

    <ErrorDisplay v-else-if="error" :error="error" :retry="loadAllData" />

    <template v-else>
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div class="p-4 bg-theme-surface rounded-sm border border-theme">
          <div class="text-[10px] text-theme-muted mb-1">总成本</div>
          <div class="text-2xl font-bold text-bull tabular-nums">
            ${{ sankeyData?.total_cost?.toFixed(4) || '0.0000' }}
          </div>
        </div>
        <div class="p-4 bg-theme-surface rounded-sm border border-theme">
          <div class="text-[10px] text-theme-muted mb-1">工作流类型</div>
          <div class="text-2xl font-bold text-terminal-accent tabular-nums">
            {{ sankeyData?.workflow_count || 0 }}
          </div>
        </div>
        <div class="p-4 bg-theme-surface rounded-sm border border-theme">
          <div class="text-[10px] text-theme-muted mb-1">模型数量</div>
          <div class="text-2xl font-bold text-theme-primary tabular-nums">
            {{ sankeyData?.model_count || 0 }}
          </div>
        </div>
      </div>

      <div class="bg-theme-surface rounded-sm border border-theme p-4">
        <h3 class="text-sm font-bold text-theme-primary mb-3">🔀 成本流向图 (Sankey)</h3>
        <div ref="sankeyChartRef" class="h-80"></div>
        <div v-if="!sankeyData?.nodes?.length" class="h-80 flex items-center justify-center text-theme-muted">
          暂无数据，请选择日期范围后刷新
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div class="bg-theme-surface rounded-sm border border-theme p-4">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-sm font-bold text-theme-primary">📊 成本分解</h3>
            <select
              v-model="groupBy"
              class="bg-theme-surface border border-theme rounded-sm px-2 py-1 text-xs text-theme-primary"
              @change="loadBreakdown"
            >
              <option value="workflow">按工作流</option>
              <option value="model">按模型</option>
              <option value="session">按会话</option>
            </select>
          </div>
          <div class="overflow-x-auto max-h-64">
            <table class="theme-table text-xs">
              <thead>
                <tr>
                  <th>名称</th>
                  <th class="text-right">请求数</th>
                  <th class="text-right">Token</th>
                  <th class="text-right">成本</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in breakdown" :key="item.name || item.model_id || item.session_id">
                  <td class="font-medium">{{ item.name || item.model_id || item.session_id?.slice(0, 16) }}</td>
                  <td class="text-right tabular-nums">{{ formatNumber(item.requests) }}</td>
                  <td class="text-right tabular-nums">{{ formatTokens(item.total_tokens) }}</td>
                  <td class="text-right tabular-nums text-bull">${{ (item.cost_usd || 0).toFixed(4) }}</td>
                </tr>
              </tbody>
            </table>
            <div v-if="breakdown.length === 0" class="p-4 text-center text-theme-muted">
              暂无数据
            </div>
          </div>
        </div>

        <div class="bg-theme-surface rounded-sm border border-theme p-4">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-sm font-bold text-theme-primary">🌳 提示词树</h3>
            <select
              v-model="selectedSessionId"
              class="bg-theme-surface border border-theme rounded-sm px-2 py-1 text-xs text-theme-primary w-48"
              @change="loadPromptTree"
            >
              <option value="">选择会话...</option>
              <option v-for="s in sessions" :key="s.session_id" :value="s.session_id">
                {{ s.session_id?.slice(0, 20) }} ({{ formatTokens(s.total_tokens) }})
              </option>
            </select>
          </div>
          <div v-if="promptTreeLoading" class="p-4 text-center text-theme-muted">
            加载中...
          </div>
          <div v-else-if="!selectedSessionId" class="p-4 text-center text-theme-muted">
            请选择一个会话查看提示词树
          </div>
          <div v-else-if="promptTree?.nodes?.length" class="max-h-64 overflow-y-auto space-y-2">
            <div
              v-for="node in promptTree.nodes"
              :key="node.id"
              class="p-2 bg-theme-hover rounded-sm border-l-2 border-terminal-accent"
            >
              <div class="flex items-center justify-between text-xs">
                <div class="flex items-center gap-2">
                  <span class="text-theme-muted">#{{ node.seq }}</span>
                  <span class="font-medium text-theme-primary">{{ node.model_id }}</span>
                </div>
                <div class="flex items-center gap-2">
                  <span class="text-theme-secondary">{{ formatTokens(node.total_tokens) }}</span>
                  <span class="text-bull tabular-nums">${{ node.cost_usd?.toFixed(6) }}</span>
                </div>
              </div>
              <div v-if="node.prompt_preview" class="mt-1 text-[10px] text-theme-muted truncate">
                {{ node.prompt_preview }}
              </div>
              <div v-if="node.tool_calls?.length" class="mt-1 text-[10px] text-terminal-accent">
                🔧 {{ node.tool_calls.length }} tool calls
              </div>
            </div>
            <div class="p-2 border-t border-theme text-xs text-theme-muted">
              总计: {{ promptTree.request_count }} 请求, {{ formatTokens(promptTree.total_tokens) }} tokens, ${{ promptTree.total_cost?.toFixed(4) }}
            </div>
          </div>
          <div v-else class="p-4 text-center text-theme-muted">
            该会话暂无数据
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, onDeactivated, onActivated, nextTick } from 'vue'
import { apiFetch } from '../../utils/api.js'
import { useECharts } from '../../composables/useECharts.js'
import { getECharts } from '../../utils/lazyEcharts.js'
import LoadingSpinner from '../f9/LoadingSpinner.vue'
import ErrorDisplay from '../f9/ErrorDisplay.vue'

const loading = ref(true)
const error = ref(null)

const today = new Date()
const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000)
const startDate = ref(weekAgo.toISOString().split('T')[0])
const endDate = ref(today.toISOString().split('T')[0])

const groupBy = ref('workflow')
const selectedSessionId = ref('')

const sankeyData = ref(null)
const breakdown = ref([])
const sessions = ref([])
const promptTree = ref(null)
const promptTreeLoading = ref(false)

const sankeyChartRef = ref(null)
const { initChart: initSankeyChart, setOption: setSankeyOption, dispose: disposeSankeyChart } = useECharts(sankeyChartRef)

async function loadAllData() {
  loading.value = true
  error.value = null
  try {
    await Promise.all([
      loadSankey(),
      loadBreakdown(),
      loadSessions()
    ])
  } catch (e) {
    error.value = e.message || '加载数据失败'
  } finally {
    loading.value = false
  }
}

async function loadSankey() {
  try {
    const res = await apiFetch(`/api/v1/cost_attribution/sankey?start_date=${startDate.value}&end_date=${endDate.value}`)
    sankeyData.value = res?.data || null
    await nextTick()
    await updateSankeyChart()
  } catch (e) {
    console.error('Failed to load sankey:', e)
  }
}

async function loadBreakdown() {
  try {
    const res = await apiFetch(`/api/v1/cost_attribution/breakdown?start_date=${startDate.value}&end_date=${endDate.value}&group_by=${groupBy.value}`)
    breakdown.value = res?.data || []
  } catch (e) {
    console.error('Failed to load breakdown:', e)
  }
}

async function loadSessions() {
  try {
    const res = await apiFetch(`/api/v1/cost_attribution/sessions?start_date=${startDate.value}&end_date=${endDate.value}&limit=50`)
    sessions.value = res?.data || []
  } catch (e) {
    console.error('Failed to load sessions:', e)
  }
}

async function loadPromptTree() {
  if (!selectedSessionId.value) {
    promptTree.value = null
    return
  }
  promptTreeLoading.value = true
  try {
    const res = await apiFetch(`/api/v1/cost_attribution/prompt_tree?session_id=${selectedSessionId.value}`)
    promptTree.value = res?.data || null
  } catch (e) {
    console.error('Failed to load prompt tree:', e)
    promptTree.value = null
  } finally {
    promptTreeLoading.value = false
  }
}

async function updateSankeyChart() {
  if (!sankeyData.value?.nodes?.length) return
  
  const echarts = await getECharts()
  const chart = await initSankeyChart()
  if (!chart) return

  const textColor = getComputedStyle(document.documentElement).getPropertyValue('--text-secondary').trim() || '#C9D1D9'

  setSankeyOption({
    tooltip: {
      trigger: 'item',
      triggerOn: 'mousemove',
      backgroundColor: 'rgba(30, 30, 30, 0.9)',
      borderColor: '#30363D',
      textStyle: { color: '#F0F6FC' },
      formatter: (params) => {
        if (params.dataType === 'node') {
          return `${params.name}`
        }
        const source = sankeyData.value.nodes[params.data.source]?.name || ''
        const target = sankeyData.value.nodes[params.data.target]?.name || ''
        return `${source} → ${target}<br/>$${params.data.value?.toFixed(4) || 0}`
      }
    },
    series: [
      {
        type: 'sankey',
        layout: 'none',
        emphasis: {
          focus: 'adjacency'
        },
        lineStyle: {
          color: 'gradient',
          curveness: 0.5,
          opacity: 0.6
        },
        label: {
          color: textColor,
          fontSize: 11
        },
        data: sankeyData.value.nodes,
        links: sankeyData.value.links,
        left: '5%',
        right: '5%',
        top: '5%',
        bottom: '5%'
      }
    ]
  })
}

function formatNumber(n) {
  if (!n) return '0'
  return n.toLocaleString()
}

function formatTokens(n) {
  if (!n) return '0'
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`
  return n.toString()
}

onMounted(async () => {
  await loadAllData()
})

onBeforeUnmount(() => {
  disposeSankeyChart()
})

// P0: KeepAlive cleanup
onDeactivated(() => {
  // Clear chart to free memory
  disposeSankeyChart()
})

onActivated(() => {
  // Re-render chart if data exists
  if (sankeyData.value?.nodes?.length) {
    nextTick(() => updateSankeyChart())
  }
})
</script>
