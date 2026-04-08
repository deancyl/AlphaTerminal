<template>
  <div class="performance-panel" :class="{ collapsed: collapsed }">
    <!-- 标题栏 -->
    <div class="panel-header" @click="collapsed = !collapsed">
      <span class="title">📊 性能监控</span>
      <span class="fps-badge" :class="fpsLevel">
        {{ fps }} FPS
      </span>
      <span v-if="warnings.length > 0" class="warning-badge" @click.stop="showWarnings = !showWarnings">
        ⚠️ {{ warnings.length }}
      </span>
    </div>

    <!-- 警告详情 -->
    <div v-if="showWarnings && warnings.length > 0" class="warnings-panel">
      <div v-for="(warn, i) in warnings" :key="i" class="warning-item">
        {{ warn }}
      </div>
    </div>

    <!-- 详细信息 -->
    <div v-if="!collapsed" class="panel-content">
      <!-- 内存 -->
      <div v-if="memory" class="metric-row">
        <span class="metric-label">内存</span>
        <span class="metric-value" :class="memoryLevel">
          {{ memory.usagePercent }}%
          <span class="metric-detail">({{ formatBytes(memory.usedJSHeapSize) }})</span>
        </span>
      </div>

      <!-- API 性能 -->
      <div v-if="slowApis.length > 0" class="api-section">
        <div class="section-title">慢 API (>1s)</div>
        <div v-for="(api, i) in slowApis" :key="i" class="api-row">
          <span class="api-name">{{ api.name }}</span>
          <span class="api-duration" :class="apiLevel(api.duration)">{{ (api.duration / 1000).toFixed(1) }}s</span>
        </div>
      </div>

      <!-- 错误计数 -->
      <div v-if="errorCount > 0" class="metric-row error">
        <span class="metric-label">错误</span>
        <span class="metric-value">{{ errorCount }}</span>
      </div>

      <!-- 刷新时间 -->
      <div class="update-time">
        更新: {{ updateTimeStr }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { usePerformanceMonitor } from '../composables/usePerformanceMonitor.js'

const { stats, formatBytes, getPerformanceLevel, getWarnings } = usePerformanceMonitor()

const collapsed = ref(true)
const showWarnings = ref(false)

const fps = computed(() => stats.value.fps || 0)
const memory = computed(() => stats.value.memory)
const errorCount = computed(() => stats.value.errorCount || 0)
const updateTime = computed(() => stats.value.lastUpdate)

const fpsLevel = computed(() => {
  const f = fps.value
  if (f >= 55) return 'excellent'
  if (f >= 45) return 'good'
  if (f >= 30) return 'fair'
  return 'poor'
})

const memoryLevel = computed(() => {
  const m = memory.value
  if (!m) return ''
  if (m.usagePercent >= 90) return 'danger'
  if (m.usagePercent >= 80) return 'warning'
  return 'normal'
})

const slowApis = computed(() => {
  const measures = stats.value.apiMeasures || {}
  return Object.entries(measures)
    .filter(([_, m]) => m.duration > 1000)
    .map(([name, m]) => ({ name, duration: m.duration }))
    .sort((a, b) => b.duration - a.duration)
    .slice(0, 5)
})

const warnings = computed(() => {
  const w = getWarnings()
  return w
})

const updateTimeStr = computed(() => {
  return new Date(updateTime.value).toLocaleTimeString('zh-CN', { hour12: false })
})

function apiLevel(duration) {
  if (duration > 5000) return 'danger'
  if (duration > 2000) return 'warning'
  return 'normal'
}
</script>

<style scoped>
.performance-panel {
  position: fixed;
  bottom: 16px;
  right: 16px;
  z-index: 9000;
  background: rgba(17, 24, 39, 0.95);
  border: 1px solid rgba(75, 85, 99, 0.5);
  border-radius: 8px;
  min-width: 200px;
  max-width: 280px;
  backdrop-filter: blur(8px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
  font-size: 11px;
}

.performance-panel.collapsed {
  min-width: auto;
}

.panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  user-select: none;
}

.panel-header:hover {
  background: rgba(75, 85, 99, 0.2);
}

.title {
  flex: 1;
  font-weight: 600;
  color: #e5e7eb;
}

.fps-badge {
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 700;
  font-family: monospace;
}

.fps-badge.excellent {
  background: rgba(34, 197, 94, 0.2);
  color: #22c55e;
}

.fps-badge.good {
  background: rgba(59, 130, 246, 0.2);
  color: #3b82f6;
}

.fps-badge.fair {
  background: rgba(251, 191, 36, 0.2);
  color: #fbbf24;
}

.fps-badge.poor {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}

.warning-badge {
  padding: 2px 6px;
  border-radius: 8px;
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
  cursor: pointer;
}

.warnings-panel {
  padding: 8px 12px;
  background: rgba(239, 68, 68, 0.1);
  border-top: 1px solid rgba(239, 68, 68, 0.2);
}

.warning-item {
  padding: 4px 0;
  color: #f87171;
  font-size: 10px;
}

.panel-content {
  padding: 8px 12px;
  border-top: 1px solid rgba(75, 85, 99, 0.3);
}

.metric-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
}

.metric-label {
  color: #9ca3af;
}

.metric-value {
  font-family: monospace;
  font-weight: 600;
}

.metric-value.danger { color: #ef4444; }
.metric-value.warning { color: #fbbf24; }
.metric-value.normal { color: #22c55e; }

.metric-detail {
  font-size: 9px;
  color: #6b7280;
  font-weight: 400;
}

.api-section {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(75, 85, 99, 0.3);
}

.section-title {
  color: #6b7280;
  font-size: 10px;
  margin-bottom: 4px;
}

.api-row {
  display: flex;
  justify-content: space-between;
  padding: 2px 0;
}

.api-name {
  color: #e5e7eb;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.api-duration {
  font-family: monospace;
}

.api-duration.danger { color: #ef4444; }
.api-duration.warning { color: #fbbf24; }
.api-duration.normal { color: #22c55e; }

.metric-row.error .metric-value {
  color: #ef4444;
}

.update-time {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(75, 85, 99, 0.3);
  color: #6b7280;
  font-size: 9px;
  text-align: right;
}
</style>
