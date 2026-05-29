<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-bold text-theme-primary">🔬 回测沙箱监控</h2>
      <div class="flex items-center gap-2">
        <span 
          class="px-2 py-1 rounded text-xs"
          :class="wsConnected ? 'bg-[var(--color-success-bg)] text-[var(--color-success)]' : 'bg-[var(--color-warning-bg)] text-[var(--color-warning)]'"
        >
          {{ wsConnected ? '● 实时连接' : '○ 离线' }}
        </span>
        <button
          class="px-3 py-1.5 bg-theme-secondary/50 text-theme-secondary rounded text-sm hover:bg-theme-hover"
          @click="refreshMetrics"
        >
          刷新
        </button>
      </div>
    </div>

    <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
      <div class="bg-terminal-panel border border-theme rounded p-3">
        <div class="text-xs text-theme-muted mb-1">运行中</div>
        <div class="text-2xl font-bold text-terminal-accent">{{ summary.running }}</div>
      </div>
      <div class="bg-terminal-panel border border-theme rounded p-3">
        <div class="text-xs text-theme-muted mb-1">已完成</div>
        <div class="text-2xl font-bold text-[var(--color-success)]">{{ summary.completed }}</div>
      </div>
      <div class="bg-terminal-panel border border-theme rounded p-3">
        <div class="text-xs text-theme-muted mb-1">CPU</div>
        <div class="text-2xl font-bold text-theme-primary">{{ summary.total_cpu_percent.toFixed(1) }}%</div>
      </div>
      <div class="bg-terminal-panel border border-theme rounded p-3">
        <div class="text-xs text-theme-muted mb-1">内存</div>
        <div class="text-2xl font-bold text-theme-primary">{{ summary.total_memory_mb.toFixed(0) }} MB</div>
      </div>
    </div>

    <div v-if="workers.length === 0" class="text-center py-8 text-theme-muted">
      <div class="text-4xl mb-2">📭</div>
      <div>暂无运行中的回测任务</div>
    </div>

    <div v-else class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-theme text-theme-muted text-left">
            <th class="py-2 px-3">ID</th>
            <th class="py-2 px-3">股票</th>
            <th class="py-2 px-3">策略</th>
            <th class="py-2 px-3">状态</th>
            <th class="py-2 px-3">进度</th>
            <th class="py-2 px-3">时长</th>
            <th class="py-2 px-3">CPU</th>
            <th class="py-2 px-3">内存</th>
            <th class="py-2 px-3">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr 
            v-for="worker in workers" 
            :key="worker.id"
            class="border-b border-theme/50 hover:bg-theme-hover"
          >
            <td class="py-2 px-3 font-mono text-xs">{{ worker.id.slice(0, 12) }}...</td>
            <td class="py-2 px-3">{{ worker.symbol }}</td>
            <td class="py-2 px-3">{{ strategyLabels[worker.strategy_type] || worker.strategy_type }}</td>
            <td class="py-2 px-3">
              <span 
                class="px-2 py-0.5 rounded text-xs"
                :class="statusClasses[worker.status]"
              >
                {{ statusLabels[worker.status] || worker.status }}
              </span>
            </td>
            <td class="py-2 px-3">
              <div class="flex items-center gap-2">
                <div class="flex-1 h-2 bg-theme-secondary/30 rounded overflow-hidden">
                  <div 
                    class="h-full transition-all duration-300"
                    :class="worker.status === 'failed' ? 'bg-[var(--color-danger)]' : 'bg-terminal-accent'"
                    :style="{ width: worker.progress + '%' }"
                  ></div>
                </div>
                <span class="text-xs text-theme-muted w-10">{{ worker.progress.toFixed(0) }}%</span>
              </div>
            </td>
            <td class="py-2 px-3">{{ worker.duration_str }}</td>
            <td class="py-2 px-3">{{ worker.cpu_percent.toFixed(1) }}%</td>
            <td class="py-2 px-3">{{ worker.memory_mb.toFixed(0) }} MB</td>
            <td class="py-2 px-3">
              <button
                v-if="worker.status === 'running'"
                class="px-2 py-1 bg-[var(--color-danger-bg)] text-[var(--color-danger)] rounded text-xs hover:opacity-80"
                @click="confirmKill(worker)"
              >
                终止
              </button>
              <span v-else class="text-xs text-theme-muted">-</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="workers.some(w => w.error)" class="mt-4">
      <h3 class="text-sm font-bold text-[var(--color-danger)] mb-2">错误信息</h3>
      <div class="space-y-2">
        <div 
          v-for="worker in workers.filter(w => w.error)" 
          :key="worker.id"
          class="p-2 bg-[var(--color-danger-bg)]/20 border border-[var(--color-danger)]/30 rounded text-xs"
        >
          <span class="font-mono">{{ worker.id }}:</span> {{ worker.error }}
        </div>
      </div>
    </div>

    <div v-if="showConfirm" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div class="bg-terminal-panel border border-theme rounded p-6 max-w-md w-full mx-4">
        <h3 class="text-lg font-bold text-[var(--color-danger)] mb-2">⚠️ 确认终止</h3>
        <p class="text-sm text-theme-secondary mb-4">
          确定要终止回测任务 <span class="font-mono">{{ workerToKill?.id }}</span> 吗？<br>
          <span class="text-[var(--color-warning)]">此操作不可撤销。</span>
        </p>
        <div class="flex gap-3 justify-end">
          <button
            class="px-4 py-2 bg-theme-secondary/50 text-theme-secondary rounded text-sm hover:bg-theme-hover"
            @click="showConfirm = false"
          >
            取消
          </button>
          <button
            class="px-4 py-2 bg-[var(--color-danger-bg)] text-[var(--color-danger)] rounded text-sm hover:opacity-80"
            :disabled="isKilling"
            @click="executeKill"
          >
            {{ isKilling ? '终止中...' : '确认终止' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, onDeactivated, onActivated, computed } from 'vue'
import { apiFetch } from '../../utils/api.js'
import { toast } from '../../composables/useToast.js'
import { logger } from '../../utils/logger.js'

const workers = ref([])
const summary = reactive({
  total_workers: 0,
  running: 0,
  completed: 0,
  failed: 0,
  cancelled: 0,
  total_cpu_percent: 0,
  total_memory_mb: 0
})

const wsConnected = ref(false)
let ws = null

const statusLabels = {
  running: '运行中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消'
}

const statusClasses = {
  running: 'bg-terminal-accent/20 text-terminal-accent',
  completed: 'bg-[var(--color-success-bg)] text-[var(--color-success)]',
  failed: 'bg-[var(--color-danger-bg)] text-[var(--color-danger)]',
  cancelled: 'bg-[var(--color-warning-bg)] text-[var(--color-warning)]'
}

const strategyLabels = {
  ma_crossover: '双均线',
  rsi_oversold: 'RSI超卖',
  bollinger_bands: '布林带',
  ml_lightgbm: 'ML-LightGBM',
  ml_qlib_hist: 'ML-HIST',
  ml_ensemble: 'ML集成'
}

const showConfirm = ref(false)
const workerToKill = ref(null)
const isKilling = ref(false)

function buildWsUrl() {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}/api/v1/backtest_monitor/stream`
}

function connectWebSocket() {
  if (ws) {
    ws.close()
    ws = null
  }
  
  try {
    ws = new WebSocket(buildWsUrl())
    
    ws.onopen = () => {
      wsConnected.value = true
      logger.info('[BacktestMonitor] WebSocket connected')
    }
    
    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data)
        if (data.type === 'backtest_metrics') {
          workers.value = data.workers || []
          Object.assign(summary, data.summary || {})
        }
      } catch (e) {
        logger.warn('[BacktestMonitor] Parse error:', e)
      }
    }
    
    ws.onerror = (e) => {
      logger.warn('[BacktestMonitor] WebSocket error:', e)
    }
    
    ws.onclose = () => {
      wsConnected.value = false
      ws = null
      setTimeout(connectWebSocket, 5000)
    }
  } catch (e) {
    logger.error('[BacktestMonitor] WebSocket connect failed:', e)
    setTimeout(connectWebSocket, 10000)
  }
}

function disconnectWebSocket() {
  if (ws) {
    ws.close()
    ws = null
  }
  wsConnected.value = false
}

async function refreshMetrics() {
  try {
    const data = await apiFetch('/api/v1/backtest_monitor/metrics')
    workers.value = data.workers || []
    Object.assign(summary, data.summary || {})
  } catch (e) {
    logger.error('[BacktestMonitor] Refresh failed:', e)
    toast.error('刷新失败: ' + e.message)
  }
}

function confirmKill(worker) {
  workerToKill.value = worker
  showConfirm.value = true
}

async function executeKill() {
  if (!workerToKill.value) return
  
  isKilling.value = true
  try {
    await apiFetch(`/api/v1/backtest_monitor/kill/${workerToKill.value.id}`, { method: 'POST' })
    toast.success(`已终止任务 ${workerToKill.value.id}`)
    showConfirm.value = false
    workerToKill.value = null
    await refreshMetrics()
  } catch (e) {
    toast.error('终止失败: ' + e.message)
  } finally {
    isKilling.value = false
  }
}

onMounted(() => {
  refreshMetrics()
  connectWebSocket()
})

onUnmounted(() => {
  disconnectWebSocket()
})

// P0: KeepAlive cleanup
onDeactivated(() => {
  // Disconnect WebSocket to save resources
  disconnectWebSocket()
})

onActivated(() => {
  // Reconnect WebSocket and refresh data
  refreshMetrics()
  connectWebSocket()
})

defineExpose({ refreshMetrics })
</script>
