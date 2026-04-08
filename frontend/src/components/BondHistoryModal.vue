<template>
  <!-- 遮罩 -->
  <div
    v-if="visible"
    class="fixed inset-0 z-50 flex items-center justify-center"
    style="background: rgba(0,0,0,0.65); backdrop-filter: blur(3px);"
    @click.self="close"
  >
    <!-- 弹窗主体 -->
    <div class="terminal-panel border border-gray-700 rounded-xl p-4 w-[480px] max-w-[90vw] flex flex-col gap-3 shadow-2xl">

      <!-- 头部 -->
      <div class="flex items-center justify-between">
        <div class="flex flex-col">
          <span class="text-[13px] font-semibold text-gray-200">{{ tenorLabel }} 国债历史走势</span>
          <span class="text-[10px] text-terminal-dim mt-0.5">周期：{{ periodLabel }} &nbsp;|&nbsp; 数据来源：AkShare</span>
        </div>
        <button
          class="text-gray-500 hover:text-gray-200 transition-colors text-lg leading-none"
          @click="close"
        >✕</button>
      </div>

      <!-- 加载 / 错误 -->
      <div v-if="isLoading" class="flex items-center justify-center py-6">
        <span class="text-terminal-dim text-xs">加载中…</span>
      </div>
      <div v-else-if="error" class="flex items-center justify-center py-6">
        <span class="text-red-400 text-xs">{{ error }}</span>
      </div>

      <!-- 核心数据 -->
      <template v-else-if="historyData.length">
        <!-- 分位标签 -->
        <div class="flex items-center gap-3 px-1">
          <div class="flex flex-col">
            <span class="text-[10px] text-terminal-dim">当前收益率</span>
            <span class="text-[18px] font-mono font-bold" :class="changeColor">
              {{ currentYield?.toFixed(4) }}%
            </span>
          </div>
          <div class="h-8 w-px bg-gray-700"></div>
          <div class="flex flex-col">
            <span class="text-[10px] text-terminal-dim">历史{{ periodLabel }}</span>
            <span
              class="text-[18px] font-mono font-bold"
              :class="percentileColor"
            >{{ percentileDisplay }}</span>
          </div>
          <div class="h-8 w-px bg-gray-700"></div>
          <div class="flex flex-col">
            <span class="text-[10px] text-terminal-dim">区间高点</span>
            <span class="text-[12px] font-mono text-red-400">{{ maxYield?.toFixed(4) }}%</span>
            <span class="text-[10px] text-terminal-dim">区间低点</span>
            <span class="text-[12px] font-mono text-green-400">{{ minYield?.toFixed(4) }}%</span>
          </div>
        </div>

        <!-- 迷你柱状图（分位分布） -->
        <div class="text-[9px] text-terminal-dim px-1">历史分位分布</div>
        <div class="relative h-4 rounded bg-gray-800 overflow-hidden mx-1">
          <div
            class="absolute top-0 bottom-0 rounded"
            :style="{ left: Math.max(0, Math.min(98, percentile ?? 0)) + '%', width: '2px', background: '#60a5fa' }"
          ></div>
          <div class="absolute inset-0 flex items-center">
            <div
              v-for="(bucket, i) in percentileBuckets"
              :key="i"
              class="flex-1 border-r border-gray-700/50 last:border-0"
            ></div>
          </div>
        </div>
        <div class="flex justify-between px-1 text-[8px] text-terminal-dim">
          <span>历史低 ({{ minYield?.toFixed(2) }}%)</span>
          <span>当前</span>
          <span>历史高 ({{ maxYield?.toFixed(2) }}%)</span>
        </div>

        <!-- 折线图 -->
        <div ref="chartRef" style="height: 160px;" class="w-full"></div>
      </template>

      <div v-else class="flex items-center justify-center py-6">
        <span class="text-terminal-dim text-xs">暂无历史数据</span>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'

const props = defineProps({
  visible:   { type: Boolean, default: false },
  tenor:     { type: String, default: '10年' },  // 如 "10年"
  period:    { type: String, default: '1Y' },   // 如 "1Y"
})

const emit = defineEmits(['close'])

const chartRef   = ref(null)
const chartInst  = ref(null)
const isLoading    = ref(false)
const error        = ref('')
const historyData  = ref([])
const currentYield = ref(null)
const percentile   = ref(null)

const periodLabel = computed(() => ({ '1M': '近1月', '3M': '近3月', '6M': '近6月', '1Y': '近1年', '3Y': '近3年' }[props.period] || props.period))
const tenorLabel  = computed(() => props.tenor)

const percentileDisplay = computed(() => {
  if (percentile.value == null) return '--'
  return `${percentile.value.toFixed(1)}% 分位`
})

const percentileColor = computed(() => {
  const p = percentile.value
  if (p == null) return 'text-gray-400'
  if (p <= 20)  return 'text-green-400'     // 极度低估
  if (p <= 50)  return 'text-blue-400'     // 偏低
  if (p <= 80)  return 'text-amber-400'    // 偏高
  return 'text-red-400'                     // 极度高估
})

const changeColor = computed(() => 'text-gray-100')

const minYield = computed(() => historyData.value.length ? Math.min(...historyData.value.map(d => d.yield)) : null)
const maxYield = computed(() => historyData.value.length ? Math.max(...historyData.value.map(d => d.yield)) : null)

const percentileBuckets = Array(20).fill(0)

async function fetchHistory() {
  if (!props.visible) return
  isLoading.value = true
  error.value = ''
  historyData.value = []
  percentile.value = null
  currentYield.value = null

  // 超时兜底（8秒强制关闭 loading）
  const timer = setTimeout(() => {
    if (isLoading.value) {
      isLoading.value = false
      error.value = '请求超时，请检查网络或稍后重试'
    }
  }, 8000)

  try {
    const res = await fetch(`/api/v1/bond/history?tenor=${encodeURIComponent(props.tenor)}&period=${props.period}`)
    clearTimeout(timer)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    if (data.error || !data.history?.length) {
      throw new Error(data.error || '暂无历史数据（AkShare 限流或网络中断）')
    }
    historyData.value = data.history || []
    currentYield.value = data.current ?? null
    percentile.value   = data.percentile ?? null
    await nextTick()
    renderChart()
  } catch (e) {
    clearTimeout(timer)
    error.value = String(e.message || '加载失败')
  } finally {
    isLoading.value = false
  }
}

function renderChart() {
  if (!chartRef.value || !window.echarts || !historyData.value.length) return
  if (chartInst.value) {
    chartInst.value.clear()
    chartInst.value.dispose()
    chartInst.value = null
  }
  chartInst.value = window.echarts.init(chartRef.value, null, { renderer: 'canvas' })

  const data  = historyData.value
  const dates = data.map(d => d.date)
  const yields = data.map(d => d.yield)
  const cur   = currentYield.value
  const minY  = Math.min(...yields)
  const maxY  = Math.max(...yields)
  const pad   = (maxY - minY) * 0.15 || 0.05

  const option = {
    backgroundColor: 'transparent',
    animation: false,
    grid: { top: 8, right: 12, bottom: 28, left: 52 },
    xAxis: {
      type: 'category', data: dates,
      axisLine: { lineStyle: { color: '#2d2d2d' } },
      axisTick: { show: false },
      axisLabel: { color: '#6b7280', fontSize: 8, fontFamily: 'monospace', rotate: 30,
        formatter: v => { const d = new Date(v); return `${d.getMonth() + 1}/${d.getDate()}` } },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value', min: minY - pad, max: maxY + pad,
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: '#6b7280', fontSize: 8, fontFamily: 'monospace', formatter: v => v.toFixed(2) + '%' },
      splitLine: { lineStyle: { color: '#1f1f1f', type: 'dashed' } },
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(10,14,23,0.95)',
      borderColor: 'rgba(50,50,50,0.8)',
      textStyle: { color: '#9ca3af', fontSize: 10, fontFamily: 'monospace' },
      formatter: p => `<span style="color:#60a5fa">${p[0].name}</span><br/>收益率: <span style="color:#f3f4f6">${p[0].value?.toFixed(4)}%</span>`,
    },
    series: [
      {
        type: 'line', data: yields,
        smooth: 0.3, symbol: 'none',
        lineStyle: { color: '#60a5fa', width: 1.5 },
        areaStyle: {
          color: new window.echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(96,165,250,0.15)' },
            { offset: 1, color: 'rgba(96,165,250,0.01)' },
          ]),
        },
        markLine: {
          silent: true, symbol: 'none',
          lineStyle: { color: '#fbbf24', width: 1.5, type: 'dashed' },
          data: cur != null ? [{ yAxis: cur, label: { formatter: `当前 ${cur.toFixed(3)}%`, color: '#fbbf24', fontSize: 8 } }] : [],
        },
      },
    ],
  }
  chartInst.value.setOption(option)
}

function close() { emit('close') }

watch(() => props.visible, (v) => { if (v) fetchHistory() })
watch(() => props.tenor,   ()  => { if (props.visible) fetchHistory() })
watch(() => props.period,  ()  => { if (props.visible) fetchHistory() })
</script>
