// frontend/src/utils/chartDataBuilder.js
import { calcMA, calcBOLL, calcMACD, calcKDJ, calcRSI } from './indicators.js'
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

  // 成交量序列 (附带涨跌颜色；期货额外附带持仓量 OI)
  const volumes = rawHist.map(h => ({
    value: h.volume,
    oi:    h.hold ?? null,   // 持仓量（期货独有）
    itemStyle: { color: h.close >= h.open ? UP + '44' : DOWN + '44' }
  }))

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

  // 4. 叠加标的处理 (对比图)
  let overlaySeriesData = []
  if (overlayData.length > 0) {
    const ovMap = {}
    for (const d of overlayData) {
      ovMap[d.date] = d.close
    }
    // 按主图时间对齐
    overlaySeriesData = rawHist.map((h, i) => [i, ovMap[h.date] ?? null])
  }

  // 5. Y 轴极值计算 (用于自适应优化)
  const yMin = +(Math.min(...closes) * 0.997).toFixed(2)
  const yMax = +(Math.max(...closes) * 1.003).toFixed(2)

  return {
    isEmpty: false,
    times,
    klineData,
    volumes,
    maData,
    bollData,
    subChartData,
    overlaySeriesData,
    yMin,
    yMax
  }
}
