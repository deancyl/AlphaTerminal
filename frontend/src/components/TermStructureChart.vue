<template>
  <div class="w-full h-full relative flex flex-col" style="min-height: 120px">
    <!-- 顶部标签 -->
    <div class="shrink-0 flex items-center gap-3 px-1 py-1 border-b border-theme bg-terminal-bg/60">
      <span class="text-[10px] font-mono text-terminal-dim">📐 期限结构</span>
      <span class="text-[10px] font-mono text-theme-muted">|</span>
      <span class="text-[10px] font-mono text-terminal-dim">{{ symbolName }}</span>
      <span class="text-[10px] font-mono text-theme-muted">|</span>
      <span
        class="text-[10px] font-mono font-medium"
        :class="curveType === 'Contango' ? 'text-bearish' : 'text-bullish'"
      >{{ curveType }}</span>
      <span class="flex-1" />
      <span class="text-[9px] text-terminal-dim">{{ updateTime || '...' }}</span>
    </div>

    <!-- 错误 / 加载 / 空数据 -->
    <div v-if="props.hasError" class="flex-1 flex items-center justify-center">
      <span class="text-bullish text-xs">{{ error || '加载失败' }}</span>
    </div>
    <div v-else-if="props.isLoading" class="flex-1 flex flex-col p-3 gap-2">
      <div class="skeleton h-3 w-24 rounded"></div>
      <div class="flex-1 skeleton rounded-lg"></div>
      <div class="flex gap-2">
        <div class="skeleton h-2 w-12 rounded"></div>
        <div class="skeleton h-2 w-12 rounded"></div>
      </div>
    </div>
    <div v-else-if="!hasData" class="flex-1 flex items-center justify-center">
      <span class="text-terminal-dim text-xs">暂无期限结构数据</span>
    </div>

    <!-- 图表 -->
    <div v-else ref="chartRef" class="flex-1 min-h-0"></div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'

const props = defineProps({
  symbol:    { type: String, default: 'RB' },
  name:      { type: String, default: '' },
  isLoading: { type: Boolean, default: false },
  hasError:  { type: Boolean, default: false },
})

const chartRef  = ref(null)
const chartInst = ref(null)
const error     = ref('')
const updateTime = ref('')

let ro = null

const symbolName = computed(() => props.name || props.symbol)

// 判断 Contango 还是 Backwardation（比较最近月与最远月）
const curveType = computed(() => {
  const items = props.data || []
  if (items.length < 2) return ''
  const first = items[0].price
  const last  = items[items.length - 1].price
  if (last > first) return 'Contango'      // 远月升水 ↑
  if (last < first) return 'Backwardation' // 近月升水 ↓
  return 'Flat'
})

const hasData = computed(() => (props.data || []).length > 0)

function buildOption() {
  const items = props.data || []
  const months  = items.map(d => d.month)
  const prices  = items.map(d => d.price)
  const oiValues = items.map(d => d.oi)

  const priceMin = Math.min(...prices)
  const priceMax = Math.max(...prices)
  const pricePad = (priceMax - priceMin) * 0.15 || priceMax * 0.02

  const oiMax = Math.max(...oiValues.filter(v => v > 0), 1)

  return {
    backgroundColor: 'transparent',
    animation: false,
    grid: [
      { top: 10, right: 70, bottom: '35%', left: 55 },
      { top: '68%', right: 70, bottom: 22, left: 55 },
    ],
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(10,14,23,0.95)',
      borderColor: 'rgba(50,50,50,0.8)',
      textStyle: { color: '#9ca3af', fontSize: 11, fontFamily: 'monospace' },
      formatter: (params) => {
        const p = params.find(p => p.seriesName === '价格')
        const o = params.find(p => p.seriesName === '持仓量')
        if (!p) return ''
        const item = items[p.dataIndex]
        return `<span style="color:#60a5fa;font-family:monospace">${item.contract}</span><br/>`
          + `价格: <span style="color:#f3f4f6">${item.price.toFixed(2)}</span><br/>`
          + `持仓量: <span style="color:#fbbf24">${item.oi.toLocaleString()}</span>`
      },
    },
    xAxis: [
      {
        type: 'category', data: months, gridIndex: 0,
        axisLine: { lineStyle: { color: '#2d2d2d' } },
        axisTick: { show: false },
        axisLabel: { color: '#6b7280', fontSize: 9, fontFamily: 'monospace' },
        splitLine: { show: false },
      },
      {
        type: 'category', data: months, gridIndex: 1,
        axisLine: { lineStyle: { color: '#2d2d2d' } },
        axisTick: { show: false },
        axisLabel: { show: false },
        splitLine: { show: false },
      },
    ],
    yAxis: [
      {
        type: 'value', scale: true, gridIndex: 0,
        min: priceMin - pricePad, max: priceMax + pricePad,
        axisLine: { show: false }, axisTick: { show: false },
        axisLabel: { color: '#6b7280', fontSize: 9, fontFamily: 'monospace', formatter: v => v.toFixed(0) },
        splitLine: { lineStyle: { color: '#1f1f1f', type: 'dashed' } },
      },
      {
        type: 'value', scale: true, gridIndex: 1,
        min: 0, max: oiMax * 1.2,
        axisLine: { show: false }, axisTick: { show: false },
        axisLabel: { show: false },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: '价格', type: 'line',
        data: prices,
        xAxisIndex: 0, yAxisIndex: 0,
        smooth: 0.3, symbol: 'circle', symbolSize: 7,
        lineStyle: { color: '#60a5fa', width: 2 },
        itemStyle: { color: '#60a5fa', borderWidth: 2, borderColor: '#0a0e17' },
        label: {
          show: true, position: 'top', distance: 4,
          color: '#9ca3af', fontSize: 8, fontFamily: 'monospace',
          formatter: v => v.value.toFixed(0),
        },
      },
      {
        name: '持仓量', type: 'bar',
        data: oiValues,
        xAxisIndex: 1, yAxisIndex: 1,
        barMaxWidth: 20,
        itemStyle: { color: 'rgba(251,191,36,0.55)' },
      },
    ],
  }
}

async function initChart() {
  await nextTick()
  if (!chartRef.value || !window.echarts) return
  if (chartInst.value) { chartInst.value.dispose(); chartInst.value = null }
  chartInst.value = window.echarts.init(chartRef.value, null, { renderer: 'canvas' })
  chartInst.value.setOption(buildOption())
}

onMounted(() => {
  initChart()
  if (chartRef.value) {
    ro = new ResizeObserver(() => chartInst.value?.resize())
    ro.observe(chartRef.value)
  }
})

onUnmounted(() => {
  ro?.disconnect()
  chartInst.value?.dispose()
})

watch([() => props.data, () => props.symbol], () => { initChart() })
</script>
