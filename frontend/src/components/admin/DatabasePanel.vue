<template>
  <div class="space-y-6">
    <h2 class="text-lg font-bold text-theme-primary">🗄️ 数据库管理</h2>
    <p class="text-xs text-theme-muted">SQLite数据库维护和优化</p>

    <div class="p-4 bg-[var(--info-bg)] border border-[var(--color-info-border)] rounded-sm">
      <h3 class="text-sm font-bold text-[var(--color-info)] mb-2">💡 这个功能是做什么的？</h3>
      <p class="text-xs text-theme-secondary leading-relaxed">
        系统使用<strong class="text-terminal-accent">SQLite数据库</strong>存储股票历史数据、投资组合等。长期使用后通过维护操作可以优化性能。
      </p>
    </div>

    <!-- 错误状态：数据加载失败 -->
    <div v-if="!hasData && !isLoading" class="p-4 bg-red-500/10 border border-red-500/30 rounded-sm">
      <p class="text-sm text-red-400 mb-3">⚠️ 数据加载失败</p>
      <button 
        class="px-4 py-2 bg-red-500/20 text-red-400 rounded-sm text-sm hover:bg-red-500/30 transition-colors"
        @click="$emit('refresh')"
      >
        重新加载
      </button>
    </div>

    <!-- 数据统计卡片 -->
    <div v-else class="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
        <div class="text-[10px] text-theme-muted mb-1">数据库大小</div>
        <div class="text-xl font-bold text-terminal-accent">{{ status.size || 0 }} MB</div>
      </div>
      <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
        <div class="text-[10px] text-theme-muted mb-1">实时数据表</div>
        <div class="text-xl font-bold text-terminal-accent">{{ status.realtime || 0 }}</div>
        <div class="text-[10px] text-theme-muted">行</div>
      </div>
      <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
        <div class="text-[10px] text-theme-muted mb-1">日K数据表</div>
        <div class="text-xl font-bold text-terminal-accent">{{ status.daily || 0 }}</div>
        <div class="text-[10px] text-theme-muted">行</div>
      </div>
      <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
        <div class="text-[10px] text-theme-muted mb-1">股票列表</div>
        <div class="text-xl font-bold text-terminal-accent">{{ status.stocks || 0 }}</div>
        <div class="text-[10px] text-theme-muted">只</div>
      </div>
    </div>

    <div v-if="vacuumTask" class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
      <h3 class="text-sm font-bold text-theme-primary mb-3">🔄 VACUUM 进度</h3>
      <div class="space-y-2">
        <div class="flex items-center justify-between text-xs">
          <span class="text-theme-secondary">{{ vacuumTask.message }}</span>
          <span class="text-terminal-accent font-bold">{{ vacuumTask.progress }}%</span>
        </div>
        <div class="w-full bg-theme-secondary/30 rounded-full h-2">
          <div 
            class="h-2 rounded-full transition-all duration-300"
            :class="{
              'bg-terminal-accent': vacuumTask.status === 'running',
              'bg-green-500': vacuumTask.status === 'completed',
              'bg-red-500': vacuumTask.status === 'failed'
            }"
            :style="{ width: vacuumTask.progress + '%' }"
          ></div>
        </div>
        <div v-if="vacuumTask.status === 'completed'" class="text-xs text-green-500">
          ✓ VACUUM 完成
        </div>
        <div v-if="vacuumTask.status === 'failed'" class="text-xs text-red-500">
          ✗ {{ vacuumTask.error }}
        </div>
      </div>
    </div>

    <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
      <h3 class="text-sm font-bold text-theme-primary mb-4">数据库维护</h3>
      <div class="flex flex-wrap gap-3">
        <button 
          class="px-4 py-2 bg-terminal-accent/20 text-terminal-accent rounded-sm text-sm disabled:opacity-50 disabled:cursor-not-allowed" 
          :disabled="vacuumTask?.status === 'running'"
          @click="$emit('confirm-action', 'VACUUM 优化', '重组数据库文件，释放空间，优化性能。可能需要几秒到几分钟。确定？', () => $emit('maintenance', 'vacuum'))"
        >🔧 VACUUM 优化</button>
        <button class="px-4 py-2 bg-[var(--color-info-bg)] text-[var(--color-info)] rounded-sm text-sm" @click="$emit('confirm-action', 'ANALYZE 分析', '分析表结构，更新查询优化器统计信息。操作快速安全。确定？', () => $emit('maintenance', 'analyze'))">📊 ANALYZE 分析</button>
        <button class="px-4 py-2 bg-[var(--color-success-bg)] text-[var(--color-success)] rounded-sm text-sm" @click="$emit('confirm-action', 'WAL 检查点', '把内存日志写入磁盘，确保数据持久化。安全快速。确定？', () => $emit('maintenance', 'wal_checkpoint'))">💾 WAL检查点</button>
      </div>
    </div>

    <div class="p-3 bg-[var(--color-warning-bg)] border border-[var(--color-warning-border)] rounded-sm text-xs text-theme-muted">
      <strong class="text-[var(--color-warning)]">维护操作说明：</strong>
      <ul class="mt-1 space-y-1 list-disc list-inside">
        <li><strong>VACUUM</strong>：清理数据库碎片，释放空间。建议在系统空闲时执行</li>
        <li><strong>ANALYZE</strong>：更新查询统计信息。建议每周执行一次</li>
        <li><strong>WAL检查点</strong>：确保内存数据写入磁盘。可安全随时执行</li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { apiFetch } from '@/utils/api.js'

const props = defineProps({
  status: { type: Object, default: () => ({}) }
})

const emit = defineEmits(['confirm-action', 'maintenance', 'refresh'])

// 计算是否有数据（非零值表示已加载）
const hasData = computed(() => {
  return props.status.size > 0 || props.status.realtime > 0 || props.status.daily > 0 || props.status.stocks > 0
})

// 加载状态（由父组件控制）
const isLoading = ref(false)

const vacuumTask = ref(null)
let pollInterval = null

async function pollTaskStatus(taskId) {
  try {
    const res = await apiFetch(`/api/v1/admin/database/maintenance/${taskId}`, { timeoutMs: 5000 })
    if (res.code === 0) {
      vacuumTask.value = res.data
      if (res.data.status !== 'running') {
        stopPolling()
      }
    }
  } catch (e) {
    console.error('Failed to poll task status:', e)
  }
}

function startPolling(taskId) {
  stopPolling()
  pollInterval = setInterval(() => pollTaskStatus(taskId), 1000)
  pollTaskStatus(taskId)
}

function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval)
    pollInterval = null
  }
}

onMounted(() => {
  const savedTaskId = localStorage.getItem('vacuum_task_id')
  if (savedTaskId) {
    pollTaskStatus(savedTaskId).then(() => {
      if (vacuumTask.value?.status === 'running') {
        startPolling(savedTaskId)
      }
    })
  }
})

onUnmounted(() => {
  stopPolling()
})

watch(() => vacuumTask.value, (task) => {
  if (task?.task_id) {
    if (task.status === 'running') {
      localStorage.setItem('vacuum_task_id', task.task_id)
    } else if (task.status === 'completed' || task.status === 'failed') {
      setTimeout(() => {
        localStorage.removeItem('vacuum_task_id')
      }, 5000)
    }
  }
})
</script>
