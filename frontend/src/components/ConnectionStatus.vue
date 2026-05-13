<template>
  <div class="connection-status flex items-center gap-1.5" :class="statusClass">
    <!-- Status indicator -->
    <div class="status-indicator">
      <!-- Idle: Gray dot -->
      <span
        v-if="status === 'idle'"
        class="w-2 h-2 rounded-full bg-[var(--text-muted)]"
      />

      <!-- Connecting: Yellow spinner -->
      <svg
        v-else-if="status === 'connecting'"
        class="w-3.5 h-3.5 animate-spin text-[var(--color-warning)]"
        viewBox="0 0 24 24"
        fill="none"
      >
        <circle
          class="opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          stroke-width="4"
        />
        <path
          class="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
        />
      </svg>

      <!-- Connected: Green pulsing dot -->
      <span
        v-else-if="status === 'connected'"
        class="relative flex h-2 w-2"
      >
        <span class="pulse-ring"></span>
        <span class="pulse-dot"></span>
      </span>

      <!-- Disconnected: Orange dot -->
      <span
        v-else-if="status === 'disconnected'"
        class="w-2 h-2 rounded-full bg-[var(--color-warning)]"
      />

      <!-- Failed: Red X icon -->
      <svg
        v-else-if="status === 'failed'"
        class="w-3 h-3 text-[var(--color-danger)]"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2.5"
      >
        <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
      </svg>
    </div>

    <!-- Status text -->
    <span class="status-text text-xs">
      {{ statusText }}
    </span>

    <!-- Latency display (connected state) -->
    <span
      v-if="status === 'connected' && latency !== null"
      class="latency text-[10px] text-[var(--text-tertiary)]"
    >
      {{ latency }}ms
    </span>

    <!-- Retry countdown (disconnected state) -->
    <span
      v-if="status === 'disconnected' && retryCountdown !== null"
      class="retry-countdown text-[10px] text-[var(--text-tertiary)]"
    >
      {{ retryCountdown }}s
    </span>

    <!-- Manual retry button (failed state) -->
    <button
      v-if="status === 'failed'"
      class="retry-btn px-1.5 py-0.5 rounded text-[10px] text-[var(--color-primary)] hover:bg-[var(--color-primary-bg)] transition-colors"
      @click="handleRetry"
    >
      重试
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: {
    type: String,
    default: 'idle',
    validator: (v) => ['idle', 'connecting', 'connected', 'disconnected', 'failed'].includes(v)
  },
  latency: {
    type: Number,
    default: null
  },
  retryCountdown: {
    type: Number,
    default: null
  }
})

const emit = defineEmits(['retry'])

const statusText = computed(() => {
  switch (props.status) {
    case 'idle': return '未连接'
    case 'connecting': return '连接中...'
    case 'connected': return '实时'
    case 'disconnected': return '已断开'
    case 'failed': return '连接失败'
    default: return '未知'
  }
})

const statusClass = computed(() => {
  switch (props.status) {
    case 'connected': return 'status-connected'
    case 'disconnected': return 'status-disconnected'
    case 'failed': return 'status-failed'
    default: return ''
  }
})

function handleRetry() {
  emit('retry')
}
</script>

<style scoped>
.connection-status {
  font-family: var(--font-sans, 'PingFang SC', 'Microsoft YaHei', sans-serif);
  user-select: none;
}

.status-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Pulse animation for connected state */
.pulse-ring {
  position: absolute;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background-color: var(--color-success);
  opacity: 0.75;
  animation: pulse-ring 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

.pulse-dot {
  position: relative;
  display: inline-flex;
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 50%;
  background-color: var(--color-success);
}

@keyframes pulse-ring {
  0%, 100% {
    transform: scale(1);
    opacity: 0.75;
  }
  50% {
    transform: scale(1.5);
    opacity: 0;
  }
}

/* Spin animation for connecting state */
@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.animate-spin {
  animation: spin 1s linear infinite;
}

/* Status-specific styling */
.status-connected .status-text {
  color: var(--color-success);
}

.status-disconnected .status-text {
  color: var(--color-warning);
}

.status-failed .status-text {
  color: var(--color-danger);
}

.retry-btn {
  border: 1px solid var(--color-primary-border);
  background-color: var(--color-primary-bg);
  cursor: pointer;
}

.retry-btn:hover {
  background-color: rgba(15, 82, 186, 0.2);
}

/* Reduced motion support */
@media (prefers-reduced-motion: reduce) {
  .pulse-ring {
    animation: none;
    opacity: 0;
  }
  
  .animate-spin {
    animation: none;
  }
}
</style>
