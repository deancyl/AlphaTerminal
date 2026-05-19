<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-lg font-bold text-theme-primary">📡 数据源控制</h2>
        <p class="text-xs text-theme-muted mt-1">管理股票行情数据的来源，控制数据质量和系统稳定性</p>
      </div>
      <div class="flex gap-2">
        <button class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-sm text-sm" @click="showTopology = !showTopology">
          {{ showTopology ? '📊 隐藏拓扑' : '🔗 显示拓扑' }}
        </button>
        <button class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-sm text-sm" @click="$emit('refresh')">🔄 刷新状态</button>
      </div>
    </div>

    <!-- Source Switchboard Topology -->
    <div v-if="showTopology" class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
      <h3 class="text-sm font-bold text-theme-primary mb-3">🔗 数据源拓扑图</h3>
      <div class="relative" style="height: 200px;">
        <svg width="100%" height="100%" class="overflow-visible">
          <!-- Edges (fallback arrows) -->
          <defs>
            <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
              <polygon points="0 0, 10 3.5, 0 7" fill="#6b7280" />
            </marker>
          </defs>
          <g v-for="(edge, idx) in topologyEdges" :key="'edge-' + idx">
            <line
              :x1="getNodeX(edge.source)"
              :y1="getNodeY(edge.source)"
              :x2="getNodeX(edge.target)"
              :y2="getNodeY(edge.target)"
              stroke="#4b5563"
              stroke-width="2"
              stroke-dasharray="5,5"
              marker-end="url(#arrowhead)"
            />
            <text
              :x="(getNodeX(edge.source) + getNodeX(edge.target)) / 2"
              :y="(getNodeY(edge.source) + getNodeY(edge.target)) / 2 - 5"
              fill="#9ca3af"
              font-size="10"
              text-anchor="middle"
            >fallback</text>
          </g>
          
          <!-- Nodes -->
          <g v-for="node in topologyNodes" :key="node.id">
            <circle
              :cx="getNodeX(node.id)"
              :cy="getNodeY(node.id)"
              r="30"
              :fill="getNodeColor(node.status)"
              stroke="#374151"
              stroke-width="2"
              class="cursor-pointer hover:opacity-80 transition-opacity"
              @click="selectNode(node)"
            />
            <text
              :x="getNodeX(node.id)"
              :y="getNodeY(node.id)"
              fill="white"
              font-size="11"
              font-weight="bold"
              text-anchor="middle"
              dominant-baseline="middle"
              class="pointer-events-none"
            >{{ node.name }}</text>
            <text
              :x="getNodeX(node.id)"
              :y="getNodeY(node.id) + 45"
              fill="#9ca3af"
              font-size="10"
              text-anchor="middle"
            >{{ node.is_current ? '✓ 当前' : node.is_primary ? '⭐ 主源' : '' }}</text>
          </g>
        </svg>
      </div>
      
      <!-- Manual Fallback Switch -->
      <div v-if="selectedNode" class="mt-4 p-3 bg-terminal-panel/50 rounded-sm border border-theme">
        <div class="flex items-center justify-between">
          <div>
            <span class="text-sm font-medium text-theme-primary">{{ selectedNode.name }}</span>
            <span class="ml-2 text-xs" :class="getStatusTextClass(selectedNode.status)">
              {{ getStatusLabel(selectedNode.status) }}
            </span>
          </div>
          <div class="flex gap-2">
            <select v-model="fallbackTarget" class="bg-terminal-bg border border-theme rounded-sm px-2 py-1 text-xs text-theme-primary">
              <option value="">选择切换目标...</option>
              <option v-for="node in topologyNodes.filter(n => n.id !== selectedNode.id)" :key="node.id" :value="node.id">
                {{ node.name }}
              </option>
            </select>
            <button
              :disabled="!fallbackTarget"
              class="px-3 py-1 bg-[var(--color-warning-bg)] text-[var(--color-warning)] rounded-sm text-xs disabled:opacity-50"
              @click="confirmSwitch"
            >切换</button>
          </div>
        </div>
      </div>
      
      <!-- Legend -->
      <div class="flex gap-4 mt-3 text-xs text-theme-muted">
        <div class="flex items-center gap-1"><span class="w-3 h-3 rounded-full bg-[var(--color-success)]"></span> 健康</div>
        <div class="flex items-center gap-1"><span class="w-3 h-3 rounded-full bg-[var(--color-warning)]"></span> 未知</div>
        <div class="flex items-center gap-1"><span class="w-3 h-3 rounded-full bg-[var(--color-danger)]"></span> 异常</div>
        <div class="flex items-center gap-1 text-theme-muted">--- 虚线箭头 = 回退路径</div>
      </div>
    </div>

    <div class="p-4 bg-[var(--info-bg)] border border-[var(--color-info-border)] rounded-sm">
      <h3 class="text-sm font-bold text-[var(--color-info)] mb-2">💡 这个功能是做什么的？</h3>
      <p class="text-xs text-theme-secondary leading-relaxed">
        <strong class="text-terminal-accent">股票/基金/期货行情数据源</strong>：当获取实时行情时，后端自动选择最快的数据源。
        当前使用：<span class="text-[var(--color-warning)]">{{ probeData?.current_source || '-' }}</span>
        <br/>⭐ 主源 = 默认优先级 | ✓ 当前使用 = 实际被使用的
        <br/><strong class="text-[var(--color-warning)]">注意</strong>：此面板仅控制行情数据源，基金/宏观等模块使用独立数据源。
      </p>
    </div>

    <!-- 统一代理设置 -->
    <div class="p-4 bg-[var(--color-warning-bg)] border border-[var(--color-warning-border)] rounded-sm">
      <h3 class="text-sm font-bold text-[var(--color-warning)] mb-2">🌐 国外数据源代理设置</h3>
      <p class="text-xs text-theme-muted mb-3">AlphaVantage 等国外数据源需要代理才能访问。设置代理后重启服务生效。</p>
      <div class="flex gap-2">
        <input v-model="localProxyUrl" type="text" placeholder="如: 192.168.1.50:7897" class="flex-1 bg-terminal-bg border border-theme rounded-sm px-3 py-2 text-sm text-theme-primary" />
        <button @click="$emit('save-proxy', localProxyUrl)" class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-sm text-sm">保存并重启</button>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <div v-for="(source, key) in sourceStatus.sources" :key="key" class="p-4 rounded-sm border" :class="source.health === 'healthy' ? 'bg-[var(--color-success-bg)] border-[var(--color-success-border)]' : source.health === 'unknown' ? 'bg-[var(--color-info-bg)] border-[var(--color-info-border)]' : 'bg-[var(--color-danger-bg)] border-[var(--color-danger-border)]'">
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center gap-2">
            <span class="w-3 h-3 rounded-full" :class="source.state === 'closed' ? 'bg-[var(--color-success-light)]' : source.state === 'unknown' ? 'bg-[var(--color-info)]' : 'bg-[var(--color-danger-light)]'"></span>
            <span class="font-medium text-theme-primary">{{ key }}</span>
            <span v-if="source.is_primary" class="text-[10px] px-1.5 py-0.5 rounded-sm bg-[var(--color-warning)] text-black font-bold">⭐ 主源</span>
            <span v-if="probeData?.current_source === key" class="text-[10px] px-1.5 py-0.5 rounded-sm bg-[var(--color-success)] text-black font-bold">✓ 当前使用</span>
          </div>
          <span class="text-[10px] px-2 py-0.5 rounded-sm" :class="source.health === 'healthy' ? 'bg-[var(--color-success-bg)] text-[var(--color-success)]' : source.health === 'unknown' ? 'bg-[var(--color-info-bg)] text-[var(--color-info)]' : 'bg-[var(--color-danger-bg)] text-[var(--color-danger)]'">
            {{ source.health === 'healthy' ? '健康' : source.health === 'unknown' ? '未探测' : '异常' }}
          </span>
        </div>
        <div class="space-y-2 text-sm">
          <div class="flex justify-between"><span class="text-theme-muted">响应延迟</span><span :class="source.latency_ms === null ? 'text-theme-muted' : source.latency_ms < 100 ? 'text-[var(--color-success)]' : 'text-[var(--color-warning)]'">{{ source.latency_ms === null ? '-' : source.latency_ms + 'ms' }}</span></div>
          <div class="flex justify-between"><span class="text-theme-muted">连续失败</span><span :class="source.fail_count === 0 ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]'">{{ source.fail_count }} 次</span></div>
        </div>
        <div class="flex gap-2 mt-4 pt-3 border-t border-theme/50">
          <button v-if="source.state !== 'open'" class="flex-1 px-3 py-1.5 bg-[var(--color-danger-bg)] text-[var(--color-danger)] rounded-sm text-xs" @click="$emit('confirm-action', `熔断 ${key}`, `系统将停止从 ${key} 获取数据，转到其他数据源。确定？`, () => $emit('control-circuit', key, 'open'))">⚠️ 熔断</button>
          <button v-if="source.state === 'open'" class="flex-1 px-3 py-1.5 bg-[var(--color-success-bg)] text-[var(--color-success)] rounded-sm text-xs" @click="$emit('confirm-action', `恢复 ${key}`, `系统将重新从 ${key} 获取数据。确定？`, () => $emit('control-circuit', key, 'close'))">✅ 恢复</button>
        </div>
        <!-- 探测历史 -->
        <div class="mt-3 pt-3 border-t border-theme/50">
          <button @click="toggleHistory(key)" class="text-[10px] text-theme-muted hover:text-theme-primary flex items-center gap-1">
            <span>{{ expandedHistory[key] ? '▼' : '▶' }}</span>
            <span>探测历史</span>
            <span v-if="source.history?.length">({{ source.history.length }})</span>
          </button>
          <div v-if="expandedHistory[key] && source.history?.length" class="mt-2 space-y-1">
            <div v-for="(h, i) in source.history.slice().reverse()" :key="i" class="flex items-center justify-between text-[10px]">
              <span class="text-theme-muted">{{ formatHistoryTime(h.timestamp) }}</span>
              <span :class="getHistoryStatusClass(h.status)">{{ h.status === 'ok' ? '✅' : h.status === 'fail' ? '❌' : h.status === 'timeout' ? '⏱️' : '⚠️' }}</span>
              <span :class="getHistoryStatusClass(h.status)">{{ h.status === 'ok' ? h.latency + 'ms' : h.status }}</span>
            </div>
            <div v-if="!source.history?.length" class="text-[10px] text-theme-muted">暂无历史记录</div>
          </div>
        </div>
      </div>
    </div>


    <!-- 饼图 + 健康详情 -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- ECharts 饼图 -->
      <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
        <div class="text-sm font-bold text-theme-primary mb-3">📊 数据源响应速度分布</div>
        <div ref="chartRef" style="width:100%;height:220px"></div>
      </div>
      <!-- 状态列表 -->
      <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
        <div class="text-sm font-bold text-theme-primary mb-3">🔍 各源详情</div>
        <div class="space-y-2">
          <div v-for="(info, key) in sourceHealthData" :key="key" class="flex items-center justify-between p-2 rounded-sm bg-terminal-panel/50">
            <div class="flex items-center gap-2">
              <span class="w-2.5 h-2.5 rounded-full" :class="info.status === 'ok' ? 'bg-[var(--color-success-light)]' : info.status === 'slow' ? 'bg-yellow-400' : 'bg-[var(--color-danger-light)]'"></span>
              <span class="text-sm text-theme-primary">{{ key }}</span>
            </div>
            <div class="flex items-center gap-3 text-xs">
              <span class="text-theme-muted">{{ info.latency_ms || 0 }}ms</span>
              <span class="px-1.5 py-0.5 rounded-sm text-[10px]" :class="info.latency_ms === null ? 'bg-[var(--color-info-bg)] text-[var(--color-info)]' : info.latency_ms < 200 ? 'bg-[var(--color-success-bg)] text-[var(--color-success)]' : info.latency_ms <= 500 ? 'bg-[var(--color-warning-bg)] text-[var(--color-warning)]' : 'bg-[var(--color-danger-bg)] text-[var(--color-danger)]'">
                  {{ info.latency_ms === null ? '未知' : info.latency_ms < 200 ? '<200ms' : info.latency_ms <= 500 ? '200-500ms' : '>500ms' }}
                </span>
            </div>
          </div>
          <div v-if="!Object.keys(sourceHealthData).length" class="text-center text-theme-muted text-xs py-4">暂无数据</div>
        </div>
      </div>
    </div>
    <div class="p-3 bg-[var(--color-warning-bg)] border border-[var(--color-warning-border)] rounded-sm text-xs text-theme-muted">
      <strong class="text-[var(--color-warning)]">操作后果说明：</strong>
      <ul class="mt-1 space-y-1 list-disc list-inside">
        <li><strong>熔断</strong>：立即停止从该数据源获取数据，系统自动切换到其他可用源</li>
        <li><strong>恢复</strong>：重新启用该数据源，系统会尝试连接并检测其健康状态</li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
const echarts = window.echarts

const props = defineProps({
  sourceStatus: { type: Object, required: true },
  probeData: { type: Object, default: null },
  sourceHealthData: { type: Object, default: () => ({}) },
  proxyUrl: { type: String, default: '' },
  topologyData: { type: Object, default: () => ({ nodes: [], edges: [] }) }
})

const emit = defineEmits(['refresh', 'save-proxy', 'confirm-action', 'control-circuit', 'switch-source', 'fetch-topology'])

const expandedHistory = ref({})
const chartRef = ref(null)
const localProxyUrl = ref('')
const showTopology = ref(false)
const selectedNode = ref(null)
const fallbackTarget = ref('')
let chart = null

const topologyNodes = computed(() => props.topologyData?.nodes || [])
const topologyEdges = computed(() => props.topologyData?.edges || [])

watch(() => props.proxyUrl, (newVal) => {
  localProxyUrl.value = newVal || ''
}, { immediate: true })

watch(showTopology, (show) => {
  if (show) {
    emit('fetch-topology')
  }
})

function toggleHistory(key) {
  expandedHistory.value[key] = !expandedHistory.value[key]
}

function formatHistoryTime(timestamp) {
  if (!timestamp) return '-'
  const d = new Date(timestamp * 1000)
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`
}

function getHistoryStatusClass(status) {
  if (status === 'ok') return 'text-[var(--color-success)]'
  if (status === 'fail' || status === 'timeout') return 'text-[var(--color-danger)]'
  return 'text-[var(--color-warning)]'
}

function getNodeX(nodeId) {
  const nodes = topologyNodes.value
  const idx = nodes.findIndex(n => n.id === nodeId)
  if (idx === -1) return 50
  const spacing = 700 / Math.max(nodes.length, 1)
  return 50 + idx * spacing
}

function getNodeY(nodeId) {
  return 100
}

function getNodeColor(status) {
  if (status === 'green') return '#22c55e'
  if (status === 'yellow') return '#eab308'
  return '#ef4444'
}

function getStatusTextClass(status) {
  if (status === 'green') return 'text-[var(--color-success)]'
  if (status === 'yellow') return 'text-[var(--color-warning)]'
  return 'text-[var(--color-danger)]'
}

function getStatusLabel(status) {
  if (status === 'green') return '健康'
  if (status === 'yellow') return '未知'
  return '异常'
}

function selectNode(node) {
  selectedNode.value = node
  fallbackTarget.value = ''
}

function confirmSwitch() {
  if (!selectedNode.value || !fallbackTarget.value) return
  emit('confirm-action', 
    `切换数据源`, 
    `将数据源从 ${selectedNode.value.name} 切换到 ${fallbackTarget.value.toUpperCase()}？此操作会立即生效。`,
    () => {
      emit('switch-source', selectedNode.value.id, fallbackTarget.value)
      selectedNode.value = null
      fallbackTarget.value = ''
    }
  )
}

function updateChart(sources) {
  if (!chartRef.value) return
  if (!chart) {
    chart = echarts.init(chartRef.value)
  }

  const fastCount = Object.values(sources).filter(s => s.latency_ms !== null && s.latency_ms < 200).length
  const mediumCount = Object.values(sources).filter(s => s.latency_ms !== null && s.latency_ms >= 200 && s.latency_ms <= 500).length
  const slowCount = Object.values(sources).filter(s => s.latency_ms !== null && s.latency_ms > 500).length
  const errorCount = Object.values(sources).filter(s => s.status === 'error').length

  const chartData = [
    { value: fastCount, name: '<200ms 快速', itemStyle: { color: '#22c55e' } },
    { value: mediumCount, name: '200-500ms 中等', itemStyle: { color: '#eab308' } },
    { value: slowCount, name: '>500ms 慢速', itemStyle: { color: '#ef4444' } },
    { value: errorCount, name: '连接异常', itemStyle: { color: '#6b7280' } },
  ]

  const visibleData = chartData.filter(d => d.value > 0)

  chart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} 个' },
    legend: { bottom: 0, textStyle: { color: '#9ca3af', fontSize: 11 } },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      label: { show: true, formatter: '{b} {c}', fontSize: 11, color: '#d1d5db' },
      data: visibleData,
    }],
  })
}

watch(() => props.sourceHealthData, (newData) => {
  if (Object.keys(newData).length > 0) {
    updateChart(newData)
  }
}, { immediate: true, deep: true })

let resizeHandler = null

onMounted(() => {
  resizeHandler = () => chart?.resize()
  window.addEventListener('resize', resizeHandler)
})

onUnmounted(() => {
  if (resizeHandler) {
    window.removeEventListener('resize', resizeHandler)
    resizeHandler = null
  }
  if (chart) {
    chart.dispose()
    chart = null
  }
})
</script>
