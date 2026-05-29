<template>
  <!-- P0: Error state UI -->
  <div v-if="componentError" class="flex flex-col w-full h-full items-center justify-center p-8" role="alert" aria-live="assertive">
    <div class="text-4xl mb-4" aria-hidden="true">⚠️</div>
    <div class="text-lg text-terminal-dim mb-2">智能投研工作流加载失败</div>
    <div class="text-sm text-theme-muted mb-4 max-w-md text-center">{{ componentError.message }}</div>
    <button
      class="px-4 py-2 text-sm rounded border border-terminal-accent text-terminal-accent hover:bg-terminal-accent hover:text-white transition"
      @click="handleRetry"
      aria-label="重试加载"
      type="button"
    >
      重试
    </button>
  </div>

  <div v-else class="flex flex-col h-full bg-theme-secondary border-l border-agent-blue/20">
    <!-- Header -->
    <div class="flex items-center justify-between p-4 border-b border-border-light">
      <div class="flex items-center gap-2">
        <span class="text-xl">🤖</span>
        <h2 class="text-lg font-semibold text-primary">智能投研工作流</h2>
      </div>
      <button
        @click="clearWorkflow"
        class="px-3 py-1.5 text-sm rounded-lg bg-agent-blue/10 hover:bg-agent-blue/20 text-agent-blue transition-colors"
      >
        清空
      </button>
    </div>

    <!-- Input Area -->
    <div class="p-4 border-b border-border-light">
      <div class="flex gap-2">
        <input
          v-model="queryInput"
          type="text"
          placeholder="输入自然语言任务，如：盘点今日半导体板块异动并生成研报"
          class="flex-1 px-4 py-2 rounded-lg bg-bg-surface border border-border-base text-primary placeholder:text-muted focus:border-agent-blue focus:outline-none"
          @keydown.enter="executeWorkflow"
          :disabled="isExecuting"
        />
        <button
          @click="executeWorkflow"
          :disabled="isExecuting || !queryInput.trim()"
          class="px-4 py-2 rounded-lg bg-agent-blue hover:bg-agent-blue-hover text-white font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {{ isExecuting ? '执行中...' : '执行' }}
        </button>
      </div>
      
      <!-- Quick Examples -->
      <div class="mt-3 flex flex-wrap gap-2">
        <button
          v-for="example in quickExamples"
          :key="example"
          @click="queryInput = example"
          class="px-2 py-1 text-xs rounded bg-bg-surface-hover text-secondary hover:text-primary transition-colors"
        >
          {{ example }}
        </button>
      </div>
    </div>

    <!-- Workflow Progress -->
    <div v-if="currentWorkflow" class="p-4 border-b border-border-light">
      <div class="flex items-center gap-2 mb-3">
        <span class="text-sm text-secondary">工作流 ID:</span>
        <span class="text-sm text-primary font-mono">{{ currentWorkflow.id }}</span>
        <span
          :class="[
            'px-2 py-0.5 text-xs rounded',
            statusColors[currentWorkflow.status] || 'bg-gray-500/20 text-gray-400'
          ]"
        >
          {{ statusLabels[currentWorkflow.status] || currentWorkflow.status }}
        </span>
      </div>

      <!-- Steps -->
      <div class="space-y-2">
        <div
          v-for="step in currentWorkflow.steps"
          :key="step.id"
          class="flex items-center gap-3 p-2 rounded bg-bg-surface"
        >
          <span
            :class="[
              'w-6 h-6 flex items-center justify-center rounded-full text-xs',
              step.status === 'completed' ? 'bg-green-500/20 text-green-400' :
              step.status === 'running' ? 'bg-blue-500/20 text-blue-400 animate-pulse' :
              step.status === 'failed' ? 'bg-red-500/20 text-red-400' :
              'bg-gray-500/20 text-gray-400'
            ]"
          >
            {{ step.status === 'completed' ? '✓' : step.status === 'failed' ? '✗' : step.status === 'running' ? '●' : '○' }}
          </span>
          <span class="text-sm text-primary">{{ step.tool }}</span>
          <span v-if="step.elapsed_ms" class="text-xs text-muted">{{ step.elapsed_ms.toFixed(0) }}ms</span>
          <span v-if="step.error" class="text-xs text-red-400">{{ step.error }}</span>
        </div>
      </div>
    </div>

    <!-- Report Display -->
    <div class="flex-1 overflow-auto p-4">
      <div v-if="report" class="prose prose-invert max-w-none">
        <div v-html="renderedReport" class="copilot-markdown"></div>
      </div>
      <div v-else-if="isExecuting" class="flex items-center justify-center h-full">
        <div class="flex flex-col items-center gap-3">
          <div class="w-8 h-8 border-2 border-agent-blue border-t-transparent rounded-full animate-spin"></div>
          <span class="text-sm text-secondary">正在执行工作流...</span>
        </div>
      </div>
      <div v-else class="flex items-center justify-center h-full text-muted">
        <span>输入自然语言任务开始分析</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onDeactivated, onActivated } from 'vue'
import { apiFetch } from '../utils/api.js'
import { mdRender } from '../composables/useCopilotMarkdown.js'

const queryInput = ref('')
const isExecuting = ref(false)

// P0: Error state for component initialization errors
const componentError = ref(null)
const currentWorkflow = ref(null)
const report = ref('')
const workflowId = ref(null)

const quickExamples = [
  '分析茅台最新行情和新闻',
  '盘点今日半导体板块异动',
  '对比茅台和五粮液财务指标',
  '分析CPI对消费板块影响',
]

const statusLabels = {
  pending: '待执行',
  running: '执行中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
}

const statusColors = {
  pending: 'bg-gray-500/20 text-gray-400',
  running: 'bg-blue-500/20 text-blue-400',
  completed: 'bg-green-500/20 text-green-400',
  failed: 'bg-red-500/20 text-red-400',
  cancelled: 'bg-yellow-500/20 text-yellow-400',
}

const renderedReport = computed(() => {
  if (!report.value) return ''
  return mdRender(report.value)
})

async function executeWorkflow() {
  if (!queryInput.value.trim() || isExecuting.value) return
  
  isExecuting.value = true
  currentWorkflow.value = null
  report.value = ''
  
  try {
    const response = await apiFetch('/api/v1/agentic/workflow', {
      method: 'POST',
      body: JSON.stringify({
        query: queryInput.value.trim(),
        execute: true
      })
    })
    
    if (response.code === 0) {
      workflowId.value = response.data.workflow_id
      currentWorkflow.value = {
        id: response.data.workflow_id,
        status: 'running',
        steps: []
      }
      
      await pollWorkflowStatus()
    } else {
      console.error('Workflow creation failed:', response.message)
    }
  } catch (error) {
    console.error('Workflow execution error:', error)
  } finally {
    isExecuting.value = false
  }
}

async function pollWorkflowStatus() {
  if (!workflowId.value) return
  
  const maxPolls = 60
  const pollInterval = 1000
  
  for (let i = 0; i < maxPolls; i++) {
    try {
      const response = await apiFetch(`/api/v1/agentic/workflow/${workflowId.value}`)
      
      if (response.code === 0) {
        currentWorkflow.value = response.data
        
        if (response.data.status === 'completed' || response.data.status === 'failed') {
          if (response.data.result) {
            report.value = response.data.result
          }
          break
        }
      }
    } catch (error) {
      console.error('Poll error:', error)
    }
    
    await new Promise(resolve => setTimeout(resolve, pollInterval))
  }
}

function clearWorkflow() {
  queryInput.value = ''
  currentWorkflow.value = null
  report.value = ''
  workflowId.value = null
  isExecuting.value = false
}

// P0: KeepAlive cleanup
onDeactivated(() => {
  // Cancel any running workflow polling
  if (isExecuting.value) {
    isExecuting.value = false
    workflowId.value = null
  }
})

// P0: Retry function for component initialization errors
function handleRetry() {
  componentError.value = null
  clearWorkflow()
}

onActivated(() => {
  // Ready for new workflow execution
})
</script>

<style scoped>
.copilot-markdown {
  color: var(--text-gray-200);
}

.copilot-markdown h1 {
  font-size: 1.5rem;
  font-weight: 600;
  margin-bottom: 1rem;
  color: var(--text-slate-100);
}

.copilot-markdown h2 {
  font-size: 1.25rem;
  font-weight: 600;
  margin-top: 1.5rem;
  margin-bottom: 0.75rem;
  color: var(--text-slate-100);
}

.copilot-markdown table {
  width: 100%;
  border-collapse: collapse;
  margin: 1rem 0;
}

.copilot-markdown th,
.copilot-markdown td {
  padding: 0.5rem 0.75rem;
  border: 1px solid rgba(59, 130, 246, 0.2);
  text-align: left;
}

.copilot-markdown th {
  background: rgba(59, 130, 246, 0.1);
  font-weight: 500;
}

.copilot-markdown p {
  margin: 0.5rem 0;
}

.copilot-markdown ul,
.copilot-markdown ol {
  margin: 0.5rem 0;
  padding-left: 1.5rem;
}

.copilot-markdown li {
  margin: 0.25rem 0;
}
</style>