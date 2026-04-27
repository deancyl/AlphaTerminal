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

/** 计算 KDJ（优化版：避免 spread 操作符大数组分配） */
export function calcKDJ(closes, highs, lows, n = 9) {
  const k = [], d = [], j = []
  for (let i = 0; i < closes.length; i++) {
    if (i < n - 1) { k.push(null); d.push(null); j.push(null); continue }
    // 优化：使用循环代替 Math.max(...arr) 避免大数组分配
    let rh = highs[i - n + 1], rl = lows[i - n + 1]
    for (let j = i - n + 2; j <= i; j++) {
      if (highs[j] > rh) rh = highs[j]
      if (lows[j] < rl) rl = lows[j]
    }
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
  if (closes.length < period + 1) {
    for (let i = 0; i < closes.length; i++) rsi.push(null)
    return rsi
  }
  let avgGain = 0, avgLoss = 0
  for (let i = 1; i <= period; i++) {
    const delta = closes[i] - closes[i - 1]
    if (delta > 0) avgGain += delta
    else avgLoss -= delta
  }
  avgGain /= period
  avgLoss /= period
  for (let i = 0; i < period; i++) rsi.push(null)
  rsi.push(avgLoss === 0 ? 100 : +(100 - 100 / (1 + avgGain / avgLoss)).toFixed(2))
  for (let i = period + 1; i < closes.length; i++) {
    const delta = closes[i] - closes[i - 1]
    avgGain = (avgGain * (period - 1) + (delta > 0 ? delta : 0)) / period
    avgLoss = (avgLoss * (period - 1) + (delta < 0 ? -delta : 0)) / period
    rsi.push(avgLoss === 0 ? 100 : +(100 - 100 / (1 + avgGain / avgLoss)).toFixed(2))
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

/** 计算 CCI（顺势指标） */
export function calcCCI(closes, highs, lows, n = 14) {
  return closes.map((_, i) => {
    if (i < n - 1) return null
    const tp = (highs[i] + lows[i] + closes[i]) / 3
    const window = closes.slice(i - n + 1, i + 1)
    const tpWindow = window.map((_, j) => (highs[i - n + 1 + j] + lows[i - n + 1 + j] + closes[i - n + 1 + j]) / 3)
    const sma = tpWindow.reduce((a, b) => a + b, 0) / n
    const mad = tpWindow.reduce((s, v) => s + Math.abs(v - sma), 0) / n
    if (mad === 0) return 0
    return +((tp - sma) / (0.015 * mad)).toFixed(2)
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


/**
 * 计算动向指标 DMI (Directional Movement Index)
 * 包括: PDI(+DI), MDI(-DI), ADX, ADXR
 */
export function calcDMI(highs, lows, closes, period = 14) {
  const len = highs.length
  const pdi = []
  const mdi = []
  const adx = []
  const dx = []
  
  // 计算真实波幅 TR
  const tr = []
  for (let i = 1; i < len; i++) {
    const hl = highs[i] - lows[i]
    const hc = Math.abs(highs[i] - closes[i - 1])
    const lc = Math.abs(lows[i] - closes[i - 1])
    tr.push(Math.max(hl, hc, lc))
  }
  
  // 计算+DM和-DM
  const plusDM = []
  const minusDM = []
  for (let i = 1; i < len; i++) {
    const up = highs[i] - highs[i - 1]
    const down = lows[i - 1] - lows[i]
    plusDM.push(up > down && up > 0 ? up : 0)
    minusDM.push(down > up && down > 0 ? down : 0)
  }
  
  // 计算平滑值
  const smooth = (arr, start, end) => {
    let sum = 0
    for (let i = start; i < end; i++) sum += arr[i]
    return sum
  }
  
  // 计算+DI和-DI
  for (let i = period; i < len; i++) {
    const trSum = smooth(tr, i - period, i)
    const plusDMSum = smooth(plusDM, i - period, i)
    const minusDMSum = smooth(minusDM, i - period, i)
    
    const pdiVal = trSum > 0 ? (plusDMSum / trSum) * 100 : 0
    const mdiVal = trSum > 0 ? (minusDMSum / trSum) * 100 : 0
    
    pdi.push(pdiVal)
    mdi.push(mdiVal)
    
    // 计算DX
    const dxVal = Math.abs(pdiVal - mdiVal) / (pdiVal + mdiVal) * 100
    dx.push(dxVal)
  }
  
  // 计算ADX
  for (let i = period; i < dx.length; i++) {
    const adxVal = dx.slice(i - period, i).reduce((a, b) => a + b, 0) / period
    adx.push(adxVal)
  }
  
  // 填充前面的null
  const pad = period * 2
  while (pdi.length < len) { pdi.unshift(null); mdi.unshift(null); adx.unshift(null) }
  
  return { pdi: pdi.slice(1), mdi: mdi.slice(1), adx: adx.slice(1) }
}


/**
 * 计算抛物线转向指标 SAR (Stop and Reverse)
 */
export function calcSAR(highs, lows, afStep = 0.02, afMax = 0.2) {
  const len = highs.length
  const sar = new Array(len).fill(null)
  
  if (len < 2) return sar
  
  // 初始化
  let trend = highs[1] > highs[0] ? 1 : -1  // 1=上涨, -1=下跌
  let af = afStep
  let ep = trend > 0 ? highs[0] : lows[0]  // 极值点
  sar[0] = trend > 0 ? lows[0] : highs[0]
  
  for (let i = 1; i < len; i++) {
    const prevSar = sar[i - 1]
    const prevEp = ep
    
    // 计算SAR
    let newSar = prevSar + af * (prevEp - prevSar)
    
    // 验证SAR是否在昨日价格范围内
    if (trend > 0) {
      if (newSar > lows[i - 1]) newSar = lows[i - 1]
      if (newSar > lows[i]) newSar = lows[i]
    } else {
      if (newSar < highs[i - 1]) newSar = highs[i - 1]
      if (newSar < highs[i]) newSar = highs[i]
    }
    
    sar[i] = newSar
    
    // 检查是否反转
    if (trend > 0) {
      if (lows[i] < newSar) {
        // 反转信号
        trend = -1
        sar[i] = ep
        ep = lows[i]
        af = afStep
      } else if (highs[i] > ep) {
        ep = highs[i]
        af = Math.min(af + afStep, afMax)
      }
    } else {
      if (highs[i] > newSar) {
        // 反转信号
        trend = 1
        sar[i] = ep
        ep = highs[i]
        af = afStep
      } else if (lows[i] < ep) {
        ep = lows[i]
        af = Math.min(af + afStep, afMax)
      }
    }
  }
  
  return sar
}
