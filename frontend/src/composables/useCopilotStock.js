import { searchStock, getMarketOverview } from '../services/copilotData.js'
import { generateAnalysisReport } from '../services/copilotAnalysis.js'
import { formatAnalysisReport, formatSearchResults } from '../services/copilotResponse.js'

export async function analyzeStock(keyword) {
  try {
    const results = await searchStock(keyword)
    if (results.length === 0) return { success: false, error: `未找到「${keyword}」相关的股票` }
    if (results.length === 1) {
      const stock = results[0]
      const overview = await getMarketOverview()
      const report = generateAnalysisReport(stock, overview)
      return { success: true, data: formatAnalysisReport(report) }
    }
    return { success: true, data: formatSearchResults(results, keyword) }
  } catch (e) {
    return { success: false, error: `分析失败: ${e.message}` }
  }
}

export async function openStock(keyword) {
  try {
    const results = await searchStock(keyword)
    if (results.length === 0) return { success: false, error: `未找到「${keyword}」相关的股票` }
    const stock = results[0]
    return { 
      success: true, 
      data: { symbol: stock.symbol, name: stock.name },
      message: `正在打开「${stock.name}(${stock.symbol})」的K线图...`
    }
  } catch (e) {
    return { success: false, error: `打开失败: ${e.message}` }
  }
}

export async function compareStocks(keywords) {
  try {
    const stocks = []
    for (const kw of keywords) {
      const results = await searchStock(kw)
      if (results.length > 0) stocks.push(results[0])
    }
    if (stocks.length < 2) return { success: false, error: '对比需要至少两只股票' }
    const text = formatCompareStocks(stocks)
    return { success: true, data: { stocks, text, symbols: stocks.map(s => s.symbol) } }
  } catch (e) {
    return { success: false, error: `对比失败: ${e.message}` }
  }
}

function formatCompareStocks(stocks) {
  const lines = ['📊 【个股对比】\n', '─'.repeat(45), '代码       名称            价格', '─'.repeat(45)]
  for (const s of stocks) {
    const code = (s.symbol || '').padEnd(10)
    const name = (s.name || '').padEnd(12)
    const price = s.price ? `¥${s.price.toFixed(2)}` : 'N/A'
    lines.push(`${code}${name}  ${price}`)
  }
  return lines.join('\n')
}
