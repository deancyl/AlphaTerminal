<template>
  <footer
    class="h-8 flex items-center justify-between px-4 border-t border-theme-secondary/50 bg-terminal-panel/80 text-xs text-terminal-dim shrink-0 select-none backdrop-blur-sm"
  >
    <!-- 左侧：数据连接状态 -->
    <div class="flex items-center gap-3">
      <div class="flex items-center gap-1.5">
        <span
          class="w-1.5 h-1.5 rounded-full"
          :class="connectionStatus === 'connected' ? 'bg-bullish' : connectionStatus === 'degraded' ? 'bg-[var(--color-warning)]' : 'bg-bearish'"
        />
        <span>{{ connectionText }}</span>
        <!-- Reconnect button when disconnected -->
        <button
          v-if="connectionStatus === 'disconnected' && showReconnect"
          class="ml-1 px-1.5 py-0.5 rounded text-terminal-accent hover:bg-terminal-accent/20 transition"
          @click="handleReconnect"
        >
          重连
        </button>
      </div>
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

const props = defineProps({
  connectionStatus: {
    type: String,
    default: 'connected',
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
})

const emit = defineEmits(['reconnect'])

const now = ref(new Date())
let timer = null

const connectionText = computed(() => {
  switch (props.connectionStatus) {
    case 'connected': return '已连接'
    case 'degraded': return '降级模式'
    case 'disconnected': return '未连接'
    default: return '未知'
  }
})

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

onMounted(() => {
  timer = setInterval(() => { now.value = new Date() }, 1000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>
