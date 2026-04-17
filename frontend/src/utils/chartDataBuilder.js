// frontend/src/utils/chartDataBuilder.js
import { calcMA, calcBOLL, calcMACD, calcKDJ, calcRSI, calcOBV, calcDMI, calcCCI } from './indicators.js'
import { buildXAxisLabels } from './symbols.js'
import { UP, DOWN } from './indicators.js'

/**
 * 将原始 K 线数据转换为图表渲染所需的全套结构化数据
 * @param {Array} rawHist - 原始历史数据 [{date, open, close, high, low, volume, ...}]
 * @param {String} period - 当前周期 (daily, 1min, etc.)
 * @param {Object} indicatorParams - 指标参数配置 { MACD: { fast: 12, slow: 26, signal: 9 }, BOLL: {...}, ... }
 * @param {Array} overlayData - (可选) 叠加标的的数据
 * @returns {Object} 结构化图表数据
 */
export function buildChartData(rawHist, period, indicatorParams = {}, overlayData = []) {
  if (!rawHist || !rawHist.length) {
    return { isEmpty: true }
  }

  // 1. 基础 X 轴与 K线序列
  const times = buildXAxisLabels(rawHist, period)
  const closes = rawHist.map(h => h.close)
  const highs = rawHist.map(h => h.high)
  const lows = rawHist.map(h => h.low)
  const opens = rawHist.map(h => h.open)

  // ECharts Candlestick: [open, close, lowest, highest]
  const klineData = rawHist.map(h => [h.open, h.close, h.low, h.high])

  // 成交量序列（含期货持仓量 / ΔOI / 涨跌方向）
  const oiValues = rawHist.map(h => h.hold ?? null)
  const volumes = rawHist.map((h, i) => {
    const priceUp = h.close >= h.open
    // ΔOI = 当根持仓 - 前根持仓（增仓为正，减仓为负）
    const prevOI = i > 0 ? (rawHist[i - 1].hold ?? null) : null
    const deltaOI = (prevOI != null && h.hold != null) ? h.hold - prevOI : null
    return {
      value:    h.volume,
      oi:       h.hold ?? null,        // 持仓量（期货独有）
      deltaOI,                          // 持仓变化（增仓正，减仓负）
      priceUp,                          // 当根涨跌方向
      itemStyle: { color: priceUp ? UP + '44' : DOWN + '44' },
    }
  })

  // 2. 主图叠加指标 (MA, BOLL)
  const maData = {
    ma5: calcMA(closes, 5),
    ma10: calcMA(closes, 10),
    ma20: calcMA(closes, 20),
  }

  const bollParams = indicatorParams.BOLL || { period: 20, stdDev: 2 }
  const bollData = calcBOLL(closes, bollParams.period, bollParams.stdDev)

  // 3. 副图指标 (MACD, KDJ, RSI)
  const subChartData = {}

  // MACD
  const macdParams = indicatorParams.MACD || { fast: 12, slow: 26, signal: 9 }
  subChartData.MACD = calcMACD(closes, macdParams.fast, macdParams.slow, macdParams.signal)

  // KDJ
  const kdjParams = indicatorParams.KDJ || { n: 9 }
  subChartData.KDJ = calcKDJ(closes, highs, lows, kdjParams.n)

  // RSI
  const rsiParams = indicatorParams.RSI || { period: 14 }
  subChartData.RSI = calcRSI(closes, rsiParams.period)

  // OBV（能量潮）
  const obvParams = indicatorParams.OBV || {}
  subChartData.OBV = calcOBV(closes, volumes)

  // DMI（趋向指标）
  const dmiParams = indicatorParams.DMI || { period: 14 }
  subChartData.DMI = calcDMI(highs, lows, closes, dmiParams.period)

  // CCI（顺势指标）
  const cciParams = indicatorParams.CCI || { period: 14 }
  const cciRaw = calcCCI ? calcCCI(closes, highs, lows, cciParams.period) : null
  if (cciRaw) subChartData.CCI = cciRaw

  // 4. 叠加标的处理 (对比图)
  let overlaySeriesData = []
  if (overlayData.length > 0) {
    const ovMap = {}
    for (const d of overlayData) {
      if (d.date && d.close != null) ovMap[d.date] = d.close
    }
    // 按主图时间对齐，未找到的日期填充 null
    overlaySeriesData = rawHist.map((h, i) => [i, ovMap[h.date] ?? null])
  }

  // 5. Y 轴极值计算 (用于自适应优化)
  const yMin = +(Math.min(...closes) * 0.997).toFixed(2)
  const yMax = +(Math.max(...closes) * 1.003).toFixed(2)

  // 6. 叠加标的 Y 轴自适应（双 Y 轴核心）
  //    策略：若叠加数据与主图量级差异 > 10x，切换为 min-max 归一化显示（0~100 范围）
  //    用途：股债跷跷板（沪深300≈4000点 vs 10年国债收益率≈2.5%）
  let overlayYAxis = null
  if (overlayData.length > 0) {
    const ovCloses = overlayData.map(d => d.close).filter(v => v != null)
    if (ovCloses.length > 0) {
      const ovMin = Math.min(...ovCloses)
      const ovMax = Math.max(...ovCloses)
      const mainRange = yMax - yMin
      const ovRange = ovMax - ovMin

      if (mainRange > 0 && ovRange > 0 && (mainRange / ovRange > 10 || ovRange / mainRange > 10)) {
        // 量级差异过大：使用归一化右侧 Y 轴（0~100 范围）
        overlayYAxis = { type: 'normalized', min: ovMin, max: ovMax }
      } else {
        // 量级相近：使用原始值右侧 Y 轴（双轴各自用真实值）
        overlayYAxis = { type: 'original' }
      }
    }
  }

  // overlayYAxis 返回 ECharts 原生 yAxis 配置对象，供调用方直接注入到 grid + yAxis 数组
  // 右侧双轴：主轴在 left='55'，对比轴在 right='8'，关闭网格线防止视觉干扰
  const _rawOverlayYAxis = overlayYAxis ? {
    scale: true,
    splitLine: { show: false },
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: {
      color: '#94a3b8',
      fontSize: 10,
      formatter: (v) => v >= 1000 ? (v / 1000).toFixed(1) + 'k' : v.toFixed(2),
    },
    position: 'right',
  } : null

  return {
    isEmpty: false,
    times,
    klineData,
    volumes,
    maData,
    bollData,
    subChartData,
    overlaySeriesData,   // [[index, price], ...] 按主图时间轴对齐
    overlayYAxis: _rawOverlayYAxis,  // ECharts yAxis 配置对象（可注入）
    yMin,
    yMax,
  }
}

/**
 * 构建对比标的的 ECharts series 片段（用于注入到主图 Option）
 * 返回结构：{ series: [{ name, type:'line', data, yAxisIndex:1, ... }], hasOverlay: bool }
 * 调用方只需将 series 数组 spread 到主图 series 中，并将 overlayYAxis push 到 yAxis 数组即可
 *
 * @param {Array}  rawHist     - 主图历史数据
 * @param {Array}  overlayData - 对比标的原始数据 [{date, close, name?}, ...]
 * @param {String} color       - 对比线颜色（默认亮橙色 #f97316）
 * @returns {{ series: Array, hasOverlay: boolean }}
 */
export function buildOverlaySeries(rawHist, overlayData, color = '#f97316') {
  if (!rawHist?.length || !overlayData?.length) return { series: [], hasOverlay: false }

  // 构建 {date -> close} 快速查找表
  const ovMap = {}
  for (const d of overlayData) {
    if (d.date && d.close != null) ovMap[d.date] = d.close
  }

  // 按主图时间轴对齐，index 对应主图数据下标（用于 xAxis index 对齐）
  const compareData = rawHist.map((h, i) => [i, ovMap[h.date] ?? null])

  // 过滤掉全 null 的头尾段（避免对比线在无数据区域突兀延伸）
  const firstValid = compareData.findIndex(d => d[1] !== null)
  const lastValid = compareData.length - 1 - [...compareData].reverse().findIndex(d => d[1] !== null)
  const trimmed = firstValid >= 0 ? compareData.slice(firstValid, lastValid + 1) : []

  return {
    hasOverlay: true,
    series: [{
      name: '对比',
      type: 'line',
      data: trimmed,
      yAxisIndex: 1,           // 绑定右侧 Y 轴
      symbol: 'none',         // 关闭小圆点，保持图表清爽
      lineStyle: { color, width: 1.5, type: 'solid' },
      itemStyle: { color },
      tooltip: { show: true },
      z: 3,                   // 渲染在 K 线（z=2）之上
      smooth: false,
      sampling: 'lttb',       // 大数据下采样
    }],
  }
}
