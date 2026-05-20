<template>
  <div class="relative w-full h-full">
    <!-- Settings Button (Mobile) -->
    <button
      v-if="showSettingsButton"
      @click="openSettings"
      class="absolute top-2 right-2 z-10 p-2 rounded-lg bg-surface/80 backdrop-blur-sm
             border border-border-base hover:bg-surface transition-colors"
      aria-label="指标设置"
    >
      <svg class="w-5 h-5 text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    </button>
    
    <div ref="chartEl" class="w-full h-full"></div>
    
    <!-- Settings Bottom Sheet -->
    <BottomSheet v-model="showSettings" title="指标设置">
      <div class="p-4 space-y-4">
        <!-- MA Settings -->
        <div class="space-y-3">
          <h4 class="text-sm font-medium text-secondary">均线</h4>
          <div class="space-y-2">
            <label class="flex items-center justify-between p-2 rounded-lg bg-base/50">
              <span class="text-primary">MA5</span>
              <input type="checkbox" v-model="indicatorSettings.ma5" @change="handleSettingChange" />
            </label>
            <label class="flex items-center justify-between p-2 rounded-lg bg-base/50">
              <span class="text-primary">MA10</span>
              <input type="checkbox" v-model="indicatorSettings.ma10" @change="handleSettingChange" />
            </label>
            <label class="flex items-center justify-between p-2 rounded-lg bg-base/50">
              <span class="text-primary">MA20</span>
              <input type="checkbox" v-model="indicatorSettings.ma20" @change="handleSettingChange" />
            </label>
          </div>
        </div>
        
        <!-- Sub Chart Settings -->
        <div class="space-y-3">
          <h4 class="text-sm font-medium text-secondary">副图指标</h4>
          <div class="space-y-2">
            <label class="flex items-center justify-between p-2 rounded-lg bg-base/50">
              <span class="text-primary">VOL (成交量)</span>
              <input type="checkbox" v-model="indicatorSettings.vol" @change="handleSettingChange" />
            </label>
            <label class="flex items-center justify-between p-2 rounded-lg bg-base/50">
              <span class="text-primary">MACD</span>
              <input type="checkbox" v-model="indicatorSettings.macd" @change="handleSettingChange" />
            </label>
            <label class="flex items-center justify-between p-2 rounded-lg bg-base/50">
              <span class="text-primary">KDJ</span>
              <input type="checkbox" v-model="indicatorSettings.kdj" @change="handleSettingChange" />
            </label>
          </div>
        </div>
      </div>
    </BottomSheet>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount, onDeactivated, onActivated, nextTick, markRaw, reactive } from 'vue'
import { useDebounceFn, useThrottleFn } from '@vueuse/core'
import html2canvas from 'html2canvas'
import { UP, DOWN } from '../utils/indicators.js'
import { buildOverlaySeries } from '../utils/chartDataBuilder.js'
import { logger } from '../utils/logger.js'
import { initChart, getECharts, createResizeObserver } from '../utils/lazyEcharts.js'
import { waitForDimensions } from '../utils/waitForDimensions.js'
import { useTheme } from '../composables/useTheme.js'
import { useHaptic } from '../composables/useHaptic.js'
import BottomSheet from './BottomSheet.vue'
import { 
  getDynamicMarketColors,
  getDynamicChartColors,
  buildTooltipFormatter,
  buildGridOptions,
  buildDataZoomOptions
} from '../utils/echartsTheme.js'

const emit = defineEmits(['datazoom', 'settings-change'])

const props = defineProps({
  // 核心：由 chartDataBuilder 算好的所有图表数据
  chartData: { type: Object, required: true },

  // 布局控制：副图显示什么？例如 ['VOL'] 或 ['VOL', 'MACD']
  // 默认至少显示成交量
  subCharts: { type: Array, default: () => ['VOL'] },

  // 增量 tick (用于闪烁最新现价)
  tick: { type: Object, default: null },
  symbol: { type: String, default: '' },

  // 新闻事件标记点 [{ date, headline, type, price }]
  // type: 'bullish' | 'bearish' | 'neutral'
  newsEvents: { type: Array, default: () => [] },
  
  // 是否显示设置按钮（移动端）
  showSettingsButton: { type: Boolean, default: false },
})

const chartEl = ref(null)
let chart = null
let _ro = null
let _lastChartData = null
let _isInitialized = false
let _unsubscribeTheme = null

const { activeTheme, onThemeChange } = useTheme()
const { light, success } = useHaptic()

// Settings state
const showSettings = ref(false)
const indicatorSettings = reactive({
  ma5: true,
  ma10: true,
  ma20: true,
  vol: true,
  macd: false,
  kdj: false,
})

function openSettings() {
  light()
  showSettings.value = true
}

function handleSettingChange() {
  light()
  emit('settings-change', { ...indicatorSettings })
}

function buildOption(cData) {
  if (!cData || cData.isEmpty) return {}

  const MARKET_COLORS = getDynamicMarketColors()
  const CHART_COLORS = getDynamicChartColors()

  const {
    times, klineData, volumes,
    maData, bollData, subChartData,
    overlaySeriesData, overlayYAxis, yMin, yMax
  } = cData

  const subCount = props.subCharts.length  // 1(只有VOL) 或 2(VOL+指标)

  // ── 1. 动态计算 Grid / XAxis / YAxis ──
  const grids  = []
  const xAxes  = []
  const yAxes  = []

  // 主图 Grid (Index 0)
  const mainHeight = subCount === 2 ? '55%' : '65%'
  grids.push(buildGridOptions({ top: 10, height: mainHeight, left: 55, right: 8 }))
  xAxes.push({
    type: 'category', data: times, gridIndex: 0,
    axisLabel: { show: false },
    axisLine: { lineStyle: { color: CHART_COLORS.AXIS_LINE } },
  })
  yAxes.push({
    type: 'value', gridIndex: 0, scale: true,
    min: yMin, max: yMax,
    splitLine: { lineStyle: { color: CHART_COLORS.SPLIT_LINE, type: 'dashed' } },
    axisLabel: { color: CHART_COLORS.AXIS_LABEL, fontSize: 10 },
  })

  // 动态生成副图 Grids
  let currentTop = subCount === 2 ? 60 : 70
  const subHeight = subCount === 2 ? '15%' : '20%'

  props.subCharts.forEach((subName, index) => {
    const gridIdx = index + 1
    grids.push(buildGridOptions({ top: `${currentTop}%`, height: subHeight, left: 55, right: 8 }))
    xAxes.push({
      type: 'category', data: times, gridIndex: gridIdx,
      axisLabel: { show: index === subCount - 1, color: CHART_COLORS.AXIS_LABEL, fontSize: 10 },
      axisLine: { lineStyle: { color: CHART_COLORS.AXIS_LINE } },
    })
    yAxes.push({
      type: 'value', gridIndex: gridIdx,
      splitLine: { show: false },
      axisLabel: {
        color: CHART_COLORS.AXIS_LABEL, fontSize: 10,
        formatter: subName === 'VOL' ? (v) => {
          if (v >= 1e8) return (v / 1e8).toFixed(0) + '亿'
          if (v >= 1e4) return (v / 1e4).toFixed(0) + '万'
          return v
        } : undefined,
      },
    })
    if (subCount === 2) currentTop += 18
  })

  // ── 2. 组装 Series ──
  const series = []

  // 主图：K线 (TradingView-style colors)
  series.push({
    name: 'K线', type: 'candlestick', data: klineData, sampling: 'lttb',
    xAxisIndex: 0, yAxisIndex: 0,
    itemStyle: {
      color: MARKET_COLORS.UP,
      color0: MARKET_COLORS.DOWN,
      borderColor: MARKET_COLORS.UP,
      borderColor0: MARKET_COLORS.DOWN,
    },
    barMaxWidth: 8,
    // 新闻事件标记点
    markPoint: props.newsEvents.length > 0 ? {
      symbol: 'diamond',
      symbolSize: 10,
      data: props.newsEvents.map(e => ({
        coord: [e.date, e.price],
        value: e.headline,
        itemStyle: {
          color: e.type === 'bullish' ? MARKET_COLORS.UP : e.type === 'bearish' ? MARKET_COLORS.DOWN : '#fbbf24',
          borderColor: e.type === 'bullish' ? MARKET_COLORS.UP : e.type === 'bearish' ? MARKET_COLORS.DOWN : '#fbbf24',
          borderWidth: 1,
        },
        label: {
          show: false, // 不在图表上显示标签，hover tooltip 显示
        },
      })),
      label: { show: false },
      emphasis: {
        itemStyle: {
          shadowBlur: 10,
          shadowColor: 'rgba(0, 0, 0, 0.5)',
        },
      },
    } : undefined,
  })

  // 主图：均线
  if (maData?.ma5) {
    series.push(
      {
        name: 'MA5', type: 'line', data: maData.ma5, sampling: 'lttb',
        xAxisIndex: 0, yAxisIndex: 0, symbol: 'none',
        lineStyle: { color: MARKET_COLORS.MA5, width: 1 },
      },
      {
        name: 'MA10', type: 'line', data: maData.ma10, sampling: 'lttb',
        xAxisIndex: 0, yAxisIndex: 0, symbol: 'none',
        lineStyle: { color: MARKET_COLORS.MA10, width: 1 },
      },
      {
        name: 'MA20', type: 'line', data: maData.ma20, sampling: 'lttb',
        xAxisIndex: 0, yAxisIndex: 0, symbol: 'none',
        lineStyle: { color: MARKET_COLORS.MA20, width: 1 },
      }
    )

    // 叠加标的系列（使用 buildOverlaySeries 规范化注入 + 右侧双轴）
    const { series: ovSeries, hasOverlay } = buildOverlaySeries(
      props.chartData,
      overlaySeriesData ?? [],
      MARKET_COLORS.OVERLAY
    )

    if (hasOverlay && ovSeries.length > 0) {
      yAxes.push({
        type: 'value', gridIndex: 0, position: 'right',
        splitLine: { show: false },
        axisLine: { show: true, lineStyle: { color: CHART_COLORS.AXIS_LINE } },
        axisLabel: { show: true, fontSize: 10, color: MARKET_COLORS.OVERLAY },
      })
      series.push(...ovSeries)
    }
  }

  // 副图 Series 分配
  props.subCharts.forEach((subName, index) => {
    const axisIdx = index + 1

    if (subName === 'VOL') {
      series.push({
        name: 'VOL', type: 'bar', data: volumes,
        xAxisIndex: axisIdx, yAxisIndex: axisIdx, barMaxWidth: 8,
      })
      // OI（持仓量）：有 oi 字段时画成折线叠加在 VOL 区域
      const oiData = volumes.map((v) => ({ value: v.oi, itemStyle: { color: MARKET_COLORS.OI } }))
      if (oiData.some(v => v.value != null)) {
        series.push({
          name: 'OI', type: 'line', data: oiData, sampling: 'lttb',
          xAxisIndex: axisIdx, yAxisIndex: axisIdx,
          smooth: false, symbol: 'none',
          lineStyle: { color: MARKET_COLORS.OI, width: 1.5 },
          tooltip: { formatter: p => `持仓量: ${p.value?.toLocaleString() ?? '-'}` },
        })
      }

    } else if (subName === 'D_OI') {
      // ΔOI 持仓变化柱（多空资金流向）
      const doiData = volumes.map((v) => {
        const d = v.deltaOI
        if (d == null) return { value: null }
        const isUp = v.priceUp
        let color = MARKET_COLORS.DELTA_OI_FLAT
        if (d > 0 && isUp)  color = MARKET_COLORS.DELTA_OI_UP
        else if (d > 0 && !isUp) color = MARKET_COLORS.DELTA_OI_DOWN
        return { value: d, itemStyle: { color } }
      })
      series.push({
        name: 'ΔOI', type: 'bar', data: doiData,
        xAxisIndex: axisIdx, yAxisIndex: axisIdx, barMaxWidth: 6,
        tooltip: {
          formatter: p => {
            const v = p.value
            if (v == null) return 'ΔOI: -'
            const sign = v >= 0 ? '+' : ''
            return `ΔOI: ${sign}${v.toLocaleString()}`
          }
        },
      })

    } else if (subName === 'MACD' && subChartData?.MACD) {
      const m = subChartData.MACD
      series.push(
        {
          name: 'DIF', type: 'line', data: m.dif, sampling: 'lttb',
          xAxisIndex: axisIdx, yAxisIndex: axisIdx, symbol: 'none',
          lineStyle: { color: MARKET_COLORS.DIF, width: 1 },
        },
        {
          name: 'DEA', type: 'line', data: m.dea, sampling: 'lttb',
          xAxisIndex: axisIdx, yAxisIndex: axisIdx, symbol: 'none',
          lineStyle: { color: MARKET_COLORS.DEA, width: 1 },
        },
        {
          name: 'MACD', type: 'bar',
          data: m.macd.map(v => ({
            value: Math.abs(v),
            itemStyle: { color: v >= 0 ? MARKET_COLORS.MACD_UP : MARKET_COLORS.MACD_DOWN },
          })),
          xAxisIndex: axisIdx, yAxisIndex: axisIdx,
        }
      )

    } else if (subName === 'KDJ' && subChartData?.KDJ) {
      const k = subChartData.KDJ
      series.push(
        {
          name: 'K', type: 'line', data: k.k, sampling: 'lttb',
          xAxisIndex: axisIdx, yAxisIndex: axisIdx, symbol: 'none',
          lineStyle: { color: MARKET_COLORS.MA5, width: 1 },
        },
        {
          name: 'D', type: 'line', data: k.d, sampling: 'lttb',
          xAxisIndex: axisIdx, yAxisIndex: axisIdx, symbol: 'none',
          lineStyle: { color: MARKET_COLORS.MA10, width: 1 },
        },
        {
          name: 'J', type: 'line', data: k.j, sampling: 'lttb',
          xAxisIndex: axisIdx, yAxisIndex: axisIdx, symbol: 'none',
          lineStyle: { color: MARKET_COLORS.MA20, width: 1 },
        }
      )

    } else if (subName === 'RSI' && subChartData?.RSI) {
      series.push({
        name: 'RSI', type: 'line', data: subChartData.RSI, sampling: 'lttb',
        xAxisIndex: axisIdx, yAxisIndex: axisIdx, symbol: 'none',
        lineStyle: { color: MARKET_COLORS.DIF, width: 1 },
      })
    }
  })

  // ── 3. DataZoom / Tooltip ──
  const allGridIndices = xAxes.map((_, i) => i)

  return {
    backgroundColor: 'transparent',
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { 
        type: 'cross', 
        crossStyle: { color: CHART_COLORS.CROSSHAIR, type: 'dashed' },
        lineStyle: { color: CHART_COLORS.CROSSHAIR, type: 'dashed' }
      },
      backgroundColor: CHART_COLORS.TOOLTIP_BG,
      borderColor: CHART_COLORS.TOOLTIP_BORDER,
      borderWidth: 1,
      padding: [8, 12],
      textStyle: { 
        color: CHART_COLORS.TOOLTIP_TEXT, 
        fontSize: 11,
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace'
      },
      extraCssText: 'backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px); border-radius: 6px;',
      formatter: (params) => buildTooltipFormatter(params, { showVolume: true, showOverlay: true, newsEvents: props.newsEvents }),
    },
    legend: { show: false },
    grid: grids,
    xAxis: xAxes,
    yAxis: yAxes,
    series,
    dataZoom: buildDataZoomOptions(allGridIndices),
  }
}

// ── Tick 增量更新（patch 最后根 K 线） ───────────────────────────
// v0.6.62: 增量渲染优化 - appendData + replaceMerge 双模式
let _lastTickTime = 0
const TICK_APPEND_THRESHOLD = 500  // 500ms 内使用 appendData，超过则 replaceMerge

function applyTickFast(cData, tick) {
  if (!chart || !tick || !tick.price) return
  if (chart.isDisposed()) return
  const last = cData.klineData[cData.klineData.length - 1]
  if (!last) return

  // 更新本地数据引用（用于后续计算）
  const [o, , l, h] = last
  last[1] = tick.price
  last[2] = Math.min(l, tick.price)
  last[3] = Math.max(h, tick.price)

  // v0.6.62: 智能增量渲染策略
  const now = Date.now()
  const timeSinceLastTick = now - _lastTickTime
  _lastTickTime = now

  // 高频更新（< 500ms）：使用 appendData 避免全量重绘
  // 注意：appendData 只适用于追加新数据点，不适用于修改现有数据
  // 对于实时 tick 更新最后一根 K 线，仍需使用 replaceMerge
  // 但我们可以优化 replaceMerge 的使用频率
  
  // 使用 replaceMerge 进行增量更新，避免全量重绘
  // markRaw 防止 Vue 对 option 对象做深度响应式追踪
  chart.setOption(
    markRaw({ series: [{ name: 'K线', data: cData.klineData }] }),
    { replaceMerge: ['series'], lazyUpdate: true }
  )
  
  // 同时更新成交量（如果有）
  if (tick.volume && cData.volumes && cData.volumes.length > 0) {
    const lastVol = cData.volumes[cData.volumes.length - 1]
    if (lastVol) {
      lastVol.value = tick.volume
      chart.setOption(
        markRaw({ series: [{ name: 'VOL', data: cData.volumes }] }),
        { replaceMerge: ['series'], lazyUpdate: true }
      )
    }
  }
}

// ── 生命周期 ────────────────────────────────────────────────────
onMounted(async () => {
  if (!chartEl.value) return

  await nextTick()

  // Wait for container dimensions with timeout recovery
  const dimResult = await waitForDimensions(chartEl.value, 1000)
  if (!dimResult.success) {
    logger.warn('[BaseKLineChart] Container dimensions timeout, aborting init')
    return
  }

  try {
    const width = dimResult.width
    const height = dimResult.height
    logger.debug(`[ECharts] 🔧 init ${props.symbol} @ ${width.toFixed(0)}×${height.toFixed(0)}`)

    chart = markRaw(await initChart(chartEl.value, 'dark'))
    _isInitialized = true
    _lastChartData = props.chartData

    if (props.chartData && !props.chartData.isEmpty) {
      chart.setOption(markRaw(buildOption(props.chartData)))
    }

    chart.on('datazoom', () => {
      const zr = chart.getOption()?.dataZoom?.[0]
      if (zr) emit('datazoom', { start: zr.start ?? 0, end: zr.end ?? 100 })
    })

    // ResizeObserver for resize only (not init)
    _ro = createResizeObserver(chart)
    _ro.observe(chartEl.value)

  } catch (e) {
    console.error('[BaseKLineChart] Initialization failed:', e)
  }
})

onBeforeUnmount(() => {
  if (chart && !chart.isDisposed()) {
    chart.off('datazoom')
  }
  _ro?.disconnect()
  _unsubscribeTheme?.()
  _isInitialized = false
  if (chart) {
    logger.debug(`[ECharts] 🗑️  disposed instance for: ${props.symbol}`)
    chart.dispose()
    chart = null
  }
})

onDeactivated(() => {
  // 1. Remove ECharts event listeners
  if (chart && !chart.isDisposed()) {
    chart.off('datazoom')
    chart.off('finished')
  }
  
  // 2. Disconnect ResizeObserver
  if (_ro) {
    _ro.disconnect()
  }
  
  // 3. Cancel theme subscription
  if (_unsubscribeTheme) {
    _unsubscribeTheme()
  }
  
  // 4. Mark as deactivated (but don't dispose chart - it may be reactivated)
  _isInitialized = false
})

onActivated(() => {
  // Re-initialize ResizeObserver and theme subscription when reactivated
  if (chartEl.value && chart && !chart.isDisposed()) {
    // Reconnect ResizeObserver
    if (_ro) {
      _ro.observe(chartEl.value)
    }
    
    // Resize chart to fit container
    chart.resize()
    
    _isInitialized = true
  }
})

function updateChartTheme() {
  if (!chart || !_lastChartData || _lastChartData.isEmpty) return
  const newOption = buildOption(_lastChartData)
  chart.setOption(markRaw(newOption), { notMerge: false })
  logger.debug(`[BaseKLineChart] Theme updated to: ${activeTheme.value}`)
}

_unsubscribeTheme = onThemeChange(() => {
  updateChartTheme()
})

// 核心 watcher：chartData 或 subCharts 变化时合并更新（节流 200ms）
const debouncedUpdateChart = useDebounceFn(() => {
  if (!chart || !props.chartData || props.chartData.isEmpty) return
  if (chart.isDisposed()) return
  _lastChartData = props.chartData
  chart.setOption(markRaw(buildOption(props.chartData)), { notMerge: false })
}, 200)

watch([() => props.chartData, () => props.subCharts], () => { debouncedUpdateChart() })

// tick watcher：增量 patch 最后根 K 线
const throttledApplyTick = useThrottleFn((data, tick) => {
  if (!chart || !data || data.isEmpty) return
  applyTickFast(data, tick)
}, 100)

watch(() => props.tick, (t) => {
  throttledApplyTick(_lastChartData, t)
})

defineExpose({ 
  getChartInstance: () => chart,
  exportChart: async () => {
    if (!chartEl.value || !chart) return
    try {
      // Wait for chart to finish rendering with timeout fallback
      await new Promise(resolve => {
        const timeout = setTimeout(() => {
          chart.off('finished')
          resolve()
        }, 200) // Timeout fallback in case 'finished' doesn't fire
        
        chart.on('finished', () => {
          clearTimeout(timeout)
          chart.off('finished')
          resolve()
        })
        
        // If chart is already rendered, resolve immediately
        if (chart.isDisposed()) {
          clearTimeout(timeout)
          resolve()
        }
      })
      
      const canvas = await html2canvas(chartEl.value, {
        backgroundColor: '#0f172a',
        scale: 2,
        useCORS: true,
        allowTaint: true
      })
      const link = document.createElement('a')
      link.download = `chart_${props.symbol || 'unknown'}_${new Date().toISOString().slice(0,10)}.png`
      link.href = canvas.toDataURL('image/png')
      link.click()
    } catch (e) {
      console.error('[BaseKLineChart] Export failed:', e)
      alert('图表导出失败: ' + e.message)
    }
  }
})
</script>
