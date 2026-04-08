/**
 * CopilotAnalysis - 技术分析引擎
 * 
 * 提供基础的技术分析功能
 */

/**
 * 计算简单移动平均
 */
export function calcSMA(data, period) {
  if (!data || data.length < period) return []
  const result = []
  for (let i = period - 1; i < data.length; i++) {
    const sum = data.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0)
    result.push(sum / period)
  }
  return result
}

/**
 * 计算 RSI (相对强弱指标)
 * @param data 收盘价数组
 * @param period RSI周期 (默认14)
 */
export function calcRSI(data, period = 14) {
  if (!data || data.length < period + 1) return null
  
  const changes = []
  for (let i = 1; i < data.length; i++) {
    changes.push(data[i] - data[i - 1])
  }
  
  let avgGain = 0
  let avgLoss = 0
  
  // 初始平均值
  for (let i = 0; i < period; i++) {
    if (changes[i] > 0) avgGain += changes[i]
    else avgLoss -= changes[i]
  }
  avgGain /= period
  avgLoss /= period
  
  const rsiValues = [100 - (100 / (1 + avgGain / (avgLoss || 0.001)))]
  
  // 后续值使用平滑
  for (let i = period; i < changes.length; i++) {
    const change = changes[i]
    avgGain = (avgGain * (period - 1) + (change > 0 ? change : 0)) / period
    avgLoss = (avgLoss * (period - 1) + (change < 0 ? -change : 0)) / period
    const rs = avgGain / (avgLoss || 0.001)
    rsiValues.push(100 - (100 / (1 + rs)))
  }
  
  return {
    values: rsiValues,
    current: rsiValues[rsiValues.length - 1],
    signal: rsiValues[rsiValues.length - 1] > 70 ? 'overbought' : rsiValues[rsiValues.length - 1] < 30 ? 'oversold' : 'neutral'
  }
}

/**
 * 判断趋势
 */
export function analyzeTrend(prices) {
  if (!prices || prices.length < 5) return null
  
  const recent = prices.slice(-5)
  const ma5 = recent.reduce((a, b) => a + b, 0) / 5
  const current = prices[prices.length - 1]
  
  // 简单趋势判断
  const isUp = current > ma5
  const momentum = (current - prices[prices.length - 5]) / prices[prices.length - 5] * 100
  
  return {
    direction: isUp ? '上涨' : '下跌',
    momentum: momentum.toFixed(2) + '%',
    strength: Math.abs(momentum) > 5 ? '强势' : Math.abs(momentum) > 2 ? '温和' : '盘整',
    current,
    ma5: ma5.toFixed(2),
  }
}

/**
 * 识别支撑位和压力位
 */
export function findSupportResistance(prices, period = 20) {
  if (!prices || prices.length < period) return { support: null, resistance: null }
  
  const recent = prices.slice(-period)
  const min = Math.min(...recent)
  const max = Math.max(...recent)
  const current = prices[prices.length - 1]
  
  // 找最近的支撑（近期低点附近）
  const supports = recent.filter(p => p <= min * 1.02)
  const resistances = recent.filter(p => p >= max * 0.98)
  
  return {
    support: supports.length > 0 ? Math.max(...supports) : min,
    resistance: resistances.length > 0 ? Math.min(...resistances) : max,
    current,
    range: ((max - min) / min * 100).toFixed(2) + '%',
  }
}

/**
 * 涨跌统计
 */
export function analyzeChangeStats(stocks) {
  if (!stocks || !Array.isArray(stocks)) return null
  
  const limitUp = stocks.filter(s => s.change_pct >= 9.9).length
  const limitDown = stocks.filter(s => s.change_pct <= -9.9).length
  const rising = stocks.filter(s => s.change_pct > 0).length
  const falling = stocks.filter(s => s.change_pct < 0).length
  const flat = stocks.length - rising - falling
  
  const avgChange = stocks.reduce((sum, s) => sum + (s.change_pct || 0), 0) / stocks.length
  
  return {
    total: stocks.length,
    rising,
    falling,
    flat,
    limitUp,
    limitDown,
    avgChange: avgChange.toFixed(2) + '%',
    marketBreadth: rising > falling ? '偏多' : rising < falling ? '偏空' : '中性',
  }
}

/**
 * 生成综合分析报告
 */
export function generateAnalysisReport(stockData, priceHistory = []) {
  if (!stockData) return null
  
  const { name, symbol, price, change_pct, volume, amount } = stockData
  
  // 基础信息
  const report = {
    basic: {
      name,
      symbol,
      price: price?.toFixed(2) || 'N/A',
      change: change_pct ? (change_pct >= 0 ? '+' : '') + change_pct.toFixed(2) + '%' : 'N/A',
      volume: formatVolume(volume),
      amount: formatAmount(amount),
    },
  }
  
  // 技术分析（如果有历史数据）
  if (priceHistory && priceHistory.length >= 20) {
    const prices = priceHistory.map(k => k.close)
    report.trend = analyzeTrend(prices)
    report.sr = findSupportResistance(prices)
    report.rsi = calcRSI(prices)
  }
  
  // 市场位置判断
  if (report.trend && report.sr) {
    const { current, support, resistance } = report.sr
    if (current >= resistance * 0.98) {
      report.position = '⚠️ 接近压力位，谨慎追高'
    } else if (current <= support * 1.02) {
      report.position = '📍 接近支撑位，关注反弹机会'
    } else {
      report.position = '📊 在支撑压力之间震荡整理'
    }
  }
  
  // 综合判断
  report.summary = generateSummary(report)
  
  return report
}

function generateSummary(report) {
  const parts = []
  
  // 涨跌判断
  const changeMatch = report.basic.change.match(/([+-]?[\d.]+)%/)
  const change = changeMatch ? parseFloat(changeMatch[1]) : 0
  
  if (change > 5) {
    parts.push('今日涨幅较大，需关注是否有利好消息支撑')
  } else if (change < -5) {
    parts.push('今日跌幅较大，需关注是否有系统性风险')
  } else if (change > 0) {
    parts.push('今日小幅上涨，市场表现平稳')
  } else if (change < 0) {
    parts.push('今日小幅调整，暂无明显趋势')
  } else {
    parts.push('今日基本持平')
  }
  
  // 趋势判断
  if (report.trend) {
    parts.push(`短期趋势${report.trend.direction}，动量${report.trend.momentum}，呈${report.trend.strength}${report.trend.direction}`)
  }
  
  // RSI 判断
  if (report.rsi) {
    const { current, signal } = report.rsi
    if (signal === 'overbought') {
      parts.push(`RSI=${current.toFixed(0)}，处于超买区域，有回调风险`)
    } else if (signal === 'oversold') {
      parts.push(`RSI=${current.toFixed(0)}，处于超卖区域，可能存在反弹机会`)
    } else {
      parts.push(`RSI=${current.toFixed(0)}，处于中性区域`)
    }
  }
  
  return parts.join('；') + '。'
}

function formatVolume(vol) {
  if (!vol) return 'N/A'
  if (vol >= 100000000) return (vol / 100000000).toFixed(2) + '亿'
  if (vol >= 10000) return (vol / 10000).toFixed(0) + '万'
  return vol.toString()
}

function formatAmount(amount) {
  if (!amount) return 'N/A'
  if (amount >= 100000000) return (amount / 100000000).toFixed(2) + '亿'
  if (amount >= 10000) return (amount / 10000).toFixed(0) + '万'
  return amount.toString()
}

/**
 * 格式化涨跌颜色
 */
export function formatChange(pct) {
  if (pct === undefined || pct === null) return { text: 'N/A', color: '' }
  const sign = pct >= 0 ? '+' : ''
  const color = pct > 0 ? '🔴' : pct < 0 ? '🟢' : '⚪'
  return { text: `${color}${sign}${pct.toFixed(2)}%`, color: pct >= 0 ? 'rise' : 'fall' }
}
