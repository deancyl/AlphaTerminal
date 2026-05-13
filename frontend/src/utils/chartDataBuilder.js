// frontend/src/utils/chartDataBuilder.js
import { calcMA, calcBOLL, calcMACD, calcKDJ, calcRSI, calcOBV, calcDMI, calcCCI } from './indicators.js'
import { buildXAxisLabels } from './symbols.js'
import { UP, DOWN } from './indicators.js'
import { safeNumber } from './typeCoercion.js'
import { indicatorWorker } from '../composables/useIndicatorWorker.js'

/**
 * 将原始 K 线数据转换为图表渲染所需的全套结构化数据
 * @param {Array} rawHist - 原始历史数据 [{date, open, close, high, low, volume, ...}]
 * @param {String} period - 当前周期 (daily, 1min, etc.)
 * @param {Object} indicatorParams - 指标参数配置 { MACD: { fast: 12, slow: 26, signal: 9 }, BOLL: {...}, ... }
 * @param {Array} overlayData - (可选) 叠加标的的数据
 * @param {Object} options - { useWorker: boolean, timeout: number }
 * @returns {Object|Promise<Object>} 结构化图表数据 (async if useWorker=true)
 */
export function buildChartData(rawHist, period, indicatorParams = {}, overlayData = [], options = {}) {
  if (!rawHist || !rawHist.length) {
    return { isEmpty: true }
  }

  const { useWorker = false, timeout = 5000 } = options

  // 1. 基础 X 轴与 K线序列
  const times = buildXAxisLabels(rawHist, period)
  const closes = rawHist.map(h => safeNumber(h.close, null))
  const highs = rawHist.map(h => safeNumber(h.high, null))
  const lows = rawHist.map(h => safeNumber(h.low, null))
  const opens = rawHist.map(h => safeNumber(h.open, null))

  // ECharts Candlestick: [open, close, lowest, highest]
  const klineData = rawHist.map(h => [
    safeNumber(h.open, null),
    safeNumber(h.close, null),
    safeNumber(h.low, null),
    safeNumber(h.high, null)
  ])

  // 成交量序列（含期货持仓量 / ΔOI / 涨跌方向）
  const oiValues = rawHist.map(h => safeNumber(h.hold, null))
  const volumes = rawHist.map((h, i) => {
    const closeVal = safeNumber(h.close, 0)
    const openVal = safeNumber(h.open, 0)
    const priceUp = closeVal >= openVal
    const prevOI = i > 0 ? safeNumber(rawHist[i - 1].hold, null) : null
    const currOI = safeNumber(h.hold, null)
    const deltaOI = (prevOI != null && currOI != null) ? currOI - prevOI : null
    return {
      value:    safeNumber(h.volume, 0),
      oi:       currOI,
      deltaOI,
      priceUp,
      itemStyle: { color: priceUp ? UP + '44' : DOWN + '44' },
    }
  })

  // Filter out NaN values for indicator calculations
  const validCloses = closes.filter(v => v != null && !isNaN(v))
  const validHighs = highs.filter(v => v != null && !isNaN(v))
  const validLows = lows.filter(v => v != null && !isNaN(v))
  const volumesForOBV = rawHist.map(h => safeNumber(h.volume, 0))

  // Worker-based calculation (async)
  if (useWorker && indicatorWorker.isAvailable()) {
    return buildChartDataWithWorker(
      rawHist, times, klineData, volumes, closes, highs, lows, volumesForOBV,
      indicatorParams, overlayData, timeout
    )
  }

  // Main thread calculation (sync fallback)
  return buildChartDataSync(
    rawHist, times, klineData, volumes, closes, highs, lows, volumesForOBV,
    indicatorParams, overlayData, validCloses
  )
}

/**
 * Build chart data using Web Worker (async)
 */
async function buildChartDataWithWorker(
  rawHist, times, klineData, volumes, closes, highs, lows, volumesForOBV,
  indicatorParams, overlayData, timeout
) {
  const workerData = { closes, highs, lows, volumes: volumesForOBV }
  const workerParams = {
    bollPeriod: indicatorParams.BOLL?.period || 20,
    bollStdDev: indicatorParams.BOLL?.stdDev || 2,
    macdFast: indicatorParams.MACD?.fast || 12,
    macdSlow: indicatorParams.MACD?.slow || 26,
    macdSignal: indicatorParams.MACD?.signal || 9,
    kdjN: indicatorParams.KDJ?.n || 9,
    rsiPeriod: indicatorParams.RSI?.period || 14,
    dmiPeriod: indicatorParams.DMI?.period || 14,
    cciPeriod: indicatorParams.CCI?.period || 14,
  }

  try {
    const indicators = await indicatorWorker.calculateAll(workerData, workerParams, { timeout })

    // Build result with worker-calculated indicators
    const result = buildChartResult(
      rawHist, times, klineData, volumes, closes,
      indicators, indicatorParams, overlayData
    )

    return result
  } catch (e) {
    console.warn('[chartDataBuilder] Worker failed, falling back to sync:', e.message)
    // Fallback to sync calculation
    const validCloses = closes.filter(v => v != null && !isNaN(v))
    return buildChartDataSync(
      rawHist, times, klineData, volumes, closes, highs, lows, volumesForOBV,
      indicatorParams, overlayData, validCloses
    )
  }
}

/**
 * Build chart data on main thread (sync)
 */
function buildChartDataSync(
  rawHist, times, klineData, volumes, closes, highs, lows, volumesForOBV,
  indicatorParams, overlayData, validCloses
) {
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
  subChartData.OBV = calcOBV(closes, volumesForOBV)

  // DMI（趋向指标）
  const dmiParams = indicatorParams.DMI || { period: 14 }
  subChartData.DMI = calcDMI(highs, lows, closes, dmiParams.period)

  // CCI（顺势指标）
  const cciParams = indicatorParams.CCI || { period: 14 }
  const cciRaw = calcCCI ? calcCCI(closes, highs, lows, cciParams.period) : null
  if (cciRaw) subChartData.CCI = cciRaw

  const indicators = {
    maData,
    bollData,
    subChartData,
  }

  return buildChartResult(
    rawHist, times, klineData, volumes, closes,
    indicators, indicatorParams, overlayData
  )
}

/**
 * Build final chart result object
 */
function buildChartResult(
  rawHist, times, klineData, volumes, closes,
  indicators, indicatorParams, overlayData
) {
  // Extract indicators (from worker or sync)
  const maData = indicators.maData || {
    ma5: indicators.ma5,
    ma10: indicators.ma10,
    ma20: indicators.ma20,
  }
  const bollData = indicators.bollData || indicators.boll
  const subChartData = indicators.subChartData || {
    MACD: indicators.macd,
    KDJ: indicators.kdj,
    RSI: indicators.rsi,
    OBV: indicators.obv,
    DMI: indicators.dmi,
    CCI: indicators.cci,
  }

  // 4. 叠加标的处理 (对比图)
  let overlaySeriesData = []
  if (overlayData.length > 0) {
    const ovMap = {}
    for (const d of overlayData) {
      const closeVal = safeNumber(d.close, null)
      if (d.date && closeVal != null) ovMap[d.date] = closeVal
    }
    overlaySeriesData = rawHist.map((h, i) => [i, ovMap[h.date] ?? null])
  }

  // 过滤无效值，计算有效数据的极值
  const validCloses = closes.filter(v => v != null && !isNaN(v))
  if (validCloses.length === 0) {
    return { isEmpty: true }
  }

  let yMin = validCloses[0], yMax = validCloses[0]
  for (let i = 1; i < validCloses.length; i++) {
    if (validCloses[i] < yMin) yMin = validCloses[i]
    if (validCloses[i] > yMax) yMax = validCloses[i]
  }
  yMin = +(yMin * 0.997).toFixed(2)
  yMax = +(yMax * 1.003).toFixed(2)

  // 6. 叠加标的 Y 轴自适应（双 Y 轴核心）
  let overlayYAxis = null
  if (overlayData.length > 0) {
    const ovCloses = overlayData.map(d => safeNumber(d.close, null)).filter(v => v != null)
    if (ovCloses.length > 0) {
      let ovMin = ovCloses[0], ovMax = ovCloses[0]
      for (let i = 1; i < ovCloses.length; i++) {
        if (ovCloses[i] < ovMin) ovMin = ovCloses[i]
        if (ovCloses[i] > ovMax) ovMax = ovCloses[i]
      }
      const mainRange = yMax - yMin
      const ovRange = ovMax - ovMin

      if (mainRange > 0 && ovRange > 0 && (mainRange / ovRange > 10 || ovRange / mainRange > 10)) {
        overlayYAxis = { type: 'normalized', min: ovMin, max: ovMax }
      } else {
        overlayYAxis = { type: 'original' }
      }
    }
  }

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
    overlaySeriesData,
    overlayYAxis: _rawOverlayYAxis,
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

  const ovMap = {}
  for (const d of overlayData) {
    const closeVal = safeNumber(d.close, null)
    if (d.date && closeVal != null) ovMap[d.date] = closeVal
  }

  const compareData = rawHist.map((h, i) => [i, ovMap[h.date] ?? null])

  const firstValid = compareData.findIndex(d => d[1] !== null)
  const lastValid = compareData.length - 1 - [...compareData].reverse().findIndex(d => d[1] !== null)
  const trimmed = firstValid >= 0 ? compareData.slice(firstValid, lastValid + 1) : []

  return {
    hasOverlay: true,
    series: [{
      name: '对比',
      type: 'line',
      data: trimmed,
      yAxisIndex: 1,
      symbol: 'none',
      lineStyle: { color, width: 1.5, type: 'solid' },
      itemStyle: { color },
      tooltip: { show: true },
      z: 3,
      smooth: false,
      sampling: 'lttb',
    }],
  }
}