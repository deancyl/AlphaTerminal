<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-lg font-bold text-theme-primary">📡 数据源控制</h2>
        <p class="text-xs text-theme-muted mt-1">管理股票行情数据的来源，控制数据质量和系统稳定性</p>
      </div>
      <button class="px-4 py-2 bg-terminal-accent/15 text-terminal-accent rounded-sm text-sm" @click="$emit('refresh')">🔄 刷新状态</button>
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
import { ref, onMounted, onUnmounted, watch } from 'vue'
// ECharts 通过 CDN 加载，使用全局变量
const echarts = window.echarts

const props = defineProps({
  sourceStatus: { type: Object, required: true },
  probeData: { type: Object, default: null },
  sourceHealthData: { type: Object, default: () => ({}) },
  proxyUrl: { type: String, default: '' }
})

const emit = defineEmits(['refresh', 'save-proxy', 'confirm-action', 'control-circuit'])

const expandedHistory = ref({})
const chartRef = ref(null)
const localProxyUrl = ref('')
let chart = null

// Sync localProxyUrl with prop
watch(() => props.proxyUrl, (newVal) => {
  localProxyUrl.value = newVal || ''
}, { immediate: true })

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

function updateChart(sources) {
  if (!chartRef.value) return
  if (!chart) {
    chart = echarts.init(chartRef.value)
  }

  // Group by latency buckets
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

  // Filter out zero-value sectors
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

// Watch for sourceHealthData changes
watch(() => props.sourceHealthData, (newData) => {
  if (Object.keys(newData).length > 0) {
    updateChart(newData)
  }
}, { immediate: true, deep: true })

// Handle resize
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
