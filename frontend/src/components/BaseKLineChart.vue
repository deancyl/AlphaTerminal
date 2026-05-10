<template>
  <div ref="chartEl" class="w-full h-full"></div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount, nextTick, markRaw } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import html2canvas from 'html2canvas'
import { UP, DOWN } from '../utils/indicators.js'
import { buildOverlaySeries } from '../utils/chartDataBuilder.js'
import { logger } from '../utils/logger.js'
import { initChart, getECharts } from '../utils/lazyEcharts.js'



const emit = defineEmits(['datazoom'])

const props = defineProps({
  // 核心：由 chartDataBuilder 算好的所有图表数据
  chartData: { type: Object, required: true },

  // 布局控制：副图显示什么？例如 ['VOL'] 或 ['VOL', 'MACD']
  // 默认至少显示成交量
  subCharts: { type: Array, default: () => ['VOL'] },

  // 增量 tick (用于闪烁最新现价)
  tick: { type: Object, default: null },
  symbol: { type: String, default: '' },
})

const chartEl = ref(null)
let chart = null
let _ro = null
let _lastChartData = null   // 保留引用用于 tick patch
let _isInitialized = false  // 初始化完成标记

// ── 动态构建 ECharts Option ──────────────────────────────────────
function buildOption(cData) {
  if (!cData || cData.isEmpty) return {}

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
  grids.push({ top: 10, height: mainHeight, left: 55, right: 8 })
  xAxes.push({
    type: 'category', data: times, gridIndex: 0,
    axisLabel: { show: false },
    axisLine: { lineStyle: { color: '#374151' } },
  })
  yAxes.push({
    type: 'value', gridIndex: 0, scale: true,
    min: yMin, max: yMax,
    splitLine: { lineStyle: { color: '#1f2937' } },
    axisLabel: { color: '#6b7280', fontSize: 9 },
  })

  // 动态生成副图 Grids
  let currentTop = subCount === 2 ? 60 : 70
  const subHeight = subCount === 2 ? '15%' : '20%'

  props.subCharts.forEach((subName, index) => {
    const gridIdx = index + 1
    grids.push({ top: `${currentTop}%`, height: subHeight, left: 55, right: 8 })
    xAxes.push({
      type: 'category', data: times, gridIndex: gridIdx,
      axisLabel: { show: index === subCount - 1 },  // 只有最下面一个副图显示X轴日期
      axisLine: { lineStyle: { color: '#374151' } },
    })
    yAxes.push({
      type: 'value', gridIndex: gridIdx,
      splitLine: { show: false },
      axisLabel: {
        color: '#6b7280', fontSize: 9,
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

  // 主图：K线
  series.push({
    name: 'K线', type: 'candlestick', data: klineData,
    xAxisIndex: 0, yAxisIndex: 0,
    itemStyle: {
      color: '#ef232a', color0: '#14b143',
      borderColor: '#ef232a', borderColor0: '#14b143',
    },
    barMaxWidth: 8,
  })

  // 主图：均线
  if (maData?.ma5) {
    series.push(
      {
        name: 'MA5', type: 'line', data: maData.ma5,
        xAxisIndex: 0, yAxisIndex: 0, symbol: 'none',
        lineStyle: { color: '#ffffff', width: 1 },
      },
      {
        name: 'MA10', type: 'line', data: maData.ma10,
        xAxisIndex: 0, yAxisIndex: 0, symbol: 'none',
        lineStyle: { color: '#fbbf24', width: 1 },
      },
      {
        name: 'MA20', type: 'line', data: maData.ma20,
        xAxisIndex: 0, yAxisIndex: 0, symbol: 'none',
        lineStyle: { color: '#c084fc', width: 1 },
      }
    )

    // 叠加标的系列（使用 buildOverlaySeries 规范化注入 + 右侧双轴）
    const { series: ovSeries, hasOverlay } = buildOverlaySeries(
      props.chartData,
      overlaySeriesData ?? [],
      '#f97316'   // 亮橙色高辨识度
    )

    if (hasOverlay && ovSeries.length > 0) {
      yAxes.push({
        type: 'value', gridIndex: 0, position: 'right',
        splitLine: { show: false },          // 防止副轴网格干扰主图
        axisLine: { show: true, lineStyle: { color: '#6b7280' } },
        axisLabel: { show: true, fontSize: 9, color: '#f97316' },
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
      const oiData = volumes.map((v) => ({ value: v.oi, itemStyle: { color: '#f59e0b' } }))
      if (oiData.some(v => v.value != null)) {
        series.push({
          name: 'OI', type: 'line', data: oiData,
          xAxisIndex: axisIdx, yAxisIndex: axisIdx,
          smooth: false, symbol: 'none',
          lineStyle: { color: '#f59e0b', width: 1.5 },
          tooltip: { formatter: p => `持仓量: ${p.value?.toLocaleString() ?? '-'}` },
        })
      }

    } else if (subName === 'D_OI') {
      // ΔOI 持仓变化柱（多空资金流向）
      // 逻辑：涨+增仓→红(多头进攻) 跌+增仓→绿(空头进攻) 减仓→灰
      const doiData = volumes.map((v) => {
        const d = v.deltaOI
        if (d == null) return { value: null }
        const isUp = v.priceUp
        let color = '#6b7280'  // 减仓灰
        if (d > 0 && isUp)  color = UP       // 涨增仓 → 多头红
        else if (d > 0 && !isUp) color = DOWN // 跌增仓 → 空头绿
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
          name: 'DIF', type: 'line', data: m.dif,
          xAxisIndex: axisIdx, yAxisIndex: axisIdx, symbol: 'none',
          lineStyle: { color: '#60a5fa', width: 1 },
        },
        {
          name: 'DEA', type: 'line', data: m.dea,
          xAxisIndex: axisIdx, yAxisIndex: axisIdx, symbol: 'none',
          lineStyle: { color: '#f87171', width: 1 },
        },
        {
          name: 'MACD', type: 'bar',
          data: m.macd.map(v => ({
            value: Math.abs(v),
            itemStyle: { color: v >= 0 ? '#ef232a' : '#14b143' },
          })),
          xAxisIndex: axisIdx, yAxisIndex: axisIdx,
        }
      )

    } else if (subName === 'KDJ' && subChartData?.KDJ) {
      const k = subChartData.KDJ
      series.push(
        {
          name: 'K', type: 'line', data: k.k,
          xAxisIndex: axisIdx, yAxisIndex: axisIdx, symbol: 'none',
          lineStyle: { color: '#ffffff', width: 1 },
        },
        {
          name: 'D', type: 'line', data: k.d,
          xAxisIndex: axisIdx, yAxisIndex: axisIdx, symbol: 'none',
          lineStyle: { color: '#fbbf24', width: 1 },
        },
        {
          name: 'J', type: 'line', data: k.j,
          xAxisIndex: axisIdx, yAxisIndex: axisIdx, symbol: 'none',
          lineStyle: { color: '#c084fc', width: 1 },
        }
      )

    } else if (subName === 'RSI' && subChartData?.RSI) {
      series.push({
        name: 'RSI', type: 'line', data: subChartData.RSI,
        xAxisIndex: axisIdx, yAxisIndex: axisIdx, symbol: 'none',
        lineStyle: { color: '#60a5fa', width: 1 },
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
      axisPointer: { type: 'cross', crossStyle: { color: '#555' } },
      backgroundColor: '#1e2130', borderColor: '#374151',
      textStyle: { color: '#d1d5db', fontSize: 11 },
      // 高阶混排 formatter：同时展示 K 线 OHLCV + 对比线数值
      formatter(params) {
        if (!Array.isArray(params) || !params.length) return ''
        const kp = params.find(p => p.seriesType === 'candlestick')
        if (!kp) return ''
        const vals = kp.data
        if (!vals) return ''
        const [o, c, l, hi] = vals
        const isUp  = c >= o
        const color = isUp ? UP : DOWN
        const sign  = isUp ? '+' : ''
        const chgPct = o > 0 ? ((c - o) / o * 100).toFixed(2) : '0.00'
        const chgAbs = (c - o).toFixed(2)
        let html = `<span style="color:#94a3b8;font-size:10px">${kp.axisValue}</span><br/>`
        html += `<span style="color:${color}">开 ${o?.toFixed(2)}</span> &nbsp; `
        html += `<span style="color:${color}">收 ${c?.toFixed(2)}</span> &nbsp; `
        html += `<span style="color:${color}">涨跌 ${sign}${chgAbs} (${sign}${chgPct}%)</span><br/>`
        html += `<span style="color:#6b7280">低 ${l?.toFixed(2)}</span> &nbsp; `
        html += `<span style="color:#6b7280">高 ${hi?.toFixed(2)}</span>`
        const OV_COLOR = '#f97316'
        const ovParams = params.filter(p => p.seriesType === 'line' && p.seriesName === '对比')
        ovParams.forEach(p => {
          const rawVal = p.value?.[1]
          if (rawVal != null) {
            html += `<br/><span style="color:${OV_COLOR}">➟ 对比 ${p.value[1]?.toFixed(4)}</span>`
          }
        })
        return html
      },
    },
    legend: { show: false },
    grid: grids,
    xAxis: xAxes,
    yAxis: yAxes,
    series,
    dataZoom: [
      { type: 'inside', xAxisIndex: allGridIndices, start: 70, end: 100 },
      {
        type: 'slider', xAxisIndex: allGridIndices,
        bottom: 0, height: 16,
        borderColor: '#374151', fillerColor: 'rgba(96,165,250,0.1)',
        handleStyle: { color: '#60a5fa' },
        textStyle: { color: '#6b7280', fontSize: 9 },
      },
    ],
  }
}

// ── Tick 增量更新（patch 最后根 K 线） ───────────────────────────
function applyTickFast(cData, tick) {
  if (!chart || !tick || !tick.price) return
  const last = cData.klineData[cData.klineData.length - 1]
  if (!last) return
  const [o, , l, h] = last
  last[1] = tick.price
  last[2] = Math.min(l, tick.price)
  last[3] = Math.max(h, tick.price)
  chart.setOption(
    { series: [{ name: 'K线', data: cData.klineData }] },
    false  // notMerge=false: 只合并K线series，不影响其他
  )
}

// ── 生命周期 ────────────────────────────────────────────────────
onMounted(async () => {
  if (!chartEl.value) return

  await nextTick()

  // Wait for container dimensions with timeout
  const startTime = performance.now()
  while (chartEl.value && (chartEl.value.clientWidth === 0 || chartEl.value.clientHeight === 0)) {
    if (performance.now() - startTime > 1000) {
      console.error('[BaseKLineChart] Container has zero dimensions after 1s')
      return
    }
    await new Promise(r => requestAnimationFrame(r))
  }

  try {
    const width = chartEl.value.clientWidth
    const height = chartEl.value.clientHeight
    logger.debug(`[ECharts] 🔧 init ${props.symbol} @ ${width.toFixed(0)}×${height.toFixed(0)}`)

    chart = markRaw(await initChart(chartEl.value, 'dark'))
    _isInitialized = true
    _lastChartData = props.chartData

    if (props.chartData && !props.chartData.isEmpty) {
      chart.setOption(buildOption(props.chartData))
    }

    chart.on('datazoom', () => {
      const zr = chart.getOption()?.dataZoom?.[0]
      if (zr) emit('datazoom', { start: zr.start ?? 0, end: zr.end ?? 100 })
    })

    // ResizeObserver for resize only (not init)
    _ro = new ResizeObserver(() => {
      if (!_isInitialized || !chart) return
      chart.resize()
    })
    _ro.observe(chartEl.value)

  } catch (e) {
    console.error('[BaseKLineChart] Initialization failed:', e)
  }
})

onBeforeUnmount(() => {
  _ro?.disconnect()
  _isInitialized = false
  if (chart) {
    logger.debug(`[ECharts] 🗑️  disposed instance for: ${props.symbol}`)
    chart.dispose()
    chart = null
  }
})

// 核心 watcher：chartData 或 subCharts 变化时合并更新（节流 200ms）
const debouncedUpdateChart = useDebounceFn(() => {
  if (!chart || !props.chartData || props.chartData.isEmpty) return
  _lastChartData = props.chartData
  chart.setOption(buildOption(props.chartData), { notMerge: false })
}, 200)

watch([() => props.chartData, () => props.subCharts], () => { debouncedUpdateChart() })

// tick watcher：增量 patch 最后根 K 线
watch(() => props.tick, (t) => {
  if (!chart || !_lastChartData || _lastChartData.isEmpty) return
  applyTickFast(_lastChartData, t)
})

defineExpose({ 
  getChartInstance: () => chart,
  exportChart: async () => {
    if (!chartEl.value) return
    try {
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
