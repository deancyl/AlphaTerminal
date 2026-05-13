<template>
  <footer
    class="h-8 flex items-center justify-between px-4 border-t border-theme-secondary/50 bg-terminal-panel/80 text-xs text-terminal-dim shrink-0 select-none backdrop-blur-sm"
  >
    <!-- 左侧：数据连接状态 -->
    <div class="flex items-center gap-3">
      <ConnectionStatus
        :status="connectionStatus"
        :latency="latency"
        :retry-countdown="retryCountdown"
        @retry="handleReconnect"
      />
      <span class="text-theme-secondary">|</span>
      <span>数据更新: {{ lastUpdateTime }}</span>
      <!-- Connection stats tooltip -->
      <span
        v-if="connectionStats"
        class="text-terminal-dim/60 hidden lg:inline"
        :title="connectionStatsTitle"
      >
        ({{ connectionStats }})
      </span>
    </div>

    <!-- 右侧：市场状态 + 快捷键提示 -->
    <div class="flex items-center gap-3">
      <span
        class="px-1.5 py-0.5 rounded-sm border"
        :class="marketStatusClass"
      >
        {{ marketStatusText }}
      </span>
      <span class="text-theme-secondary hidden sm:inline">Ctrl+K 命令面板</span>
      <span class="text-theme-secondary hidden md:inline">F1 帮助</span>
    </div>
  </footer>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import ConnectionStatus from './ConnectionStatus.vue'
import { usePollingManager } from '../composables/usePollingManager.js'

const props = defineProps({
  connectionStatus: {
    type: String,
    default: 'idle',
  },
  lastUpdate: {
    type: String,
    default: '',
  },
  marketStatus: {
    type: String,
    default: 'closed',
  },
  showReconnect: {
    type: Boolean,
    default: false,
  },
  lastConnectedAt: {
    type: Number,
    default: null,
  },
  connectionAttempts: {
    type: Number,
    default: 0,
  },
  latency: {
    type: Number,
    default: null,
  },
  retryCountdown: {
    type: Number,
    default: null,
  },
})

const emit = defineEmits(['reconnect'])

const now = ref(new Date())
let unregisterPolling = null

const { register } = usePollingManager()

const lastUpdateTime = computed(() => {
  if (props.lastUpdate) return props.lastUpdate
  const d = now.value
  return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}:${String(d.getSeconds()).padStart(2,'0')}`
})

const marketStatusText = computed(() => {
  switch (props.marketStatus) {
    case 'open': return '交易中'
    case 'pre': return '盘前'
    case 'post': return '盘后'
    case 'closed': return '已收盘'
    default: return '未知'
  }
})

const marketStatusClass = computed(() => {
  switch (props.marketStatus) {
    case 'open':
    case 'pre':
    case 'post':
      return 'border-bullish/30 bg-bullish/10 text-bullish'
    default:
      return 'border-theme-secondary/30 bg-terminal-panel text-terminal-dim'
  }
})

const connectionStats = computed(() => {
  if (props.connectionStatus === 'connected' && props.lastConnectedAt) {
    const seconds = Math.floor((Date.now() - props.lastConnectedAt) / 1000)
    if (seconds < 60) return `${seconds}秒`
    const minutes = Math.floor(seconds / 60)
    if (minutes < 60) return `${minutes}分钟`
    const hours = Math.floor(minutes / 60)
    return `${hours}小时`
  }
  if (props.connectionAttempts > 0 && props.connectionStatus === 'disconnected') {
    return `重试${props.connectionAttempts}次`
  }
  return null
})

const connectionStatsTitle = computed(() => {
  if (props.lastConnectedAt) {
    const d = new Date(props.lastConnectedAt)
    return `上次连接: ${d.toLocaleTimeString()}`
  }
  return ''
})

function handleReconnect() {
  emit('reconnect')
}

function updateClock() {
  now.value = new Date()
}

onMounted(() => {
  unregisterPolling = register(
    'status-bar-clock',
    updateClock,
    'low',
    { interval: 1000 }
  )
})

onUnmounted(() => {
  if (unregisterPolling) {
    unregisterPolling()
    unregisterPolling = null
  }
})
</script>
