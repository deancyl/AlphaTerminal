<template>
  <div class="flex flex-col w-full h-full overflow-hidden">

    <!-- 顶部栏 -->
    <div class="shrink-0 flex items-center justify-between px-2 py-1 border-b border-theme bg-terminal-panel/80">
      <span class="text-[10px] text-amber-400 font-bold">💰 资金流向</span>
      <span class="text-[8px] text-theme-muted">{{ tsDisplay }}</span>
    </div>

    <!-- 核心指标行 -->
    <div v-if="latestData" class="shrink-0 grid grid-cols-3 gap-px p-1 bg-theme border-y border-theme">
      <div class="flex flex-col items-center bg-terminal-panel/60 px-1 py-0.5 rounded">
        <span class="text-[8px] text-theme-muted">主力净流入</span>
        <span
          class="text-[10px] font-mono font-bold"
          :class="(latestData.main_net || 0) >= 0 ? 'text-bullish' : 'text-bearish'"
        >{{ formatYuan(latestData.main_net) }}</span>
      </div>
      <div class="flex flex-col items-center bg-terminal-panel/60 px-1 py-0.5 rounded">
        <span class="text-[8px] text-theme-muted">净占比</span>
        <span
          class="text-[10px] font-mono"
          :class="(latestData.main_pct || 0) >= 0 ? 'text-bullish' : 'text-bearish'"
        >{{ (latestData.main_pct || 0) >= 0 ? '+' : '' }}{{ (latestData.main_pct || 0).toFixed(2) }}%</span>
      </div>
      <div class="flex flex-col items-center bg-terminal-panel/60 px-1 py-0.5 rounded">
        <span class="text-[8px] text-theme-muted">趋势</span>
        <span
          class="text-[10px] font-mono font-bold"
          :class="mainTrend >= 0 ? 'text-bullish' : 'text-bearish'"
        >{{ mainTrend >= 0 ? '↑吸筹' : '↓出逃' }}</span>
      </div>
    </div>

    <!-- 大单/小单对比网格 -->
    <div v-if="latestData" class="shrink-0 grid grid-cols-4 gap-px p-1">
      <div class="flex flex-col items-center bg-terminal-panel/40 px-1 py-0.5 rounded">
        <span class="text-[7px] text-theme-muted">超大单</span>
        <span
          class="text-[9px] font-mono"
          :class="(latestData.super_net || 0) >= 0 ? 'text-bullish' : 'text-bearish'"
        >{{ formatYuan(latestData.super_net) }}</span>
      </div>
      <div class="flex flex-col items-center bg-terminal-panel/40 px-1 py-0.5 rounded">
        <span class="text-[7px] text-theme-muted">大单</span>
        <span
          class="text-[9px] font-mono"
          :class="(latestData.large_net || 0) >= 0 ? 'text-bullish' : 'text-bearish'"
        >{{ formatYuan(latestData.large_net) }}</span>
      </div>
      <div class="flex flex-col items-center bg-terminal-panel/40 px-1 py-0.5 rounded">
        <span class="text-[7px] text-theme-muted">中单</span>
        <span
          class="text-[9px] font-mono"
          :class="(latestData.medium_net || 0) >= 0 ? 'text-bullish' : 'text-bearish'"
        >{{ formatYuan(latestData.medium_net) }}</span>
      </div>
      <div class="flex flex-col items-center bg-terminal-panel/40 px-1 py-0.5 rounded">
        <span class="text-[7px] text-theme-muted">小单</span>
        <span
          class="text-[9px] font-mono"
          :class="(latestData.small_net || 0) >= 0 ? 'text-bullish' : 'text-bearish'"
        >{{ formatYuan(latestData.small_net) }}</span>
      </div>
    </div>

    <!-- ECharts 柱状图：近10日主力净流入 -->
    <div class="flex-1 min-h-0" ref="chartEl"></div>

    <!-- 无数据 / 加载（始终显示数据，无时间硬拦截） -->
    <div v-if="isLoading && !fundFlowData.length" class="flex-1 flex flex-col items-center justify-center">
      <span class="text-theme-muted text-[10px] animate-pulse">⏳ 加载资金流...</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { apiFetch } from '../utils/api.js'
import { logger } from '../utils/logger.js'

const chartEl    = ref(null)
const fundFlowData = ref([])
const isLoading   = ref(false)
const tsDisplay   = ref('')
let refreshTimer  = null
let chartInstance = null

// ── 最新一天数据 ──────────────────────────────────────────────
const latestData = computed(() => fundFlowData.value[0] || null)

// 近10日数据（用于图表）
const chartData = computed(() => fundFlowData.value.slice(0, 10).reverse())

// 过去N日净流入趋势（决定"吸筹/出逃"标签）
const mainTrend = computed(() => {
  const items = chartData.value
  if (!items.length) return 0
  const pos = items.filter(i => (i.main_net || 0) > 0).length
  return pos >= items.length / 2 ? 1 : -1
})

// ── 工具函数 ───────────────────────────────────────────────────
function formatYuan(val) {
  if (val == null) return '0'
  const abs = Math.abs(val)
  if (abs >= 1e8) return `${val < 0 ? '-' : '+'}${((abs) / 1e8).toFixed(2)}亿`
  if (abs >= 1e4) return `${val < 0 ? '-' : '+'}${((abs) / 1e4).toFixed(0)}万`
  return `${val < 0 ? '-' : '+'}${abs.toFixed(0)}`
}

// ── ECharts 渲染 ──────────────────────────────────────────────
function renderChart() {
  if (!chartEl.value) return
  if (chartInstance) { chartInstance.dispose(); chartInstance = null }

  const items = chartData.value
  if (!items.length) return

  const dates = items.map(i => (i.date || '').slice(5))  // MM-DD
  const mainNets = items.map(i => i.main_net || 0)
  const maxAbs = Math.max(...mainNets.map(Math.abs), 1)

  chartInstance = window.echarts.init(chartEl.value, 'dark')
  chartInstance.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: '#1e2130', borderColor: '#374151',
      textStyle: { color: '#d1d5db', fontSize: 9 },
      formatter: (p) => {
        const v = p[0].value
        return `${p[0].name}<br/><b style="color:${v >= 0 ? '#14b143' : '#ef232a'}">${formatYuan(v)}</b>`
      },
    },
    grid: { top: 4, bottom: 2, left: 4, right: 8, containLabel: true },
    xAxis: {
      type: 'category', data: dates,
      axisLabel: { show: true, fontSize: 8, color: '#6b7280', interval: 0, rotate: 30 },
      axisLine: { lineStyle: { color: '#374151' } },
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        show: true, fontSize: 8, color: '#6b7280',
        formatter: (v) => Math.abs(v) >= 1e8 ? (v / 1e8).toFixed(0) + '亿' : (v / 1e4).toFixed(0) + 'w',
      },
      splitLine: { lineStyle: { color: '#1f2937' } },
    },
    series: [{
      type: 'bar',
      data: mainNets.map(v => ({
        value: v,
        itemStyle: { color: v >= 0 ? '#14b143' : '#ef232a' },
      })),
      barMaxWidth: 20,
      label: {
        show: true,
        position: 'top',
        color: '#9ca3af',
        fontSize: 7,
        formatter: (p) => `${(p.value / 1e4).toFixed(0)}w`,
      },
    }],
  })
}

// ── 数据获取 ───────────────────────────────────────────────────
async function fetchFundFlow() {
  isLoading.value = fundFlowData.value.length === 0
  try {
    const d = await apiFetch('/api/v1/market/fund_flow', { timeoutMs: 15000 })
    if (!d || d.code !== 0) return

    fundFlowData.value = d.data?.items || d.data || []

    if (fundFlowData.value.length > 0) {
      const latest = fundFlowData.value[0]
      tsDisplay.value = latest.date || new Date().toLocaleDateString('zh-CN')
    }

    await nextTick()
    renderChart()
  } catch (e) {
    logger.error('[FundFlowPanel] fetchFundFlow error:', e)
  } finally {
    isLoading.value = false
  }
}

// ── 生命周期 ───────────────────────────────────────────────────
onMounted(() => {
  fetchFundFlow()
  refreshTimer = setInterval(fetchFundFlow, 5 * 60 * 1000)  // 5 分钟轮询
})

onBeforeUnmount(() => {
  if (refreshTimer) clearInterval(refreshTimer)
  if (chartInstance) chartInstance.dispose()
  chartInstance = null
})

watch(fundFlowData, () => {
  nextTick(renderChart)
})
</script>
