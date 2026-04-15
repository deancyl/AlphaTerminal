<template>
  <div class="flex h-full">
    <!-- 左侧导航 -->
    <aside class="w-56 border-r border-theme bg-theme-panel flex-shrink-0">
      <div class="p-4 border-b border-theme">
        <span class="text-sm font-bold text-terminal-accent">⚙️ 系统控制</span>
        <div class="text-[10px] text-theme-muted mt-1">v{{ version }}</div>
      </div>
      <nav class="py-2">
        <button
          v-for="item in navItems"
          :key="item.id"
          class="w-full flex items-center gap-3 px-4 py-3 text-sm transition-all"
          :class="activeTab === item.id
            ? 'bg-terminal-accent/15 text-terminal-accent border-r-2 border-terminal-accent'
            : 'text-theme-secondary hover:bg-theme-hover hover:text-theme-primary'"
          @click="activeTab = item.id"
        >
          <span class="text-base">{{ item.icon }}</span>
          <div class="flex-1 text-left">
            <div>{{ item.label }}</div>
            <div class="text-[10px] text-theme-muted">{{ item.desc }}</div>
          </div>
          <span v-if="item.status" class="w-2 h-2 rounded-full" :class="item.statusClass"></span>
        </button>
      </nav>
    </aside>

    <!-- 右侧内容 -->
    <main class="flex-1 overflow-auto p-6">
      
      <!-- ═══ 数据源控制 ══════════════════════════════════════════ -->
      <div v-if="activeTab === 'sources'" class="space-y-6">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-lg font-bold text-theme-primary">📡 数据源控制</h2>
            <p class="text-xs text-theme-muted mt-1">熔断控制、负载均衡、健康检查</p>
          </div>
          <button
            class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-lg text-sm hover:bg-terminal-accent/25"
            @click="refreshSourceStatus"
          >
            🔄 刷新状态
          </button>
        </div>

        <!-- 数据源健康状态 -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div
            v-for="(source, key) in sourceStatus.sources"
            :key="key"
            class="p-4 rounded-lg border"
            :class="source.health === 'healthy' ? 'bg-green-500/5 border-green-500/30' : 'bg-red-500/5 border-red-500/30'"
          >
            <div class="flex items-center justify-between mb-3">
              <div class="flex items-center gap-2">
                <span class="w-3 h-3 rounded-full" :class="source.state === 'closed' ? 'bg-green-400' : source.state === 'half_open' ? 'bg-yellow-400' : 'bg-red-400'"></span>
                <span class="font-medium text-theme-primary">{{ key }}</span>
              </div>
              <span class="text-[10px] px-2 py-0.5 rounded" :class="source.health === 'healthy' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'">
                {{ source.health === 'healthy' ? '健康' : '异常' }}
              </span>
            </div>
            
            <div class="space-y-2 text-sm">
              <div class="flex justify-between">
                <span class="text-theme-muted">延迟</span>
                <span :class="source.latency_ms < 100 ? 'text-green-400' : source.latency_ms < 300 ? 'text-yellow-400' : 'text-red-400'">
                  {{ source.latency_ms }}ms
                </span>
              </div>
              <div class="flex justify-between">
                <span class="text-theme-muted">失败次数</span>
                <span :class="source.fail_count === 0 ? 'text-green-400' : 'text-red-400'">{{ source.fail_count }}</span>
              </div>
            </div>

            <!-- 熔断控制按钮 -->
            <div class="flex gap-2 mt-4 pt-3 border-t border-theme/50">
              <button
                v-if="source.state !== 'open'"
                class="flex-1 px-3 py-1.5 bg-red-500/20 text-red-400 rounded text-xs hover:bg-red-500/30"
                @click="controlCircuit(key, 'open')"
              >
                熔断
              </button>
              <button
                v-if="source.state === 'open'"
                class="flex-1 px-3 py-1.5 bg-green-500/20 text-green-400 rounded text-xs hover:bg-green-500/30"
                @click="controlCircuit(key, 'close')"
              >
                恢复
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- ═══ 调度器控制 ══════════════════════════════════════════ -->
      <div v-else-if="activeTab === 'scheduler'" class="space-y-6">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-lg font-bold text-theme-primary">⏱️ 调度器控制</h2>
            <p class="text-xs text-theme-muted mt-1">定时任务管理、手动触发</p>
          </div>
          <button
            class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-lg text-sm hover:bg-terminal-accent/25"
            @click="refreshScheduler"
          >
            🔄 刷新
          </button>
        </div>

        <!-- 任务列表 -->
        <div class="space-y-3">
          <div
            v-for="job in schedulerJobs"
            :key="job.id"
            class="p-4 bg-theme-secondary/20 rounded-lg border border-theme"
          >
            <div class="flex items-center justify-between mb-3">
              <div class="flex items-center gap-3">
                <span class="w-2 h-2 rounded-full" :class="job.state === 'running' ? 'bg-green-400 animate-pulse' : 'bg-yellow-400'"></span>
                <span class="font-medium text-theme-primary">{{ job.name }}</span>
              </div>
              <div class="flex gap-2">
                <button
                  v-if="job.state === 'running'"
                  class="px-3 py-1.5 bg-yellow-500/20 text-yellow-400 rounded text-xs hover:bg-yellow-500/30"
                  @click="controlJob(job.id, 'pause')"
                >
                  暂停
                </button>
                <button
                  v-else
                  class="px-3 py-1.5 bg-green-500/20 text-green-400 rounded text-xs hover:bg-green-500/30"
                  @click="controlJob(job.id, 'resume')"
                >
                  恢复
                </button>
                <button
                  class="px-3 py-1.5 bg-blue-500/20 text-blue-400 rounded text-xs hover:bg-blue-500/30"
                  @click="controlJob(job.id, 'trigger_now')"
                >
                  立即执行
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ═══ 缓存管理 ══════════════════════════════════════════ -->
      <div v-else-if="activeTab === 'cache'" class="space-y-6">
        <h2 class="text-lg font-bold text-theme-primary">💾 缓存管理</h2>
        <div class="p-4 bg-theme-secondary/20 rounded-lg border border-theme">
          <div class="flex gap-2">
            <button
              class="px-4 py-2 bg-red-500/20 text-red-400 rounded text-sm hover:bg-red-500/30"
              @click="invalidateCache('memory')"
            >
              清空内存缓存
            </button>
            <button
              class="px-4 py-2 bg-blue-500/20 text-blue-400 rounded text-sm hover:bg-blue-500/30"
              @click="warmupCache('sectors')"
            >
              预热板块缓存
            </button>
          </div>
        </div>
      </div>

      <!-- ═══ 数据库管理 ══════════════════════════════════════════ -->
      <div v-else-if="activeTab === 'database'" class="space-y-6">
        <h2 class="text-lg font-bold text-theme-primary">🗄️ 数据库管理</h2>
        <div class="p-4 bg-theme-secondary/20 rounded-lg border border-theme">
          <div class="flex gap-2">
            <button
              class="px-4 py-2 bg-terminal-accent/20 text-terminal-accent rounded text-sm hover:bg-terminal-accent/30"
              @click="dbMaintenance('vacuum')"
            >
              VACUUM 优化
            </button>
            <button
              class="px-4 py-2 bg-blue-500/20 text-blue-400 rounded text-sm hover:bg-blue-500/30"
              @click="dbMaintenance('analyze')"
            >
              ANALYZE 分析
            </button>
          </div>
        </div>
      </div>

      <!-- ═══ 系统监控 ══════════════════════════════════════════ -->
      <div v-else-if="activeTab === 'monitor'" class="space-y-6">
        <div class="flex items-center justify-between">
          <h2 class="text-lg font-bold text-theme-primary">📊 系统监控</h2>
          <button
            class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-lg text-sm hover:bg-terminal-accent/25"
            @click="refreshSystemMetrics"
          >
            🔄 刷新
          </button>
        </div>

        <!-- 核心指标 -->
        <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div class="p-4 bg-theme-secondary/20 rounded-lg border border-theme">
            <div class="text-[10px] text-theme-muted mb-1">CPU 使用率</div>
            <div class="text-2xl font-bold text-terminal-accent">{{ systemMetrics.cpu_percent?.toFixed(1) || 0 }}%</div>
          </div>
          <div class="p-4 bg-theme-secondary/20 rounded-lg border border-theme">
            <div class="text-[10px] text-theme-muted mb-1">内存使用</div>
            <div class="text-2xl font-bold text-terminal-accent">{{ systemMetrics.memory?.percent?.toFixed(1) || 0 }}%</div>
          </div>
          <div class="p-4 bg-theme-secondary/20 rounded-lg border border-theme">
            <div class="text-[10px] text-theme-muted mb-1">磁盘使用</div>
            <div class="text-2xl font-bold text-terminal-accent">{{ systemMetrics.disk?.percent?.toFixed(1) || 0 }}%</div>
          </div>
          <div class="p-4 bg-theme-secondary/20 rounded-lg border border-theme">
            <div class="text-[10px] text-theme-muted mb-1">进程内存</div>
            <div class="text-2xl font-bold text-terminal-accent">{{ systemMetrics.process?.memory_mb || 0 }} MB</div>
          </div>
        </div>
      </div>

      <!-- ═══ 日志管理 ══════════════════════════════════════════ -->
      <div v-else-if="activeTab === 'logs'" class="space-y-6">
        <h2 class="text-lg font-bold text-theme-primary">📝 日志管理</h2>
        <div class="p-4 bg-theme-secondary/20 rounded-lg border border-theme h-96 overflow-auto font-mono text-xs">
          <div class="text-theme-muted text-center py-8">
            实时日志流功能开发中...
          </div>
        </div>
      </div>

    </main>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { apiFetch } from '../utils/api.js'

const version = '0.4.137'
const activeTab = ref('sources')

const navItems = [
  { id: 'sources', label: '数据源', desc: '熔断控制、负载均衡', icon: '📡', status: true, statusClass: 'bg-green-400' },
  { id: 'scheduler', label: '调度器', desc: '定时任务管理', icon: '⏱️', status: true, statusClass: 'bg-green-400' },
  { id: 'cache', label: '缓存', desc: '内存/数据库缓存', icon: '💾', status: true, statusClass: 'bg-green-400' },
  { id: 'database', label: '数据库', desc: 'SQLite维护优化', icon: '🗄️', status: true, statusClass: 'bg-green-400' },
  { id: 'monitor', label: '监控', desc: 'CPU/内存/网络', icon: '📊', status: true, statusClass: 'bg-green-400' },
  { id: 'logs', label: '日志', desc: '实时日志流', icon: '📝', status: false, statusClass: 'bg-gray-400' },
]

// 数据源控制
const sourceStatus = reactive({
  sources: {
    tencent: { state: 'closed', fail_count: 0, last_success: '09:15:32', latency_ms: 85, health: 'healthy' },
    sina: { state: 'closed', fail_count: 1, last_success: '09:15:28', latency_ms: 120, health: 'healthy' },
    eastmoney: { state: 'open', fail_count: 5, last_failure: '09:14:18', health: 'unhealthy' }
  }
})

const schedulerJobs = ref([
  { id: 'data_fetch', name: '行情数据拉取', trigger: 'interval (30s)', state: 'running' },
  { id: 'sectors_update', name: '板块数据更新', trigger: 'interval (300s)', state: 'running' },
  { id: 'news_refresh', name: '新闻快讯刷新', trigger: 'interval (600s)', state: 'running' }
])

const systemMetrics = reactive({
  cpu_percent: 35.2,
  memory: { percent: 55.1 },
  disk: { percent: 42.3 },
  process: { memory_mb: 167 }
})

async function refreshSourceStatus() {
  try {
    const data = await apiFetch('/api/v1/admin/sources/status')
    if (data) Object.assign(sourceStatus, data)
  } catch (e) {
    console.error('刷新失败:', e)
  }
}

async function controlCircuit(source, action) {
  try {
    await apiFetch('/api/v1/admin/sources/circuit_breaker', {
      method: 'POST',
      body: JSON.stringify({ source, action })
    })
    await refreshSourceStatus()
  } catch (e) {
    alert('操作失败: ' + e.message)
  }
}

async function refreshScheduler() {
  try {
    const data = await apiFetch('/api/v1/admin/scheduler/jobs')
    if (data?.jobs) schedulerJobs.value = data.jobs
  } catch (e) {
    console.error('刷新失败:', e)
  }
}

async function controlJob(jobId, action) {
  try {
    await apiFetch(`/api/v1/admin/scheduler/jobs/${jobId}/control`, {
      method: 'POST',
      body: JSON.stringify({ action })
    })
    await refreshScheduler()
  } catch (e) {
    alert('操作失败: ' + e.message)
  }
}

async function invalidateCache(type) {
  try {
    await apiFetch('/api/v1/admin/cache/invalidate', {
      method: 'POST',
      body: JSON.stringify({ cache_type: type })
    })
    alert('缓存已清空')
  } catch (e) {
    alert('操作失败: ' + e.message)
  }
}

async function warmupCache(type) {
  try {
    await apiFetch('/api/v1/admin/cache/warmup', {
      method: 'POST',
      body: JSON.stringify({ data_type: type })
    })
    alert('缓存预热已启动')
  } catch (e) {
    alert('操作失败: ' + e.message)
  }
}

async function dbMaintenance(action) {
  try {
    await apiFetch('/api/v1/admin/database/maintenance', {
      method: 'POST',
      body: JSON.stringify({ action })
    })
    alert('维护操作已执行')
  } catch (e) {
    alert('操作失败: ' + e.message)
  }
}

async function refreshSystemMetrics() {
  try {
    const data = await apiFetch('/api/v1/admin/system/metrics')
    if (data) Object.assign(systemMetrics, data)
  } catch (e) {
    console.error('刷新失败:', e)
  }
}

onMounted(() => {
  refreshSourceStatus()
  refreshScheduler()
  refreshSystemMetrics()
})
</script>
