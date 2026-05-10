import {
  getMarketOverview,
  getSectors,
  getLimitUpStocks,
  getLimitDownStocks,
  getUnusualStocks,
  getTopSectors,
  getNorthFlowRanking,
  getLimitSummary,
} from '../services/copilotData.js'

import {
  formatMarketOverview,
  formatTopSectors,
  formatNorthFlowRanking,
  formatLimitUp,
  formatLimitDown,
  formatUnusualStocks,
  formatMarketSentiment,
} from '../services/copilotResponse.js'

import { analyzeMarketSentiment } from '../services/copilotAnalysis.js'

export async function showMarket() {
  const [overview, sectors, limitSummary] = await Promise.all([
    getMarketOverview(),
    getSectors(),
    getLimitSummary(),
  ])
  
  const text = formatMarketOverview(overview)
  const sentiment = analyzeMarketSentiment(overview?.indices, sectors)
  const sentimentText = formatMarketSentiment({ market: sentiment })
  
  let limitText = ''
  if (limitSummary && (limitSummary.zt_count > 0 || limitSummary.dt_count > 0)) {
    limitText = `\n📌 【涨跌停汇总】\n涨停: ${limitSummary.zt_count} 只\n跌停: ${limitSummary.dt_count} 只\n市场情绪: ${limitSummary.market_sentiment || '分析中'}`
  }
  
  const topSectors = await getTopSectors(3)
  return text + '\n\n' + sentimentText + limitText + '\n\n' + formatTopSectors(topSectors)
}

export async function showSectors() {
  const [sectors, limitSummary] = await Promise.all([getSectors(), getLimitSummary()])
  
  const lines = [formatTopSectors({ top: sectors, bottom: sectors })]
  
  if (limitSummary?.zt_industry) {
    const topInd = Object.entries(limitSummary.zt_industry).slice(0, 3)
    if (topInd.length > 0) {
      lines.push('', '🏆 【涨停集中板块】')
      topInd.forEach(([ind, count]) => lines.push(`  ${ind}: ${count}只涨停`))
    }
  }
  
  return lines.join('\n')
}

export async function showNorthFlow() {
  const data = await getNorthFlowRanking()
  return formatNorthFlowRanking(data)
}

export async function showLimitUp() {
  const [stocks, summary] = await Promise.all([getLimitUpStocks(), getLimitSummary()])
  return formatLimitUp(stocks, summary)
}

export async function showLimitDown() {
  const stocks = await getLimitDownStocks()
  return formatLimitDown(stocks)
}

export async function showUnusual() {
  const [stocks, limitSummary] = await Promise.all([getUnusualStocks(), getLimitSummary()])
  
  const lines = [formatUnusualStocks(stocks)]
  
  if (limitSummary?.strongest?.length > 0) {
    lines.push('', '🔥 【强势股】换手率最高:')
    limitSummary.strongest.slice(0, 3).forEach(s => {
      lines.push(`  ${s.name}: 换手率${s.turnover_rate?.toFixed(1)}% 涨幅${s.change_pct?.toFixed(2)}%`)
    })
  }
  
  return lines.join('\n')
}
