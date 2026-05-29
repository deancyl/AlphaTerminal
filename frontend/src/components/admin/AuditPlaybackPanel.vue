<template>
  <!-- P0: Error state UI -->
  <div v-if="componentError" class="flex flex-col items-center justify-center p-8 min-h-[300px]" role="alert" aria-live="assertive">
    <div class="text-4xl mb-4" aria-hidden="true">⚠️</div>
    <div class="text-lg text-terminal-dim mb-2">审计回放加载失败</div>
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

  <div v-else class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-lg font-bold text-theme-primary">📜 审计回放</h2>
        <p class="text-xs text-theme-muted mt-1">查看配置变更历史，支持时间旅行回滚</p>
      </div>
      <div class="flex gap-2">
        <button 
          class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-sm text-sm"
          @click="verifyChain"
        >🔐 验证链</button>
        <button 
          class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-sm text-sm"
          @click="fetchTimeline"
        >🔄 刷新</button>
      </div>
    </div>

    <!-- Chain Status -->
    <div class="p-4 rounded-sm border" :class="chainValid ? 'bg-[var(--color-success-bg)] border-[var(--color-success-border)]' : 'bg-[var(--color-danger-bg)] border-[var(--color-danger-border)]'">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <span class="w-3 h-3 rounded-full" :class="chainValid ? 'bg-[var(--color-success)]' : 'bg-[var(--color-danger)]'"></span>
          <span class="text-sm font-medium text-theme-primary">
            哈希链状态: {{ chainValid ? '✅ 完整' : '❌ 已损坏' }}
          </span>
        </div>
        <div class="text-xs text-theme-muted">
          共 {{ chainStats.total_records || 0 }} 条记录 | 链索引: {{ chainStats.chain_index_min || 0 }} - {{ chainStats.chain_index_max || 0 }}
        </div>
      </div>
      <div v-if="!chainValid && verifyResult.first_invalid_id" class="mt-2 text-xs text-[var(--color-danger)]">
        ⚠️ 首条无效记录 ID: {{ verifyResult.first_invalid_id }} | 错误类型: {{ verifyResult.error_type }}
      </div>
    </div>

    <!-- Timeline Slider -->
    <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
      <h3 class="text-sm font-bold text-theme-primary mb-3">⏱️ 时间轴</h3>
      <div class="space-y-3">
        <div class="flex items-center gap-4">
          <input 
            type="range" 
            v-model="timelineIndex" 
            min="0" 
            :max="timeline.length - 1"
            class="flex-1 h-2 bg-terminal-bg rounded-lg appearance-none cursor-pointer"
          />
          <span class="text-xs text-theme-muted w-32 text-right">
            {{ selectedRecord?.timestamp ? formatTimestamp(selectedRecord.timestamp) : '-' }}
          </span>
        </div>
        <div class="flex items-center justify-between text-xs text-theme-muted">
          <span>最早: {{ timeline.length > 0 ? formatTimestamp(timeline[timeline.length - 1]?.timestamp) : '-' }}</span>
          <span>最新: {{ timeline.length > 0 ? formatTimestamp(timeline[0]?.timestamp) : '-' }}</span>
        </div>
      </div>
    </div>

    <!-- Selected Record Details -->
    <div v-if="selectedRecord" class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
      <h3 class="text-sm font-bold text-theme-primary mb-3">📋 选中的审计记录</h3>
      <div class="grid grid-cols-2 gap-4 text-sm">
        <div>
          <span class="text-theme-muted">记录 ID:</span>
          <span class="ml-2 text-theme-primary">{{ selectedRecord.id }}</span>
        </div>
        <div>
          <span class="text-theme-muted">操作类型:</span>
          <span class="ml-2 text-theme-primary">{{ selectedRecord.action }}</span>
        </div>
        <div>
          <span class="text-theme-muted">操作者:</span>
          <span class="ml-2 text-theme-primary">{{ selectedRecord.actor_id }}</span>
        </div>
        <div>
          <span class="text-theme-muted">资源:</span>
          <span class="ml-2 text-theme-primary">{{ selectedRecord.resource }}</span>
        </div>
      </div>
    </div>

    <!-- Diff View -->
    <div v-if="diffData.changes.length > 0" class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
      <h3 class="text-sm font-bold text-theme-primary mb-3">🔍 变更对比</h3>
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div class="p-3 bg-[var(--color-danger-bg)]/30 rounded-sm border border-[var(--color-danger-border)]">
          <h4 class="text-xs font-bold text-[var(--color-danger)] mb-2">旧值 (Before)</h4>
          <pre class="text-xs text-theme-primary overflow-auto max-h-60">{{ formatJSON(diffData.beforeState) }}</pre>
        </div>
        <div class="p-3 bg-[var(--color-success-bg)]/30 rounded-sm border border-[var(--color-success-border)]">
          <h4 class="text-xs font-bold text-[var(--color-success)] mb-2">新值 (After)</h4>
          <pre class="text-xs text-theme-primary overflow-auto max-h-60">{{ formatJSON(diffData.afterState) }}</pre>
        </div>
      </div>
      
      <!-- Field Changes Table -->
      <div class="mt-4">
        <h4 class="text-xs font-bold text-theme-primary mb-2">字段变更明细</h4>
        <div class="overflow-x-auto">
          <table class="w-full text-xs">
            <thead>
              <tr class="border-b border-theme">
                <th class="text-left p-2 text-theme-muted">字段</th>
                <th class="text-left p-2 text-[var(--color-danger)]">旧值</th>
                <th class="text-left p-2 text-[var(--color-success)]">新值</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(change, idx) in diffData.changes" :key="idx" class="border-b border-theme/50">
                <td class="p-2 text-theme-primary font-medium">{{ change.field }}</td>
                <td class="p-2 text-[var(--color-danger)]">{{ formatValue(change.old_value) }}</td>
                <td class="p-2 text-[var(--color-success)]">{{ formatValue(change.new_value) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Rollback Section -->
    <div v-if="selectedRecord" class="p-4 bg-[var(--color-warning-bg)] border border-[var(--color-warning-border)] rounded-sm">
      <h3 class="text-sm font-bold text-[var(--color-warning)] mb-2">⚠️ 时间旅行回滚</h3>
      <p class="text-xs text-theme-muted mb-3">
        回滚将恢复配置到选中时间点的状态。此操作不可逆，请谨慎操作。
      </p>
      <div class="flex items-center gap-4">
        <label class="flex items-center gap-2 text-xs text-theme-primary">
          <input type="checkbox" v-model="rollbackConfirmed" class="rounded" />
          我已确认要执行回滚操作
        </label>
        <button 
          :disabled="!rollbackConfirmed || isRollingBack"
          class="px-4 py-2 bg-[var(--color-danger)] text-white rounded-sm text-xs disabled:opacity-50"
          @click="executeRollback"
        >{{ isRollingBack ? '回滚中...' : '执行回滚' }}</button>
      </div>
    </div>

    <!-- Timeline List -->
    <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
      <h3 class="text-sm font-bold text-theme-primary mb-3">📊 审计记录列表</h3>
      <div class="space-y-2 max-h-60 overflow-y-auto">
        <div 
          v-for="(record, idx) in timeline" 
          :key="record.id"
          class="p-2 rounded-sm cursor-pointer transition-colors"
          :class="timelineIndex === idx ? 'bg-terminal-accent/20 border border-terminal-accent' : 'bg-terminal-panel/50 hover:bg-terminal-panel'"
          @click="timelineIndex = idx"
        >
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <span class="text-xs px-1.5 py-0.5 rounded-sm" :class="getActionClass(record.action)">
                {{ record.action }}
              </span>
              <span class="text-xs text-theme-primary">{{ record.resource }}</span>
            </div>
            <span class="text-xs text-theme-muted">{{ formatTimestamp(record.timestamp) }}</span>
          </div>
        </div>
        <div v-if="timeline.length === 0" class="text-center text-theme-muted text-xs py-4">
          暂无审计记录
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onDeactivated, onActivated } from 'vue'

const emit = defineEmits(['refresh', 'verify-chain', 'rollback', 'fetch-timeline', 'fetch-diff', 'fetch-record'])

// P0: Error state for component initialization errors
const componentError = ref(null)

const timeline = ref([])
const timelineIndex = ref(0)
const chainValid = ref(true)
const chainStats = ref({})
const verifyResult = ref({})
const diffData = ref({ changes: [], beforeState: null, afterState: null })
const rollbackConfirmed = ref(false)
const isRollingBack = ref(false)

const selectedRecord = computed(() => {
  if (timeline.value.length === 0 || timelineIndex.value < 0) return null
  return timeline.value[timelineIndex.value]
})

watch(selectedRecord, async (record) => {
  if (record) {
    emit('fetch-record', record.id)
  }
})

function formatTimestamp(ts) {
  if (!ts) return '-'
  try {
    const d = new Date(ts)
    return d.toLocaleString('zh-CN', { 
      year: 'numeric', 
      month: '2-digit', 
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  } catch {
    return ts
  }
}

function formatJSON(obj) {
  if (!obj) return 'null'
  try {
    return JSON.stringify(obj, null, 2)
  } catch {
    return String(obj)
  }
}

function formatValue(val) {
  if (val === null || val === undefined) return '-'
  if (typeof val === 'object') return JSON.stringify(val)
  return String(val)
}

function getActionClass(action) {
  if (action === 'buy' || action === 'deposit' || action === 'transfer_in') {
    return 'bg-[var(--color-success-bg)] text-[var(--color-success)]'
  }
  if (action === 'sell' || action === 'withdraw' || action === 'transfer_out') {
    return 'bg-[var(--color-danger-bg)] text-[var(--color-danger)]'
  }
  return 'bg-[var(--color-info-bg)] text-[var(--color-info)]'
}

async function verifyChain() {
  emit('verify-chain')
}

async function fetchTimeline() {
  emit('fetch-timeline')
}

async function executeRollback() {
  if (!rollbackConfirmed.value || !selectedRecord.value) return
  
  isRollingBack.value = true
  emit('rollback', selectedRecord.value.timestamp)
  
  setTimeout(() => {
    isRollingBack.value = false
    rollbackConfirmed.value = false
  }, 2000)
}

function setTimeline(data) {
  timeline.value = data
}

function setChainStatus(valid, stats, result = {}) {
  chainValid.value = valid
  chainStats.value = stats
  verifyResult.value = result
}

function setDiffData(data) {
  diffData.value = data
}

defineExpose({
  setTimeline,
  setChainStatus,
  setDiffData
})

// P0: Retry function for component initialization errors
function handleRetry() {
  componentError.value = null
  fetchTimeline()
  verifyChain()
}

onMounted(() => {
  fetchTimeline()
  verifyChain()
})

// P0: KeepAlive cleanup
onDeactivated(() => {
  // Reset rollback confirmation state
  rollbackConfirmed.value = false
  isRollingBack.value = false
})

onActivated(() => {
  // Refresh timeline and chain status
  fetchTimeline()
  verifyChain()
})
</script>
