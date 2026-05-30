<template>
  <div class="w-full h-full relative flex flex-col" style="min-height: 120px">
    <!-- 顶部标签 -->
    <div class="shrink-0 flex items-center gap-3 px-1 py-1 border-b border-theme bg-terminal-bg/60">
      <span class="text-[10px] font-mono text-terminal-dim">📐 期限利差 (10Y-3Y)</span>
      <span
        class="text-[10px] font-mono font-medium"
        :class="spread >= 0 ? 'text-[var(--color-info)]' : 'text-bullish'"
      >{{ spread >= 0 ? '+' : '' }}{{ spread?.toFixed(1) ?? '--' }}bp</span>
      <span
        v-if="spread != null"
        class="text-[10px] px-1 py-0.5 rounded-sm border text-[10px]"
        :class="spread >= 0 ? 'border-[var(--color-info-border)] text-[var(--color-info)]/70' : 'border-[var(--color-danger-border)] text-bullish/70'"
      >{{ spread >= 0 ? '正常' : '倒挂⚠️' }}</span>
      <div class="flex-1" />
      <span class="text-[10px] text-terminal-dim">{{ updateTime || '...' }}</span>
    </div>

    <!-- 错误 / 加载 / 空 -->
    <div v-if="hasError" class="flex-1 flex items-center justify-center">
      <span class="text-bullish text-xs">{{ errorMsg }}</span>
    </div>
    <div v-else-if="isLoading" class="flex-1 flex flex-col p-3 gap-2">
      <div class="skeleton h-3 w-24 rounded-sm"></div>
      <div class="flex-1 skeleton rounded-sm"></div>
      <div class="flex gap-2">
        <div class="skeleton h-2 w-12 rounded-sm"></div>
        <div class="skeleton h-2 w-12 rounded-sm"></div>
      </div>
    </div>
    <div v-else-if="!hasData" class="flex-1 flex items-center justify-center">
      <span class="text-terminal-dim text-xs">暂无利差数据</span>
    </div>
    <div v-else ref="chartRef" class="flex-1 min-h-0"></div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, onActivated, onDeactivated, nextTick } from 'vue'
import { createResizeObserver } from '../utils/lazyEcharts.js'
import { safeDispose } from '../utils/chartManager.js'
import { getDynamicThemeColors, getDynamicMarketColors } from '../utils/echartsTheme.js'

const props = defineProps({
  tenors10y: { type: Object, default: null },   // {date, yield}[]
  tenors3y:  { type: Object, default: null },   // {date, yield}[]
  updateTime: { type: String, default: '' },
  isLoading:  { type: Boolean, default: false },
  hasError:   { type: Boolean, default: false },
  errorMsg:   { type: String, default: '' },
})

const chartRef  = ref(null)
const chartInst = ref(null)
let resizeObserver = null  // v0.6.70: Fix - store ResizeObserver directly

// 计算 10Y-3Y 差值序列
const spreadData = computed(() => {
  const s10 = props.tenors10y || []
  const s3  = props.tenors3y  || []
  const map3 = {}
  for (const d of s3) map3[d.date] = d.yield
  return s10
    .filter(d => map3[d.date] != null)
    .map(d => ({
      date:   d.date,
      spread: (d.yield - map3[d.date]) * 10000, // 转换为 bp
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
  if (!data || data.length === 0) return null

  const colors = getDynamicThemeColors()

  const dates = data.map(d => d.date)
  const values = data.map(d => d.spread)

  // Guard against empty arrays
  if (values.length === 0) return null

  // Filter out NaN and Infinity values
  const validValues = values.filter(v => typeof v === 'number' && isFinite(v))
  if (validValues.length === 0) return null  // Don't render chart if no valid data

  const minV = Math.min(...validValues)
  const maxV = Math.max(...validValues)
  const pad  = (maxV - minV) * 0.2 || 10

  return {
    backgroundColor: 'transparent',
    animation: false,
    grid: { top: 8, right: 14, bottom: 28, left: 52 },
    xAxis: {
      type: 'category', data: dates,
      axisLine: { lineStyle: { color: colors.grid } },
      axisTick: { show: false },
      axisLabel: {
        color: colors.textMuted, fontSize: 8, fontFamily: 'monospace',
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
      axisLabel: { color: colors.textMuted, fontSize: 9, fontFamily: 'monospace', formatter: v => v.toFixed(0) + 'bp' },
      splitLine: { lineStyle: { color: colors.grid, type: 'dashed' } },
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: colors.tooltipBg,
      borderColor: colors.tooltipBorder,
      textStyle: { color: colors.tooltipText, fontSize: 11, fontFamily: 'monospace' },
      formatter: (params) => {
        const p = params[0]
        const v = p.value
        const sign = v >= 0 ? '+' : ''
        const color = v >= 0 ? colors.info : colors.error
        return `<span style="color:${colors.info};font-family:monospace">${p.name}</span><br/>`
          + `<span style="color:${color}">利差: ${sign}${v.toFixed(1)} bp</span>`
      },
    },
    series: [
      {
        type: 'bar',
        data: values.map(v => ({
          value: v,
          itemStyle: { color: v >= 0 ? colors.info + 'b3' : colors.error + 'b3' },
        })),
        barMaxWidth: 8,
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { color: colors.textMuted, width: 1, type: 'dashed' },
          data: [{ yAxis: 0 }],
          label: { formatter: '0bp', color: colors.textMuted, fontSize: 8, fontFamily: 'monospace' },
        },
      },
    ],
  }
}

async function initChart() {
  await nextTick()
  if (!chartRef.value || !window.echarts) return
  
  const option = buildOption()
  if (!option) return // Don't render if no data
  
  // Only init if no existing instance or disposed
  if (!chartInst.value || chartInst.value.isDisposed()) {
    chartInst.value = window.echarts.init(chartRef.value, null, { renderer: 'canvas' })
    chartInst.value.setOption(option)
  } else {
    // Update existing instance with notMerge for clean replacement
    chartInst.value.setOption(option, true)
  }
}

onMounted(async () => {
  await initChart()
  // v0.6.70: Fix - Only create ResizeObserver after chart is initialized
  if (chartRef.value && chartInst.value && !chartInst.value.isDisposed()) {
    const { observer } = createResizeObserver(chartInst.value)
    resizeObserver = observer
    resizeObserver.observe(chartRef.value)
  }
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
  if (chartInst.value && !chartInst.value.isDisposed()) {
    chartInst.value.dispose()
    chartInst.value = null
  }
})

// v0.6.70: KeepAlive lifecycle - prevent white screen on tab switch
onDeactivated(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
  if (chartInst.value && !chartInst.value.isDisposed()) {
    chartInst.value.clear()
  }
})

onActivated(async () => {
  await nextTick()
  if (chartRef.value && chartInst.value && !chartInst.value.isDisposed()) {
    const { observer } = createResizeObserver(chartInst.value)
    resizeObserver = observer
    resizeObserver.observe(chartRef.value)
    window.dispatchEvent(new Event('resize'))
  }
})

watch([() => props.tenors10y, () => props.tenors3y], () => { initChart() }, { deep: true })
</script>
