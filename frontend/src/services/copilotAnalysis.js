/**
 * CopilotAnalysis - 技术分析引擎
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
 * 计算 RSI
 */
export function calcRSI(data, period = 14) {
  if (!data || data.length < period + 1) return null
  
  const changes = []
  for (let i = 1; i < data.length; i++) {
    changes.push(data[i] - data[i - 1])
  }
  
  let avgGain = 0
  let avgLoss = 0
  
  for (let i = 0; i < period; i++) {
    if (changes[i] > 0) avgGain += changes[i]
    else avgLoss -= changes[i]
  }
  avgGain /= period
  avgLoss /= period
  
  const rsiValues = [100 - (100 / (1 + avgGain / (avgLoss || 0.001)))]
  
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
 * 简单趋势分析
 */
export function analyzeTrend(changePct) {
  if (changePct === null || changePct === undefined) {
    return { direction: '未知', strength: 'N/A', verdict: '数据不足' }
  }
  
  const abs = Math.abs(changePct)
  let direction, strength, verdict
  
  if (changePct > 0) {
    direction = '上涨'
    if (abs >= 5) { strength = '强势上涨'; verdict = '市场做多情绪高涨' }
    else if (abs >= 2) { strength = '温和上涨'; verdict = '市场表现良好' }
    else { strength = '小幅上涨'; verdict = '市场平稳偏多' }
  } else if (changePct < 0) {
    direction = '下跌'
    if (abs >= 5) { strength = '大幅下跌'; verdict = '市场恐慌情绪蔓延' }
    else if (abs >= 2) { strength = '温和下跌'; verdict = '市场有所回调' }
    else { strength = '小幅下跌'; verdict = '市场平稳偏弱' }
  } else {
    direction = '持平'
    strength = '横盘'
    verdict = '市场观望情绪浓厚'
  }
  
  return { direction, strength, verdict }
}

/**
 * 市场情绪判断
 */
export function analyzeMarketSentiment(indices, sectors) {
  if (!indices || indices.length === 0) {
    return { sentiment: '未知', score: 0, description: '数据不足' }
  }
  
  // 计算平均涨跌
  const avgChange = indices.reduce((sum, i) => sum + (i.change_pct || 0), 0) / indices.length
  
  // 统计涨跌数量
  const risingIndices = indices.filter(i => i.change_pct > 0).length
  const risingRatio = risingIndices / indices.length
  
  // 板块统计
  let sectorStrength = 0
  if (sectors && sectors.length > 0) {
    const topSector = sectors.reduce((a, b) => (a.change_pct || 0) > (b.change_pct || 0) ? a : b)
    sectorStrength = topSector.change_pct || 0
  }
  
  // 综合评分 (-100 到 100)
  const score = Math.round(avgChange * 20 + (risingRatio - 0.5) * 40 + sectorStrength * 2)
  
  let sentiment, description
  if (score >= 60) {
    sentiment = '🔥 强势看多'
    description = '市场做多情绪高涨，趋势强劲'
  } else if (score >= 30) {
    sentiment = '📈 温和看多'
    description = '市场表现良好，趋势向上'
  } else if (score >= 10) {
    sentiment = '➡️ 谨慎偏多'
    description = '市场平稳，方向不明确'
  } else if (score >= -10) {
    sentiment = '➡️ 观望'
    description = '市场交投清淡，等待方向'
  } else if (score >= -30) {
    sentiment = '➡️ 谨慎偏空'
    description = '市场有所回调'
  } else if (score >= -60) {
    sentiment = '📉 温和看空'
    description = '市场表现疲软'
  } else {
    sentiment = '💥 强势看空'
    description = '市场恐慌情绪蔓延'
  }
  
  return { sentiment, score, description, avgChange, risingRatio }
}

/**
 * 生成综合分析报告
 */
export function generateAnalysisReport(stockData, marketData = null) {
  if (!stockData) return null
  
  const { name, symbol, price, change_pct } = stockData
  
  const report = {
    basic: {
      name: name || symbol,
      symbol,
      price: price ? `¥${price.toFixed(2)}` : '获取中...',
      change: change_pct !== null && change_pct !== undefined 
        ? `${change_pct >= 0 ? '+' : ''}${change_pct.toFixed(2)}%`
        : '获取中...',
    },
    trend: analyzeTrend(change_pct),
  }
  
  // 添加市场背景
  if (marketData) {
    report.market = analyzeMarketSentiment(marketData.indices, marketData.sectors)
  }
  
  // 生成投资建议
  report.suggestion = generateSuggestion(report)
  
  return report
}

function generateSuggestion(report) {
  const parts = []
  const change = report.trend
  
  // 短期走势判断
  if (change.direction === '上涨') {
    if (change.strength.includes('强势')) {
      parts.push('短期走势强劲，注意获利了结风险')
    } else {
      parts.push('短期表现良好，可继续持有')
    }
  } else if (change.direction === '下跌') {
    if (change.strength.includes('大幅')) {
      parts.push('短期风险较大，建议观望')
    } else {
      parts.push('短期有所回调，关注支撑位')
    }
  } else {
    parts.push('短期横盘整理，等待方向明确')
  }
  
  // 市场情绪
  if (report.market) {
    if (report.market.score >= 30) {
      parts.push('整体市场氛围偏暖')
    } else if (report.market.score <= -30) {
      parts.push('整体市场氛围偏冷，注意风险')
    }
  }
  
  return parts.join('；') + '。'
}

/**
 * 格式化涨跌颜色
 */
export function formatChange(pct) {
  if (pct === undefined || pct === null) return { text: 'N/A', color: '' }
  const sign = pct >= 0 ? '+' : ''
  const emoji = pct > 0 ? '🔴' : pct < 0 ? '🟢' : '⚪'
  return { text: `${emoji}${sign}${pct.toFixed(2)}%`, color: pct >= 0 ? 'rise' : 'fall' }
}
