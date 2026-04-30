<template>
  <div class="w-full h-full relative flex flex-col" style="min-height: 120px">
    <!-- 顶部标签 -->
    <div class="shrink-0 flex items-center gap-3 px-1 py-1 border-b border-theme bg-terminal-bg/60">
      <span class="text-[10px] font-mono text-terminal-dim">📐 期限利差 (10Y-2Y)</span>
      <span
        class="text-[10px] font-mono font-medium"
        :class="spread >= 0 ? 'text-[var(--color-info)]' : 'text-bullish'"
      >{{ spread >= 0 ? '+' : '' }}{{ spread?.toFixed(1) ?? '--' }}bp</span>
      <span
        v-if="spread != null"
        class="text-[9px] px-1 py-0.5 rounded border text-[9px]"
        :class="spread >= 0 ? 'border-[var(--color-info-border)] text-[var(--color-info)]/70' : 'border-[var(--color-danger-border)] text-bullish/70'"
      >{{ spread >= 0 ? '正常' : '倒挂⚠️' }}</span>
      <div class="flex-1" />
      <span class="text-[9px] text-terminal-dim">{{ updateTime || '...' }}</span>
    </div>

    <!-- 错误 / 加载 / 空 -->
    <div v-if="hasError" class="flex-1 flex items-center justify-center">
      <span class="text-bullish text-xs">{{ errorMsg }}</span>
    </div>
    <div v-else-if="isLoading" class="flex-1 flex items-center justify-center">
      <span class="text-terminal-dim text-xs">加载中…</span>
    </div>
    <div v-else-if="!hasData" class="flex-1 flex items-center justify-center">
      <span class="text-terminal-dim text-xs">暂无利差数据</span>
    </div>
    <div v-else ref="chartRef" class="flex-1 min-h-0"></div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'

const props = defineProps({
  tenors10y: { type: Object, default: null },   // {date, yield}[]
  tenors2y:  { type: Object, default: null },   // {date, yield}[]
  updateTime: { type: String, default: '' },
  isLoading:  { type: Boolean, default: false },
  hasError:   { type: Boolean, default: false },
  errorMsg:   { type: String, default: '' },
})

const chartRef  = ref(null)
const chartInst = ref(null)
let ro = null

// 计算 10Y-2Y 差值序列
const spreadData = computed(() => {
  const s10 = props.tenors10y || []
  const s2  = props.tenors2y  || []
  const map2 = {}
  for (const d of s2) map2[d.date] = d.yield
  return s10
    .filter(d => map2[d.date] != null)
    .map(d => ({
      date:   d.date,
      spread: (d.yield - map2[d.date]) * 10000, // 转换为 bp
    }))
})

const hasData = computed(() => spreadData.value.length > 0)

// 当前利差（最新）
const spread = computed(() => {
  const d = spreadData.value
  return d.length ? d[d.length - 1].spread : null
})

function buildOption() {
  const data = spreadData.value
  const dates = data.map(d => d.date)
  const values = data.map(d => d.spread)

  const minV = Math.min(...values)
  const maxV = Math.max(...values)
  const pad  = (maxV - minV) * 0.2 || 10

  return {
    backgroundColor: 'transparent',
    animation: false,
    grid: { top: 8, right: 14, bottom: 28, left: 52 },
    xAxis: {
      type: 'category', data: dates,
      axisLine: { lineStyle: { color: '#2d2d2d' } },
      axisTick: { show: false },
      axisLabel: {
        color: '#6b7280', fontSize: 8, fontFamily: 'monospace',
        formatter: v => {
          const d = new Date(v)
          return `${d.getMonth() + 1}/${d.getDate()}`
        },
        rotate: 30,
      },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      min: minV - pad, max: maxV + pad,
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: '#6b7280', fontSize: 9, fontFamily: 'monospace', formatter: v => v.toFixed(0) + 'bp' },
      splitLine: { lineStyle: { color: '#1f1f1f', type: 'dashed' } },
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(10,14,23,0.95)',
      borderColor: 'rgba(50,50,50,0.8)',
      textStyle: { color: '#9ca3af', fontSize: 11, fontFamily: 'monospace' },
      formatter: (params) => {
        const p = params[0]
        const v = p.value
        const sign = v >= 0 ? '+' : ''
        const color = v >= 0 ? '#60a5fa' : '#f87171'
        return `<span style="color:#60a5fa;font-family:monospace">${p.name}</span><br/>`
          + `<span style="color:${color}">利差: ${sign}${v.toFixed(1)} bp</span>`
      },
    },
    series: [
      {
        type: 'bar',
        data: values.map(v => ({
          value: v,
          itemStyle: { color: v >= 0 ? 'rgba(96,165,250,0.7)' : 'rgba(248,113,113,0.7)' },
        })),
        barMaxWidth: 8,
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { color: '#6b7280', width: 1, type: 'dashed' },
          data: [{ yAxis: 0 }],
          label: { formatter: '0bp', color: '#6b7280', fontSize: 8, fontFamily: 'monospace' },
        },
      },
    ],
  }
}

async function initChart() {
  await nextTick()
  if (!chartRef.value || !window.echarts) return
  if (chartInst.value) {
    chartInst.value.clear()
    chartInst.value.dispose()
    chartInst.value = null
  }
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
  if (chartInst.value) {
    chartInst.value.clear()
    chartInst.value.dispose()
    chartInst.value = null
  }
})

watch([() => props.tenors10y, () => props.tenors2y], () => { initChart() }, { deep: true })
</script>
