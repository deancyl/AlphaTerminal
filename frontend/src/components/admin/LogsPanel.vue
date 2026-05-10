<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-lg font-bold text-theme-primary">📝 日志查看</h2>
        <p class="text-xs text-theme-muted">查看系统运行日志和错误信息</p>
      </div>
      <div class="flex gap-2">
        <select v-model="localLogLevel" class="px-3 py-2 bg-terminal-panel border border-theme rounded-sm text-sm">
          <option value="ALL">全部级别</option>
          <option value="ERROR">ERROR</option>
          <option value="WARNING">WARNING</option>
          <option value="INFO">INFO</option>
          <option value="DEBUG">DEBUG</option>
        </select>
        <button class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-sm text-sm" @click="$emit('refresh')">🔄 刷新</button>
      </div>
    </div>

    <div class="p-4 bg-[var(--info-bg)] border border-[var(--color-info-border)] rounded-sm">
      <h3 class="text-sm font-bold text-[var(--color-info)] mb-2">💡 这个功能是做什么的？</h3>
      <p class="text-xs text-theme-secondary leading-relaxed">
        显示系统的<strong class="text-terminal-accent">运行日志</strong>，包括数据更新记录、错误信息等。当系统异常时，可通过日志排查问题。
      </p>
    </div>

    <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme h-96 overflow-auto font-mono text-xs" ref="logContainer">
      <div v-if="logs.length === 0" class="text-theme-muted text-center py-8">
        <div class="text-2xl mb-2">📭</div>
        <div>暂无日志数据</div>
        <div class="mt-2 text-[10px]">点击刷新按钮加载日志</div>
      </div>
      <div v-else class="space-y-1">
        <div v-for="(log, i) in filteredLogs" :key="i" class="break-all">
          <span class="text-theme-muted">{{ formatTime(log.timestamp) }}</span>
          <span class="px-1.5 py-0.5 rounded-sm text-[10px] ml-2" :class="getLogLevelClass(log.level)">{{ log.level }}</span>
          <span class="text-theme-secondary ml-2">{{ log.message }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  logs: { type: Array, default: () => [] },
  logLevel: { type: String, default: 'ALL' },
  wsConnected: { type: Boolean, default: false }
})

const emit = defineEmits(['refresh', 'update:logLevel'])

const localLogLevel = ref(props.logLevel)
const logContainer = ref(null)

// Sync local log level with parent
watch(localLogLevel, (val) => {
  emit('update:logLevel', val)
})

// Filter logs by level
const filteredLogs = computed(() => {
  if (localLogLevel.value === 'ALL') return props.logs
  return props.logs.filter(l => l.level === localLogLevel.value)
})

function formatTime(isoTime) {
  if (!isoTime) return null
  const date = new Date(isoTime)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function getLogLevelClass(level) {
  const classes = {
    'ERROR': 'bg-[var(--color-danger-bg)] text-[var(--color-danger)]',
    'WARNING': 'bg-[var(--color-warning-bg)] text-[var(--color-warning)]',
    'INFO': 'bg-[var(--color-info-bg)] text-[var(--color-info)]',
    'DEBUG': 'bg-[var(--color-neutral-bg)] text-[var(--text-secondary)]'
  }
  return classes[level] || classes['INFO']
}

// Auto-scroll to bottom when new logs arrive
watch(() => props.logs.length, () => {
  setTimeout(() => {
    if (logContainer.value) {
      logContainer.value.scrollTop = logContainer.value.scrollHeight
    }
  }, 50)
})
</script>
