/**
 * indicators.js — 前端指标计算库
 * 基于 AlphaTerminal IndexLineChart.vue 抽取并增强
 * 所有指标计算均为纯函数，输入 OHLCV 数组，输出指标数组
 */

export const UP = '#ef232a'
export const DOWN = '#14b143'

// ─────────────────────────────────────────────────────────────────
// 基础工具
// ─────────────────────────────────────────────────────────────────

function isValid(v) {
  return v != null && !isNaN(v) && v !== '-' && v !== ''
}

/** 计算简单移动平均线 */
export function calcMA(data, n) {
  return data.map((_, i) => {
    if (i < n - 1) return null
    const slice = data.slice(i - n + 1, i + 1)
    return +(slice.reduce((a, b) => a + b, 0) / n).toFixed(3)
  })
}

/** 计算指数移动平均线 EMA */
export function calcEMA(data, n) {
  const k = 2 / (n + 1)
  const result = []
  let ema = data[0]
  for (let i = 0; i < data.length; i++) {
    ema = i === 0 ? data[0] : data[i] * k + ema * (1 - k)
    result.push(+ema.toFixed(4))
  }
  return result
}

/** 计算布林带 */
export function calcBOLL(closes, period = 20, stdDev = 2) {
  const mid = [], upper = [], lower = []
  for (let i = 0; i < closes.length; i++) {
    if (i < period - 1) {
      mid.push(null); upper.push(null); lower.push(null)
      continue
    }
    const slice = closes.slice(i - period + 1, i + 1)
    const mean = slice.reduce((a, b) => a + b, 0) / period
    const std = Math.sqrt(slice.reduce((a, b) => a + (b - mean) ** 2, 0) / period)
    mid.push(+mean.toFixed(3))
    upper.push(+(mean + stdDev * std).toFixed(3))
    lower.push(+(mean - stdDev * std).toFixed(3))
  }
  return { mid, upper, lower }
}

/** 计算 MACD */
export function calcMACD(closes, fast = 12, slow = 26, signal = 9) {
  const ema12 = calcEMA(closes, fast)
  const ema26 = calcEMA(closes, slow)
  const dif = ema12.map((v, i) => +(v - ema26[i]).toFixed(4))
  const dea = calcEMA(dif, signal)
  const macd = dif.map((v, i) => +((v - dea[i]) * 2).toFixed(4))
  return { dif, dea, macd }
}

/** 计算 KDJ */
export function calcKDJ(closes, highs, lows, n = 9) {
  const k = [], d = [], j = []
  for (let i = 0; i < closes.length; i++) {
    if (i < n - 1) { k.push(null); d.push(null); j.push(null); continue }
    const rh = Math.max(...highs.slice(i - n + 1, i + 1))
    const rl = Math.min(...lows.slice(i - n + 1, i + 1))
    const rsv = rh === rl ? 50 : (closes[i] - rl) / (rh - rl) * 100
    const pk = k[i - 1] != null && k[i - 1] !== '-' ? k[i - 1] : 50
    const pd = d[i - 1] != null && d[i - 1] !== '-' ? d[i - 1] : 50
    const nk = +(2/3 * pk + 1/3 * rsv).toFixed(2)
    const nd = +(2/3 * pd + 1/3 * nk).toFixed(2)
    k.push(nk); d.push(nd); j.push(+(3 * nk - 2 * nd).toFixed(2))
  }
  return { k, d, j }
}

/** 计算 RSI */
export function calcRSI(closes, period = 14) {
  const rsi = []
  let gains = [], losses = []
  for (let i = 1; i < closes.length; i++) {
    const delta = closes[i] - closes[i - 1]
    gains.push(delta > 0 ? delta : 0)
    losses.push(delta < 0 ? -delta : 0)
  }
  for (let i = 0; i < closes.length; i++) {
    if (i < period) { rsi.push(null); continue }
    const gainSlice = gains.slice(i - period, i)
    const lossSlice = losses.slice(i - period, i)
    const avgGain = gainSlice.reduce((a, b) => a + b, 0) / period
    const avgLoss = lossSlice.reduce((a, b) => a + b, 0) / period
    if (avgLoss === 0) { rsi.push(100); continue }
    const rs = avgGain / avgLoss
    rsi.push(+(100 - 100 / (1 + rs)).toFixed(2))
  }
  return rsi
}

/** 计算威廉指标 WR */
export function calcWR(closes, highs, lows, n = 14) {
  return closes.map((_, i) => {
    if (i < n - 1) return null
    const rh = Math.max(...highs.slice(i - n + 1, i + 1))
    const rl = Math.min(...lows.slice(i - n + 1, i + 1))
    if (rh === rl) return 0
    return +((rh - closes[i]) / (rh - rl) * -100).toFixed(2)
  })
}

/** 计算均线乖离率 */
export function calcBIAS(closes, period = 20) {
  return closes.map((_, i) => {
    if (i < period - 1) return null
    const slice = closes.slice(i - period + 1, i + 1)
    const ma = slice.reduce((a, b) => a + b, 0) / period
    return +((closes[i] - ma) / ma * 100).toFixed(3)
  })
}

/**
 * 计算成交量加权平均价格 VWAP
 * 简化版：仅日线可用
 */
export function calcVWAP(closes, volumes) {
  let cumVol = 0, cumPV = 0
  return closes.map((c, i) => {
    cumPV += c * volumes[i]
    cumVol += volumes[i]
    return cumVol > 0 ? +(cumPV / cumVol).toFixed(3) : null
  })
}

/**
 * 计算能量潮 OBV
 */
export function calcOBV(closes, volumes) {
  let obv = 0
  return closes.map((c, i) => {
    if (i === 0) { obv = volumes[i]; return obv }
    if (c > closes[i - 1]) obv += volumes[i]
    else if (c < closes[i - 1]) obv -= volumes[i]
    return obv
  })
}
